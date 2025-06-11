#!/usr/bin/env python3

import os
import sys
import asyncio
import logging
from youtube_service import YouTubeService
from config import get_settings

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_transcript_fetch():
    """Test transcript fetching for the problematic video"""
    
    # Load settings
    settings = get_settings()
    
    # Initialize YouTube service
    youtube_service = YouTubeService(settings.youtube_api_key)
    
    # Test multiple video IDs with different characteristics
    test_videos = [
        "o7aQhb-PK08",  # The specific video user is trying
        "dQw4w9WgXcQ",  # Rick Roll - popular, old video
        "9bZkp7q19f0",  # PSY - Gangnam Style - extremely popular
        "kJQP7kiw5Fk",  # Despacito - very popular
        "000yxkGXSVM",  # Original video from screenshot
    ]
    
    # Test each video with smart retry logic
    for i, video_id in enumerate(test_videos):
        logger.info("=" * 80)
        logger.info(f"TESTING VIDEO {i+1}/{len(test_videos)}: {video_id}")
        logger.info(f"Video URL: https://www.youtube.com/watch?v={video_id}")
        logger.info("=" * 80)
        
        try:
            # Test the main method with all strategies
            result = await youtube_service.get_video_transcript(video_id)
            if result:
                logger.info(f"SUCCESS for {video_id}: {len(result.segments)} segments, language: {result.language}")
                logger.info(f"First 200 characters: {result.full_text[:200]}...")
                
                # If we found a working video, note it for future reference
                logger.info(f"*** WORKING VIDEO FOUND: {video_id} ***")
                
                # Test a few more to see pattern
                if i < 2:  # Test first 3 videos thoroughly
                    continue
                else:
                    logger.info("Found working video, continuing with remaining tests...")
                    
            else:
                logger.warning(f"FAILED for {video_id}: No transcript returned")
                
        except Exception as e:
            logger.error(f"ERROR for {video_id}: {type(e).__name__}: {e}")
        
        # Add delay between videos to avoid rate limiting
        if i < len(test_videos) - 1:
            logger.info("Waiting 3 seconds before next video...")
            await asyncio.sleep(3)
    
    # Cleanup
    youtube_service.cleanup()
    logger.info("Test completed and resources cleaned up")

if __name__ == "__main__":
    asyncio.run(test_transcript_fetch())
