import sqlite3

import pytest

from backend.memory import profile_store


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "pip.db"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    profile_store.initialize_schema(connection)
    yield connection
    connection.close()


def test_get_connection_rejects_non_hex_db_key(tmp_path):
    # Security regression test: this used to be `assert re.fullmatch(...)`,
    # which python -O/-OO strip out entirely, silently letting a non-hex
    # db_key reach the f-string-built PRAGMA key statement unchecked.
    with pytest.raises(ValueError, match="hex-encoded"):
        profile_store.get_connection(str(tmp_path / "pip.db"), db_key="not-hex!!")


def test_onboarding_writes_identity_profile_and_completion_flag(conn):
    message = profile_store.complete_onboarding(
        conn,
        name="BatMan",
        language_preference="English",
        timezone=None,
        current_project={"name": "PIP", "description": "Personal Intelligence Platform"},
        skills=["Python", "AI", "Databases", "Ignored"],
        interaction_style=None,
        preferred_tools=["VS Code", "Git", "Ollama", "SQLite", "pytest", "Ignored"],
    )

    assert message == "Setup complete. PIP is ready."
    identity = conn.execute("SELECT * FROM identity WHERE id = 1").fetchone()
    assert identity["name"] == "BatMan"
    assert identity["language_preference"] == "English"
    assert identity["timezone"] == profile_store.DEFAULT_TIMEZONE

    meta = conn.execute("SELECT * FROM profile_meta WHERE id = 1").fetchone()
    assert meta["onboarding_complete"] == 1
    assert meta["first_session_date"] is not None

    assert conn.execute("SELECT COUNT(*) FROM skill_memory").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM preferred_tools").fetchone()[0] == 5
    style = conn.execute("SELECT * FROM interaction_style WHERE id = 1").fetchone()
    assert style["value"] == profile_store.DEFAULT_INTERACTION_STYLE


def test_profile_view_includes_confidence_and_source_label(conn):
    profile_store.complete_onboarding(
        conn,
        name="BatMan",
        language_preference="English",
        skills=["Python"],
        interaction_style="Brief summary first",
        preferred_tools=["Git"],
    )

    profile = profile_store.get_profile(conn)
    fields = {row["field"]: row for row in profile}

    assert fields["name"]["confidence"] == 1.0
    assert fields["name"]["source_label"] == "explicit"
    assert fields["Python"]["table"] == "skill_memory"
    assert fields["Python"]["source_label"] == "explicit"
    assert fields["interaction_style"]["value"] == "Brief summary first"


def test_profile_correction_and_soft_delete(conn):
    profile_store.complete_onboarding(
        conn,
        name="BatMan",
        language_preference="English",
        skills=["Python"],
    )

    profile_store.correct_profile_field(conn, "answer_depth", "brief")
    corrected = profile_store.get_profile_field(conn, "answer_depth")
    assert corrected["value"] == "brief"
    assert corrected["source_label"] == "user_correction"

    assert profile_store.soft_delete_profile_field(conn, "Python") is True
    assert profile_store.get_profile_field(conn, "Python") is None


def test_identity_fields_are_immutable_after_onboarding(conn):
    profile_store.complete_onboarding(conn, name="BatMan", language_preference="English")

    with pytest.raises(ValueError):
        profile_store.correct_profile_field(conn, "name", "Bruce")
    with pytest.raises(ValueError):
        profile_store.soft_delete_profile_field(conn, "timezone")


def test_profile_write_interrupted_before_commit_reopens_with_prewrite_state(tmp_path, db_key):
    db_path = tmp_path / "pip.db"
    conn = profile_store.get_connection(str(db_path), db_key=db_key)
    profile_store.initialize_schema(conn)
    profile_store.complete_onboarding(conn, name="BatMan", language_preference="English")
    profile_store.correct_profile_field(conn, "answer_depth", "brief")
    conn.close()

    raw_conn = profile_store.get_connection(str(db_path), db_key=db_key)

    class CrashBeforeCommitConnection:
        def __init__(self, wrapped):
            self.wrapped = wrapped

        def execute(self, *args, **kwargs):
            return self.wrapped.execute(*args, **kwargs)

        def commit(self):
            raise RuntimeError("simulated crash before final commit")

    with pytest.raises(RuntimeError, match="simulated crash"):
        profile_store.correct_profile_field(
            CrashBeforeCommitConnection(raw_conn),
            "answer_depth",
            "full detail",
        )
    raw_conn.close()

    reopened = profile_store.get_connection(str(db_path), db_key=db_key)
    try:
        field = profile_store.get_profile_field(reopened, "answer_depth")
        assert field["value"] == "brief"
        assert field["source_label"] == "user_correction"
        assert reopened.execute(
            "SELECT COUNT(*) FROM preference_memory WHERE name = ?",
            ("answer_depth",),
        ).fetchone()[0] == 1
    finally:
        reopened.close()
