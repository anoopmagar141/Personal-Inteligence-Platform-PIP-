# PIP Core - the single daemon thread a WebSocket connection's database work
# runs on.
#
# Two properties, both load-bearing, neither offered together by
# ThreadPoolExecutor:
#
# ONE THREAD, so a connection stays pinned to it. sqlite3/sqlcipher3
# connections can only be used on the thread that created them, and this
# executor is where ws_chat opens its connection and every later call that
# touches it is dispatched. The crash that proved it is recorded in
# stream_pipeline_to_websocket's docstring: the default shared pool sent
# successive next() calls to different workers and Stage 8 died with "SQLite
# objects created in a thread can only be used in that same thread".
# ThreadPoolExecutor(max_workers=1) gave this much.
#
# A DAEMON THREAD, so abandoning work actually abandons it. This is the half
# that was missing, and it is not a tidiness point. ThreadPoolExecutor's
# workers are non-daemon, and TWO separate registries join every one of them
# before the interpreter may exit: concurrent.futures' own atexit hook
# (_threads_queues) and threading._shutdown (_shutdown_locks). Removing a
# thread from one still leaves the other holding it - verified on 3.12, both
# must go for the process to exit.
#
# So `executor.shutdown(wait=False)` abandons the FUTURE and not the THREAD.
# ws_chat's disconnect path stops waiting on a stuck conn.close() after 5s
# precisely so teardown cannot hang - and then handed the process a worker
# still inside a call that same code documents as "genuinely never completes".
# The server hid it: a process meant to keep running does not notice that it
# has become unable to stop. The test suite did not - a run reported every test
# passed and then sat for minutes without exiting, which reads as a hung test
# rather than a finished one, and behind a shell pipe printed nothing at all.
#
# stage_06_web_search.py hit this same wall from the other side and reached the
# same conclusion in its own comment ("A daemon thread specifically, not
# ThreadPoolExecutor ... measured, a test abandoned a search at 30s exactly as
# intended and then sat for five minutes waiting for the worker before it could
# exit"). That comment cites THIS path as the precedent it was following, which
# was true of the intent and false of the code. Now it is true of both.
#
# What a daemon worker costs: work still in flight when the interpreter exits
# is cut off rather than finished. That is the accepted posture here, not a new
# risk - ADR-033 already says shutdown cannot wait on slow work, and an
# interrupted write is the power-cut case SQLite's journal and
# session_lifecycle.recover_unobserved_conversations() are built for.

import logging
import queue
import threading
from concurrent.futures import Future
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class _WorkItem:
    """One submitted call and the Future reporting it. Mirrors CPython's."""

    __slots__ = ("future", "fn", "args", "kwargs")

    def __init__(self, future: Future, fn: Callable[..., Any], args: tuple, kwargs: dict):
        self.future = future
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self) -> None:
        # A caller that already cancelled gets nothing run on its behalf.
        if not self.future.set_running_or_notify_cancel():
            return
        try:
            result = self.fn(*self.args, **self.kwargs)
        except BaseException as exc:  # noqa: BLE001 - handed to the caller's Future
            self.future.set_exception(exc)
        else:
            self.future.set_result(result)


class PinnedExecutor:
    """
    A one-thread, daemon-backed executor with enough of ThreadPoolExecutor's
    surface for asyncio: loop.run_in_executor() calls submit() and wraps the
    concurrent.futures.Future it returns, and nothing else is used here.

    Deliberately NOT a ThreadPoolExecutor subclass. The behaviour that had to
    change is how its worker threads are created, which is exactly the part a
    subclass cannot reach without reimplementing _adjust_thread_count.
    """

    def __init__(self, name: str = "pip-connection"):
        self._queue: queue.SimpleQueue = queue.SimpleQueue()
        self._shutdown = False
        self._thread = threading.Thread(target=self._work, name=name, daemon=True)
        self._thread.start()

    def _work(self) -> None:
        while True:
            item: Optional[_WorkItem] = self._queue.get()
            if item is None:  # shutdown sentinel
                return
            item.run()
            # Dropped before the next get() blocks, so a completed call's
            # arguments - a whole conversation transcript, on this path - are
            # not held alive for as long as the connection stays idle.
            del item

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
        future: Future = Future()
        if self._shutdown:
            # Reported through the Future rather than raised, so a late
            # submission on a torn-down connection surfaces to whoever awaits
            # it instead of blowing up an unrelated caller mid-teardown.
            future.set_exception(RuntimeError("PinnedExecutor is shut down"))
            return future
        self._queue.put(_WorkItem(future, fn, args, kwargs))
        return future

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        """
        Stops accepting work and asks the worker to finish.

        wait=False returns immediately even if the worker is stuck inside a
        call that will never return - which is the entire point, and is safe
        here only because that thread is a daemon and so cannot hold the
        interpreter open. The sentinel is queued regardless: a worker that is
        merely busy still sees it and exits when it gets there.
        """
        self._shutdown = True
        self._queue.put(None)
        if wait:
            self._thread.join()

    @property
    def thread(self) -> threading.Thread:
        """The one worker. Exposed for tests asserting the pinning holds."""
        return self._thread
