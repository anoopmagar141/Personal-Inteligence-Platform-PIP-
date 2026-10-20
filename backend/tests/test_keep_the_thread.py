"""
Step 6, keep the thread in a chat (BLUEPRINT card "Step 6"; the plan's #7, #9, #10, #12; #8 is in test_ws_chat.py,
where the chat socket's own fixtures are).

Each was a way a follow-up inside one chat lost its context:
- #12: the prompt never said what day it is, so "yesterday" or "last week" could not be placed;
- #9: history trimming stopped at the first message that did not fit, so one long reply pushed every earlier
  message out, the last exchange included;
- #10: the answer cache did not know the chat, so a follow-up ("why?") could get another chat's saved answer;
- #7: decisions and documents were searched with the first 12 words of the newest message only, so "and the other
  one?" found nothing it referred to.

Through the real pipeline (pipeline.run_sync) with a stand-in model that records the prompt it is given.
"""

from datetime import date

import pytest

from backend.core import pipeline, response_cache
from backend.memory import conversation_store, decision_log
from backend.memory.profile_store import get_connection, initialize_schema
from backend.providers.base_provider import BaseLLMProvider
from backend.stages import stage_07_context_assembly as stage_07


class _Recorder(BaseLLMProvider):
    def __init__(self, answer="answer"):
        self.prompts: list[str] = []
        self.answer = answer

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
        self.prompts.append((context or "") + "\n" + "\n".join(m.get("content", "") for m in messages))
        yield self.answer

    def is_available(self):
        return True

    def get_model_info(self):
        return {"provider_id": "ollama", "is_local": True, "model_name": "recorder"}


@pytest.fixture
def conn(tmp_path, db_key):
    response_cache.clear()
    c = get_connection(str(tmp_path / "pip.db"), db_key=db_key)
    initialize_schema(c)
    yield c
    c.close()
    response_cache.clear()


def _ask(conn, message, **kw):
    recorder = _Recorder()
    pipeline.run_sync(conn, message, providers=[recorder], **kw)
    return recorder


GENERAL = "how does a hash map handle collisions?"


# --- #12 today's date -------------------------------------------------------------------------------------------


def test_the_prompt_says_what_day_it_is(conn, monkeypatch):
    monkeypatch.setattr(pipeline, "_today", lambda: date(2026, 10, 20))

    prompt = _ask(conn, "what should I do tomorrow?").prompts[-1]

    assert "Today is Tuesday, 20 October 2026." in prompt


def test_a_cached_answer_is_not_replayed_on_another_day(conn, monkeypatch):
    # A cached answer to "what day is it?" would be wrong tomorrow; any cached answer was built from a prompt
    # that named its day.
    monkeypatch.setattr(pipeline, "_today", lambda: date(2026, 10, 20))
    first = _ask(conn, GENERAL)
    same_day = _ask(conn, GENERAL)
    monkeypatch.setattr(pipeline, "_today", lambda: date(2026, 10, 21))
    next_day = _ask(conn, GENERAL)

    assert len(first.prompts) == 1
    assert same_day.prompts == [], "the same day, the cached answer is used"
    assert len(next_day.prompts) == 1 and "Wednesday, 21 October 2026" in next_day.prompts[0]


# --- #9 one long answer -----------------------------------------------------------------------------------------


def test_one_long_answer_does_not_push_out_the_last_exchange():
    long_answer = "Postgres " + " ".join(f"detail{i}" for i in range(4000))
    history = [
        {"role": "user", "content": "Which database should Zephyr use?"},
        {"role": "assistant", "content": long_answer},
    ]

    result = stage_07.run("and why that one?", conversation_history=history)

    roles = [m["role"] for m in result["messages"]]
    assert roles == ["user", "assistant", "user"], "the last exchange is kept, the long answer shortened"
    assert result["messages"][0]["content"] == "Which database should Zephyr use?"
    kept = result["messages"][1]["content"]
    assert kept.startswith("Postgres detail0") and len(kept.split()) < 2000


def test_earlier_messages_still_go_first_when_the_budget_is_short():
    long_answer = " ".join(f"word{i}" for i in range(4000))
    history = [
        {"role": "user", "content": "an earlier question about Lanternfish"},
        {"role": "assistant", "content": "an earlier answer about Lanternfish"},
        {"role": "user", "content": "Which database should Zephyr use?"},
        {"role": "assistant", "content": long_answer},
    ]

    result = stage_07.run("and why that one?", conversation_history=history)

    contents = [m["content"] for m in result["messages"]]
    assert "an earlier question about Lanternfish" not in contents
    assert contents[0] == "Which database should Zephyr use?"


def test_a_history_that_fits_is_passed_whole():
    history = [
        {"role": "user", "content": "Which database should Zephyr use?"},
        {"role": "assistant", "content": "Postgres, for the concurrency."},
    ]

    result = stage_07.run("and why that one?", conversation_history=history)

    assert [m["content"] for m in result["messages"]] == [
        "Which database should Zephyr use?", "Postgres, for the concurrency.", "and why that one?"]


# --- #10 a saved answer in another chat -------------------------------------------------------------------------


def test_a_follow_up_is_never_answered_from_the_cache(conn):
    _ask(conn, GENERAL)  # a first message: cached
    follow_up = _ask(conn, GENERAL, conversation_history=[
        {"role": "user", "content": "Tell me about Python dictionaries."},
        {"role": "assistant", "content": "They are hash maps."},
    ])

    assert len(follow_up.prompts) == 1, "a follow-up depends on its chat, so it is not served from the cache"


def test_a_follow_ups_answer_is_not_saved_for_another_chat(conn):
    _ask(conn, GENERAL, conversation_history=[
        {"role": "user", "content": "Tell me about Python dictionaries."},
        {"role": "assistant", "content": "They are hash maps."},
    ])
    first_message = _ask(conn, GENERAL)

    assert len(first_message.prompts) == 1


def test_a_chats_first_message_still_uses_the_cache(conn):
    _ask(conn, GENERAL)
    again = _ask(conn, GENERAL)

    assert again.prompts == []


# --- #7 searches see the previous message and the whole current one ----------------------------------------------


FOLLOW_UP_HISTORY = [
    {"role": "user", "content": "What did we decide about the analytics warehouse for the reporting team?"},
    {"role": "assistant", "content": "Let me check."},
]


def test_a_follow_up_finds_the_decision_its_previous_message_was_about(conn):
    decision_log.insert_decision(conn, text="Use Postgres for the analytics warehouse", confidence=0.9)

    prompt = _ask(conn, "and why?", conversation_history=FOLLOW_UP_HISTORY).prompts[-1]

    assert "Use Postgres for the analytics warehouse" in prompt


def test_decisions_and_documents_are_searched_with_the_previous_and_the_whole_current_message(conn, monkeypatch):
    seen = {}
    monkeypatch.setattr(pipeline.stage_03, "run", lambda c, text, project_id=None: seen.setdefault("decisions", text) and [])
    monkeypatch.setattr(pipeline.stage_05, "run",
                        lambda c, text, project_id=None: seen.setdefault("documents", text) and {"chunks": [], "conflict_flag": False})
    current = "and what about the second option, the one with the managed replicas and the nightly backups?"

    _ask(conn, current, conversation_history=FOLLOW_UP_HISTORY)

    for key in ("decisions", "documents"):
        assert FOLLOW_UP_HISTORY[0]["content"] in seen[key]
        assert current in seen[key], "the whole current message, not its first 12 words"


def test_the_web_query_is_still_the_first_12_words_of_the_current_message(conn, monkeypatch):
    seen = []
    monkeypatch.setattr(pipeline.stage_06, "matches_trigger", lambda message: True)
    monkeypatch.setattr(pipeline.stage_08, "run", lambda *a, **k: None)
    monkeypatch.setattr(pipeline.stage_06, "run", lambda query: seen.append(query) or [])
    current = "what is the latest news on the managed replicas and the nightly backups this week?"

    _ask(conn, current, conversation_history=FOLLOW_UP_HISTORY)

    assert seen == [" ".join(current.split()[:12])], "nothing from the earlier message goes to the web"
