import os
import sqlite3
from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """Application settings"""
    
    # API Keys - loaded from encrypted database or environment
    google_ai_api_key: Optional[str] = None
    youtube_api_key: Optional[str] = None
    google_cloud_project_id: Optional[str] = None
    
    # Database
    database_path: str = "data/project_insight.db"
    transcripts_dir: str = "data/transcripts"
    
    # AI Configuration
    gemini_model: str = "gemini-2.5-flash-preview-05-20"
    max_conversation_history: int = 10
    max_tokens_per_request: int = 30000
    
    # YouTube Configuration
    max_videos_per_sync: int = 1000
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    def __init__(self, **data):
        """Initialize settings with encrypted key loading"""
        super().__init__(**data)
        
        # Try to load API keys from encrypted storage if not in environment
        if not self.google_ai_api_key or not self.youtube_api_key:
            self._load_encrypted_keys()
    
    def _load_encrypted_keys(self):
        """Load API keys from encrypted database storage"""
        try:
            # Only load if database exists
            if not os.path.exists(self.database_path):
                return
                
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # Check if encrypted_keys table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='encrypted_keys'
            """)
            if not cursor.fetchone():
                conn.close()
                return
            
            # Import here to avoid circular dependency
            from security import decrypt_value
            
            # Load Google AI API Key
            if not self.google_ai_api_key:
                cursor.execute(
                    "SELECT encrypted_value FROM encrypted_keys WHERE key_name = ?",
                    ("GOOGLE_AI_API_KEY",)
                )
                result = cursor.fetchone()
                if result:
                    try:
                        self.google_ai_api_key = decrypt_value(result[0])
                        logger.info("Loaded Google AI API Key from encrypted storage")
                    except Exception as e:
                        logger.error(f"Failed to decrypt Google AI API Key: {e}")
            
            # Load YouTube API Key
            if not self.youtube_api_key:
                cursor.execute(
                    "SELECT encrypted_value FROM encrypted_keys WHERE key_name = ?",
                    ("YOUTUBE_API_KEY",)
                )
                result = cursor.fetchone()
                if result:
                    try:
                        self.youtube_api_key = decrypt_value(result[0])
                        logger.info("Loaded YouTube API Key from encrypted storage")
                    except Exception as e:
                        logger.error(f"Failed to decrypt YouTube API Key: {e}")
            
            # Load Google Cloud Project ID (not encrypted)
            if not self.google_cloud_project_id:
                cursor.execute(
                    "SELECT encrypted_value FROM encrypted_keys WHERE key_name = ?",
                    ("GOOGLE_CLOUD_PROJECT_ID",)
                )
                result = cursor.fetchone()
                if result:
                    self.google_cloud_project_id = result[0]
                    logger.info("Loaded Google Cloud Project ID from storage")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Error loading encrypted keys: {e}")

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

def clear_settings_cache():
    """Clear the settings cache to reload configuration"""
    get_settings.cache_clear()
    logger.info("Settings cache cleared - configuration will be reloaded on next access")

def ensure_data_directories():
    """Ensure required data directories exist"""
    settings = get_settings()
    
    # Create data directory
    data_dir = os.path.dirname(settings.database_path)
    os.makedirs(data_dir, exist_ok=True)
    
    # Create transcripts directory
    os.makedirs(settings.transcripts_dir, exist_ok=True)

# Ensure data directories are created when this module is imported
ensure_data_directories()