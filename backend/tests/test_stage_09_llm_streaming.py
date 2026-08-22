from typing import Iterator

import pytest

from backend.providers.base_provider import (
    BaseLLMProvider,
    ProviderExecutionError,
    ProviderUnavailableError,
)
from backend.stages import stage_09_llm_streaming as stage_09


class FakeProvider(BaseLLMProvider):
    def __init__(self, provider_id="fake", tokens=None, raise_error=None, raise_after=0):
        self.provider_id = provider_id
        self.tokens = tokens or []
        self.raise_error = raise_error
        self.raise_after = raise_after  # raise after yielding this many tokens

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30) -> Iterator[str]:
        for i, token in enumerate(self.tokens):
            if self.raise_error and i == self.raise_after:
                raise self.raise_error
            yield token
        if self.raise_error and self.raise_after >= len(self.tokens):
            raise self.raise_error

    def is_available(self) -> bool:
        return True

    def get_model_info(self):
        return {"provider_id": self.provider_id, "is_local": True, "model_name": "fake"}


def test_stage_hint_is_always_first_event():
    provider = FakeProvider(tokens=["hi"])
    events = list(stage_09.run("ctx", [], [provider], decision_log_hit=True))
    assert events[0]["type"] == "stage_hint"
    assert events[0]["data"]["decision_log_hit"] is True


def test_successful_stream_yields_tokens_then_done():
    provider = FakeProvider(tokens=["Hello", " ", "world"])
    events = list(stage_09.run("ctx", [], [provider]))
    token_events = [e for e in events if e["type"] == "token"]
    assert [e["data"] for e in token_events] == ["Hello", " ", "world"]
    assert events[-1] == {"type": "done", "data": None}


def test_provider_fails_before_any_tokens_falls_through_to_next():
    failing = FakeProvider(provider_id="failing", tokens=[], raise_error=ProviderUnavailableError("down"), raise_after=0)
    working = FakeProvider(provider_id="working", tokens=["ok"])
    events = list(stage_09.run("ctx", [], [failing, working]))
    token_events = [e for e in events if e["type"] == "token"]
    assert token_events == [{"type": "token", "data": "ok"}]
    assert events[-1] == {"type": "done", "data": None}


def test_provider_fails_mid_stream_does_not_fall_through():
    failing = FakeProvider(provider_id="failing", tokens=["a", "b", "c"], raise_error=ProviderExecutionError("dropped"), raise_after=2)
    working = FakeProvider(provider_id="working", tokens=["should not appear"])
    events = list(stage_09.run("ctx", [], [failing, working]))
    token_events = [e["data"] for e in events if e["type"] == "token"]
    assert token_events == ["a", "b"]  # partial output preserved
    assert "should not appear" not in token_events  # no fallback after partial output
    assert events[-1]["type"] == "error"


def test_all_providers_fail_yields_final_error():
    p1 = FakeProvider(provider_id="p1", tokens=[], raise_error=ProviderUnavailableError("down1"))
    p2 = FakeProvider(provider_id="p2", tokens=[], raise_error=ProviderUnavailableError("down2"))
    events = list(stage_09.run("ctx", [], [p1, p2]))
    assert events[-1]["type"] == "error"
    assert "All providers failed" in events[-1]["data"]


def test_zero_token_response_is_treated_as_failure_and_falls_through():
    empty = FakeProvider(provider_id="empty", tokens=[])
    working = FakeProvider(provider_id="working", tokens=["real content"])
    events = list(stage_09.run("ctx", [], [empty, working]))
    token_events = [e["data"] for e in events if e["type"] == "token"]
    assert token_events == ["real content"]


def test_collect_aggregates_successful_stream():
    provider = FakeProvider(tokens=["Hello", " world"])
    result = stage_09.collect(stage_09.run("ctx", [], [provider], cache_hit=True))
    assert result["response_text"] == "Hello world"
    assert result["status"] == "success"


def test_should_stop_ends_stream_early_with_stopped_event():
    provider = FakeProvider(tokens=["a", "b", "c", "d"])
    # Stops right after the 2nd token has been yielded to the caller - proves
    # the check runs before yielding the NEXT token, not that it drops
    # tokens already delivered.
    seen_tokens = []

    def should_stop():
        return len(seen_tokens) >= 2

    events = []
    for event in stage_09.run("ctx", [], [provider], should_stop=should_stop):
        events.append(event)
        if event["type"] == "token":
            seen_tokens.append(event["data"])

    assert [e["data"] for e in events if e["type"] == "token"] == ["a", "b"]
    assert events[-1] == {"type": "stopped", "data": None}


def test_should_stop_true_from_the_start_yields_stopped_before_any_token():
    provider = FakeProvider(tokens=["a", "b", "c"])
    events = list(stage_09.run("ctx", [], [provider], should_stop=lambda: True))
    assert [e["type"] for e in events if e["type"] != "stage_hint"] == ["stopped"]


def test_should_stop_none_never_stops_a_normal_stream():
    # Default (no should_stop passed) behaves exactly as before this
    # feature existed - a regression guard, not a stop-specific test.
    provider = FakeProvider(tokens=["a", "b"])
    events = list(stage_09.run("ctx", [], [provider]))
    assert events[-1] == {"type": "done", "data": None}


def test_collect_reports_stopped_status():
    provider = FakeProvider(tokens=["a", "b", "c"])
    result = stage_09.collect(stage_09.run("ctx", [], [provider], should_stop=lambda: True, cache_hit=True))
    assert result["status"] == "stopped"
    assert result["response_text"] == ""
    assert result["error"] is None
    assert result["stage_hints"]["cache_hit"] is True  # stage_hint (always first) still reported normally


def test_collect_aggregates_failed_stream():
    provider = FakeProvider(tokens=[], raise_error=ProviderUnavailableError("down"))
    result = stage_09.collect(stage_09.run("ctx", [], [provider]))
    assert result["status"] == "error"
    assert result["response_text"] == ""
    assert "All providers failed" in result["error"]
