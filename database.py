import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional, Dict, Any

from config import get_settings, ensure_data_directories
from models import VideoMetadata

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
    """Search videos by text query in title and description with improved relevance"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Split query into individual words for better matching
            # Filter out very short words and common stop words that cause false matches
            stop_words = {'i', 'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'to', 'of', 'in', 'on', 'at', 'by', 'for', 'with', 'as', 'and', 'or', 'but', 'if', 'any', 'some', 'all', 'no', 'not', 'my', 'your', 'his', 'her', 'its', 'our', 'their'}
            query_words = [
                word.strip().lower().rstrip('?.,!;:')
                for word in query.split()
                if word.strip() and len(word.strip()) > 2 and word.strip().lower().rstrip('?.,!;:') not in stop_words
            ]

            if not query_words:
                # If all words were filtered out, try the original query as a phrase
                query_words = [query.lower().strip()]

            # Build a more sophisticated search query
            # First, try exact phrase match
            exact_phrase = f"%{query.lower()}%"
            cursor.execute("""
                SELECT *,
                       CASE
                           WHEN LOWER(title) LIKE ? THEN 3
                           WHEN LOWER(description) LIKE ? THEN 2
                           ELSE 1
                       END as relevance_score
                FROM videos
                WHERE LOWER(title) LIKE ? OR LOWER(description) LIKE ?
                ORDER BY relevance_score DESC, published_at DESC
                LIMIT ?
            """, (exact_phrase, exact_phrase, exact_phrase, exact_phrase, limit))

            exact_results = [dict(row) for row in cursor.fetchall()]

            # If we have exact matches, return them
            if exact_results:
                return exact_results

            # If no exact matches, try individual word matching
            word_conditions = []
            word_params = []

            for word in query_words:
                word_pattern = f"%{word}%"
                word_conditions.append("(LOWER(title) LIKE ? OR LOWER(description) LIKE ?)")
                word_params.extend([word_pattern, word_pattern])

            if word_conditions:
                word_query = f"""
                    SELECT *,
                           ({' + '.join(['(CASE WHEN LOWER(title) LIKE ? OR LOWER(description) LIKE ? THEN 1 ELSE 0 END)' for _ in query_words])}) as word_matches
                    FROM videos
                    WHERE {' OR '.join(word_conditions)}
                    ORDER BY word_matches DESC, published_at DESC
                    LIMIT ?
                """

                # Duplicate params for the CASE statements in SELECT
                all_params = []
                for word in query_words:
                    word_pattern = f"%{word}%"
                    all_params.extend([word_pattern, word_pattern])
                all_params.extend(word_params)
                all_params.append(limit)

                cursor.execute(word_query, all_params)
                word_results = [dict(row) for row in cursor.fetchall()]

                # Filter out results with very low relevance (less than 1 word match)
                filtered_results = [video for video in word_results if video.get('word_matches', 0) > 0]
                return filtered_results

            return []

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
