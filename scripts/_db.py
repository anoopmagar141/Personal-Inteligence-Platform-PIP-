"""
Open the PIP database from a script, under whichever key model is in force.

Four scripts carried an identical _connect() that predated the password
migration:

    key = os.environ.get("PIP_DB_KEY")
    if not key and KEY_PATH.exists():
        key = KEY_PATH.read_text(...).strip()
    return profile_store.get_connection(str(DB_PATH), key or None)

Once data/db_key.txt was replaced by data/salt.bin that resolves to None, and
None does not mean "no key" to get_connection() - it means "open this as plain
SQLite". So the script opened an encrypted file as an unencrypted one, which
succeeds, and then failed on the first query with "file is not a database".
The message names neither the password nor the migration, and arrives after
the script has already reported that it is doing something.

That is the same shape as the wrong-interpreter bug _venv.py exists for: a
true statement about a symptom, pointing away from the cause. So this resolves
the key the way the launcher does, verifies it before returning a connection,
and says which of the three situations it is in.

The password is taken through getpass and never printed, stored, or passed as
an argument - Windows command lines are readable by other processes, which is
why derive_db_key.py takes it on stdin rather than argv.
"""

from __future__ import annotations

import getpass
import os
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.core import db_key  # noqa: E402  (path set above)
from backend.memory import profile_store  # noqa: E402

DB_PATH = REPO_ROOT / "data" / "pip.db"
LEGACY_KEY_PATH = REPO_ROOT / "data" / "db_key.txt"
LOCK_PATH = REPO_ROOT / "data" / "pip.lock"


def resolve_key(db_path: pathlib.Path | None = None) -> str:
    """
    The hex key the database is currently encrypted with.

    PIP_DB_KEY wins, so a script run from a launcher that already derived it
    does not ask again. Then the password model (salt.bin), then the legacy
    random-key file, which still exists on installations that have not
    migrated.
    """
    path = db_path or DB_PATH

    env_key = os.environ.get("PIP_DB_KEY")
    if env_key:
        return env_key.strip()

    if db_key.salt_path().exists():
        password = getpass.getpass("PIP database password: ")
        if not password:
            raise SystemExit("ERROR: no password entered.")
        key = db_key.derive_key_from_stored_salt(password)
        if not db_key.verify_key(str(path), key):
            # Checked here rather than left to the first query, so the failure
            # names the password instead of surfacing as "file is not a
            # database" three steps later.
            raise SystemExit("ERROR: wrong password - the database did not open.")
        return key

    if LEGACY_KEY_PATH.exists():
        return LEGACY_KEY_PATH.read_text(encoding="utf-8").strip()

    raise SystemExit(
        f"ERROR: no key material found.\n"
        f"       Expected {db_key.salt_path()} (password model) or "
        f"{LEGACY_KEY_PATH} (legacy random key)."
    )


def connect(db_path: pathlib.Path | None = None):
    """An open, keyed connection - never an unkeyed one against an encrypted file."""
    path = db_path or DB_PATH
    if not path.exists():
        raise SystemExit(f"ERROR: no database at {path}")
    return profile_store.get_connection(str(path), resolve_key(path))


def warn_if_running() -> None:
    """
    A running backend holds data/pip.lock. WAL serialises the writes either
    way, so this is a note rather than a refusal - but a live session that
    disconnects afterwards runs its own Observer pass, which can write over
    what a script just wrote.
    """
    if not LOCK_PATH.exists():
        return
    pid = LOCK_PATH.read_text(encoding="utf-8").strip()
    print(f"NOTE: data/pip.lock exists (pid {pid}) - PIP may be running.")
    print("      WAL serialises the writes, but close PIP first if you want to")
    print("      read the result back without a live session writing over it.")
    print()
