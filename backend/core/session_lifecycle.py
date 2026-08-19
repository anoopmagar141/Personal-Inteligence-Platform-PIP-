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
from backend.memory import pending_observer
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

    async def register(self, session_id: int, conn, executor, conversation_history: list) -> None:
        async with self._lock:
            self._sessions[session_id] = {
                "conn": conn,
                "executor": executor,
                "conversation_history": conversation_history,
            }

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
    try:
        result = await loop.run_in_executor(
            executor, lambda: observer.run_session_end(conn, transcript, provider, project_id)
        )
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
    """
    history = session["conversation_history"]
    if not history:
        return
    transcript = format_transcript(history)
    await loop.run_in_executor(
        session["executor"], pending_observer.enqueue, session["conn"], transcript
    )


def drain_pending_on_startup(conn, provider: BaseLLMProvider) -> dict[str, list]:
    """
    Runs before the app accepts real traffic (Part 7: drain before Stage 0).
    Processes any pending_observer rows a previous shutdown persisted instead
    of losing that session's learning outright.
    """

    def observer_runner(transcript: str) -> None:
        observer.run_session_end(conn, transcript, provider)

    return pending_observer.drain(conn, observer_runner)
