import pytest
from backend.memory import vector_store
from backend.memory.profile_store import get_connection, initialize_schema
from backend.stages import stage_05_rag_retrieval as stage_05


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


def test_run_returns_empty_when_no_documents_ingested(db_conn):
    result = stage_05.run(db_conn, "anything")
    assert result == {"chunks": [], "conflict_flag": False}


def test_run_returns_matching_chunks(db_conn, tmp_path):
    doc = tmp_path / "notes.txt"
    doc.write_text("We chose FastAPI over Flask for async support.", encoding="utf-8")
    vector_store.ingest_document(db_conn, str(doc))

    result = stage_05.run(db_conn, "Why FastAPI?", threshold=0.1)
    assert len(result["chunks"]) >= 1


def test_run_flags_conflict_when_chunk_overlaps_active_decision(db_conn, tmp_path):
    db_conn.execute(
        "INSERT INTO decision_log (decision_text, reasoning, confidence, state, created_at) "
        "VALUES ('We chose FastAPI for the inventory service', 'async support needed', 0.7, 'active', '2026-01-01T00:00:00Z')"
    )
    db_conn.commit()

    doc = tmp_path / "notes.txt"
    doc.write_text("The inventory service actually ended up using Flask instead of FastAPI in production.", encoding="utf-8")
    vector_store.ingest_document(db_conn, str(doc))

    result = stage_05.run(db_conn, "inventory service framework", threshold=0.1)
    assert result["conflict_flag"] is True


def test_run_no_conflict_when_no_overlap(db_conn, tmp_path):
    db_conn.execute(
        "INSERT INTO decision_log (decision_text, reasoning, confidence, state, created_at) "
        "VALUES ('We chose FastAPI for the inventory service', 'async support needed', 0.7, 'active', '2026-01-01T00:00:00Z')"
    )
    db_conn.commit()

    doc = tmp_path / "notes.txt"
    doc.write_text("Neovim's modal editing took about a week to get used to.", encoding="utf-8")
    vector_store.ingest_document(db_conn, str(doc))

    result = stage_05.run(db_conn, "Neovim editing experience", threshold=0.1)
    assert result["conflict_flag"] is False


def test_run_fails_open_on_vector_store_error(db_conn, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("simulated ChromaDB failure")

    monkeypatch.setattr(stage_05.vector_store, "query", _boom)
    result = stage_05.run(db_conn, "anything")
    assert result == {"chunks": [], "conflict_flag": False}
