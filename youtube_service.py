import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

from config import get_settings
from database import get_db_connection, insert_video, update_video_transcript_status
from models import VideoMetadata, VideoTranscript, TranscriptSegment
from topic_service import TopicExtractor, TopicManager

logger = logging.getLogger(__name__)

class YouTubeService:
    """Service for interacting with YouTube Data API and fetching transcripts"""
    
    def __init__(self, api_key: str, gemini_api_key: str = None):
        self.api_key = api_key
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        self.settings = get_settings()
        
        # Initialize topic extractor if Gemini API key is provided
        self.topic_extractor = None
        if gemini_api_key:
            self.topic_extractor = TopicExtractor(gemini_api_key)
        
    async def test_connection(self):
        """Test YouTube API connection"""
        try:
            # Simple test request
            request = self.youtube.channels().list(
                part='snippet',
                mine=True
            )
            request.execute()
            logger.info("YouTube API connection test successful")
            return True
        except HttpError as e:
            logger.error(f"YouTube API connection test failed: {e}")
            raise Exception(f"YouTube API test failed: {e}")
    
    async def add_video_by_url(self, video_url: str) -> Dict[str, Any]:
        """Add a single video to the library by URL"""
        logger.info(f"Adding video from URL: {video_url}")

        result = {
            "success": False,
            "video_id": None,
            "title": None,
            "message": "",
            "transcript_fetched": False
        }

        try:
            # Extract video ID from URL
            video_id = self._extract_video_id(video_url)
            if not video_id:
                result["message"] = "Invalid YouTube URL format"
                return result

            # Check if video already exists
            from database import get_all_videos
            existing_videos = get_all_videos()
            if any(v['video_id'] == video_id for v in existing_videos):
                result["message"] = "Video already exists in your library"
                result["video_id"] = video_id
                return result

            # Fetch video metadata
            video_metadata = await self._fetch_video_metadata(video_id)
            if not video_metadata:
                result["message"] = "Could not fetch video metadata. Video may be private or deleted."
                return result

            # Save video to database
            if insert_video(video_metadata):
                result["success"] = True
                result["video_id"] = video_id
                result["title"] = video_metadata.title
                result["message"] = "Video added successfully"

                # Fetch transcript
                transcript = await self.get_video_transcript(video_id)
                transcript_text = ""
                if transcript:
                    self._save_transcript_to_file(video_id, transcript.full_text)
                    update_video_transcript_status(video_id, True, transcript.language)
                    result["transcript_fetched"] = True
                    result["message"] += " with transcript"
                    transcript_text = transcript.full_text
                else:
                    update_video_transcript_status(video_id, False)
                    result["message"] += " (no transcript available)"
                
                # Extract and assign topic if extractor is available (works with or without transcript)
                if self.topic_extractor:
                    # Use transcript if available, otherwise use title and description
                    content_for_topic = transcript_text if transcript_text else f"{video_metadata.title}. {video_metadata.description or ''}"
                    topic, confidence = await self._extract_and_assign_topic(
                        video_id, video_metadata.title, content_for_topic
                    )
                    if topic:
                        result["topic"] = topic
                        result["topic_confidence"] = confidence
                        result["message"] += f" and assigned to topic: {topic}"

                logger.info(f"Successfully added video: {video_metadata.title}")
            else:
                result["message"] = "Failed to save video to database"

            return result

        except Exception as e:
            error_msg = f"Failed to add video: {str(e)}"
            logger.error(error_msg)
            result["message"] = error_msg
            return result
    
    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extract video ID from YouTube URL"""
        import re

        # Common YouTube URL patterns
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com\/watch\?.*v=([a-zA-Z0-9_-]{11})',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    async def _fetch_video_metadata(self, video_id: str) -> Optional[VideoMetadata]:
        """Fetch metadata for a single video"""
        try:
            request = self.youtube.videos().list(
                part='snippet,contentDetails,statistics',
                id=video_id
            )

            response = request.execute()
            items = response.get('items', [])

            if not items:
                logger.warning(f"No video found with ID: {video_id}")
                return None

            return self._parse_video_item(items[0])

        except HttpError as e:
            logger.error(f"Error fetching video metadata for {video_id}: {e}")
            return None

    async def remove_video(self, video_id: str) -> Dict[str, Any]:
        """Remove a video from the library"""
        try:
            from database import get_db_connection

            # Remove from database
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM videos WHERE video_id = ?", (video_id,))
                deleted_count = cursor.rowcount
                conn.commit()

            # Remove transcript file
            transcript_path = os.path.join(self.settings.transcripts_dir, f"{video_id}.txt")
            if os.path.exists(transcript_path):
                os.remove(transcript_path)
                logger.info(f"Removed transcript file for {video_id}")

            if deleted_count > 0:
                logger.info(f"Successfully removed video {video_id}")
                return {"success": True, "message": "Video removed successfully"}
            else:
                return {"success": False, "message": "Video not found in library"}

        except Exception as e:
            logger.error(f"Error removing video {video_id}: {e}")
            return {"success": False, "message": f"Failed to remove video: {str(e)}"}
            
    async def _extract_and_assign_topic(
        self, video_id: str, title: str, transcript: str
    ) -> Tuple[Optional[str], float]:
        """Extract topic from video content and assign it"""
        if not self.topic_extractor:
            return None, 0.0
            
        try:
            # Extract topic using Gemini
            topic, confidence = await self.topic_extractor.extract_topic(title, transcript)
            
            if not topic:
                return None, 0.0
                
            # Save topic to database
            with get_db_connection() as conn:
                topic_manager = TopicManager(conn)
                success = topic_manager.update_video_topic(
                    video_id=video_id,
                    topic_name=topic,
                    confidence=confidence,
                    auto_generated=True
                )
                
                if success:
                    return topic, confidence
                    
        except Exception as e:
            logger.error(f"Error in topic extraction/assignment: {e}")
            
        return None, 0.0

    async def _sync_liked_videos(self) -> int:
        """Sync user's liked videos"""
        logger.info("Syncing liked videos...")
        count = 0
        next_page_token = None
        
        try:
            while True:
                request = self.youtube.videos().list(
                    part='snippet,contentDetails,statistics',
                    myRating='like',
                    maxResults=50,
                    pageToken=next_page_token
                )
                
                response = request.execute()
                
                for item in response.get('items', []):
                    video_metadata = self._parse_video_item(item)
                    if insert_video(video_metadata):
                        count += 1
                
                next_page_token = response.get('nextPageToken')
                if not next_page_token or count >= self.settings.max_videos_per_sync:
                    break
                    
            logger.info(f"Synced {count} liked videos")
            return count
            
        except HttpError as e:
            logger.error(f"Error syncing liked videos: {e}")
            return count
    
    async def _sync_uploaded_videos(self) -> int:
        """Sync user's uploaded videos"""
        logger.info("Syncing uploaded videos...")
        count = 0
        
        try:
            # Get user's channel
            channels_response = self.youtube.channels().list(
                part='contentDetails',
                mine=True
            ).execute()
            
            if not channels_response.get('items'):
                logger.info("No user channel found")
                return 0
            
            uploads_playlist_id = channels_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            
            # Get videos from uploads playlist
            next_page_token = None
            
            while True:
                playlist_request = self.youtube.playlistItems().list(
                    part='snippet',
                    playlistId=uploads_playlist_id,
                    maxResults=50,
                    pageToken=next_page_token
                )
                
                playlist_response = playlist_request.execute()
                
                # Get video IDs
                video_ids = [item['snippet']['resourceId']['videoId'] 
                           for item in playlist_response.get('items', [])]
                
                if video_ids:
                    # Get detailed video information
                    videos_request = self.youtube.videos().list(
                        part='snippet,contentDetails,statistics',
                        id=','.join(video_ids)
                    )
                    
                    videos_response = videos_request.execute()
                    
                    for item in videos_response.get('items', []):
                        video_metadata = self._parse_video_item(item)
                        if insert_video(video_metadata):
                            count += 1
                
                next_page_token = playlist_response.get('nextPageToken')
                if not next_page_token or count >= self.settings.max_videos_per_sync:
                    break
            
            logger.info(f"Synced {count} uploaded videos")
            return count
            
        except HttpError as e:
            logger.error(f"Error syncing uploaded videos: {e}")
            return count
    
    def _parse_video_item(self, item: Dict[str, Any]) -> VideoMetadata:
        """Parse YouTube API video item into VideoMetadata"""
        snippet = item['snippet']
        content_details = item.get('contentDetails', {})
        statistics = item.get('statistics', {})
        
        return VideoMetadata(
            video_id=item['id'],
            title=snippet['title'],
            description=snippet.get('description', ''),
            channel_id=snippet['channelId'],
            channel_title=snippet['channelTitle'],
            published_at=snippet['publishedAt'],
            duration=content_details.get('duration'),
            thumbnail_url=snippet.get('thumbnails', {}).get('medium', {}).get('url'),
            view_count=int(statistics.get('viewCount', 0)) if statistics.get('viewCount') else None,
            like_count=int(statistics.get('likeCount', 0)) if statistics.get('likeCount') else None,
            has_transcript=False  # Will be updated when transcript is fetched
        )
    
    async def _fetch_missing_transcripts(self) -> int:
        """Fetch transcripts for videos that don't have them"""
        logger.info("Fetching missing transcripts...")
        
        from database import get_all_videos
        
        videos = get_all_videos()
        videos_without_transcripts = [v for v in videos if not v['has_transcript']]
        
        count = 0
        for video in videos_without_transcripts:
            try:
                transcript = await self.get_video_transcript(video['video_id'])
                if transcript:
                    # Save transcript to file
                    self._save_transcript_to_file(video['video_id'], transcript.full_text)
                    
                    # Update database
                    update_video_transcript_status(
                        video['video_id'], 
                        True, 
                        transcript.language
                    )
                    count += 1
                    
            except Exception as e:
                logger.warning(f"Failed to fetch transcript for {video['video_id']}: {e}")
                # Mark as no transcript available
                update_video_transcript_status(video['video_id'], False)
        
        logger.info(f"Fetched {count} transcripts")
        return count
    
    async def get_video_transcript(self, video_id: str) -> Optional[VideoTranscript]:
        """Get transcript for a specific video with robust error handling and multiple fallback strategies"""
        logger.info(f"Attempting to fetch transcript for video: {video_id}")
        
        # Try different approaches in order of preference
        strategies = [
            self._fetch_transcript_with_retries,
            self._fetch_transcript_with_proxy_headers,
            self._fetch_transcript_basic
        ]
        
        for i, strategy in enumerate(strategies, 1):
            try:
                logger.info(f"Trying transcript fetch strategy {i}/{len(strategies)} for {video_id}")
                result = await strategy(video_id)
                if result:
                    logger.info(f"Successfully fetched transcript for {video_id} using strategy {i}")
                    return result
                else:
                    logger.debug(f"Strategy {i} returned no transcript for {video_id}")
            except Exception as e:
                logger.warning(f"Strategy {i} failed for {video_id}: {type(e).__name__}: {e}")
                continue
        
        logger.error(f"All transcript fetch strategies failed for {video_id}")
        return None
    
    async def _fetch_transcript_with_retries(self, video_id: str) -> Optional[VideoTranscript]:
        """Fetch transcript with retries and delays to avoid rate limiting"""
        import time
        import random
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    # Add random delay between retries to avoid rate limiting
                    delay = random.uniform(1, 3)
                    logger.debug(f"Waiting {delay:.1f}s before retry {attempt + 1}/{max_retries}")
                    time.sleep(delay)
                
                return await self._fetch_transcript_basic(video_id)
                
            except Exception as e:
                if "no element found" in str(e).lower() or "xml" in str(e).lower():
                    logger.debug(f"XML parsing error on attempt {attempt + 1}: {e}")
                    if attempt == max_retries - 1:
                        raise
                    continue
                else:
                    # For other errors, don't retry
                    raise
        
        return None
    
    async def _fetch_transcript_with_proxy_headers(self, video_id: str) -> Optional[VideoTranscript]:
        """Fetch transcript with browser-like headers to avoid bot detection"""
        try:
            # Import here to avoid issues if requests isn't available
            import requests
            
            # Set up session with browser-like headers
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            })
            
            # Temporarily patch the session into youtube-transcript-api
            # This is a bit hacky but should work for most cases
            original_get = requests.get
            requests.get = session.get
            
            try:
                result = await self._fetch_transcript_basic(video_id)
                return result
            finally:
                # Restore original requests.get
                requests.get = original_get
                
        except ImportError:
            logger.debug("requests library not available for enhanced headers strategy")
            raise
        except Exception as e:
            logger.debug(f"Enhanced headers strategy failed: {e}")
            raise
    
    async def _fetch_transcript_basic(self, video_id: str) -> Optional[VideoTranscript]:
        """Basic transcript fetching using youtube-transcript-api"""
        try:
            # Check if video exists and is accessible first
            logger.debug(f"Checking video accessibility for {video_id}")
            
            # Try to list all transcript languages
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Convert TranscriptList to a list to see available languages
            available_transcripts = []
            for transcript in transcript_list:
                available_transcripts.append({
                    'language': transcript.language,
                    'language_code': transcript.language_code,
                    'is_generated': transcript.is_generated
                })
            
            logger.info(f"Available transcripts for {video_id}: {available_transcripts}")
            
            if not available_transcripts:
                logger.warning(f"No transcripts available for {video_id}")
                return None
            
            # Strategy: try different transcript types in order of preference
            transcript = None
            language_used = None
            
            # 1. Try manually created English
            try:
                transcript = transcript_list.find_manually_created_transcript(['en', 'en-US', 'en-GB'])
                language_used = transcript.language_code
                logger.info(f"Found manually created English transcript for {video_id} ({language_used})")
            except Exception as e:
                logger.debug(f"No manually created English transcript: {e}")
                
            # 2. Try auto-generated English
            if not transcript:
                try:
                    transcript = transcript_list.find_generated_transcript(['en', 'en-US', 'en-GB'])
                    language_used = transcript.language_code
                    logger.info(f"Found auto-generated English transcript for {video_id} ({language_used})")
                except Exception as e:
                    logger.debug(f"No auto-generated English transcript: {e}")
                    
            # 3. Try any manually created transcript
            if not transcript:
                try:
                    for available in available_transcripts:
                        if not available['is_generated']:
                            transcript = transcript_list.find_transcript([available['language_code']])
                            language_used = transcript.language_code
                            logger.info(f"Found manually created transcript for {video_id} in {language_used}")
                            break
                except Exception as e:
                    logger.debug(f"No manually created transcript in any language: {e}")
                    
            # 4. Fallback: use any available transcript
            if not transcript:
                try:
                    # Get the first available transcript
                    first_available = available_transcripts[0]
                    transcript = transcript_list.find_transcript([first_available['language_code']])
                    language_used = transcript.language_code
                    logger.info(f"Using fallback transcript for {video_id} in language: {language_used}")
                except Exception as e:
                    logger.error(f"No fallback transcript available for {video_id}: {e}")
                    return None
                    
            if transcript:
                logger.info(f"Fetching transcript data for {video_id} in language: {language_used}")
                transcript_list_data = transcript.fetch()
                
                if not transcript_list_data:
                    logger.warning(f"Transcript fetch returned empty list for {video_id}")
                    return None
                
                segments = []
                full_text_parts = []
                for entry in transcript_list_data:
                    segment = TranscriptSegment(
                        start_time=entry.get('start', 0),
                        duration=entry.get('duration', 0),
                        text=entry.get('text', '')
                    )
                    segments.append(segment)
                    full_text_parts.append(entry.get('text', ''))
                    
                full_text = ' '.join(full_text_parts).strip()
                if not full_text:
                    logger.warning(f"Transcript for {video_id} is empty after processing")
                    return None
                    
                logger.info(f"Successfully fetched transcript for {video_id}: {len(segments)} segments, {len(full_text)} characters")
                return VideoTranscript(
                    video_id=video_id,
                    language=language_used,
                    segments=segments,
                    full_text=full_text
                )
            else:
                logger.warning(f"No transcript could be selected for {video_id}")
                return None
                
        except Exception as e:
            error_msg = f"Could not fetch transcript for {video_id}: {type(e).__name__}: {e}"
            logger.error(error_msg)
            
            # Provide more specific error messages for common issues
            if "no element found" in str(e).lower():
                logger.error(f"XML parsing error for {video_id} - this usually means YouTube blocked the request or the video has restricted access")
            elif "video unavailable" in str(e).lower():
                logger.error(f"Video {video_id} is unavailable or private")
            elif "transcript disabled" in str(e).lower():
                logger.error(f"Transcripts are disabled for video {video_id}")
            elif "not available" in str(e).lower():
                logger.error(f"No transcripts available for video {video_id}")
            
            raise
    
    def _save_transcript_to_file(self, video_id: str, transcript_text: str):
        """Save transcript text to file"""
        try:
            transcript_path = os.path.join(self.settings.transcripts_dir, f"{video_id}.txt")
            with open(transcript_path, 'w', encoding='utf-8') as f:
                f.write(transcript_text)
            logger.debug(f"Saved transcript for {video_id}")
        except Exception as e:
            logger.error(f"Failed to save transcript for {video_id}: {e}")
    
    def get_transcript_from_file(self, video_id: str) -> Optional[str]:
        """Load transcript from file"""
        try:
            transcript_path = os.path.join(self.settings.transcripts_dir, f"{video_id}.txt")
            if os.path.exists(transcript_path):
                with open(transcript_path, 'r', encoding='utf-8') as f:
                    return f.read()
        except Exception as e:
            logger.error(f"Failed to load transcript for {video_id}: {e}")
        return None
