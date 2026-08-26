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


def mark_observed(conn, conversation_id: str, *, timestamp: str | None = None) -> None:
    """
    Records that the Observer has taken a pass over this conversation, so
    startup recovery does not process it a second time.
    """
    conn.execute(
        "UPDATE conversations SET observed_at = ? WHERE id = ?",
        (timestamp or now_utc(), conversation_id),
    )
    conn.commit()


def list_unobserved(conn) -> list[dict[str, Any]]:
    """
    Conversations that hold messages but have never been through the Observer.

    In normal operation this is empty: a disconnect runs the Observer straight
    away, and a clean shutdown persists the transcript to pending_observer. It
    fills only when the process died without either - `Stop-Process -Force`, a
    crash, a power cut - where the messages were already committed per turn but
    the extraction never happened. That failure was previously silent, which is
    the worst shape for it to take in a memory system: the conversation is
    visible in the sidebar, so nothing looks wrong, while none of it was
    learned from.

    Empty conversations are excluded via the JOIN - a row created for a
    connection that disconnected before sending anything has nothing to extract
    and would only produce an empty Observer pass.
    """
    rows = conn.execute(
        "SELECT c.id, c.project_id, c.created_at, c.updated_at, COUNT(m.id) AS message_count "
        "FROM conversations c JOIN messages m ON m.conversation_id = c.id "
        "WHERE c.observed_at IS NULL "
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
