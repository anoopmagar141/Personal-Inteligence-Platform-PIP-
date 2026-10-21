"""
No click, no search (BLUEPRINT card D-45, the owner's choice of 2026-10-21; Promise 6).

Q-1 found it (FREEZE_LIST §7.66): with web search consented, any message with one of Stage 1's trigger words that
is not filed as a personal or project question was searched at once, its first 12 words sent to the search provider.
"I feel tired today" was sent, and so was "we had a big fight today". Consent now means PIP may ASK: the first pass
sends nothing and ends with an offer of the exact query, and only an approved run sends that query.

Through the real pipeline and the real Stage 1, with Stage 6 replaced by a recorder that counts what would have left
the machine. The socket's half (the offer event, the approval message) is in test_ws_chat.py.
"""

import pytest

from backend.api import server
from backend.core import pipeline, response_cache
from backend.memory import profile_store
from backend.providers.base_provider import BaseLLMProvider
from backend.stages import stage_01_intent_classifier as stage_01
from backend.stages import stage_06_web_search as stage_06

# Q-1's finding and the sentences checked on 2026-10-21: none is a news question, all were searched.
D45_SENTENCES = [
    "hey pip, how are you doing today?",
    "I feel tired today",
    "feeling anxious about the exam today",
    "we had a big fight today",
    "today I finished chapter two",
]
NEWS = "what is the weather in Kathmandu today?"
SNIPPET = "Kathmandu: light rain, 18 degrees"


class _Recorder(BaseLLMProvider):
    def __init__(self):
        self.prompts: list[str] = []

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
        self.prompts.append((context or "") + "\n" + "\n".join(m.get("content", "") for m in messages))
        yield "answer"

    def is_available(self):
        return True

    def get_model_info(self):
        return {"provider_id": "ollama", "is_local": True, "model_name": "recorder"}


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    connection = server.open_app_connection(str(tmp_path / "pip.db"), None)
    profile_store.complete_onboarding(connection, name="Zarqa Venn", language_preference="English")
    server.api_grant_consent(connection, "web_search", "web_search_only")
    response_cache.clear()
    yield connection
    response_cache.clear()
    connection.close()


@pytest.fixture
def sent(monkeypatch):
    queries: list[str] = []

    def record(query, **kwargs):
        queries.append(query)
        return [{"title": "Weather", "url": "https://example.test/weather", "snippet": SNIPPET}]

    monkeypatch.setattr(stage_06, "run", record)
    return queries


def _ask(conn, message, **kw):
    recorder = _Recorder()
    events = list(pipeline.run(conn, message, providers=[recorder], **kw))
    return events[-1]["data"], recorder, events


def _first_12_words(message):
    return stage_01.run(message)["retrieval_hint"]


# --- the first pass sends nothing ---------------------------------------------------------------------------------


@pytest.mark.parametrize("message", D45_SENTENCES + [NEWS])
def test_nothing_is_searched_without_a_click(conn, sent, message):
    assert stage_06.matches_trigger(message), "precondition: the message would have been searched"

    result, recorder, _ = _ask(conn, message)

    assert sent == [], f"{message!r} was sent to the web as {sent!r}"
    assert len(recorder.prompts) == 1, "it is still answered, without the web"
    assert result["web_search_offer"] == _first_12_words(message), "the offer is exactly what would be sent"


def test_the_first_pass_says_what_it_would_send(conn, sent):
    _, _, events = _ask(conn, "I feel tired today")

    web = [e["data"] for e in events if e["type"] == "stage" and e["data"]["stage"] == "web"]
    assert len(web) == 1 and web[0]["status"] == "skipped"
    assert "'I feel tired today'" in web[0]["detail"]


# --- an approved run sends exactly the offer ------------------------------------------------------------------------


def test_an_approved_search_sends_exactly_the_offered_query_once(conn, sent):
    offer = _ask(conn, NEWS)[0]["web_search_offer"]

    result, recorder, events = _ask(conn, NEWS, approved_web_query=offer)

    assert sent == [offer]
    assert SNIPPET in recorder.prompts[-1], "the results reach the answer"
    assert result["web_search_offer"] is None, "an approved run offers nothing more"
    web = [e["data"] for e in events if e["type"] == "stage" and e["data"]["stage"] == "web"]
    assert len(web) == 1 and offer in web[0]["detail"] and web[0]["status"] == "ok"


def test_an_approved_search_checks_consent_again(conn, sent):
    offer = _ask(conn, NEWS)[0]["web_search_offer"]
    server.api_revoke_consent(conn, "web_search")

    _, recorder, _ = _ask(conn, NEWS, approved_web_query=offer)

    assert sent == [], "consent revoked after the offer: nothing leaves"
    assert len(recorder.prompts) == 1, "the question is still answered"


def test_an_approved_answer_is_never_taken_from_the_cache(conn, sent):
    offer = _ask(conn, NEWS)[0]["web_search_offer"]

    _, first, _ = _ask(conn, NEWS, approved_web_query=offer)
    _, second, _ = _ask(conn, NEWS, approved_web_query=offer)

    assert len(first.prompts) == 1 and len(second.prompts) == 1, "each approved run reaches the model"
    assert sent == [offer, offer], "and each one is the search the user clicked"


# --- a turn with an offer is not cached ----------------------------------------------------------------------------


def test_a_first_message_with_an_offer_is_not_cached(conn, sent):
    first, _, _ = _ask(conn, NEWS)
    again, recorder, _ = _ask(conn, NEWS)

    assert len(recorder.prompts) == 1, "not answered from the cache"
    assert again["web_search_offer"] == first["web_search_offer"], "so the offer is made again"


# --- what gets no offer, as before ------------------------------------------------------------------------------------


def test_no_consent_no_offer(conn, sent):
    server.api_revoke_consent(conn, "web_search")

    result, _, _ = _ask(conn, NEWS)

    assert sent == [] and result["web_search_offer"] is None


def test_a_question_about_the_user_gets_no_offer(conn, sent):
    result, _, _ = _ask(conn, "what is my current project?")

    assert sent == [] and result["web_search_offer"] is None


def test_a_message_with_no_trigger_word_gets_no_offer(conn, sent):
    result, _, _ = _ask(conn, "explain how a hash table works")

    assert sent == [] and result["web_search_offer"] is None
