import logging
import re
from typing import Optional

from backend.memory import decision_log, profile_store, vector_store

logger = logging.getLogger(__name__)

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "and", "or", "but", "for",
    "to", "of", "in", "on", "at", "with", "this", "that", "it", "as", "be",
    "we", "i", "you", "our", "my", "so", "if", "not", "chose", "chosen",
}

# Conflict detection is a lexical heuristic, not semantic contradiction detection -
# there is no LLM call in this stage (Part 7 pipeline keeps retrieval stages fast and
# deterministic; ADR-014 forbids "model judgment of relevance" for proactive triggers,
# and the same caution applies here). This flags topical overlap between a retrieved
# chunk and an active decision as "worth a human double-check," not a proven
# contradiction. Calibrate the threshold from real usage, same as similarity_threshold.
_CONFLICT_OVERLAP_THRESHOLD = 0.3


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


def _overlap_ratio(a: set[str], b: set[str]) -> float:
    """
    Overlap coefficient (intersection / smaller set size), not Jaccard. Decision
    text/reasoning and a retrieved chunk are usually very different lengths, and
    Jaccard's union-based denominator punishes that size mismatch too heavily -
    it under-flags exactly the short-decision-vs-long-chunk case this check exists
    for. Overlap coefficient asks "how much of the smaller side is covered," which
    is the more honest question for a topical-overlap heuristic.
    """
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _check_conflict(chunks: list[dict], active_decisions: list[dict]) -> bool:
    for chunk in chunks:
        chunk_kw = _keywords(chunk["chunk_text"])
        for decision in active_decisions:
            decision_kw = _keywords(decision.get("decision_text", "") + " " + (decision.get("reasoning") or ""))
            if _overlap_ratio(chunk_kw, decision_kw) >= _CONFLICT_OVERLAP_THRESHOLD:
                return True
    return False


def run(
    conn,
    retrieval_hint: str,
    project_id: Optional[str] = None,
    threshold: float | None = None,
    top_k: int | None = None,
) -> dict:
    """
    Retrieves RAG chunks above threshold and flags potential conflict against the
    active Decision Log. Fail-open per Part 7.4: any failure returns empty chunks
    and conflict_flag=False, pipeline continues.

    threshold/top_k default to None and are resolved by vector_store from
    config/settings.json. They used to be restated here as 0.6 and 3 - the same
    numbers settings.json already carried, in a third place, where the pipeline
    (which passes neither) picked them up and settings.json was read by nobody.
    """
    try:
        chunks = vector_store.query(conn, retrieval_hint, project_id=project_id, threshold=threshold, top_k=top_k)
    except Exception as e:
        logger.error(f"Stage 5 RAG retrieval failed, returning empty: {e}")
        return {"chunks": [], "conflict_flag": False}

    if not chunks:
        return {"chunks": [], "conflict_flag": False}

    # document_access_patterns is written here and nowhere else. The
    # constitution files it under observer_may_write, but the Observer reads a
    # conversation transcript and a transcript cannot say which documents were
    # consulted - this stage is the only thing that knows. Documents reach a
    # conversation only by being retrieved, so retrieval frequency IS the access
    # pattern. Fails open inside record_document_access; a usage counter must
    # never cost a response.
    profile_store.record_document_access(
        conn, [chunk.get("file_path") for chunk in chunks]
    )

    try:
        active_decisions = decision_log.list_decisions(conn, state="active", project_id=project_id)
        conflict_flag = _check_conflict(chunks, active_decisions)
    except Exception as e:
        logger.error(f"Stage 5 conflict check failed, defaulting to no conflict: {e}")
        conflict_flag = False

    return {"chunks": chunks, "conflict_flag": conflict_flag}
