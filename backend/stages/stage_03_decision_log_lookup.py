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


def run(conn, retrieval_hint: str, project_id: str | None = None) -> list[dict]:
    """
    Returns active decision_log entries matching retrieval_hint.
    Failure mode: return empty, continue (Part 7.2 spec).
    """
    if not retrieval_hint:
        return []
    try:
        return decision_log.search_decisions(conn, query=retrieval_hint, state="active", project_id=project_id)
    except Exception as e:
        logger.error(f"Stage 3 decision log lookup failed, returning empty: {e}")
        return []
