import json
from typing import Any

from backend.core.types import now_utc


def create_decision_candidate(
    conn,
    *,
    decision_text: str,
    signals_found: list[str],
    raw_quote: str,
    confidence: float,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO decision_candidates_pending (
            decision_text, signals_found, raw_quote, confidence, state, created_at
        )
        VALUES (?, ?, ?, ?, 'pending', ?)
        """,
        (
            decision_text,
            json.dumps(signals_found),
            raw_quote,
            confidence,
            now_utc(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_decision_candidates(conn, *, limit: int | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT * FROM decision_candidates_pending
        WHERE state = 'pending'
        ORDER BY confidence ASC, created_at ASC
    """
    params: tuple[Any, ...] = ()
    if limit is not None:
        sql += " LIMIT ?"
        params = (limit,)
    return [_candidate_row(row) for row in conn.execute(sql, params)]


def get_decision_candidate(conn, candidate_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM decision_candidates_pending WHERE id = ?",
        (candidate_id,),
    ).fetchone()
    return _candidate_row(row) if row else None


def mark_decision_candidate_promoted(conn, candidate_id: int) -> None:
    conn.execute(
        "UPDATE decision_candidates_pending SET state = 'promoted' WHERE id = ?",
        (candidate_id,),
    )
    conn.commit()


def dismiss_decision_candidate(conn, candidate_id: int) -> None:
    conn.execute(
        """
        UPDATE decision_candidates_pending
        SET state = 'dismissed', dismissed_at = ?
        WHERE id = ?
        """,
        (now_utc(), candidate_id),
    )
    conn.commit()


def _candidate_row(row) -> dict[str, Any]:
    data = dict(row)
    data["signals_found"] = json.loads(data["signals_found"] or "[]")
    return data
