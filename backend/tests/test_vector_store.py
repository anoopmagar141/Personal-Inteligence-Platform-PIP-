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


def test_rebuild_reports_missing_file_as_failed(db_conn, sample_doc, tmp_path):
    vector_store.ingest_document(db_conn, sample_doc)
    import os
    os.remove(sample_doc)

    result = vector_store.rebuild_from_sqlite(db_conn)
    assert result["rebuilt"] == []
    assert len(result["failed"]) == 1
    assert result["failed"][0]["file_path"] == sample_doc


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
