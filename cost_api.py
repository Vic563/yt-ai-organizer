from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
import logging

from cost_tracking_service import CostTrackingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cost", tags=["cost"])

# Initialize cost tracking service
cost_tracker = CostTrackingService()

@router.get("/usage/overall")
async def get_overall_usage() -> Dict[str, Any]:
    """
    Retrieves overall API usage statistics.
    
    Returns:
        A dictionary containing a success flag and the overall usage statistics data.
        
    Raises:
        HTTPException: If retrieval of usage statistics fails.
    """
    try:
        stats = cost_tracker.get_usage_stats()
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        logger.error(f"Error getting overall usage: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve usage statistics")

@router.get("/usage/by-type")
async def get_usage_by_type() -> Dict[str, Any]:
    """
    Retrieves API usage statistics grouped by query type.
    
    Returns:
        A dictionary containing a success flag and usage statistics grouped by query type.
    """
    try:
        stats = cost_tracker.get_usage_by_type()
        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        logger.error(f"Error getting usage by type: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve usage by type")

@router.get("/usage/daily")
async def get_daily_usage(days: Optional[int] = 7) -> Dict[str, Any]:
    """
    Retrieves daily API usage statistics for the specified number of days.
    
    Args:
        days: The number of days to include in the statistics (between 1 and 365, default is 7).
    
    Returns:
        A dictionary containing a success flag and the usage statistics data.
    
    Raises:
        HTTPException: If the days parameter is out of range or if an unexpected error occurs.
    """
    try:
        if days < 1 or days > 365:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 365")
        
        stats = cost_tracker.get_daily_usage(days)
        return {
            "success": True,
            "data": stats
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting daily usage: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve daily usage")

@router.get("/limits/check")
async def check_usage_limits() -> Dict[str, Any]:
    """
    Checks if current API usage is approaching or exceeding predefined daily and monthly limits.
    
    Returns:
        A dictionary containing whether usage is within limits, any warning messages, current usage values, and the configured limits.
    """
    try:
        # Get current usage stats
        overall_stats = cost_tracker.get_usage_stats()
        daily_stats = cost_tracker.get_daily_usage(1)
        
        # Define some reasonable limits (these could be configurable)
        daily_cost_limit = 5.00  # $5 per day
        monthly_cost_limit = 100.00  # $100 per month
        daily_token_limit = 1000000  # 1M tokens per day
        
        # Calculate current usage
        today_cost = daily_stats[0]['total_cost'] if daily_stats else 0
        today_tokens = daily_stats[0]['total_tokens'] if daily_stats else 0
        total_cost = overall_stats['total_cost']
        
        # Check limits
        warnings = []
        if today_cost > daily_cost_limit * 0.8:  # 80% of daily limit
            warnings.append(f"Daily cost approaching limit: ${today_cost:.4f} / ${daily_cost_limit}")
        
        if today_tokens > daily_token_limit * 0.8:  # 80% of daily token limit
            warnings.append(f"Daily tokens approaching limit: {today_tokens:,} / {daily_token_limit:,}")
        
        if total_cost > monthly_cost_limit * 0.8:  # 80% of monthly limit
            warnings.append(f"Total cost approaching monthly limit: ${total_cost:.4f} / ${monthly_cost_limit}")
        
        return {
            "success": True,
            "data": {
                "within_limits": len(warnings) == 0,
                "warnings": warnings,
                "current_usage": {
                    "today_cost": today_cost,
                    "today_tokens": today_tokens,
                    "total_cost": total_cost
                },
                "limits": {
                    "daily_cost_limit": daily_cost_limit,
                    "monthly_cost_limit": monthly_cost_limit,
                    "daily_token_limit": daily_token_limit
                }
            }
        }
    except Exception as e:
        logger.error(f"Error checking usage limits: {e}")
        raise HTTPException(status_code=500, detail="Failed to check usage limits")

@router.get("/pricing/info")
async def get_pricing_info() -> Dict[str, Any]:
    """Get current Gemini API pricing information"""
    try:
        return {
            "success": True,
            "data": {
                "model": "gemini-1.5-flash",
                "pricing": {
                    "input_tokens": {
                        "price_per_1k": 0.000075,
                        "description": "Input tokens (prompts)"
                    },
                    "output_tokens": {
                        "price_per_1k": 0.0003,
                        "description": "Output tokens (responses)"
                    }
                },
                "note": "Prices are in USD and may change. Check Google AI pricing for latest rates."
            }
        }
    except Exception as e:
        logger.error(f"Error getting pricing info: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve pricing information")