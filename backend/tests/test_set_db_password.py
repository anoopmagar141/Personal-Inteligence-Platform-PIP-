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


# --- the search index ------------------------------------------------------
#
# This script re-encrypted the database and left ChromaDB alone. Everything
# identifying a chunk there is keyed on the database key - the id is an HMAC of
# it, the text and the stored path are Fernet under it - so the index stopped
# answering while nothing said so: the Documents screen reads its chunk counts
# from the SQLite `documents` table and went on describing an index that had
# gone dark. Survivable, because chroma/ is derived and a rebuild restores it,
# but a rebuild re-embeds every document and only runs once something notices.


def test_the_index_is_carried_over_to_the_new_key(script, tmp_path, monkeypatch):
    """The whole point. Called with both keys, so the conversion is possible at
    all - the old key is gone from disk by the time anything else could run."""
    _seed_legacy_db(tmp_path)
    seen = {}
    monkeypatch.setattr(
        script, "reencrypt_vector_index",
        lambda old, new: seen.update(old=old, new=new),
    )
    _answer(monkeypatch, script, "a good long password", "a good long password")

    assert script.main() == 0

    assert seen, "the rekey never offered the index to be carried over"
    assert seen["new"] == db_key.derive_key_from_stored_salt("a good long password")
    assert seen["old"] != seen["new"]


def test_no_index_rekey_is_honoured(script, tmp_path, monkeypatch, capsys):
    _seed_legacy_db(tmp_path)
    monkeypatch.setattr(
        script, "reencrypt_vector_index",
        lambda *a, **k: pytest.fail("--no-index-rekey must skip this"),
    )
    monkeypatch.setattr(sys, "argv", ["set_db_password.py", "--no-index-rekey"])
    _answer(monkeypatch, script, "a good long password", "a good long password")

    assert script.main() == 0
    assert "still under the OLD key" in capsys.readouterr().out


def test_the_index_is_carried_over_only_after_the_database_is_verified(
    script, tmp_path, monkeypatch
):
    """
    Ordering, and it is the safety property. A conversion that ran before the
    new key was proven would be a second irreversible operation stacked on an
    unverified first - and the index is the one of the two that can be rebuilt,
    so it is the one that goes last.
    """
    _seed_legacy_db(tmp_path)
    order = []
    real_verify = db_key.verify_key
    monkeypatch.setattr(
        db_key, "verify_key",
        lambda path, key: (order.append("verify"), real_verify(path, key))[1],
    )
    monkeypatch.setattr(
        script, "reencrypt_vector_index",
        lambda old, new: order.append("index"),
    )
    _answer(monkeypatch, script, "a good long password", "a good long password")

    assert script.main() == 0
    assert order.index("index") > order.index("verify")


def test_a_failing_index_conversion_does_not_fail_the_rekey(script, tmp_path, monkeypatch, capsys):
    """
    The database is already verified by then. Failing the run over a derived
    store would report a rekey as broken when it had succeeded - and the cost
    of the failure is a re-embed, not a loss.
    """
    _seed_legacy_db(tmp_path)

    def _explode(*_a, **_k):
        raise RuntimeError("chromadb is not installed")

    monkeypatch.setattr(script, "reencrypt_vector_index", _explode)
    _answer(monkeypatch, script, "a good long password", "a good long password")

    assert script.main() == 0
    assert "index re-encryption failed" in capsys.readouterr().out
    assert db_key.verify_key(
        str(tmp_path / "pip.db"), db_key.derive_key_from_stored_salt("a good long password")
    )
    # And the legacy key file is still removed: that step is gated on the
    # database verifying, not on a derived store converting.
    assert not (tmp_path / "db_key.txt").exists()


def test_the_index_still_answers_after_a_real_rekey(script, tmp_path, monkeypatch):
    """
    End to end, with nothing stubbed: ingest a document under the old key, run
    the script for real, and ask a question under the new one.

    The mocked tests above prove the wiring - that the conversion is offered,
    in the right order, with both keys. This proves the thing itself, which is
    the only claim that matters: before the fix this query came back empty from
    an index that still had every chunk in it.
    """
    from backend.memory import vector_store

    old_key = _seed_legacy_db(tmp_path)

    documents = tmp_path / "documents"
    documents.mkdir()
    doc = documents / "notes.txt"
    doc.write_text(
        "PIP uses SQLCipher for encrypted storage. ChromaDB is the vector index "
        "for RAG and is never authoritative.",
        encoding="utf-8",
    )
    monkeypatch.setattr(vector_store, "DOCUMENTS_ROOT", documents)
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(vector_store, "_collection", None)

    monkeypatch.setenv("PIP_DB_KEY", old_key)
    conn = profile_store.get_connection(str(tmp_path / "pip.db"), old_key)
    vector_store.ingest_document(conn, str(doc))
    conn.close()
    assert vector_store.query(
        profile_store.get_connection(str(tmp_path / "pip.db"), old_key),
        "Is ChromaDB the source of truth?", threshold=0.1, top_k=3,
    ), "the fixture did not leave a searchable index"

    _answer(monkeypatch, script, "a good long password", "a good long password")
    assert script.main() == 0

    new_key = db_key.derive_key_from_stored_salt("a good long password")
    monkeypatch.setenv("PIP_DB_KEY", new_key)
    conn = profile_store.get_connection(str(tmp_path / "pip.db"), new_key)
    try:
        matches = vector_store.query(
            conn, "Is ChromaDB the source of truth?", threshold=0.1, top_k=3
        )
    finally:
        conn.close()

    assert any("ChromaDB" in m["chunk_text"] for m in matches), (
        "the index went dark: the database was re-encrypted and the chunks were not"
    )
    assert all(m["file_path"] == str(doc) for m in matches)
