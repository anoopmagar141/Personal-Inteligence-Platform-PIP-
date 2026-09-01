"""
The executor a WebSocket connection's database work runs on.

The regression these guard is not a wrong answer - it is a process that has
finished its work and cannot exit. Behind a shell pipe that prints nothing
until the process ends, it is indistinguishable from a hung test, which is how
it was first misread here.
"""

import subprocess
import sys
import threading
import time

import pytest

from backend.core.pinned_executor import PinnedExecutor


@pytest.fixture
def executor():
    ex = PinnedExecutor(name="test-pinned")
    yield ex
    ex.shutdown(wait=False)


def test_the_worker_is_a_daemon_thread(executor):
    """
    The whole reason this class exists rather than
    ThreadPoolExecutor(max_workers=1). A non-daemon worker is joined by the
    interpreter before it may exit, so a call abandoned by shutdown(wait=False)
    still holds the process open.
    """
    assert executor.thread.daemon is True


def test_every_call_lands_on_the_same_thread(executor):
    """
    The other load-bearing property: conn is a SQLite/SQLCipher connection
    pinned to the thread that created it, so a second worker would not be a
    speed-up, it would be the "SQLite objects created in a thread can only be
    used in that same thread" crash recorded in server.py.
    """
    idents = [executor.submit(threading.get_ident).result(timeout=5) for _ in range(25)]

    assert len(set(idents)) == 1
    assert idents[0] == executor.thread.ident


def test_a_result_comes_back_through_the_future(executor):
    assert executor.submit(lambda a, b: a + b, 2, 3).result(timeout=5) == 5


def test_a_raising_call_reports_through_the_future_not_the_worker(executor):
    """
    The worker must survive a failing call - it is the connection's only
    thread, so losing it would strand every later call on that connection.
    """
    future = executor.submit(lambda: 1 / 0)

    with pytest.raises(ZeroDivisionError):
        future.result(timeout=5)
    assert executor.thread.is_alive()
    assert executor.submit(lambda: "still here").result(timeout=5) == "still here"


def test_submitting_after_shutdown_fails_the_future_rather_than_the_caller():
    """
    Reported through the Future, so a late submission during teardown surfaces
    to whoever awaits it instead of raising inside unrelated cleanup.
    """
    ex = PinnedExecutor(name="test-late-submit")
    ex.shutdown(wait=False)

    with pytest.raises(RuntimeError):
        ex.submit(lambda: "too late").result(timeout=5)


def test_shutdown_does_not_wait_for_a_call_that_never_returns():
    """
    conn.close() on this path is documented as able to never complete. Teardown
    stops waiting on it after 5s; shutdown must not then reintroduce the wait.
    """
    ex = PinnedExecutor(name="test-wedged")
    never = threading.Event()
    ex.submit(never.wait)
    time.sleep(0.05)  # let the worker pick it up

    started = time.monotonic()
    ex.shutdown(wait=False)
    elapsed = time.monotonic() - started

    assert elapsed < 1.0, "shutdown(wait=False) waited for the wedged call"
    never.set()


# The measurement, as a test. A subprocess because the claim is about
# interpreter exit, which cannot be asserted from inside the interpreter making
# it - and because the failure mode is an infinite hang, which only a timeout
# on someone else's process can turn into a verdict.
_EXIT_PROBE = """
import threading
{setup}
never = threading.Event()
ex.submit(never.wait)
ex.shutdown(wait=False)
print("work abandoned, leaving __main__", flush=True)
"""

_PINNED_SETUP = """
import sys
sys.path.insert(0, {root!r})
from backend.core.pinned_executor import PinnedExecutor
ex = PinnedExecutor()
"""

_POOL_SETUP = """
import concurrent.futures
ex = concurrent.futures.ThreadPoolExecutor(max_workers=1)
"""


def _exits_cleanly(setup: str, root: str) -> bool:
    try:
        subprocess.run(
            [sys.executable, "-c", _EXIT_PROBE.format(setup=setup)],
            # A clean exit is immediate; the failure is an unbounded hang.
            # 8s separates them with room to spare on a loaded machine.
            timeout=8, capture_output=True,
        )
        return True
    except subprocess.TimeoutExpired:
        return False


def test_an_abandoned_call_cannot_hold_the_interpreter_open(pytestconfig):
    """
    The bug, end to end: submit something that never returns, abandon it, and
    the process must still be able to exit.
    """
    root = str(pytestconfig.rootpath)
    assert _exits_cleanly(_PINNED_SETUP.format(root=root), root), (
        "the interpreter could not exit with an abandoned call outstanding - "
        "the worker is holding it open, which is the entire bug this class fixes"
    )


def test_the_thread_pool_this_replaced_really_did_hold_it_open(pytestconfig):
    """
    Guards the guard. If a future Python made ThreadPoolExecutor's workers
    daemons, the test above would pass for a reason unrelated to this class and
    quietly stop testing anything - this fails first and says so.
    """
    root = str(pytestconfig.rootpath)
    assert not _exits_cleanly(_POOL_SETUP, root), (
        "ThreadPoolExecutor no longer blocks interpreter exit on an abandoned "
        "call. PinnedExecutor may no longer be needed - check before deleting it."
    )
