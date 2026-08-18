import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.api import server
from backend.memory import profile_store, vector_store


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "pip.db"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    profile_store.initialize_schema(connection)
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def isolated_chroma(tmp_path, monkeypatch):
    monkeypatch.setattr(vector_store, "CHROMA_DB_PATH", str(tmp_path / "chroma"))
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(vector_store, "_collection", None)
    yield


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


def test_providers_api(conn):
    providers = {p["provider_id"]: p for p in server.api_list_providers(conn)}
    assert providers["ollama"]["is_cloud"] is False
    assert providers["web_search"]["is_cloud"] is True

    # Regression test: is_cloud/user_consented/revoked are stored as SQLite
    # INTEGER (0/1) - SQLite has no native boolean type - so the driver hands
    # them back as Python int unless api_list_providers explicitly coerces.
    # config/provider_consent.json's own test suite (test_provider_consent.py)
    # locks "is_cloud is a native JSON boolean" as a contract, but only against
    # the seed file, never against this actual API response - the two had
    # silently diverged (int 0/1 shipped over the wire as JSON numbers, not
    # booleans) until a strict client (the Flutter client's `== true` checks,
    # which JS's truthy coercion in the web client had been masking) caught it
    # live. `is` (not `==`) here specifically rejects 0/1 masquerading as bool.
    for provider in providers.values():
        assert provider["is_cloud"] in (True, False)
        assert provider["user_consented"] in (True, False)
        assert provider["revoked"] in (True, False)

    granted = server.api_grant_consent(conn, "web_search", "full_inference")
    assert granted["status"] == "consented"
    providers = {p["provider_id"]: p for p in server.api_list_providers(conn)}
    assert providers["web_search"]["user_consented"] is True
    assert providers["web_search"]["revoked"] is False

    revoked = server.api_revoke_consent(conn, "web_search")
    assert revoked["status"] == "revoked"
    providers = {p["provider_id"]: p for p in server.api_list_providers(conn)}
    assert providers["web_search"]["revoked"] is True


def test_cors_allows_local_clients_on_other_ports(tmp_path, monkeypatch):
    # Regression test: any client served from a different origin than this
    # server - e.g. `flutter run -d web-server` on its own port, unlike the
    # HTML/JS web client, which is same-origin via the StaticFiles mount -
    # needs CORS headers or a real browser's fetch() fails outright with
    # "Failed to fetch", no matter how trusted the target is. Found live: the
    # Flutter web client got exactly that error hitting GET /status from a
    # different port. TestClient simulates a real browser request (sends a
    # real Origin header, checks the real response headers), unlike
    # tool/validate_live.dart's Dart-VM-based validation, which passed
    # cleanly precisely because CORS is a browser-only mechanism the VM
    # doesn't enforce - this is the missing link for a browser client.
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)

    client = TestClient(server.app)
    response = client.get("/api/v1/status", headers={"Origin": "http://127.0.0.1:8091"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:8091"


def test_rag_api(conn, tmp_path):
    doc = tmp_path / "notes.txt"
    doc.write_text("PIP uses SQLCipher for encrypted storage.", encoding="utf-8")

    ingested = server.api_ingest_document(conn, {"file_path": str(doc)})
    assert ingested["status"] == "ingested"

    docs = server.api_list_documents(conn)
    assert len(docs) == 1
    assert docs[0]["file_path"] == str(doc)

    matches = server.api_query_rag(conn, {"query": "encrypted storage", "threshold": 0.1})
    assert len(matches) >= 1

    removed = server.api_delete_document(conn, str(doc))
    assert removed["status"] == "removed"
    assert server.api_list_documents(conn) == []


def test_rag_api_missing_file_path_raises(conn):
    with pytest.raises(ValueError):
        server.api_ingest_document(conn, {})


def test_rag_api_missing_query_raises(conn):
    with pytest.raises(ValueError):
        server.api_query_rag(conn, {})


def test_rag_api_delete_nonexistent_raises(conn):
    with pytest.raises(ValueError):
        server.api_delete_document(conn, "/no/such/file.txt")
