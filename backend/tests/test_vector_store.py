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
    yield


@pytest.fixture
def sample_doc(tmp_path):
    doc_path = tmp_path / "notes.txt"
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


def test_reingest_changed_file_replaces_chunks(db_conn, tmp_path):
    doc_path = tmp_path / "notes.txt"
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


def test_rebuild_reports_missing_file_as_failed(db_conn, sample_doc, tmp_path):
    vector_store.ingest_document(db_conn, sample_doc)
    import os
    os.remove(sample_doc)

    result = vector_store.rebuild_from_sqlite(db_conn)
    assert result["rebuilt"] == []
    assert len(result["failed"]) == 1
    assert result["failed"][0]["file_path"] == sample_doc


def test_unsupported_extension_raises(db_conn, tmp_path):
    bad_file = tmp_path / "notes.docx"
    bad_file.write_text("irrelevant", encoding="utf-8")
    with pytest.raises(ValueError):
        vector_store.ingest_document(db_conn, str(bad_file))


def test_oversized_document_raises(db_conn, tmp_path):
    big_file = tmp_path / "big.txt"
    big_file.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="exceeds max_document_size_mb"):
        vector_store.ingest_document(db_conn, str(big_file), max_document_size_mb=0)
