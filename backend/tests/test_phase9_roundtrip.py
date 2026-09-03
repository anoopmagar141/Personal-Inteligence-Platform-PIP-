"""
Phase 9: the round trip that actually matters.

Every other test in test_export_backup.py and test_restore_backup.py checks one
leg of the journey against a live database that is still sitting there working.
That is not the situation any of this exists for. The situation is: the database
is gone, and the .pipbak is the only thing left.

So this file writes data, deliberately leaves the most recent write in the -wal
file where a naive backup would miss it, exports, DESTROYS the live database,
restores, and then asks whether the row that was never checkpointed came back.

    write (no checkpoint) -> export -> corrupt -> restore -> verify

Two things are being pinned at once.

THE GUARANTEE
    Recent writes survive. A backup that silently drops the last thing you told
    PIP is worse than no backup, because you would not find out until you needed
    it and by then the original is gone.

THE MECHANISM
    Which is not the checkpoint. Part 10.2 records this as empirically verified
    and marks PRAGMA wal_checkpoint(TRUNCATE) as defence in depth rather than
    the thing doing the work - sqlcipher_export() reads through SQLite's page
    layer, not raw file bytes, so it sees committed WAL content whether or not
    anyone folded it back into the database file first.

    That claim is easy to state and easy to quietly break: swap the export for a
    file copy, or move the checkpoint, and the checkpoint silently becomes
    load-bearing again. test_the_export_does_not_need_the_checkpoint_at_all
    removes the checkpoint entirely and demands the row anyway, which is the
    only way to keep knowing which of the two is holding the guarantee up.

The projects and decisions asked about below are ordinary rows in the same
database - active_projects.project_id and decision_log - so they need nothing
special to survive, and this asserts that rather than assuming it.
"""

import importlib.util
import pathlib
import shutil
import sys

import pytest
import sqlcipher3

from backend.core import db_key as db_key_module
from backend.memory import decision_log, profile_store

LIVE_KEY = "11" * 32
BACKUP_PASSWORD = "the-backup-password"
NEW_LIVE_PASSWORD = "the-new-live-password"

UNCHECKPOINTED = "Ship the cross-machine restore before the demo"
PROJECT_NAME = "Personal Intelligence Platform"


def _load(name: str):
    """scripts/ is not a package - the same by-path load the sibling tests use."""
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
def machine_one(tmp_path):
    """
    A populated database with its most recent write still in the -wal file.

    The connection is handed back still open, and that is the fixture's whole
    trick: SQLite checkpoints on the close of the last connection, so closing
    here would quietly fold the WAL back in and leave nothing for the test to
    prove. wal_autocheckpoint = 0 stops it happening on a page threshold too.
    """
    db_path = tmp_path / "pip.db"
    conn = profile_store.get_connection(str(db_path), db_key=LIVE_KEY)
    profile_store.initialize_schema(conn)
    profile_store.complete_onboarding(
        conn, name="Anup", language_preference="English", skills=["Python"]
    )
    project_id = profile_store.create_project(conn, PROJECT_NAME, "final year project")
    decision_log.insert_decision(conn, text="Use SQLCipher end to end")
    conn.commit()

    # Everything above may or may not have been checkpointed. Everything below
    # definitely is not.
    conn.execute("PRAGMA wal_autocheckpoint = 0")
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    decision_log.insert_decision(conn, text=UNCHECKPOINTED, project_id=project_id)
    conn.commit()

    wal = db_path.with_name(db_path.name + "-wal")
    assert wal.exists() and wal.stat().st_size > 0, "nothing is in the WAL to lose"

    yield db_path, conn, project_id
    try:
        conn.close()
    except Exception:
        pass


def _main_file_only(db_path: pathlib.Path, tmp_path: pathlib.Path) -> int:
    """
    How many decisions a backup that copied only the .db file would have found.

    This is the control. Without it, "the row came back" proves nothing about
    WAL residency - the row might have been in the main file the whole time and
    the test would pass just as happily.
    """
    isolated = tmp_path / "main-file-only.db"
    shutil.copyfile(db_path, isolated)
    conn = sqlcipher3.connect(str(isolated))
    try:
        conn.execute(f"PRAGMA key = \"x'{LIVE_KEY}'\"")
        return conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0]
    finally:
        conn.close()


def _export(export_script, monkeypatch, db_path, out, *, checkpoint=True):
    monkeypatch.setenv("PIP_DB_KEY", LIVE_KEY)
    monkeypatch.setattr(export_script.getpass, "getpass", lambda prompt="": BACKUP_PASSWORD)
    if not checkpoint:
        monkeypatch.setattr(export_script, "checkpoint", lambda conn: None)
    return export_script.main(["--db-path", str(db_path), "--out", str(out)])


def _destroy(db_path: pathlib.Path, conn) -> None:
    """
    Machine one dies. Not "the password was forgotten" - the file itself is
    rubble, along with the WAL and shared-memory files beside it, because a
    corruption test that left a recoverable sidecar would not be one.
    """
    conn.close()
    db_path.write_bytes(b"\x00\xff" * 8192)
    for suffix in ("-wal", "-shm"):
        sidecar = db_path.with_name(db_path.name + suffix)
        if sidecar.exists():
            sidecar.unlink()

    with pytest.raises(sqlcipher3.DatabaseError):
        broken = sqlcipher3.connect(str(db_path))
        try:
            broken.execute(f"PRAGMA key = \"x'{LIVE_KEY}'\"")
            broken.execute("SELECT COUNT(*) FROM decision_log").fetchone()
        finally:
            broken.close()


def _restore(restore_script, monkeypatch, backup, out):
    answers = iter([BACKUP_PASSWORD, NEW_LIVE_PASSWORD, NEW_LIVE_PASSWORD])
    monkeypatch.setattr(restore_script.getpass, "getpass", lambda prompt="": next(answers))
    monkeypatch.setattr("builtins.input", lambda prompt="": "yes")
    return restore_script.main(["--from", str(backup), "--out", str(out)])


def _reopen(db_path: pathlib.Path):
    """Machine two, opening the restored database with the new password."""
    new_key = db_key_module.derive_key_from_stored_salt(NEW_LIVE_PASSWORD)
    return profile_store.get_connection(str(db_path), db_key=new_key)


def test_the_unckeckpointed_write_survives_the_whole_round_trip(
    export_script, restore_script, monkeypatch, machine_one, tmp_path, capsys
):
    """
    The one that matters. The last thing written before the machine died is the
    thing most likely to be the reason somebody is restoring at all.
    """
    db_path, conn, project_id = machine_one
    before = conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0]
    assert _main_file_only(db_path, tmp_path) < before, (
        "the newest decision is not actually WAL-resident, so this test is not "
        "testing what it says it is"
    )

    backup = _export(export_script, monkeypatch, db_path, tmp_path / "machine-one.pipbak")
    _destroy(db_path, conn)
    assert _restore(restore_script, monkeypatch, backup, db_path) == 0

    restored = _reopen(db_path)
    try:
        texts = [r["decision_text"] for r in restored.execute("SELECT * FROM decision_log")]
        assert UNCHECKPOINTED in texts
        assert len(texts) == before
    finally:
        restored.close()


def test_the_export_does_not_need_the_checkpoint_at_all(
    export_script, restore_script, monkeypatch, machine_one, tmp_path, capsys
):
    """
    Part 10.2's empirical claim, kept honest.

    The checkpoint is removed outright here, so if sqlcipher_export() ever stops
    reading through the page layer - or gets swapped for a file copy - this
    fails and the note calling the checkpoint "defence in depth" stops being
    true quietly.
    """
    db_path, conn, _ = machine_one
    before = conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0]

    backup = _export(export_script, monkeypatch, db_path,
                     tmp_path / "no-checkpoint.pipbak", checkpoint=False)
    _destroy(db_path, conn)
    assert _restore(restore_script, monkeypatch, backup, db_path) == 0

    restored = _reopen(db_path)
    try:
        texts = [r["decision_text"] for r in restored.execute("SELECT * FROM decision_log")]
    finally:
        restored.close()

    assert UNCHECKPOINTED in texts
    assert len(texts) == before


def test_projects_come_back_with_everything_else(
    export_script, restore_script, monkeypatch, machine_one, tmp_path, capsys
):
    """
    active_projects rows, and the project_id foreign key pointing at one from
    the decision written into the WAL.

    Nothing was added anywhere to make this work: projects are ordinary rows in
    the same database, so they travel in the same file as the profile and the
    decision log. Asserted because "nothing extra is required" is a claim, and
    an untested claim about a restore is the kind that is discovered to be
    wrong at the worst possible moment.
    """
    db_path, conn, project_id = machine_one
    backup = _export(export_script, monkeypatch, db_path, tmp_path / "projects.pipbak")
    _destroy(db_path, conn)
    _restore(restore_script, monkeypatch, backup, db_path)

    restored = _reopen(db_path)
    try:
        projects = profile_store.list_projects(restored)
        linked = restored.execute(
            "SELECT project_id FROM decision_log WHERE decision_text = ?", (UNCHECKPOINTED,)
        ).fetchone()
    finally:
        restored.close()

    assert [p["name"] for p in projects] == [PROJECT_NAME]
    assert projects[0]["project_id"] == project_id
    assert linked["project_id"] == project_id, "the foreign key survived, not just the row"


def test_the_profile_comes_back_intact(
    export_script, restore_script, monkeypatch, machine_one, tmp_path, capsys
):
    """
    The exit condition for this phase is a second machine where nothing has to
    be re-entered by hand - identity and skills included, not just the log.
    """
    db_path, conn, _ = machine_one
    before = {
        (row["field"], str(row["value"]))
        for row in profile_store.get_profile(conn)
    }

    backup = _export(export_script, monkeypatch, db_path, tmp_path / "profile.pipbak")
    _destroy(db_path, conn)
    _restore(restore_script, monkeypatch, backup, db_path)

    restored = _reopen(db_path)
    try:
        after = {(row["field"], str(row["value"])) for row in profile_store.get_profile(restored)}
        name = restored.execute("SELECT name FROM identity WHERE id = 1").fetchone()["name"]
    finally:
        restored.close()

    assert name == "Anup"
    assert after == before
    assert before, "the fixture should have written a profile worth losing"


def test_the_restored_database_refuses_both_of_the_old_secrets(
    export_script, restore_script, monkeypatch, machine_one, tmp_path, capsys
):
    """
    Machine two is not machine one. The restored database opens with the new
    live password and with nothing else - not the old live key, which is what a
    restore-in-place would have quietly kept, and not the backup password, which
    would collapse the two-secret model into one.
    """
    db_path, conn, _ = machine_one
    backup = _export(export_script, monkeypatch, db_path, tmp_path / "secrets.pipbak")
    _destroy(db_path, conn)
    _restore(restore_script, monkeypatch, backup, db_path)

    for pragma in (f"PRAGMA key = \"x'{LIVE_KEY}'\"", f"PRAGMA key = '{BACKUP_PASSWORD}'"):
        with pytest.raises(sqlcipher3.DatabaseError):
            rejected = sqlcipher3.connect(str(db_path))
            try:
                rejected.execute(pragma)
                rejected.execute("SELECT COUNT(*) FROM decision_log").fetchone()
            finally:
                rejected.close()

    restored = _reopen(db_path)
    restored.close()


def test_a_restore_onto_a_machine_with_no_data_directory_works(
    export_script, restore_script, monkeypatch, machine_one, tmp_path, capsys
):
    """
    Machine two, literally: a fresh clone where data/ has never existed.

    Every other restore test writes into a directory that is already there,
    which quietly assumes the thing a second machine does not have. If the
    destination's parent had to exist, the exit condition for this whole feature
    would fail on the first real attempt - after the user had already destroyed
    or left behind the original.
    """
    db_path, conn, _ = machine_one
    backup = _export(export_script, monkeypatch, db_path, tmp_path / "carried-over.pipbak")
    conn.close()

    fresh = tmp_path / "fresh-clone" / "data"
    assert not fresh.exists(), "the point is that it does not exist yet"
    monkeypatch.setenv("PIP_SALT_PATH", str(fresh / "salt.bin"))

    assert _restore(restore_script, monkeypatch, backup, fresh / "pip.db") == 0

    assert (fresh / "pip.db").exists()
    assert (fresh / "salt.bin").exists()

    restored = _reopen(fresh / "pip.db")
    try:
        name = restored.execute("SELECT name FROM identity WHERE id = 1").fetchone()["name"]
        decisions = [r["decision_text"] for r in restored.execute("SELECT * FROM decision_log")]
        projects = profile_store.list_projects(restored)
    finally:
        restored.close()

    assert name == "Anup"
    assert UNCHECKPOINTED in decisions
    assert [p["name"] for p in projects] == [PROJECT_NAME]


def test_documents_come_back_as_rows_but_not_as_files(
    export_script, restore_script, monkeypatch, machine_one, tmp_path, capsys
):
    """
    The honest limit of a single-file backup, pinned so nobody discovers it on
    the machine they were relying on.

    The documents table stores file_path, content_hash and chunk_count - the
    REGISTRY of what was ingested, not the bytes. So a .pipbak carries the fact
    that four documents were indexed and none of their content. On a second
    machine those paths do not resolve, rebuild_from_sqlite() reports them as
    missing, and RAG over them returns nothing until the files are copied across
    and re-ingested.

    Everything else - profile, projects, decisions, conversations - is rows, and
    rows travel.
    """
    db_path, conn, project_id = machine_one
    conn.execute(
        "INSERT INTO documents (project_id, file_path, content_hash, chunk_count, "
        "status, ingested_at) VALUES (?, ?, ?, ?, 'active', ?)",
        (project_id, str(tmp_path / "only-on-machine-one.md"), "abc123", 7,
         "2026-09-02T10:00:00Z"),
    )
    conn.commit()

    backup = _export(export_script, monkeypatch, db_path, tmp_path / "docs.pipbak")
    _destroy(db_path, conn)
    _restore(restore_script, monkeypatch, backup, db_path)

    restored = _reopen(db_path)
    try:
        row = restored.execute("SELECT * FROM documents").fetchone()
    finally:
        restored.close()

    assert row["chunk_count"] == 7, "the registry row travelled"
    assert row["file_path"].endswith("only-on-machine-one.md")
    assert "content" not in row.keys(), (
        "if documents ever starts storing content, this test's premise - and the "
        "advice to copy data/documents/ by hand - both change"
    )


def test_document_content_travels_and_is_written_back(
    export_script, restore_script, monkeypatch, machine_one, tmp_path, capsys
):
    """
    The gap that made "everything, A to Z" untrue, and the test that keeps it
    closed.

    The documents table records that a file was ingested - path, hash, chunk
    count - and for a long time nothing held the file. So a restore brought back
    a registry pointing at paths that had never existed on the new machine:
    profile, projects, decisions and conversations all arrived, and RAG arrived
    empty, repairable only by remembering to copy data/documents/ by hand on the
    day you were already restoring from a backup.

    document_blobs carries the bytes inside the same single .pipbak - no new
    format, no sibling folder, nothing to keep together. This writes a document,
    exports, destroys the database AND deletes the file, restores onto a
    documents directory that has never held it, and asks for the content back.
    """
    db_path, conn, project_id = machine_one

    source = tmp_path / "machine-one-docs"
    source.mkdir()
    original = source / "thesis-notes.md"
    body = "# Thesis notes\n\nSQLCipher end to end, one encrypted unit.\n"
    original.write_text(body, encoding="utf-8")

    cursor = conn.execute(
        "INSERT INTO documents (project_id, file_path, content_hash, chunk_count, "
        "status, ingested_at) VALUES (?, ?, ?, ?, 'active', ?)",
        (project_id, str(original), "hash-abc", 3, "2026-09-02T10:00:00Z"),
    )
    profile_store.store_document_content(conn, cursor.lastrowid, original.read_bytes())
    conn.commit()

    backup = _export(export_script, monkeypatch, db_path, tmp_path / "with-docs.pipbak")

    _destroy(db_path, conn)
    original.unlink()
    shutil.rmtree(source)

    assert _restore(restore_script, monkeypatch, backup, db_path) == 0

    # A documents directory on the new machine that has never held this file.
    machine_two_docs = tmp_path / "machine-two-docs"
    monkeypatch.setenv("PIP_DOCUMENTS_ROOT", str(machine_two_docs))

    restored = _reopen(db_path)
    try:
        result = profile_store.materialise_documents(restored)
        row = restored.execute("SELECT file_path FROM documents").fetchone()
    finally:
        restored.close()

    written = machine_two_docs / "thesis-notes.md"
    assert written.exists(), "the document did not come back"
    assert written.read_text(encoding="utf-8") == body
    assert result["written"] == [str(written)]
    assert row["file_path"] == str(written), (
        "the registry still points at the old machine's path, so the next "
        "rebuild would look somewhere that does not exist"
    )


def test_a_restored_document_never_escapes_the_documents_directory(
    export_script, restore_script, monkeypatch, machine_one, tmp_path, capsys
):
    """
    A .pipbak is a file that arrives from somewhere else, and file_path is a
    string inside it. Writing to that path verbatim would let a backup - crafted,
    or merely made on a machine with a different layout - place bytes anywhere
    the user can write. Only the file NAME is used, under this machine's own
    documents directory.
    """
    db_path, conn, project_id = machine_one
    escape = tmp_path / "somewhere-else" / "escaped.md"

    cursor = conn.execute(
        "INSERT INTO documents (project_id, file_path, content_hash, chunk_count, "
        "status, ingested_at) VALUES (?, ?, ?, ?, 'active', ?)",
        (project_id, str(escape), "hash-xyz", 1, "2026-09-02T10:00:00Z"),
    )
    profile_store.store_document_content(conn, cursor.lastrowid, b"payload")
    conn.commit()

    backup = _export(export_script, monkeypatch, db_path, tmp_path / "escape.pipbak")
    _destroy(db_path, conn)
    _restore(restore_script, monkeypatch, backup, db_path)

    docs = tmp_path / "safe-documents"
    monkeypatch.setenv("PIP_DOCUMENTS_ROOT", str(docs))

    restored = _reopen(db_path)
    try:
        profile_store.materialise_documents(restored)
    finally:
        restored.close()

    assert not escape.exists(), "a restore wrote outside the documents directory"
    assert (docs / "escaped.md").read_bytes() == b"payload"
