"""
Browser-based YouTube transcript fetcher using Selenium
"""
import logging
import time
import re
import json
import asyncio
from typing import Optional, List
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from models import VideoTranscript, TranscriptSegment

logger = logging.getLogger(__name__)

class BrowserTranscriptFetcher:
    """Fetch transcripts using real browser automation with Selenium"""
    
    def __init__(self):
        self.driver = None
        self._setup_driver()
    
    def _setup_driver(self):
        """Setup Chrome driver with optimized options"""
        try:
            chrome_options = Options()
            
            # Browser arguments for stealth and performance
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Disable images and CSS for faster loading
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.managed_default_content_settings.stylesheets": 2
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            # User agent to look like real browser
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36')
            
            # Install and setup ChromeDriver automatically
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Execute script to remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("Browser driver initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup Chrome driver: {e}")
            self.driver = None
    
    async def fetch_transcript(self, video_id: str) -> Optional[VideoTranscript]:
        """Fetch transcript using browser automation"""
        if not self.driver:
            logger.error("Browser driver not available")
            return None
            
        try:
            logger.info(f"Fetching transcript for {video_id} using browser automation")
            
            # Load the video page
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            self.driver.get(video_url)
            
            # Wait for page to load
            await asyncio.sleep(3)
            
            # Check if video is available
            try:
                error_element = self.driver.find_element(By.CSS_SELECTOR, "[class*='error-message']")
                if error_element:
                    logger.debug(f"Video {video_id} appears to be unavailable")
                    return None
            except NoSuchElementException:
                pass  # Good, no error message found
            
            # Look for transcript button/menu
            transcript = await self._extract_transcript_from_page(video_id)
            if transcript:
                logger.info(f"Successfully extracted transcript using browser: {len(transcript.segments)} segments")
                return transcript
            
            # Alternative: Extract from page source
            transcript = await self._extract_transcript_from_source(video_id)
            if transcript:
                logger.info(f"Successfully extracted transcript from page source: {len(transcript.segments)} segments")
                return transcript
                
            logger.debug(f"No transcript found for {video_id} using browser automation")
            return None
            
        except Exception as e:
            logger.error(f"Error in browser transcript fetching for {video_id}: {type(e).__name__}: {e}")
            return None
    
    async def _extract_transcript_from_page(self, video_id: str) -> Optional[VideoTranscript]:
        """Try to extract transcript by interacting with YouTube's transcript UI"""
        try:
            # Look for the three-dot menu button
            wait = WebDriverWait(self.driver, 10)
            
            # Wait for video player to load
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#movie_player")))
            
            # Try to find the more actions menu (three dots)
            try:
                more_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 
                    "button[aria-label*='More actions'], button[aria-label*='More'], .ytp-button[aria-label*='More']")))
                more_button.click()
                await asyncio.sleep(1)
                
                # Look for transcript option in the menu
                transcript_button = self.driver.find_element(By.XPATH, 
                    "//div[contains(text(), 'Show transcript') or contains(text(), 'Transcript')]")
                transcript_button.click()
                await asyncio.sleep(2)
                
                # Extract transcript segments from the transcript panel
                transcript_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                    ".ytd-transcript-segment-renderer, .transcript-segment")
                
                if transcript_elements:
                    segments = []
                    full_text_parts = []
                    
                    for element in transcript_elements:
                        try:
                            # Extract timestamp and text
                            time_element = element.find_element(By.CSS_SELECTOR, 
                                ".ytd-transcript-segment-renderer .segment-timestamp")
                            text_element = element.find_element(By.CSS_SELECTOR, 
                                ".ytd-transcript-segment-renderer .segment-text")
                            
                            timestamp_text = time_element.text.strip()
                            text = text_element.text.strip()
                            
                            # Parse timestamp (format: "0:00" or "1:23")
                            start_time = self._parse_timestamp(timestamp_text)
                            
                            if text and start_time is not None:
                                segment = TranscriptSegment(
                                    start_time=start_time,
                                    duration=0.0,  # Duration not available from UI
                                    text=text
                                )
                                segments.append(segment)
                                full_text_parts.append(text)
                                
                        except Exception as e:
                            logger.debug(f"Error extracting transcript segment: {e}")
                            continue
                    
                    if segments:
                        full_text = ' '.join(full_text_parts)
                        return VideoTranscript(
                            video_id=video_id,
                            language='en',  # Assume English for UI-extracted transcripts
                            segments=segments,
                            full_text=full_text
                        )
                        
            except Exception as e:
                logger.debug(f"Could not interact with transcript UI: {e}")
                
        except Exception as e:
            logger.debug(f"Error in UI-based transcript extraction: {e}")
            
        return None
    
    async def _extract_transcript_from_source(self, video_id: str) -> Optional[VideoTranscript]:
        """Extract transcript from page source (similar to SimpleTranscriptFetcher but with real browser)"""
        try:
            page_source = self.driver.page_source
            
            # Extract player response from page source
            player_response = self._extract_player_response(page_source)
            if not player_response:
                return None
            
            # Extract caption tracks
            caption_tracks = self._extract_caption_tracks(player_response)
            if not caption_tracks:
                return None
            
            # Try to fetch captions using the browser's session
            for track in caption_tracks:
                try:
                    lang_code = track.get('languageCode', '')
                    base_url = track.get('baseUrl')
                    
                    if not base_url:
                        continue
                    
                    # Use browser to fetch the caption URL
                    self.driver.get(base_url)
                    await asyncio.sleep(1)
                    
                    # Get the page source which should contain the caption data
                    caption_data = self.driver.page_source
                    
                    if caption_data and len(caption_data) > 100:  # Ensure we got actual content
                        transcript = self._parse_caption_data(caption_data, video_id, lang_code)
                        if transcript:
                            return transcript
                            
                except Exception as e:
                    logger.debug(f"Error fetching caption track {lang_code}: {e}")
                    continue
                    
        except Exception as e:
            logger.debug(f"Error in source-based transcript extraction: {e}")
            
        return None
    
    def _parse_timestamp(self, timestamp_text: str) -> Optional[float]:
        """Parse timestamp string like '1:23' into seconds"""
        try:
            if ':' in timestamp_text:
                parts = timestamp_text.split(':')
                if len(parts) == 2:
                    minutes, seconds = parts
                    return int(minutes) * 60 + int(seconds)
                elif len(parts) == 3:
                    hours, minutes, seconds = parts
                    return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
            else:
                return float(timestamp_text)
        except:
            return None
    
    def _extract_player_response(self, page_source: str) -> Optional[dict]:
        """Extract player response from page source (same logic as SimpleTranscriptFetcher)"""
        try:
            patterns = [
                r'var ytInitialPlayerResponse = ({.+?});',
                r'window\["ytInitialPlayerResponse"\] = ({.+?});',
                r'ytInitialPlayerResponse":\s*({.+?})(?:,|\})',
                r'ytInitialPlayerResponse\s*=\s*({.+?});'
            ]

            for pattern in patterns:
                match = re.search(pattern, page_source, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(1))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.debug(f"Error extracting player response: {e}")
        return None
    
    def _extract_caption_tracks(self, player_response: dict) -> list:
        """Extract caption tracks from player response"""
        try:
            captions = player_response.get('captions', {})
            caption_tracks = captions.get('playerCaptionsTracklistRenderer', {}).get('captionTracks', [])
            return caption_tracks
        except Exception as e:
            logger.debug(f"Error extracting caption tracks: {e}")
            return []
    
    def _parse_caption_data(self, caption_data: str, video_id: str, language: str) -> Optional[VideoTranscript]:
        """Parse caption data (reuse logic from SimpleTranscriptFetcher)"""
        # This would contain the same parsing logic as SimpleTranscriptFetcher._parse_caption_data
        # For brevity, I'll implement a simplified version
        try:
            # Look for XML-style captions
            if '<transcript>' in caption_data or '<text start=' in caption_data:
                segments = []
                full_text_parts = []
                
                # Simple regex to extract caption segments
                pattern = r'<text start="([^"]+)"[^>]*>([^<]+)</text>'
                matches = re.findall(pattern, caption_data, re.DOTALL)
                
                for start_time_str, text in matches:
                    try:
                        start_time = float(start_time_str)
                        clean_text = text.strip()
                        
                        if clean_text:
                            segment = TranscriptSegment(
                                start_time=start_time,
                                duration=0.0,
                                text=clean_text
                            )
                            segments.append(segment)
                            full_text_parts.append(clean_text)
                    except:
                        continue
                
                if segments:
                    full_text = ' '.join(full_text_parts)
                    return VideoTranscript(
                        video_id=video_id,
                        language=language,
                        segments=segments,
                        full_text=full_text
                    )
        except Exception as e:
            logger.debug(f"Error parsing caption data: {e}")
        
        return None
    
    def cleanup(self):
        """Clean up browser resources"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Browser driver cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up browser driver: {e}")
            finally:
                self.driver = None
    
    def __del__(self):
        """Ensure cleanup on object destruction"""
        self.cleanup()