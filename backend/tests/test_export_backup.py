"""
Tests for scripts/export_backup.py (Part 10.2).

The property that matters is not "a file appeared" but "a file appeared that
opens with the BACKUP password and refuses the live one". A backup encrypted
under the live key would look identical on disk and be worthless for the thing
backups exist for: surviving the compromise or loss of that key.
"""

import importlib.util
import json
import pathlib
import sys
from datetime import datetime, timezone

import pytest

import sqlcipher3

from backend.memory import decision_log, profile_store

LIVE_KEY = "11" * 32
BACKUP_PASSWORD = "a-different-password"


def _load_script():
    """
    scripts/ is not a package, so the module is loaded by path.

    Running `python scripts/export_backup.py` puts scripts/ at sys.path[0],
    which is how the script reaches its sibling _venv helper. Loading by path
    does not, so put it there - otherwise this fixture fails on an import that
    works perfectly well in the only way the script is actually invoked.
    """
    root = pathlib.Path(__file__).parent.parent.parent
    scripts_dir = str(root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("export_backup", root / "scripts" / "export_backup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    return _load_script()


@pytest.fixture
def live_db(tmp_path):
    path = tmp_path / "pip.db"
    conn = profile_store.get_connection(str(path), db_key=LIVE_KEY)
    profile_store.initialize_schema(conn)
    profile_store.complete_onboarding(conn, name="Anup", language_preference="English", skills=["Python"])
    decision_log.insert_decision(conn, text="Use SQLCipher end to end")
    conn.commit()
    conn.close()
    return path


def _run(script, monkeypatch, live_db, out, password=BACKUP_PASSWORD):
    monkeypatch.setenv("PIP_DB_KEY", LIVE_KEY)
    monkeypatch.setattr(script.getpass, "getpass", lambda prompt="": password)
    monkeypatch.setattr(script.sys, "argv",
                        ["export_backup.py", "--db-path", str(live_db), "--out", str(out)])
    script.main()


def _open_with(path, pragma):
    conn = sqlcipher3.connect(str(path))
    try:
        conn.execute(pragma)
        return conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0]
    finally:
        conn.close()


def test_the_backup_opens_with_its_own_password(script, monkeypatch, live_db, tmp_path, capsys):
    out = tmp_path / "backup.pipbak"
    _run(script, monkeypatch, live_db, out)

    assert out.exists()
    assert _open_with(out, f"PRAGMA key = '{BACKUP_PASSWORD}'") == 1


def test_the_backup_refuses_the_live_key(script, monkeypatch, live_db, tmp_path, capsys):
    """
    The separation is the feature. A backup readable with the live key gives no
    protection against that key leaking, which is most of why backups exist.
    """
    out = tmp_path / "backup.pipbak"
    _run(script, monkeypatch, live_db, out)

    with pytest.raises(sqlcipher3.DatabaseError):
        _open_with(out, f"PRAGMA key = \"x'{LIVE_KEY}'\"")


def test_the_backup_is_not_plaintext(script, monkeypatch, live_db, tmp_path, capsys):
    out = tmp_path / "backup.pipbak"
    _run(script, monkeypatch, live_db, out)

    assert not out.read_bytes().startswith(b"SQLite format 3")


def test_a_wrong_password_is_refused(script, monkeypatch, live_db, tmp_path, capsys):
    out = tmp_path / "backup.pipbak"
    _run(script, monkeypatch, live_db, out)

    with pytest.raises(sqlcipher3.DatabaseError):
        _open_with(out, "PRAGMA key = 'not-it'")


def test_an_existing_file_is_never_overwritten(script, monkeypatch, live_db, tmp_path, capsys):
    """
    The file being overwritten could be somebody's only copy of everything. A
    backup command that destroys a backup is the exact failure this exists to
    prevent.
    """
    out = tmp_path / "backup.pipbak"
    out.write_bytes(b"an earlier backup")

    with pytest.raises(SystemExit):
        _run(script, monkeypatch, live_db, out)

    assert out.read_bytes() == b"an earlier backup"


def test_mismatched_confirmation_writes_nothing(script, monkeypatch, live_db, tmp_path):
    entries = iter(["first-password", "second-password"])
    monkeypatch.setenv("PIP_DB_KEY", LIVE_KEY)
    monkeypatch.setattr(script.getpass, "getpass", lambda prompt="": next(entries))
    out = tmp_path / "backup.pipbak"
    monkeypatch.setattr(script.sys, "argv",
                        ["export_backup.py", "--db-path", str(live_db), "--out", str(out)])

    with pytest.raises(SystemExit):
        script.main()

    assert not out.exists()


def test_an_empty_backup_password_is_refused(script, monkeypatch, live_db, tmp_path):
    monkeypatch.setenv("PIP_DB_KEY", LIVE_KEY)
    monkeypatch.setattr(script.getpass, "getpass", lambda prompt="": "")
    out = tmp_path / "backup.pipbak"
    monkeypatch.setattr(script.sys, "argv",
                        ["export_backup.py", "--db-path", str(live_db), "--out", str(out)])

    with pytest.raises(SystemExit):
        script.main()

    assert not out.exists()


def test_a_missing_database_is_reported_not_guessed(script, monkeypatch, tmp_path):
    monkeypatch.setenv("PIP_DB_KEY", LIVE_KEY)
    monkeypatch.setattr(script.sys, "argv",
                        ["export_backup.py", "--db-path", str(tmp_path / "nope.db"),
                         "--out", str(tmp_path / "b.pipbak")])

    with pytest.raises(SystemExit):
        script.main()


def test_every_row_survives_the_export(script, monkeypatch, live_db, tmp_path, capsys):
    """
    sqlcipher_export reads through the page layer, so generated columns are
    recomputed and committed WAL content comes across. Asserted rather than
    assumed - an unverified backup is the absence of a recovery path plus the
    belief that one exists.
    """
    out = tmp_path / "backup.pipbak"
    _run(script, monkeypatch, live_db, out)

    source = profile_store.get_connection(str(live_db), db_key=LIVE_KEY)
    expected = {
        t: source.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        for t in ("identity", "skill_memory", "decision_log", "profile_meta")
    }
    source.close()

    conn = sqlcipher3.connect(str(out))
    try:
        conn.execute(f"PRAGMA key = '{BACKUP_PASSWORD}'")
        actual = {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in expected}
    finally:
        conn.close()

    assert actual == expected
    assert expected["decision_log"] == 1, "the fixture should have written something to lose"


# ---------------------------------------------------------------------------
# The default name
# ---------------------------------------------------------------------------


def test_the_default_name_is_the_one_the_spec_fixes(script, monkeypatch, live_db, tmp_path, capsys):
    """
    pip_backup_YYYYMMDD.pipbak - dated, not timestamped, so the file somebody
    goes looking for a month later is one they can name from memory.
    """
    monkeypatch.setattr(script, "DATA_DIR", tmp_path)
    monkeypatch.setenv("PIP_DB_KEY", LIVE_KEY)
    monkeypatch.setattr(script.getpass, "getpass", lambda prompt="": BACKUP_PASSWORD)

    written = script.main(["--db-path", str(live_db)])

    expected = f"pip_backup_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pipbak"
    assert written.name == expected
    assert (tmp_path / expected).exists()


def test_a_second_export_the_same_day_does_not_eat_the_first(
    script, monkeypatch, live_db, tmp_path, capsys
):
    """
    A dated name collides by design. Refusing outright would punish somebody for
    making an extra backup; overwriting would destroy the one they already had.
    """
    monkeypatch.setattr(script, "DATA_DIR", tmp_path)
    monkeypatch.setenv("PIP_DB_KEY", LIVE_KEY)
    monkeypatch.setattr(script.getpass, "getpass", lambda prompt="": BACKUP_PASSWORD)

    first = script.main(["--db-path", str(live_db)])
    first_bytes = first.read_bytes()
    second = script.main(["--db-path", str(live_db)])

    assert second != first
    assert second.name.endswith("-2.pipbak")
    assert first.read_bytes() == first_bytes


# ---------------------------------------------------------------------------
# --readable: the plaintext dump
# ---------------------------------------------------------------------------
#
# This is the most dangerous artefact the project can produce - every profile
# field, decision and conversation in the clear, with no password on it. The
# tests below are about the fence around it, not just about the dump working.


def _readable(script, monkeypatch, live_db, out, *, answer="yes", extra=()):
    monkeypatch.setenv("PIP_DB_KEY", LIVE_KEY)
    monkeypatch.setattr("builtins.input", lambda prompt="": answer)
    return script.main(["--db-path", str(live_db), "--readable", "--out", str(out), *extra])


def test_a_readable_dump_has_no_default_location(script, monkeypatch, live_db, capsys):
    """
    Every other output in this project defaults into data/. This one must not
    default anywhere, so the location is a decision somebody made.
    """
    monkeypatch.setenv("PIP_DB_KEY", LIVE_KEY)

    with pytest.raises(SystemExit) as exit_info:
        script.main(["--db-path", str(live_db), "--readable"])

    assert "no default location" in str(exit_info.value)


def test_a_readable_dump_refuses_to_land_in_the_data_directory(
    script, monkeypatch, live_db, tmp_path
):
    """
    The open gap this closes. data/ is what every backup, sync and archive step
    treats as the state worth keeping - a plaintext dump there stops being a
    one-off the moment anything copies the directory.
    """
    data_dir = tmp_path / "data"
    (data_dir / "nested").mkdir(parents=True)
    monkeypatch.setattr(script, "DATA_DIR", data_dir)
    monkeypatch.setenv("PIP_DB_KEY", LIVE_KEY)

    for target in (data_dir / "dump.json", data_dir / "nested" / "dump.json"):
        with pytest.raises(SystemExit) as exit_info:
            script.main(["--db-path", str(live_db), "--readable", "--out", str(target)])
        assert "refusing to write a plaintext dump" in str(exit_info.value)
        assert not target.exists()


def test_a_readable_dump_says_what_it_is_before_writing_it(
    script, monkeypatch, live_db, tmp_path, capsys
):
    out = tmp_path / "elsewhere" / "dump.json"
    _readable(script, monkeypatch, live_db, out)

    printed = capsys.readouterr().out
    assert "PLAINTEXT EXPORT" in printed
    assert "UNENCRYPTED" in printed
    assert str(out.resolve()) in printed


def test_declining_the_warning_writes_nothing(script, monkeypatch, live_db, tmp_path):
    out = tmp_path / "dump.json"

    with pytest.raises(SystemExit):
        _readable(script, monkeypatch, live_db, out, answer="no")

    assert not out.exists()


def test_the_readable_dump_actually_contains_the_data(
    script, monkeypatch, live_db, tmp_path, capsys
):
    """
    The point of the file is that somebody can read what PIP holds without
    restoring anything. A dump of table names and no rows would satisfy every
    other test here and none of that.
    """
    out = tmp_path / "dump.json"
    _readable(script, monkeypatch, live_db, out)

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["format"] == "pip-readable-export"
    assert payload["tables"]["identity"][0]["name"] == "Anup"
    assert [d["decision_text"] for d in payload["tables"]["decision_log"]] == [
        "Use SQLCipher end to end"
    ]


def test_the_readable_dump_skips_the_fts_shadow_tables(
    script, monkeypatch, live_db, tmp_path, capsys
):
    """
    They are an implementation detail of the index, rebuildable from
    decision_log, and dumping them would pad the file with binary noise no
    reader has a use for.
    """
    out = tmp_path / "dump.json"
    _readable(script, monkeypatch, live_db, out)

    tables = json.loads(out.read_text(encoding="utf-8"))["tables"]
    assert "decision_log" in tables
    assert not [t for t in tables if t.endswith(("_data", "_idx", "_docsize", "_config"))]


def test_the_readable_dump_never_overwrites(script, monkeypatch, live_db, tmp_path):
    out = tmp_path / "dump.json"
    out.write_text("something else that was here first", encoding="utf-8")

    with pytest.raises(SystemExit) as exit_info:
        _readable(script, monkeypatch, live_db, out)

    assert "already exists" in str(exit_info.value)
    assert out.read_text(encoding="utf-8") == "something else that was here first"


def test_yes_skips_the_readable_confirmation(script, monkeypatch, live_db, tmp_path, capsys):
    out = tmp_path / "dump.json"

    def _no_prompting(prompt=""):
        raise AssertionError("--yes must not reach the confirmation prompt")

    monkeypatch.setattr("builtins.input", _no_prompting)
    monkeypatch.setenv("PIP_DB_KEY", LIVE_KEY)

    script.main(["--db-path", str(live_db), "--readable", "--out", str(out), "--yes"])

    assert json.loads(out.read_text(encoding="utf-8"))["tables"]["identity"][0]["name"] == "Anup"


def test_a_readable_dump_is_not_a_pipbak(script, monkeypatch, live_db, tmp_path, capsys):
    """
    Two outputs, one command, and no chance of mistaking which one you have:
    the encrypted branch is unreadable without its password, and this branch is
    JSON that opens in any text editor.
    """
    encrypted = tmp_path / "backup.pipbak"
    _run(script, monkeypatch, live_db, encrypted)

    readable = tmp_path / "dump.json"
    _readable(script, monkeypatch, live_db, readable)

    with pytest.raises(UnicodeDecodeError):
        encrypted.read_text(encoding="utf-8")
    json.loads(readable.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
#
# An export produces a complete, portable copy of everything PIP holds. Taking
# one has to be a deliberate act by the person whose profile it is - not
# something a script inherits the right to do from the shell it was started in.
#
# The gate is only real under the password model, and these tests are written to
# keep that distinction visible rather than to imply a protection that is not
# there. See authenticate()'s docstring for what the boundary actually is.


@pytest.fixture
def password_model(tmp_path, monkeypatch):
    """
    An installation on the password model: a salt, and no db_key.txt.

    conftest points PIP_SALT_PATH at this test's tmp_path, so create_salt writes
    somewhere harmless - the real data/salt.bin is half of the user's key
    derivation and overwriting it would make their database permanently
    unopenable with the correct password.
    """
    from backend.core import db_key as db_key_module

    salt = db_key_module.create_salt(db_key_module.salt_path())
    return db_key_module.derive_key("the-live-password", salt)


@pytest.fixture
def password_model_db(script, monkeypatch, tmp_path, password_model):
    """A database actually keyed with the password-derived key."""
    monkeypatch.setattr(script, "KEY_PATH", tmp_path / "db_key.txt")
    path = tmp_path / "pip.db"
    conn = profile_store.get_connection(str(path), db_key=password_model)
    profile_store.initialize_schema(conn)
    profile_store.complete_onboarding(conn, name="Anup", language_preference="English", skills=["Python"])
    decision_log.insert_decision(conn, text="Use SQLCipher end to end")
    conn.commit()
    conn.close()
    return path


def test_an_inherited_key_does_not_authorise_an_export(
    script, monkeypatch, password_model, password_model_db, tmp_path, capsys
):
    """
    The hole this closes. The launcher derives the key at startup and exports
    PIP_DB_KEY into the backend process, so it is sitting in the environment of
    anything descended from a running PIP. Honouring it here would let a script
    started from that environment take a full copy of the profile without anyone
    proving they are the owner.
    """
    monkeypatch.setenv("PIP_DB_KEY", password_model)
    asked = []

    def _prompt(prompt=""):
        asked.append(prompt)
        return "the-live-password" if "Live" in prompt else BACKUP_PASSWORD

    monkeypatch.setattr(script.getpass, "getpass", _prompt)
    script.main(["--db-path", str(password_model_db), "--out", str(tmp_path / "b.pipbak")])

    assert any("Live database password" in p for p in asked), (
        "PIP_DB_KEY was accepted instead of asking for the password"
    )
    assert "is being ignored" in capsys.readouterr().out


def test_a_wrong_live_password_exports_nothing(script, monkeypatch, password_model_db, tmp_path):
    monkeypatch.setattr(script.getpass, "getpass", lambda prompt="": "not-the-live-password")
    out = tmp_path / "b.pipbak"

    with pytest.raises(SystemExit) as exit_info:
        script.main(["--db-path", str(password_model_db), "--out", str(out)])

    assert "authentication failed" in str(exit_info.value)
    assert not out.exists()


def test_a_mistyped_password_gets_another_go(
    script, monkeypatch, password_model_db, tmp_path, capsys
):
    """
    Three attempts. Not a limit on a guesser - they can re-run the script - so
    it buys patience for the owner and nothing for anyone else. The real cost of
    a guess is the KDF pass, which is paid per attempt either way.
    """
    entries = iter(["typo", "another-typo", "the-live-password"])
    monkeypatch.setattr(script.getpass, "getpass",
                        lambda prompt="": next(entries) if "Live" in prompt else BACKUP_PASSWORD)
    out = tmp_path / "b.pipbak"

    script.main(["--db-path", str(password_model_db), "--out", str(out)])

    assert out.exists()
    assert "2 attempts left" in capsys.readouterr().out


def test_the_plaintext_dump_is_gated_too(script, monkeypatch, password_model_db, tmp_path):
    """
    The readable dump is the export that needs the gate most: it is the same
    data with the encryption taken off.
    """
    out = tmp_path / "elsewhere" / "dump.json"
    monkeypatch.setattr(script.getpass, "getpass", lambda prompt="": "not-the-live-password")
    monkeypatch.setattr("builtins.input", lambda prompt="": "yes")

    with pytest.raises(SystemExit) as exit_info:
        script.main(["--db-path", str(password_model_db), "--readable", "--out", str(out), "--yes"])

    assert "authentication failed" in str(exit_info.value)
    assert not out.exists()


def test_authentication_happens_before_anything_is_read_or_written(
    script, monkeypatch, password_model_db, tmp_path, capsys
):
    """
    A refusal should leave no trace: no output file, and no row counts printed,
    because printing the shape of the database is itself a disclosure.
    """
    monkeypatch.setattr(script.getpass, "getpass", lambda prompt="": "wrong")
    out = tmp_path / "b.pipbak"

    with pytest.raises(SystemExit):
        script.main(["--db-path", str(password_model_db), "--out", str(out)])

    printed = capsys.readouterr().out
    assert "tables" not in printed, "the database shape leaked before authentication"
    assert not out.exists()


def test_the_random_key_model_says_what_is_protecting_the_data(
    script, monkeypatch, live_db, tmp_path, capsys
):
    """
    No prompt here, and the absence is stated rather than hidden. The key is a
    file; anything that can read it can read the database, so a password box in
    front of it would be theatre.
    """
    key_file = tmp_path / "db_key.txt"
    key_file.write_text(LIVE_KEY, encoding="utf-8")
    monkeypatch.setattr(script, "KEY_PATH", key_file)
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setattr(script.getpass, "getpass", lambda prompt="": BACKUP_PASSWORD)

    script.main(["--db-path", str(live_db), "--out", str(tmp_path / "b.pipbak")])

    printed = capsys.readouterr().out
    assert "data/db_key.txt" in printed
    assert "set_db_password.py" in printed
