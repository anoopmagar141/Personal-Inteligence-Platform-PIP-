import os
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.api import server
from backend.core import auth, instance_lock
from backend.memory import conversation_store, profile_store, vector_store


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


def test_rag_api_omitted_threshold_defers_to_settings(conn, monkeypatch):
    """
    An omitted threshold must reach vector_store as None, not as a literal
    copied into the endpoint - that is what makes the Documents preview and the
    Stage 5 retrieval it previews read the same rag.similarity_threshold.
    """
    captured = {}

    def fake_query(_conn, query_text, project_id=None, threshold=None, top_k=None):
        captured["threshold"] = threshold
        return []

    monkeypatch.setattr(server.vector_store, "query", fake_query)

    server.api_query_rag(conn, {"query": "anything"})
    assert captured["threshold"] is None

    # An explicit threshold still overrides it - that is the slider's whole job.
    server.api_query_rag(conn, {"query": "anything", "threshold": 0.25})
    assert captured["threshold"] == 0.25


def test_rag_defaults_report_what_retrieval_actually_uses():
    """
    The endpoint must report the same constants query() falls back to, not a
    fresh read of settings.json - a client that starts its slider anywhere else
    is previewing a threshold the pipeline is not retrieving at.
    """
    defaults = server.api_rag_defaults()

    assert defaults["similarity_threshold"] == vector_store.DEFAULT_SIMILARITY_THRESHOLD
    assert defaults["top_k_results"] == vector_store.DEFAULT_TOP_K


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


# --- Memory candidate review queue -----------------------------------------


def _park_memory_candidate(conn, validation_status="REQUIRES_CONFIRMATION"):
    from backend.core.types import ValidationResult
    from backend.stages import stage_13_profile_update as stage_13

    candidate = {
        "target_table": "preference_memory",
        "field_name": "editor",
        "proposed_value": "vim",
        "label": "inferred",
        "evidence_count": 2,
        "evidence_text": "Used hjkl repeatedly",
    }
    assert stage_13.run(conn, candidate, ValidationResult(validation_status, "test")) == "pending"
    return server.api_get_pending_memory(conn)[0]["id"]


def test_pending_memory_api_confirm(conn):
    assert server.api_get_pending_memory(conn) == []
    candidate_id = _park_memory_candidate(conn)

    pending = server.api_get_pending_memory(conn)
    assert len(pending) == 1
    assert pending[0]["target_table"] == "preference_memory"
    assert pending[0]["validation_status"] == "REQUIRES_CONFIRMATION"

    confirmed = server.api_confirm_pending_memory(conn, candidate_id)
    assert confirmed["status"] == "resolved"
    assert server.api_get_pending_memory(conn) == []
    assert server.api_get_profile_field(conn, "editor")["value"] == "vim"


def test_pending_memory_api_dismiss(conn):
    candidate_id = _park_memory_candidate(conn, "TIER_2_REQUIRED")

    assert server.api_dismiss_pending_memory(conn, candidate_id)["status"] == "dismissed"
    assert server.api_get_pending_memory(conn) == []
    assert server.api_get_profile_field(conn, "editor") is None


def test_status_reports_pending_memory_count(conn):
    assert server.api_status(conn)["pending_memory"] == 0
    _park_memory_candidate(conn)
    assert server.api_status(conn)["pending_memory"] == 1


def test_rest_pending_memory_routes_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    token = auth.get_or_create_token(tmp_path / "api_token.txt")

    client = TestClient(server.app)
    headers = {"Authorization": f"Bearer {token}"}

    with server.open_app_connection(str(tmp_path / "pip.db")) as setup_conn:
        _park_memory_candidate(setup_conn)

    listed = client.get("/api/v1/memory/pending", headers=headers)
    assert listed.status_code == 200
    candidate_id = listed.json()[0]["id"]

    assert client.get("/api/v1/status", headers=headers).json()["pending_memory"] == 1

    confirmed = client.post(f"/api/v1/memory/pending/{candidate_id}/confirm", headers=headers)
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "resolved"
    assert client.get("/api/v1/memory/pending", headers=headers).json() == []

    # Already resolved - gone from the queue, so 404, not a silent second write.
    again = client.post(f"/api/v1/memory/pending/{candidate_id}/confirm", headers=headers)
    assert again.status_code == 404


def test_rest_pending_memory_confirm_reports_unapplicable_as_422(tmp_path, monkeypatch):
    """
    A candidate the write path cannot accept must not be reported as a missing
    candidate - it is still sitting in the queue. An immutable identity field is
    the durable example; this used to use a goal, back when goal candidates were
    unapplicable for a reason that was a bug rather than a rule.
    """
    from backend.core.types import ValidationResult
    from backend.stages import stage_13_profile_update as stage_13

    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    token = auth.get_or_create_token(tmp_path / "api_token.txt")

    client = TestClient(server.app)
    headers = {"Authorization": f"Bearer {token}"}

    with server.open_app_connection(str(tmp_path / "pip.db")) as setup_conn:
        stage_13.run(
            setup_conn,
            {
                "target_table": "identity",
                "field_name": "name",
                "proposed_value": "Bruce",
                "label": "explicit",
                "evidence_count": 3,
                "evidence_text": "User said so",
            },
            ValidationResult("REQUIRES_CONFIRMATION", "gated_field"),
        )

    candidate_id = client.get("/api/v1/memory/pending", headers=headers).json()[0]["id"]
    response = client.post(f"/api/v1/memory/pending/{candidate_id}/confirm", headers=headers)
    assert response.status_code == 422
    assert len(client.get("/api/v1/memory/pending", headers=headers).json()) == 1


# --- trace read API ---------------------------------------------------------
# The trace answers "why did PIP reply like that". It was being written to a
# file no interface read; moving it into the database without a way to read it
# back would only have changed where it was unreachable from.


def test_api_list_and_get_trace(conn):
    from backend.core import trace

    trace_id = trace.generate_trace_id()
    trace.stage_log(conn, trace_id, "stage_01_intent_classifier", "ok", "classified")
    trace.stage_log(conn, trace_id, "stage_09_llm_streaming", "error", "failed", error_detail="boom")

    listed = server.api_list_traces(conn)
    assert len(listed) == 1
    assert listed[0]["trace_id"] == trace_id
    assert listed[0]["entries"] == 2
    assert listed[0]["errors"] == 1

    entries = server.api_get_trace(conn, trace_id)
    assert [e["stage"] for e in entries] == ["stage_01_intent_classifier", "stage_09_llm_streaming"]


def test_api_get_trace_unknown_id_raises(conn):
    with pytest.raises(ValueError):
        server.api_get_trace(conn, "not-a-real-trace")


def test_rest_trace_routes_round_trip(tmp_path, monkeypatch):
    from backend.core import trace

    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    token = auth.get_or_create_token(tmp_path / "api_token.txt")

    seed = server.open_app_connection(str(tmp_path / "pip.db"))
    trace_id = trace.generate_trace_id()
    trace.stage_log(seed, trace_id, "stage_01_intent_classifier", "ok", "classified")
    seed.close()

    client = TestClient(server.app)
    headers = {"Authorization": f"Bearer {token}"}

    listed = client.get("/api/v1/trace", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["trace_id"] == trace_id

    detail = client.get(f"/api/v1/trace/{trace_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()[0]["stage"] == "stage_01_intent_classifier"

    assert client.get("/api/v1/trace/nope", headers=headers).status_code == 404


# --- refusal reporting on the write routes -----------------------------------
# Four routes call into write paths that refuse work by raising ValueError, and
# none of them caught it: the refusal reached the client as a bare 500 with the
# reason stripped off. That reason is not incidental detail here - "immutable
# identity fields cannot be edited after onboarding" and "reason is required"
# are the entire answer to why an edit did not take, and a client that cannot
# read them can only say something unspecified went wrong. Same treatment and
# same status code as /memory/pending/{candidate_id}/confirm above.


def _client_with_token(tmp_path, monkeypatch):
    """The TestClient + auth-header setup every REST test in this file repeats."""
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    token = auth.get_or_create_token(tmp_path / "api_token.txt")
    return TestClient(server.app), {"Authorization": f"Bearer {token}"}



def test_resumed_messages_carry_their_timestamps(conn):
    """
    The break this closes. messages.created_at has been written since the table
    existed and conversation_store.get_messages has always returned it -
    _resolve_connection_state then rebuilt each message as {role, content} and
    dropped it, so a conversation resumed from last week arrived at the client
    with nothing to say when any of it happened.
    """
    conversation_id = conversation_store.create_conversation(conn)
    conversation_store.append_message(conn, conversation_id, "user", "hello", timestamp="2026-09-04T14:32:00Z")
    conversation_store.append_message(conn, conversation_id, "assistant", "hi", timestamp="2026-09-04T14:32:07Z")

    _, _, _, messages = server._resolve_connection_state(conn, conversation_id)

    assert [m["created_at"] for m in messages] == [
        "2026-09-04T14:32:00Z",
        "2026-09-04T14:32:07Z",
    ]


def test_the_prompt_history_does_not_carry_timestamps(conn):
    """
    The other half, and the reason the strip happens in the caller rather than
    never happening at all: the same list seeds conversation_history, which is
    prompt input. A created_at on every prior turn would be tokens spent
    telling the model something nobody asked it about, and stage_07 appends to
    this list before handing it to a provider that expects {role, content}.
    """
    conversation_id = conversation_store.create_conversation(conn)
    conversation_store.append_message(conn, conversation_id, "user", "hello")

    _, _, _, resumed = server._resolve_connection_state(conn, conversation_id)
    conversation_history = [{"role": m["role"], "content": m["content"]} for m in resumed]

    assert conversation_history == [{"role": "user", "content": "hello"}]

def test_rest_memory_correct_accepts_a_new_name(tmp_path, monkeypatch):
    """
    This asserted a 422 until identity fields became correctable. Someone who
    mistyped their own name at onboarding had no route to fixing it, through
    this endpoint or any other.
    """
    client, headers = _client_with_token(tmp_path, monkeypatch)
    client.post(
        "/api/v1/onboarding/complete",
        headers=headers,
        json={"name": "BatMan", "language_preference": "English"},
    )

    response = client.post(
        "/api/v1/memory/correct",
        headers=headers,
        json={"field": "name", "value": "Bruce"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "updated"}


def test_rest_memory_correct_reports_an_empty_name_as_422(tmp_path, monkeypatch):
    """
    The endpoint still has to turn a refusal into a sentence rather than a
    bare 500 - there is just a different set of refusals now. identity is NOT
    NULL, and a name is what PIP addresses the user by.
    """
    client, headers = _client_with_token(tmp_path, monkeypatch)
    client.post(
        "/api/v1/onboarding/complete",
        headers=headers,
        json={"name": "BatMan", "language_preference": "English"},
    )

    response = client.post(
        "/api/v1/memory/correct",
        headers=headers,
        json={"field": "name", "value": "   "},
    )

    assert response.status_code == 422
    assert "cannot be empty" in response.json()["detail"]


def test_rest_memory_correct_still_accepts_a_mutable_field(tmp_path, monkeypatch):
    """A field with no rule of its own still goes straight through."""
    client, headers = _client_with_token(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/memory/correct",
        headers=headers,
        json={"field": "answer_depth", "value": "brief"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "updated"}


def test_rest_profile_delete_reports_immutable_field_as_422(tmp_path, monkeypatch):
    client, headers = _client_with_token(tmp_path, monkeypatch)

    response = client.delete("/api/v1/memory/profile/timezone", headers=headers)

    assert response.status_code == 422
    assert "immutable identity fields" in response.json()["detail"]


def test_rest_profile_delete_of_an_absent_field_is_not_an_error(tmp_path, monkeypatch):
    """
    A field that is not there is reported as not_found in the body, not as a
    refusal - deleting something already gone is the state the caller wanted.
    """
    client, headers = _client_with_token(tmp_path, monkeypatch)

    response = client.delete("/api/v1/memory/profile/never_existed", headers=headers)

    assert response.status_code == 200
    assert response.json()["status"] == "not_found"


def test_rest_decision_state_reports_a_missing_reason_as_422(tmp_path, monkeypatch):
    """
    Retracting without a reason is refused by update_decision_state() because
    ADR-022 keeps the row forever, and state alone cannot tell a later reader
    "this was a fabrication we cleaned up" from "we changed our mind".
    """
    from backend.memory import decision_log

    client, headers = _client_with_token(tmp_path, monkeypatch)

    with server.open_app_connection(str(tmp_path / "pip.db")) as setup_conn:
        decision_id = decision_log.insert_decision(setup_conn, text="Use FastAPI")

    response = client.patch(
        f"/api/v1/decision/{decision_id}/state",
        headers=headers,
        json={"state": "abandoned", "reason": "   "},
    )

    assert response.status_code == 422
    assert "reason is required" in response.json()["detail"]


def test_rest_decision_state_reports_an_unknown_state_as_422(tmp_path, monkeypatch):
    from backend.memory import decision_log

    client, headers = _client_with_token(tmp_path, monkeypatch)

    with server.open_app_connection(str(tmp_path / "pip.db")) as setup_conn:
        decision_id = decision_log.insert_decision(setup_conn, text="Use FastAPI")

    response = client.patch(
        f"/api/v1/decision/{decision_id}/state",
        headers=headers,
        json={"state": "deleted", "reason": "no longer true"},
    )

    assert response.status_code == 422
    assert "invalid decision state" in response.json()["detail"]


def test_rest_decision_state_retraction_with_a_reason_is_persisted(tmp_path, monkeypatch):
    from backend.memory import decision_log

    client, headers = _client_with_token(tmp_path, monkeypatch)

    with server.open_app_connection(str(tmp_path / "pip.db")) as setup_conn:
        decision_id = decision_log.insert_decision(setup_conn, text="Use FastAPI")

    response = client.patch(
        f"/api/v1/decision/{decision_id}/state",
        headers=headers,
        json={"state": "abandoned", "reason": "PIP invented this one"},
    )
    assert response.status_code == 200

    with server.open_app_connection(str(tmp_path / "pip.db")) as read_conn:
        row = read_conn.execute(
            "SELECT state, state_reason FROM decision_log WHERE id = ?", (decision_id,)
        ).fetchone()
    assert row["state"] == "abandoned"
    assert row["state_reason"] == "PIP invented this one"


def test_rest_project_status_reports_an_unknown_status_as_422(tmp_path, monkeypatch):
    client, headers = _client_with_token(tmp_path, monkeypatch)

    with server.open_app_connection(str(tmp_path / "pip.db")) as setup_conn:
        project_id = profile_store.create_project(setup_conn, "PIP")

    # Not 'deleted', which this used to use: that became a legal status when
    # projects gained a retraction, so the example had to move to one that is
    # still genuinely invalid or the test would assert nothing.
    response = client.patch(
        f"/api/v1/projects/{project_id}/status",
        headers=headers,
        json={"status": "binned"},
    )

    assert response.status_code == 422
    assert "invalid project status" in response.json()["detail"]


def test_rest_project_status_archives_a_project(tmp_path, monkeypatch):
    client, headers = _client_with_token(tmp_path, monkeypatch)

    with server.open_app_connection(str(tmp_path / "pip.db")) as setup_conn:
        project_id = profile_store.create_project(setup_conn, "PIP")

    response = client.patch(
        f"/api/v1/projects/{project_id}/status",
        headers=headers,
        json={"status": "archived"},
    )
    assert response.status_code == 200

    listed = client.get("/api/v1/projects", headers=headers).json()
    assert [p["status"] for p in listed if p["project_id"] == project_id] == ["archived"]
