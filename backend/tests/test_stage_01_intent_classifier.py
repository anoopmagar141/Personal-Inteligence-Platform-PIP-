import pytest

from backend.memory.profile_store import get_connection, initialize_schema
from backend.stages import stage_01_intent_classifier as intent


@pytest.fixture
def db_conn(tmp_path, db_key):
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path, db_key=db_key)
    initialize_schema(conn)
    yield conn
    conn.close()


def test_general_knowledge_default_skips_rag():
    result = intent.run("What is the capital of France?")
    assert result["category"] == "general_knowledge"
    assert result["skip_rag"] is True


def test_project_continuation():
    result = intent.run("Let's continue where we left off")
    assert result["category"] == "project_continuation"
    assert result["skip_rag"] is False


def test_external_information_keyword():
    result = intent.run("What's the latest news on the election?")
    assert result["category"] == "external_information"
    assert result["skip_rag"] is False


def test_coding_question():
    result = intent.run("Can you help me debug this function?")
    assert result["category"] == "coding_question"


def test_research_request():
    result = intent.run("Can you research FastAPI vs Flask for me?")
    assert result["category"] == "research_request"


def test_personal_question():
    result = intent.run("What did I say my favorite editor was?")
    assert result["category"] == "personal_question"
    assert result["skip_rag"] is False


def test_technical_explanation_skips_rag_with_no_project_terms():
    result = intent.run("Explain how a hash table works")
    assert result["category"] == "technical_explanation"
    assert result["skip_rag"] is True


def test_technical_explanation_does_not_skip_rag_with_project_terms(db_conn):
    db_conn.execute(
        "INSERT INTO active_projects (project_id, name, description, status, last_active) "
        "VALUES ('p1', 'InventorySync', 'sync service', 'active', '2026-01-01T00:00:00Z')"
    )
    db_conn.commit()

    result = intent.run("Explain how InventorySync handles retries", conn=db_conn)
    assert result["category"] == "project_question"  # project match takes priority over technical_explanation
    assert result["skip_rag"] is False


def test_project_question_via_active_project_name(db_conn):
    db_conn.execute(
        "INSERT INTO active_projects (project_id, name, description, status, last_active) "
        "VALUES ('p1', 'InventorySync', 'sync service', 'active', '2026-01-01T00:00:00Z')"
    )
    db_conn.commit()

    result = intent.run("How is InventorySync coming along?", conn=db_conn)
    assert result["category"] == "project_question"
    assert result["skip_rag"] is False


def test_project_question_via_decision_log_keyword_overlap(db_conn):
    db_conn.execute(
        "INSERT INTO decision_log (decision_text, confidence, state, created_at) "
        "VALUES ('We chose FastAPI for the inventory service', 0.7, 'active', '2026-01-01T00:00:00Z')"
    )
    db_conn.commit()

    result = intent.run("Why did we pick FastAPI again?", conn=db_conn)
    assert result["category"] == "project_question"


def test_decision_keyword_overlap_ignores_short_stopwords(db_conn):
    db_conn.execute(
        "INSERT INTO decision_log (decision_text, confidence, state, created_at) "
        "VALUES ('We will use it for the new service', 0.7, 'active', '2026-01-01T00:00:00Z')"
    )
    db_conn.commit()

    # Only shares short/stopword-length tokens ("use", "the", "for", "it") with the
    # decision text above - must not count as a project match.
    result = intent.run("What is the weather like today", conn=db_conn)
    assert result["category"] == "external_information"


def test_retrieval_hint_is_bounded():
    long_message = " ".join(f"word{i}" for i in range(30))
    result = intent.run(long_message)
    assert len(result["retrieval_hint"].split()) == 12


def test_fails_open_when_conn_raises():
    class BoomConn:
        def execute(self, *args, **kwargs):
            raise RuntimeError("simulated DB failure")

    result = intent.run("How is InventorySync going?", conn=BoomConn())
    # active_projects/decision_log lookups fail open to no-match, classifier still runs
    assert result["category"] in intent.CATEGORIES
    assert isinstance(result["skip_rag"], bool)
