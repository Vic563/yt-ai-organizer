"""Asynchronous transcript fetching with concurrent strategies"""

import asyncio
import logging
from typing import Optional, List, Dict, Any, Tuple
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
import aiohttp
from concurrent.futures import ThreadPoolExecutor

# Import existing transcript fetchers
from youtube_transcript_api import YouTubeTranscriptApi
from simple_transcript_fetcher import SimpleTranscriptFetcher
from ytdlp_transcript_fetcher import YtdlpTranscriptFetcher

logger = logging.getLogger(__name__)

@dataclass
class TranscriptResult:
    """Result of transcript fetch attempt"""
    video_id: str
    transcript: Optional[str]
    language: Optional[str]
    method: str
    success: bool
    error: Optional[str] = None
    fetch_time: float = 0.0

class TranscriptStrategy(ABC):
    """Abstract base class for transcript fetching strategies"""
    
    @abstractmethod
    async def fetch(self, video_id: str) -> TranscriptResult:
        """Fetch transcript for a video"""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name"""
        pass

class YouTubeTranscriptApiStrategy(TranscriptStrategy):
    """Strategy using youtube-transcript-api library"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=5)
    
    @property
    def name(self) -> str:
        return "youtube-transcript-api"
    
    def _fetch_sync(self, video_id: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Synchronous fetch for thread executor"""
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Try to get English transcript first
            try:
                transcript = transcript_list.find_transcript(['en'])
                text = ' '.join([item['text'] for item in transcript.fetch()])
                return text, 'en', None
            except:
                # Fall back to any available transcript
                for transcript in transcript_list:
                    text = ' '.join([item['text'] for item in transcript.fetch()])
                    return text, transcript.language_code, None
                    
        except Exception as e:
            return None, None, str(e)
    
    async def fetch(self, video_id: str) -> TranscriptResult:
        """Fetch transcript asynchronously"""
        start_time = asyncio.get_event_loop().time()
        
        loop = asyncio.get_event_loop()
        text, language, error = await loop.run_in_executor(
            self.executor, self._fetch_sync, video_id
        )
        
        fetch_time = asyncio.get_event_loop().time() - start_time
        
        return TranscriptResult(
            video_id=video_id,
            transcript=text,
            language=language,
            method=self.name,
            success=text is not None,
            error=error,
            fetch_time=fetch_time
        )

class SimpleTranscriptStrategy(TranscriptStrategy):
    """Strategy using simple transcript fetcher"""
    
    def __init__(self):
        self.fetcher = SimpleTranscriptFetcher()
        self.executor = ThreadPoolExecutor(max_workers=5)
    
    @property
    def name(self) -> str:
        return "simple-fetcher"
    
    async def fetch(self, video_id: str) -> TranscriptResult:
        """Fetch transcript asynchronously"""
        start_time = asyncio.get_event_loop().time()
        
        loop = asyncio.get_event_loop()
        try:
            transcript = await loop.run_in_executor(
                self.executor, self.fetcher.fetch_transcript, video_id
            )
            
            fetch_time = asyncio.get_event_loop().time() - start_time
            
            if transcript:
                return TranscriptResult(
                    video_id=video_id,
                    transcript=transcript,
                    language='en',  # Assuming English
                    method=self.name,
                    success=True,
                    fetch_time=fetch_time
                )
            else:
                return TranscriptResult(
                    video_id=video_id,
                    transcript=None,
                    language=None,
                    method=self.name,
                    success=False,
                    error="No transcript found",
                    fetch_time=fetch_time
                )
        except Exception as e:
            fetch_time = asyncio.get_event_loop().time() - start_time
            return TranscriptResult(
                video_id=video_id,
                transcript=None,
                language=None,
                method=self.name,
                success=False,
                error=str(e),
                fetch_time=fetch_time
            )

class YtdlpStrategy(TranscriptStrategy):
    """Strategy using yt-dlp"""
    
    def __init__(self):
        self.fetcher = YtdlpTranscriptFetcher()
        self.executor = ThreadPoolExecutor(max_workers=3)  # Fewer workers for yt-dlp
    
    @property
    def name(self) -> str:
        return "yt-dlp"
    
    async def fetch(self, video_id: str) -> TranscriptResult:
        """Fetch transcript asynchronously"""
        start_time = asyncio.get_event_loop().time()
        
        loop = asyncio.get_event_loop()
        try:
            transcript = await loop.run_in_executor(
                self.executor, self.fetcher.fetch_transcript, video_id
            )
            
            fetch_time = asyncio.get_event_loop().time() - start_time
            
            if transcript:
                return TranscriptResult(
                    video_id=video_id,
                    transcript=transcript,
                    language='en',  # Assuming English
                    method=self.name,
                    success=True,
                    fetch_time=fetch_time
                )
            else:
                return TranscriptResult(
                    video_id=video_id,
                    transcript=None,
                    language=None,
                    method=self.name,
                    success=False,
                    error="No transcript found",
                    fetch_time=fetch_time
                )
        except Exception as e:
            fetch_time = asyncio.get_event_loop().time() - start_time
            return TranscriptResult(
                video_id=video_id,
                transcript=None,
                language=None,
                method=self.name,
                success=False,
                error=str(e),
                fetch_time=fetch_time
            )

class ConcurrentTranscriptFetcher:
    """Fetch transcripts using multiple strategies concurrently"""
    
    def __init__(self, strategies: Optional[List[TranscriptStrategy]] = None):
        self.strategies = strategies or [
            YouTubeTranscriptApiStrategy(),
            SimpleTranscriptStrategy(),
            YtdlpStrategy()
        ]
        self.retry_delays = [1, 3, 5]  # Exponential backoff delays
        
        # Track failed attempts to avoid repeated failures
        self.failure_cache: Dict[str, datetime] = {}
        self.failure_cache_ttl = timedelta(hours=24)
    
    def _is_recently_failed(self, video_id: str) -> bool:
        """Check if video recently failed to fetch"""
        if video_id in self.failure_cache:
            if datetime.utcnow() - self.failure_cache[video_id] < self.failure_cache_ttl:
                return True
            else:
                del self.failure_cache[video_id]
        return False
    
    async def fetch_transcript(
        self, 
        video_id: str,
        timeout: float = 30.0,
        retry_failed: bool = False
    ) -> TranscriptResult:
        """
        Fetch transcript using concurrent strategies
        
        Args:
            video_id: YouTube video ID
            timeout: Maximum time to wait for all strategies
            retry_failed: Whether to retry recently failed videos
        
        Returns:
            Best available transcript result
        """
        # Check failure cache
        if not retry_failed and self._is_recently_failed(video_id):
            return TranscriptResult(
                video_id=video_id,
                transcript=None,
                language=None,
                method="cache",
                success=False,
                error="Recently failed, skipping"
            )
        
        # Create tasks for all strategies
        tasks = []
        for strategy in self.strategies:
            task = asyncio.create_task(strategy.fetch(video_id))
            tasks.append((strategy.name, task))
        
        # Wait for first successful result or all to complete
        results = []
        try:
            done, pending = await asyncio.wait(
                [task for _, task in tasks],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=timeout
            )
            
            # Check completed tasks for success
            for task in done:
                result = await task
                results.append(result)
                if result.success:
                    # Cancel pending tasks
                    for pending_task in pending:
                        pending_task.cancel()
                    return result
            
            # If no success yet, wait for remaining tasks
            if pending:
                done, _ = await asyncio.wait(pending, timeout=timeout/2)
                for task in done:
                    try:
                        result = await task
                        results.append(result)
                        if result.success:
                            return result
                    except Exception:
                        pass
        
        except asyncio.TimeoutError:
            # Cancel all pending tasks
            for _, task in tasks:
                if not task.done():
                    task.cancel()
        
        # No successful result - cache failure and return best error
        self.failure_cache[video_id] = datetime.utcnow()
        
        if results:
            # Return the result with the most information
            return max(results, key=lambda r: (r.success, len(r.error or "")))
        else:
            return TranscriptResult(
                video_id=video_id,
                transcript=None,
                language=None,
                method="all",
                success=False,
                error="All strategies failed or timed out"
            )
    
    async def fetch_multiple(
        self,
        video_ids: List[str],
        max_concurrent: int = 10,
        progress_callback: Optional[callable] = None
    ) -> List[TranscriptResult]:
        """
        Fetch transcripts for multiple videos concurrently
        
        Args:
            video_ids: List of video IDs
            max_concurrent: Maximum concurrent fetches
            progress_callback: Callback for progress updates
        
        Returns:
            List of transcript results
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results = []
        
        async def fetch_with_semaphore(video_id: str, index: int):
            async with semaphore:
                result = await self.fetch_transcript(video_id)
                if progress_callback:
                    progress_callback(index + 1, len(video_ids), result)
                return result
        
        tasks = [
            fetch_with_semaphore(video_id, i) 
            for i, video_id in enumerate(video_ids)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to failed results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(TranscriptResult(
                    video_id=video_ids[i],
                    transcript=None,
                    language=None,
                    method="error",
                    success=False,
                    error=str(result)
                ))
            else:
                final_results.append(result)
        
        return final_results

# Convenience functions for integration
async def fetch_transcript_async(video_id: str) -> Optional[str]:
    """Simple async function to fetch a transcript"""
    fetcher = ConcurrentTranscriptFetcher()
    result = await fetcher.fetch_transcript(video_id)
    return result.transcript if result.success else None

def fetch_transcript_sync(video_id: str) -> Optional[str]:
    """Synchronous wrapper for async transcript fetching"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(fetch_transcript_async(video_id))
    finally:
        loop.close()