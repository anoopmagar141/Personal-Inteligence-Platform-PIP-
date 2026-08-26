"""
Tests for scripts/derive_db_key.py - the launchers' only route to a key.

Everything here guards the same property from a different angle: the key this
script prints for a password must be the key every other entry point derives
for that same password. It is the seam between PowerShell and Python, and a
mismatch across it presents to the user as "wrong password" against a database
whose password they typed correctly - with set_db_password.py's "there is no
recovery" still ringing in their ears.
"""

import importlib
import io
import sys
from pathlib import Path

import pytest

from backend.core import db_key
from backend.memory import profile_store

SCRIPTS = Path(__file__).parent.parent.parent / "scripts"

PASSWORD = "a good long password"


@pytest.fixture
def script(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_SALT_PATH", str(tmp_path / "salt.bin"))
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.setattr(sys, "argv", ["derive_db_key.py"])
    monkeypatch.syspath_prepend(str(SCRIPTS))
    module = importlib.import_module("derive_db_key")
    importlib.reload(module)
    yield module
    sys.modules.pop("derive_db_key", None)


def _stdin(monkeypatch, text: str) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))


def test_a_bom_on_the_piped_password_is_ignored(script, tmp_path, monkeypatch, capsys):
    """
    The regression test for the bug that made the documented workflow
    impossible.

    `$password | & python.exe derive_db_key.py` is how both launchers pass the
    password, and PowerShell writes a UTF-8 byte-order mark ahead of the first
    character when piping a string to a native executable. Python decodes it as
    U+FEFF and it lands inside the password, so PBKDF2 derived from
    "\\ufeff<password>".

    set_db_password.py reads with getpass and never sees a BOM, so it keyed the
    salt and the database to the clean password. The two therefore disagreed on
    every launch after a password was set: correct password, correct database,
    "Wrong password" three times, then a launcher that refuses to start.
    """
    db_key.create_salt(tmp_path / "salt.bin")
    expected = db_key.derive_key_from_stored_salt(PASSWORD)

    _stdin(monkeypatch, "\ufeff" + PASSWORD + "\n")
    assert script.main() == 0

    assert capsys.readouterr().out == expected


def test_a_plain_piped_password_derives_the_same_key(script, tmp_path, monkeypatch, capsys):
    """The no-BOM case must be untouched - the strip is not allowed to be lossy."""
    db_key.create_salt(tmp_path / "salt.bin")
    expected = db_key.derive_key_from_stored_salt(PASSWORD)

    _stdin(monkeypatch, PASSWORD + "\n")
    assert script.main() == 0

    assert capsys.readouterr().out == expected


def test_init_creates_a_salt_and_prints_a_usable_key(script, tmp_path, monkeypatch, capsys):
    """
    First run: no salt, no database. --init is what stops the launcher falling
    through to an unencrypted database, so the key it prints has to be one the
    normal (non-init) path reproduces on the next launch.
    """
    monkeypatch.setattr(sys, "argv", ["derive_db_key.py", "--init"])
    _stdin(monkeypatch, PASSWORD + "\n")

    assert script.main() == 0
    printed = capsys.readouterr().out

    assert (tmp_path / "salt.bin").exists()
    assert printed == db_key.derive_key_from_stored_salt(PASSWORD)

    # And the database it creates really is encrypted under it.
    conn = profile_store.get_connection(str(tmp_path / "pip.db"), printed)
    profile_store.initialize_schema(conn)
    conn.close()
    assert db_key.verify_key(str(tmp_path / "pip.db"), printed) is True


def test_init_refuses_a_short_password(script, tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["derive_db_key.py", "--init"])
    _stdin(monkeypatch, "short\n")

    assert script.main() == 2
    assert not (tmp_path / "salt.bin").exists()


def test_init_refuses_when_a_salt_already_exists(script, tmp_path, monkeypatch):
    """
    create_salt() overwrites, and the salt is half the derivation - so running
    --init against an existing password would change the key that password
    produces and strand the database permanently. It must refuse, and it must
    leave the existing salt exactly as it found it.
    """
    original = db_key.create_salt(tmp_path / "salt.bin")
    monkeypatch.setattr(sys, "argv", ["derive_db_key.py", "--init"])
    _stdin(monkeypatch, PASSWORD + "\n")

    assert script.main() == 4
    assert (tmp_path / "salt.bin").read_bytes() == original


def test_init_refuses_against_an_existing_plaintext_database(script, tmp_path, monkeypatch):
    """
    No salt but a database on disk means an unencrypted one. Creating a salt
    here would hand SQLCipher a plaintext file on the next launch, which dies
    on "file is not a database" in a hidden window. set_db_password.py owns
    that direction; this path must not guess at it.
    """
    conn = profile_store.get_connection(str(tmp_path / "pip.db"), None)
    profile_store.initialize_schema(conn)
    conn.close()

    monkeypatch.setattr(sys, "argv", ["derive_db_key.py", "--init"])
    _stdin(monkeypatch, PASSWORD + "\n")

    assert script.main() == 5
    assert not (tmp_path / "salt.bin").exists()


def test_wrong_password_is_reported_rather_than_printed(script, tmp_path, monkeypatch):
    """Exit 3 is what lets the launcher say "wrong password, try again" instead
    of handing a bad key to the backend and letting it die later."""
    db_key.create_salt(tmp_path / "salt.bin")
    conn = profile_store.get_connection(
        str(tmp_path / "pip.db"), db_key.derive_key_from_stored_salt(PASSWORD)
    )
    profile_store.initialize_schema(conn)
    conn.close()

    _stdin(monkeypatch, "definitely not it\n")
    assert script.main() == 3


def test_no_salt_reports_exit_1(script, monkeypatch):
    _stdin(monkeypatch, PASSWORD + "\n")
    assert script.main() == 1
