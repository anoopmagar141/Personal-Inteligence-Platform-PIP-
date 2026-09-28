"""
The instance lock must name a process, not a number (docs/FREEZE_LIST.md §7.4).

A PID names a process only for its lifetime. The lock stored the bare PID, so
once the PIP that wrote it was gone and the number was handed to something
else, every gate read "PIP is running": the backend refused to start, restore
and merge refused to run, and the launcher's stale-lock cleanup kept the lock -
all three asking the same question with the same missing information.

PID reuse is not waited for (§6: not controllable). A real process takes the
lock and exits, and the PID in the file is then pointed at a live process that
is not PIP, leaving everything else the holder wrote untouched - the exact
state reuse produces. The control is a real holder that stays alive, which
every gate must still refuse: single-instance is the property this protects,
and a fix that read everything as stale would trade one broken lock for a
missing one.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.core import instance_lock

REPO = Path(__file__).resolve().parents[2]

_TAKE_LOCK = (
    "import sys, time\n"
    "from backend.core import instance_lock\n"
    "instance_lock.acquire()\n"
    "print('held', flush=True)\n"
    "if sys.argv[1] == 'stay':\n"
    "    time.sleep(60)\n"
)


@pytest.fixture
def lock(tmp_path, monkeypatch):
    path = tmp_path / "pip.lock"
    monkeypatch.setenv("PIP_LOCK_PATH", str(path))
    return path


def _holder(mode: str) -> subprocess.Popen:
    """A separate process that takes the lock the real way."""
    env = dict(os.environ, PYTHONPATH=str(REPO))
    child = subprocess.Popen(
        [sys.executable, "-c", _TAKE_LOCK, mode], cwd=REPO, env=env, stdout=subprocess.PIPE, text=True
    )
    assert child.stdout.readline().strip() == "held"
    return child


def _not_pip() -> subprocess.Popen:
    return subprocess.Popen(["ping", "-n", "60", "127.0.0.1"], stdout=subprocess.DEVNULL)


def _restore_refuses() -> bool:
    spec = importlib.util.spec_from_file_location("restore_backup", REPO / "scripts" / "restore_backup.py")
    restore = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(REPO / "scripts"))
    try:
        spec.loader.exec_module(restore)
        try:
            restore.refuse_if_pip_is_running()
        except SystemExit:
            return True
        return False
    finally:
        sys.path.remove(str(REPO / "scripts"))


def _launcher_keeps(lock: Path) -> bool:
    """Runs launch_pip.ps1's own stale-lock block, cut from the script itself."""
    script = (REPO / "scripts" / "launch_pip.ps1").read_text(encoding="utf-8")
    start = script.index("$lockFile = Join-Path $dataDir")
    end = script.index("# Ollama, in every state")
    block = script[start:end]
    wrapper = (
        f"$dataDir = '{lock.parent}'\n$root = '{REPO}'\n$pipPython = '{sys.executable}'\n"
        f"function Write-Phase($phase, $detail) {{ }}\n{block}"
    )
    result = subprocess.run(["powershell", "-NoProfile", "-Command", wrapper], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return lock.exists()


def _repoint_pid(lock: Path, pid: int) -> None:
    fields = lock.read_text(encoding="utf-8").split()
    lock.write_text(" ".join([str(pid)] + fields[1:]), encoding="utf-8")


@pytest.fixture
def reused(lock):
    """A lock taken by a real process that has since exited, whose PID now
    names a live process that is not PIP."""
    _holder("exit").wait()
    other = _not_pip()
    _repoint_pid(lock, other.pid)
    yield lock
    other.kill()
    other.wait()


def test_the_launcher_clears_a_lock_whose_pid_now_names_another_process(reused):
    assert not _launcher_keeps(reused), "the launcher kept a lock whose PID belongs to another process"


def test_restore_runs_when_the_locks_pid_now_names_another_process(reused):
    assert not _restore_refuses(), "restore refused to run because a process that is not PIP was alive"


def test_the_backend_starts_when_the_locks_pid_now_names_another_process(reused):
    try:
        instance_lock.acquire()  # AlreadyRunningError before the fix
        assert reused.read_text(encoding="utf-8").split()[0] == str(os.getpid())
    finally:
        instance_lock.release()


def test_a_live_holder_is_still_refused_by_every_gate(lock):
    holder = _holder("stay")
    try:
        assert _launcher_keeps(lock)
        assert _restore_refuses()
        with pytest.raises(instance_lock.AlreadyRunningError):
            instance_lock.acquire()
    finally:
        holder.kill()
        holder.wait()
