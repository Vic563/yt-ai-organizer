from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import sqlite3
from pydantic import BaseModel

from performance_middleware import performance_tracker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/performance", tags=["performance"])

class PerformanceStats(BaseModel):
    avg_response_time: float
    request_count: int
    error_rate: float
    p50: float
    p90: float
    p99: float

@router.get("/metrics", response_model=Dict[str, Any])
async def get_performance_metrics(
    hours: int = 24,
    endpoint: Optional[str] = None,
    method: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get performance metrics for the specified time period
    
    Args:
        hours: Number of hours to look back (default: 24)
        endpoint: Filter by endpoint path (optional)
        method: Filter by HTTP method (e.g., GET, POST) (optional)
    """
    try:
        if hours < 1 or hours > 720:  # Limit to 30 days
            raise HTTPException(status_code=400, detail="Hours must be between 1 and 720")
            
        with performance_tracker._get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Calculate time range
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)
            
            # Build query
            query = """
                SELECT 
                    path,
                    method,
                    COUNT(*) as request_count,
                    AVG(response_time_ms) as avg_response_time,
                    MAX(response_time_ms) as max_response_time,
                    MIN(response_time_ms) as min_response_time,
                    SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as error_count
                FROM performance_metrics
                WHERE timestamp >= ?
            """
            
            params = [start_time.isoformat()]
            
            if endpoint:
                query += " AND path = ?"
                params.append(endpoint)
                
            if method:
                query += " AND method = ?"
                params.append(method.upper())
                
            query += """
                GROUP BY path, method
                ORDER BY avg_response_time DESC
            """
            
            cursor.execute(query, params)
            results = [dict(row) for row in cursor.fetchall()]
            
            # Get all response times for percentile calculation
            cursor.execute("""
                SELECT response_time_ms
                FROM performance_metrics
                WHERE timestamp >= ?
                ORDER BY response_time_ms
            """, [start_time.isoformat()])
            
            # Calculate percentiles manually
            response_times = [row[0] for row in cursor.fetchall()]
            percentiles = {"p50": 0, "p90": 0, "p99": 0}
            
            if response_times:
                response_times.sort()
                n = len(response_times)
                percentiles["p50"] = response_times[int(n * 0.5)] if n > 0 else 0
                percentiles["p90"] = response_times[int(n * 0.9)] if n > 0 else 0
                percentiles["p99"] = response_times[int(n * 0.99)] if n > 0 else 0
            
            # Calculate overall stats
            total_requests = sum(r['request_count'] for r in results)
            total_errors = sum(r.get('error_count', 0) for r in results)
            error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat()
                },
                "total_requests": total_requests,
                "error_rate": round(error_rate, 2),
                "response_time_percentiles": {
                    "p50": round(percentiles["p50"], 2),
                    "p90": round(percentiles["p90"], 2),
                    "p99": round(percentiles["p99"], 2)
                },
                "endpoints": results
            }
            
    except Exception as e:
        logger.error(f"Error retrieving performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve performance metrics")

@router.get("/slow-endpoints", response_model=List[Dict[str, Any]])
async def get_slow_endpoints(
    threshold_ms: int = 1000,
    hours: int = 24
) -> List[Dict[str, Any]]:
    """
    Get endpoints with average response time above the threshold
    
    Args:
        threshold_ms: Response time threshold in milliseconds (default: 1000ms)
        hours: Number of hours to look back (default: 24)
    """
    try:
        if hours < 1 or hours > 720:  # Limit to 30 days
            raise HTTPException(status_code=400, detail="Hours must be between 1 and 720")
            
        with performance_tracker._get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Calculate time range
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)
            
            cursor.execute("""
                SELECT 
                    path,
                    method,
                    COUNT(*) as request_count,
                    AVG(response_time_ms) as avg_response_time,
                    MAX(response_time_ms) as max_response_time,
                    MIN(response_time_ms) as min_response_time
                FROM performance_metrics
                WHERE timestamp >= ?
                GROUP BY path, method
                HAVING AVG(response_time_ms) > ?
                ORDER BY avg_response_time DESC
            """, [start_time.isoformat(), threshold_ms])
            
            return [dict(row) for row in cursor.fetchall()]
            
    except Exception as e:
        logger.error(f"Error retrieving slow endpoints: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve slow endpoints")

@router.delete("/reset-metrics", status_code=200)
async def reset_performance_metrics():
    """
    Reset all performance metrics by clearing the performance_metrics table.
    """
    try:
        with performance_tracker._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM performance_metrics")
            conn.commit()
            logger.info("Performance metrics table has been reset.")
            return {"message": "Performance metrics reset successfully"}
    except Exception as e:
        logger.error(f"Error resetting performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset performance metrics")
