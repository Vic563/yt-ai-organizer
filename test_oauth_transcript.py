#!/usr/bin/env python3

import os
import sys
import asyncio
import logging
from oauth_transcript_fetcher import OAuthTranscriptFetcher

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_oauth_transcript():
    """Test OAuth-based transcript fetching"""
    
    logger.info("Testing OAuth-based YouTube transcript fetching")
    
    # Initialize OAuth fetcher
    fetcher = OAuthTranscriptFetcher()
    
    # Check if already authenticated
    if fetcher.is_authenticated():
        logger.info("✅ OAuth authentication already set up")
    else:
        logger.info("❌ OAuth authentication not set up")
        logger.info("\n" + fetcher.setup_instructions())
        
        # Ask user if they want to set up OAuth now
        response = input("\nWould you like to set up OAuth authentication now? (y/N): ")
        if response.lower() in ['y', 'yes']:
            success = fetcher.authenticate()
            if not success:
                logger.error("Failed to set up OAuth authentication")
                return
        else:
            logger.info("OAuth setup skipped. Cannot test OAuth transcript fetching.")
            return
    
    # Test videos - start with the user's problematic video
    test_videos = [
        ("o7aQhb-PK08", "User's problematic video"),
        ("dQw4w9WgXcQ", "Rick Roll - popular video"),
        ("9bZkp7q19f0", "PSY - Gangnam Style"),
    ]
    
    logger.info(f"\nTesting OAuth transcript fetching on {len(test_videos)} videos...")
    
    for video_id, description in test_videos:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing: {description}")
        logger.info(f"Video ID: {video_id}")
        logger.info(f"URL: https://www.youtube.com/watch?v={video_id}")
        logger.info(f"{'='*60}")
        
        try:
            # Get available captions first
            captions = fetcher.get_available_captions(video_id)
            if captions:
                logger.info(f"Available captions:")
                for caption in captions:
                    logger.info(f"  - {caption['language']} ({caption['language_name']}) - {'Auto' if caption['is_auto_generated'] else 'Manual'}")
            else:
                logger.warning(f"No captions found for {video_id}")
                continue
            
            # Fetch transcript
            transcript = await fetcher.fetch_transcript(video_id)
            
            if transcript:
                logger.info(f"✅ SUCCESS: Fetched transcript for {video_id}")
                logger.info(f"   Language: {transcript.language}")
                logger.info(f"   Segments: {len(transcript.segments)}")
                logger.info(f"   Total characters: {len(transcript.full_text)}")
                logger.info(f"   First 200 characters: {transcript.full_text[:200]}...")
                
                # Show first few segments
                if transcript.segments:
                    logger.info("   First 3 segments:")
                    for i, segment in enumerate(transcript.segments[:3]):
                        logger.info(f"     {segment.start_time:.1f}s: {segment.text}")
                
                logger.info(f"🎉 OAuth transcript fetching WORKS for {description}!")
                
            else:
                logger.warning(f"❌ No transcript returned for {video_id} - may be download restricted")
            
        except Exception as e:
            logger.error(f"❌ Error testing {video_id}: {type(e).__name__}: {e}")
        
        # Add delay between requests to be respectful
        if video_id != test_videos[-1][0]:  # Don't delay after last video
            logger.info("Waiting 2 seconds before next test...")
            await asyncio.sleep(2)
    
    logger.info(f"\n{'='*60}")
    logger.info("OAuth transcript testing completed!")
    logger.info(f"{'='*60}")

if __name__ == "__main__":
    try:
        asyncio.run(test_oauth_transcript())
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}")
        sys.exit(1)