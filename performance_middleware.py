import time
from fastapi import Request, Response
from typing import Callable, Awaitable, Optional
import logging
from datetime import datetime
from contextlib import contextmanager
import sqlite3
from config import get_settings

logger = logging.getLogger(__name__)

class PerformanceTracker:
    """Service for tracking API performance metrics"""
    
    def __init__(self):
        self.settings = get_settings()
        self._init_performance_table()
    
    def _init_performance_table(self):
        """Initialize the performance metrics table"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS performance_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        method TEXT NOT NULL,
                        path TEXT NOT NULL,
                        status_code INTEGER NOT NULL,
                        response_time_ms REAL NOT NULL,
                        user_agent TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_perf_timestamp 
                    ON performance_metrics(timestamp)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_perf_path 
                    ON performance_metrics(path)
                """)
                
                conn.commit()
                logger.info("Performance metrics table initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing performance metrics table: {e}")
            raise
    
    @contextmanager
    def _get_db_connection(self):
        """Get database connection with automatic cleanup"""
        conn = sqlite3.connect(self.settings.database_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    async def track_request(self, request: Request, call_next: Callable) -> Response:
        """Track request performance and log metrics"""
        start_time = time.time()
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Calculate response time
            process_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Log the metrics, excluding performance API calls
            if not request.url.path.startswith('/api/performance/'):
                await self._log_metrics(
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    response_time_ms=process_time,
                    user_agent=request.headers.get('user-agent')
                )
            
            # Add Server-Timing header for browser dev tools
            response.headers["Server-Timing"] = f"total;dur={process_time:.2f}"
            
            return response
            
        except Exception as e:
            logger.error(f"Error in performance tracking: {e}")
            raise
    
    async def _log_metrics(self, method: str, path: str, status_code: int, 
                          response_time_ms: float, user_agent: Optional[str] = None):
        """Log performance metrics to the database"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO performance_metrics 
                    (timestamp, method, path, status_code, response_time_ms, user_agent)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        datetime.utcnow().isoformat(),
                        method,
                        path,
                        status_code,
                        response_time_ms,
                        user_agent
                    )
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error logging performance metrics: {e}")
            # Don't fail the request if metrics logging fails

# Initialize global instance
performance_tracker = PerformanceTracker()

async def performance_middleware(request: Request, call_next: Callable) -> Response:
    """Middleware to track API performance"""
    # Skip performance tracking for certain paths (e.g., health checks)
    if request.url.path in ['/health', '/favicon.ico']:
        return await call_next(request)
        
    return await performance_tracker.track_request(request, call_next)
