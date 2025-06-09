import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

from config import get_settings
from models import BaseModel

logger = logging.getLogger(__name__)

class TokenUsage(BaseModel):
    """Token usage data model"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    cost_usd: float
    timestamp: str
    conversation_id: Optional[str] = None
    query_type: Optional[str] = None  # 'discovery', 'synthesis', 'general'

class UsageStats(BaseModel):
    """Usage statistics model"""
    total_requests: int
    total_tokens: int
    total_cost_usd: float
    avg_tokens_per_request: float
    period_start: str
    period_end: str
    breakdown_by_type: Dict[str, Dict[str, Any]]

class CostTrackingService:
    """Service for tracking API costs and token usage"""
    
    # Gemini 1.5 Pro pricing (as of 2024)
    GEMINI_PRICING = {
        "gemini-1.5-pro": {
            "input_tokens_per_million": 3.50,  # $3.50 per 1M input tokens
            "output_tokens_per_million": 10.50  # $10.50 per 1M output tokens
        },
        "gemini-1.5-flash": {
            "input_tokens_per_million": 0.075,  # $0.075 per 1M input tokens
            "output_tokens_per_million": 0.30   # $0.30 per 1M output tokens
        }
    }
    
    def __init__(self):
        self.settings = get_settings()
        self._init_cost_tracking_table()
    
    def _init_cost_tracking_table(self):
        """Initialize the cost tracking table in database"""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS api_usage (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        conversation_id TEXT,
                        model TEXT NOT NULL,
                        prompt_tokens INTEGER NOT NULL,
                        completion_tokens INTEGER NOT NULL,
                        total_tokens INTEGER NOT NULL,
                        cost_usd REAL NOT NULL,
                        query_type TEXT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for better performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON api_usage(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_conversation ON api_usage(conversation_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_model ON api_usage(model)")
                
                conn.commit()
                logger.info("Cost tracking table initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing cost tracking table: {e}")
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
    
    def calculate_cost(self, prompt_tokens: int, completion_tokens: int, model: str) -> float:
        """Calculate cost in USD for given token usage"""
        if model not in self.GEMINI_PRICING:
            logger.warning(f"Unknown model {model}, using gemini-1.5-pro pricing")
            model = "gemini-1.5-pro"
        
        pricing = self.GEMINI_PRICING[model]
        
        input_cost = (prompt_tokens / 1_000_000) * pricing["input_tokens_per_million"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output_tokens_per_million"]
        
        return round(input_cost + output_cost, 6)  # Round to 6 decimal places
    
    def track_usage(
        self, 
        prompt_tokens: int, 
        completion_tokens: int, 
        model: str,
        conversation_id: Optional[str] = None,
        query_type: Optional[str] = None
    ) -> TokenUsage:
        """Track API usage and store in database"""
        total_tokens = prompt_tokens + completion_tokens
        cost_usd = self.calculate_cost(prompt_tokens, completion_tokens, model)
        timestamp = datetime.now().isoformat()
        
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            model=model,
            cost_usd=cost_usd,
            timestamp=timestamp,
            conversation_id=conversation_id,
            query_type=query_type
        )
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO api_usage (
                        timestamp, conversation_id, model, prompt_tokens, 
                        completion_tokens, total_tokens, cost_usd, query_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp, conversation_id, model, prompt_tokens,
                    completion_tokens, total_tokens, cost_usd, query_type
                ))
                
                conn.commit()
                logger.info(f"Tracked usage: {total_tokens} tokens, ${cost_usd:.6f}")
                
        except Exception as e:
            logger.error(f"Error tracking usage: {e}")
            # Don't raise exception to avoid breaking the main flow
        
        return usage
    
    def get_usage_stats(self, days: int = 30) -> UsageStats:
        """Get usage statistics for the last N days"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get overall stats
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_requests,
                        SUM(total_tokens) as total_tokens,
                        SUM(cost_usd) as total_cost,
                        AVG(total_tokens) as avg_tokens
                    FROM api_usage 
                    WHERE timestamp >= ?
                """, (start_date.isoformat(),))
                
                row = cursor.fetchone()
                
                total_requests = row['total_requests'] or 0
                total_tokens = row['total_tokens'] or 0
                total_cost = row['total_cost'] or 0.0
                avg_tokens = row['avg_tokens'] or 0.0
                
                # Get breakdown by query type
                cursor.execute("""
                    SELECT 
                        query_type,
                        COUNT(*) as requests,
                        SUM(total_tokens) as tokens,
                        SUM(cost_usd) as cost
                    FROM api_usage 
                    WHERE timestamp >= ?
                    GROUP BY query_type
                """, (start_date.isoformat(),))
                
                breakdown = {}
                for row in cursor.fetchall():
                    query_type = row['query_type'] or 'unknown'
                    breakdown[query_type] = {
                        'requests': row['requests'],
                        'tokens': row['tokens'],
                        'cost': row['cost']
                    }
                
                return UsageStats(
                    total_requests=total_requests,
                    total_tokens=total_tokens,
                    total_cost_usd=round(total_cost, 6),
                    avg_tokens_per_request=round(avg_tokens, 2),
                    period_start=start_date.isoformat(),
                    period_end=end_date.isoformat(),
                    breakdown_by_type=breakdown
                )
                
        except Exception as e:
            logger.error(f"Error getting usage stats: {e}")
            # Return empty stats on error
            return UsageStats(
                total_requests=0,
                total_tokens=0,
                total_cost_usd=0.0,
                avg_tokens_per_request=0.0,
                period_start=start_date.isoformat(),
                period_end=end_date.isoformat(),
                breakdown_by_type={}
            )
    
    def get_daily_usage(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get daily usage breakdown for the last N days"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT 
                        DATE(timestamp) as date,
                        COUNT(*) as requests,
                        SUM(total_tokens) as tokens,
                        SUM(cost_usd) as cost
                    FROM api_usage 
                    WHERE timestamp >= ?
                    GROUP BY DATE(timestamp)
                    ORDER BY date DESC
                """, (start_date.isoformat(),))
                
                daily_stats = []
                for row in cursor.fetchall():
                    daily_stats.append({
                        'date': row['date'],
                        'requests': row['requests'],
                        'tokens': row['tokens'],
                        'cost': round(row['cost'], 6)
                    })
                
                return daily_stats
                
        except Exception as e:
            logger.error(f"Error getting daily usage: {e}")
            return []
    
    def check_usage_limits(self, daily_limit_usd: float = 5.0, monthly_limit_usd: float = 50.0) -> Dict[str, Any]:
        """Check if usage is approaching limits"""
        today_stats = self.get_usage_stats(days=1)
        monthly_stats = self.get_usage_stats(days=30)
        
        daily_usage_pct = (today_stats.total_cost_usd / daily_limit_usd) * 100 if daily_limit_usd > 0 else 0
        monthly_usage_pct = (monthly_stats.total_cost_usd / monthly_limit_usd) * 100 if monthly_limit_usd > 0 else 0
        
        warnings = []
        if daily_usage_pct > 80:
            warnings.append(f"Daily usage at {daily_usage_pct:.1f}% of limit")
        if monthly_usage_pct > 80:
            warnings.append(f"Monthly usage at {monthly_usage_pct:.1f}% of limit")
        
        return {
            'daily_usage_usd': today_stats.total_cost_usd,
            'daily_limit_usd': daily_limit_usd,
            'daily_usage_percentage': round(daily_usage_pct, 1),
            'monthly_usage_usd': monthly_stats.total_cost_usd,
            'monthly_limit_usd': monthly_limit_usd,
            'monthly_usage_percentage': round(monthly_usage_pct, 1),
            'warnings': warnings,
            'is_over_daily_limit': today_stats.total_cost_usd > daily_limit_usd,
            'is_over_monthly_limit': monthly_stats.total_cost_usd > monthly_limit_usd
        }