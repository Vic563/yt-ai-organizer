"""
OAuth-based YouTube transcript fetcher using official YouTube Data API v3
This is the most reliable method that bypasses all anti-bot protection
"""
import os
import logging
import json
from typing import Optional, List, Dict, Any
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import pickle

from models import VideoTranscript, TranscriptSegment
from config import get_settings

logger = logging.getLogger(__name__)

class OAuthTranscriptFetcher:
    """Fetch YouTube transcripts using official OAuth-authenticated YouTube Data API"""
    
    # Required OAuth scopes for caption access
    SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']
    
    def __init__(self):
        self.settings = get_settings()
        self.youtube_service = None
        self.credentials = None
        self._load_credentials()
    
    def _get_credentials_path(self) -> str:
        """Get path for storing OAuth credentials"""
        credentials_dir = os.path.join(os.path.dirname(__file__), 'oauth_credentials')
        os.makedirs(credentials_dir, exist_ok=True)
        return os.path.join(credentials_dir, 'youtube_oauth_token.pickle')
    
    def _get_client_secrets_path(self) -> str:
        """Get path for OAuth client secrets file"""
        return os.path.join(os.path.dirname(__file__), 'oauth_credentials', 'client_secret.json')
    
    def _load_credentials(self):
        """Load existing OAuth credentials or prompt for new authentication"""
        token_path = self._get_credentials_path()
        
        # Load existing credentials
        if os.path.exists(token_path):
            try:
                with open(token_path, 'rb') as token_file:
                    self.credentials = pickle.load(token_file)
                logger.debug("Loaded existing OAuth credentials")
            except Exception as e:
                logger.warning(f"Failed to load credentials: {e}")
                self.credentials = None
        
        # Check if credentials are valid
        if self.credentials and self.credentials.valid:
            self._build_service()
            return
        
        # Refresh credentials if they're expired
        if self.credentials and self.credentials.expired and self.credentials.refresh_token:
            try:
                self.credentials.refresh(Request())
                self._save_credentials()
                self._build_service()
                logger.info("Refreshed OAuth credentials")
                return
            except Exception as e:
                logger.warning(f"Failed to refresh credentials: {e}")
                self.credentials = None
        
        # Need new authentication
        logger.info("OAuth credentials not available or invalid")
    
    def _save_credentials(self):
        """Save OAuth credentials to file"""
        try:
            token_path = self._get_credentials_path()
            with open(token_path, 'wb') as token_file:
                pickle.dump(self.credentials, token_file)
            logger.debug("Saved OAuth credentials")
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
    
    def _build_service(self):
        """Build YouTube Data API service with authenticated credentials"""
        if self.credentials and self.credentials.valid:
            self.youtube_service = build('youtube', 'v3', credentials=self.credentials)
            logger.debug("Built authenticated YouTube service")
        else:
            self.youtube_service = None
            logger.warning("Cannot build YouTube service - invalid credentials")
    
    def authenticate(self, client_secrets_path: Optional[str] = None) -> bool:
        """
        Perform OAuth authentication flow
        
        Args:
            client_secrets_path: Path to client_secret.json file
            
        Returns:
            bool: True if authentication successful
        """
        if not client_secrets_path:
            client_secrets_path = self._get_client_secrets_path()
        
        if not os.path.exists(client_secrets_path):
            logger.error(f"Client secrets file not found: {client_secrets_path}")
            logger.error("Please follow OAuth setup instructions:")
            logger.error("1. Go to Google Cloud Console")
            logger.error("2. Enable YouTube Data API v3")
            logger.error("3. Create OAuth 2.0 client credentials")
            logger.error(f"4. Download and save as: {client_secrets_path}")
            return False
        
        try:
            # Run OAuth flow
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_path, 
                self.SCOPES
            )
            
            # Try to run local server flow first, fallback to console
            try:
                self.credentials = flow.run_local_server(port=0)
                logger.info("OAuth authentication completed via local server")
            except Exception:
                logger.info("Local server flow failed, trying console flow")
                self.credentials = flow.run_console()
                logger.info("OAuth authentication completed via console")
            
            self._save_credentials()
            self._build_service()
            return True
            
        except Exception as e:
            logger.error(f"OAuth authentication failed: {e}")
            return False
    
    def is_authenticated(self) -> bool:
        """Check if we have valid OAuth credentials"""
        return (self.credentials and 
                self.credentials.valid and 
                self.youtube_service is not None)
    
    async def fetch_transcript(self, video_id: str) -> Optional[VideoTranscript]:
        """
        Fetch transcript using OAuth-authenticated YouTube Data API
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            VideoTranscript object or None if not available
        """
        if not self.is_authenticated():
            logger.warning("OAuth authentication required for transcript fetching")
            logger.info("Run authenticate() method first or check OAuth setup")
            return None
        
        try:
            logger.info(f"Fetching transcript for {video_id} using OAuth YouTube Data API")
            
            # List available caption tracks
            captions_response = self.youtube_service.captions().list(
                part='id,snippet',
                videoId=video_id
            ).execute()
            
            caption_items = captions_response.get('items', [])
            if not caption_items:
                logger.info(f"No caption tracks found for video {video_id}")
                return None
            
            logger.debug(f"Found {len(caption_items)} caption tracks")
            
            # Find the best caption track (prefer manual, then auto-generated English)
            best_caption = self._select_best_caption(caption_items)
            if not best_caption:
                logger.info(f"No suitable caption track found for video {video_id}")
                return None
            
            caption_id = best_caption['id']
            language = best_caption['snippet']['language']
            track_kind = best_caption['snippet'].get('trackKind', 'unknown')
            
            logger.debug(f"Selected caption track: {caption_id} (language: {language}, kind: {track_kind})")
            
            # Download the caption track
            try:
                caption_content = self.youtube_service.captions().download(
                    id=caption_id,
                    tfmt='vtt'  # WebVTT format
                ).execute()
                
                if isinstance(caption_content, bytes):
                    caption_content = caption_content.decode('utf-8')
                
                logger.debug(f"Downloaded caption content: {len(caption_content)} characters")
                
                # Parse VTT content into transcript
                transcript = self._parse_vtt_content(caption_content, video_id, language)
                if transcript:
                    logger.info(f"Successfully fetched transcript via OAuth: {len(transcript.segments)} segments")
                    return transcript
                else:
                    logger.warning(f"Failed to parse VTT content for video {video_id}")
                    
            except Exception as download_error:
                # Check if it's a download restriction
                if 'downloadRestricted' in str(download_error) or 'forbidden' in str(download_error).lower():
                    logger.info(f"Caption track {caption_id} is download restricted")
                else:
                    logger.error(f"Error downloading caption track {caption_id}: {download_error}")
                
                # Try next caption track if available
                remaining_captions = [c for c in caption_items if c['id'] != caption_id]
                if remaining_captions:
                    logger.debug("Trying alternative caption tracks...")
                    for alt_caption in remaining_captions:
                        try:
                            alt_id = alt_caption['id']
                            alt_content = self.youtube_service.captions().download(
                                id=alt_id,
                                tfmt='vtt'
                            ).execute()
                            
                            if isinstance(alt_content, bytes):
                                alt_content = alt_content.decode('utf-8')
                            
                            transcript = self._parse_vtt_content(
                                alt_content, 
                                video_id, 
                                alt_caption['snippet']['language']
                            )
                            if transcript:
                                logger.info(f"Successfully fetched transcript using alternative track")
                                return transcript
                                
                        except Exception as alt_error:
                            logger.debug(f"Alternative caption track {alt_id} also failed: {alt_error}")
                            continue
        
        except Exception as e:
            logger.error(f"OAuth transcript fetch failed for {video_id}: {type(e).__name__}: {e}")
        
        return None
    
    def _select_best_caption(self, caption_items: List[Dict]) -> Optional[Dict]:
        """
        Select the best caption track from available options
        Priority: Manual English > Auto English > Manual other > Auto other
        """
        manual_english = []
        auto_english = []
        manual_other = []
        auto_other = []
        
        for item in caption_items:
            snippet = item['snippet']
            language = snippet['language']
            track_kind = snippet.get('trackKind', 'standard')
            
            is_english = language.startswith('en')
            is_manual = track_kind == 'standard'
            
            if is_english and is_manual:
                manual_english.append(item)
            elif is_english and not is_manual:
                auto_english.append(item)
            elif not is_english and is_manual:
                manual_other.append(item)
            else:
                auto_other.append(item)
        
        # Return best available option
        for category in [manual_english, auto_english, manual_other, auto_other]:
            if category:
                return category[0]
        
        return None
    
    def _parse_vtt_content(self, vtt_content: str, video_id: str, language: str) -> Optional[VideoTranscript]:
        """Parse WebVTT format content into VideoTranscript"""
        try:
            lines = vtt_content.strip().split('\n')
            segments = []
            full_text_parts = []
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # Skip empty lines and headers
                if not line or line.startswith('WEBVTT') or line.startswith('NOTE'):
                    i += 1
                    continue
                
                # Look for timestamp line (format: 00:00:00.000 --> 00:00:03.000)
                if '-->' in line:
                    try:
                        # Parse timestamp
                        start_str, end_str = line.split(' --> ')
                        start_time = self._parse_vtt_timestamp(start_str.strip())
                        end_time = self._parse_vtt_timestamp(end_str.strip())
                        duration = end_time - start_time
                        
                        # Get text lines following the timestamp
                        text_lines = []
                        i += 1
                        while i < len(lines) and lines[i].strip():
                            text_line = lines[i].strip()
                            # Remove VTT formatting tags
                            text_line = self._clean_vtt_text(text_line)
                            if text_line:
                                text_lines.append(text_line)
                            i += 1
                        
                        if text_lines:
                            text = ' '.join(text_lines)
                            segment = TranscriptSegment(
                                start_time=start_time,
                                duration=duration,
                                text=text
                            )
                            segments.append(segment)
                            full_text_parts.append(text)
                    
                    except Exception as parse_error:
                        logger.debug(f"Error parsing VTT segment: {parse_error}")
                
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
            logger.error(f"Error parsing VTT content: {e}")
        
        return None
    
    def _parse_vtt_timestamp(self, timestamp_str: str) -> float:
        """Parse VTT timestamp (HH:MM:SS.mmm) to seconds"""
        try:
            # Handle both HH:MM:SS.mmm and MM:SS.mmm formats
            parts = timestamp_str.split(':')
            if len(parts) == 3:
                hours, minutes, seconds = parts
                return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            elif len(parts) == 2:
                minutes, seconds = parts
                return int(minutes) * 60 + float(seconds)
            else:
                return float(timestamp_str)
        except:
            return 0.0
    
    def _clean_vtt_text(self, text: str) -> str:
        """Remove VTT formatting tags and clean text"""
        import re
        
        # Remove VTT tags like <c.colorname>, <i>, </i>, etc.
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove timing tags
        text = re.sub(r'<\d+:\d+:\d+\.\d+>', '', text)
        
        # Clean up extra whitespace
        text = ' '.join(text.split())
        
        return text.strip()
    
    def get_available_captions(self, video_id: str) -> List[Dict[str, Any]]:
        """
        Get list of available caption tracks for a video
        
        Returns:
            List of caption track information
        """
        if not self.is_authenticated():
            logger.warning("OAuth authentication required")
            return []
        
        try:
            response = self.youtube_service.captions().list(
                part='id,snippet',
                videoId=video_id
            ).execute()
            
            caption_info = []
            for item in response.get('items', []):
                snippet = item['snippet']
                caption_info.append({
                    'id': item['id'],
                    'language': snippet['language'],
                    'language_name': snippet.get('name', ''),
                    'track_kind': snippet.get('trackKind', 'standard'),
                    'is_auto_generated': snippet.get('trackKind') == 'ASR',
                    'is_draft': snippet.get('isDraft', False)
                })
            
            return caption_info
            
        except Exception as e:
            logger.error(f"Error fetching caption list for {video_id}: {e}")
            return []
    
    def setup_instructions(self) -> str:
        """Return setup instructions for OAuth authentication"""
        client_secrets_path = self._get_client_secrets_path()
        
        return f"""
OAuth Setup Instructions for YouTube Transcript Access:

1. Go to Google Cloud Console (https://console.cloud.google.com/)
2. Create a new project or select existing project
3. Enable YouTube Data API v3:
   - Go to APIs & Services > Library
   - Search for "YouTube Data API v3"
   - Click and enable it

4. Create OAuth 2.0 credentials:
   - Go to APIs & Services > Credentials
   - Click "Create Credentials" > "OAuth 2.0 Client IDs"
   - Choose "Desktop application"
   - Download the JSON file

5. Save the downloaded JSON file as:
   {client_secrets_path}

6. Run authentication:
   fetcher = OAuthTranscriptFetcher()
   fetcher.authenticate()

7. Grant permissions when prompted in browser

Note: This method requires user consent but bypasses all anti-bot protection
and works reliably for videos where captions are available for download.
"""