# PIP Memory layer - Periodic Memory Verification (constitutional.json
# memory_verification, settings.json memory.verification_loop_*)
#
# Every frequency_sessions (30) sessions, sample fields_sampled (3) stored
# memories and ask the user whether PIP still has them right.
#
# Both settings existed and were read by nothing - no loop, no sampler, no
# question ever asked. The constitution gives this mechanism authority
# "overrides_observer_derived", which is only meaningful if it runs: memory PIP
# inferred or extracted drifts, and the only thing that can settle whether a
# recorded preference is still true is the person it describes.
#
# Deliberately reuses memory_candidates_pending rather than adding a second
# queue. A verification is the same interaction the review queue already models
# - PIP asks, the user accepts or rejects - and confirming one runs the same
# write path (apply_verified_correction, source_label user_verified, maximum
# confidence), which is exactly the "overrides observer-derived" authority the
# constitution asks for. The origin column is what lets a client word the two
# questions differently: "should I remember this?" versus "do I still have this
# right?".
#
# Sampling is deterministic - lowest confidence first, then oldest id - not
# random. The constitution forbids model judgment of relevance for proactive
# triggers, and while this is not one of those, the same reasoning applies: the
# rule for what gets asked about should be inspectable and reproducible rather
# than a shuffle nobody can audit. Lowest-confidence-first also asks about the
# memory PIP is least sure of, which is where a user's answer is worth most.

import logging
from typing import Any

from backend.config.settings import get_settings
from backend.memory import candidate_store

logger = logging.getLogger(__name__)

ORIGIN = "verification"

# Tables sampled from. Both carry a source_label (so an already user-attested
# value can be skipped) and a confidence (so sampling can be ordered), and both
# are writable by apply_verified_correction, which is what a confirmation runs.
# goal_memory is excluded on purpose: its field naming ("goal:<id>") reaches the
# write path through a different convention, and its own decay mechanism already
# asks a version of this question - see profile_store.decay_stale_goals.
_SAMPLED_TABLES = (
    ("preference_memory", "name", "value"),
    ("skill_memory", "name", "level"),
)

# A value the user has already confirmed or corrected does not need confirming
# again - asking would spend the user's attention re-litigating their own answer.
_ALREADY_ATTESTED = ("user_verified", "user_correction")


def is_due(session_no: int | None) -> bool:
    """
    True on every frequency_sessions-th session. None (no profile yet) is never
    due: there is nothing recorded to verify before onboarding.
    """
    if not session_no:
        return False
    return session_no % get_settings()["memory"]["verification_loop_frequency_sessions"] == 0


def select_fields(conn, limit: int | None = None) -> list[dict[str, Any]]:
    """
    The fields to ask about this round: active, not already user-attested, not
    already sitting in the queue, lowest confidence first.

    Excluding what is already pending matters more than it looks. The queue is
    only emptied when the user answers it, so without this a user who ignores
    the queue for 60 sessions would be asked the same three questions twice, and
    confirming one of the duplicates would leave its twin pending forever.
    """
    if limit is None:
        limit = get_settings()["memory"]["verification_loop_sample_size"]

    pending = {
        (row["target_table"], row["field_name"])
        for row in candidate_store.list_memory_candidates(conn)
    }

    rows: list[dict[str, Any]] = []
    for table, name_column, value_column in _SAMPLED_TABLES:
        for row in conn.execute(
            f"SELECT {name_column} AS field_name, {value_column} AS value, "
            f"confidence, source_label FROM {table} "
            f"WHERE status = 'active' AND source_label NOT IN (?, ?) "
            f"ORDER BY confidence ASC, id ASC",
            _ALREADY_ATTESTED,
        ):
            if (table, row["field_name"]) in pending:
                continue
            rows.append({
                "target_table": table,
                "field_name": row["field_name"],
                "value": row["value"],
                "confidence": row["confidence"],
                "source_label": row["source_label"],
            })

    rows.sort(key=lambda r: r["confidence"])
    return rows[:limit]


def run_if_due(conn, session_no: int | None) -> list[int]:
    """
    Queues this round's verification questions if the session is a multiple of
    frequency_sessions. Returns the candidate ids created - empty when not due,
    or when there is nothing left worth asking about.

    Fails open: a broken verification round must never stop a session starting.
    The cost of skipping one is that the questions are asked 30 sessions later;
    the cost of raising here would be a chat that will not open.
    """
    if not is_due(session_no):
        return []

    try:
        fields = select_fields(conn)
    except Exception as e:
        logger.error(f"Memory verification sampling failed, skipping this round: {e}")
        return []

    created = []
    for field in fields:
        try:
            created.append(candidate_store.create_memory_candidate(
                conn,
                target_table=field["target_table"],
                field_name=field["field_name"],
                # The CURRENT stored value, not a new one. The question is "is
                # this still right?", so confirming must reaffirm what is there
                # rather than overwrite it with something the user never said.
                proposed_value=str(field["value"]),
                label=field["source_label"],
                evidence_count=1,
                evidence_text=(
                    f"Periodic memory check (session {session_no}). PIP recorded this "
                    f"as {field['source_label']} and has not had it confirmed since."
                ),
                # REQUIRES_CONFIRMATION so resolving one writes it back as
                # user_verified at maximum confidence - the constitution's
                # "overrides_observer_derived" authority, expressed through the
                # write path that already implements exactly that.
                validation_status="REQUIRES_CONFIRMATION",
                origin=ORIGIN,
            ))
        except Exception as e:
            logger.error(f"Failed to queue verification for {field['field_name']}: {e}")

    if created:
        logger.info(f"Session {session_no}: queued {len(created)} memory verification question(s).")
    return created
