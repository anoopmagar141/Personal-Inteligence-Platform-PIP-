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


# How much of the previous chat's not-yet-summarised end a new chat is shown
# (BLUEPRINT #13 part 3): the last few messages, each cut short, inside the
# same small budget as the record itself.
UNSUMMARISED_MESSAGES = 4
UNSUMMARISED_WORDS_PER_MESSAGE = 40


def unsummarised_tail(conn, *, exclude: Optional[str], project_id: Optional[str]) -> Optional[dict[str, Any]]:
    """
    The end of the previous chat that its Observer pass has not summarised yet
    (BLUEPRINT #13 part 3), or None.

    A chat's record is written when its Observer pass runs, after the chat
    ends; a new chat opened before that (the usual case: the user leaves one
    chat and opens the next) used to be given an older note, or none. So the
    new chat is also shown the previous chat's messages after its last pass,
    labelled as not yet summarised: the user's own words, not a summary.

    The previous chat is the newest other chat in the same project, else the
    newest other chat of all (as the record's own fallback), counting only
    chats with messages: an empty one (created, nothing said yet) has no end
    to show and must not hide the chat before it. Only messages after its
    observed_at count; a chat whose pass already ran shows nothing here,
    since its record covers it.
    """
    has_messages = "EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id = conversations.id)"
    tries = []
    if project_id:
        tries.append((f"SELECT id, observed_at FROM conversations WHERE project_id = ? AND id != ? AND {has_messages} "
                      "ORDER BY updated_at DESC, rowid DESC LIMIT 1", (project_id, exclude or ""),
                      "the last chat in this project"))
    tries.append((f"SELECT id, observed_at FROM conversations WHERE id != ? AND {has_messages} "
                  "ORDER BY updated_at DESC, rowid DESC LIMIT 1",
                  (exclude or "",), "your last chat"))
    for sql, params, scope in tries:
        previous = conn.execute(sql, params).fetchone()
        if previous is None:
            continue
        rows = conn.execute(
            "SELECT id, role, content, created_at FROM messages WHERE conversation_id = ? "
            "AND (? IS NULL OR created_at > ?) ORDER BY id DESC LIMIT ?",
            (previous["id"], previous["observed_at"], previous["observed_at"], UNSUMMARISED_MESSAGES),
        ).fetchall()
        if not rows:
            return None
        rows = list(reversed(rows))
        return {
            "conversation_id": previous["id"],
            "scope": scope,
            "last_message_id": rows[-1]["id"],
            "date": rows[-1]["created_at"],
            "messages": [
                {"role": r["role"], "content": _first_words(r["content"], UNSUMMARISED_WORDS_PER_MESSAGE)}
                for r in rows
            ],
        }
    return None


def _first_words(text: str, limit: int) -> str:
    words = str(text).split()
    return " ".join(words[:limit]) + (" ..." if len(words) > limit else "")


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


def project_of(conn, conversation_id: Optional[str]) -> Optional[str]:
    """
    The project a chat belongs to, or None (no chat, a chat with no project,
    or one that no longer exists). The one source for "the chat's project"
    when the Observer learns from a chat (BLUEPRINT C-14): the row is created
    with the project the app sends, so every path that knows the chat's id -
    the end of a chat, the shutdown queue, crash recovery - reads the same.
    """
    if not conversation_id:
        return None
    row = conn.execute("SELECT project_id FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    return row["project_id"] if row else None


def conversation_exists(conn, conversation_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    return row is not None


def delete_conversation(conn, conversation_id: str) -> bool:
    cursor = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    return cursor.rowcount > 0
