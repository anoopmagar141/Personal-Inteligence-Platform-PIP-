"""
What the model is told about saving when the user tells it something
(docs/FREEZE_LIST.md §7.76, D-51).

PIP keeps nothing while a chat is going on: what the user says is read at the
chat's end, after an idle wait or when the chat is left, and the evidence gate
and the Constitution decide what is kept, which may be nothing. The model was
never told that, so told "I prefer Python for small automation scripts, but I
use Java for university coursework." it answered "I have noted your
preferences" - in the owner's own app, with nothing saved. Asked "Will you
remember this next time?" it said "I will update your records".

And told a fact, it often answered "I don't have that in front of me": rule 4,
written for a fact the user ASKS for, read as covering one the user has just
GIVEN. The same instructions answer both: what the user says is in front of
the model for the rest of the chat, and nothing is saved by the model at all.

Where the words sit was measured to matter (§7.76): the rule alone, at the end
of the instructions or at their top, moved the real model little; a short
reminder as the last thing in the context, nearest the reply, is what took
"did you save that?" from "yes" to "not yet". So the reminder's position is
asserted, not only its presence.

Asserted on the prompt the model actually receives, through the real pipeline,
with a recording provider standing in for the model, for statements that Stage
1 routes in different ways. What the model then says is measured separately
(§7.76), against the real model, and is not fully fixed.
"""

import pytest

from backend.core import pipeline, response_cache
from backend.memory import decision_log, profile_store, vector_store
from backend.memory.profile_store import get_connection, initialize_schema
from backend.providers.base_provider import BaseLLMProvider


class RecordingProvider(BaseLLMProvider):
    def __init__(self):
        self.prompts: list[str] = []

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
        self.prompts.append(context or "")
        yield "OK"

    def is_available(self):
        return True

    def get_model_info(self):
        return {"provider_id": "ollama", "is_local": True, "model_name": "recorder"}


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    response_cache.clear()
    monkeypatch.setattr(vector_store, "CHROMA_DB_PATH", str(tmp_path / "chroma"))
    monkeypatch.setattr(vector_store, "_client", None)
    monkeypatch.setattr(vector_store, "_collection", None)
    yield
    response_cache.clear()


@pytest.fixture
def conn(tmp_path, db_key):
    connection = get_connection(str(tmp_path / "pip.db"), db_key=db_key)
    initialize_schema(connection)
    profile_store.complete_onboarding(connection, name="Test User", language_preference="English",
                                      skills=["Python"], preferred_tools=["VS Code"])
    project_id = profile_store.create_project(connection, "Lanternfish", "a budgeting app for students")
    decision_log.create_decision(connection, text="We decided to use PostgreSQL for Lanternfish",
                                 reasoning="the data is relational", project_id=project_id)
    yield connection
    connection.close()


def _context_for(conn, message) -> str:
    provider = RecordingProvider()
    pipeline.run_sync(conn, message, providers=[provider])
    assert provider.prompts, f"the model was never called for {message!r}"
    return " ".join(provider.prompts[-1].lower().split())


# The owner's own sentence first, then the ways the D-51 check (§7.76) saw the
# reply go wrong: a request to remember, a "from now on", a decision, a plain
# fact, and a question about the project, which brings the profile and the
# decision into the context ahead of the reminder.
STATEMENTS = [
    "I prefer Python for small automation scripts, but I use Java for university coursework.",
    "Please remember that my exam is on 3 December.",
    "From now on, call me Sam.",
    "I decided to use SQLite instead of Firebase for my app.",
    "I usually study late at night, after 11.",
    "What did we decide about the database for Lanternfish?",
]


@pytest.mark.parametrize("message", STATEMENTS)
def test_the_model_is_told_it_saves_nothing_during_the_chat(conn, message):
    text = _context_for(conn, message)

    assert "you cannot save anything yourself" in text
    assert "nothing the user says is kept while this conversation is going on" in text
    # What happens instead. Its first wording ("keeps only what passes its
    # checks, so it may keep nothing") was read by the real model as "nothing
    # is ever kept" (§7.76), which is untrue the other way.
    assert "after it pauses or ends, pip reads it and may keep some of what the user said" in text
    assert "it may also keep none of it" in text


@pytest.mark.parametrize("message", STATEMENTS)
def test_the_model_is_told_not_to_claim_a_save(conn, message):
    text = _context_for(conn, message)

    assert "never say you have noted, saved, recorded or stored something" in text
    assert "none of that is true of you" in text
    assert "promise nothing beyond this conversation" in text
    # A direct "did you save that?" / "will you remember?" has a true answer.
    assert "the true answer is: not yet" in text


@pytest.mark.parametrize("message", STATEMENTS)
def test_what_the_user_just_said_counts_as_in_front_of_the_model(conn, message):
    # Rule 4's "say you do not have it in front of you" is for a fact the user
    # asks for. A fact the user has just given is in front of the model, and
    # "I don't have that in front of me" is no reply to it.
    text = _context_for(conn, message)

    assert "when the user tells you something about themselves, it is in front of you" in text
    assert "reply to what they said and use it for the rest of this conversation" in text


@pytest.mark.parametrize("message", STATEMENTS)
def test_the_reminder_is_the_last_thing_the_model_reads_before_the_conversation(conn, message):
    text = _context_for(conn, message)

    reminder = "before you reply: you cannot save anything."
    assert reminder in text
    # After the profile, the decisions and everything else the context holds:
    # nothing follows the reminder but the messages themselves.
    tail = text[text.rindex(reminder):]
    assert tail.endswith("but that is not certain.")
    assert "lanternfish" not in tail
    assert text.index("lanternfish") < text.rindex(reminder)
    assert "if the user asks you to remember something, or asks whether you saved or will remember it" in tail
    assert "the answer is: not yet" in tail
