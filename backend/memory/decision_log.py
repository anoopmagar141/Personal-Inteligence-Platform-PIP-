from typing import Any

from backend.config.settings import get_settings
from backend.core.types import now_utc
from backend.memory import candidate_store


COMMITMENT_TERMS = (
    "decide",
    "decided",
    "choose",
    "chosen",
    "use ",
    "will ",
    "commit",
    "locked",
)


def create_decision(
    conn,
    *,
    text: str,
    reasoning: str | None = None,
    alternatives: str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    signals = classify_decision_signals(text, reasoning, alternatives)
    confidence = score_confidence(signals)
    threshold = get_settings()["decision_log"]["log_threshold_manual"]

    if confidence < threshold:
        candidate_id = candidate_store.create_decision_candidate(
            conn,
            decision_text=text,
            signals_found=signals,
            raw_quote=text,
            confidence=confidence,
        )
        return {"status": "pending", "candidate_id": candidate_id, "confidence": confidence, "signals": signals}

    decision_id = insert_decision(
        conn,
        text=text,
        reasoning=reasoning,
        alternatives=alternatives,
        project_id=project_id,
        confidence=confidence,
    )
    return {"status": "logged", "decision_id": decision_id, "confidence": confidence, "signals": signals}


def insert_decision(
    conn,
    *,
    text: str,
    reasoning: str | None = None,
    alternatives: str | None = None,
    project_id: str | None = None,
    confidence: float = 0.4,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO decision_log (
            decision_text, reasoning, alternatives_considered,
            project_id, confidence, state, created_at
        )
        VALUES (?, ?, ?, ?, ?, 'active', ?)
        """,
        (text, reasoning, alternatives, project_id, confidence, now_utc()),
    )
    decision_id = int(cur.lastrowid)
    _sync_decision_fts(conn, decision_id, text, reasoning, alternatives)
    conn.commit()
    return decision_id


def list_decisions(conn, *, state: str = "active", project_id: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM decision_log WHERE state = ?"
    params: list[Any] = [state]
    if project_id:
        sql += " AND project_id = ?"
        params.append(project_id)
    sql += " ORDER BY created_at DESC, id DESC"
    return [dict(row) for row in conn.execute(sql, params)]


def search_decisions(
    conn,
    *,
    query: str,
    state: str = "active",
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if _ensure_decision_fts(conn):
        return _search_decisions_fts(conn, query=query, state=state, project_id=project_id)
    return _search_decisions_like(conn, query=query, state=state, project_id=project_id)


def update_decision_state(
    conn,
    decision_id: int,
    *,
    state: str,
    reason: str,
    superseded_by: int | None = None,
) -> None:
    if state not in {"active", "superseded", "abandoned"}:
        raise ValueError("invalid decision state")
    if state in {"superseded", "abandoned"} and not reason.strip():
        raise ValueError("reason is required")

    conn.execute(
        "UPDATE decision_log SET state = ?, superseded_by = ? WHERE id = ?",
        (state, superseded_by, decision_id),
    )
    conn.commit()


def list_pending(conn, *, limit: int | None = None) -> list[dict[str, Any]]:
    return candidate_store.list_decision_candidates(conn, limit=limit)


def promote_pending(conn, candidate_id: int) -> dict[str, Any]:
    candidate = candidate_store.get_decision_candidate(conn, candidate_id)
    if candidate is None or candidate["state"] != "pending":
        raise ValueError("pending decision candidate not found")

    decision_id = insert_decision(
        conn,
        text=candidate["decision_text"],
        reasoning=candidate["raw_quote"],
        alternatives=None,
        project_id=None,
        confidence=max(candidate["confidence"], get_settings()["decision_log"]["log_threshold_manual"]),
    )
    candidate_store.mark_decision_candidate_promoted(conn, candidate_id)
    return {"status": "promoted", "decision_id": decision_id}


def dismiss_pending(conn, candidate_id: int) -> dict[str, Any]:
    candidate = candidate_store.get_decision_candidate(conn, candidate_id)
    if candidate is None or candidate["state"] != "pending":
        raise ValueError("pending decision candidate not found")
    candidate_store.dismiss_decision_candidate(conn, candidate_id)
    return {"status": "dismissed", "candidate_id": candidate_id}


def classify_decision_signals(
    text: str,
    reasoning: str | None,
    alternatives: str | None,
) -> list[str]:
    signals: list[str] = []
    if reasoning and reasoning.strip():
        signals.append("explicit_reasoning_in_conversation")
    lowered = f" {text.lower()} "
    if any(term in lowered for term in COMMITMENT_TERMS):
        signals.append("commitment_language")
    if alternatives and alternatives.strip():
        signals.append("alternative_considered")
    return signals


def score_confidence(signals: list[str]) -> float:
    count = len(set(signals))
    if count >= 3:
        return 1.0
    if count == 2:
        return 0.7
    if count == 1:
        return 0.4
    return 0.0


def _ensure_decision_fts(conn) -> bool:
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS decision_fts
            USING fts5(
                decision_text,
                reasoning,
                alternatives_considered,
                decision_id UNINDEXED
            )
            """
        )
        conn.commit()
        return True
    except Exception:
        return False


def _sync_decision_fts(
    conn,
    decision_id: int,
    text: str,
    reasoning: str | None,
    alternatives: str | None,
) -> None:
    if not _ensure_decision_fts(conn):
        return
    conn.execute(
        """
        INSERT INTO decision_fts (
            decision_text, reasoning, alternatives_considered, decision_id
        )
        VALUES (?, ?, ?, ?)
        """,
        (text, reasoning, alternatives, decision_id),
    )


def _search_decisions_fts(
    conn,
    *,
    query: str,
    state: str,
    project_id: str | None,
) -> list[dict[str, Any]]:
    sql = """
        SELECT d.*
        FROM decision_fts f
        JOIN decision_log d ON d.id = f.decision_id
        WHERE decision_fts MATCH ? AND d.state = ?
    """
    params: list[Any] = [query, state]
    if project_id:
        sql += " AND d.project_id = ?"
        params.append(project_id)
    sql += " ORDER BY d.created_at DESC, d.id DESC"
    return [dict(row) for row in conn.execute(sql, params)]


def _search_decisions_like(
    conn,
    *,
    query: str,
    state: str,
    project_id: str | None,
) -> list[dict[str, Any]]:
    needle = f"%{query}%"
    sql = """
        SELECT * FROM decision_log
        WHERE state = ?
          AND (
            decision_text LIKE ?
            OR reasoning LIKE ?
            OR alternatives_considered LIKE ?
          )
    """
    params: list[Any] = [state, needle, needle, needle]
    if project_id:
        sql += " AND project_id = ?"
        params.append(project_id)
    sql += " ORDER BY created_at DESC, id DESC"
    return [dict(row) for row in conn.execute(sql, params)]
