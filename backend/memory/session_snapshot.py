import json
import logging
from typing import List, Optional, TypedDict

logger = logging.getLogger(__name__)


class SessionSnapshot(TypedDict):
    topic: str
    open_problems: List[str]
    last_decisions: List[str]
    suggested_next_step: str
    snapshot_date: str


def load_snapshot(conn) -> Optional[SessionSnapshot]:
    """
    Loads the session snapshot from the SQLCipher-encrypted DB (session_snapshot
    table, singleton row id=1) - moved off a plain data/session_snapshot.json
    file (security review finding: sensitive extracted context sitting in
    plaintext outside the SQLCipher boundary).

    Failure mode: fail-open. No row yet (first-ever run, or Observer hasn't
    completed a session yet) or an unexpected read error both return None -
    missing a snapshot only degrades conversational continuity, it never
    violates a privacy or integrity guarantee, same reasoning as Stage 0's own
    fail-open policy. The old file-based version also fail-opened on a
    malformed/corrupted file; that failure mode doesn't exist here at all -
    the table's NOT NULL columns make a shape-invalid row structurally
    impossible to write in the first place.
    """
    try:
        row = conn.execute(
            "SELECT topic, open_problems, last_decisions, suggested_next_step, snapshot_date "
            "FROM session_snapshot WHERE id = 1"
        ).fetchone()
    except Exception as e:
        logger.error(f"Unexpected error loading session_snapshot: {e}. Failing open to None.")
        return None

    if row is None:
        return None

    return {
        "topic": row["topic"],
        "open_problems": json.loads(row["open_problems"]),
        "last_decisions": json.loads(row["last_decisions"]),
        "suggested_next_step": row["suggested_next_step"],
        "snapshot_date": row["snapshot_date"],
    }


def clear_snapshot(conn) -> bool:
    """
    Removes the singleton snapshot row, returning the store to its genuine
    "no snapshot yet" state (load_snapshot() -> None), rather than leaving a
    row with empty strings that merely reads as one.

    Exists because a snapshot can be actively wrong rather than just stale:
    an Observer that extracted its topic from a transcript containing the
    assistant's own invented content will persist that invention here, and
    every subsequent session then receives it as established context (Stage 7
    assembles it into the prompt unconditionally). There was no supported way
    to retract that - write_snapshot() only ever overwrites with another
    snapshot, and the next real session-end may not arrive for days.

    Deliberately in this module rather than a caller issuing its own DELETE:
    session_snapshot is the sole owner of this table, and a cleanup script
    reaching past it would be exactly the direct-SQL coupling the dependency
    rule exists to prevent.

    Returns True if a row was actually removed, False if there was none -
    so a caller can report "nothing to clear" honestly instead of implying
    it undid something.
    """
    cur = conn.execute("DELETE FROM session_snapshot WHERE id = 1")
    conn.commit()
    return cur.rowcount > 0


def write_snapshot(conn, snapshot: SessionSnapshot) -> None:
    """
    Writes a new session snapshot to the DB. Called by the Observer (Stage 11)
    at the end of a session. Singleton row - INSERT ... ON CONFLICT(id) DO
    UPDATE, the same upsert pattern already used for profile_meta/identity/
    interaction_style.
    """
    conn.execute(
        """
        INSERT INTO session_snapshot (id, topic, open_problems, last_decisions, suggested_next_step, snapshot_date)
        VALUES (1, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            topic = excluded.topic,
            open_problems = excluded.open_problems,
            last_decisions = excluded.last_decisions,
            suggested_next_step = excluded.suggested_next_step,
            snapshot_date = excluded.snapshot_date
        """,
        (
            snapshot["topic"],
            json.dumps(snapshot["open_problems"]),
            json.dumps(snapshot["last_decisions"]),
            snapshot["suggested_next_step"],
            snapshot["snapshot_date"],
        ),
    )
    conn.commit()
