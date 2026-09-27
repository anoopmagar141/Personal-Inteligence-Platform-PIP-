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
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import server
from backend.core import auth, pipeline, response_cache, session_key
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
