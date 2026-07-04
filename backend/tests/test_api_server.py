import sqlite3

import pytest

from backend.api import server
from backend.memory import profile_store


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "pip.db"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    profile_store.initialize_schema(connection)
    yield connection
    connection.close()


def test_status_and_onboarding_api(conn):
    assert server.api_status(conn)["onboarding_complete"] is False

    result = server.api_complete_onboarding(
        conn,
        {
            "name": "BatMan",
            "language_preference": "English",
            "skills": ["Python"],
            "preferred_tools": ["Git"],
        },
    )

    assert result == {"message": "Setup complete. PIP is ready."}
    assert server.api_status(conn)["onboarding_complete"] is True
    fields = {row["field"]: row for row in server.api_get_profile(conn)}
    assert fields["Python"]["table"] == "skill_memory"


def test_memory_crud_api(conn):
    server.api_complete_onboarding(conn, {"name": "BatMan", "language_preference": "English"})

    assert server.api_correct_memory(conn, {"field": "answer_depth", "value": "brief"}) == {"status": "updated"}
    assert server.api_get_profile_field(conn, "answer_depth")["value"] == "brief"
    assert server.api_delete_profile_field(conn, "answer_depth") == {
        "status": "deleted",
        "field": "answer_depth",
    }
    assert server.api_get_profile_field(conn, "answer_depth") is None


def test_decision_and_pending_api(conn):
    logged = server.api_create_decision(conn, {"text": "We decided to keep REST CRUD only."})
    assert logged["status"] == "logged"

    matches = server.api_search_decisions(conn, q="REST")
    assert len(matches) == 1

    updated = server.api_update_decision_state(
        conn,
        logged["decision_id"],
        {"state": "abandoned", "reason": "Superseded by API split."},
    )
    assert updated["status"] == "updated"
    assert server.api_search_decisions(conn, state="active") == []

    pending = server.api_create_decision(conn, {"text": "REST CRUD"})
    assert pending["status"] == "pending"
    assert len(server.api_get_pending(conn)) == 1

    promoted = server.api_promote_pending(conn, pending["candidate_id"])
    assert promoted["status"] == "promoted"
    assert server.api_get_pending(conn) == []


def test_project_api(conn):
    project = server.api_create_project(conn, {"name": "PIP", "description": "Final year project"})
    projects = server.api_list_projects(conn)

    assert projects[0]["project_id"] == project["project_id"]
    assert server.api_update_project_status(conn, project["project_id"], {"status": "archived"})["status"] == "updated"
    assert server.api_activate_project(conn, project["project_id"])["status"] == "active"
