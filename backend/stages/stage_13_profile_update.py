import logging
from backend.core.types import MemoryCandidate, ValidationResult
from backend.memory import candidate_store, profile_store

logger = logging.getLogger(__name__)

# ValidationResult statuses that cannot be resolved without a live user decision.
# Persisted to memory_candidates_pending so they survive session close (Part 8.6).
PENDING_STATUSES = {"REQUIRES_CONFIRMATION", "TIER_2_REQUIRED", "PROMPT_RECONCILIATION"}


def run(conn, candidate: MemoryCandidate, validation_result: ValidationResult) -> str:
    """
    Routes a Stage 12 ValidationResult to its write path.

    APPROVED                -> write now via profile_store.write_approved_candidate
    REQUIRES_CONFIRMATION,
    TIER_2_REQUIRED,
    PROMPT_RECONCILIATION   -> persist to memory_candidates_pending, surfaced next session
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
        return "rejected"

    raise ValueError(f"Unknown ValidationResult status: {status}")
