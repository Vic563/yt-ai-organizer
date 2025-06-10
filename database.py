import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional, Dict, Any

from config import get_settings, ensure_data_directories
from models import VideoMetadata
from database_migrations import run_migrations
from database_search import search_videos_safe

logger = logging.getLogger(__name__)

def init_database():
    """Initialize the SQLite database with required tables"""
    ensure_data_directories()
    settings = get_settings()
    
    try:
        with sqlite3.connect(settings.database_path) as conn:
            cursor = conn.cursor()
            
            # Create videos table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    video_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    channel_id TEXT NOT NULL,
                    channel_title TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    duration TEXT,
                    thumbnail_url TEXT,
                    view_count INTEGER,
                    like_count INTEGER,
                    has_transcript BOOLEAN DEFAULT FALSE,
                    transcript_language TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create conversations table for chat history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create messages table for conversation history
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                )
            """)
            
            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_channel ON videos(channel_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_published ON videos(published_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_transcript ON videos(has_transcript)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id)")
            
            conn.commit()
            logger.info("Database initialized successfully")
            
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

@contextmanager
def get_db_connection():
    """Get database connection with automatic cleanup"""
    settings = get_settings()
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
    try:
        yield conn
    finally:
        conn.close()

def insert_video(video: VideoMetadata) -> bool:
    """Insert or update video metadata in database"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if video exists
            cursor.execute("SELECT video_id FROM videos WHERE video_id = ?", (video.video_id,))
            exists = cursor.fetchone()
            
            if exists:
                # Update existing video
                cursor.execute("""
                    UPDATE videos SET
                        title = ?, description = ?, channel_id = ?, channel_title = ?,
                        published_at = ?, duration = ?, thumbnail_url = ?, view_count = ?,
                        like_count = ?, has_transcript = ?, transcript_language = ?,
                        updated_at = ?
                    WHERE video_id = ?
                """, (
                    video.title, video.description, video.channel_id, video.channel_title,
                    video.published_at, video.duration, video.thumbnail_url, video.view_count,
                    video.like_count, video.has_transcript, video.transcript_language,
                    datetime.now().isoformat(), video.video_id
                ))
            else:
                # Insert new video
                cursor.execute("""
                    INSERT INTO videos (
                        video_id, title, description, channel_id, channel_title,
                        published_at, duration, thumbnail_url, view_count, like_count,
                        has_transcript, transcript_language, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    video.video_id, video.title, video.description, video.channel_id,
                    video.channel_title, video.published_at, video.duration, video.thumbnail_url,
                    video.view_count, video.like_count, video.has_transcript, video.transcript_language,
                    datetime.now().isoformat(), datetime.now().isoformat()
                ))
            
            conn.commit()
            return True
            
    except Exception as e:
        logger.error(f"Error inserting/updating video {video.video_id}: {e}")
        return False

def get_videos_by_query(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Search videos by text query in title and description with SQL injection protection"""
    try:
        with get_db_connection() as conn:
            return search_videos_safe(conn, query, limit)
    except Exception as e:
        logger.error(f"Error searching videos: {e}")
        return []

def get_all_videos() -> List[Dict[str, Any]]:
    """Get all videos from database"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM videos ORDER BY published_at DESC")
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Error getting all videos: {e}")
        return []

def update_video_transcript_status(video_id: str, has_transcript: bool, language: str = None):
    """Update transcript status for a video"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE videos SET 
                    has_transcript = ?, 
                    transcript_language = ?,
                    updated_at = ?
                WHERE video_id = ?
            """, (has_transcript, language, datetime.now().isoformat(), video_id))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error updating transcript status for {video_id}: {e}")
        return False
