"""Redis caching implementation with fallback to in-memory cache"""

import json
import logging
import time
from typing import Any, Optional, Union, Callable
from functools import wraps
from datetime import datetime, timedelta
import hashlib

try:
    import redis
    from redis.exceptions import RedisError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    
logger = logging.getLogger(__name__)

class InMemoryCache:
    """Simple in-memory cache as fallback when Redis is not available"""
    
    def __init__(self):
        self.cache = {}
        self.expiry = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if key in self.cache:
            if key in self.expiry and time.time() > self.expiry[key]:
                del self.cache[key]
                del self.expiry[key]
                return None
            return self.cache[key]
        return None
    
    def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set value in cache with optional expiration (seconds)"""
        self.cache[key] = value
        if expire:
            self.expiry[key] = time.time() + expire
        return True
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if key in self.cache:
            del self.cache[key]
            if key in self.expiry:
                del self.expiry[key]
            return True
        return False
    
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        return self.get(key) is not None
    
    def clear(self) -> None:
        """Clear all cache"""
        self.cache.clear()
        self.expiry.clear()
    
    def ping(self) -> bool:
        """Check if cache is available"""
        return True

class CacheManager:
    """Cache manager with Redis and in-memory fallback"""
    
    def __init__(self, redis_url: Optional[str] = None, prefix: str = "ytai"):
        self.prefix = prefix
        self.redis_client = None
        self.in_memory = InMemoryCache()
        
        if REDIS_AVAILABLE and redis_url:
            try:
                self.redis_client = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                self.redis_client.ping()
                logger.info("Redis cache connected successfully")
            except (RedisError, Exception) as e:
                logger.warning(f"Failed to connect to Redis: {e}. Using in-memory cache.")
                self.redis_client = None
    
    def _make_key(self, key: str) -> str:
        """Create namespaced cache key"""
        return f"{self.prefix}:{key}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        full_key = self._make_key(key)
        
        if self.redis_client:
            try:
                value = self.redis_client.get(full_key)
                if value:
                    return json.loads(value)
            except (RedisError, json.JSONDecodeError) as e:
                logger.error(f"Redis get error: {e}")
        
        # Fallback to in-memory
        return self.in_memory.get(full_key)
    
    def set(
        self, 
        key: str, 
        value: Any, 
        expire: Optional[int] = None,
        expire_at: Optional[datetime] = None
    ) -> bool:
        """Set value in cache with optional expiration"""
        full_key = self._make_key(key)
        serialized = json.dumps(value)
        
        if expire_at:
            expire = int((expire_at - datetime.utcnow()).total_seconds())
        
        if self.redis_client:
            try:
                if expire:
                    return bool(self.redis_client.setex(full_key, expire, serialized))
                else:
                    return bool(self.redis_client.set(full_key, serialized))
            except RedisError as e:
                logger.error(f"Redis set error: {e}")
        
        # Fallback to in-memory
        return self.in_memory.set(full_key, value, expire)
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        full_key = self._make_key(key)
        
        if self.redis_client:
            try:
                return bool(self.redis_client.delete(full_key))
            except RedisError as e:
                logger.error(f"Redis delete error: {e}")
        
        return self.in_memory.delete(full_key)
    
    def exists(self, key: str) -> bool:
        """Check if key exists"""
        full_key = self._make_key(key)
        
        if self.redis_client:
            try:
                return bool(self.redis_client.exists(full_key))
            except RedisError as e:
                logger.error(f"Redis exists error: {e}")
        
        return self.in_memory.exists(full_key)
    
    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern"""
        full_pattern = self._make_key(pattern)
        count = 0
        
        if self.redis_client:
            try:
                keys = self.redis_client.keys(full_pattern)
                if keys:
                    count = self.redis_client.delete(*keys)
            except RedisError as e:
                logger.error(f"Redis clear pattern error: {e}")
        
        # For in-memory, we need to manually match patterns
        keys_to_delete = [k for k in self.in_memory.cache.keys() if k.startswith(self.prefix)]
        for key in keys_to_delete:
            if pattern == "*" or key.startswith(full_pattern.replace("*", "")):
                self.in_memory.delete(key)
                count += 1
        
        return count
    
    def is_redis_available(self) -> bool:
        """Check if Redis is available"""
        if self.redis_client:
            try:
                return self.redis_client.ping()
            except RedisError:
                return False
        return False

# Global cache instance
_cache: Optional[CacheManager] = None

def init_cache(redis_url: Optional[str] = "redis://localhost:6379/0") -> CacheManager:
    """Initialize global cache instance"""
    global _cache
    if _cache is None:
        _cache = CacheManager(redis_url)
    return _cache

def get_cache() -> CacheManager:
    """Get global cache instance"""
    if _cache is None:
        return init_cache()
    return _cache

# Cache decorators
def cache_result(
    key_prefix: str,
    expire: int = 3600,
    key_func: Optional[Callable] = None
):
    """
    Decorator to cache function results
    
    Args:
        key_prefix: Prefix for cache key
        expire: Expiration time in seconds
        key_func: Function to generate cache key from arguments
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = f"{key_prefix}:{key_func(*args, **kwargs)}"
            else:
                # Default key generation
                key_parts = [str(arg) for arg in args]
                key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
                key_hash = hashlib.md5("".join(key_parts).encode()).hexdigest()
                cache_key = f"{key_prefix}:{key_hash}"
            
            # Try to get from cache
            cache = get_cache()
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_value
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Store in cache
            cache.set(cache_key, result, expire)
            logger.debug(f"Cached result for {cache_key}")
            
            return result
        
        return wrapper
    return decorator

# Specific cache functions for the application
class VideoCache:
    """Cache operations for video data"""
    
    def __init__(self, cache: Optional[CacheManager] = None):
        self.cache = cache or get_cache()
    
    def get_video(self, video_id: str) -> Optional[dict]:
        """Get video metadata from cache"""
        return self.cache.get(f"video:{video_id}")
    
    def set_video(self, video_id: str, video_data: dict, expire: int = 3600) -> bool:
        """Cache video metadata"""
        return self.cache.set(f"video:{video_id}", video_data, expire)
    
    def get_transcript(self, video_id: str) -> Optional[str]:
        """Get video transcript from cache"""
        return self.cache.get(f"transcript:{video_id}")
    
    def set_transcript(self, video_id: str, transcript: str, expire: int = 86400) -> bool:
        """Cache video transcript (24 hours)"""
        return self.cache.set(f"transcript:{video_id}", transcript, expire)
    
    def get_search_results(self, query: str, limit: int) -> Optional[list]:
        """Get search results from cache"""
        key = f"search:{hashlib.md5(f'{query}:{limit}'.encode()).hexdigest()}"
        return self.cache.get(key)
    
    def set_search_results(self, query: str, limit: int, results: list, expire: int = 1800) -> bool:
        """Cache search results (30 minutes)"""
        key = f"search:{hashlib.md5(f'{query}:{limit}'.encode()).hexdigest()}"
        return self.cache.set(key, results, expire)
    
    def invalidate_video(self, video_id: str) -> None:
        """Invalidate all caches for a video"""
        self.cache.delete(f"video:{video_id}")
        self.cache.delete(f"transcript:{video_id}")
        # Also clear search results that might contain this video
        self.cache.clear_pattern("search:*")
    
    def invalidate_searches(self) -> int:
        """Invalidate all search caches"""
        return self.cache.clear_pattern("search:*")

class APICache:
    """Cache operations for API responses"""
    
    def __init__(self, cache: Optional[CacheManager] = None):
        self.cache = cache or get_cache()
    
    def get_youtube_api_response(self, endpoint: str, params: dict) -> Optional[dict]:
        """Get YouTube API response from cache"""
        key = f"ytapi:{endpoint}:{hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()}"
        return self.cache.get(key)
    
    def set_youtube_api_response(self, endpoint: str, params: dict, response: dict, expire: int = 3600) -> bool:
        """Cache YouTube API response"""
        key = f"ytapi:{endpoint}:{hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()}"
        return self.cache.set(key, response, expire)
    
    def get_gemini_response(self, prompt_hash: str) -> Optional[dict]:
        """Get Gemini API response from cache"""
        return self.cache.get(f"gemini:{prompt_hash}")
    
    def set_gemini_response(self, prompt_hash: str, response: dict, expire: int = 3600) -> bool:
        """Cache Gemini API response"""
        return self.cache.set(f"gemini:{prompt_hash}", response, expire)