import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)

class GapDetectorResult(TypedDict):
    warm_start_level: str
    context_depth_modifier: int

def run(last_session_timestamp: Optional[datetime], now: Optional[datetime] = None) -> GapDetectorResult:
    """
    Calculates the gap since the last session to determine how much context to load.
    
    `now` is an optional injectable parameter to ensure deterministic testing across boundaries.
    Without it, tests would be subject to clock jitter and timing race conditions.
    
    Gap table:
      < 1 hour -> none, 0
      1 to < 24 hours -> brief, 1
      24h to 7 days -> summary, 2 (continuous at 24h, inclusive of exactly 7 days)
      > 7 days -> full, 3
      
    Failure mode: fail-open (returns none/0 on any error, logs it, never raises/blocks)
    """
    default_result: GapDetectorResult = {"warm_start_level": "none", "context_depth_modifier": 0}
    
    # First-ever run (no prior session)
    if last_session_timestamp is None:
        return default_result

    try:
        if now is None:
            now = datetime.now(timezone.utc)
            
        gap = now - last_session_timestamp
        
        # If timestamp is in the future, fail safe to 0
        if gap < timedelta(seconds=0):
            logger.warning("last_session_timestamp is in the future. Defaulting to none/0.")
            return default_result

        # Exact boundaries mapping (resolved for continuity):
        # < 1 hour: none
        # >= 1 hour AND < 24 hours: brief
        # >= 24 hours AND <= 7 days: summary (continuous at 24h, inclusive of exactly 7 days)
        # > 7 days: full
        if gap < timedelta(hours=1):
            return {"warm_start_level": "none", "context_depth_modifier": 0}
        elif gap < timedelta(hours=24):
            return {"warm_start_level": "brief", "context_depth_modifier": 1}
        elif gap <= timedelta(days=7):
            return {"warm_start_level": "summary", "context_depth_modifier": 2}
        else:
            return {"warm_start_level": "full", "context_depth_modifier": 3}
            
    except Exception as e:
        logger.error(f"Error in gap detector: {e}")
        return default_result
