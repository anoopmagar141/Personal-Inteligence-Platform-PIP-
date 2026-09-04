import os

import pytest
from backend.memory import vector_store
from backend.memory.profile_store import get_connection, initialize_schema


@pytest.fixture
def db_conn(tmp_path, db_key):
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path, db_key=db_key)
    initialize_schema(conn)
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def isolated_chroma(tmp_path, monkeypatch):
    monkeypatch.setattr(vector_store, "CHROMA_DB_PATH", str(tmp_path / "chroma"))
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(vector_store, "_collection", None)
    # This module derives its own encryption key from PIP_DB_KEY directly
    # (see vector_store._get_db_key()), independent of the SQLCipher db_key
    # fixture/connection above - keep it unset by default so the existing
    # plaintext-mode tests below stay exercising the no-key passthrough path.
    # Tests for the encrypted path opt in explicitly via monkeypatch.setenv.
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    yield


@pytest.fixture(autouse=True)
def isolated_documents_root(tmp_path, monkeypatch):
    # ingest_document() now rejects any file_path outside DOCUMENTS_ROOT
    # (arbitrary-file-read fix) - without this, every test here would need a
    # file physically inside the real project's data/documents/, and would
    # fail against the real default root entirely in CI.
    root = tmp_path / "documents"
    root.mkdir()
    monkeypatch.setattr(vector_store, "DOCUMENTS_ROOT", root)
    return root


@pytest.fixture
def sample_doc(isolated_documents_root):
    doc_path = isolated_documents_root / "notes.txt"
    doc_path.write_text(
        "PIP uses SQLCipher for encrypted storage. "
        "ChromaDB is the vector index for RAG and is never authoritative. "
        "The Observer runs at session end only, never per message.",
        encoding="utf-8",
    )
    return str(doc_path)


def test_ingest_then_query_returns_matching_chunk(db_conn, sample_doc):
    result = vector_store.ingest_document(db_conn, sample_doc)
    assert result["status"] == "ingested"
    assert result["chunk_count"] >= 1

    matches = vector_store.query(db_conn, "Is ChromaDB the source of truth?", threshold=0.1, top_k=3)
    assert len(matches) >= 1
    assert any("ChromaDB" in m["chunk_text"] for m in matches)


def test_query_below_threshold_returns_empty(db_conn, sample_doc):
    vector_store.ingest_document(db_conn, sample_doc)
    matches = vector_store.query(db_conn, "Is ChromaDB the source of truth?", threshold=0.999, top_k=3)
    assert matches == []


def test_reingest_unchanged_file_is_noop(db_conn, sample_doc):
    first = vector_store.ingest_document(db_conn, sample_doc)
    second = vector_store.ingest_document(db_conn, sample_doc)
    assert first["status"] == "ingested"
    assert second["status"] == "unchanged"
    assert db_conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 1


def test_reingest_changed_file_replaces_chunks(db_conn, isolated_documents_root):
    doc_path = isolated_documents_root / "notes.txt"
    doc_path.write_text("Original content about FastAPI.", encoding="utf-8")
    vector_store.ingest_document(db_conn, str(doc_path))

    doc_path.write_text("Completely different content about Neovim.", encoding="utf-8")
    result = vector_store.ingest_document(db_conn, str(doc_path))
    assert result["status"] == "ingested"

    matches = vector_store.query(db_conn, "Neovim", threshold=0.1, top_k=5)
    assert any("Neovim" in m["chunk_text"] for m in matches)
    matches_old = vector_store.query(db_conn, "FastAPI", threshold=0.5, top_k=5)
    assert matches_old == [] or all("FastAPI" not in m["chunk_text"] for m in matches_old)


def test_delete_document_removes_chunks_and_marks_removed(db_conn, sample_doc):
    vector_store.ingest_document(db_conn, sample_doc)
    assert vector_store.delete_document(db_conn, sample_doc) is True

    row = db_conn.execute("SELECT status FROM documents WHERE file_path = ?", (sample_doc,)).fetchone()
    assert row["status"] == "removed"

    matches = vector_store.query(db_conn, "SQLCipher", threshold=0.1, top_k=3)
    assert matches == []


def test_delete_nonexistent_document_returns_false(db_conn):
    assert vector_store.delete_document(db_conn, "/no/such/file.txt") is False


def test_list_documents_only_returns_active(db_conn, sample_doc):
    vector_store.ingest_document(db_conn, sample_doc)
    vector_store.delete_document(db_conn, sample_doc)
    assert vector_store.list_documents(db_conn) == []


def test_rebuild_from_sqlite_reingests_active_documents(db_conn, sample_doc):
    vector_store.ingest_document(db_conn, sample_doc)
    # Simulate ChromaDB drift: clear the collection directly without touching SQLite.
    vector_store._get_collection().delete(where={"file_path": sample_doc})
    assert vector_store.query(db_conn, "SQLCipher", threshold=0.1, top_k=3) == []

    result = vector_store.rebuild_from_sqlite(db_conn)
    assert sample_doc in result["rebuilt"]
    assert result["failed"] == []
    assert len(vector_store.query(db_conn, "SQLCipher", threshold=0.1, top_k=3)) >= 1


def test_rebuild_puts_back_a_deleted_file_from_the_stored_copy(db_conn, sample_doc):
    """
    This test used to assert the opposite, and the change is the feature.

    Deleting the file used to cost the document: the rebuild looked for the
    recorded path, found nothing, and reported it failed. Ingestion now stores
    the bytes in document_blobs, so the rebuild writes the file back and
    re-embeds it - which is what makes a restored backup work on a machine that
    has never held these files, and incidentally makes an accidental deletion
    survivable on the machine that has.
    """
    vector_store.ingest_document(db_conn, sample_doc)
    os.remove(sample_doc)

    result = vector_store.rebuild_from_sqlite(db_conn)

    assert os.path.exists(sample_doc), "the file was not put back"
    assert sample_doc in result["rebuilt"]
    assert result["failed"] == []
    assert len(vector_store.query(db_conn, "SQLCipher", threshold=0.1, top_k=3)) >= 1


def test_rebuild_still_reports_a_document_with_no_stored_copy(db_conn, sample_doc):
    """
    The case that genuinely cannot be recovered, and must still be reported:
    a document ingested before document_blobs existed, whose file has since
    gone. Nothing holds its content, so the rebuild has nothing to work from.

    Worth keeping as its own test rather than deleting with the old one - the
    failure path still exists, and a rebuild that silently reported success for
    a document it could not embed would be worse than the behaviour this
    replaced.
    """
    vector_store.ingest_document(db_conn, sample_doc)
    db_conn.execute("DELETE FROM document_blobs")
    db_conn.commit()
    os.remove(sample_doc)

    result = vector_store.rebuild_from_sqlite(db_conn)

    assert result["rebuilt"] == []
    assert len(result["failed"]) == 1
    assert result["failed"][0]["file_path"] == sample_doc


def test_a_rebuild_does_not_disturb_documents_whose_files_are_present(db_conn, sample_doc):
    """
    The restraint that makes materialise_documents safe to run inside every
    rebuild, including on the machine that ingested the files.

    An earlier version repointed every document at this machine's documents
    directory whether or not anything was missing - which rewrote working paths,
    and, because the documents root was not isolated in the test suite, wrote a
    file into the developer's real data/documents/.
    """
    vector_store.ingest_document(db_conn, sample_doc)
    before = db_conn.execute("SELECT file_path FROM documents").fetchone()["file_path"]

    result = vector_store.rebuild_from_sqlite(db_conn)

    after = db_conn.execute("SELECT file_path FROM documents").fetchone()["file_path"]
    assert after == before, "a path that was already valid was rewritten"
    assert result["materialised"] == []


def test_unsupported_extension_raises(db_conn, isolated_documents_root):
    bad_file = isolated_documents_root / "notes.docx"
    bad_file.write_text("irrelevant", encoding="utf-8")
    with pytest.raises(ValueError):
        vector_store.ingest_document(db_conn, str(bad_file))


def test_oversized_document_raises(db_conn, isolated_documents_root):
    big_file = isolated_documents_root / "big.txt"
    big_file.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="exceeds max_document_size_mb"):
        vector_store.ingest_document(db_conn, str(big_file), max_document_size_mb=0)


def test_ingest_rejects_file_outside_documents_root(db_conn, tmp_path, isolated_documents_root):
    # Security regression test: file_path must resolve inside DOCUMENTS_ROOT.
    # Before this fix, ingest_document() would happily read and embed any
    # file the process could access, with no auth on the endpoint that calls
    # it - a full arbitrary local file read chained with exfiltration via
    # rag/query.
    outside_file = tmp_path / "outside_root.txt"
    outside_file.write_text("secret content that should never be embedded", encoding="utf-8")

    with pytest.raises(ValueError, match="must resolve inside"):
        vector_store.ingest_document(db_conn, str(outside_file))


def test_ingest_rejects_path_traversal_out_of_documents_root(db_conn, tmp_path, isolated_documents_root):
    outside_file = tmp_path / "outside_root.txt"
    outside_file.write_text("secret content", encoding="utf-8")
    traversal_path = isolated_documents_root / ".." / "outside_root.txt"

    with pytest.raises(ValueError, match="must resolve inside"):
        vector_store.ingest_document(db_conn, str(traversal_path))


def test_ingest_accepts_file_in_documents_root_subdirectory(db_conn, isolated_documents_root):
    subdir = isolated_documents_root / "project_notes"
    subdir.mkdir()
    doc_path = subdir / "notes.txt"
    doc_path.write_text("Notes about the RAG pipeline and SQLCipher.", encoding="utf-8")

    result = vector_store.ingest_document(db_conn, str(doc_path))
    assert result["status"] == "ingested"


# --- Encryption at rest (PIP_DB_KEY set) ---


def test_ingest_encrypts_chunk_text_and_file_path_on_disk(db_conn, sample_doc, monkeypatch, db_key):
    # Security regression test: ChromaDB used to store chunk text and
    # file_path in plaintext regardless of whether the main SQLite DB was
    # SQLCipher-encrypted. With PIP_DB_KEY set, the raw values Chroma actually
    # persists must never contain the plaintext content or path.
    monkeypatch.setenv("PIP_DB_KEY", db_key)

    vector_store.ingest_document(db_conn, sample_doc)

    raw = vector_store._get_collection().get(include=["documents", "metadatas"])
    assert raw["documents"], "expected at least one stored chunk"
    for doc in raw["documents"]:
        assert "ChromaDB" not in doc
        assert "SQLCipher" not in doc
    for meta in raw["metadatas"]:
        assert "file_path" not in meta  # only the encrypted file_path_enc should be present
        assert sample_doc not in meta["file_path_enc"]
        assert "file_key" in meta


def test_query_decrypts_chunk_text_and_file_path(db_conn, sample_doc, monkeypatch, db_key):
    monkeypatch.setenv("PIP_DB_KEY", db_key)

    vector_store.ingest_document(db_conn, sample_doc)
    matches = vector_store.query(db_conn, "Is ChromaDB the source of truth?", threshold=0.1, top_k=3)

    assert len(matches) >= 1
    assert any("ChromaDB" in m["chunk_text"] for m in matches)
    assert all(m["file_path"] == sample_doc for m in matches)


def test_delete_document_works_under_encryption(db_conn, sample_doc, monkeypatch, db_key):
    monkeypatch.setenv("PIP_DB_KEY", db_key)

    vector_store.ingest_document(db_conn, sample_doc)
    assert vector_store.delete_document(db_conn, sample_doc) is True

    matches = vector_store.query(db_conn, "SQLCipher", threshold=0.1, top_k=3)
    assert matches == []


def test_reingest_changed_file_replaces_chunks_under_encryption(db_conn, isolated_documents_root, monkeypatch, db_key):
    monkeypatch.setenv("PIP_DB_KEY", db_key)

    doc_path = isolated_documents_root / "notes.txt"
    doc_path.write_text("Original content about FastAPI.", encoding="utf-8")
    vector_store.ingest_document(db_conn, str(doc_path))

    doc_path.write_text("Completely different content about Neovim.", encoding="utf-8")
    vector_store.ingest_document(db_conn, str(doc_path))

    matches = vector_store.query(db_conn, "Neovim", threshold=0.1, top_k=5)
    assert any("Neovim" in m["chunk_text"] for m in matches)
    matches_old = vector_store.query(db_conn, "FastAPI", threshold=0.5, top_k=5)
    assert matches_old == [] or all("FastAPI" not in m["chunk_text"] for m in matches_old)


def test_query_skips_chunks_from_a_different_key_without_crashing(db_conn, sample_doc, monkeypatch, db_key):
    # Simulates the mixed-schema edge case: chunks ingested under one key (or
    # no key at all) still sitting in Chroma when PIP_DB_KEY changes. The read
    # path must degrade to "skip that chunk" rather than raise.
    vector_store.ingest_document(db_conn, sample_doc)  # ingested with no key (plaintext schema)

    monkeypatch.setenv("PIP_DB_KEY", db_key)
    matches = vector_store.query(db_conn, "Is ChromaDB the source of truth?", threshold=0.1, top_k=3)
    assert matches == []


def test_rejects_non_hex_db_key(db_conn, sample_doc, monkeypatch):
    monkeypatch.setenv("PIP_DB_KEY", "not-hex!!")
    with pytest.raises(ValueError, match="hex-encoded"):
        vector_store.ingest_document(db_conn, sample_doc)


def test_rag_tunables_come_from_settings_not_from_duplicated_literals():
    """
    These were restated as Python defaults in vector_store and again in
    stage_05, so editing config/settings.json changed nothing - the silent kind
    of broken, since a config file read by no one still looks authoritative.
    """
    from backend.config.settings import get_settings

    rag = get_settings()["rag"]
    assert vector_store.SUPPORTED_EXTENSIONS == set(rag["supported_extensions"])
    assert vector_store.DEFAULT_CHUNK_SIZE_TOKENS == rag["chunk_size_tokens"]
    assert vector_store.DEFAULT_CHUNK_OVERLAP_TOKENS == rag["chunk_overlap_tokens"]
    assert vector_store.DEFAULT_SIMILARITY_THRESHOLD == rag["similarity_threshold"]
    assert vector_store.DEFAULT_TOP_K == rag["top_k_results"]
    assert vector_store.DEFAULT_MAX_DOCUMENT_SIZE_MB == rag["max_document_size_mb"]


# --- how the embedding model is loaded --------------------------------------
# Loading it used to contact the HuggingFace Hub on every call to check a model
# that is pinned by name and already cached. Measured on the dev machine: 87.22s
# with that check, 0.24s without - the weights themselves read in under a
# second. It is also an outbound call a local-first application should not be
# making at all.


def test_model_is_loaded_from_local_disk(monkeypatch):
    """The normal path: no network, whatever the network is doing."""
    calls = []

    class FakeModel:
        def __init__(self, name, device=None, local_files_only=False):
            calls.append(local_files_only)

    monkeypatch.setattr(vector_store, "_model", None)
    monkeypatch.setattr(vector_store, "SentenceTransformer", FakeModel)

    vector_store._get_model()

    assert calls == [True], "the model must be requested offline first"


def test_a_missing_cache_falls_back_to_downloading_once(monkeypatch):
    """
    The branch that keeps a fresh clone working. Without it, offline-first would
    turn "model not downloaded yet" into a hard failure on first run.
    """
    calls = []

    class FakeModel:
        def __init__(self, name, device=None, local_files_only=False):
            calls.append(local_files_only)
            if local_files_only:
                raise OSError("not in the local cache")

    monkeypatch.setattr(vector_store, "_model", None)
    monkeypatch.setattr(vector_store, "SentenceTransformer", FakeModel)

    vector_store._get_model()

    assert calls == [True, False], "offline first, then one real download"


def test_the_model_is_loaded_once_per_process(monkeypatch):
    calls = []

    class FakeModel:
        def __init__(self, name, device=None, local_files_only=False):
            calls.append(local_files_only)

    monkeypatch.setattr(vector_store, "_model", None)
    monkeypatch.setattr(vector_store, "SentenceTransformer", FakeModel)

    vector_store._get_model()
    vector_store._get_model()
    vector_store._get_model()

    assert len(calls) == 1


# --- Consistency check / rebuild-on-mismatch trigger ------------------------
#
# The regression these cover is not "the rebuild is broken" - it never was.
# It is "nothing calls the rebuild", which no test could fail on while every
# test invoked it by hand. check_consistency() is the piece that turns an
# emptied index from a silent condition into a detectable one.


def test_consistency_check_passes_on_a_freshly_ingested_document(db_conn, sample_doc):
    vector_store.ingest_document(db_conn, sample_doc)

    report = vector_store.check_consistency(db_conn)

    assert report["ok"] is True
    assert report["drifted"] == []
    assert report["indexed"] == report["expected"] > 0


def test_consistency_check_reports_an_emptied_index(db_conn, sample_doc):
    """
    The live failure, reproduced: SQLite still lists the document with its
    chunk_count, ChromaDB holds nothing, and query() returns empty without
    complaining - which is indistinguishable from a question no document
    answers, and is why this went unnoticed for two days in real use.
    """
    vector_store.ingest_document(db_conn, sample_doc)
    expected = vector_store.list_documents(db_conn)[0]["chunk_count"]
    vector_store._get_collection().delete(where={"file_path": sample_doc})

    report = vector_store.check_consistency(db_conn)

    assert report["ok"] is False
    assert report["indexed"] == 0
    assert report["expected"] == expected
    assert report["drifted"] == [
        {"file_path": sample_doc, "expected": expected, "indexed": 0}
    ]


def test_consistency_check_is_quiet_when_nothing_is_registered(db_conn):
    assert vector_store.check_consistency(db_conn) == {
        "documents": 0, "indexed": 0, "expected": 0, "drifted": [], "ok": True
    }


def test_rebuild_if_drifted_repairs_an_emptied_index(db_conn, sample_doc):
    vector_store.ingest_document(db_conn, sample_doc)
    vector_store._get_collection().delete(where={"file_path": sample_doc})

    report = vector_store.rebuild_if_drifted(db_conn)

    assert report["ok"] is False  # what was FOUND, before the repair
    assert sample_doc in report["rebuild"]["rebuilt"]
    assert vector_store.check_consistency(db_conn)["ok"] is True
    assert len(vector_store.query(db_conn, "SQLCipher", threshold=0.1, top_k=3)) >= 1


def test_rebuild_if_drifted_does_nothing_when_the_index_agrees(db_conn, sample_doc, monkeypatch):
    """
    A startup check that re-embeds every document on every launch would be a
    different bug wearing this one's clothes.
    """
    vector_store.ingest_document(db_conn, sample_doc)
    called = []
    monkeypatch.setattr(vector_store, "rebuild_from_sqlite", lambda conn: called.append(conn))

    report = vector_store.rebuild_if_drifted(db_conn)

    assert report["ok"] is True
    assert "rebuild" not in report
    assert called == []


def test_a_chunk_written_under_another_key_counts_as_missing(db_conn, sample_doc, monkeypatch, db_key):
    """
    Precisely this installation's case. Chunks ingested before PIP_DB_KEY was
    set are unreadable once it is, so retrieval sees nothing - and the check
    has to agree with retrieval, not with the raw row count, or a rebuild that
    is genuinely needed never fires.
    """
    vector_store.ingest_document(db_conn, sample_doc)  # plaintext, no key
    assert vector_store.check_consistency(db_conn)["ok"] is True

    monkeypatch.setenv("PIP_DB_KEY", db_key)

    assert vector_store.check_consistency(db_conn)["ok"] is False
    vector_store.rebuild_if_drifted(db_conn)
    assert vector_store.check_consistency(db_conn)["ok"] is True


# --- Project scoping -------------------------------------------------------
#
# The second wall in front of this installation's documents, and the quieter
# one: the index can be perfectly healthy and still answer nothing, because
# every chunk was filed under no project while chat ran scoped to one.


@pytest.fixture
def projects(db_conn):
    """
    Two real projects. documents.project_id is a foreign key onto
    active_projects, so a made-up id is rejected at ingest - the scoping tests
    have to file documents under projects that exist.
    """
    from backend.memory.profile_store import create_project

    return (
        create_project(db_conn, "Alpha"),
        create_project(db_conn, "Beta"),
    )


@pytest.fixture
def project_doc(isolated_documents_root):
    doc_path = isolated_documents_root / "roadmap.txt"
    doc_path.write_text(
        "The migration to FastAPI is scheduled for the second sprint.",
        encoding="utf-8",
    )
    return str(doc_path)


def test_an_unfiled_document_is_reachable_from_a_scoped_query(db_conn, sample_doc):
    """
    The live failure. Uploading happens on a screen with no project picker, so
    "no project" is what most documents get; scoping it out made PIP unable to
    read its own reference material the moment a project was activated.
    """
    vector_store.ingest_document(db_conn, sample_doc)  # no project_id

    matches = vector_store.query(
        db_conn, "SQLCipher", project_id="proj-a", threshold=0.1, top_k=3
    )

    assert len(matches) >= 1


def test_another_projects_document_stays_out_of_scope(db_conn, sample_doc, project_doc, projects):
    """
    The half that must NOT change: unfiled is not a wildcard in both
    directions. A document filed under one project stays out of another's
    retrieval.
    """
    alpha, beta = projects
    vector_store.ingest_document(db_conn, sample_doc, project_id=alpha)
    vector_store.ingest_document(db_conn, project_doc, project_id=beta)

    # Deliberately the text of BETA's document. Asserting only that it is
    # absent would pass for the wrong reason if it simply scored too low, so
    # the same query is run unscoped first to establish that it does retrieve
    # beta's document - leaving the project filter as the only thing that can
    # account for its absence in the scoped call.
    question = "FastAPI migration second sprint"
    unscoped = vector_store.query(db_conn, question, threshold=0.1, top_k=5)
    assert project_doc in [m["file_path"] for m in unscoped]

    scoped = vector_store.query(db_conn, question, project_id=alpha, threshold=0.1, top_k=5)
    assert project_doc not in [m["file_path"] for m in scoped]


def test_a_scoped_query_reaches_its_own_project_and_the_unfiled_together(
    db_conn, sample_doc, project_doc, projects
):
    alpha, _ = projects
    vector_store.ingest_document(db_conn, sample_doc)  # unfiled
    vector_store.ingest_document(db_conn, project_doc, project_id=alpha)

    found = {
        m["file_path"]
        for m in vector_store.query(
            db_conn, "FastAPI and SQLCipher", project_id=alpha, threshold=0.1, top_k=10
        )
    }

    assert found == {sample_doc, project_doc}


def test_an_unscoped_query_is_unchanged_and_sees_everything(db_conn, sample_doc, project_doc, projects):
    _, beta = projects
    vector_store.ingest_document(db_conn, sample_doc)
    vector_store.ingest_document(db_conn, project_doc, project_id=beta)

    found = {
        m["file_path"]
        for m in vector_store.query(
            db_conn, "FastAPI and SQLCipher", threshold=0.1, top_k=10
        )
    }

    assert found == {sample_doc, project_doc}
