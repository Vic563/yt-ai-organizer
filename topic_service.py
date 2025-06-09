"""Topic extraction and management service"""
import logging
from typing import Optional, Tuple, List, Dict, Any
import google.generativeai as genai
import os
from pathlib import Path
import re

logger = logging.getLogger(__name__)

class TopicExtractor:
    """Handles topic extraction using Gemini AI"""
    
    def __init__(self, api_key: str):
        """Initialize the topic extractor with Gemini API key"""
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
    
    async def extract_topic(self, title: str, content: str) -> Tuple[Optional[str], float]:
        """
        Extract a single main topic from video content
        
        Args:
            title: Video title
            content: Video transcript or description text
            
        Returns:
            Tuple of (topic_name, confidence) or (None, 0.0) if extraction fails
        """
        try:
            # Truncate content to avoid hitting token limits
            max_content_length = 8000  # Leave room for prompt and title
            truncated_content = content[:max_content_length] if content else ""
            
            # Determine if we have transcript or just title/description
            has_transcript = len(content) > 200 and not content.startswith(title)
            content_type = "transcript" if has_transcript else "title and description"
            
            prompt = f"""Analyze the following YouTube video content and identify the SINGLE most relevant, specific topic 
            that best represents the main subject of the video. The topic should be concise (1-3 words), 
            specific, and in title case (e.g., "Machine Learning", "Python Tutorials", "Cooking Italian Food").
            
            Video Title: "{title}"
            
            Video {content_type}:
            {truncated_content}
            
            Return ONLY the topic name in title case, nothing else. Example: "Python Programming"
            """
            
            response = await self.model.generate_content_async(prompt)
            topic = response.text.strip()
            
            # Basic validation and cleanup
            topic = self._clean_topic(topic)
            if not topic:
                return None, 0.0
                
            # Adjust confidence based on available content
            confidence = 0.9 if has_transcript else 0.7
            return topic, confidence
            
        except Exception as e:
            logger.error(f"Error extracting topic: {e}")
            return None, 0.0
    
    def _clean_topic(self, topic: str) -> Optional[str]:
        """Clean and validate the extracted topic"""
        if not topic or len(topic) > 50:  # Sanity check on length
            return None
            
        # Remove any quotes, extra whitespace, and ensure title case
        topic = topic.strip('"\'').strip()
        topic = ' '.join(word.capitalize() for word in topic.split())
        
        # Remove any non-alphanumeric characters except spaces and hyphens
        topic = re.sub(r'[^\w\s-]', '', topic)
        
        return topic if topic else None


class TopicManager:
    """Manages topic-related database operations"""
    
    def __init__(self, db_connection):
        self.conn = db_connection
    
    def get_or_create_topic(self, topic_name: str) -> Optional[int]:
        """Get existing topic ID or create a new one"""
        cursor = self.conn.cursor()
        
        # Try to find existing topic
        cursor.execute("SELECT id FROM topics WHERE name = ?", (topic_name,))
        result = cursor.fetchone()
        
        if result:
            return result[0]
            
        # Create new topic
        try:
            cursor.execute(
                "INSERT INTO topics (name) VALUES (?)",
                (topic_name,)
            )
            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error creating topic '{topic_name}': {e}")
            self.conn.rollback()
            return None
    
    def update_video_topic(
        self, 
        video_id: str, 
        topic_name: str, 
        confidence: float = 1.0,
        auto_generated: bool = True
    ) -> bool:
        """
        Update or set the topic for a video
        
        Args:
            video_id: YouTube video ID
            topic_name: Name of the topic
            confidence: Confidence score (0.0 to 1.0)
            auto_generated: Whether the topic was auto-generated
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not topic_name:
            return False
            
        try:
            cursor = self.conn.cursor()
            
            # Get or create topic
            topic_id = self.get_or_create_topic(topic_name)
            if not topic_id:
                return False
            
            # Update video with topic
            cursor.execute(
                """
                UPDATE videos 
                SET topic_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE video_id = ?
                """,
                (topic_id, video_id)
            )
            
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error updating video topic: {e}")
            self.conn.rollback()
            return False
    
    def get_videos_by_topic(self, topic_id: int) -> List[Dict[str, Any]]:
        """Get all videos for a specific topic"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT v.*, t.name as topic_name
                FROM videos v
                JOIN topics t ON v.topic_id = t.id
                WHERE t.id = ?
                ORDER BY v.published_at DESC
                """,
                (topic_id,)
            )
            
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Error getting videos by topic: {e}")
            return []
    
    def get_all_topics(self) -> List[Dict[str, Any]]:
        """Get all topics with video counts"""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT t.id, t.name, COUNT(v.video_id) as video_count
                FROM topics t
                LEFT JOIN videos v ON t.id = v.topic_id
                GROUP BY t.id, t.name
                ORDER BY t.name
                """
            )
            
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Error getting all topics: {e}")
            return []
    
    def rename_topic(self, old_name: str, new_name: str) -> bool:
        """
        Rename a topic
        
        Args:
            old_name: Current topic name
            new_name: New topic name
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not old_name or not new_name:
            return False
            
        try:
            cursor = self.conn.cursor()
            
            # Check if old topic exists
            cursor.execute("SELECT id FROM topics WHERE name = ?", (old_name,))
            old_topic = cursor.fetchone()
            
            if not old_topic:
                logger.error(f"Topic '{old_name}' not found")
                return False
            
            # Check if new topic name already exists
            cursor.execute("SELECT id FROM topics WHERE name = ?", (new_name,))
            existing_topic = cursor.fetchone()
            
            if existing_topic:
                logger.error(f"Topic '{new_name}' already exists")
                return False
            
            # Update the topic name
            cursor.execute(
                "UPDATE topics SET name = ? WHERE name = ?",
                (new_name, old_name)
            )
            
            self.conn.commit()
            logger.info(f"Successfully renamed topic from '{old_name}' to '{new_name}'")
            return True
            
        except Exception as e:
            logger.error(f"Error renaming topic: {e}")
            self.conn.rollback()
            return False
