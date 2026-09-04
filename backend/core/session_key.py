"""
The database key for the life of this process, and the states a launch can be
in before there is one.

WHY THIS EXISTS
---------------
The key used to arrive as an environment variable, derived by scripts/_db_key.ps1
before uvicorn was started. That worked, and it meant the first thing a new
user ever saw was a PowerShell console asking for a password - the launcher's
own docstring calls this out as the one place it is not silent, and calls the
cost deliberate.

It stops being worth paying once PIP is something other people install. So the
order inverts: the backend now starts with no key at all and serves exactly
three routes, the application window opens, and the password is typed into PIP
itself. Everything else stays refused until this module holds a key.

WHY THE KEY IS ALSO PUT IN THE ENVIRONMENT
------------------------------------------
Not for this process's own connections - server._conn() could read it from
here. It is for backend/memory/vector_store.py, which opens its own connection
to decrypt document blobs and reads PIP_DB_KEY directly, and for anything else
descended from this process that already expects to find it there.

That is the same variable the launcher used to set, with the same visibility,
so nothing about the exposure changes - only when it appears. It is set after
a password is proven to open the database and never written to disk, which is
Part 10.1's model intact.

WHY A WRONG PASSWORD IS SLOW
----------------------------
PBKDF2 at 256,000 iterations costs about a quarter of a second per attempt,
which is the real work factor and is unchanged. The delay below is on top of
that, and exists because a password prompt that used to be a console with
three tries is now an HTTP endpoint that can be called in a loop. It is
deliberately small: this is one more obstacle in front of an attacker who
already has the API token and local access, not a lockout that could leave the
owner of the machine unable to open their own data.
"""

import os
import threading
import time
from pathlib import Path

from backend.core import db_key

# Held for the life of the process, never written down. Guarded because the
# unlock endpoint and a request being served can touch it at the same moment.
_key: str | None = None
_failed_attempts = 0
_guard = threading.Lock()

# Roughly a second by the fourth wrong attempt, and no further. Enough to make
# a scripted guess loop unattractive next to PBKDF2's own cost; not enough to
# lock anybody out of their own machine.
_MAX_PENALTY_SECONDS = 1.0

SQLITE_MAGIC = b"SQLite format 3\x00"


def is_unlocked() -> bool:
    with _guard:
        return _key is not None


def current_key() -> str | None:
    with _guard:
        return _key


def lock() -> None:
    """Forget the key. Used by tests, and by nothing in production - a locked
    session is what a restart produces."""
    global _key, _failed_attempts
    with _guard:
        _key = None
        _failed_attempts = 0
    os.environ.pop("PIP_DB_KEY", None)


def adopt_environment_key() -> bool:
    """
    Treat a key already in the environment as this session's key.

    The launcher no longer sets PIP_DB_KEY, but three callers still can: an
    older copy of scripts/launch_pip.ps1 that somebody has not replaced, the
    test suite, and anything started from a shell that exported it. Adopting it
    means those keep working exactly as before rather than meeting a sign-in
    screen for a database that is already open to them.

    Not verified against the database here. Whoever set the variable already
    had to derive it, and a wrong one fails the same way it did before this
    module existed - at the first query, loudly. Verifying would mean opening
    the database during import, which is the thing this whole change exists to
    stop doing.
    """
    global _key
    existing = os.environ.get("PIP_DB_KEY")
    if not existing:
        return False
    with _guard:
        _key = existing
    return True


def _db_is_plaintext(db_path: Path) -> bool:
    """
    Whether this file is an UNENCRYPTED SQLite database with something in it.

    An encrypted database is indistinguishable from random bytes, so the test
    is for the plaintext header rather than against it. Size is checked too
    because get_connection() creates an empty file the moment it is pointed at
    a path, and an empty file is not data anybody would lose.
    """
    try:
        if not db_path.exists() or db_path.stat().st_size <= len(SQLITE_MAGIC):
            return False
        with open(db_path, "rb") as f:
            return f.read(len(SQLITE_MAGIC)) == SQLITE_MAGIC
    except OSError:
        return False


def state(db_path: str | Path) -> str:
    """
    Which of four situations this launch is in.

      unlocked          - a key is held; the application can be used
      locked            - a salt exists, so a password has been set: sign in
      setup             - no salt and no data: choose a password
      needs_migration   - no salt, but a plaintext database with content

    needs_migration is reported rather than repaired. Encrypting a database
    that already holds someone's memory is a rekey with backup implications,
    and scripts/set_db_password.py does it carefully - proving the new key
    opens the copy before removing anything. A button that did it silently
    would be the one irreversible action in the product with the least
    ceremony around it.
    """
    if is_unlocked():
        return "unlocked"
    if db_key.salt_path().exists():
        return "locked"
    if _db_is_plaintext(Path(db_path)):
        return "needs_migration"
    return "setup"


def unlock(password: str, db_path: str) -> bool:
    """
    Derive the key from *password* and keep it if it opens the database.

    Verified before it is kept, so a wrong password is answered as a wrong
    password rather than by every later query failing somewhere unrelated -
    SQLCipher does not fail on connect, it fails on first page access, which
    without this check would surface as a corrupt-looking error several
    requests later.
    """
    global _key, _failed_attempts

    if not password:
        return False

    try:
        candidate = db_key.derive_key_from_stored_salt(password)
    except (db_key.NoSaltError, ValueError):
        return False

    if not db_key.verify_key(db_path, candidate):
        with _guard:
            _failed_attempts += 1
            penalty = min(_failed_attempts * 0.25, _MAX_PENALTY_SECONDS)
        time.sleep(penalty)
        return False

    with _guard:
        _key = candidate
        _failed_attempts = 0
    os.environ["PIP_DB_KEY"] = candidate
    return True


def set_initial_password(password: str, db_path: str) -> None:
    """
    Choose the first password on an installation that has never had one.

    Refuses in both directions rather than guessing. A salt already present
    means a password exists and this is not the way to change it; a plaintext
    database with content means there is data to migrate, which belongs to
    scripts/set_db_password.py and its backup-first sequence.

    Creates the salt only after those checks, because create_salt() overwrites
    and a replaced salt makes an existing database permanently unopenable.
    """
    global _key

    if not password or not password.strip():
        raise ValueError("A password is required.")
    if len(password) < 8:
        # Short enough to type, long enough that 256,000 PBKDF2 iterations are
        # protecting something. The number is a floor, not advice.
        raise ValueError("Use at least 8 characters.")
    if db_key.salt_path().exists():
        raise ValueError(
            "This installation already has a password. "
            "Change it with scripts/set_db_password.py."
        )
    if _db_is_plaintext(Path(db_path)):
        raise ValueError(
            "There is already an unencrypted database here. Encrypting existing "
            "data is a migration - run scripts/set_db_password.py, which backs "
            "up first and proves the new key works before removing anything."
        )

    salt = db_key.create_salt()
    candidate = db_key.derive_key(password, salt)
    with _guard:
        _key = candidate
    os.environ["PIP_DB_KEY"] = candidate
