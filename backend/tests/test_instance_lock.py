import os

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
