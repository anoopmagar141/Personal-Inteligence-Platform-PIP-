import pytest

from backend.memory.profile_store import get_connection, initialize_schema
from backend.stages import stage_04_memory_lookup as stage_04


@pytest.fixture
def db_conn(tmp_path, db_key):
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path, db_key=db_key)
    initialize_schema(conn)
    conn.execute("INSERT INTO identity (id, name, language_preference, timezone) VALUES (1, 'Alice', 'en-US', 'UTC')")
    conn.execute(
        "INSERT INTO preference_memory (name, value, evidence_count, source_label, status) "
        "VALUES ('editor', 'Neovim', 3, 'explicit', 'active')"
    )
    conn.execute(
        "INSERT INTO skill_memory (name, level, evidence_count, source_label, status) "
        "VALUES ('python_level', 0.8, 3, 'explicit', 'active')"
    )
    conn.execute(
        "INSERT INTO active_projects (project_id, name, description, status, last_active) "
        "VALUES ('p1', 'InventorySync', 'sync service', 'active', '2026-01-01T00:00:00Z')"
    )
    conn.execute("INSERT INTO interaction_style (id, value, evidence_count, source_label) VALUES (1, 'concise', 3, 'explicit')")
    conn.commit()
    yield conn
    conn.close()


def test_personal_question_returns_only_relevant_tables(db_conn):
    result = stage_04.run(db_conn, "personal_question")
    tables = {row["table"] for row in result}
    # active_projects is included here now (found live: "summarize my
    # project" lands in personal_question via the bare "my" match, and needs
    # real project data too, not just identity/preferences/skills).
    assert tables <= {"identity", "preference_memory", "interaction_style", "skill_memory", "active_projects"}
    assert "goal_memory" not in tables


def test_project_question_returns_only_relevant_tables(db_conn):
    result = stage_04.run(db_conn, "project_question")
    tables = {row["table"] for row in result}
    assert tables <= {"active_projects", "goal_memory", "interaction_style"}
    assert "skill_memory" not in tables
    assert "identity" not in tables


def test_never_returns_full_profile_dump(db_conn):
    full_profile = stage_04.profile_store.get_profile(db_conn)
    result = stage_04.run(db_conn, "coding_question")
    assert len(result) < len(full_profile)


def test_unknown_category_falls_back_to_default_tables(db_conn):
    result = stage_04.run(db_conn, "totally_unrecognized_category")
    tables = {row["table"] for row in result}
    assert tables <= {"interaction_style"}


def test_fails_open_on_error(db_conn, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(stage_04.profile_store, "get_profile", _boom)
    assert stage_04.run(db_conn, "personal_question") == []
