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
import os
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
    # Safety net. _rebuild_vector_store() scopes PIP_DB_KEY to the rebuild and
    # restores it, so this should already be clean - but monkeypatch.delenv
    # above records nothing when the variable was already absent, leaving it
    # with no value to restore if that ever stops being true. Nothing else in
    # the suite isolates PIP_DB_KEY, and a stray real key makes
    # get_connection() hand a plaintext test database to SQLCipher, which
    # fails somewhere else entirely.
    os.environ.pop("PIP_DB_KEY", None)


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


def test_the_vector_index_is_rebuilt_under_the_new_key(script, tmp_path, monkeypatch):
    """
    PIP_DB_KEY protects the ChromaDB vector index as well as the database:
    chunk text and file paths are Fernet-encrypted with a key derived from it,
    and chunks are addressed by HMAC(PIP_DB_KEY, file_path). A rekey therefore
    orphans the whole index - unreadable AND unaddressable in one step - and
    the read path degrades to returning nothing at all, silently, forever.

    So the rebuild is part of the operation, not homework for the user. The
    key it rebuilds under has to be the NEW one; rebuilding under the old key
    would re-encrypt everything right back into unreadability.

    Spied rather than run for real - vector_store pulls in chromadb and
    sentence-transformers, and the rebuild itself is covered end-to-end in
    test_vector_store.py.
    """
    _seed_legacy_db(tmp_path)
    _answer(monkeypatch, script, "a good long password", "a good long password")

    called_with = []
    monkeypatch.setattr(script, "_rebuild_vector_store", lambda key: called_with.append(key))

    assert script.main() == 0

    assert called_with == [db_key.derive_key_from_stored_salt("a good long password")]


def test_rebuild_is_skipped_when_nothing_is_ingested(script, tmp_path, monkeypatch, capsys):
    """
    The real _rebuild_vector_store, unspied, on a database with no documents.

    It must reach its early return without importing vector_store: that import
    costs seconds of chromadb + sentence-transformers startup, and a database
    with nothing ingested should not pay it just to change a password.
    """
    _seed_legacy_db(tmp_path)
    _answer(monkeypatch, script, "a good long password", "a good long password")

    assert script.main() == 0
    assert "nothing ingested, nothing to rebuild" in capsys.readouterr().out


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
