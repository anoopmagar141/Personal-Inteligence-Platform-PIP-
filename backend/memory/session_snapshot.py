import json
import logging
from typing import TypedDict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class SessionSnapshot(TypedDict):
    last_topic: str
    open_problems: List[str]
    suggested_next_step: str
    last_session_timestamp: str

def load_snapshot(filepath: str) -> Optional[SessionSnapshot]:
    """
    Loads the session snapshot from JSON.
    Failure mode: Fail-open. If the file is missing, malformed, or corrupted,
    it returns None. This is identical to Stage 0's fail-open rationale: missing a
    session snapshot only degrades conversational continuity, it does not violate a
    privacy or integrity guarantee. Returning None causes downstream stages to treat
    it as a first-ever run.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # Basic schema validation
        required_keys = ("last_topic", "open_problems", "suggested_next_step", "last_session_timestamp")
        if not all(key in data for key in required_keys):
            logger.warning("session_snapshot.json is missing required keys. Failing open to None.")
            return None
            
        return data # type: ignore
        
    except FileNotFoundError:
        logger.info("session_snapshot.json not found. Treating as first run (fail open).")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"session_snapshot.json is corrupted: {e}. Failing open to None.")
        return None
    except Exception as e:
        logger.error(f"Unexpected error loading session_snapshot.json: {e}. Failing open to None.")
        return None

def write_snapshot(filepath: str, snapshot: SessionSnapshot) -> None:
    """
    Writes a new session snapshot to JSON.
    This will be called by the Observer (Stage 11) at the end of a session.
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, indent=2)
