#!/usr/bin/env python3

import asyncio
from youtube_transcript_api import YouTubeTranscriptApi

async def test_correct_api():
    """Test the correct API usage"""
    video_id = "000yxkGXSVM"
    
    print(f"Testing correct API for video: {video_id}")
    
    try:
        # Get the transcript list
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        print(f"TranscriptList type: {type(transcript_list)}")
        print(f"Is iterable: {hasattr(transcript_list, '__iter__')}")
        
        # List all available transcripts
        print("\nAvailable transcripts:")
        for transcript in transcript_list:
            print(f"  - Language: {transcript.language} ({transcript.language_code})")
            print(f"    Generated: {transcript.is_generated}")
            print(f"    Translation languages: {len(transcript.translation_languages)}")
        
        # Try to find English transcript
        try:
            transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
            print(f"\nFound English transcript: {transcript.language} ({transcript.language_code})")
            
            # Fetch the transcript
            transcript_data = transcript.fetch()
            print(f"Transcript has {len(transcript_data)} segments")
            
            # Show first few segments
            for i, segment in enumerate(transcript_data[:3]):
                print(f"  {i+1}. [{segment['start']:.2f}s] {segment['text']}")
                
        except Exception as e:
            print(f"Could not find English transcript: {e}")
            
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_correct_api())
