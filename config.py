import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings"""
    
    # API Keys
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

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

def ensure_data_directories():
    """Ensure required data directories exist"""
    settings = get_settings()
    
    # Create data directory
    data_dir = os.path.dirname(settings.database_path)
    os.makedirs(data_dir, exist_ok=True)
    
    # Create transcripts directory
    os.makedirs(settings.transcripts_dir, exist_ok=True)
