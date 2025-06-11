"""
Simple and reliable YouTube transcript fetcher
"""
import logging
import re
import json
import time
import random
import asyncio
import requests
from typing import Optional
from models import VideoTranscript, TranscriptSegment
from proxy_manager import proxy_manager

logger = logging.getLogger(__name__)

class SimpleTranscriptFetcher:
    """Simple transcript fetcher that mimics browser behavior"""
    
    def __init__(self, use_proxy: bool = True):
        self.use_proxy = use_proxy
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Origin': 'https://www.youtube.com',
            'Referer': 'https://www.youtube.com/',
        })
    
    async def fetch_transcript(self, video_id: str) -> Optional[VideoTranscript]:
        """Fetch transcript by extracting the timedtext URL from YouTube page"""
        try:
            # Step 1: Load the video page
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            logger.debug(f"Loading video page: {video_url}")

            response = self.session.get(video_url, timeout=15)
            if response.status_code != 200:
                logger.debug(f"Failed to load video page: {response.status_code}")
                return None

            page_content = response.text

            # Check if video is available
            if 'Video unavailable' in page_content or 'This video is not available' in page_content:
                logger.debug(f"Video {video_id} is unavailable")
                return None

            # Step 2: Extract the player response
            # YouTube embeds JSON data in the page containing caption information
            player_response = self._extract_player_response(page_content)
            if not player_response:
                logger.debug("Could not extract player response from page")
                return None

            # Step 3: Extract caption tracks
            caption_tracks = self._extract_caption_tracks(player_response)
            if not caption_tracks:
                logger.debug("No caption tracks found")
                return None

            # Step 4: Try all available caption tracks until we find one that works
            for track in caption_tracks:
                lang_code = track.get('languageCode', '')
                base_url = track.get('baseUrl')
                track_name = track.get('name', {}).get('simpleText', 'Unknown')

                if not base_url:
                    continue

                logger.debug(f"Trying caption track: {track_name} ({lang_code})")

                try:
                    # Fetch captions with exponential backoff retry
                    caption_response = await self._fetch_with_exponential_backoff(base_url, lang_code)
                    if not caption_response:
                        continue

                    caption_text = caption_response.text
                    if not caption_text:
                        logger.debug(f"Empty caption response for {lang_code}")
                        continue

                    # Try to parse the caption data
                    transcript = self._parse_caption_data(caption_text, video_id, lang_code)
                    if transcript:
                        logger.debug(f"Successfully fetched transcript using {track_name} ({lang_code}): {len(transcript.segments)} segments")
                        return transcript
                    else:
                        logger.debug(f"Failed to parse caption data for {lang_code}")

                except Exception as e:
                    logger.debug(f"Error fetching captions for {lang_code}: {e}")
                    continue

            logger.debug("All caption tracks failed")
            return None

        except Exception as e:
            logger.debug(f"Error fetching transcript: {type(e).__name__}: {e}")
            return None
    
    def _extract_player_response(self, page_content: str) -> Optional[dict]:
        """Extract player response JSON from page HTML"""
        try:
            # Method 1: Look for ytInitialPlayerResponse
            patterns = [
                r'var ytInitialPlayerResponse = ({.+?});',
                r'window\["ytInitialPlayerResponse"\] = ({.+?});',
                r'ytInitialPlayerResponse":\s*({.+?})(?:,|\})',
                r'ytInitialPlayerResponse\s*=\s*({.+?});'
            ]

            for pattern in patterns:
                match = re.search(pattern, page_content, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(1))
                    except json.JSONDecodeError:
                        continue

            # Method 2: Look for player response in ytInitialData
            match = re.search(r'var ytInitialData = ({.+?});', page_content, re.DOTALL)
            if match:
                try:
                    initial_data = json.loads(match.group(1))
                    # Navigate to find player response
                    player_response = (initial_data
                        .get('contents', {})
                        .get('twoColumnWatchNextResults', {})
                        .get('results', {})
                        .get('results', {})
                        .get('contents', [{}])[0]
                        .get('videoPrimaryInfoRenderer', {})
                        .get('playerResponse'))
                    if player_response:
                        return json.loads(player_response)
                except:
                    pass

            # Method 3: Look for embedded player config
            match = re.search(r'"PLAYER_CONFIG":\s*({.+?})\s*,', page_content, re.DOTALL)
            if match:
                try:
                    player_config = json.loads(match.group(1))
                    if 'args' in player_config and 'player_response' in player_config['args']:
                        return json.loads(player_config['args']['player_response'])
                except:
                    pass

        except Exception as e:
            logger.debug(f"Error extracting player response: {e}")

        return None
    
    def _extract_caption_tracks(self, player_response: dict) -> list:
        """Extract caption tracks from player response"""
        try:
            captions = player_response.get('captions', {})
            caption_tracks = captions.get('playerCaptionsTracklistRenderer', {}).get('captionTracks', [])
            
            if caption_tracks:
                logger.info(f"Found {len(caption_tracks)} caption tracks")
                for track in caption_tracks:
                    logger.debug(f"Caption track: {track.get('name', {}).get('simpleText', 'Unknown')} ({track.get('languageCode', 'Unknown')})")
            
            return caption_tracks
            
        except Exception as e:
            logger.debug(f"Error extracting caption tracks: {e}")
            return []
    
    def _parse_caption_data(self, caption_data: str, video_id: str, language: str = 'en') -> Optional[VideoTranscript]:
        """Parse caption data in various formats"""
        # Remove any BOM
        caption_data = caption_data.lstrip('\ufeff')

        # Try XML format first (most common)
        if caption_data.strip().startswith('<?xml') or '<transcript>' in caption_data or '<text' in caption_data:
            return self._parse_xml_captions(caption_data, video_id, language)

        # Try JSON format
        if caption_data.strip().startswith('{') or caption_data.strip().startswith('['):
            return self._parse_json_captions(caption_data, video_id, language)

        return None
    
    def _parse_xml_captions(self, xml_data: str, video_id: str, language: str = 'en') -> Optional[VideoTranscript]:
        """Parse XML format captions"""
        try:
            import xml.etree.ElementTree as ET
            import html

            root = ET.fromstring(xml_data)
            segments = []
            full_text_parts = []

            # Handle different XML structures
            text_elements = root.findall('.//text') or root.findall('text')

            for elem in text_elements:
                start = float(elem.attrib.get('start', 0))
                dur = float(elem.attrib.get('dur', 0))
                text = html.unescape(elem.text or '')

                # Clean up the text - remove extra whitespace and newlines
                text = ' '.join(text.split()).strip()
                if text:
                    segment = TranscriptSegment(
                        start_time=start,
                        duration=dur,
                        text=text
                    )
                    segments.append(segment)
                    full_text_parts.append(text)

            if segments:
                full_text = ' '.join(full_text_parts)
                return VideoTranscript(
                    video_id=video_id,
                    language=language,
                    segments=segments,
                    full_text=full_text
                )

        except Exception as e:
            logger.debug(f"Error parsing XML captions: {e}")

        return None
    
    def _parse_json_captions(self, json_data: str, video_id: str, language: str = 'en') -> Optional[VideoTranscript]:
        """Parse JSON format captions (srv3 format)"""
        try:
            data = json.loads(json_data)

            if 'events' in data:
                segments = []
                full_text_parts = []

                for event in data['events']:
                    # Skip events without segments
                    if 'segs' not in event:
                        continue

                    # Combine all segments in this event
                    text_parts = []
                    for seg in event['segs']:
                        if 'utf8' in seg:
                            text_parts.append(seg['utf8'])

                    text = ''.join(text_parts)
                    # Clean up the text - remove extra whitespace and newlines
                    text = ' '.join(text.split()).strip()
                    if text:
                        start_time = event.get('tStartMs', 0) / 1000.0
                        duration = event.get('dDurationMs', 0) / 1000.0

                        segment = TranscriptSegment(
                            start_time=start_time,
                            duration=duration,
                            text=text
                        )
                        segments.append(segment)
                        full_text_parts.append(text)

                if segments:
                    full_text = ' '.join(full_text_parts)
                    return VideoTranscript(
                        video_id=video_id,
                        language=language,
                        segments=segments,
                        full_text=full_text
                    )

        except Exception as e:
            logger.debug(f"Error parsing JSON captions: {e}")

        return None
    
    async def _fetch_with_exponential_backoff(self, url: str, lang_code: str, max_retries: int = 3) -> Optional[requests.Response]:
        """Fetch URL with exponential backoff retry logic and optional proxy rotation"""
        for attempt in range(max_retries):
            try:
                # Calculate delay: 1s, 2s, 4s + random jitter
                if attempt > 0:
                    delay = (2 ** attempt) + random.uniform(0.5, 1.5)
                    logger.debug(f"Retrying {lang_code} after {delay:.1f}s delay (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(delay)
                
                # Use proxy session if enabled and proxies are available
                session_to_use = self.session
                if self.use_proxy and attempt > 0:  # Use proxy on retries
                    try:
                        await proxy_manager.refresh_working_proxies()
                        if proxy_manager.working_proxies:
                            session_to_use = proxy_manager.get_proxy_session()
                            logger.debug(f"Using proxy for retry attempt {attempt + 1}")
                    except Exception as e:
                        logger.debug(f"Failed to get proxy session: {e}")
                
                # Enhanced headers to look more like a real browser
                enhanced_headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'same-origin',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0'
                }
                
                # Update session headers for this request
                old_headers = session_to_use.headers.copy()
                session_to_use.headers.update(enhanced_headers)
                
                try:
                    response = session_to_use.get(url, timeout=15)
                    if response.status_code == 200 and response.text:
                        logger.debug(f"Successfully fetched captions for {lang_code} on attempt {attempt + 1}")
                        return response
                    else:
                        logger.debug(f"Failed to fetch captions for {lang_code}: HTTP {response.status_code}, content length: {len(response.text)}")
                        
                        # If using proxy and got bad response, report proxy failure
                        if session_to_use != self.session and hasattr(session_to_use, 'proxies'):
                            proxy_manager.report_proxy_failure(session_to_use.proxies)
                            
                finally:
                    # Restore original headers
                    session_to_use.headers = old_headers
                    
            except Exception as e:
                logger.debug(f"Error fetching captions for {lang_code} (attempt {attempt + 1}): {type(e).__name__}: {e}")
                
                # If using proxy and got error, report proxy failure
                if session_to_use != self.session and hasattr(session_to_use, 'proxies'):
                    proxy_manager.report_proxy_failure(session_to_use.proxies)
                
                if attempt == max_retries - 1:
                    logger.debug(f"All retry attempts failed for {lang_code}")
                    
        return None