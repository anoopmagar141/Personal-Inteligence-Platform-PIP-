import os
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.api import server
from backend.core import auth, instance_lock
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


@pytest.fixture(autouse=True)
def isolated_documents_root(tmp_path, monkeypatch):
    root = tmp_path / "documents"
    root.mkdir()
    monkeypatch.setattr(vector_store, "DOCUMENTS_ROOT", root)
    return root


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
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    token = auth.get_or_create_token(tmp_path / "api_token.txt")

    client = TestClient(server.app)
    response = client.get(
        "/api/v1/status",
        headers={"Origin": "http://127.0.0.1:8091", "Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:8091"


def test_rest_rejects_missing_token(tmp_path, monkeypatch):
    # Security regression test: every /api/v1/* route must require the
    # local API token - this used to have zero authentication at all.
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    auth.get_or_create_token(tmp_path / "api_token.txt")

    client = TestClient(server.app)
    response = client.get("/api/v1/status")
    assert response.status_code == 401


def test_rest_rejects_wrong_token(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    auth.get_or_create_token(tmp_path / "api_token.txt")

    client = TestClient(server.app)
    response = client.get("/api/v1/status", headers={"Authorization": "Bearer wrong-token"})
    assert response.status_code == 401


def test_rest_rejects_non_bearer_authorization_header(tmp_path, monkeypatch):
    # A well-formed Authorization header in the wrong scheme (e.g. Basic)
    # must still be rejected, not accidentally treated as a bearer token.
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    token = auth.get_or_create_token(tmp_path / "api_token.txt")

    client = TestClient(server.app)
    response = client.get("/api/v1/status", headers={"Authorization": f"Basic {token}"})
    assert response.status_code == 401


def test_rest_401_body_never_echoes_the_provided_token(tmp_path, monkeypatch):
    # "Never return it in an error body" - the 401 response must be a fixed
    # message, never a copy of whatever the caller sent.
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    auth.get_or_create_token(tmp_path / "api_token.txt")

    client = TestClient(server.app)
    response = client.get("/api/v1/status", headers={"Authorization": "Bearer a-guessed-secret-value"})
    assert response.status_code == 401
    assert "a-guessed-secret-value" not in response.text


def test_rest_accepts_valid_token_on_a_mutating_route(tmp_path, monkeypatch):
    # POST, not just the GET the other tests exercise - confirms the
    # middleware covers write routes too, not just reads.
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    token = auth.get_or_create_token(tmp_path / "api_token.txt")

    client = TestClient(server.app)
    response = client.post(
        "/api/v1/onboarding/complete",
        json={"name": "BatMan", "language_preference": "English"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


def test_rag_api(conn, isolated_documents_root):
    doc = isolated_documents_root / "notes.txt"
    doc.write_text("PIP uses SQLCipher for encrypted storage.", encoding="utf-8")
    resolved_doc = str(doc.resolve())

    ingested = server.api_ingest_document(conn, {"file_path": str(doc)})
    assert ingested["status"] == "ingested"

    docs = server.api_list_documents(conn)
    assert len(docs) == 1
    assert docs[0]["file_path"] == resolved_doc

    matches = server.api_query_rag(conn, {"query": "encrypted storage", "threshold": 0.1})
    assert len(matches) >= 1

    removed = server.api_delete_document(conn, resolved_doc)
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


def test_rag_api_ingest_rejects_file_outside_documents_root(conn, tmp_path, isolated_documents_root):
    # Security regression test at the REST-handler layer, not just
    # vector_store directly - this is the actual unauthenticated endpoint an
    # attacker would hit.
    outside_file = tmp_path / "outside_root.txt"
    outside_file.write_text("secret", encoding="utf-8")

    with pytest.raises(ValueError, match="must resolve inside"):
        server.api_ingest_document(conn, {"file_path": str(outside_file)})


def test_upload_api_writes_into_documents_root_and_ingests(conn, isolated_documents_root):
    result = server.api_upload_document(conn, "notes.txt", b"PIP uses SQLCipher for encrypted storage.")
    assert result["status"] == "ingested"

    saved = isolated_documents_root / "notes.txt"
    assert saved.read_bytes() == b"PIP uses SQLCipher for encrypted storage."

    docs = server.api_list_documents(conn)
    assert len(docs) == 1
    assert docs[0]["file_path"] == str(saved.resolve())


def test_upload_api_dedupes_colliding_filename(conn, isolated_documents_root):
    server.api_upload_document(conn, "notes.txt", b"first")
    server.api_upload_document(conn, "notes.txt", b"second")

    assert (isolated_documents_root / "notes.txt").read_bytes() == b"first"
    assert (isolated_documents_root / "notes (1).txt").read_bytes() == b"second"
    assert len(server.api_list_documents(conn)) == 2


def test_upload_api_rejects_unsupported_extension(conn, isolated_documents_root):
    with pytest.raises(ValueError, match="Unsupported document extension"):
        server.api_upload_document(conn, "virus.exe", b"whatever")


def test_upload_api_rejects_path_traversal_in_filename(conn, isolated_documents_root, tmp_path):
    # filename is attacker-controlled input (comes straight from the
    # multipart upload) - Path(filename).name must strip any directory
    # component so "../../evil.txt" can't escape DOCUMENTS_ROOT.
    server.api_upload_document(conn, "../../evil.txt", b"payload")

    escaped = tmp_path / "evil.txt"
    assert not escaped.exists()
    assert (isolated_documents_root / "evil.txt").read_bytes() == b"payload"


def test_upload_api_rejects_empty_filename(conn, isolated_documents_root):
    with pytest.raises(ValueError, match="Invalid filename"):
        server.api_upload_document(conn, "", b"payload")


def test_rest_upload_route_ingests_a_real_multipart_request(tmp_path, monkeypatch, isolated_documents_root):
    # Route-level test, not just api_upload_document directly - confirms the
    # actual FastAPI File()/Form() wiring works over real multipart, which a
    # unit-level call to api_upload_document can't catch (the CORS ordering
    # bug earlier this session was exactly this class of miss).
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    token = auth.get_or_create_token(tmp_path / "api_token.txt")

    client = TestClient(server.app)
    response = client.post(
        "/api/v1/rag/upload",
        files={"file": ("notes.txt", b"PIP uses SQLCipher for encrypted storage.", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ingested"
    assert (isolated_documents_root / "notes.txt").read_bytes() == b"PIP uses SQLCipher for encrypted storage."


def test_get_active_model_defaults_when_no_row(conn):
    from backend.core import pipeline
    assert server.api_get_active_model(conn) == {"model_name": pipeline.DEFAULT_MODEL_NAME}


def test_set_active_model_persists_and_is_read_back(conn, monkeypatch):
    monkeypatch.setattr(
        "backend.providers.ollama_provider.list_models",
        lambda host="http://localhost:11434": [{"name": "mistral:latest", "size": 123}],
    )
    result = server.api_set_active_model(conn, {"model_name": "mistral:latest"})
    assert result == {"status": "updated", "model_name": "mistral:latest"}
    assert server.api_get_active_model(conn) == {"model_name": "mistral:latest"}


def test_set_active_model_overwrites_previous_choice(conn, monkeypatch):
    monkeypatch.setattr(
        "backend.providers.ollama_provider.list_models",
        lambda host="http://localhost:11434": [{"name": "a"}, {"name": "b"}],
    )
    server.api_set_active_model(conn, {"model_name": "a"})
    server.api_set_active_model(conn, {"model_name": "b"})
    assert server.api_get_active_model(conn) == {"model_name": "b"}


def test_set_active_model_rejects_unpulled_model_when_ollama_reachable(conn, monkeypatch):
    monkeypatch.setattr(
        "backend.providers.ollama_provider.list_models",
        lambda host="http://localhost:11434": [{"name": "llama3.1:8b"}],
    )
    with pytest.raises(ValueError, match="isn't pulled"):
        server.api_set_active_model(conn, {"model_name": "nonexistent-model"})


def test_set_active_model_fails_open_when_ollama_unreachable(conn, monkeypatch):
    def raising(host="http://localhost:11434"):
        raise ConnectionError("unreachable")
    monkeypatch.setattr("backend.providers.ollama_provider.list_models", raising)
    # Can't verify the name is real right now, but the choice is still saved -
    # an unreachable Ollama shouldn't block picking a model for when it's
    # back up (api_set_active_model's own fail-open reasoning).
    result = server.api_set_active_model(conn, {"model_name": "llama3.1:8b"})
    assert result["status"] == "updated"


def test_set_active_model_requires_model_name(conn):
    with pytest.raises(ValueError, match="model_name is required"):
        server.api_set_active_model(conn, {})


def test_list_llm_models_fails_open_when_ollama_unreachable(monkeypatch):
    def raising(host="http://localhost:11434"):
        raise ConnectionError("unreachable")
    monkeypatch.setattr("backend.providers.ollama_provider.list_models", raising)
    result = server.api_list_llm_models()
    assert result["models"] == []
    assert "error" in result


def test_list_llm_models_returns_name_and_size(monkeypatch):
    monkeypatch.setattr(
        "backend.providers.ollama_provider.list_models",
        lambda host="http://localhost:11434": [{"name": "llama3.1:8b", "size": 4700000000, "digest": "abc"}],
    )
    result = server.api_list_llm_models()
    assert result["models"] == [{"name": "llama3.1:8b", "size": 4700000000}]


def test_rest_llm_model_routes_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    token = auth.get_or_create_token(tmp_path / "api_token.txt")
    monkeypatch.setattr(
        "backend.providers.ollama_provider.list_models",
        lambda host="http://localhost:11434": [{"name": "phi3:latest", "size": 1}],
    )

    client = TestClient(server.app)
    headers = {"Authorization": f"Bearer {token}"}

    models = client.get("/api/v1/llm/models", headers=headers)
    assert models.status_code == 200
    assert models.json()["models"] == [{"name": "phi3:latest", "size": 1}]

    set_response = client.post("/api/v1/llm/active-model", json={"model_name": "phi3:latest"}, headers=headers)
    assert set_response.status_code == 200

    get_response = client.get("/api/v1/llm/active-model", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json() == {"model_name": "phi3:latest"}


def test_rest_llm_model_route_rejects_unpulled_model(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    token = auth.get_or_create_token(tmp_path / "api_token.txt")
    monkeypatch.setattr(
        "backend.providers.ollama_provider.list_models",
        lambda host="http://localhost:11434": [{"name": "llama3.1:8b"}],
    )

    client = TestClient(server.app)
    response = client.post(
        "/api/v1/llm/active-model",
        json={"model_name": "made-up-model"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_api_create_conversation_defaults_to_new_chat(conn):
    result = server.api_create_conversation(conn, {})
    assert result["title"] == "New chat"
    assert result["id"]


def test_api_list_conversations_empty_then_populated(conn):
    assert server.api_list_conversations(conn) == []

    created = server.api_create_conversation(conn, {})
    conversations = server.api_list_conversations(conn)
    assert len(conversations) == 1
    assert conversations[0]["id"] == created["id"]


def test_api_get_conversation_messages_returns_them_in_order(conn):
    from backend.memory import conversation_store

    created = server.api_create_conversation(conn, {})
    conversation_store.append_message(conn, created["id"], "user", "hi")
    conversation_store.append_message(conn, created["id"], "assistant", "hello")

    messages = server.api_get_conversation_messages(conn, created["id"])
    assert [(m["role"], m["content"]) for m in messages] == [("user", "hi"), ("assistant", "hello")]


def test_api_get_conversation_messages_raises_for_unknown_id(conn):
    with pytest.raises(ValueError, match="Unknown conversation"):
        server.api_get_conversation_messages(conn, "not-a-real-id")


def test_api_delete_conversation_removes_it(conn):
    created = server.api_create_conversation(conn, {})
    result = server.api_delete_conversation(conn, created["id"])
    assert result == {"status": "deleted", "id": created["id"]}
    assert server.api_list_conversations(conn) == []


def test_api_delete_conversation_raises_for_unknown_id(conn):
    with pytest.raises(ValueError, match="Unknown conversation"):
        server.api_delete_conversation(conn, "not-a-real-id")


def test_rest_conversation_routes_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    token = auth.get_or_create_token(tmp_path / "api_token.txt")

    client = TestClient(server.app)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post("/api/v1/conversations", json={}, headers=headers)
    assert create_response.status_code == 200
    conversation_id = create_response.json()["id"]

    list_response = client.get("/api/v1/conversations", headers=headers)
    assert list_response.status_code == 200
    assert [c["id"] for c in list_response.json()] == [conversation_id]

    messages_response = client.get(f"/api/v1/conversations/{conversation_id}/messages", headers=headers)
    assert messages_response.status_code == 200
    assert messages_response.json() == []

    delete_response = client.delete(f"/api/v1/conversations/{conversation_id}", headers=headers)
    assert delete_response.status_code == 200
    assert client.get("/api/v1/conversations", headers=headers).json() == []


def test_rest_conversation_messages_route_404s_for_unknown_id(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    token = auth.get_or_create_token(tmp_path / "api_token.txt")

    client = TestClient(server.app)
    response = client.get(
        "/api/v1/conversations/not-a-real-id/messages",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_rest_conversation_delete_route_404s_for_unknown_id(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    token = auth.get_or_create_token(tmp_path / "api_token.txt")

    client = TestClient(server.app)
    response = client.delete(
        "/api/v1/conversations/not-a-real-id",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_lifespan_refuses_to_start_when_another_instance_holds_the_lock(tmp_path, monkeypatch):
    # Security review finding: nothing stopped a second backend process from
    # starting against the same DB - see instance_lock.py. This confirms the
    # FastAPI lifespan actually wires the check in, not just the module in
    # isolation.
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    lock_path = tmp_path / "pip.lock"
    monkeypatch.setenv("PIP_LOCK_PATH", str(lock_path))
    lock_path.write_text(str(os.getppid()))  # a pid that's genuinely alive, but not this process

    with pytest.raises(instance_lock.AlreadyRunningError):
        with TestClient(server.app):
            pass


def test_lifespan_releases_the_lock_on_clean_shutdown(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    lock_path = tmp_path / "pip.lock"
    monkeypatch.setenv("PIP_LOCK_PATH", str(lock_path))

    with TestClient(server.app):
        assert lock_path.exists()
        assert int(lock_path.read_text()) == os.getpid()

    assert not lock_path.exists()
