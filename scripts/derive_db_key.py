"""
Read a password on stdin, print the derived database key on stdout.

Two modes:

  (default)  Derive from the EXISTING salt. Used on every normal launch.
  --init     Create a salt and derive from it. Used once, on a first run,
             so the database is created encrypted instead of plaintext.

--init exists because the launchers previously had no answer for the
no-salt-no-key case at all. Set-PipDbKey returned success without setting
PIP_DB_KEY, get_connection() took its unencrypted sqlite3 fallback, and a fresh
install ran entirely in the clear - silently, which is the same shape as the
bug commit 8414e44 fixed ("ADR-026's encrypted-at-rest guarantee was dead code
in every launch"), just narrowed to installs that hadn't run yet. Creating the
salt up front is better than creating a plaintext database and re-keying it
later: there is never a window where the profile exists unencrypted on disk,
and no plaintext pages linger in free space afterwards.

The launchers need the key to hand to the backend, and must not derive it
themselves. PBKDF2 is only reproducible if every parameter matches exactly -
hash, iteration count, output length, salt encoding - and a PowerShell
reimplementation that differed in any one of them would produce a different
key, silently, presenting as "wrong password" against a database the user had
typed the right password for. One implementation (backend/core/db_key.py),
called from everywhere.

The password arrives on stdin rather than as an argument on purpose: command
lines are readable by other processes on Windows, which would put the password
exactly where this whole change exists to keep it out of.

The derived key is verified against the database before being printed, when one
exists. Without that, a mistyped password would surface as the backend dying on
"file is not a database" some seconds later, in a hidden window - the launcher
can say "wrong password, try again" instead.

Exit codes:
    0  key printed
    1  no salt (no password has been set)
    2  bad input
    3  key does not open the database (wrong password)
    4  --init refused: a salt already exists
    5  --init refused: the database already exists

Usage (from a launcher):
    $key = $password | & python.exe scripts\\derive_db_key.py
    $key = $password | & python.exe scripts\\derive_db_key.py --init
"""

from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from backend.core import db_key  # noqa: E402


def _read_password() -> str:
    """
    One line from stdin, minus the line ending and minus a leading BOM.

    The BOM strip is load-bearing, not defensive. `$password | & python.exe
    derive_db_key.py` is how both launchers pass the password, and PowerShell
    writes a UTF-8 byte-order mark ahead of the first character when it pipes a
    string to a native executable. Python decodes it as U+FEFF and it becomes
    part of the password, so PBKDF2 derives from "\\ufeff<password>".

    Which silently broke the one path the user is actually told to take.
    set_db_password.py reads with getpass and gets the clean string, so the
    salt and the database are keyed to "<password>" - then the launcher pipes
    the same correct password, derives a different key, and reports "Wrong
    password" three times before refusing to start. The database is fine and
    the password is right; only the transport differs. Nothing in the failure
    message could have pointed at that, and the script it came from states
    there is no recovery, so the natural conclusion for a user is that they
    have lost their profile.

    Stripped here rather than in PowerShell because this is the single point
    every caller passes through, and a fix in one launcher would leave the
    other wrong.
    """
    # Spelled as an escape on purpose - a literal BOM here would be an
    # invisible character in the source, which is how this class of bug hides.
    return sys.stdin.readline().lstrip("\ufeff").rstrip("\r\n")


def _db_path() -> pathlib.Path:
    # PIP_DB_PATH honoured for the same reason every other entry point honours
    # it: one way to point at a database, and this stays testable.
    override = os.environ.get("PIP_DB_PATH")
    return pathlib.Path(override) if override else pathlib.Path(__file__).parent.parent / "data" / "pip.db"


def _init() -> int:
    """
    First run: create a salt from a new password and print the derived key.

    Both refusals below protect the same thing. create_salt() overwrites, and
    the salt is half the derivation - replacing it changes the key that any
    given password produces, so an existing encrypted database would become
    unopenable with the password its owner correctly remembers. A first-run
    path must never be able to do that, however it is invoked.
    """
    password = _read_password()
    if len(password) < db_key.MIN_PASSWORD_LENGTH:
        print(f"password must be at least {db_key.MIN_PASSWORD_LENGTH} characters", file=sys.stderr)
        return 2

    if db_key.salt_path().exists():
        print(
            f"a salt already exists at {db_key.salt_path()} - a password is already set. "
            "Use scripts/set_db_password.py to change it.",
            file=sys.stderr,
        )
        return 4

    # No salt but a database on disk means an existing PLAINTEXT database (an
    # encrypted one could only have come from a salt or the legacy key file).
    # Deriving a key here would hand SQLCipher a plaintext file and fail with
    # "file is not a database" on the first query, in a hidden window.
    # set_db_password.py handles that direction properly - it rekeys with
    # verification instead of guessing.
    if _db_path().exists():
        print(
            f"{_db_path()} already exists and is not encrypted. "
            "Use scripts/set_db_password.py to encrypt it in place.",
            file=sys.stderr,
        )
        return 5

    key = db_key.derive_key(password, db_key.create_salt())
    sys.stdout.write(key)
    return 0


def main() -> int:
    if "--init" in sys.argv[1:]:
        return _init()

    password = _read_password()
    if not password:
        print("empty password", file=sys.stderr)
        return 2
    try:
        salt = db_key.load_salt()
    except db_key.NoSaltError as e:
        print(str(e), file=sys.stderr)
        return 1

    key = db_key.derive_key(password, salt)

    db_path = _db_path()
    if db_path.exists() and not db_key.verify_key(str(db_path), key):
        print("wrong password", file=sys.stderr)
        return 3

    # stdout carries the key and nothing else - the caller captures it whole.
    sys.stdout.write(key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
