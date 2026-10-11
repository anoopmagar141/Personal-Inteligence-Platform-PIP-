"""Outcome tests for the four B-1 honesty promises."""

from typing import Iterator

import pytest

from backend.api import server
from backend.core import pipeline
from backend.memory import llm_endpoint_store
from backend.providers.base_provider import BaseLLMProvider, ProviderExecutionError
from backend.providers.ollama_provider import OllamaProvider
from backend.tests.test_consent_before_sending import _Stub


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    connection = server.open_app_connection(str(tmp_path / "pip.db"), None)
    yield connection
    connection.close()


@pytest.fixture
def stub():
    server_stub = _Stub()
    yield server_stub
    server_stub.close()


@pytest.fixture
def ollama_down(monkeypatch):
    monkeypatch.setattr(OllamaProvider, "is_available", lambda self: False)


class _FailingProvider(BaseLLMProvider):
    def __init__(self, provider_id: str, model_name: str, fails: bool):
        self.provider_id = provider_id
        self.model_name = model_name
        self.fails = fails

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None) -> Iterator[str]:
        if self.fails:
            raise ProviderExecutionError("provider unavailable")
        yield "fallback answer"

    def is_available(self) -> bool:
        return True

    def get_model_info(self):
        return {
            "provider_id": self.provider_id,
            "model_name": self.model_name,
            "is_local": True,
        }


def _stage_events(events, stage_name):
    return [
        event for event in events
        if event.get("type") == "stage" and event.get("data", {}).get("stage") == stage_name
    ]


def test_writing_status_names_the_consented_provider_and_model(conn, stub, ollama_down):
    llm_endpoint_store.add_endpoint(
        conn,
        provider_id="stub-cloud",
        label="Stub Cloud",
        base_url=stub.url,
        is_local=False,
        model_name="model-one",
        priority=10,
    )
    server.api_grant_consent(conn, "stub-cloud", "full_inference")

    events = list(pipeline.run(conn, "Hello there"))

    writing = _stage_events(events, "writing")
    assert stub.sent, "the consented stub did not receive the request"
    assert len(writing) == 1
    assert writing[0]["data"]["detail"] == "stub-cloud / model-one"


def test_writing_status_names_the_provider_that_fallback_reaches(conn, monkeypatch):
    first = _FailingProvider("first", "model-a", fails=True)
    fallback = _FailingProvider("second", "model-b", fails=False)
    monkeypatch.setattr(pipeline, "_gate_providers", lambda *args: [first, fallback])

    events = list(pipeline.run(conn, "Explain a hash table"))

    writing = _stage_events(events, "writing")
    assert [event["data"]["detail"] for event in writing] == [
        "first / model-a",
        "second / model-b",
    ]
    assert events[-1]["type"] == "pipeline_complete"
    assert events[-1]["data"]["response_text"] == "fallback answer"
