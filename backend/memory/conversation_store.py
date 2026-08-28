# PIP Memory layer - Conversation history (schema.sql's conversations/messages
# tables).
#
# Gives chat a Claude/ChatGPT-style sidebar: every turn is written here as it
# happens (see backend/api/server.py's ws_chat()), and a past conversation_id
# can be resumed by replaying its messages back into a fresh WS connection's
# in-memory conversation_history - Part 7's "no message-history table, the
# caller owns that state" was true right up until this feature.

import uuid
from typing import Any, Optional

from backend.core.types import now_utc

TITLE_MAX_LENGTH = 60


def create_conversation(conn, project_id: Optional[str] = None, *, timestamp: str | None = None) -> str:
    conversation_id = str(uuid.uuid4())
    ts = timestamp or now_utc()
    conn.execute(
        "INSERT INTO conversations (id, title, project_id, created_at, updated_at) VALUES (?, 'New chat', ?, ?, ?)",
        (conversation_id, project_id, ts, ts),
    )
    conn.commit()
    return conversation_id


def append_message(conn, conversation_id: str, role: str, content: str, *, timestamp: str | None = None) -> None:
    """
    Writes one turn and updates the conversation's updated_at (for
    most-recently-active sidebar ordering) and title (first user message
    only - every later call is a no-op on title, WHERE title = 'New chat'
    keeps a user from clobbering a title they already set - not exposed yet,
    but this way adding a rename endpoint later doesn't need any changes here).
    """
    ts = timestamp or now_utc()
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (conversation_id, role, content, ts),
    )
    conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (ts, conversation_id))
    if role == "user":
        title = content.strip().replace("\n", " ")
        if len(title) > TITLE_MAX_LENGTH:
            title = title[:TITLE_MAX_LENGTH].rstrip() + "..."
        if title:
            conn.execute(
                "UPDATE conversations SET title = ? WHERE id = ? AND title = 'New chat'",
                (title, conversation_id),
            )
    conn.commit()


def list_conversations(conn, project_id: Optional[str] = None) -> list[dict[str, Any]]:
    if project_id is not None:
        rows = conn.execute(
            "SELECT id, title, project_id, created_at, updated_at FROM conversations "
            "WHERE project_id = ? ORDER BY updated_at DESC",
            (project_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, title, project_id, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_messages(conn, conversation_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY id ASC",
        (conversation_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_messages_after(
    conn, conversation_id: str, after_message_id: Optional[int] = None
) -> list[dict[str, Any]]:
    """
    Messages the Observer has not seen yet, oldest first, including their ids.

    Separate from get_messages() rather than a parameter on it because the two
    have different jobs and different shapes: get_messages() feeds the client
    and the LLM's context, where every turn belongs and the id is noise;
    this feeds extraction, where the id is the whole point - the caller needs
    to know which message it got to so it can record the new high-water mark.

    after_message_id=None returns everything, which is what a conversation the
    Observer has never touched should get.
    """
    if after_message_id is None:
        rows = conn.execute(
            "SELECT id, role, content, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, role, content, created_at FROM messages "
            "WHERE conversation_id = ? AND id > ? ORDER BY id ASC",
            (conversation_id, after_message_id),
        ).fetchall()
    return [dict(r) for r in rows]


def observed_upto(conn, conversation_id: str) -> Optional[int]:
    """
    The messages.id high-water mark for this conversation, or None if the
    Observer has never processed any of it.

    Collapses the legacy case on the way out: a row with observed_at set but no
    high-water mark predates the column and means "all of it was observed," so
    the current maximum id is returned rather than None. Without that, every
    conversation carried over from before this column would look completely
    unprocessed and be queued for a full re-extraction.
    """
    row = conn.execute(
        "SELECT observed_at, observed_upto_message_id FROM conversations WHERE id = ?",
        (conversation_id,),
    ).fetchone()
    if row is None:
        return None
    if row["observed_upto_message_id"] is not None:
        return row["observed_upto_message_id"]
    if row["observed_at"] is not None:
        return conn.execute(
            "SELECT MAX(id) FROM messages WHERE conversation_id = ?", (conversation_id,)
        ).fetchone()[0]
    return None


def mark_observed(
    conn,
    conversation_id: str,
    *,
    timestamp: str | None = None,
    upto_message_id: int | None = None,
) -> None:
    """
    Records that the Observer has taken a pass, and HOW FAR it got, so startup
    recovery neither reprocesses what was handled nor skips what wasn't.

    upto_message_id defaults to the conversation's current highest message id.
    That is right for the live paths (every turn is committed before the
    Observer runs, so "everything currently there" is exactly what it read),
    but recovery passes the id explicitly: it built its transcript from a
    snapshot, and defaulting there would mark a message that arrived afterwards
    as observed without anything ever having read it.
    """
    if upto_message_id is None:
        upto_message_id = conn.execute(
            "SELECT MAX(id) FROM messages WHERE conversation_id = ?", (conversation_id,)
        ).fetchone()[0]
    conn.execute(
        "UPDATE conversations SET observed_at = ?, observed_upto_message_id = ? WHERE id = ?",
        (timestamp or now_utc(), upto_message_id, conversation_id),
    )
    conn.commit()


def list_unobserved(conn) -> list[dict[str, Any]]:
    """
    Conversations holding messages the Observer has not processed, with the
    high-water mark to resume from and a count of only the unprocessed ones.

    In normal operation this is empty: a disconnect runs the Observer straight
    away, and a clean shutdown persists the transcript to pending_observer. It
    fills only when the process died without either - `Stop-Process -Force`, a
    crash, a power cut - where the messages were already committed per turn but
    the extraction never happened. That failure was previously silent, which is
    the worst shape for it to take in a memory system: the conversation is
    visible in the sidebar, so nothing looks wrong, while none of it was
    learned from.

    The filter used to be `observed_at IS NULL`, which treated observation as a
    property of a whole conversation. It isn't - it happens per segment, and
    two ordinary flows produce a conversation that is marked observed and still
    carries turns that never were:

      - an idle timeout runs the Observer mid-connection, then the same
        connection goes on accepting turns
      - resuming a conversation from the sidebar adds turns to one that a
        previous disconnect already marked

    A kill in either state lost those turns silently, which is precisely the
    failure this function was written to end - just narrowed to the cases that
    had been observed once already. Comparing against the high-water mark
    catches them.

    The WHERE clause filters the joined message rows, so COUNT(m.id) is the
    number of UNOBSERVED messages, not the conversation's total - it is what
    the recovery log reports, and reporting the total would overstate what was
    actually recovered.

    Empty conversations are excluded via the JOIN - a row created for a
    connection that disconnected before sending anything has nothing to extract
    and would only produce an empty Observer pass.
    """
    rows = conn.execute(
        "SELECT c.id, c.project_id, c.created_at, c.updated_at, "
        "       c.observed_upto_message_id, COUNT(m.id) AS message_count "
        "FROM conversations c JOIN messages m ON m.conversation_id = c.id "
        # Three states, and the middle one is the compatibility case: a row
        # with observed_at set but no high-water mark predates the column and
        # is read as fully observed, never as fully unobserved.
        "WHERE (c.observed_upto_message_id IS NOT NULL AND m.id > c.observed_upto_message_id) "
        "   OR (c.observed_upto_message_id IS NULL AND c.observed_at IS NULL) "
        "GROUP BY c.id ORDER BY c.updated_at ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def conversation_exists(conn, conversation_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    return row is not None


def delete_conversation(conn, conversation_id: str) -> bool:
    cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    return cursor.rowcount > 0
