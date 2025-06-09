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
    
    # Test video ID that should have a transcript
    video_id = "000yxkGXSVM"  # The video from your screenshot
    
    logger.info(f"Testing transcript fetch for video: {video_id}")
    logger.info(f"Video URL: https://www.youtube.com/watch?v={video_id}")
    
    try:
        # Test each strategy individually
        logger.info("=" * 50)
        logger.info("TESTING STRATEGY 1: Basic with retries")
        logger.info("=" * 50)
        
        result1 = await youtube_service._fetch_transcript_with_retries(video_id)
        if result1:
            logger.info(f"Strategy 1 SUCCESS: {len(result1.segments)} segments, language: {result1.language}")
        else:
            logger.info("Strategy 1 FAILED: No transcript returned")
            
    except Exception as e:
        logger.error(f"Strategy 1 ERROR: {type(e).__name__}: {e}")
    
    try:
        logger.info("=" * 50)
        logger.info("TESTING STRATEGY 2: Enhanced headers")
        logger.info("=" * 50)
        
        result2 = await youtube_service._fetch_transcript_with_proxy_headers(video_id)
        if result2:
            logger.info(f"Strategy 2 SUCCESS: {len(result2.segments)} segments, language: {result2.language}")
        else:
            logger.info("Strategy 2 FAILED: No transcript returned")
            
    except Exception as e:
        logger.error(f"Strategy 2 ERROR: {type(e).__name__}: {e}")
    
    try:
        logger.info("=" * 50)
        logger.info("TESTING STRATEGY 3: Basic fallback")
        logger.info("=" * 50)
        
        result3 = await youtube_service._fetch_transcript_basic(video_id)
        if result3:
            logger.info(f"Strategy 3 SUCCESS: {len(result3.segments)} segments, language: {result3.language}")
        else:
            logger.info("Strategy 3 FAILED: No transcript returned")
            
    except Exception as e:
        logger.error(f"Strategy 3 ERROR: {type(e).__name__}: {e}")
    
    logger.info("=" * 50)
    logger.info("TESTING MAIN METHOD")
    logger.info("=" * 50)
    
    # Test the main method
    result = await youtube_service.get_video_transcript(video_id)
    if result:
        logger.info(f"MAIN METHOD SUCCESS: {len(result.segments)} segments, language: {result.language}")
        logger.info(f"First 200 characters: {result.full_text[:200]}...")
    else:
        logger.error("MAIN METHOD FAILED: No transcript returned")

if __name__ == "__main__":
    asyncio.run(test_transcript_fetch())
