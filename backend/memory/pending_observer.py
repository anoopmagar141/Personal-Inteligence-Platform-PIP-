# ADR-033 condition 2: an Observer pass on llama3.1:8b cannot block SIGINT/SIGTERM long
# enough to finish (~130s cold measured in the ADR-033 A/B test). Rather than block exit
# or lose the session's learning, the transcript is enqueued here and drained on next
# startup, before Stage 0 (Part 7 pipeline order). This module owns the pending_observer
# table (ADR-025 one-writer-per-resource).
#
# Stage 11 (Observer) doesn't exist yet - Phase 7 hasn't started. drain() takes the actual
# extraction function as a parameter so this queue can be built and fully tested now,
# ready for Stage 11 to plug into later without changing this module.
from typing import Any, Callable, Optional

from backend.core.types import now_utc


class RetryableError(Exception):
    """
    Raised by an observer_runner to say "this could not be attempted, try again
    next start" rather than "this was attempted and failed."

    Defined here rather than imported from the stage that raises the underlying
    error, because this module deliberately knows nothing about Stage 11 - it
    takes the extraction function as a parameter (see the note at the top of
    this file), and importing backend.stages from the memory layer would invert
    that. session_lifecycle owns the translation: it already imports both.

    The distinction is load-bearing because 'failed' is TERMINAL here.
    _list_for_drain() only picks up 'pending' and 'processing', so a row marked
    failed is retained but never retried by anything. That is right for a
    transcript the model choked on, and wrong for one it never saw: an
    unreachable Ollama at startup would file every recovered session as
    permanently failed, which is the same lost learning as dropping it, just
    with a row left behind as evidence.
    """


def enqueue(
    conn,
    session_transcript: str,
    session_ended_at: Optional[str] = None,
    session_started_at: Optional[str] = None,
) -> int:
    timestamp = now_utc()
    cur = conn.execute(
        """
        INSERT INTO pending_observer
            (session_transcript, session_started_at, session_ended_at, status, created_at)
        VALUES (?, ?, ?, 'pending', ?)
        """,
        (session_transcript, session_started_at, session_ended_at or timestamp, timestamp),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_pending(conn, limit: Optional[int] = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM pending_observer WHERE status = 'pending' ORDER BY created_at ASC"
    params: tuple[Any, ...] = ()
    if limit is not None:
        sql += " LIMIT ?"
        params = (limit,)
    return [dict(r) for r in conn.execute(sql, params)]


def _list_for_drain(conn) -> list[dict[str, Any]]:
    # Includes 'processing' rows: see the schema.sql comment on this table for why.
    return [
        dict(r) for r in conn.execute(
            "SELECT * FROM pending_observer WHERE status IN ('pending', 'processing') "
            "ORDER BY created_at ASC"
        )
    ]


def mark_processing(conn, entry_id: int) -> None:
    conn.execute("UPDATE pending_observer SET status = 'processing' WHERE id = ?", (entry_id,))
    conn.commit()


def mark_completed(conn, entry_id: int) -> None:
    conn.execute(
        "UPDATE pending_observer SET status = 'completed', processed_at = ? WHERE id = ?",
        (now_utc(), entry_id),
    )
    conn.commit()


def mark_failed(conn, entry_id: int, error_detail: str) -> None:
    conn.execute(
        "UPDATE pending_observer SET status = 'failed', processed_at = ?, error_detail = ? WHERE id = ?",
        (now_utc(), error_detail, entry_id),
    )
    conn.commit()


def drain(conn, observer_runner: Callable[[str], None]) -> dict[str, list]:
    """
    Runs observer_runner(session_transcript) for every pending/stuck-processing entry.
    observer_runner must raise on failure, return anything (or nothing) on success.

    Three outcomes, not two:

      completed - ran, marked 'completed'.
      deferred  - observer_runner raised RetryableError, meaning it could not be
                  attempted at all (the LLM was unreachable). The row is LEFT as
                  'processing' so the next drain() picks it up, because the work
                  genuinely has not happened yet.
      failed    - anything else. Marked 'failed' with error_detail and retained -
                  never silently dropped, never hard-deleted (ADR-024's memory
                  deletion philosophy).

    'deferred' exists because 'failed' is terminal: _list_for_drain() only
    selects 'pending' and 'processing'. Before it, an unreachable Ollama at
    startup - the normal state after the crash that recovery exists for - filed
    every recovered transcript as permanently failed, or worse, as completed
    (Stage 11 used to fail open rather than raise, so drain never saw an error
    at all and called mark_completed on a transcript the model never read).

    One entry failing or deferring does not block draining the rest.
    """
    results: dict[str, list] = {"completed": [], "deferred": [], "failed": []}
    for entry in _list_for_drain(conn):
        mark_processing(conn, entry["id"])
        try:
            observer_runner(entry["session_transcript"])
        except RetryableError as e:
            # Deliberately no status write: 'processing' is already the state
            # _list_for_drain() picks back up, and it is the honest description
            # of a row that still needs doing.
            results["deferred"].append({"id": entry["id"], "reason": str(e)})
        except Exception as e:
            mark_failed(conn, entry["id"], str(e))
            results["failed"].append({"id": entry["id"], "error": str(e)})
        else:
            mark_completed(conn, entry["id"])
            results["completed"].append(entry["id"])
    return results
