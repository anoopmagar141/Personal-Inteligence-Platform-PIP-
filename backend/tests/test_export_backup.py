"""
Tests for scripts/export_backup.py (Part 10.2).

The property that matters is not "a file appeared" but "a file appeared that
opens with the BACKUP password and refuses the live one". A backup encrypted
under the live key would look identical on disk and be worthless for the thing
backups exist for: surviving the compromise or loss of that key.
"""

import importlib.util
import pathlib

import pytest

import sqlcipher3

from backend.memory import decision_log, profile_store

LIVE_KEY = "11" * 32
BACKUP_PASSWORD = "a-different-password"


def _load_script():
    """scripts/ is not a package, so the module is loaded by path."""
    root = pathlib.Path(__file__).parent.parent.parent
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
