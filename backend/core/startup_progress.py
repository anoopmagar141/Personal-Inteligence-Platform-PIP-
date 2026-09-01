# PIP Core - startup progress, for the app's launch screen.
#
# The Flutter client used to show a spinner and one of two sentences chosen by
# a RETRY COUNTER: "Starting PIP..." for the first seven attempts, "Still
# preparing things" after that. Neither was derived from anything actually
# happening - the app has no way to see inside a backend that is not answering
# yet, so after eight seconds it guessed, and said the same thing whether the
# database was being decrypted or nothing was running at all.
#
# WHY A FILE AND NOT AN ENDPOINT. The obvious design is GET /startup, and it
# cannot work: FastAPI's lifespan blocks serving until it finishes, so an
# endpoint cannot describe the work that is currently stopping it from
# existing. Nothing HTTP-shaped can report on a server that is not up.
#
# A file can, and this app already reads one on exactly this path - it polls
# data/api_token.txt in the same retry loop, for the same reason (the token is
# generated on first run and cannot be known at build time). So the launch
# screen is not being taught a new trick; it is reading a second file next to
# the one it already reads.
#
# APPEND-ONLY, one JSON object per line. A phase is a fact that happened, not a
# state to be overwritten, and appending is the one write that cannot leave a
# reader looking at a half-replaced file. It also means PowerShell and Python
# can both write here without coordinating - the launcher owns the phases
# before uvicorn exists, this module owns the ones after.
#
# NEVER RAISES. A launch screen is a courtesy. Taking down a startup because
# the courtesy could not be written would invert the priority exactly the way
# trace.stage_log() already declines to.

import json
import logging
import os
from pathlib import Path
from typing import Any

from backend.core.types import now_utc

logger = logging.getLogger(__name__)

DEFAULT_PROGRESS_PATH = Path(__file__).parent.parent.parent / "data" / "startup.jsonl"


def progress_path() -> Path:
    """Where phases are written. PIP_STARTUP_PROGRESS_PATH overrides, for tests."""
    override = os.environ.get("PIP_STARTUP_PROGRESS_PATH")
    return Path(override) if override else DEFAULT_PROGRESS_PATH


def report(phase: str, detail: str = "") -> None:
    """
    Records that [phase] has been reached.

    Ordering comes from the file, not from a timestamp: now_utc() has second
    resolution and a whole startup fits inside one second, which is the same
    trap trace.get_trace() documents ordering by id to avoid.
    """
    try:
        path = progress_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"phase": phase, "detail": detail, "at": now_utc()})
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception as exc:  # pragma: no cover - defensive, see module docstring
        logger.debug(f"Could not record startup phase {phase!r}: {exc}")


def reset() -> None:
    """
    Clears the file for a fresh launch.

    Called by whoever starts the run - the launcher for a normal double-click,
    this module's own caller otherwise. Without it the previous launch's
    phases are still there and a launch screen would show a completed
    checklist before anything had happened. The client has a second guard for
    the same hazard (it ignores a file older than its own start), because a
    backend started by hand never goes through the launcher at all.
    """
    try:
        path = progress_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(f"Could not reset startup progress: {exc}")


def read() -> list[dict[str, Any]]:
    """
    The phases recorded so far, in the order they happened.

    Skips any line that does not parse. A reader can arrive mid-write, and one
    torn line is not a reason to report nothing - the phases before it are
    still true.
    """
    try:
        raw = progress_path().read_text(encoding="utf-8")
    except OSError:
        return []

    phases: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict) and isinstance(entry.get("phase"), str):
            phases.append(entry)
    return phases
