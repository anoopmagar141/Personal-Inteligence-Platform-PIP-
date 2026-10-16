"""
G-3 / D-08 (docs/FREEZE_LIST.md §7.16): a `*-cloud` Ollama model is not a local model.

Ollama can run a model on its own servers: sign in to Ollama, and a model whose
name ends in "-cloud" (or has the tag "cloud") is answered over the internet,
through the same local port and the same API. PIP's built-in "ollama" provider
reported `is_local: True` whatever model it was given, and its consent record
says the same, so a conversation - and the Observer's whole session transcript -
was sent off the machine as though it were local. The two records Stage 8 and
Stage 11 compare agreed, because both were wrong the same way.

Nothing here contacts a service: Ollama is a stub, and what is asserted is what
reached it. That is also why this was a card from reading the code, not a probe -
demonstrating it for real would have been the leak.

Three places, one rule (providers.ollama_provider.is_cloud_model): a pull and a
selection are refused with a sentence, and the provider itself stops claiming to
be local for such a name, which is what makes Stage 8 and Stage 11 refuse one
that is already stored from before.
"""

import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import server
from backend.core import auth, pipeline, response_cache
from backend.memory import vector_store
from backend.providers import ollama_provider
from backend.providers.base_provider import ProviderUnavailableError
from backend.providers.ollama_provider import OllamaProvider
from backend.stages import stage_11_observer as stage_11

API = "/api/v1"
CLOUD = "gpt-oss:120b-cloud"

CLOUD_NAMES = [
    "gpt-oss:120b-cloud",
    "gpt-oss:cloud",
    "qwen3-coder:480b-cloud",
    "GPT-OSS:120B-CLOUD",
    "  deepseek-v3.1:671b-cloud  ",
    "someone/their-model:70b-cloud",
]
LOCAL_NAMES = ["llama3.1:8b", "qwen2.5:7b", "cloudy:7b", "cloud-atlas:3b", "mistral:7b", "my-cloud-model:13b"]


@pytest.fixture(autouse=True)
def fresh_state(monkeypatch):
    response_cache.clear()
    # a pull from another test must not leave this one thinking one is running
    monkeypatch.setitem(server._pull_state, "status", "idle")
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(vector_store, "_collection", None)
    yield
    response_cache.clear()


@pytest.fixture
def client():
    headers = {"Authorization": "Bearer " + auth.get_or_create_token(Path(os.environ["PIP_TOKEN_PATH"]))}
    with TestClient(server.app) as c:
        yield c, headers


@pytest.fixture
def conn(tmp_path):
    connection = server.open_app_connection(str(tmp_path / "pip.db"), None)
    yield connection
    connection.close()


@pytest.fixture
def pulls(monkeypatch):
    """Ollama's pull, replaced by a recorder. A pull that reaches it is a pull that started."""
    asked = []

    def record(name, on_progress, should_cancel=None):
        asked.append(name)

    monkeypatch.setattr(ollama_provider, "pull_model", record)
    return asked


@pytest.fixture
def sent(monkeypatch):
    """Ollama as a stub that is up, and notes every request it is sent."""
    asked = []

    def answer(self, messages, *args, **kwargs):
        asked.append((self.model_name, messages))
        yield "STUB-REPLY"

    monkeypatch.setattr(OllamaProvider, "is_available", lambda self: True)
    monkeypatch.setattr(OllamaProvider, "chat", answer)
    return asked


def _wait_for_pull(seconds=5.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if server._pull_state["status"] != "pulling":
            return
        time.sleep(0.02)
    pytest.fail("the pull never finished")


# --- the one rule -----------------------------------------------------------


@pytest.mark.parametrize("name", CLOUD_NAMES)
def test_a_cloud_name_is_recognised(name):
    assert ollama_provider.is_cloud_model(name)


@pytest.mark.parametrize("name", LOCAL_NAMES)
def test_a_name_that_only_contains_cloud_is_not_a_cloud_model(name):
    """A model called cloudy, or one with "cloud" in the middle of its name, runs here."""
    assert not ollama_provider.is_cloud_model(name)


@pytest.mark.parametrize("name", CLOUD_NAMES)
def test_the_provider_does_not_claim_to_be_local_for_a_cloud_model(name):
    assert OllamaProvider(model_name=name).get_model_info()["is_local"] is False


@pytest.mark.parametrize("name", LOCAL_NAMES)
def test_control_the_provider_still_claims_to_be_local_for_a_local_model(name):
    assert OllamaProvider(model_name=name).get_model_info()["is_local"] is True


# --- pull -------------------------------------------------------------------


@pytest.mark.parametrize("name", CLOUD_NAMES)
def test_a_cloud_model_cannot_be_pulled(client, pulls, name):
    """Refused with the reason, and Ollama is never asked: there is no pull to cancel."""
    c, headers = client

    response = c.post(f"{API}/llm/pull", json={"model_name": name}, headers=headers)

    assert response.status_code == 400, response.text
    detail = response.json()["detail"]
    assert "cloud" in detail.lower() and "leave this machine" in detail
    assert pulls == [], "Ollama was asked to pull a cloud model"
    assert server._pull_state["status"] == "idle"


@pytest.mark.parametrize("name", LOCAL_NAMES)
def test_control_a_local_model_is_still_pulled(client, pulls, name):
    c, headers = client

    response = c.post(f"{API}/llm/pull", json={"model_name": name}, headers=headers)
    _wait_for_pull()

    assert response.status_code == 200, response.text
    assert pulls == [name]


# --- selection --------------------------------------------------------------


def test_a_cloud_model_cannot_be_selected_even_when_ollama_lists_it(client, conn, monkeypatch):
    """
    Once someone has signed in to Ollama and run a cloud model there, it is in the
    list Ollama returns and so passes the check that a name is real. It is the
    name that is refused, not the absence of the model.
    """
    c, headers = client
    monkeypatch.setattr(ollama_provider, "list_models", lambda *a, **k: [{"name": "llama3.1:8b"}, {"name": CLOUD}])
    before = c.get(f"{API}/llm/active-model", headers=headers).json()["model_name"]

    response = c.post(f"{API}/llm/active-model", json={"model_name": CLOUD}, headers=headers)

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "cloud" in detail.lower() and "leave this machine" in detail
    assert c.get(f"{API}/llm/active-model", headers=headers).json()["model_name"] == before
    stored = conn.execute("SELECT model_name FROM llm_settings WHERE id = 1").fetchone()
    assert stored is None or stored["model_name"] != CLOUD, "the cloud model was saved as the active model"


def test_a_cloud_model_is_refused_even_when_ollama_cannot_be_reached(client, monkeypatch):
    """
    Checking that a name is real is done by asking Ollama, and fails open when
    Ollama is down: choosing a model for when it is back should not be blocked.
    A name that sends the conversation away must not be able to ride that.
    """
    c, headers = client

    def unreachable(*args, **kwargs):
        raise ProviderUnavailableError("Ollama is not running")

    monkeypatch.setattr(ollama_provider, "list_models", unreachable)

    response = c.post(f"{API}/llm/active-model", json={"model_name": CLOUD}, headers=headers)

    assert response.status_code == 422, response.text
    assert "leave this machine" in response.json()["detail"]
    assert c.get(f"{API}/llm/active-model", headers=headers).json()["model_name"] != CLOUD


def test_control_a_local_model_is_still_saved_while_ollama_cannot_be_reached(client, monkeypatch):
    c, headers = client

    def unreachable(*args, **kwargs):
        raise ProviderUnavailableError("Ollama is not running")

    monkeypatch.setattr(ollama_provider, "list_models", unreachable)

    response = c.post(f"{API}/llm/active-model", json={"model_name": "qwen2.5:7b"}, headers=headers)

    assert response.status_code == 200, response.text
    assert c.get(f"{API}/llm/active-model", headers=headers).json()["model_name"] == "qwen2.5:7b"


def test_control_a_local_model_is_still_selected(client, monkeypatch):
    c, headers = client
    monkeypatch.setattr(ollama_provider, "list_models", lambda *a, **k: [{"name": "llama3.1:8b"}, {"name": "qwen2.5:7b"}])

    response = c.post(f"{API}/llm/active-model", json={"model_name": "qwen2.5:7b"}, headers=headers)

    assert response.status_code == 200, response.text
    assert c.get(f"{API}/llm/active-model", headers=headers).json()["model_name"] == "qwen2.5:7b"


# --- a name that is already stored ------------------------------------------


def _store_active_model(conn, name):
    """What an installation from before the refusal can already hold."""
    conn.execute(
        "INSERT INTO llm_settings (id, model_name) VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET model_name = excluded.model_name",
        (name,),
    )
    conn.commit()


def test_a_cloud_model_already_stored_is_sent_nothing(conn, sent):
    """
    The refusals above stop a name getting in. This is the one that is already
    in: the conversation is not sent, because the provider no longer says it is
    local and Stage 8 compares that with the consent record.
    """
    _store_active_model(conn, CLOUD)

    result = pipeline.run_sync(conn, "explain how a hash map works")

    assert result["status"] == "error"
    assert sent == [], f"the conversation was sent to Ollama for a cloud model: {sent!r}"


def test_control_a_stored_local_model_is_used(conn, sent):
    _store_active_model(conn, "qwen2.5:7b")

    result = pipeline.run_sync(conn, "explain how a hash map works")

    assert result["status"] == "success"
    assert [model for model, _ in sent] == ["qwen2.5:7b"]


def test_the_observer_refuses_a_cloud_model_before_sending_the_transcript(conn, sent):
    """The Observer is handed the whole session. Stage 11 asks the provider the same question."""
    transcript = "User: I prefer Flask for small services.\nAssistant: Noted.\n"

    with pytest.raises(stage_11.ObserverLocalProviderError):
        stage_11.run(transcript, OllamaProvider(model_name=CLOUD), conn)

    assert sent == [], "a session transcript was sent to Ollama for a cloud model"
