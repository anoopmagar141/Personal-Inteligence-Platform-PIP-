import logging
from typing import Any

from backend.core.constitution_enforcer import is_contradicting_inferred_observation
from backend.core.types import MemoryCandidate, ValidationResult
from backend.memory import candidate_store, profile_store

logger = logging.getLogger(__name__)

# ValidationResult statuses that cannot be resolved without a live user decision.
# Persisted to memory_candidates_pending so they survive session close (Part 8.6).
PENDING_STATUSES = {"REQUIRES_CONFIRMATION", "TIER_2_REQUIRED", "PROMPT_RECONCILIATION"}


# The tables whose stated values a behavioral contradiction can be logged
# against, and how to read the current value out of each.
_CONTRADICTION_TABLES = {
    "preference_memory": ("value", profile_store.log_preference_contradiction),
    "skill_memory": ("level", profile_store.log_skill_contradiction),
}


def _maybe_log_behavioral_contradiction(conn, candidate: MemoryCandidate) -> None:
    """
    A DISCARDed inferred candidate that contradicts a stated value is exactly
    the evidence the behavioral override mechanism needs to accumulate before it
    can ever fire (see is_contradicting_inferred_observation's docstring) -
    without this it is thrown away silently and the override's
    trigger_sessions/trigger_days condition can never become true from real
    usage.

    Covers skill_memory as well as preference_memory. This was previously
    preference-only, on the grounds that skill_memory uses the constitution's
    "demonstrated_performance" validation model rather than
    "explicit_or_behavioral" - see profile_store.log_skill_contradiction for
    why that reasoning was reversed, and what it was silently costing.
    """
    target_table = candidate.get("target_table")
    handler = _CONTRADICTION_TABLES.get(target_table)
    if handler is None:
        return
    value_column, log_contradiction = handler

    row = conn.execute(
        f"SELECT id, {value_column} AS current_value, source_label "
        f"FROM {target_table} WHERE name = ?",
        (candidate.get("field_name"),),
    ).fetchone()
    if row is None:
        return

    if not is_contradicting_inferred_observation(
        candidate.get("proposed_value"),
        row["current_value"],
        candidate.get("label", "inferred"),
        row["source_label"],
    ):
        return

    log_contradiction(conn, row["id"], candidate.get("evidence_text", ""))


def run(conn, candidate: MemoryCandidate, validation_result: ValidationResult) -> str:
    """
    Routes a Stage 12 ValidationResult to its write path.

    APPROVED                -> write now via profile_store.write_approved_candidate
    REQUIRES_CONFIRMATION,
    TIER_2_REQUIRED,
    PROMPT_RECONCILIATION   -> persist to memory_candidates_pending, then surfaced to
                               the user by list_pending() and applied or discarded by
                               resolve_pending()/dismiss_pending() below. Deduplicated
                               against the questions already waiting there, so a signal
                               repeated across sessions is asked about once
    HARD_REJECT, DISCARD    -> logged, no write

    Failure mode: retry the write once; on repeated failure, log and discard
    rather than risk a partial/corrupt write (Part 7 Stage 13 spec).

    Returns one of: "written", "pending", "rejected", "failed".
    """
    status = validation_result.status

    if status == "APPROVED":
        try:
            profile_store.write_approved_candidate(conn, candidate)
        except Exception as e:
            logger.warning(f"Stage 13 write failed, retrying once: {e}")
            try:
                profile_store.write_approved_candidate(conn, candidate)
            except Exception as e2:
                logger.error(f"Stage 13 write failed twice, discarding candidate: {e2}")
                return "failed"
        return "written"

    if status in PENDING_STATUSES:
        # Goals are gated by the constitution, so every session that mentions
        # one queues a confirmation for it - measured at three identical rows
        # after three sessions, and the user would have been asked the same
        # question three times, with confirming one leaving two live twins
        # behind it. The same applies to any gated field the user keeps
        # mentioning.
        #
        # Returns "pending" rather than a new outcome value: the candidate's
        # state genuinely IS pending, represented by the row already sitting in
        # the queue, and adding a fifth return value would quietly narrow every
        # existing `== "pending"` check so that none of them covered this path.
        # The dedup is asserted by row count instead, which is the thing that
        # actually matters.
        duplicate = candidate_store.find_pending_memory_candidate(
            conn,
            target_table=candidate.get("target_table"),
            field_name=candidate.get("field_name"),
            proposed_value=candidate.get("proposed_value"),
        )
        if duplicate is not None:
            logger.info(
                f"Candidate {status} already queued as #{duplicate['id']} "
                f"({candidate.get('target_table')}.{candidate.get('field_name')}); not re-asking."
            )
            return "pending"

        candidate_store.create_memory_candidate(
            conn,
            target_table=candidate.get("target_table"),
            field_name=candidate.get("field_name"),
            proposed_value=candidate.get("proposed_value"),
            label=candidate.get("label"),
            evidence_count=candidate.get("evidence_count"),
            evidence_text=candidate.get("evidence_text"),
            validation_status=status,
        )
        return "pending"

    if status in ("HARD_REJECT", "DISCARD"):
        logger.info(f"Candidate {status.lower()}: {validation_result.reason}")
        _maybe_log_behavioral_contradiction(conn, candidate)
        return "rejected"

    raise ValueError(f"Unknown ValidationResult status: {status}")


# ---------------------------------------------------------------------------
# Resolving what run() parked.
#
# run() above routes REQUIRES_CONFIRMATION / TIER_2_REQUIRED /
# PROMPT_RECONCILIATION to memory_candidates_pending and returns "pending", on
# the promise (Part 8.6, and this module's own docstring) that they are
# "surfaced next session" for the user to decide. Nothing surfaced them:
# candidate_store's four read/resolve helpers had no callers outside tests and
# there was no API route, so every candidate the constitution said to ask about
# was written to a table and then left there forever. The rows accumulated, the
# user was never asked, and the memory those candidates represented was
# silently never learned.
#
# These live here rather than in candidate_store because resuming a parked
# branch belongs next to the code that parked it - run() decides a candidate
# needs a human, and resolve_pending() is the other half of that same decision.
# candidate_store stays a pure store (no profile_store import, no write-path
# knowledge), which is what let it be reused by the retraction script.
#
# Deliberately NOT auto-resolving anything: the whole point of these three
# statuses is that the constitution requires a live user decision. A "confirm
# everything older than N days" convenience would quietly reintroduce exactly
# the unattended write the gate exists to prevent.


def list_pending(conn, *, limit: int | None = None) -> list[dict[str, Any]]:
    """Memory candidates awaiting a user decision, oldest first."""
    return candidate_store.list_memory_candidates(conn, limit=limit)


def resolve_pending(conn, candidate_id: int) -> dict[str, Any]:
    """
    The user confirmed a pending candidate: apply it as a verified correction
    and mark the row resolved.

    Writes through profile_store.apply_verified_correction rather than
    write_approved_candidate - a candidate that reached this table did so
    because the constitution demanded a human decision, and once that decision
    exists the value is user-attested, not Observer-attested. That is the
    difference the two write paths encode (maximum confidence and a
    user_verified/user_correction source_label, versus the candidate's own
    label and evidence_count).

    The row is marked resolved only after the write succeeds. A write that
    raises leaves the candidate pending and propagates, so a failure is visible
    and retryable instead of consuming the candidate and losing it.

    Raises LookupError when there is no pending candidate by that id, and lets
    profile_store's ValueError through unchanged when there is one but it
    cannot be applied - two different failures that the decision-candidate
    equivalents can collapse into one ValueError only because "not found" is
    the sole way those can fail. Here it is not: a goal_memory candidate whose
    field_name is not prefixed "goal:" reaches apply_verified_correction and is
    rejected by it, and the Observer's own approved goal fields (active_goals,
    project_objectives) are spelled exactly that way. Reporting that to the
    caller as "no such candidate" would send them looking for a row that is
    sitting right there in the queue.
    """
    candidate = candidate_store.get_memory_candidate(conn, candidate_id)
    if candidate is None or candidate["state"] != "pending":
        raise LookupError("pending memory candidate not found")

    memory_candidate: MemoryCandidate = {
        "target_table": candidate["target_table"],
        "field_name": candidate["field_name"],
        "proposed_value": candidate["proposed_value"],
        "label": candidate["label"],
        "evidence_count": candidate["evidence_count"],
        "evidence_text": candidate["evidence_text"] or "",
    }
    validation_result = ValidationResult(
        candidate["validation_status"], reason="user_resolved_pending"
    )

    profile_store.apply_verified_correction(conn, memory_candidate, validation_result)
    candidate_store.mark_memory_candidate_resolved(conn, candidate_id)
    logger.info(
        f"Pending memory candidate {candidate_id} confirmed by user: "
        f"{candidate['target_table']}.{candidate['field_name']}"
    )
    return {
        "status": "resolved",
        "candidate_id": candidate_id,
        "target_table": candidate["target_table"],
        "field_name": candidate["field_name"],
    }


def dismiss_pending(conn, candidate_id: int) -> dict[str, Any]:
    """
    The user rejected a pending candidate: mark it dismissed and write nothing.

    Nothing is logged to preference_contradiction_log here, unlike run()'s
    DISCARD path. That path logs because the Observer keeps inferring something
    the stored value contradicts, and the count of those is the evidence the
    behavioral override accumulates. A user saying "no" is the opposite signal -
    counting it toward a trigger whose whole purpose is to ask the user again
    would make each rejection push the system closer to re-asking.
    """
    candidate = candidate_store.get_memory_candidate(conn, candidate_id)
    if candidate is None or candidate["state"] != "pending":
        raise LookupError("pending memory candidate not found")
    candidate_store.dismiss_memory_candidate(conn, candidate_id)
    return {"status": "dismissed", "candidate_id": candidate_id}
