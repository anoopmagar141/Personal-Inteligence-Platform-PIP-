"""
What the model is given when it is asked about the user (docs/FREEZE_LIST.md
§7.5 and §7.6).

Asserted on the prompt the model actually receives, through the real
pipeline, with a recording provider standing in for the model. The Stage 1
tests assert on the intent label; that is how every case below passed review
while the model was being handed nothing about the user's projects.
"""

import pytest

from backend.core import pipeline, response_cache
from backend.memory import profile_store, vector_store
from backend.memory.profile_store import get_connection, initialize_schema
from backend.providers.base_provider import BaseLLMProvider

NAME = "Zarqa Venn"
PROJECT = "Heliotrope"


class RecordingProvider(BaseLLMProvider):
    def __init__(self):
        self.prompts: list[str] = []

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
        self.prompts.append((context or "") + "\n" + "\n".join(m.get("content", "") for m in messages))
        yield f"ANSWER#{len(self.prompts)}"

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
    yield connection
    connection.close()


@pytest.fixture
def seeded(conn):
    profile_store.complete_onboarding(conn, name=NAME, language_preference="English")
    profile_store.create_project(conn, PROJECT, "Final year thesis platform")
    return conn


def _prompt_for(conn, question) -> str:
    provider = RecordingProvider()
    pipeline.run_sync(conn, question, providers=[provider])
    assert provider.prompts, f"the model was never called for {question!r}"
    return provider.prompts[-1]


# The Track 4a probe, verbatim. The first four were the only ones that
# reached the model with the project: the rest were routed to a category whose
# Stage 4 table set holds neither identity nor projects.
QUESTIONS_ABOUT_THE_USER = [
    "who am I?",
    "what's my name?",
    "list my projects",
    "what are my goals?",
    "what is my current project?",
    "what's the latest on my project?",
    "what have I been working on recently?",
    "what am I working on right now?",
    "what should I do today on my thesis?",
    "what am I working on?",
    "where did we leave off?",
    "help me implement the next step of my project",
    "debug the login bug in my project",
    "compare my project vs a typical final year project",
]


@pytest.mark.parametrize("question", QUESTIONS_ABOUT_THE_USER)
def test_every_question_reaches_the_model_with_the_users_identity_and_projects(seeded, question):
    prompt = _prompt_for(seeded, question)

    assert NAME in prompt, "identity was not in the prompt"
    assert PROJECT in prompt, "the active project was not in the prompt"
