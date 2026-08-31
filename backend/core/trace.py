# PIP Core - Pipeline trace log
#
# Writes to the trace_log table in the SQLCipher-encrypted database. It used to
# write to a plain JSON file at backend/logs/trace_log.json, which had three
# problems, and the schema already carried the answer to all three - the table
# was declared from the start and never written to.
#
#   1. Plaintext on disk. Everything else PIP records lives inside SQLCipher.
#      pipeline.py carries a security fix that had to STOP recording message
#      text because trace_log.json sat outside that boundary - the trace is
#      poorer for it, and the reason has now been removed. Same finding and
#      same resolution as session_snapshot, which used to be a JSON file too.
#   2. Quadratic writes on the hot path. Every single stage_log() call parsed
#      the ENTIRE file, appended one entry, and rewrote the whole thing. A
#      pipeline run logs around fourteen times, so the cost of tracing a message
#      grew with the square of everything ever traced. The file was 90KB after
#      about a day's use. An INSERT does not care how many rows precede it.
#   3. No retention. trace.hard_delete_after_days (90) was in settings.json and
#      read by nothing, so the file only ever grew. purge_old_entries() below
#      implements it.
#
# conn is now the first argument everywhere. Every existing call site already
# had one in scope, including stage_10, whose conn parameter was carried unused
# and documented as "in case future delivery bookkeeping needs it".
#
# THREAD AFFINITY: conn must be the connection belonging to the calling thread.
# SQLCipher connections can only be used on the thread that created them, which
# this codebase has hit as a live production bug more than once. In the WS
# server every trace write happens inside the connection's dedicated
# single-worker executor - see session_lifecycle.run_observer_now, where the
# trace calls were moved inside the executor function for exactly this reason.

import logging
import uuid
from typing import Any

from backend.config.settings import get_settings
from backend.core.types import now_utc

logger = logging.getLogger(__name__)


def generate_trace_id() -> str:
    """Generates a unique trace ID using UUIDv4."""
    return str(uuid.uuid4())


def stage_log(
    conn,
    trace_id: str,
    stage: str,
    status: str,
    message: str,
    error_detail: str = "",
) -> None:
    """
    Records one stage's outcome against a trace.

    Never raises. A trace is a diagnostic aid, and taking down a user's response
    because the diagnostics could not be written would invert the priority
    entirely - the failure goes to the application log instead, where it is
    still visible.

    Commits immediately rather than leaving the row to whatever commits next.
    A trace is worth most when a run ends badly, and an uncommitted trace is
    exactly the one that disappears when the process dies.

    Measured, so nobody has to re-argue it from intuition: fourteen entries -
    one pipeline run - cost 8.64ms committing each, against 0.93ms committing
    once at the end. The 7.7ms difference is 0.4% of the 2s budget
    settings.json sets for a simple query, and it buys a trace that survives the
    crash it was written to explain. Batching would be a real optimisation of
    the wrong thing.
    """
    if conn is None:
        logger.warning(f"trace.stage_log called without a connection; dropping {stage}/{status}.")
        return
    try:
        conn.execute(
            "INSERT INTO trace_log (trace_id, timestamp, stage, status, message, error_detail) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (trace_id, now_utc(), stage, status, message, error_detail),
        )
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to write trace entry ({stage}/{status}): {e}")


def get_trace(conn, trace_id: str) -> list[dict[str, Any]]:
    """
    One trace's entries in the order they were recorded.

    Ordered by id, not timestamp: now_utc() has second resolution and a whole
    pipeline run fits comfortably inside one second, so timestamps tie and the
    stage order - the only thing that makes a trace readable - would be
    arbitrary.
    """
    return [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM trace_log WHERE trace_id = ? ORDER BY id ASC", (trace_id,)
        )
    ]


def list_recent_traces(conn, limit: int = 20) -> list[dict[str, Any]]:
    """
    Most recent traces, newest first, one summary row each: when it started, how
    many stages it recorded, and whether any of them errored.

    A listing rather than raw entries, because the question this answers is
    "which run do I want to look at" - get_trace() answers the next one.
    """
    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT trace_id,
                   MIN(timestamp) AS started_at,
                   COUNT(*) AS entries,
                   SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS errors
            FROM trace_log
            GROUP BY trace_id
            ORDER BY MIN(id) DESC
            LIMIT ?
            """,
            (limit,),
        )
    ]


def purge_old_entries(conn) -> int:
    """
    Deletes entries older than trace.hard_delete_after_days (settings.json, 90)
    and returns how many went. Implements a retention policy that was configured
    from the start and enforced by nothing.

    "hard_delete" is the setting's own word, and it is meant literally: a trace
    is diagnostic telemetry about the user's own messages, so expiry removes the
    row rather than flagging it. Nothing else references these rows, so there is
    nothing to leave dangling.

    Never raises - retention running late is not a reason to fail a startup.
    """
    import datetime

    days = get_settings()["trace"]["hard_delete_after_days"]
    cutoff = (
        datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        cur = conn.execute("DELETE FROM trace_log WHERE timestamp < ?", (cutoff,))
        conn.commit()
    except Exception as e:
        # Exception, not sqlite3.Error: the connection is opened through
        # sqlcipher3, whose DB-API exceptions are a separate hierarchy that
        # sqlite3.Error does not cover. Catching the narrower type made the
        # "never raises" promise above false for the likeliest case of all - a
        # connection already closed underneath a shutdown-time sweep.
        logger.error(f"Trace retention sweep failed, leaving the log alone: {e}")
        return 0
    if cur.rowcount:
        logger.info(f"Trace retention: removed {cur.rowcount} entries older than {days} days.")
    return cur.rowcount
