# PIP Core - stage trace log
#
# One JSON object per line (JSONL), appended.
#
# This was a single JSON array, rewritten in full on every call: read the whole
# file, parse it, append one entry, re-serialize, truncate, write it all back.
# That is O(n) work per entry and O(n^2) over a session, on the response path -
# roughly 14 entries per message, so a 250KB log already meant ~3.5MB of
# read-modify-write per message, growing with every message ever sent, and
# nothing ever trimmed it. Appending one line costs the same whether the file
# holds ten entries or ten million.
#
# It was also unsafe in two ways that a debug log has no business being:
#
#   - Not thread-safe. Each WS connection runs its stages on its own executor
#     thread (see backend/api/server.py), and two of them doing
#     read/seek(0)/dump/truncate on the same file interleave into a corrupt
#     one.
#   - A corrupt file was silently emptied. The old `except JSONDecodeError:
#     data = []` meant one torn write discarded every entry in the log - the
#     entire debugging history, thrown away by the code whose job was keeping
#     it, with no error and no trace of what happened.
#
# JSONL fixes all three at once: a torn line costs that line and nothing else,
# and read_entries() skips it rather than treating the file as a total loss.

import json
import logging
import os
import threading
import uuid
from pathlib import Path
from typing import Any

from backend.core.types import now_utc

logger = logging.getLogger(__name__)

TRACE_LOG_PATH = Path(__file__).parent.parent / "logs" / "trace_log.jsonl"

# Rotated at this size, keeping one previous generation, so the log is bounded
# at ~2x this on disk. Previously unbounded: nothing anywhere trimmed it, and
# it is written to on the response path of every message forever.
MAX_TRACE_LOG_BYTES = 5 * 1024 * 1024

# The writers are threads inside one process, so a plain Lock is the right
# primitive - there is no second process writing here (instance_lock.py makes
# sure of that).
_write_lock = threading.Lock()


def generate_trace_id() -> str:
    """Generates a unique trace ID using UUIDv4."""
    return str(uuid.uuid4())


def _rotate_if_needed(path: Path) -> None:
    """
    Moves the log aside once it passes MAX_TRACE_LOG_BYTES, keeping exactly one
    previous generation. os.replace is atomic, so a reader either sees the old
    file or the new one, never a half-moved one.

    Best-effort: a log that cannot be rotated is not a reason to fail a
    request, and the append below will simply keep going.
    """
    try:
        if path.exists() and path.stat().st_size >= MAX_TRACE_LOG_BYTES:
            os.replace(path, path.parent / (path.name + ".1"))
    except OSError as e:
        logger.warning(f"Could not rotate the trace log: {e}")


def stage_log(trace_id: str, stage: str, status: str, message: str, error_detail: str = "") -> None:
    """
    Appends one trace entry.

    Callers must keep user content out of `message` - the pipeline logs
    lengths and categories, not text, because this file sits outside the
    SQLCipher database and is not encrypted (see pipeline.run's note).
    """
    entry = {
        "trace_id": trace_id,
        "timestamp": now_utc(),
        "stage": stage,
        "status": status,
        "message": message,
        "error_detail": error_detail,
    }

    try:
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with _write_lock:
            TRACE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            _rotate_if_needed(TRACE_LOG_PATH)
            with open(TRACE_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(line)
    except Exception as e:
        # A failure to write a debug log must never take down the pipeline it
        # is describing.
        logger.error(f"Failed to write to trace log: {e}")


def read_entries(path: Path | None = None) -> list[dict[str, Any]]:
    """
    Every entry in the log, oldest first.

    The one supported way to read this file. A line that does not parse is
    skipped rather than treated as the end of the log or as a reason to
    discard the rest - a torn write costs one entry, which is the whole point
    of the line-per-entry format.

    Only the current generation; a rotated trace_log.jsonl.1 is deliberately
    not merged in, since callers asking for "the trace log" mean the live one.
    """
    target = Path(path) if path is not None else TRACE_LOG_PATH
    if not target.exists():
        return []

    entries: list[dict[str, Any]] = []
    with open(target, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                logger.warning("Skipping an unparseable line in the trace log")
    return entries
