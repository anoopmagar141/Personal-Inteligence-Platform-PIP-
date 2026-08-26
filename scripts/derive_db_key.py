"""
Read a password on stdin, print the derived database key on stdout.

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

Usage (from a launcher):
    $key = $password | & python.exe scripts\\derive_db_key.py
"""

from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from backend.core import db_key  # noqa: E402


def main() -> int:
    password = sys.stdin.readline().rstrip("\r\n")
    if not password:
        print("empty password", file=sys.stderr)
        return 2
    try:
        salt = db_key.load_salt()
    except db_key.NoSaltError as e:
        print(str(e), file=sys.stderr)
        return 1

    key = db_key.derive_key(password, salt)

    # PIP_DB_PATH honoured for the same reason every other entry point honours
    # it: one way to point at a database, and this stays testable.
    override = os.environ.get("PIP_DB_PATH")
    db_path = pathlib.Path(override) if override else pathlib.Path(__file__).parent.parent / "data" / "pip.db"
    if db_path.exists() and not db_key.verify_key(str(db_path), key):
        print("wrong password", file=sys.stderr)
        return 3

    # stdout carries the key and nothing else - the caller captures it whole.
    sys.stdout.write(key)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
