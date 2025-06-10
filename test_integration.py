"""Integration tests for the upgraded application"""

import pytest
import asyncio
import sqlite3
import os
from datetime import datetime

# Test imports
from database import init_database, get_db_connection
from database_migrations import run_migrations
from auth import create_user, authenticate_user, UserCreate
from security import encrypt_value, decrypt_value, get_password_hash, verify_password
from database_search import search_videos_safe
from database_fts import FullTextSearch
from cache import CacheManager, VideoCache

class TestSecurity:
    """Test security features"""
    
    def test_password_hashing(self):
        """Test password hashing and verification"""
        password = "test_password_123"
        hashed = get_password_hash(password)
        
        assert hashed != password
        assert verify_password(password, hashed)
        assert not verify_password("wrong_password", hashed)
    
    def test_encryption(self):
        """Test value encryption and decryption"""
        secret = "my_api_key_12345"
        encrypted = encrypt_value(secret)
        
        assert encrypted != secret
        assert decrypt_value(encrypted) == secret

class TestAuthentication:
    """Test authentication system"""
    
    def setup_method(self):
        """Setup test database"""
        self.test_db = "test_auth.db"
        os.environ["DATABASE_PATH"] = self.test_db
        init_database()
        run_migrations()
    
    def teardown_method(self):
        """Cleanup test database"""
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
    
    def test_user_registration(self):
        """Test user registration"""
        user_data = UserCreate(
            username="testuser",
            email="test@example.com",
            password="password123"
        )
        
        user = create_user(user_data)
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.is_active
        assert not user.is_admin
    
    def test_user_authentication(self):
        """Test user authentication"""
        # Create user
        user_data = UserCreate(
            username="authtest",
            email="auth@example.com",
            password="secure_pass_123"
        )
        create_user(user_data)
        
        # Test authentication
        auth_result = authenticate_user("authtest", "secure_pass_123")
        assert auth_result is not None
        assert auth_result["username"] == "authtest"
        
        # Test with wrong password
        assert authenticate_user("authtest", "wrong_pass") is None

class TestDatabase:
    """Test database features"""
    
    def setup_method(self):
        """Setup test database"""
        self.test_db = "test_db.db"
        os.environ["DATABASE_PATH"] = self.test_db
        init_database()
        run_migrations()
        self._insert_test_data()
    
    def teardown_method(self):
        """Cleanup test database"""
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
    
    def _insert_test_data(self):
        """Insert test video data"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            videos = [
                ("video1", "Python Tutorial", "Learn Python basics", "channel1", "Python Channel", "2024-01-01"),
                ("video2", "JavaScript Guide", "JS for beginners", "channel2", "JS Channel", "2024-01-02"),
                ("video3", "Database Design", "SQL best practices", "channel3", "DB Channel", "2024-01-03"),
            ]
            
            for video in videos:
                cursor.execute("""
                    INSERT INTO videos (video_id, title, description, channel_id, channel_title, published_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, video)
            conn.commit()
    
    def test_safe_search(self):
        """Test SQL injection safe search"""
        with get_db_connection() as conn:
            # Normal search
            results = search_videos_safe(conn, "Python", limit=10)
            assert len(results) == 1
            assert results[0]["title"] == "Python Tutorial"
            
            # Test SQL injection attempt
            malicious_query = "'; DROP TABLE videos; --"
            results = search_videos_safe(conn, malicious_query, limit=10)
            # Should return empty results, not execute SQL
            assert isinstance(results, list)
            
            # Verify table still exists
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM videos")
            assert cursor.fetchone()[0] == 3
    
    def test_full_text_search(self):
        """Test FTS functionality"""
        with get_db_connection() as conn:
            fts = FullTextSearch(conn)
            
            # Search for Python
            results = fts.search("Python", limit=5)
            assert len(results) > 0
            assert results[0].title == "Python Tutorial"
            
            # Search for multiple terms
            results = fts.search("database SQL", limit=5)
            assert len(results) > 0

class TestCaching:
    """Test caching functionality"""
    
    def test_cache_manager(self):
        """Test cache manager operations"""
        cache = CacheManager(redis_url=None)  # Use in-memory cache
        
        # Test set and get
        cache.set("test_key", {"data": "value"}, expire=60)
        result = cache.get("test_key")
        assert result == {"data": "value"}
        
        # Test delete
        cache.delete("test_key")
        assert cache.get("test_key") is None
        
        # Test pattern clearing
        cache.set("prefix:key1", "value1")
        cache.set("prefix:key2", "value2")
        cache.set("other:key3", "value3")
        
        cleared = cache.clear_pattern("prefix:*")
        assert cleared == 2
        assert cache.get("other:key3") == "value3"
    
    def test_video_cache(self):
        """Test video-specific caching"""
        cache = VideoCache()
        
        # Test video metadata caching
        video_data = {
            "video_id": "test123",
            "title": "Test Video",
            "description": "Test description"
        }
        cache.set_video("test123", video_data)
        cached = cache.get_video("test123")
        assert cached == video_data
        
        # Test transcript caching
        transcript = "This is a test transcript"
        cache.set_transcript("test123", transcript)
        cached_transcript = cache.get_transcript("test123")
        assert cached_transcript == transcript

class TestAsyncTranscriptFetching:
    """Test async transcript fetching"""
    
    @pytest.mark.asyncio
    async def test_concurrent_fetcher(self):
        """Test concurrent transcript fetcher"""
        from transcript_fetcher_async import ConcurrentTranscriptFetcher
        
        fetcher = ConcurrentTranscriptFetcher()
        
        # Test with a known video ID (may fail if video doesn't exist)
        # Using a placeholder test
        result = await fetcher.fetch_transcript("dQw4w9WgXcQ", timeout=5.0)
        
        assert result.video_id == "dQw4w9WgXcQ"
        assert result.method in ["youtube-transcript-api", "simple-fetcher", "yt-dlp", "cache"]
        # May or may not succeed depending on network/availability

def run_tests():
    """Run all tests"""
    test_classes = [
        TestSecurity,
        TestAuthentication,
        TestDatabase,
        TestCaching,
        TestAsyncTranscriptFetching
    ]
    
    for test_class in test_classes:
        print(f"\nRunning {test_class.__name__}...")
        instance = test_class()
        
        # Run setup if exists
        if hasattr(instance, 'setup_method'):
            instance.setup_method()
        
        # Run all test methods
        for method_name in dir(instance):
            if method_name.startswith('test_'):
                print(f"  - {method_name}...", end="")
                try:
                    method = getattr(instance, method_name)
                    if asyncio.iscoroutinefunction(method):
                        asyncio.run(method())
                    else:
                        method()
                    print(" ✓")
                except Exception as e:
                    print(f" ✗ ({str(e)})")
        
        # Run teardown if exists
        if hasattr(instance, 'teardown_method'):
            instance.teardown_method()

if __name__ == "__main__":
    print("Running integration tests for YouTube AI Organizer upgrades...")
    run_tests()
    print("\nTests completed!")