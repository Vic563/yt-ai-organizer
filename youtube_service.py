import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptList
from youtube_transcript_api.formatters import TextFormatter
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable, CouldNotRetrieveTranscript

from config import get_settings
from database import get_db_connection, insert_video, update_video_transcript_status
from models import VideoMetadata, VideoTranscript, TranscriptSegment
from topic_service import TopicExtractor, TopicManager
from simple_transcript_fetcher import SimpleTranscriptFetcher
from browser_transcript_fetcher import BrowserTranscriptFetcher
from oauth_transcript_fetcher import OAuthTranscriptFetcher

logger = logging.getLogger(__name__)

class YouTubeService:
    """Service for interacting with YouTube Data API and fetching transcripts"""
    
    def __init__(self, api_key: str, gemini_api_key: str = None):
        self.api_key = api_key
        self.youtube = build('youtube', 'v3', developerKey=api_key)
        self.settings = get_settings()
        self.transcript_fetcher = SimpleTranscriptFetcher()
        self.browser_fetcher = None  # Initialize browser fetcher lazily
        self.oauth_fetcher = OAuthTranscriptFetcher()  # OAuth-based fetcher (most reliable)
        
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
                    result["message"] += f" with transcript ({len(transcript.full_text)} characters)"
                    transcript_text = transcript.full_text
                else:
                    # Enhanced user-friendly error messaging
                    logger.warning(f"Could not fetch transcript for {video_id} after trying multiple methods")
                    update_video_transcript_status(video_id, False)
                    result["message"] += " (transcript unavailable - YouTube may be blocking automated requests)"
                
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
                    logger.info(f"Successfully fetched transcript for {video['video_id']}: {video.get('title', 'Unknown')}")
                else:
                    logger.info(f"No transcript available for {video['video_id']}: {video.get('title', 'Unknown')}")
                    
            except Exception as e:
                logger.warning(f"Failed to fetch transcript for {video['video_id']}: {e}")
                # Don't mark as permanently unavailable - might be temporary issue
        
        logger.info(f"Fetched {count} new transcripts out of {len(videos_without_transcripts)} videos without transcripts")
        return count
    
    async def retry_transcript_fetch(self, video_id: str) -> bool:
        """Retry fetching transcript for a specific video"""
        logger.info(f"Retrying transcript fetch for video {video_id}")
        
        try:
            transcript = await self.get_video_transcript(video_id)
            if transcript:
                # Save transcript to file
                self._save_transcript_to_file(video_id, transcript.full_text)
                
                # Update database
                update_video_transcript_status(
                    video_id, 
                    True, 
                    transcript.language
                )
                logger.info(f"Successfully fetched transcript on retry for {video_id}")
                return True
            else:
                logger.info(f"Still no transcript available for {video_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to retry transcript fetch for {video_id}: {e}")
            return False
    
    async def get_video_transcript(self, video_id: str) -> Optional[VideoTranscript]:
        """Get transcript for a specific video using multiple fallback strategies"""
        logger.info(f"Attempting to fetch transcript for video: {video_id}")

        # Strategy 0: OAuth YouTube Data API (MOST RELIABLE - bypasses all anti-bot protection)
        try:
            logger.debug("Strategy 0: Using OAuth YouTube Data API (Official)")
            if self.oauth_fetcher.is_authenticated():
                transcript = await self.oauth_fetcher.fetch_transcript(video_id)
                if transcript:
                    logger.info(f"Strategy 0 SUCCESS: Fetched transcript using OAuth API - {len(transcript.segments)} segments, {len(transcript.full_text)} characters")
                    return transcript
            else:
                logger.debug("OAuth not authenticated, skipping Strategy 0")
                logger.info("To enable OAuth transcript fetching, run: setup_oauth_authentication()")
        except Exception as e:
            logger.debug(f"Strategy 0 FAILED: OAuth API error: {type(e).__name__}: {e}")

        # Strategy 1: Use SimpleTranscriptFetcher (browser-like approach)
        try:
            logger.debug("Strategy 1: Using SimpleTranscriptFetcher")
            transcript = await self.transcript_fetcher.fetch_transcript(video_id)
            if transcript:
                logger.info(f"Strategy 1 SUCCESS: Fetched transcript using SimpleTranscriptFetcher - {len(transcript.segments)} segments, {len(transcript.full_text)} characters")
                return transcript
        except Exception as e:
            logger.debug(f"Strategy 1 FAILED: SimpleTranscriptFetcher error: {type(e).__name__}: {e}")

        # Strategy 2: Use yt-dlp based fetcher
        try:
            logger.debug("Strategy 2: Using yt-dlp based fetcher")
            from ytdlp_transcript_fetcher import YtDlpTranscriptFetcher
            ytdlp_fetcher = YtDlpTranscriptFetcher()
            transcript = await ytdlp_fetcher.fetch_transcript(video_id)
            if transcript:
                logger.info(f"Strategy 2 SUCCESS: Fetched transcript using yt-dlp - {len(transcript.segments)} segments, {len(transcript.full_text)} characters")
                return transcript
        except Exception as e:
            logger.debug(f"Strategy 2 FAILED: yt-dlp error: {type(e).__name__}: {e}")

        # Strategy 3: Use YouTube Transcript API with focus on auto-generated captions
        try:
            logger.debug("Strategy 3: Using YouTube Transcript API focusing on auto-generated captions")
            transcript = await self._fetch_transcript_auto_generated_only(video_id)
            if transcript:
                logger.info(f"Strategy 3 SUCCESS: Fetched auto-generated transcript - {len(transcript.segments)} segments, {len(transcript.full_text)} characters")
                return transcript
        except Exception as e:
            logger.debug(f"Strategy 3 FAILED: Auto-generated captions error: {type(e).__name__}: {e}")

        # Strategy 4: Direct timedtext endpoint access
        try:
            logger.debug("Strategy 4: Using direct timedtext endpoint")
            transcript = await self._fetch_transcript_timedtext(video_id)
            if transcript:
                logger.info(f"Strategy 4 SUCCESS: Fetched transcript using timedtext endpoint - {len(transcript.segments)} segments, {len(transcript.full_text)} characters")
                return transcript
        except Exception as e:
            logger.debug(f"Strategy 4 FAILED: Timedtext endpoint error: {type(e).__name__}: {e}")

        # Strategy 5: Innertube API approach
        try:
            logger.debug("Strategy 5: Using innertube API approach")
            transcript = await self._fetch_transcript_innertube(video_id)
            if transcript:
                logger.info(f"Strategy 5 SUCCESS: Fetched transcript using innertube API - {len(transcript.segments)} segments, {len(transcript.full_text)} characters")
                return transcript
        except Exception as e:
            logger.debug(f"Strategy 5 FAILED: Innertube API error: {type(e).__name__}: {e}")

        # Strategy 6: Browser automation as last resort (optional)
        try:
            logger.debug("Strategy 6: Using browser automation (Selenium)")
            if not self.browser_fetcher:
                try:
                    self.browser_fetcher = BrowserTranscriptFetcher()
                except Exception as browser_init_error:
                    logger.debug(f"Browser automation not available: {browser_init_error}")
                    self.browser_fetcher = None
            
            if self.browser_fetcher and self.browser_fetcher.driver:
                transcript = await self.browser_fetcher.fetch_transcript(video_id)
                if transcript:
                    logger.info(f"Strategy 6 SUCCESS: Fetched transcript using browser automation - {len(transcript.segments)} segments, {len(transcript.full_text)} characters")
                    return transcript
            else:
                logger.debug("Browser automation not available, skipping strategy 6")
        except Exception as e:
            logger.debug(f"Strategy 6 FAILED: Browser automation error: {type(e).__name__}: {e}")

        # All strategies failed - provide concise logging
        logger.warning(f"All 7 transcript fetching strategies failed for video {video_id}")
        logger.info("YouTube's anti-bot protection is blocking automated transcript requests.")
        if not self.oauth_fetcher.is_authenticated():
            logger.info("💡 TIP: Set up OAuth authentication for 99% reliable transcript access!")
            logger.info("Run: youtube_service.setup_oauth_authentication()")

        return None

    async def _fetch_transcript_auto_generated_only(self, video_id: str) -> Optional[VideoTranscript]:
        """Fetch only auto-generated transcripts using youtube-transcript-api"""
        try:
            logger.debug(f"Attempting to fetch auto-generated transcript for {video_id}")

            # Try to list all transcript languages
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # Look specifically for auto-generated English transcripts
            transcript = None
            language_used = None

            # Try to find auto-generated English transcript
            try:
                transcript = transcript_list.find_generated_transcript(['en'])
                language_used = transcript.language_code
                logger.debug(f"Found auto-generated English transcript for {video_id} ({language_used})")
            except Exception as e:
                logger.debug(f"No auto-generated English transcript: {e}")

                # Try any auto-generated transcript
                available_transcripts = []
                for t in transcript_list:
                    if t.is_generated:
                        available_transcripts.append({
                            'language': t.language,
                            'language_code': t.language_code,
                            'is_generated': t.is_generated
                        })

                if available_transcripts:
                    # Use the first auto-generated transcript
                    first_auto = available_transcripts[0]
                    transcript = transcript_list.find_transcript([first_auto['language_code']])
                    language_used = transcript.language_code
                    logger.debug(f"Using auto-generated transcript in {language_used}")

            if transcript:
                logger.debug(f"Fetching auto-generated transcript data for {video_id} in language: {language_used}")
                transcript_list_data = transcript.fetch()

                if not transcript_list_data:
                    logger.debug(f"Auto-generated transcript fetch returned empty list for {video_id}")
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
                    logger.debug(f"Auto-generated transcript for {video_id} is empty after processing")
                    return None

                logger.debug(f"Successfully fetched auto-generated transcript for {video_id}: {len(segments)} segments, {len(full_text)} characters")
                return VideoTranscript(
                    video_id=video_id,
                    language=language_used,
                    segments=segments,
                    full_text=full_text
                )
            else:
                logger.debug(f"No auto-generated transcript available for {video_id}")
                return None

        except Exception as e:
            logger.debug(f"Error fetching auto-generated transcript for {video_id}: {type(e).__name__}: {e}")
            return None

    async def _fetch_transcript_timedtext(self, video_id: str) -> Optional[VideoTranscript]:
        """Fetch transcript using the public timedtext endpoint as a last resort"""
        import requests
        import xml.etree.ElementTree as ET
        import html

        # Try different URL patterns and headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        languages = ['en', 'en-US', 'en-GB', 'a.en']  # 'a.en' is sometimes used for auto-generated
        for lang in languages:
            try:
                # Try the standard timedtext URL
                url = f"https://www.youtube.com/api/timedtext?v={video_id}&lang={lang}&fmt=srv3"
                logger.debug(f"Attempting timedtext fetch for {video_id} using {lang} with srv3 format")
                resp = requests.get(url, headers=headers, timeout=10)
                
                if resp.status_code == 200 and resp.text.strip():
                    # Try to parse as srv3 format (JSON)
                    try:
                        import json
                        data = json.loads(resp.text)
                        if 'events' in data:
                            segments = []
                            full_text_parts = []
                            for event in data['events']:
                                if 'segs' in event:
                                    text = ''.join(seg.get('utf8', '') for seg in event['segs'])
                                    start = event.get('tStartMs', 0) / 1000.0
                                    duration = event.get('dDurationMs', 0) / 1000.0
                                    if text:
                                        segment = TranscriptSegment(start_time=start, duration=duration, text=text)
                                        segments.append(segment)
                                        full_text_parts.append(text)
                            
                            if segments:
                                full_text = ' '.join(full_text_parts).strip()
                                logger.info(f"Fetched transcript for {video_id} via timedtext srv3 format")
                                return VideoTranscript(
                                    video_id=video_id,
                                    language=lang,
                                    segments=segments,
                                    full_text=full_text,
                                )
                    except json.JSONDecodeError:
                        pass
                
                # Try legacy XML format
                url = f"https://video.google.com/timedtext?lang={lang}&v={video_id}"
                logger.debug(f"Attempting legacy timedtext fetch for {video_id} using {lang}")
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code != 200 or not resp.text.strip():
                    continue

                root = ET.fromstring(resp.text)
                segments = []
                full_text_parts = []
                for elem in root.findall('text'):
                    start = float(elem.attrib.get('start', '0'))
                    dur = float(elem.attrib.get('dur', '0'))
                    text = html.unescape(elem.text or '')
                    segment = TranscriptSegment(start_time=start, duration=dur, text=text)
                    segments.append(segment)
                    full_text_parts.append(text)

                full_text = ' '.join(full_text_parts).strip()
                if full_text:
                    logger.info(f"Fetched transcript for {video_id} via legacy timedtext")
                    return VideoTranscript(
                        video_id=video_id,
                        language=lang,
                        segments=segments,
                        full_text=full_text,
                    )
            except Exception as e:
                logger.debug(f"Timedtext fetch failed for {video_id} lang {lang}: {e}")
                continue

        return None
    
    async def _fetch_transcript_innertube(self, video_id: str) -> Optional[VideoTranscript]:
        """Fetch transcript using YouTube's innertube API (what the player uses)"""
        import requests
        import json
        
        try:
            # First, get the page to extract necessary data
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
            }
            
            page_url = f"https://www.youtube.com/watch?v={video_id}"
            logger.debug(f"Fetching YouTube page for {video_id} to get innertube data")
            
            resp = requests.get(page_url, headers=headers, timeout=10)
            if resp.status_code != 200:
                logger.debug(f"Failed to fetch YouTube page: {resp.status_code}")
                return None
            
            # Extract the initial data from the page
            import re
            ytInitialData_match = re.search(r'var ytInitialData = ({.*?});', resp.text)
            if not ytInitialData_match:
                logger.debug("Could not find ytInitialData in page")
                return None
                
            try:
                yt_data = json.loads(ytInitialData_match.group(1))
            except json.JSONDecodeError:
                logger.debug("Failed to parse ytInitialData")
                return None
            
            # Look for caption tracks in the player response
            captions = None
            try:
                # Navigate through the nested structure
                captions = (yt_data.get('playerOverlays', {})
                           .get('playerOverlayRenderer', {})
                           .get('videoDetails', {})
                           .get('playerVideoDetailsRenderer', {})
                           .get('subtitle', {})
                           .get('playerSubtitleRenderer', {})
                           .get('trackList', []))
            except:
                pass
                
            if not captions:
                # Try alternative path
                try:
                    player_response_str = re.search(r'"playerResponse":"({.*?})"', resp.text)
                    if player_response_str:
                        # Unescape the JSON string
                        player_response = json.loads(player_response_str.group(1).replace('\\"', '"').replace('\\\\', '\\'))
                        captions = (player_response.get('captions', {})
                                   .get('playerCaptionsTracklistRenderer', {})
                                   .get('captionTracks', []))
                except:
                    pass
            
            if not captions:
                logger.debug("No caption tracks found in page data")
                return None
            
            # Find English caption track
            caption_url = None
            for track in captions:
                if track.get('languageCode', '').startswith('en'):
                    caption_url = track.get('baseUrl')
                    if caption_url:
                        break
            
            if not caption_url:
                logger.debug("No English caption track found")
                return None
            
            # Fetch the actual captions
            logger.debug(f"Fetching captions from: {caption_url}")
            caption_resp = requests.get(caption_url, headers=headers, timeout=10)
            if caption_resp.status_code != 200:
                logger.debug(f"Failed to fetch captions: {caption_resp.status_code}")
                return None
            
            # Parse the caption data (usually in XML format)
            import xml.etree.ElementTree as ET
            import html
            
            root = ET.fromstring(caption_resp.text)
            segments = []
            full_text_parts = []
            
            for elem in root.findall('.//text'):
                start = float(elem.attrib.get('start', '0'))
                dur = float(elem.attrib.get('dur', '0'))
                text = html.unescape(elem.text or '')
                if text:
                    segment = TranscriptSegment(start_time=start, duration=dur, text=text)
                    segments.append(segment)
                    full_text_parts.append(text)
            
            if segments:
                full_text = ' '.join(full_text_parts).strip()
                logger.info(f"Successfully fetched transcript via innertube for {video_id}")
                return VideoTranscript(
                    video_id=video_id,
                    language='en',
                    segments=segments,
                    full_text=full_text,
                )
            
        except Exception as e:
            logger.debug(f"Innertube transcript fetch failed: {type(e).__name__}: {e}")
        
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
                
            # 2. Try auto-generated English - use a more flexible approach
            if not transcript:
                try:
                    # First try the standard approach
                    transcript = transcript_list.find_generated_transcript(['en', 'en-US', 'en-GB'])
                    language_used = transcript.language_code
                    logger.info(f"Found auto-generated English transcript for {video_id} ({language_used})")
                except Exception as e:
                    logger.debug(f"Standard auto-generated English search failed: {e}")
                    # Try finding any English transcript by checking available transcripts directly
                    for available in available_transcripts:
                        if available['language_code'] == 'en' and available['is_generated']:
                            try:
                                # Get transcript directly by language code
                                for t in transcript_list:
                                    if t.language_code == 'en':
                                        transcript = t
                                        language_used = 'en'
                                        logger.info(f"Found English transcript via direct search for {video_id}")
                                        break
                                if transcript:
                                    break
                            except Exception as e2:
                                logger.debug(f"Direct English transcript fetch failed: {e2}")
                    
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
    
    def cleanup(self):
        """Clean up resources, especially browser automation"""
        if self.browser_fetcher and hasattr(self.browser_fetcher, 'cleanup'):
            try:
                self.browser_fetcher.cleanup()
                logger.info("Cleaned up browser transcript fetcher")
            except Exception as e:
                logger.error(f"Error cleaning up browser fetcher: {e}")
            finally:
                self.browser_fetcher = None
    
    def __del__(self):
        """Ensure cleanup on object destruction"""
        self.cleanup()
    
    # OAuth Authentication Methods
    
    def setup_oauth_authentication(self, client_secrets_path: Optional[str] = None) -> bool:
        """
        Set up OAuth authentication for reliable transcript access
        
        Args:
            client_secrets_path: Path to client_secret.json (optional)
            
        Returns:
            bool: True if authentication successful
        """
        logger.info("Setting up OAuth authentication for YouTube transcript access...")
        logger.info(self.oauth_fetcher.setup_instructions())
        
        return self.oauth_fetcher.authenticate(client_secrets_path)
    
    def is_oauth_authenticated(self) -> bool:
        """Check if OAuth authentication is set up and valid"""
        return self.oauth_fetcher.is_authenticated()
    
    def get_oauth_status(self) -> Dict[str, Any]:
        """Get OAuth authentication status and information"""
        return {
            "authenticated": self.oauth_fetcher.is_authenticated(),
            "credentials_valid": (
                self.oauth_fetcher.credentials and 
                self.oauth_fetcher.credentials.valid
            ) if self.oauth_fetcher.credentials else False,
            "service_available": self.oauth_fetcher.youtube_service is not None,
            "setup_instructions": "Run setup_oauth_authentication() method"
        }
    
    async def get_available_captions_oauth(self, video_id: str) -> List[Dict[str, Any]]:
        """Get available caption tracks using OAuth API"""
        return self.oauth_fetcher.get_available_captions(video_id)
    
    async def force_oauth_transcript(self, video_id: str) -> Optional[VideoTranscript]:
        """Force transcript fetch using only OAuth method"""
        if not self.oauth_fetcher.is_authenticated():
            logger.error("OAuth authentication required. Run setup_oauth_authentication() first.")
            return None
        
        return await self.oauth_fetcher.fetch_transcript(video_id)
