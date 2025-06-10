from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class ConversationMessage(BaseModel):
    """Single message in conversation history"""
    role: str  # 'user' or 'assistant'
    content: str

class ChatMessage(BaseModel):
    """Incoming chat message from frontend"""
    message: str
    conversation_history: List[ConversationMessage] = []

class VideoCitation(BaseModel):
    """Citation linking to specific video timestamp"""
    video_id: str
    video_title: str
    timestamp: Optional[str] = None  # Format: "12:45"
    url: str

class VideoRecommendation(BaseModel):
    """Video recommendation with metadata"""
    id: str
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[str] = None
    published_at: Optional[str] = None
    channel_title: Optional[str] = None
    description: Optional[str] = None
    relevance_reason: Optional[str] = None
    url: str

class ChatResponse(BaseModel):
    """AI response to chat message"""
    message: str
    type: str = "text"  # 'text', 'discovery', 'synthesis'
    videos: List[VideoRecommendation] = []
    citations: List[VideoCitation] = []
    conversation_id: Optional[str] = None
    token_usage: Optional[Dict[str, int]] = None

class ConfigUpdate(BaseModel):
    """Configuration update request"""
    googleAiApiKey: Optional[str] = None
    youtubeApiKey: Optional[str] = None
    googleCloudProjectId: Optional[str] = None

class LibraryStats(BaseModel):
    """Library statistics"""
    total_videos: int
    videos_with_transcripts: int
    last_sync: Optional[str] = None

class VideoMetadata(BaseModel):
    """Video metadata for database storage"""
    video_id: str
    title: str
    description: Optional[str] = None
    channel_id: str
    channel_title: str
    published_at: str
    duration: Optional[str] = None
    thumbnail_url: Optional[str] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    has_transcript: bool = False
    transcript_language: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class TranscriptSegment(BaseModel):
    """Individual transcript segment"""
    start_time: float
    duration: float
    text: str

class VideoTranscript(BaseModel):
    """Complete video transcript"""
    video_id: str
    language: str
    segments: List[TranscriptSegment]
    full_text: str

class TopicUpdate(BaseModel):
    """Topic update request for a video"""
    topic_name: str

class TopicRename(BaseModel):
    """Topic rename request"""
    old_name: str
    new_name: str
