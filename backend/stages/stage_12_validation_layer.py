from typing import Optional, Dict, Any
from datetime import datetime, timezone
from backend.core.types import MemoryCandidate, ValidationResult
from backend.core.constitution_enforcer import ConstitutionEnforcer

def _get_profile_age_weeks(conn) -> int:
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

def _fetch_existing_state(conn, candidate: MemoryCandidate) -> Optional[Dict[str, Any]]:
    target_table = candidate.get("target_table")
    field_name = candidate.get("field_name")
    
    if not target_table or not field_name:
        return None
        
    try:
        if target_table == "preference_memory":
            row = conn.execute(
                "SELECT id, value, source_label, confidence, evidence_count "
                "FROM preference_memory WHERE name = ?",
                (field_name,)
            ).fetchone()

            if not row:
                return None

            # Security review finding: preference_memory.behavioral_signal_count
            # was never incremented anywhere in this codebase (only defaulted to
            # 0 and reset to 0 on resolution), so the enforcer's override trigger
            # could never see a real count. preference_contradiction_log is the
            # actual source of truth now (Stage 13 appends to it on the DISCARD
            # path via profile_store.log_preference_contradiction) - derived here
            # via COUNT()/MIN() instead of trusting the stale column, so there's
            # one source of truth instead of two that can drift apart.
            c_row = conn.execute(
                "SELECT COUNT(*) as contradiction_count, MIN(created_at) as first_created_at "
                "FROM preference_contradiction_log WHERE preference_id = ?",
                (row["id"],)
            ).fetchone()

            return {
                "current_value": row["value"],
                "source_label": row["source_label"],
                "confidence": row["confidence"],
                "evidence_count": row["evidence_count"],
                "behavioral_signal_count": c_row["contradiction_count"] if c_row else 0,
                "first_contradiction_date": c_row["first_created_at"] if c_row else None
            }

        elif target_table == "skill_memory":
            row = conn.execute(
                "SELECT id, level, source_label, confidence, evidence_count "
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
                "evidence_count": row["evidence_count"],
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
                "evidence_count": None,  # no evidence_count column - immutable, never reinforced
                "behavioral_signal_count": 0,
                "first_contradiction_date": None
            }

        elif target_table == "interaction_style":
            row = conn.execute("SELECT value, source_label, confidence, evidence_count FROM interaction_style WHERE id = 1").fetchone()
            if not row:
                return None
            return {
                "current_value": row["value"],
                "source_label": row["source_label"],
                "confidence": row["confidence"],
                "evidence_count": row["evidence_count"],
                "behavioral_signal_count": 0,
                "first_contradiction_date": None
            }

        elif target_table == "goal_memory":
            row = conn.execute("SELECT goal_text, confidence, evidence_count FROM goal_memory WHERE id = ?", (field_name.replace("goal:", ""),)).fetchone()
            if not row:
                return None
            return {
                "current_value": row["goal_text"],
                "source_label": "explicit",
                "confidence": row["confidence"],
                "evidence_count": row["evidence_count"],
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
                "evidence_count": None,  # no evidence_count column - not a confidence-scored field
                "behavioral_signal_count": 0,
                "first_contradiction_date": None
            }
            
        else:
            # target_table not recognized by any handler
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Unhandled target_table in _fetch_existing_state: '{target_table}'")
            return None
            
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Database error in _fetch_existing_state querying table '{target_table}': {e}")
        return None

def reinforce_evidence(conn, candidate: MemoryCandidate) -> MemoryCandidate:
    """
    Part 8.6's REINFORCEMENT step: if the existing stored value for this field
    matches the candidate's proposed_value, this is a repeat observation of the
    same signal, not a fresh one - bump evidence_count to existing + 1 rather than
    leaving it at whatever the caller (e.g. a single Observer pass, which can only
    ever attest evidence_count=1 - one transcript is one observation) provided.

    Deliberately does NOT reinforce when the proposed_value differs from the
    existing value: that's a conflicting observation, not a repeat one, and is
    already handled by the existing behavioral-override/TIER_2_REQUIRED paths in
    ConstitutionEnforcer.validate() - reinforcing evidence_count there too would
    let a single contradicting session look more confident, not less.

    Call this BEFORE enforcer.validate(), and pass the (possibly reinforced)
    returned candidate to both stage_12.run() and stage_13.run() - reinforcement
    must be visible to both the confidence/threshold check and the actual write,
    or the reinforced count is computed but never persisted.

    Tables with no evidence_count column (identity, active_projects) are returned
    unchanged - there's nothing to reinforce.
    """
    existing = _fetch_existing_state(conn, candidate)
    if existing is None or existing.get("evidence_count") is None:
        return candidate
    if existing["current_value"] != candidate.get("proposed_value"):
        return candidate

    reinforced = dict(candidate)
    reinforced["evidence_count"] = existing["evidence_count"] + 1
    return reinforced

def run(conn, candidate: MemoryCandidate, enforcer: ConstitutionEnforcer) -> ValidationResult:
    """
    Validates a memory candidate against the constitution.
    """
    profile_age_weeks = _get_profile_age_weeks(conn)
    existing_field = _fetch_existing_state(conn, candidate)
    
    return enforcer.validate(candidate, existing_field, profile_age_weeks)
