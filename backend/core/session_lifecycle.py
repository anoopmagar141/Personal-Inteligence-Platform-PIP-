# PIP Core - Session Lifecycle (idle-timeout / disconnect / process-exit triggering)
#
# Rule 3 (Part 12.1): Observer runs at session end only - 10-min idle OR process
# exit, never per-message. In a WS server, "session" = one WebSocket connection's
# conversation; "process exit" from the original single-session CLI-era spec
# doesn't map 1:1 onto a multi-connection server, so this module treats three
# triggers differently, on purpose:
#
#   - idle timeout within a connection -> run Observer now (there's time, the
#     connection just isn't sending anything, nothing else is waiting on it)
#   - normal disconnect (client closed, network dropped) -> run Observer now,
#     same reasoning - this one connection ending doesn't block anything else
#   - whole-server shutdown (SIGINT/SIGTERM) -> too slow to run a ~130s-class
#     Observer pass synchronously for every currently-open connection
#     (ADR-033 condition 2 exists specifically for this). Persist each
#     connection's transcript to pending_observer instead and exit promptly;
#     drain_pending_on_startup() processes them for real on the next launch.

import asyncio
import logging
from typing import Any, Optional

from backend.core import trace
from backend.memory import conversation_store, pending_observer
from backend.providers.base_provider import BaseLLMProvider
from backend.stages import stage_11_observer as observer

logger = logging.getLogger(__name__)


class SessionRegistry:
    """
    Tracks currently-open WS sessions so a whole-server shutdown can find every
    connection's in-progress conversation_history and persist it, rather than
    try to run Observer synchronously for each one.

    Not a distributed-systems concern - this is a single local process serving
    a single user. An asyncio.Lock (all access happens from coroutines on the
    same event loop) is sufficient; no cross-process coordination is needed.
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self._sessions: dict[int, dict[str, Any]] = {}
        self.shutting_down = False

    async def register(self, session_id: int, conn, executor, conversation_history: list,
                       observed_upto_index: int = 0) -> dict[str, Any]:
        """
        Returns the session record so the caller can keep observed_upto_index
        current. It has to be mutated through this dict rather than tracked as
        a local int in the handler: shutdown reads these records, and an int
        copied in at registration would still say 0 after an idle-timeout
        Observer run had already retired half the transcript.
        """
        async with self._lock:
            record = {
                "conn": conn,
                "executor": executor,
                "conversation_history": conversation_history,
                # Index into conversation_history where the turns the Observer
                # has NOT seen begin. Non-zero from the start for a resumed
                # conversation, whose earlier turns were observed on the
                # disconnect that ended the previous session.
                "observed_upto_index": observed_upto_index,
            }
            self._sessions[session_id] = record
            return record

    async def unregister(self, session_id: int) -> None:
        async with self._lock:
            self._sessions.pop(session_id, None)

    async def snapshot(self) -> list[dict[str, Any]]:
        async with self._lock:
            return list(self._sessions.values())


def format_transcript(conversation_history: list[dict[str, str]]) -> str:
    """Plain User:/Assistant: transcript, matching Part 12.2's extraction prompt example."""
    lines = []
    for message in conversation_history:
        role = "User" if message.get("role") == "user" else "Assistant"
        lines.append(f"{role}: {message.get('content', '')}")
    return "\n".join(lines)


async def run_observer_now(
    loop,
    executor,
    conn,
    conversation_history: list[dict[str, str]],
    provider: BaseLLMProvider,
    project_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Runs Stage 11's full session-end flow on the connection's own dedicated
    executor - conn is thread-pinned to it (see backend/api/server.py's WS
    thread-safety note: SQLite/SQLCipher connections can only be used on the
    thread that created them). Used for idle-timeout and normal-disconnect
    triggers, where there's time to actually run the LLM pass. Never used
    during a whole-server shutdown - see enqueue_for_shutdown().

    The snapshot itself now lives in the same encrypted DB conn already points
    at (session_snapshot table, security review fix - it used to be a plain
    data/session_snapshot.json file), which incidentally also retired a real
    bug this docstring used to warn about: run_session_end()'s old
    snapshot_path parameter had a default bound at function-definition time (a
    plain Python default-argument gotcha), so monkeypatching the module
    constant in a test silently did nothing - the call still wrote to the real
    path baked in at import time. There's no path default left to bind wrong
    at all now; conn is the only thing threaded through, and it was already
    being passed explicitly everywhere this class of bug could have hit.

    Logs to trace_log under its own trace_id - Observer session-end runs
    aren't tied to any single message's trace_id, but need their own
    visibility. Found live: without this, there was no way to tell whether a
    disconnect had actually triggered Observer, or why a run produced nothing.
    """
    trace_id = trace.generate_trace_id()
    trace.stage_log(trace_id, "stage_11_observer", "ok", f"session-end run starting, {len(conversation_history)} messages")
    transcript = format_transcript(conversation_history)

    def _extract_and_mark() -> dict[str, Any]:
        # Marking happens inside this same executor call rather than as a
        # second `await run_in_executor(...)` at the call site. Both callers
        # are in ws_chat's disconnect/idle paths, and the disconnect path is
        # documented there as able to leave a fresh executor submission never
        # dequeued once the connection has done any DB writes - adding another
        # unbounded await into it would be putting a new call in the one place
        # already known to wedge. One round trip avoids that entirely.
        #
        # After run_session_end, so a raised extraction leaves observed_at NULL
        # and the conversation is retried by startup recovery rather than being
        # written off as handled.
        outcome = observer.run_session_end(conn, transcript, provider, project_id)
        if conversation_id:
            conversation_store.mark_observed(conn, conversation_id)
        return outcome

    try:
        result = await loop.run_in_executor(executor, _extract_and_mark)
    except Exception as e:
        trace.stage_log(trace_id, "stage_11_observer", "error", "session-end run raised", error_detail=str(e))
        raise
    trace.stage_log(
        trace_id, "stage_11_observer", "ok",
        f"{len(result['memory_results'])} memory candidates, {len(result['decision_results'])} decision candidates",
    )
    return result


async def enqueue_for_shutdown(loop, session: dict[str, Any]) -> None:
    """
    Persists one session's transcript to pending_observer instead of running
    Observer synchronously - shutdown cannot wait for a ~130s-class pass per
    open connection (ADR-033 condition 2). Drained for real on next startup.
    No-ops if the session has no unprocessed conversation yet.

    Only the turns past observed_upto_index are persisted. Sending the whole
    list would re-extract the replayed history of a resumed conversation, and
    would re-extract everything before an idle timeout that had already run -
    a full LLM pass on the next start to re-derive memory that already exists.
    """
    history = session["conversation_history"][session.get("observed_upto_index", 0):]
    if not history:
        return
    transcript = format_transcript(history)
    await loop.run_in_executor(
        session["executor"], pending_observer.enqueue, session["conn"], transcript
    )


def recover_unobserved_conversations(conn) -> list[str]:
    """
    Finds conversations whose messages were committed but never went through the
    Observer, and queues them for the startup drain. Returns the ids recovered.

    Closes the third failure mode this module did not previously handle. A
    disconnect runs the Observer immediately; a clean shutdown persists the
    transcript to pending_observer; but a process killed outright - taskkill,
    `Stop-Process -Force`, a crash, a power cut - runs neither, because both
    paths live in code that never gets to execute. conversation_history lives
    only in the WS handler's memory, so it dies with the process.

    Found live: a real session was killed mid-test, and the conversation sat in
    the sidebar looking perfectly normal while none of it had been learned
    from. Silent non-learning is the worst possible shape for this failure in a
    system whose entire purpose is remembering - a crash that loses data is at
    least visible.

    Recovery is possible at all because messages are committed per turn (see
    ws_chat), so the transcript can be rebuilt from the database rather than
    from the memory that died. This reconstructs it and hands it to
    pending_observer, deliberately reusing the queue the shutdown path already
    fills rather than adding a second way to process a session: that queue
    already has retry-on-failure, keeps failed entries instead of dropping
    them, and is drained by machinery that exists and is tested.

    Marks each conversation observed at enqueue time, not after the LLM pass.
    Once the transcript is in pending_observer its recovery is that queue's
    responsibility - a row that fails is retained and retried on the next
    start, so leaving the high-water mark where it was would queue the same
    conversation twice on every subsequent boot.

    Only the messages past the high-water mark are rebuilt, not the whole
    conversation. A conversation the Observer already handled a segment of -
    one resumed from the sidebar, or one that outlived an idle timeout - would
    otherwise be re-extracted from turn one, burning a full LLM pass to
    re-derive memory that already exists.
    """
    unobserved = conversation_store.list_unobserved(conn)
    recovered = []
    for conversation in unobserved:
        messages = conversation_store.get_messages_after(
            conn, conversation["id"], conversation["observed_upto_message_id"]
        )
        if not messages:
            continue
        history = [{"role": m["role"], "content": m["content"]} for m in messages]
        pending_observer.enqueue(conn, format_transcript(history))
        # The id actually read, not whatever the maximum happens to be by the
        # time this line runs - marking past the end of the snapshot would
        # retire a message nothing ever extracted from.
        conversation_store.mark_observed(
            conn, conversation["id"], upto_message_id=messages[-1]["id"]
        )
        recovered.append(conversation["id"])
        logger.info(
            f"Recovered {len(messages)} unobserved message(s) from a conversation "
            f"left by an unclean shutdown; queued for the Observer."
        )
    return recovered


def drain_pending_on_startup(conn, provider: BaseLLMProvider) -> dict[str, list]:
    """
    Runs before the app accepts real traffic (Part 7: drain before Stage 0).
    Processes any pending_observer rows a previous shutdown persisted instead
    of losing that session's learning outright.
    """

    def observer_runner(transcript: str) -> None:
        observer.run_session_end(conn, transcript, provider)

    return pending_observer.drain(conn, observer_runner)
