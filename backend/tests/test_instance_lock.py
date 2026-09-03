import os
import subprocess
import sys
import time

import pytest

from backend.core import instance_lock


@pytest.fixture(autouse=True)
def isolated_lock(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_LOCK_PATH", str(tmp_path / "pip.lock"))
    return tmp_path / "pip.lock"


def test_acquire_creates_lock_file_with_own_pid(isolated_lock):
    instance_lock.acquire()
    assert isolated_lock.exists()
    assert int(isolated_lock.read_text()) == os.getpid()


def test_acquire_is_idempotent_for_the_same_process(isolated_lock):
    instance_lock.acquire()
    instance_lock.acquire()  # must not raise - same PID re-entering
    assert int(isolated_lock.read_text()) == os.getpid()


def test_acquire_raises_when_a_live_different_pid_holds_the_lock(isolated_lock):
    # A PID that's certainly alive but isn't ours - our own PID minus 0 would
    # be us, so fake a different-but-live pid via the current process's
    # parent, which is guaranteed to be alive while this test runs.
    other_pid = os.getppid()
    isolated_lock.write_text(str(other_pid))

    with pytest.raises(instance_lock.AlreadyRunningError, match=str(other_pid)):
        instance_lock.acquire()


def test_acquire_takes_over_a_stale_lock(isolated_lock):
    # A PID essentially guaranteed not to be running.
    dead_pid = 999999
    isolated_lock.write_text(str(dead_pid))

    instance_lock.acquire()  # must not raise
    assert int(isolated_lock.read_text()) == os.getpid()


def test_acquire_takes_over_a_corrupt_lock_file(isolated_lock):
    isolated_lock.write_text("not-a-pid")
    instance_lock.acquire()
    assert int(isolated_lock.read_text()) == os.getpid()


def test_release_removes_lock_owned_by_this_process(isolated_lock):
    instance_lock.acquire()
    instance_lock.release()
    assert not isolated_lock.exists()


def test_release_does_not_remove_a_lock_owned_by_another_process(isolated_lock):
    other_pid = os.getppid()
    isolated_lock.write_text(str(other_pid))

    instance_lock.release()
    assert isolated_lock.exists()
    assert int(isolated_lock.read_text()) == other_pid


def test_release_without_a_lock_file_is_a_noop(isolated_lock):
    instance_lock.release()  # must not raise
    assert not isolated_lock.exists()


# ---------------------------------------------------------------------------
# A killed process is not a running one
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="the defect is Windows-specific")
def test_a_terminated_process_is_not_reported_as_running():
    """
    Windows keeps the process OBJECT alive while anyone holds a handle to it, so
    OpenProcess() succeeds long after the process has exited. _pid_is_running()
    used to take that as proof of life.

    The consequence was a lock that could never go stale on this platform: kill
    the backend and every check afterwards read the dead pid as live, so the
    scripts refused to run and acquire()'s stale-lock takeover - the branch that
    exists because this project leaves locks around - was unreachable.

    Popen deliberately keeps the handle (no wait/poll before the assertion),
    because that is the situation PowerShell's Stop-Process leaves behind.
    """
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        assert instance_lock._pid_is_running(child.pid), "the child should start alive"

        child.kill()
        time.sleep(1.0)

        assert not instance_lock._pid_is_running(child.pid), (
            "a killed process was reported as running - the handle held by Popen "
            "is keeping the process object addressable, which is not the same as "
            "the process being alive"
        )
    finally:
        child.kill()
        child.wait()


def test_a_lock_left_by_a_killed_process_is_taken_over(tmp_path, monkeypatch):
    """
    The whole point of the fix, at the level the user meets it: PIP has to be
    able to start again after a hard kill, without anyone deleting a file by
    hand.
    """
    lock = tmp_path / "pip.lock"
    monkeypatch.setenv("PIP_LOCK_PATH", str(lock))

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    lock.write_text(str(child.pid), encoding="utf-8")
    child.kill()
    time.sleep(1.0)

    try:
        instance_lock.acquire()
    finally:
        child.wait()

    assert lock.read_text(encoding="utf-8").strip() == str(os.getpid()), (
        "the stale lock should have been taken over"
    )


def test_a_lock_held_by_a_live_process_is_still_refused(tmp_path, monkeypatch):
    """
    The fix must not swing the other way. Single-instance is the property; a
    liveness check that read everything as dead would trade one broken lock for
    a missing one.
    """
    lock = tmp_path / "pip.lock"
    monkeypatch.setenv("PIP_LOCK_PATH", str(lock))

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    lock.write_text(str(child.pid), encoding="utf-8")

    try:
        with pytest.raises(instance_lock.AlreadyRunningError):
            instance_lock.acquire()
    finally:
        child.kill()
        child.wait()
