import sqlite3
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from backend.core.types import MemoryCandidate, ValidationResult
from backend.core.constitution_enforcer import ConstitutionEnforcer

def _get_profile_age_weeks(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT first_session_date FROM profile_meta WHERE id = 1").fetchone()
    if not row or not row["first_session_date"]:
        return 0
    try:
        first_session = datetime.fromisoformat(row["first_session_date"].replace("Z", "+00:00"))
        if first_session.tzinfo is None:
            first_session = first_session.replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - first_session).days
        return max(0, days // 7)
    except Exception:
        return 0

def _fetch_existing_state(conn: sqlite3.Connection, candidate: MemoryCandidate) -> Optional[Dict[str, Any]]:
    target_table = candidate.get("target_table")
    field_name = candidate.get("field_name")
    
    if not target_table or not field_name:
        return None
        
    try:
        if target_table == "preference_memory":
            row = conn.execute(
                "SELECT id, value, source_label, confidence, behavioral_signal_count "
                "FROM preference_memory WHERE name = ?", 
                (field_name,)
            ).fetchone()
            
            if not row:
                return None
                
            c_row = conn.execute(
                "SELECT MIN(created_at) as created_at "
                "FROM preference_contradiction_log WHERE preference_id = ?", 
                (row["id"],)
            ).fetchone()
            
            return {
                "current_value": row["value"],
                "source_label": row["source_label"],
                "confidence": row["confidence"],
                "behavioral_signal_count": row["behavioral_signal_count"],
                "first_contradiction_date": c_row["created_at"] if c_row else None
            }
            
        elif target_table == "skill_memory":
            row = conn.execute(
                "SELECT id, level, source_label, confidence "
                "FROM skill_memory WHERE name = ?", 
                (field_name,)
            ).fetchone()
            
            if not row:
                return None
                
            c_row = conn.execute(
                "SELECT MIN(created_at) as created_at "
                "FROM skill_contradiction_log WHERE skill_id = ?", 
                (row["id"],)
            ).fetchone()
            
            return {
                "current_value": row["level"],
                "source_label": row["source_label"],
                "confidence": row["confidence"],
                "behavioral_signal_count": 0,
                "first_contradiction_date": c_row["created_at"] if c_row else None
            }
            
        elif target_table == "identity":
            row = conn.execute("SELECT * FROM identity WHERE id = 1").fetchone()
            if not row or field_name not in ["name", "language_preference", "timezone"]:
                return None
            return {
                "current_value": row[field_name],
                "source_label": "explicit",
                "confidence": 1.0,
                "behavioral_signal_count": 0,
                "first_contradiction_date": None
            }
            
        elif target_table == "interaction_style":
            row = conn.execute("SELECT value, source_label, confidence FROM interaction_style WHERE id = 1").fetchone()
            if not row:
                return None
            return {
                "current_value": row["value"],
                "source_label": row["source_label"],
                "confidence": row["confidence"],
                "behavioral_signal_count": 0,
                "first_contradiction_date": None
            }
            
        elif target_table == "goal_memory":
            row = conn.execute("SELECT goal_text, confidence FROM goal_memory WHERE id = ?", (field_name.replace("goal:", ""),)).fetchone()
            if not row:
                return None
            return {
                "current_value": row["goal_text"],
                "source_label": "explicit",
                "confidence": row["confidence"],
                "behavioral_signal_count": 0,
                "first_contradiction_date": None
            }
            
        elif target_table == "active_projects":
            row = conn.execute("SELECT description FROM active_projects WHERE name = ?", (field_name,)).fetchone()
            if not row:
                return None
            return {
                "current_value": row["description"],
                "source_label": "explicit",
                "confidence": 1.0,
                "behavioral_signal_count": 0,
                "first_contradiction_date": None
            }
            
        else:
            # target_table not recognized by any handler
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Unhandled target_table in _fetch_existing_state: '{target_table}'")
            return None
            
    except sqlite3.OperationalError as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Database error in _fetch_existing_state querying table '{target_table}': {e}")
        return None

def run(conn: sqlite3.Connection, candidate: MemoryCandidate, enforcer: ConstitutionEnforcer) -> ValidationResult:
    """
    Validates a memory candidate against the constitution.
    """
    profile_age_weeks = _get_profile_age_weeks(conn)
    existing_field = _fetch_existing_state(conn, candidate)
    
    return enforcer.validate(candidate, existing_field, profile_age_weeks)
