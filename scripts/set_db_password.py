"""
Set or change the PIP database password, re-keying the database to match.

Why this exists
---------------
Encryption at rest was first switched on with a randomly generated key persisted
to data/db_key.txt. That works, but the key sits in the same directory as the
database it decrypts, so anything capturing data/ captures both - a stolen disk,
a disk image, a backup tool pointed at that folder. Part 10.1 specifies the
stronger model this moves to: a password typed at launch, PBKDF2-derived, never
written down. What remains on disk is the salt, which is not secret.

What it does
------------
  1. Reads the CURRENT key - from data/db_key.txt (the random-key era) or from a
     password you already set - and proves it opens the database.
  2. Takes a new password, twice, and derives a key from it against a fresh salt.
  3. Re-encrypts the database in place with SQLCipher's PRAGMA rekey.
  4. Reopens with the NEW key and verifies integrity plus row counts.
  5. Only then removes data/db_key.txt, if it was there.

Ordering is the safety property. Nothing irreversible happens until the new key
has been proven to open the re-encrypted database - and if the rekey fails
partway, the old key still works, because PRAGMA rekey is transactional.

THERE IS NO RECOVERY. Part 10.1 states this as a feature rather than a
limitation: a forgotten password means permanent profile loss, and that is the
privacy guarantee. Write the password down somewhere that is not this machine
before running this on a database you care about. This script says so and makes
you type the password twice; it cannot do more than that.

Usage
-----
    .venv\\Scripts\\python.exe scripts\\set_db_password.py
    .venv\\Scripts\\python.exe scripts\\set_db_password.py --check

--check derives from a password you type and reports whether it opens the
database, changing nothing. Useful for confirming you remember it.
"""

from __future__ import annotations

import argparse
import getpass
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from backend.core import db_key  # noqa: E402
from backend.memory import profile_store  # noqa: E402

ROOT = pathlib.Path(__file__).parent.parent
# PIP_DB_PATH honoured like every other entry point, which also lets this be
# exercised against a throwaway database rather than only the real one.
DB_PATH = pathlib.Path(os.environ["PIP_DB_PATH"]) if os.environ.get("PIP_DB_PATH") else ROOT / "data" / "pip.db"
DATA_DIR = DB_PATH.parent
LEGACY_KEY_PATH = DATA_DIR / "db_key.txt"

MIN_PASSWORD_LENGTH = 8


def _current_key() -> str | None:
    """
    The key that opens the database right now, or None if it isn't encrypted.

    Tries, in order: PIP_DB_KEY from the environment, the legacy random-key
    file, then a password against an existing salt. Returns None only when the
    database opens with no key at all (never encrypted).
    """
    env_key = os.environ.get("PIP_DB_KEY")
    if env_key and db_key.verify_key(str(DB_PATH), env_key.strip()):
        print("  current key: PIP_DB_KEY from the environment")
        return env_key.strip()

    if LEGACY_KEY_PATH.exists():
        candidate = LEGACY_KEY_PATH.read_text(encoding="utf-8").strip()
        if db_key.verify_key(str(DB_PATH), candidate):
            print(f"  current key: {LEGACY_KEY_PATH.name} (the random-key era)")
            return candidate
        print(f"  WARNING: {LEGACY_KEY_PATH.name} exists but does not open the database.")

    try:
        db_key.load_salt()
    except db_key.NoSaltError:
        pass
    else:
        password = getpass.getpass("  Current database password: ")
        candidate = db_key.derive_key_from_stored_salt(password)
        if db_key.verify_key(str(DB_PATH), candidate):
            print("  current key: derived from the password you entered")
            return candidate
        raise SystemExit("ERROR: that password does not open the database. Nothing changed.")

    # Unencrypted?
    try:
        conn = profile_store.get_connection(str(DB_PATH), None)
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        conn.close()
        print("  current key: none - the database is not encrypted")
        return None
    except Exception:
        raise SystemExit(
            "ERROR: could not open the database with any known key, and it is not plaintext.\n"
            "       Nothing changed. If you have the password, re-run and enter it when asked."
        )


def _read_new_password() -> str:
    print()
    print("  " + "!" * 68)
    print("  THERE IS NO PASSWORD RECOVERY. If you forget this, the profile,")
    print("  decision log and conversation history are permanently unreadable.")
    print("  Write it down somewhere that is not this machine, first.")
    print("  " + "!" * 68)
    print()
    while True:
        first = getpass.getpass("  New database password: ")
        if len(first) < MIN_PASSWORD_LENGTH:
            print(f"  Too short - at least {MIN_PASSWORD_LENGTH} characters.")
            continue
        second = getpass.getpass("  Type it again: ")
        if first != second:
            print("  They don't match. Again.")
            continue
        return first


def _row_counts(conn) -> dict[str, int]:
    tables = [
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    counts = {}
    for name in tables:
        # FTS5 shadow tables are internal representation; the parent is counted.
        if name.endswith(("_data", "_idx", "_content", "_docsize", "_config")):
            continue
        counts[name] = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
    return counts


def _check_only() -> int:
    try:
        db_key.load_salt()
    except db_key.NoSaltError as e:
        print(e)
        return 1
    password = getpass.getpass("Password to check: ")
    derived = db_key.derive_key_from_stored_salt(password)
    if db_key.verify_key(str(DB_PATH), derived):
        print("OK - that password opens the database.")
        return 0
    print("NO - that password does not open the database.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="Check a password without changing anything.")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"No database at {DB_PATH}.")
        print("Set the password after the app has run once and created it.")
        return 1

    if args.check:
        return _check_only()

    print(f"Database: {DB_PATH}")
    old_key = _current_key()

    # Counts taken under the OLD key, compared under the NEW one - the check
    # that actually proves the rekey preserved the data rather than merely
    # producing a file that opens.
    conn = profile_store.get_connection(str(DB_PATH), old_key)
    before = _row_counts(conn)
    print(f"  {len(before)} tables, {sum(before.values())} rows")

    password = _read_new_password()

    # A fresh salt per password change: reusing one would let anyone who
    # captured the old salt keep a head start on precomputation.
    salt = db_key.create_salt()
    new_key = db_key.derive_key(password, salt)

    print()
    print("  Re-encrypting (PBKDF2-HMAC-SHA512, 256,000 iterations - this takes a moment) ...")
    conn.execute(f"PRAGMA rekey = \"x'{new_key}'\"")
    conn.close()

    print("  Verifying with the new key ...")
    if not db_key.verify_key(str(DB_PATH), new_key):
        print()
        print("  ERROR: the database does not open with the new key.")
        print("  The old key should still work (PRAGMA rekey is transactional).")
        print(f"  {LEGACY_KEY_PATH.name} has NOT been removed.")
        return 1

    verify_conn = profile_store.get_connection(str(DB_PATH), new_key)
    integrity = verify_conn.execute("PRAGMA integrity_check").fetchone()[0]
    after = _row_counts(verify_conn)
    verify_conn.close()

    if integrity != "ok":
        print(f"  ERROR: integrity_check returned {integrity!r}. Nothing removed.")
        return 1
    mismatched = {t: (before[t], after.get(t)) for t in before if before[t] != after.get(t)}
    if mismatched:
        detail = ", ".join(f"{t}: {b} -> {a}" for t, (b, a) in mismatched.items())
        print(f"  ERROR: row counts differ after rekey ({detail}). Nothing removed.")
        return 1

    print(f"  verified: integrity ok, {sum(after.values())} rows intact")

    if LEGACY_KEY_PATH.exists():
        LEGACY_KEY_PATH.unlink()
        print(f"  removed {LEGACY_KEY_PATH.name} - the key is no longer stored on disk")

    print()
    print("Done. The database is now encrypted with a key derived from your password.")
    print(f"On disk: {db_key.salt_path().name} (the salt, not secret). The key itself is not stored.")
    print()
    print("The launchers will now prompt for this password at startup.")
    print("Check you remember it, without changing anything:")
    print("    .venv\\Scripts\\python.exe scripts\\set_db_password.py --check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
