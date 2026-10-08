"""
A restore brings back the BACKUP's documents (FREEZE_LIST D-20 and D-07).

Two ways it did not, one root:

D-20. An in-app restore swapped pip.db, its sidecars and salt.bin, and left the
profile's documents/ and chroma/ where they were. At the first sign-in the
write-back found the recorded path missing and a same-named file in the folder,
and pointed the restored record at that file: the OLD profile's content was
indexed under the backup's record, and the rebuild then stored those bytes as
the record's blob - the backup's own copy overwritten inside the restored
database. Every view still compared equal and the Documents screen listed the
name as before, so nothing showed it, against a dialog that promises "everything
in this profile will be replaced by what is in the backup ... and your
documents".

D-07. A backup restored into a SECOND profile on the same machine records paths
into the first profile's folder. They exist, so the write-back counted the
documents as present, wrote nothing, and the next rebuild - whose ingestion
sandbox is the profile's own folder - rejected the foreign path.

What is held is the outcome on disk: after the swap the old folders are kept
aside under the database's stamp and the profile's own folder holds the
backup's bytes, never the other profile's.
"""

import importlib.util
import pathlib
import sys

import pytest
import sqlcipher3

from backend.core import db_key, restore
from backend.memory import profile_store

LIVE_KEY = "11" * 32
BACKUP_PASSWORD = "the-backup-password"
NEW_PASSWORD = "a-brand-new-live-password"
BACKUPS_TEXT = b"Heliotrope design note. QUOKKA-7 is the sync engine codename."
OLD_PROFILES_TEXT = b"Zed's own note under the same name. ZEDSAME-55."


def _load(name):
    root = pathlib.Path(__file__).parent.parent.parent
    scripts_dir = str(root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(name, root / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def backup_with_a_document(tmp_path, monkeypatch):
    """A real, marked .pipbak holding one document record and its bytes, made
    on a 'machine' whose own copy of the file is no longer anywhere."""
    source = tmp_path / "machine-one"
    source.mkdir()
    db = source / "pip.db"
    conn = profile_store.get_connection(str(db), db_key=LIVE_KEY)
    profile_store.initialize_schema(conn)
    profile_store.complete_onboarding(conn, name="Zarqa", language_preference="English", skills=[])
    cursor = conn.execute(
        "INSERT INTO documents (project_id, file_path, content_hash, chunk_count, status, ingested_at) "
        "VALUES (NULL, ?, 'h', 1, 'active', '2026-09-02T10:00:00Z')",
        (str(source / "documents" / "heliotrope.txt"),),
    )
    profile_store.store_document_content(conn, cursor.lastrowid, BACKUPS_TEXT)
    conn.commit()
    conn.close()

    export = _load("export_backup")
    out = tmp_path / "backup.pipbak"
    monkeypatch.setenv("PIP_DB_KEY", LIVE_KEY)
    monkeypatch.setattr(export.getpass, "getpass", lambda prompt="": BACKUP_PASSWORD)
    monkeypatch.setattr(export.sys, "argv", ["export_backup.py", "--db-path", str(db), "--out", str(out)])
    export.main()
    monkeypatch.delenv("PIP_DB_KEY")
    return out


@pytest.fixture
def profile(tmp_path):
    """The profile being replaced: a database, a salt, a documents folder with a
    file of its own, and a vector index directory."""
    folder = tmp_path / "profiles" / "zed"
    (folder / "documents").mkdir(parents=True)
    (folder / "chroma").mkdir()
    (folder / "documents" / "heliotrope.txt").write_bytes(OLD_PROFILES_TEXT)
    (folder / "documents" / "zed-only.txt").write_bytes(b"ZEDONLY-77")
    (folder / "chroma" / "index.bin").write_bytes(b"old index")
    salt = db_key.create_salt(folder / "salt.bin")
    conn = profile_store.get_connection(str(folder / "pip.db"), db_key.derive_key("zeds-old-password", salt))
    profile_store.initialize_schema(conn)
    conn.close()
    return folder


def _stage(backup, folder, **kwargs):
    return restore.stage_restore(
        backup, BACKUP_PASSWORD, NEW_PASSWORD,
        db_path=folder / "pip.db", salt_path=folder / "salt.bin", **kwargs,
    )


def _stage_with_folders(backup, folder):
    return _stage(backup, folder, documents_dir=folder / "documents", chroma_dir=folder / "chroma")


def _kept(folder, name):
    found = sorted(folder.glob(f"{name}.superseded-*"))
    return found[0] if found else None


# ---------------------------------------------------------------------------
# D-20: the swap takes the folders with the database
# ---------------------------------------------------------------------------


def test_the_swap_moves_the_documents_and_the_index_aside_with_the_database(backup_with_a_document, profile):
    _stage_with_folders(backup_with_a_document, profile)

    assert restore.drain_pending_restore() is not None

    assert not (profile / "documents").exists(), "the old profile's documents were left where the write-back looks"
    assert not (profile / "chroma").exists(), "the old index was left beside a database it no longer matches"
    assert (_kept(profile, "documents") / "heliotrope.txt").read_bytes() == OLD_PROFILES_TEXT
    assert (_kept(profile, "documents") / "zed-only.txt").read_bytes() == b"ZEDONLY-77"
    assert (_kept(profile, "chroma") / "index.bin").read_bytes() == b"old index"
    assert _kept(profile, "pip.db") is not None


def test_a_refused_swap_puts_the_folders_back(backup_with_a_document, profile, monkeypatch):
    """The same all-or-nothing the database already had: a swap Windows refuses
    half-way must not leave the profile without its documents."""
    _stage_with_folders(backup_with_a_document, profile)
    real_move = restore.shutil.move

    def refuse_the_new_salt(src, dst, *args, **kwargs):
        if str(src).endswith(".tmp.salt"):
            raise PermissionError("[WinError 32] in use")
        return real_move(src, dst, *args, **kwargs)

    monkeypatch.setattr(restore.shutil, "move", refuse_the_new_salt)
    restore.drain_pending_restore()

    assert (profile / "documents" / "heliotrope.txt").read_bytes() == OLD_PROFILES_TEXT
    assert (profile / "chroma" / "index.bin").read_bytes() == b"old index"
    assert _kept(profile, "documents") is None and _kept(profile, "chroma") is None


def test_staging_without_the_folders_touches_only_the_database(backup_with_a_document, profile):
    """Callers that predate the two arguments get what they always got."""
    _stage(backup_with_a_document, profile)

    restore.drain_pending_restore()

    assert (profile / "documents" / "heliotrope.txt").read_bytes() == OLD_PROFILES_TEXT
    assert _kept(profile, "documents") is None


def test_a_restore_over_a_same_named_document_brings_back_the_backups_file(backup_with_a_document, profile, monkeypatch):
    """
    The measured failure, end to end: Zed's heliotrope.txt (ZEDSAME-55) sits
    where the write-back looks, and the backup's record is for a different
    heliotrope.txt (QUOKKA-7).
    """
    _stage_with_folders(backup_with_a_document, profile)
    restore.drain_pending_restore()

    monkeypatch.setenv("PIP_DOCUMENTS_ROOT", str(profile / "documents"))
    salt = db_key.load_salt(profile / "salt.bin")
    conn = profile_store.get_connection(str(profile / "pip.db"), db_key.derive_key(NEW_PASSWORD, salt))
    try:
        profile_store.materialise_documents(conn)
        record = conn.execute("SELECT id, file_path FROM documents").fetchone()
        blob = profile_store.document_content(conn, record["id"])
    finally:
        conn.close()

    written = profile / "documents" / "heliotrope.txt"
    assert record["file_path"] == str(written)
    assert written.read_bytes() == BACKUPS_TEXT, "the restored record was pointed at the old profile's file"
    assert blob == BACKUPS_TEXT
    assert not (profile / "documents" / "zed-only.txt").exists(), "a document of the old profile survived the restore"


# ---------------------------------------------------------------------------
# D-07: a path that exists, somewhere else, is not this profile's file
# ---------------------------------------------------------------------------


def _database_with_a_document(tmp_path, recorded_path, content):
    conn = profile_store.get_connection(str(tmp_path / "second.db"), db_key=LIVE_KEY)
    profile_store.initialize_schema(conn)
    cursor = conn.execute(
        "INSERT INTO documents (project_id, file_path, content_hash, chunk_count, status, ingested_at) "
        "VALUES (NULL, ?, 'h', 1, 'active', '2026-09-02T10:00:00Z')",
        (str(recorded_path),),
    )
    profile_store.store_document_content(conn, cursor.lastrowid, content)
    conn.commit()
    return conn


def test_a_document_that_exists_in_another_profiles_folder_is_written_into_this_one(tmp_path):
    first = tmp_path / "profiles" / "first" / "documents"
    first.mkdir(parents=True)
    (first / "heliotrope.txt").write_bytes(OLD_PROFILES_TEXT)
    second = tmp_path / "profiles" / "second" / "documents"
    conn = _database_with_a_document(tmp_path, first / "heliotrope.txt", BACKUPS_TEXT)
    try:
        result = profile_store.materialise_documents(conn, into=second)
        recorded = conn.execute("SELECT file_path FROM documents").fetchone()["file_path"]
    finally:
        conn.close()

    assert result["written"] == [str(second / "heliotrope.txt")]
    assert (second / "heliotrope.txt").read_bytes() == BACKUPS_TEXT
    assert recorded == str(second / "heliotrope.txt"), "the record still points into the other profile's folder"
    assert (first / "heliotrope.txt").read_bytes() == OLD_PROFILES_TEXT, "the other profile's file was touched"


def test_a_document_that_is_in_this_profiles_folder_is_left_alone(tmp_path):
    """The restraint that makes the write-back safe inside every rebuild."""
    mine = tmp_path / "profiles" / "mine" / "documents"
    mine.mkdir(parents=True)
    (mine / "notes.txt").write_bytes(b"as ingested")
    conn = _database_with_a_document(tmp_path, mine / "notes.txt", b"the stored copy")
    try:
        result = profile_store.materialise_documents(conn, into=mine)
        recorded = conn.execute("SELECT file_path FROM documents").fetchone()["file_path"]
    finally:
        conn.close()

    assert result == {"written": [], "skipped": []}
    assert recorded == str(mine / "notes.txt")
    assert (mine / "notes.txt").read_bytes() == b"as ingested"


# ---------------------------------------------------------------------------
# The same through the desktop shortcut's script
# ---------------------------------------------------------------------------


def test_the_shortcut_moves_the_documents_folder_aside_before_the_write_back(tmp_path, monkeypatch):
    """
    restore_backup.py rebuilds the index and writes the backup's documents back
    in one pass, so the folder has to be out of the way before that starts - not
    after. The stub records what the write-back would have found.
    """
    from backend.memory import vector_store

    restore_script = _load("restore_backup")
    documents = tmp_path / "shortcut-documents"
    documents.mkdir()
    (documents / "heliotrope.txt").write_bytes(OLD_PROFILES_TEXT)
    monkeypatch.setenv("PIP_DOCUMENTS_ROOT", str(documents))
    monkeypatch.setenv("PIP_CHROMA_PATH", str(tmp_path / "shortcut-chroma"))

    seen = {}

    def write_back(conn):
        seen["folder_present"] = documents.exists()
        return {"rebuilt": [], "failed": [], "materialised": []}

    monkeypatch.setattr(vector_store, "rebuild_from_sqlite", write_back)
    db = tmp_path / "restored.db"
    conn = profile_store.get_connection(str(db), "aa" * 32)
    profile_store.initialize_schema(conn)
    conn.close()

    restore_script.rebuild_vector_index(db, "aa" * 32)

    assert seen["folder_present"] is False, "the write-back would have met the old profile's files"
    kept = next(tmp_path.glob("shortcut-documents.superseded-*"))
    assert (kept / "heliotrope.txt").read_bytes() == OLD_PROFILES_TEXT
