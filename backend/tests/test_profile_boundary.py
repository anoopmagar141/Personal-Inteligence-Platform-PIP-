"""
Profile isolation at the sign-out boundary (docs/FREEZE_LIST.md §7.7 Pattern 1,
§7.8).

Profiles are separate password-encrypted databases served by ONE backend
process, and sign-out is the only thing that stands between one profile's
session and the next. It forgets the key; these tests are about what else it
has to take with it. Each was found by the end-to-end run in §7.8 and each is
asserted on what the next profile actually receives or what reaches disk, not
on a return value.

Driven through the real routes under a real lifespan. Replaced, and why: the
model (a recorder - these tests are about what it would be sent, not what it
says) and the session-end Observer (unrelated here, and it would reach for
Ollama on disconnect).
"""

import os
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import server
from backend.core import auth, pipeline, response_cache, session_key
from backend.memory import profile_store, vector_store
from backend.providers.base_provider import BaseLLMProvider

API = "/api/v1"
QUESTION = "explain how the Heliotrope sync engine works"


class RecordingProvider(BaseLLMProvider):
    """Answers with a number unique to each call, so a replayed answer is
    distinguishable from a fresh one by its text alone."""

    def __init__(self):
        self.calls: list[str] = []

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
        self.calls.append((context or "") + "\n" + "\n".join(m.get("content", "") for m in messages))
        yield f"ANSWER#{len(self.calls)}"

    def is_available(self):
        return True

    def get_model_info(self):
        return {"provider_id": "ollama", "is_local": True, "model_name": "recorder"}


@pytest.fixture(autouse=True)
def forget_the_key():
    # The key and the response cache are both process-global; a test that
    # signs in must not leave either for the next one.
    session_key.lock()
    response_cache.clear()
    yield
    session_key.lock()
    response_cache.clear()


@pytest.fixture
def provider(monkeypatch):
    recorder = RecordingProvider()
    monkeypatch.setattr(pipeline, "_default_providers", lambda conn: [recorder])

    async def no_observer(*args, **kwargs):
        return {"memory_results": [], "decision_results": []}

    monkeypatch.setattr(server.session_lifecycle, "run_observer_now", no_observer)
    return recorder


@pytest.fixture
def token():
    return auth.get_or_create_token(Path(os.environ["PIP_TOKEN_PATH"]))


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def _new_profile(client, token, name, password) -> str:
    slug = client.post(f"{API}/auth/profiles", json={"name": name}, headers=_headers(token)).json()["slug"]
    response = client.post(
        f"{API}/auth/setup", json={"password": password, "profile": slug}, headers=_headers(token)
    )
    assert response.status_code == 200, response.text
    return slug


def _ask(client, token, question) -> tuple[str, dict]:
    text, hints = "", {}
    with client.websocket_connect(f"/ws/chat?token={token}") as ws:
        assert ws.receive_json()["type"] == "session_info"
        ws.send_json({"message": question})
        while True:
            event = ws.receive_json()
            if event["type"] == "stage_hint":
                hints = event["data"]
            elif event["type"] == "token":
                text += event["data"]
            elif event["type"] in ("done", "error", "stopped"):
                break
    return text.strip(), hints


def test_an_answer_cached_before_sign_out_is_not_served_to_the_next_profile(provider, token):
    """
    Found end to end (§7.8): Bob, signed into his own new profile, asked the
    question Alice had asked and received Alice's answer - built from Alice's
    documents - with his own model never called. The response cache is keyed
    on the message and project only, lives for the life of the process, and
    nothing cleared it at sign-out.
    """
    with TestClient(server.app) as client:
        _new_profile(client, token, "Alice", "alice-password-1")
        alice_answer, _ = _ask(client, token, QUESTION)
        assert client.post(f"{API}/auth/lock", headers=_headers(token)).status_code == 200

        _new_profile(client, token, "Bob", "bob-password-22")
        calls_before = len(provider.calls)
        bob_answer, bob_hints = _ask(client, token, QUESTION)

    assert len(provider.calls) == calls_before + 1, "Bob's question never reached his model"
    assert not bob_hints.get("cache_hit")
    assert bob_answer != alice_answer


def test_an_index_write_in_flight_at_sign_out_is_not_stored_in_plaintext(provider, token, monkeypatch):
    """
    Found end to end (§7.8): an ingest that had read its connection before
    sign-out and wrote to the index after it stored the chunk text and file
    path in plaintext, and the plaintext was still there after the profile's
    next sign-in and index rebuild. vector_store reads the key from the
    environment at write time and, finding none, treated the profile as one
    that never had a password.

    The pause is the only thing added to the real path: a one-shot hold just
    before the index write, so sign-out lands in that window every run rather
    than by luck. It changes when, not what.
    """
    secret = "ZEBRAFINCH-9"
    reached, release = threading.Event(), threading.Event()
    armed = {"on": False}
    real_get_collection = vector_store._get_collection

    def pause_once_before_the_index_write():
        if armed["on"] and threading.current_thread() is not threading.main_thread():
            armed["on"] = False
            reached.set()
            release.wait(30)
        return real_get_collection()

    monkeypatch.setattr(vector_store, "_get_collection", pause_once_before_the_index_write)

    with TestClient(server.app, raise_server_exceptions=False) as client:
        _new_profile(client, token, "Alice", "alice-password-1")
        documents = Path(os.environ["PIP_DOCUMENTS_ROOT"])
        documents.mkdir(parents=True, exist_ok=True)
        note = documents / "notes.txt"
        note.write_text(f"Private note {secret} about the Heliotrope rollout.", encoding="utf-8")

        armed["on"] = True
        result = {}
        ingest = threading.Thread(
            target=lambda: result.update(
                status=client.post(f"{API}/rag/ingest", json={"file_path": str(note)}, headers=_headers(token)).status_code
            )
        )
        ingest.start()
        assert reached.wait(60), "the ingest never reached the index write"
        assert client.post(f"{API}/auth/lock", headers=_headers(token)).status_code == 200
        assert not session_key.is_unlocked()
        release.set()
        ingest.join(60)

        monkeypatch.setattr(vector_store, "_get_collection", real_get_collection)
        stored = vector_store._get_collection().get(include=["documents", "metadatas"])

    assert not any(secret in text for text in stored["documents"]), "chunk text reached disk in plaintext"
    assert not [m for m in stored["metadatas"] if m.get("file_path")], "file path reached disk in plaintext"
    assert result.get("status") != 200, "an ingest that could not be encrypted reported success"


def test_an_upload_is_stored_in_its_own_profiles_folder_and_no_other_profile_can_ingest_it(
    provider, token, tmp_path, monkeypatch
):
    """
    Found end to end (§7.8): /rag/upload wrote into vector_store.DOCUMENTS_ROOT,
    a constant fixed at import to the installation's data/documents, which a
    profile switch never re-pointed. Every profile's uploads landed in one
    shared folder, as the uploaded bytes, where any other profile's ingest
    would accept them.
    """
    with TestClient(server.app) as client:
        _new_profile(client, token, "Alice", "alice-password-1")
        alice_documents = Path(os.environ["PIP_DOCUMENTS_ROOT"]).resolve()
        response = client.post(
            f"{API}/rag/upload",
            files={"file": ("diary.txt", b"Alice's diary: the Heliotrope rollout slipped again.", "text/plain")},
            headers=_headers(token),
        )
        assert response.status_code == 200, response.text
        stored_at = Path(response.json()["file_path"]).resolve()
        assert client.post(f"{API}/auth/lock", headers=_headers(token)).status_code == 200

        _new_profile(client, token, "Bob", "bob-password-22")
        bob_ingest = client.post(f"{API}/rag/ingest", json={"file_path": str(stored_at)}, headers=_headers(token))

    assert stored_at.parent == alice_documents, f"Alice's upload was stored in {stored_at.parent}"
    assert bob_ingest.status_code == 422, "Bob's profile ingested a file from Alice's"


def test_a_profiles_documents_in_the_old_shared_folder_are_adopted_into_its_own(
    provider, token, tmp_path, monkeypatch
):
    """
    Installations from before per-profile uploads have each profile's
    documents recorded under the one shared folder. With the ingestion
    sandbox now the profile's own folder, those records would be rejected by
    the next index rebuild and drop out of search. At sign-in they are copied
    into the profile's folder and repointed - only files under the old shared
    folder, so a record from a restored or crafted backup cannot make PIP copy
    an arbitrary file. The original is left: another profile's record may name
    the same file.
    """
    legacy = tmp_path / "old_shared_documents"
    legacy.mkdir()
    monkeypatch.setattr(profile_store, "_DEFAULT_DOCUMENTS_ROOT", legacy)
    old_file = legacy / "roadmap.txt"
    old_file.write_text("The Heliotrope roadmap: ship the sync engine before the viva.", encoding="utf-8")

    with TestClient(server.app) as client:
        _new_profile(client, token, "Bob", "bob-password-22")
        bob_documents = Path(os.environ["PIP_DOCUMENTS_ROOT"]).resolve()
        # Let the setup's own catch-up finish first, so the sign-in below is
        # the one that runs the adoption. What happens when it has not
        # finished is a separate defect with its own test.
        _wait_for_catch_up()

        # The state an older version left: a registry row and stored bytes
        # pointing into the shared folder, with no chunks for this key yet.
        conn = server._conn()
        try:
            cursor = conn.execute(
                "INSERT INTO documents (file_path, content_hash, chunk_count, status, ingested_at) "
                "VALUES (?, 'legacy', 1, 'active', '2026-09-01T00:00:00Z')",
                (str(old_file.resolve()),),
            )
            conn.commit()
            profile_store.store_document_content(conn, cursor.lastrowid, old_file.read_bytes())
        finally:
            conn.close()

        assert client.post(f"{API}/auth/lock", headers=_headers(token)).status_code == 200
        bob = client.get(f"{API}/auth/profiles", headers=_headers(token)).json()["active"]
        response = client.post(
            f"{API}/auth/unlock", json={"password": "bob-password-22", "profile": bob}, headers=_headers(token)
        )
        assert response.status_code == 200, response.text
        _wait_for_catch_up()

        documents = client.get(f"{API}/rag/documents", headers=_headers(token)).json()
        found = client.post(
            f"{API}/rag/query", json={"query": "Heliotrope roadmap sync engine", "threshold": 0.0}, headers=_headers(token)
        ).json()

    paths = [Path(d["file_path"]).resolve() for d in documents]
    assert paths == [bob_documents / "roadmap.txt"], f"registry still points at {paths}"
    assert (bob_documents / "roadmap.txt").read_bytes() == old_file.read_bytes()
    assert old_file.exists(), "the shared original was removed; another profile may still name it"
    hit_paths = {Path(h["file_path"]).resolve() for h in found}
    assert hit_paths == {bob_documents / "roadmap.txt"}, f"search returned {hit_paths}"


def _wait_for_catch_up(timeout: float = 60.0) -> None:
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        task = server._catch_up_task
        if task is not None and task.done():
            return
        time.sleep(0.1)
    pytest.fail("the sign-in catch-up did not finish")
