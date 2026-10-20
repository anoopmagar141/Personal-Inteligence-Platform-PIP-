import json
import logging
from typing import List, Optional, TypedDict

from backend.core.types import now_utc

logger = logging.getLogger(__name__)


class SessionSnapshot(TypedDict):
    topic: str
    open_problems: List[str]
    last_decisions: List[str]
    suggested_next_step: str
    snapshot_date: str


def load_snapshot(conn) -> Optional[SessionSnapshot]:
    """
    The newest chat record (BLUEPRINT #13): what the next chat is shown as
    "where we left off". Until #13 this read the singleton session_snapshot
    row, which held only the last chat's summary; the newest record is that
    same summary, so the next chat sees what it saw before, while every other
    chat's record is kept instead of overwritten.

    Moved off a plain data/session_snapshot.json file before that (security
    review finding: sensitive extracted context sitting in plaintext outside
    the SQLCipher boundary).

    Failure mode: fail-open. No record yet (first-ever run, or Observer hasn't
    completed a session yet) or an unexpected read error both return None -
    missing a snapshot only degrades conversational continuity, it never
    violates a privacy or integrity guarantee, same reasoning as Stage 0's own
    fail-open policy. The table's NOT NULL columns make a shape-invalid row
    structurally impossible to write in the first place.
    """
    try:
        row = conn.execute(
            "SELECT topic, open_problems, last_decisions, suggested_next_step, record_date "
            "FROM chat_records ORDER BY record_date DESC, id DESC LIMIT 1"
        ).fetchone()
    except Exception as e:
        logger.error(f"Unexpected error loading the chat record: {e}. Failing open to None.")
        return None

    if row is None:
        return None

    return {
        "topic": row["topic"],
        "open_problems": json.loads(row["open_problems"]),
        "last_decisions": json.loads(row["last_decisions"]),
        "suggested_next_step": row["suggested_next_step"],
        "snapshot_date": row["record_date"],
    }


# Which record a chat is given, in the order they are tried, and how the
# prompt names it (BLUEPRINT #13).
SCOPE_THIS_CHAT = "this chat, earlier"
SCOPE_PROJECT = "the last chat in this project"
SCOPE_NEWEST = "your last chat"


def load_record_for(
    conn, *, conversation_id: Optional[str] = None, project_id: Optional[str] = None,
) -> Optional[dict]:
    """
    The record a chat is shown as "where we left off" (BLUEPRINT #13): this
    chat's own (a resumed chat), else its project's latest, else the newest
    record of all. Before #13 every chat in every project got the one note the
    last chat had written, so a chat in one project opened on another
    project's last conversation.

    The newest record of all is the last resort, kept on purpose: a chat with
    no project, or in a project with no record yet, still gets the thread the
    user was last on, as before. The prompt names which it is and when it was
    written (record_scope, snapshot_date), so a record from elsewhere is not
    presented as this chat's own.

    Same shape as load_snapshot() plus record_id (part of the answer cache
    key, since two chats can now be given different records), record_scope
    and source. Fails open to None, as load_snapshot() does.
    """
    columns = "id, topic, open_problems, last_decisions, suggested_next_step, record_date, source"
    tries = []
    if conversation_id:
        tries.append((SCOPE_THIS_CHAT, f"SELECT {columns} FROM chat_records WHERE conversation_id = ?",
                      (conversation_id,)))
    if project_id:
        tries.append((SCOPE_PROJECT, f"SELECT {columns} FROM chat_records WHERE project_id = ? "
                                      "ORDER BY record_date DESC, id DESC LIMIT 1", (project_id,)))
    tries.append((SCOPE_NEWEST, f"SELECT {columns} FROM chat_records ORDER BY record_date DESC, id DESC LIMIT 1",
                  ()))
    try:
        for scope, sql, params in tries:
            row = conn.execute(sql, params).fetchone()
            if row is not None:
                return {
                    "record_id": row["id"],
                    "record_scope": scope,
                    "source": row["source"],
                    "topic": row["topic"],
                    "open_problems": json.loads(row["open_problems"]),
                    "last_decisions": json.loads(row["last_decisions"]),
                    "suggested_next_step": row["suggested_next_step"],
                    "snapshot_date": row["record_date"],
                }
    except Exception as e:
        logger.error(f"Unexpected error choosing the chat record: {e}. Failing open to None.")
    return None


def delete_chat_record(conn, conversation_id: str) -> bool:
    """
    Removes one chat's record, and only that chat's (BLUEPRINT #13).

    Replaces clear_snapshot(), which removed THE note whichever chat had
    written it: deleting any chat cost the continuity of whichever chat had
    ended last (P-2, FREEZE_LIST §7.53). A record names its chat, so deleting
    a chat now takes its own summary and leaves every other chat's. The
    conversations foreign key cascades the same delete; this is the explicit
    form callers use, so the order of a delete stays readable where it is
    written.

    Deliberately in this module rather than a caller issuing its own DELETE:
    it is the sole owner of chat_records. Returns True if a record was
    removed, False if the chat had none.
    """
    cur = conn.execute("DELETE FROM chat_records WHERE conversation_id = ?", (conversation_id,))
    conn.commit()
    return cur.rowcount > 0


def write_snapshot(
    conn,
    snapshot: SessionSnapshot,
    *,
    conversation_id: Optional[str] = None,
    project_id: Optional[str] = None,
) -> None:
    """
    Writes a chat's record (BLUEPRINT #13). Called by the Observer (Stage 11)
    at the end of a chat, with the chat and its project.

    One record per chat: a chat's later pass (a resumed chat) replaces its own
    record and no other, where the singleton it replaces was overwritten by
    every chat. A pass given no chat adds a record of its own rather than
    replacing anything, since nothing says which earlier record it would be.
    source is 'observer': the model wrote it, so it can be wrong. A record the
    user corrected is left as it is: the user's word stands over the model's,
    as user corrections do everywhere else in PIP, until they clear it.

    Raises if the chat no longer exists (the conversations foreign key): a
    chat deleted while its pass ran gets no record. The Observer isolates this
    write, so the session's candidates are unaffected.
    """
    values = (
        project_id,
        snapshot["topic"],
        json.dumps(snapshot["open_problems"]),
        json.dumps(snapshot["last_decisions"]),
        snapshot["suggested_next_step"],
        snapshot["snapshot_date"],
    )
    if conversation_id is None:
        conn.execute(
            """
            INSERT INTO chat_records (
                project_id, topic, open_problems, last_decisions, suggested_next_step, record_date, source
            )
            VALUES (?, ?, ?, ?, ?, ?, 'observer')
            """,
            values,
        )
    else:
        conn.execute(
            """
            INSERT INTO chat_records (
                conversation_id, project_id, topic, open_problems, last_decisions, suggested_next_step,
                record_date, source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'observer')
            ON CONFLICT(conversation_id) DO UPDATE SET
                project_id = excluded.project_id,
                topic = excluded.topic,
                open_problems = excluded.open_problems,
                last_decisions = excluded.last_decisions,
                suggested_next_step = excluded.suggested_next_step,
                record_date = excluded.record_date,
                source = excluded.source
            WHERE chat_records.source != 'user'
            """,
            (conversation_id, *values),
        )
    conn.commit()


# What a correction may hold: a record is a short summary, not a document.
_MAX_TOPIC = 300
_MAX_LINE = 300
_MAX_ITEMS = 20


def get_chat_record(conn, conversation_id: str) -> Optional[dict]:
    """A chat's own record (BLUEPRINT #13 part 4), for the user to read; None if it has none."""
    row = conn.execute(
        "SELECT topic, open_problems, last_decisions, suggested_next_step, record_date, source "
        "FROM chat_records WHERE conversation_id = ?",
        (conversation_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "topic": row["topic"],
        "open_problems": json.loads(row["open_problems"]),
        "last_decisions": json.loads(row["last_decisions"]),
        "suggested_next_step": row["suggested_next_step"],
        "record_date": row["record_date"],
        "source": row["source"],
    }


def correct_chat_record(conn, conversation_id: str, fields: dict, *, project_id: Optional[str]) -> dict:
    """
    The user's own version of a chat's record (BLUEPRINT #13 part 4). The
    Observer, a model, writes a record when a chat ends and can be wrong; this
    is how the user puts it right. source becomes 'user', which the prompt
    says and the Observer's later passes leave alone.

    Raises ValueError with the sentence the user is shown for anything that is
    not a record: a topic that is empty or too long, problems or decisions
    that are not a list of short texts, a next step that is not a short text.
    """
    topic = fields.get("topic")
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("A chat record needs a topic.")
    if len(topic) > _MAX_TOPIC:
        raise ValueError(f"A chat record's topic can be at most {_MAX_TOPIC} characters.")
    lists = {}
    for name, label in (("open_problems", "open problems"), ("last_decisions", "decisions")):
        items = fields.get(name, [])
        if not isinstance(items, list) or not all(isinstance(i, str) for i in items):
            raise ValueError(f"A chat record's {label} must be a list of texts.")
        if len(items) > _MAX_ITEMS or any(len(i) > _MAX_LINE for i in items):
            raise ValueError(f"A chat record holds at most {_MAX_ITEMS} {label}, each at most {_MAX_LINE} characters.")
        lists[name] = [i.strip() for i in items if i.strip()]
    step = fields.get("suggested_next_step", "")
    if not isinstance(step, str) or len(step) > _MAX_LINE:
        raise ValueError(f"A chat record's next step must be a text of at most {_MAX_LINE} characters.")

    conn.execute(
        """
        INSERT INTO chat_records (
            conversation_id, project_id, topic, open_problems, last_decisions, suggested_next_step, record_date, source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'user')
        ON CONFLICT(conversation_id) DO UPDATE SET
            project_id = excluded.project_id,
            topic = excluded.topic,
            open_problems = excluded.open_problems,
            last_decisions = excluded.last_decisions,
            suggested_next_step = excluded.suggested_next_step,
            record_date = excluded.record_date,
            source = excluded.source
        """,
        (conversation_id, project_id, topic.strip(), json.dumps(lists["open_problems"]),
         json.dumps(lists["last_decisions"]), step.strip(), now_utc()),
    )
    conn.commit()
    return get_chat_record(conn, conversation_id)
