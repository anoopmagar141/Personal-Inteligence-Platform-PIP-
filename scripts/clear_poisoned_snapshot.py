"""
Clear a session_snapshot that describes PIP failing to remember, rather than
anything the user did.

What was in there
-----------------
    topic: retrieving information about the pip project
    open_problems: ['User wants to recall previous conversation about pip project']
    suggested_next_step: Try searching previous conversations or ask for clarification
    snapshot_date: 2026-09-01T12:52:38Z

That is a summary of a two-message conversation in which the user asked "what
we were doing last time in pip project" and PIP answered "I don't have that
recorded." The Observer then wrote that exchange over the standing snapshot -
so the failure to recall became the thing recalled, and the session it failed
to recall was destroyed in the same move. Left alone, the next attempt is
answered with a description of the previous attempt, and every retry ratchets
the real content further out of reach.

Why a script and not a fix
--------------------------
The leak is repaired separately, in stage_11_observer's
_snapshot_may_overwrite_the_standing_one(): a session now earns the right to
overwrite by having produced a candidate or carried more than one substantive
user turn. That stops the next one. It cannot undo this one - write_snapshot()
only ever overwrites with another snapshot, and the singleton row has no
version behind it. This is the mop, same division of labour as
cleanup_fabricated_memory.py and retract_fabricated_candidates.py.

What clearing means
-------------------
session_snapshot.clear_snapshot() removes the row outright, returning the store
to its genuine "no snapshot yet" state (load_snapshot() -> None) rather than
leaving empty strings that merely read as one. Nothing else is touched: the
conversation, its messages, the profile and the decision log all stay exactly
as they are - only the one-line recap of "last session" goes. The next real
working session writes a true one.

There is nothing to restore afterwards, so --dry-run prints the row and stops.
Run that first if you want to read what is about to go.
"""

from __future__ import annotations

import _venv

_venv.require("sqlcipher3")

import argparse
import getpass
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from backend.core import db_key  # noqa: E402
from backend.memory import profile_store, session_snapshot  # noqa: E402

ROOT = pathlib.Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "pip.db"
LOCK_PATH = ROOT / "data" / "pip.lock"


def _connect():
    """
    PIP_DB_KEY if a launcher already derived it, otherwise prompt. The password
    is never printed, stored, or passed as an argument - command lines are
    readable by other processes on Windows, which is why derive_db_key.py takes
    it on stdin and why this takes it through getpass.
    """
    key = os.environ.get("PIP_DB_KEY")
    if not key:
        key = db_key.derive_key_from_stored_salt(getpass.getpass("DB password: "))
    if not db_key.verify_key(str(DB_PATH), key):
        raise SystemExit("wrong password - the database did not open.")
    return profile_store.get_connection(str(DB_PATH), key)


def _warn_if_running() -> None:
    if not LOCK_PATH.exists():
        return
    pid = LOCK_PATH.read_text(encoding="utf-8").strip()
    print(
        f"NOTE: data/pip.lock exists (pid {pid}) - PIP may be running. A live "
        "session that disconnects afterwards will write a NEW snapshot, which "
        "is fine, but close PIP first if you want to read the result back."
    )
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Clear a wrong session snapshot.")
    parser.add_argument("--dry-run", action="store_true", help="show the row, write nothing")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"no database at {DB_PATH}", file=sys.stderr)
        return 1

    _warn_if_running()
    conn = _connect()
    try:
        current = session_snapshot.load_snapshot(conn)
        if current is None:
            print("No snapshot stored - nothing to clear.")
            return 0

        print("Current snapshot:")
        for field, value in current.items():
            print(f"  {field}: {value}")
        print()

        if args.dry_run:
            print("DRY RUN - nothing was written.")
            return 0

        # Reported from clear_snapshot's own return value rather than assumed:
        # it distinguishes "a row was removed" from "there was none", so this
        # cannot claim to have undone something it did not.
        if session_snapshot.clear_snapshot(conn):
            print("Cleared. load_snapshot() now returns None - the genuine")
            print("'no snapshot yet' state, not an empty row dressed up as one.")
            print("The next session that actually goes somewhere writes a true one.")
        else:
            print("Nothing was removed - the row disappeared between the read and the delete.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
