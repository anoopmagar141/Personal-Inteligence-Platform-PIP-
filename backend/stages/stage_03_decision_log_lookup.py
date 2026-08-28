# PIP Message Pipeline - Stage 3: Decision Log Lookup
#
# Thin wrapper: decision_log.search_decisions() already implements the FTS5-with-
# LIKE-fallback search this stage's spec calls for (Part 7.2). This stage's only job
# is the fail-open contract - decision_log.py itself doesn't fail open on a search
# error, it would let sqlite3 exceptions propagate, which is correct for its own
# direct callers (e.g. the /decisions CLI command, where a real error should surface)
# but wrong for a parallel pipeline stage, which must never block the pipeline.

import logging

from backend.memory import decision_log

logger = logging.getLogger(__name__)

# Most relevant N only. _build_fts5_match_query() ORs bareword tokens, so a
# question's ordinary words - "what", "is", "the", "of" - match nearly every
# entry that has any reasoning stored, and this stage was returning all of
# them. Invisible while the decision log was small; with a real log behind it,
# "What is the capital of France?" retrieved 77 decisions and carried a
# couple of hundred tokens of unrelated project history into a
# general-knowledge answer.
#
# Not a change to what counts as a match, which is search_decisions' business
# and is deliberately broad (the OR is what lets one shared content word
# surface a decision a natural-language question shares little vocabulary
# with). This bounds what a single message's context can be filled with.
#
# Nothing new is being hidden: Stage 7 already dropped everything past its
# decision_log_tokens budget, silently and mid-sentence. Cutting here instead
# cuts at bm25 rank - the ordering search_decisions already sorts by - so what
# survives is the most relevant N rather than the first N that happened to fit.
MAX_ENTRIES = 12


def run(conn, retrieval_hint: str, project_id: str | None = None) -> list[dict]:
    """
    Returns the most relevant active decision_log entries matching retrieval_hint.
    Failure mode: return empty, continue (Part 7.2 spec).
    """
    if not retrieval_hint:
        return []
    try:
        entries = decision_log.search_decisions(
            conn, query=retrieval_hint, state="active", project_id=project_id
        )
        return entries[:MAX_ENTRIES]
    except Exception as e:
        logger.error(f"Stage 3 decision log lookup failed, returning empty: {e}")
        return []
