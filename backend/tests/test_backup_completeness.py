"""
A backup is accepted only if it is a COMPLETE export (FREEZE_LIST D-18).

Both restores used to check a .pipbak against itself and nothing else: the
backup password opens it, integrity_check says ok, and the restored copy has
the row counts the backup has. SQLCipher opens a zero-length file as a new,
empty database under ANY key, so a 0-byte file passed every one of those checks
and "restored" an empty profile over the person's real one. An export killed
part-way passes the same way - sqlcipher_export commits table by table, so what
is left opens fine with some tables empty.

What these tests hold is the outcome, not the check: after a refused backup the
installation is exactly as it was (no marker, no temporary files, the database
and salt untouched), and a refused backup is told why in a sentence.

Three kinds of file, and what each is owed:
  - a complete export carries a mark written as the LAST step of a verified
    export, and restores;
  - a part-written or truncated one is refused, because its mark says so or
    its counts disagree with the mark;
  - an older backup, from before marks existed, has nothing to compare against
    and is accepted on the weaker evidence that it holds PIP's tables - the
    people most in need of a restore are the ones holding exactly those files.
"""

import importlib.util
import pathlib
import sys

import pytest
import sqlcipher3

from backend.core import db_key, restore
from backend.memory import decision_log, profile_store

LIVE_KEY = "11" * 32
BACKUP_PASSWORD = "the-backup-password"
NEW_PASSWORD = "a-brand-new-live-password"


def _load(name: str):
    root = pathlib.Path(__file__).parent.parent.parent
    scripts_dir = str(root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(name, root / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def export_script():
    return _load("export_backup")


@pytest.fixture
def restore_script():
    return _load("restore_backup")


@pytest.fixture
def live_db(tmp_path):
    path = tmp_path / "pip.db"
    conn = profile_store.get_connection(str(path), db_key=LIVE_KEY)
    profile_store.initialize_schema(conn)
    profile_store.complete_onboarding(
        conn, name="Anup", language_preference="English", skills=["Python"]
    )
    decision_log.insert_decision(conn, text="Use SQLCipher end to end")
    conn.execute(
        "INSERT INTO conversations (id, title, created_at, updated_at) VALUES ('c1', 'Chat', 't', 't')"
    )
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES ('c1', 'user', 'hi', 't')"
    )
    conn.commit()
    conn.close()
    return path


def _export(export_script, monkeypatch, live_db, out):
    monkeypatch.setenv("PIP_DB_KEY", LIVE_KEY)
    monkeypatch.setattr(export_script.getpass, "getpass", lambda prompt="": BACKUP_PASSWORD)
    monkeypatch.setattr(
        export_script.sys, "argv",
        ["export_backup.py", "--db-path", str(live_db), "--out", str(out)],
    )
    return export_script.main()


@pytest.fixture
def backup(export_script, monkeypatch, live_db, tmp_path):
    out = tmp_path / "backup.pipbak"
    _export(export_script, monkeypatch, live_db, out)
    return out


def _stage(backup_path, tmp_path):
    return restore.stage_restore(
        backup_path, BACKUP_PASSWORD, NEW_PASSWORD,
        db_path=tmp_path / "pip.db", salt_path=tmp_path / "salt.bin",
    )


def _nothing_staged(tmp_path):
    return (
        not restore.pending_restore_path().exists()
        and not list(tmp_path.glob("restore-*.tmp.*"))
    )


def _tables(path, password):
    conn = sqlcipher3.connect(str(path))
    try:
        conn.execute(f"PRAGMA key = '{password}'")
        return [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Files that are not backups at all
# ---------------------------------------------------------------------------


def test_an_empty_file_is_refused_and_nothing_is_staged(tmp_path):
    empty = tmp_path / "empty.pipbak"
    empty.write_bytes(b"")

    with pytest.raises(restore.RestoreError, match="no tables"):
        _stage(empty, tmp_path)

    assert _nothing_staged(tmp_path)


def test_a_database_with_no_tables_is_refused(tmp_path):
    path = tmp_path / "blank.pipbak"
    conn = sqlcipher3.connect(str(path))
    conn.execute(f"PRAGMA key = '{BACKUP_PASSWORD}'")
    conn.execute("CREATE TABLE t (x)")
    conn.execute("DROP TABLE t")
    conn.commit()
    conn.close()

    with pytest.raises(restore.RestoreError, match="no tables"):
        _stage(path, tmp_path)

    assert _nothing_staged(tmp_path)


def test_a_database_that_is_not_pips_is_refused(tmp_path):
    path = tmp_path / "other.pipbak"
    conn = sqlcipher3.connect(str(path))
    conn.execute(f"PRAGMA key = '{BACKUP_PASSWORD}'")
    conn.execute("CREATE TABLE shopping (item TEXT)")
    conn.execute("INSERT INTO shopping VALUES ('milk')")
    conn.commit()
    conn.close()

    with pytest.raises(restore.RestoreError, match="not a PIP backup"):
        _stage(path, tmp_path)

    assert _nothing_staged(tmp_path)


# ---------------------------------------------------------------------------
# A real export is marked, and only a finished one
# ---------------------------------------------------------------------------


def test_a_complete_export_carries_a_mark_and_restores(backup, tmp_path):
    assert "pip_backup_mark" in _tables(backup, BACKUP_PASSWORD)

    staged = _stage(backup, tmp_path)

    assert staged["rows"] > 0

    # The mark describes the FILE, not the profile: it must not follow the data
    # into the live database, where the next export would copy a stale one.
    conn = sqlcipher3.connect(staged["db"])
    try:
        salt = db_key.load_salt(pathlib.Path(staged["salt"]))
        conn.execute(f"PRAGMA key = \"x'{db_key.derive_key(NEW_PASSWORD, salt)}'\"")
        names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    finally:
        conn.close()
    assert "pip_backup_mark" not in names
    assert "identity" in names


def _killed_after_verifying(export_script, monkeypatch, live_db, out):
    """
    An export that was killed between verify() and the mark: the file is whole,
    opens, has every table and every row - and nothing ever vouched for it.
    (A run that FAILS removes its file; only a kill can leave one behind.)
    """
    monkeypatch.setattr(export_script.backup_mark, "finish", lambda *args, **kwargs: None)
    _export(export_script, monkeypatch, live_db, out)
    assert out.exists()
    return out


def _killed_while_copying(live_db, out):
    """An export killed during the copy: the unfinished mark and nothing else."""
    from backend.core import backup_mark

    src = sqlcipher3.connect(str(live_db))
    try:
        src.execute(f"PRAGMA key = \"x'{LIVE_KEY}'\"")
        src.execute(f"ATTACH DATABASE '{out}' AS backup KEY '{BACKUP_PASSWORD}'")
        backup_mark.begin(src, "backup")
        src.execute("DETACH DATABASE backup")
    finally:
        src.close()
    return out


def test_an_export_killed_after_verifying_is_not_restorable(
    export_script, monkeypatch, live_db, tmp_path
):
    """
    A file nothing ever vouched for must be refused even though it is real,
    opens, and holds every table - which is exactly why a mark, and not a look
    at the contents, is the evidence.
    """
    out = _killed_after_verifying(export_script, monkeypatch, live_db, tmp_path / "partial.pipbak")

    with pytest.raises(restore.RestoreError, match="did not finish|incomplete"):
        _stage(out, tmp_path)

    assert _nothing_staged(tmp_path)


def test_an_export_killed_while_copying_is_not_restorable(live_db, tmp_path):
    out = _killed_while_copying(live_db, tmp_path / "partial.pipbak")

    with pytest.raises(restore.RestoreError, match="did not finish|incomplete"):
        _stage(out, tmp_path)

    assert _nothing_staged(tmp_path)


def test_a_backup_that_lost_rows_after_it_was_marked_is_refused(backup, tmp_path):
    conn = sqlcipher3.connect(str(backup))
    conn.execute(f"PRAGMA key = '{BACKUP_PASSWORD}'")
    conn.execute("DELETE FROM messages")
    conn.commit()
    conn.close()

    with pytest.raises(restore.RestoreError, match="messages"):
        _stage(backup, tmp_path)

    assert _nothing_staged(tmp_path)


def test_a_backup_from_before_marks_still_restores(tmp_path):
    """Older exports have nothing to compare against; refusing them would
    strand exactly the people a restore is for."""
    path = tmp_path / "older.pipbak"
    conn = sqlcipher3.connect(str(path))
    conn.execute(f"PRAGMA key = '{BACKUP_PASSWORD}'")
    conn.execute("CREATE TABLE identity (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO identity VALUES (1, 'Before marks')")
    conn.commit()
    conn.close()

    staged = _stage(path, tmp_path)

    assert staged["rows"] == 1


# ---------------------------------------------------------------------------
# The same rule through the shortcut's script
# ---------------------------------------------------------------------------


def _drive_restore(restore_script, monkeypatch, source, out):
    answers = iter([BACKUP_PASSWORD, NEW_PASSWORD, NEW_PASSWORD])
    monkeypatch.setattr(restore_script.getpass, "getpass", lambda prompt="": next(answers))
    monkeypatch.setattr("builtins.input", lambda prompt="": "yes")
    monkeypatch.setattr(
        restore_script.sys, "argv",
        ["restore_backup.py", "--from", str(source), "--out", str(out), "--no-index-rebuild"],
    )
    return restore_script.main()


def test_the_shortcut_refuses_an_empty_file_and_replaces_nothing(
    restore_script, monkeypatch, live_db, tmp_path, capsys
):
    salt = tmp_path / "salt.bin"
    salt.write_bytes(b"x" * 32)
    before = (live_db.read_bytes(), salt.read_bytes())
    empty = tmp_path / "empty.pipbak"
    empty.write_bytes(b"")

    code = _drive_restore(restore_script, monkeypatch, empty, live_db)

    assert code == 1
    assert (live_db.read_bytes(), salt.read_bytes()) == before
    assert not list(tmp_path.glob("*.superseded-*"))
    assert not list(tmp_path.glob("restore-*.tmp.*"))


def test_the_shortcut_refuses_an_unfinished_export(
    export_script, restore_script, monkeypatch, live_db, tmp_path
):
    partial = _killed_after_verifying(export_script, monkeypatch, live_db, tmp_path / "partial.pipbak")
    before = live_db.read_bytes()

    code = _drive_restore(restore_script, monkeypatch, partial, live_db)

    assert code == 1
    assert live_db.read_bytes() == before
    assert not list(tmp_path.glob("*.superseded-*"))


def test_the_shortcut_restores_a_complete_export(
    restore_script, monkeypatch, backup, tmp_path
):
    out = tmp_path / "restored" / "pip.db"

    code = _drive_restore(restore_script, monkeypatch, backup, out)

    assert code == 0
    assert out.exists()


# ---------------------------------------------------------------------------
# The file the person chose is read, never written
# ---------------------------------------------------------------------------


def _backup_with_a_hot_journal(tmp_path):
    """
    A backup somebody copied while a writer was mid-transaction: the .pipbak and
    a rollback journal beside it that SQLite would play back into it. Built the
    way test_restore_in_app does for a WAL - the pair is copied out while the
    writing connection is still open.
    """
    import shutil

    path = tmp_path / "carried.pipbak"
    conn = sqlcipher3.connect(str(path))
    conn.execute(f"PRAGMA key = '{BACKUP_PASSWORD}'")
    conn.execute("CREATE TABLE identity (id INTEGER PRIMARY KEY, name TEXT)")
    conn.executemany("INSERT INTO identity VALUES (?, ?)", [(i, "x" * 200) for i in range(300)])
    conn.commit()
    # A journal only counts as hot once SQLite has synced it, which it does when
    # the page cache spills into the database file. A small cache and an update
    # across every page forces that; without it the journal is a stub that plays
    # back nothing and the test would pass whatever the file is opened with.
    conn.execute("PRAGMA cache_size = 2")
    conn.execute("BEGIN")
    conn.execute("UPDATE identity SET name = 'changed mid-transaction ' || id")
    journal = path.with_name(path.name + "-journal")
    assert journal.exists() and journal.stat().st_size > 0, "no journal to leave behind"
    frozen = tmp_path / "frozen"
    frozen.mkdir()
    for p in (path, journal):
        shutil.copyfile(p, frozen / p.name)
    conn.rollback()
    conn.close()
    for p in (path, journal):
        shutil.copyfile(frozen / p.name, p)
    shutil.rmtree(frozen)
    return path, journal


def test_choosing_a_backup_never_writes_to_it(tmp_path):
    """
    Staging opened the chosen file read-write, so a hot journal beside it was
    rolled back INTO the person's own .pipbak - their copy modified, and the
    journal consumed, by a step whose job is to read it (FREEZE_LIST D-18).
    """
    path, journal = _backup_with_a_hot_journal(tmp_path)
    before = (path.read_bytes(), path.stat().st_mtime_ns, journal.read_bytes())

    with pytest.raises(restore.RestoreError, match="leftover journal"):
        _stage(path, tmp_path)

    assert journal.exists(), "the journal beside the chosen file was played back into it"
    assert (path.read_bytes(), path.stat().st_mtime_ns, journal.read_bytes()) == before


def test_the_shortcut_never_writes_to_the_chosen_backup_either(restore_script, monkeypatch, tmp_path):
    path, journal = _backup_with_a_hot_journal(tmp_path)
    before = (path.read_bytes(), path.stat().st_mtime_ns, journal.read_bytes())
    out = tmp_path / "restored" / "pip.db"

    with pytest.raises(SystemExit) as refused:
        _drive_restore(restore_script, monkeypatch, path, out)

    assert "leftover journal" in str(refused.value)
    assert journal.exists(), "the journal beside the chosen file was played back into it"
    assert (path.read_bytes(), path.stat().st_mtime_ns, journal.read_bytes()) == before
