"""
Tests for the password migration script (scripts/set_db_password.py).

This script re-encrypts the real database. If it goes wrong the profile,
decision log and conversation history become permanently unreadable - there is
no recovery by design (Part 10.1). The ordering it promises is therefore the
thing worth testing: nothing irreversible happens until the new key has been
proven to open the re-encrypted database.

getpass reads the Windows console directly rather than stdin, so it cannot be
driven by piping - the prompts are monkeypatched instead.
"""

import importlib
import secrets
import sys
from pathlib import Path

import pytest

from backend.core import db_key
from backend.memory import profile_store

SCRIPTS = Path(__file__).parent.parent.parent / "scripts"


@pytest.fixture
def script(tmp_path, monkeypatch):
    """Loads the script fresh with its paths pointed at a throwaway database."""
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.setenv("PIP_SALT_PATH", str(tmp_path / "salt.bin"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.syspath_prepend(str(SCRIPTS))
    # main() parses sys.argv, which under pytest is pytest's own command line -
    # argparse would reject it. Individual tests override this for --check.
    monkeypatch.setattr(sys, "argv", ["set_db_password.py"])
    module = importlib.import_module("set_db_password")
    importlib.reload(module)  # re-read the env-derived module paths
    yield module
    sys.modules.pop("set_db_password", None)


def _seed_legacy_db(tmp_path) -> str:
    """An encrypted database plus db_key.txt beside it - the random-key era."""
    key = secrets.token_hex(32)
    conn = profile_store.get_connection(str(tmp_path / "pip.db"), key)
    profile_store.initialize_schema(conn)
    conn.execute(
        "INSERT INTO identity (id, name, language_preference, timezone) VALUES (1, 'BatMan', 'English', 'Nepal')"
    )
    conn.commit()
    conn.close()
    (tmp_path / "db_key.txt").write_text(key, encoding="utf-8")
    return key


def _answer(monkeypatch, script, *responses):
    it = iter(responses)
    monkeypatch.setattr(script.getpass, "getpass", lambda *_a, **_k: next(it))


def test_migrates_from_the_legacy_key_file_and_removes_it(script, tmp_path, monkeypatch):
    old_key = _seed_legacy_db(tmp_path)
    _answer(monkeypatch, script, "a good long password", "a good long password")

    assert script.main() == 0

    new_key = db_key.derive_key_from_stored_salt("a good long password")
    assert db_key.verify_key(str(tmp_path / "pip.db"), new_key) is True
    assert db_key.verify_key(str(tmp_path / "pip.db"), old_key) is False
    # The point of the exercise: no key left on disk.
    assert not (tmp_path / "db_key.txt").exists()


def test_data_survives_the_rekey(script, tmp_path, monkeypatch):
    _seed_legacy_db(tmp_path)
    _answer(monkeypatch, script, "a good long password", "a good long password")
    assert script.main() == 0

    conn = profile_store.get_connection(
        str(tmp_path / "pip.db"), db_key.derive_key_from_stored_salt("a good long password")
    )
    assert conn.execute("SELECT name FROM identity").fetchone()["name"] == "BatMan"
    conn.close()


def test_mismatched_confirmation_is_retried_not_accepted(script, tmp_path, monkeypatch):
    _seed_legacy_db(tmp_path)
    _answer(
        monkeypatch, script,
        "first attempt here", "typo attempt here",   # mismatch -> asked again
        "a good long password", "a good long password",
    )
    assert script.main() == 0
    assert db_key.verify_key(
        str(tmp_path / "pip.db"), db_key.derive_key_from_stored_salt("a good long password")
    )


def test_short_password_is_rejected_and_reprompted(script, tmp_path, monkeypatch):
    _seed_legacy_db(tmp_path)
    _answer(monkeypatch, script, "short", "a good long password", "a good long password")
    assert script.main() == 0


def test_check_mode_changes_nothing(script, tmp_path, monkeypatch):
    _seed_legacy_db(tmp_path)
    _answer(monkeypatch, script, "a good long password", "a good long password")
    assert script.main() == 0

    monkeypatch.setattr(sys, "argv", ["set_db_password.py", "--check"])
    _answer(monkeypatch, script, "a good long password")
    assert script.main() == 0

    monkeypatch.setattr(sys, "argv", ["set_db_password.py", "--check"])
    _answer(monkeypatch, script, "definitely not it")
    assert script.main() == 1
    # Still openable with the real password - --check must not mutate anything.
    assert db_key.verify_key(
        str(tmp_path / "pip.db"), db_key.derive_key_from_stored_salt("a good long password")
    )


def test_changing_an_existing_password_requires_the_current_one(script, tmp_path, monkeypatch):
    _seed_legacy_db(tmp_path)
    _answer(monkeypatch, script, "the first password", "the first password")
    assert script.main() == 0

    # db_key.txt is gone, so the current key can only come from the password.
    _answer(monkeypatch, script, "the first password", "the second password", "the second password")
    assert script.main() == 0
    assert db_key.verify_key(
        str(tmp_path / "pip.db"), db_key.derive_key_from_stored_salt("the second password")
    )


def test_wrong_current_password_aborts_without_touching_the_database(script, tmp_path, monkeypatch):
    _seed_legacy_db(tmp_path)
    _answer(monkeypatch, script, "the first password", "the first password")
    assert script.main() == 0
    salt_before = db_key.salt_path().read_bytes()

    _answer(monkeypatch, script, "not the current password")
    with pytest.raises(SystemExit):
        script.main()

    # Salt untouched, so the original password still derives the working key -
    # a failed attempt must not be able to strand the database.
    assert db_key.salt_path().read_bytes() == salt_before
    assert db_key.verify_key(
        str(tmp_path / "pip.db"), db_key.derive_key_from_stored_salt("the first password")
    )
