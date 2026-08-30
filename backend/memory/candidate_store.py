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


def create_memory_candidate(
    conn,
    *,
    target_table: str,
    field_name: str,
    proposed_value: str,
    label: str,
    evidence_count: int,
    evidence_text: str,
    validation_status: str,
    origin: str = "observer",
) -> int:
    cur = conn.execute(
        """
        INSERT INTO memory_candidates_pending (
            target_table, field_name, proposed_value, label,
            evidence_count, evidence_text, validation_status, origin, state, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
        """,
        (
            target_table,
            field_name,
            proposed_value,
            label,
            evidence_count,
            evidence_text,
            validation_status,
            origin,
            now_utc(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_memory_candidates(conn, *, limit: int | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT * FROM memory_candidates_pending
        WHERE state = 'pending'
        ORDER BY created_at ASC
    """
    params: tuple[Any, ...] = ()
    if limit is not None:
        sql += " LIMIT ?"
        params = (limit,)
    return [dict(row) for row in conn.execute(sql, params)]


def find_pending_memory_candidate(
    conn,
    *,
    target_table: str,
    field_name: str,
    proposed_value: Any,
) -> dict[str, Any] | None:
    """
    An unanswered candidate already asking this exact question, if there is one.

    Matched on target_table as well as field_name and proposed_value. The table
    is what makes the field name unambiguous - field names are only unique
    within their own table, so two tables that happened to share one would
    otherwise be treated as the same question and one of them would be dropped.

    Scoped to state = 'pending' on purpose. A resolved or dismissed candidate is
    a question the user has already answered, and a fresh observation later is
    new information rather than a repeat - suppressing it against an answer from
    weeks ago would be the silent discard this queue exists to avoid.
    """
    row = conn.execute(
        """
        SELECT * FROM memory_candidates_pending
        WHERE state = 'pending'
          AND target_table = ?
          AND field_name = ?
          AND proposed_value = ?
        ORDER BY created_at ASC
        LIMIT 1
        """,
        (target_table, field_name, str(proposed_value)),
    ).fetchone()
    return dict(row) if row else None


def get_memory_candidate(conn, candidate_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM memory_candidates_pending WHERE id = ?",
        (candidate_id,),
    ).fetchone()
    return dict(row) if row else None


def mark_memory_candidate_resolved(conn, candidate_id: int) -> None:
    conn.execute(
        "UPDATE memory_candidates_pending SET state = 'resolved', resolved_at = ? WHERE id = ?",
        (now_utc(), candidate_id),
    )
    conn.commit()


def dismiss_memory_candidate(conn, candidate_id: int) -> None:
    conn.execute(
        "UPDATE memory_candidates_pending SET state = 'dismissed', resolved_at = ? WHERE id = ?",
        (now_utc(), candidate_id),
    )
    conn.commit()
