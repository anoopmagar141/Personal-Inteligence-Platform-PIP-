"""
A question about the user or their project is not sent to the web
(BLUEPRINT card P-1, FREEZE_LIST §7.5 recommendation 3, Promise 6).

Stage 1 used to check the news words ("today", "current", "latest", ...)
before it asked whether a message was about the user or a project, and the
web guard in pipeline.run skips the search only for the personal and project
categories. So "what is my current project?" was filed as news, and with web
search consented its first 12 words went to the search provider.

The guard's own test (test_b1_honesty_fixes) stubs Stage 1 and hands the
pipeline a category, so it proved the guard and never the routing in front
of it. Every case here runs the real Stage 1 through the real pipeline, with
web consent granted and Stage 6 replaced by a recorder, and counts what would
have left the machine.

Both lists were fixed before the fix was written. The first holds only
messages Stage 1's existing checks already recognise as about the user or a
project (a first-person phrase, the word "project"/"program", or an active
project's name): the fix reorders those checks and adds no words, so a
phrasing they do not recognise is out of its reach and is recorded in
FREEZE_LIST instead of being listed here.
"""

import pytest

from backend.api import server
from backend.core import pipeline, response_cache
from backend.memory import profile_store
from backend.providers.base_provider import BaseLLMProvider
from backend.stages import stage_06_web_search as stage_06

PROJECT = "Heliotrope"

ABOUT_THE_USER_OR_A_PROJECT = [
    # Track 4a's phrasings (§7.5) that carry a whole-word web trigger.
    "what should I do today on my thesis?",
    "what is my current project?",
    "what's the latest on my project?",
    # Wording that appears nowhere in §7.5 or in Stage 1's lists.
    "any news on Heliotrope?",
    "do I have anything due today?",
    "I'm behind on the current chapter, what is left?",
    "what's the current state of the program I'm writing?",
]

PLAIN_NEWS = [
    "who won the football match last night?",
    "what is the weather in Kathmandu today?",
    "latest news about the Mars rover",
    "what is the current price of gold?",
    "any recent earthquakes in Nepal?",
]


class _Provider(BaseLLMProvider):
    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
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
    profile_store.create_project(connection, PROJECT, "Final year thesis platform")
    server.api_grant_consent(connection, "web_search", "web_search_only")
    response_cache.clear()
    yield connection
    response_cache.clear()
    connection.close()


@pytest.fixture
def sent(monkeypatch):
    queries: list[str] = []
    monkeypatch.setattr(stage_06, "run", lambda query, **kwargs: queries.append(query) or [])
    return queries


@pytest.mark.parametrize("question", ABOUT_THE_USER_OR_A_PROJECT)
def test_a_question_about_the_user_or_a_project_sends_no_web_query(conn, sent, question):
    # Precondition, so a case cannot pass for the wrong reason: the message
    # does carry a web trigger, and without the fix it would be searched.
    assert stage_06.matches_trigger(question)

    pipeline.run_sync(conn, question, providers=[_Provider()])

    assert sent == [], f"{question!r} was sent to the web as {sent!r}"


@pytest.mark.parametrize("question", PLAIN_NEWS)
def test_a_plain_news_question_is_still_offered_and_searched_when_approved(conn, sent, question):
    # Since D-45 the first pass only offers the search; the approved run sends it.
    offer = pipeline.run_sync(conn, question, providers=[_Provider()])["web_search_offer"]
    assert sent == [] and offer, f"{question!r} was not offered"

    pipeline.run_sync(conn, question, providers=[_Provider()], approved_web_query=offer)

    assert sent == [offer], f"{question!r} sent {sent!r}"
