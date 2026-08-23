# PIP Core - single-instance lock
#
# Security review finding: nothing stopped a second `run_dev.ps1` (or a bare
# second `uvicorn backend.api.server:app`) from starting - the only thing
# that ever caught it was the OS refusing to bind :8765 twice, which is luck,
# not design, and doesn't catch two backends on different ports writing to
# the SAME SQLite/SQLCipher file at once (WAL tolerates concurrent readers
# fine; two writers is exactly the corruption/lost-write risk a real
# single-instance guard exists to rule out).
#
# A PID file at data/pip.lock records the PID of the process that currently
# holds the lock. On startup: if the file exists AND names a still-live PID,
# refuse to start - loud, not a silent no-op, matching this codebase's
# existing "fail loud, not silent" precedent (the wrong-key SQLCipher check,
# the hex-only db_key validation). If the PID is dead (e.g. a process that
# was `taskkill`ed without a clean shutdown), the lock is stale - log a
# warning and take it over rather than blocking forever on a lock nothing
# will ever release.
#
# Re-acquiring with the SAME pid already in the file is treated as success,
# not a conflict: that's what happens on every FastAPI TestClient lifespan
# cycle within one pytest process (many sequential startups, one PID), and
# it's just correct - a process can't conflict with itself.

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

LOCK_PATH = Path(__file__).parent.parent.parent / "data" / "pip.lock"


class AlreadyRunningError(Exception):
    """Raised when another live PIP backend process already holds the lock."""


def _lock_path() -> Path:
    # Test isolation, same pattern as PIP_DB_PATH/PIP_TOKEN_PATH - unset
    # means "use the real lock file in data/pip.lock" (production behavior).
    override = os.environ.get("PIP_LOCK_PATH")
    return Path(override) if override else LOCK_PATH


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    else:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # exists, just not ours to signal
        return True


def acquire() -> None:
    """
    Claims the single-instance lock for the current process. Raises
    AlreadyRunningError if a different, still-live process already holds it.
    Safe to call repeatedly from the same process (tests re-entering the
    FastAPI lifespan, one TestClient after another).
    """
    path = _lock_path()
    our_pid = os.getpid()

    if path.exists():
        try:
            existing_pid = int(path.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            existing_pid = -1

        if existing_pid == our_pid:
            return  # already ours - nothing to do

        if _pid_is_running(existing_pid):
            raise AlreadyRunningError(
                f"PIP backend is already running (pid {existing_pid}, lock file {path}). "
                "Stop that instance first, or delete the lock file if it's actually dead."
            )

        logger.warning(
            f"Found a stale lock file at {path} (pid {existing_pid} is not running) - taking over the lock."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(our_pid), encoding="utf-8")


def release() -> None:
    """Releases the lock if - and only if - this process still owns it."""
    path = _lock_path()
    if not path.exists():
        return
    try:
        existing_pid = int(path.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return
    if existing_pid == os.getpid():
        try:
            path.unlink()
        except OSError:
            pass
