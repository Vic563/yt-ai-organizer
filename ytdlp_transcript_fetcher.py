"""
YouTube transcript fetcher using yt-dlp
"""
import logging
import json
import tempfile
import os
from typing import Optional, List, Dict, Any
import yt_dlp
from models import VideoTranscript, TranscriptSegment

logger = logging.getLogger(__name__)

class YtDlpTranscriptFetcher:
    """Transcript fetcher using yt-dlp to bypass YouTube's anti-bot measures"""
    
    def __init__(self):
        # Configure yt-dlp options
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'en-US', 'en-GB'],
            'subtitlesformat': 'vtt',
            'skip_download': True,
            'extract_flat': False,
            # Use a temporary directory for subtitle files
            'outtmpl': os.path.join(tempfile.gettempdir(), 'yt_transcript_%(id)s.%(ext)s'),
        }
    
    async def fetch_transcript(self, video_id: str) -> Optional[VideoTranscript]:
        """Fetch transcript using yt-dlp"""
        try:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            logger.debug(f"Fetching transcript for {video_id} using yt-dlp")
            
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                # Extract video info including subtitles
                info = ydl.extract_info(video_url, download=False)
                
                if not info:
                    logger.debug(f"Could not extract video info for {video_id}")
                    return None
                
                # Check for subtitles
                subtitles = info.get('subtitles', {})
                automatic_captions = info.get('automatic_captions', {})
                
                logger.debug(f"Available subtitles: {list(subtitles.keys())}")
                logger.debug(f"Available automatic captions: {list(automatic_captions.keys())}")
                
                # Try to find English subtitles
                subtitle_data = None
                language_used = None
                
                # Priority: manual subtitles first, then automatic
                for lang in ['en', 'en-US', 'en-GB']:
                    if lang in subtitles:
                        subtitle_data = subtitles[lang]
                        language_used = lang
                        logger.debug(f"Found manual subtitles in {lang}")
                        break
                
                if not subtitle_data:
                    for lang in ['en', 'en-US', 'en-GB']:
                        if lang in automatic_captions:
                            subtitle_data = automatic_captions[lang]
                            language_used = lang
                            logger.debug(f"Found automatic captions in {lang}")
                            break
                
                if not subtitle_data:
                    logger.debug(f"No English subtitles found for {video_id}")
                    return None
                
                # Find VTT format subtitle
                vtt_subtitle = None
                for sub in subtitle_data:
                    if sub.get('ext') == 'vtt':
                        vtt_subtitle = sub
                        break
                
                if not vtt_subtitle:
                    logger.debug(f"No VTT format subtitle found for {video_id}")
                    return None
                
                # Download the subtitle file
                subtitle_url = vtt_subtitle.get('url')
                if not subtitle_url:
                    logger.debug(f"No subtitle URL found for {video_id}")
                    return None
                
                logger.debug(f"Downloading subtitle from: {subtitle_url}")
                
                # Download subtitle content
                import requests
                response = requests.get(subtitle_url, timeout=10)
                if response.status_code != 200:
                    logger.debug(f"Failed to download subtitle: {response.status_code}")
                    return None
                
                subtitle_content = response.text
                if not subtitle_content:
                    logger.debug(f"Empty subtitle content for {video_id}")
                    return None
                
                # Parse VTT content
                transcript = self._parse_vtt_content(subtitle_content, video_id, language_used)
                if transcript:
                    logger.debug(f"Successfully parsed transcript: {len(transcript.segments)} segments")
                    return transcript
                
                logger.debug(f"Failed to parse VTT content for {video_id}")
                return None
                
        except Exception as e:
            logger.debug(f"Error fetching transcript with yt-dlp: {type(e).__name__}: {e}")
            return None
    
    def _parse_vtt_content(self, vtt_content: str, video_id: str, language: str = 'en') -> Optional[VideoTranscript]:
        """Parse VTT (WebVTT) subtitle content"""
        try:
            lines = vtt_content.split('\n')
            segments = []
            full_text_parts = []
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # Skip empty lines and headers
                if not line or line.startswith('WEBVTT') or line.startswith('NOTE'):
                    i += 1
                    continue
                
                # Look for timestamp line (format: 00:00:00.000 --> 00:00:00.000)
                if '-->' in line:
                    try:
                        # Parse timestamp
                        start_str, end_str = line.split(' --> ')
                        start_time = self._parse_vtt_timestamp(start_str)
                        end_time = self._parse_vtt_timestamp(end_str)
                        duration = end_time - start_time
                        
                        # Get the text (next non-empty lines until we hit another timestamp or end)
                        i += 1
                        text_lines = []
                        while i < len(lines):
                            text_line = lines[i].strip()
                            if not text_line:
                                break
                            if '-->' in text_line:
                                # This is the next timestamp, don't consume it
                                i -= 1
                                break
                            text_lines.append(text_line)
                            i += 1
                        
                        if text_lines:
                            # Join text lines and clean up
                            text = ' '.join(text_lines)
                            # Remove VTT formatting tags
                            text = self._clean_vtt_text(text)
                            
                            if text:
                                segment = TranscriptSegment(
                                    start_time=start_time,
                                    duration=duration,
                                    text=text
                                )
                                segments.append(segment)
                                full_text_parts.append(text)
                    
                    except Exception as e:
                        logger.debug(f"Error parsing VTT timestamp line '{line}': {e}")
                
                i += 1
            
            if segments:
                full_text = ' '.join(full_text_parts)
                return VideoTranscript(
                    video_id=video_id,
                    language=language,
                    segments=segments,
                    full_text=full_text
                )
            
        except Exception as e:
            logger.debug(f"Error parsing VTT content: {e}")
        
        return None
    
    def _parse_vtt_timestamp(self, timestamp_str: str) -> float:
        """Parse VTT timestamp to seconds"""
        # Format: HH:MM:SS.mmm or MM:SS.mmm
        parts = timestamp_str.split(':')
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
        elif len(parts) == 2:
            minutes, seconds = parts
            return float(minutes) * 60 + float(seconds)
        else:
            return float(timestamp_str)
    
    def _clean_vtt_text(self, text: str) -> str:
        """Clean VTT formatting from text"""
        import re
        
        # Remove VTT tags like <c.colorname>, <i>, <b>, etc.
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove alignment tags
        text = re.sub(r'\{[^}]+\}', '', text)
        
        # Clean up whitespace
        text = ' '.join(text.split())
        
        return text.strip()
