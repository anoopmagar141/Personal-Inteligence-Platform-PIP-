from typing import Optional, Dict, Any
from datetime import datetime, timezone
from backend.core.types import MemoryCandidate, ValidationResult
from backend.core.constitution_enforcer import ConstitutionEnforcer
from backend.core.types import now_utc
from backend.memory import profile_store

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
            #
            # DISTINCT sessions, not rows: the enforcer compares this against
            # behavioral_override.trigger_sessions (3), and counting rows meant
            # three contradictions inside a single session satisfied a rule that
            # asks for three separate ones - the override could fire off one
            # unusual conversation. COALESCE(session_no, -id) counts a row with
            # no session number as its own session: session_no is NULL only on
            # rows written before that column existed (see profile_store's
            # _ADDED_COLUMNS - deliberately not backfilled, the information does
            # not exist to backfill with), and -id is always negative where a
            # real session_no is always >= 1, so the two can never collide. The
            # effect is that legacy rows keep counting exactly as they did
            # before, and only new rows get the stricter, correct treatment.
            c_row = conn.execute(
                "SELECT COUNT(DISTINCT COALESCE(session_no, -id)) as contradiction_count, "
                "MIN(created_at) as first_created_at "
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

            # Was a hardcoded 0 alongside a real first_contradiction_date read
            # from this same table - a count that could never move, dated from
            # a table nothing wrote to. Both halves are real now; see
            # profile_store.log_skill_contradiction for why skills get a
            # behavioral override after all. Same DISTINCT-session counting as
            # preferences above, for the same reason.
            c_row = conn.execute(
                "SELECT COUNT(DISTINCT COALESCE(session_no, -id)) as contradiction_count, "
                "MIN(created_at) as first_created_at "
                "FROM skill_contradiction_log WHERE skill_id = ?",
                (row["id"],)
            ).fetchone()

            return {
                "current_value": row["level"],
                "source_label": row["source_label"],
                "confidence": row["confidence"],
                "evidence_count": row["evidence_count"],
                "behavioral_signal_count": c_row["contradiction_count"] if c_row else 0,
                "first_contradiction_date": c_row["first_created_at"] if c_row else None
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
            # Resolved through the same helper the write paths use, so lookup
            # and write cannot disagree about which goal a candidate names.
            # This previously did field_name.replace("goal:", ""), a substring
            # replace rather than a prefix strip, and then queried
            # id = 'active_goals' for every candidate the Observer produced -
            # always no row, so a repeated goal never reinforced against its own
            # stored evidence and the conflict check had nothing to compare.
            goal_id = profile_store.goal_id_from_field(field_name or "")
            if goal_id is not None:
                row = conn.execute(
                    "SELECT goal_text, confidence, evidence_count FROM goal_memory WHERE id = ?",
                    (goal_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT goal_text, confidence, evidence_count FROM goal_memory "
                    "WHERE goal_text = ? AND status = 'active'",
                    (str(candidate.get("proposed_value")),),
                ).fetchone()
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

        elif target_table == "topic_interests":
            # Set membership: the topic IS the field, so "already recorded"
            # means present, and current_value equals the proposed value by
            # construction. That matters for the conflict check above - a topic
            # can never contradict itself, so a repeat observation reinforces
            # rather than escalating to TIER_2_REQUIRED.
            row = conn.execute(
                "SELECT evidence_count FROM topic_interests WHERE topic = ? AND status = 'active'",
                (field_name,),
            ).fetchone()
            if not row:
                return None
            return {
                "current_value": field_name,
                "source_label": "inferred",
                "confidence": None,
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

def _record_observation(conn, candidate: MemoryCandidate) -> None:
    """
    Appends this observation to memory_observation_log, stamped with the session
    it was made in. Failure is swallowed: reinforcement is an accuracy
    improvement, and a broken log must never stop a candidate being validated.
    """
    target_table = candidate.get("target_table")
    field_name = candidate.get("field_name")
    proposed_value = candidate.get("proposed_value")
    label = candidate.get("label", "inferred")
    if not target_table or not field_name or proposed_value is None:
        return
    try:
        conn.execute(
            "INSERT INTO memory_observation_log "
            "(target_table, field_name, proposed_value, label, session_no, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (target_table, field_name, str(proposed_value), label,
             profile_store.current_session_no(conn), now_utc()),
        )
        conn.commit()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to record memory observation: {e}")


def _observed_sessions(conn, candidate: MemoryCandidate) -> int:
    """
    How many DISTINCT sessions this exact signal has been observed in, the
    current one included (_record_observation runs first).

    COALESCE(session_no, -id) counts an unstamped row as its own session, the
    same rule the behavioral override uses - session_no is NULL only for
    observations made before onboarding created profile_meta, and -id is always
    negative where a real session_no is always >= 1, so the two cannot collide.

    Counting sessions rather than rows is what makes this safe to call more than
    once for the same candidate: a retry inside one session adds a row but not a
    session, so the count does not move.
    """
    try:
        row = conn.execute(
            "SELECT COUNT(DISTINCT COALESCE(session_no, -id)) AS sessions "
            "FROM memory_observation_log "
            "WHERE target_table = ? AND field_name = ? AND proposed_value = ?",
            (candidate.get("target_table"), candidate.get("field_name"),
             str(candidate.get("proposed_value"))),
        ).fetchone()
        return int(row["sessions"]) if row else 0
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to count memory observations: {e}")
        return 0


def _already_counted_this_session(conn, candidate: MemoryCandidate) -> bool:
    """
    Whether this signal had an observation in the CURRENT session before the
    one _record_observation just wrote for this call.

    _observed_sessions() collapses repeats within a session by construction -
    it counts sessions, not rows. The stored-value branch below does not: it
    adds 1 to whatever the profile row holds, and a second pass in the same
    session reads a row the first pass has already had written, so it adds 1
    again. Two passes, one session, +2.

    Not hypothetical, and not a retry either. drain_pending_on_startup()
    processes every queued transcript in one loop, before any new session has
    begun, so two queued sessions that both mention the same preference are two
    passes under ONE session_no. Startup recovery fills that queue from every
    conversation an unclean shutdown left unobserved, so the batch is routinely
    larger than one.

    An unstamped observation (session_no NULL, from before onboarding created
    profile_meta) is never a repeat: _observed_sessions counts each of those as
    its own session via COALESCE(session_no, -id), and contradicting that here
    would make the two halves disagree about the same rows.

    Fails open to False - the old, over-counting behaviour - because a broken
    read of the log must not silently stop reinforcement altogether. Same
    direction _observed_sessions fails in.
    """
    session_no = profile_store.current_session_no(conn)
    if session_no is None:
        return False
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS observations FROM memory_observation_log "
            "WHERE target_table = ? AND field_name = ? AND proposed_value = ? "
            "AND session_no = ?",
            (candidate.get("target_table"), candidate.get("field_name"),
             str(candidate.get("proposed_value")), session_no),
        ).fetchone()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to check this session's observations: {e}")
        return False
    # > 1, not > 0: _record_observation has already written this call's own row.
    return bool(row) and int(row["observations"]) > 1


def reinforce_evidence(conn, candidate: MemoryCandidate) -> MemoryCandidate:
    """
    Part 8.6's REINFORCEMENT step: a signal seen in more than one session is
    worth more than evidence_count=1, which is all a single Observer pass over a
    single transcript can honestly attest on its own.

    Records the observation, then returns the candidate carrying however much
    evidence has actually accumulated for it:

      - Nothing stored for this field yet -> the number of distinct sessions the
        signal has been observed in. This is the case that was broken. The old
        version could only raise evidence_count by reading the stored row, and
        from week 3 onward (evidence >= 2) storing the row is exactly what the
        thresholds were blocking - so a value PIP had never stored could never
        BE stored, however often the user said it. Measured before the fix: the
        same explicit statement in six separate sessions, DISCARDed six times,
        evidence_count never leaving 1. The call site in Stage 11 already
        claimed this function prevented that; it could not, because there was
        nowhere for the first observation to live.
      - Stored value matches -> max(stored + 1, distinct sessions), where the
        + 1 is this session's own contribution and is added at most once per
        session however many passes that session makes. The log acts as a floor
        for a row whose stored count was reset (a soft-deleted field can come
        back at 1).
      - Stored value differs -> unchanged, deliberately. That is a conflicting
        observation, not a repeat one, and reinforcing it would make a single
        contradicting session look MORE confident rather than less. Conflicts
        have their own path: Stage 13 logs them to preference_contradiction_log
        and the behavioral override escalates to the user.
      - Tables with no evidence_count column to reinforce (identity,
        active_projects) -> unchanged.

    Call this BEFORE enforcer.validate(), and pass the returned candidate to
    both stage_12.run() and stage_13.run() - reinforcement must be visible to
    both the confidence/threshold check and the actual write, or the reinforced
    count is computed but never persisted.

    What this does NOT fix, deliberately: the month_2_plus rule also requires
    confidence >= 0.7, and an inferred label caps confidence at 0.4 no matter
    how many sessions accumulate. An inferred signal therefore still cannot
    auto-write after month 2 - that is the constitution's confidence model, not
    a bug in reinforcement, and the route for such a signal is the user-review
    queue rather than a silent write.
    """
    _record_observation(conn, candidate)
    observed_sessions = _observed_sessions(conn, candidate)

    existing = _fetch_existing_state(conn, candidate)
    if existing is None:
        if observed_sessions <= candidate.get("evidence_count", 1):
            return candidate
        reinforced = dict(candidate)
        reinforced["evidence_count"] = observed_sessions
        return reinforced

    if existing.get("evidence_count") is None:
        return candidate
    if existing["current_value"] != candidate.get("proposed_value"):
        return candidate

    reinforced = dict(candidate)
    # +1 for THIS session, once - see _already_counted_this_session for the
    # second pass in one session that used to add it twice.
    increment = 0 if _already_counted_this_session(conn, candidate) else 1
    reinforced["evidence_count"] = max(existing["evidence_count"] + increment, observed_sessions)
    return reinforced

def run(conn, candidate: MemoryCandidate, enforcer: ConstitutionEnforcer) -> ValidationResult:
    """
    Validates a memory candidate against the constitution.
    """
    profile_age_weeks = _get_profile_age_weeks(conn)
    existing_field = _fetch_existing_state(conn, candidate)
    
    return enforcer.validate(candidate, existing_field, profile_age_weeks)
