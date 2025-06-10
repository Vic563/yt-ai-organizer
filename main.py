from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Callable, Awaitable
import os
import logging
import time

from config import get_settings, clear_settings_cache
from database import init_database, get_db_connection
from youtube_service import YouTubeService
from gemini_service import GeminiService
from chat_handler import ChatHandler
from models import ChatMessage, ChatResponse, ConfigUpdate, LibraryStats, TopicUpdate, TopicRename
from topic_service import TopicManager
from cost_api import router as cost_router
from performance_middleware import performance_middleware
from performance_api import router as performance_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Project Insight API",
    description="Conversational AI interface for YouTube video library exploration",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add performance monitoring middleware
app.middleware("http")(performance_middleware)

# Initialize services
settings = get_settings()
youtube_service = None
gemini_service = None
chat_handler = None

def init_services():
    settings = get_settings()
    
    # Initialize services if configured
    if settings.google_ai_api_key and settings.youtube_api_key:
        global youtube_service, gemini_service, chat_handler
        gemini_service = GeminiService(settings.google_ai_api_key)
        youtube_service = YouTubeService(
            api_key=settings.youtube_api_key,
            gemini_api_key=settings.google_ai_api_key
        )
        chat_handler = ChatHandler(gemini_service, youtube_service)
        logger.info("Services initialized successfully")
    else:
        logger.warning("Missing required API keys. Some features may be disabled.")

@app.on_event("startup")
async def startup_event():
    """Initialize database and services on startup"""
    logger.info("Starting Project Insight API...")
    
    # Initialize database
    init_database()
    
    # Initialize services if configured
    init_services()
    logger.info("Services initialized successfully")

# Configuration endpoints
@app.get("/api/config/check")
async def check_configuration():
    """Check if the application is properly configured"""
    try:
        # Get fresh settings
        current_settings = get_settings()
        configured = bool(current_settings.google_ai_api_key and current_settings.youtube_api_key and current_settings.google_cloud_project_id)
        
        logger.info(f"Config check - Google AI API Key: {'Set' if current_settings.google_ai_api_key else 'Not set'}")
        logger.info(f"Config check - YouTube API Key: {'Set' if current_settings.youtube_api_key else 'Not set'}")
        logger.info(f"Config check - Google Cloud Project ID: {current_settings.google_cloud_project_id or 'Not set'}")
        
        return {
            "configured": configured,
            "keys": {
                "googleAiApiKey": bool(current_settings.google_ai_api_key),
                "youtubeApiKey": bool(current_settings.youtube_api_key),
                "googleCloudProjectId": current_settings.google_cloud_project_id
            }
        }
    except Exception as e:
        logger.error(f"Error checking configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to check configuration")

@app.post("/api/config/update")
async def update_configuration(config: ConfigUpdate):
    """Update API configuration"""
    try:
        logger.info(f"Received /api/config/update request")
        logger.info(f"googleAiApiKey: {config.googleAiApiKey}")
        logger.info(f"youtubeApiKey: {config.youtubeApiKey}")
        logger.info(f"googleCloudProjectId: {config.googleCloudProjectId}")
        env_path = ".env"
        env_vars = {}
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and "=" in line and not line.startswith("#"):
                        key, value = line.split("=", 1)
                        env_vars[key.strip()] = value.strip()
        
        # Update with new values if provided and valid
        logger.info(f"Current env_vars before update: {env_vars}")
        # Only update if a non-null, non-empty value is provided
        if config.googleAiApiKey and config.googleAiApiKey.strip():
            env_vars["GOOGLE_AI_API_KEY"] = config.googleAiApiKey
            logger.info("Updating GOOGLE_AI_API_KEY")
        if config.youtubeApiKey and config.youtubeApiKey.strip():
            env_vars["YOUTUBE_API_KEY"] = config.youtubeApiKey
            logger.info("Updating YOUTUBE_API_KEY")
        if config.googleCloudProjectId and config.googleCloudProjectId.strip():
            env_vars["GOOGLE_CLOUD_PROJECT_ID"] = config.googleCloudProjectId
            logger.info("Updating GOOGLE_CLOUD_PROJECT_ID")

        logger.info(f"Attempting to write to .env. env_vars to be written: {env_vars}")
        with open(env_path, "w") as f:
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")
        
        # Clear the settings cache and reinitialize
        clear_settings_cache()
        
        # Reinitialize settings
        global settings, youtube_service, gemini_service, chat_handler
        settings = get_settings()
        
        # Log the new settings to verify they were loaded
        logger.info(f"New settings loaded - Google AI API Key: {'Set' if settings.google_ai_api_key else 'Not set'}")
        logger.info(f"New settings loaded - YouTube API Key: {'Set' if settings.youtube_api_key else 'Not set'}")
        logger.info(f"New settings loaded - Google Cloud Project ID: {settings.google_cloud_project_id or 'Not set'}")
        
        # Test the API keys by initializing services
        init_services()
        logger.info(".env file updated and services re-initialized.")
        
        logger.info("Configuration updated and tested successfully")
        return {"success": True, "message": "Configuration updated and services reinitialized"}
        
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        return {"success": False, "message": f"Configuration failed: {str(e)}"}

# Video management endpoints
@app.post("/api/videos/add")
async def add_video(video_data: dict):
    """Add a video to the library by URL"""
    if not youtube_service:
        raise HTTPException(status_code=400, detail="YouTube service not configured")

    video_url = video_data.get("url")
    if not video_url:
        raise HTTPException(status_code=400, detail="Video URL is required")

    try:
        logger.info(f"Adding video: {video_url}")
        result = await youtube_service.add_video_by_url(video_url)
        logger.info(f"Add video result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error adding video: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add video: {str(e)}")

@app.delete("/api/videos/{video_id}")
async def remove_video(video_id: str):
    """Remove a video from the library"""
    if not youtube_service:
        raise HTTPException(status_code=400, detail="YouTube service not configured")

    try:
        logger.info(f"Removing video: {video_id}")
        result = await youtube_service.remove_video(video_id)
        logger.info(f"Remove video result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error removing video: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove video: {str(e)}")

@app.get("/api/videos")
async def get_all_videos():
    """Get all videos in the library"""
    try:
        from database import get_all_videos
        videos = get_all_videos()
        return {"videos": videos}
    except Exception as e:
        logger.error(f"Error getting videos: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get videos: {str(e)}")

@app.post("/api/videos/{video_id}/retry-transcript")
async def retry_video_transcript(video_id: str):
    """Retry fetching transcript for a specific video"""
    if not youtube_service:
        raise HTTPException(status_code=400, detail="YouTube service not configured")
    
    try:
        logger.info(f"Retrying transcript fetch for video: {video_id}")
        success = await youtube_service.retry_transcript_fetch(video_id)
        
        if success:
            return {"success": True, "message": "Transcript fetched successfully"}
        else:
            return {"success": False, "message": "Transcript still unavailable. This could be due to rate limiting, restricted access, or the video not having captions."}
    except Exception as e:
        logger.error(f"Error retrying transcript fetch: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retry transcript fetch: {str(e)}")

@app.post("/api/videos/retry-all-transcripts")
async def retry_all_missing_transcripts():
    """Retry fetching transcripts for all videos without transcripts"""
    if not youtube_service:
        raise HTTPException(status_code=400, detail="YouTube service not configured")
    
    try:
        logger.info("Retrying transcript fetch for all videos without transcripts")
        count = await youtube_service._fetch_missing_transcripts()
        return {
            "success": True, 
            "message": f"Fetched {count} new transcripts",
            "transcripts_fetched": count
        }
    except Exception as e:
        logger.error(f"Error retrying all transcript fetches: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retry transcript fetches: {str(e)}")

@app.get("/api/library/stats")
async def get_library_stats():
    """Get library statistics"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get total videos
            cursor.execute("SELECT COUNT(*) FROM videos")
            total_videos = cursor.fetchone()[0]
            
            # Get videos with transcripts
            cursor.execute("SELECT COUNT(*) FROM videos WHERE has_transcript = 1")
            videos_with_transcripts = cursor.fetchone()[0]
            
            # Get last sync time
            cursor.execute("SELECT MAX(created_at) FROM videos")
            last_sync = cursor.fetchone()[0]
            
            return LibraryStats(
                total_videos=total_videos,
                videos_with_transcripts=videos_with_transcripts,
                last_sync=last_sync
            )
    except Exception as e:
        logger.error(f"Error getting library stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get library statistics")

# Topic endpoints
@app.get("/api/topics")
async def get_topics():
    """Get all available topics with video counts"""
    try:
        with get_db_connection() as conn:
            topic_manager = TopicManager(conn)
            topics = topic_manager.get_all_topics()
            return {"topics": topics}
    except Exception as e:
        logger.error(f"Error getting topics: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch topics")

@app.get("/api/topics/{topic_name}/videos")
async def get_videos_by_topic(topic_name: str):
    """Get all videos for a specific topic"""
    try:
        with get_db_connection() as conn:
            topic_manager = TopicManager(conn)
            
            # First get the topic ID
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM topics WHERE name = ?", (topic_name,))
            topic = cursor.fetchone()
            
            if not topic:
                return {"videos": []}
                
            videos = topic_manager.get_videos_by_topic(topic[0])
            return {"videos": videos}
    except Exception as e:
        logger.error(f"Error getting videos for topic {topic_name}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch videos for topic")

@app.put("/api/videos/{video_id}/topic")
async def update_video_topic(video_id: str, topic_update: TopicUpdate):
    """Update the topic for a video"""
    try:
        with get_db_connection() as conn:
            topic_manager = TopicManager(conn)
            success = topic_manager.update_video_topic(
                video_id=video_id,
                topic_name=topic_update.topic_name,
                confidence=1.0,  # Manual updates get full confidence
                auto_generated=False
            )
            
            if not success:
                raise HTTPException(status_code=400, detail="Failed to update video topic")
                
            return {"success": True, "message": f"Video topic updated to '{topic_update.topic_name}'"}
    except Exception as e:
        logger.error(f"Error updating video topic: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/topics/rename")
async def rename_topic(topic_rename: TopicRename):
    """Rename a topic"""
    try:
        with get_db_connection() as conn:
            topic_manager = TopicManager(conn)
            success = topic_manager.rename_topic(
                old_name=topic_rename.old_name,
                new_name=topic_rename.new_name
            )
            
            if not success:
                raise HTTPException(status_code=400, detail="Failed to rename topic. Topic may not exist or new name may already be in use.")
                
            return {"success": True, "message": f"Topic renamed from '{topic_rename.old_name}' to '{topic_rename.new_name}'"}
    except Exception as e:
        logger.error(f"Error renaming topic: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Chat endpoints
@app.post("/api/chat/message")
async def send_chat_message(message: ChatMessage):
    """Process a chat message and return AI response"""
    if not chat_handler:
        raise HTTPException(status_code=400, detail="Chat service not configured")
    
    try:
        logger.info(f"Processing chat message: {message.message[:50]}...")
        response = await chat_handler.process_message(
            message.message, 
            message.conversation_history
        )
        logger.info("Chat response generated successfully")
        return response
    except Exception as e:
        logger.error(f"Error processing chat message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        with get_db_connection() as conn:
            conn.cursor().execute("SELECT 1")
            db_status = "connected"
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        db_status = f"error: {str(e)}"

    return {
        "status": "ok",
        "services": {
            "youtube": youtube_service is not None,
            "gemini": gemini_service is not None,
            "chat": chat_handler is not None,
            "database": db_status
        }
    }

# Include API routes
app.include_router(cost_router)
app.include_router(performance_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
