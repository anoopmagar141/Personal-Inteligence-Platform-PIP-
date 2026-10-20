"""
One checked record per chat, the "small PIP" (BLUEPRINT card #13; PROTECTED).

What was wrong: "where we left off" was ONE row per profile (session_snapshot, CHECK (id = 1)), overwritten by
every chat that passed the substance check and loaded into every project's prompt. Each chat's summary replaced
the last one, a chat started in one project was shown another project's last chat, and deleting any chat cleared
the note whichever chat had written it (P-2, FREEZE_LIST §7.53), because the row did not say.

Built in four parts (the card); this file holds them in order:
  1. one record per chat, written by the Observer at chat end, deleted with its chat; today's single note
     becomes the first record on upgrade.

Driven through the real session-end path with a stand-in model playing the Observer's LLM.
"""

import json

import pytest

from backend.api import server
from backend.memory import conversation_store, profile_store, session_snapshot
from backend.memory.profile_store import get_connection, initialize_schema
from backend.providers.base_provider import BaseLLMProvider
from backend.stages import stage_11_observer as observer

ZEPHYR, LANTERNFISH = "Zephyr warehouse migration", "Lanternfish budgeting app"


class _Model(BaseLLMProvider):
    def __init__(self, topic):
        self.answer = json.dumps({
            "memory_candidates": [], "decision_candidates": [],
            "session_snapshot": {"topic": topic, "open_problems": [f"{topic}: the open question"],
                                 "last_decisions": [], "suggested_next_step": f"{topic}: the next step"},
        })

    def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
        yield self.answer

    def is_available(self):
        return True

    def get_model_info(self):
        return {"provider_id": "ollama", "is_local": True, "model_name": "recorder"}


@pytest.fixture
def conn(tmp_path, db_key):
    c = get_connection(str(tmp_path / "pip.db"), db_key=db_key)
    initialize_schema(c)
    yield c
    c.close()


def _talk(topic):
    # Two substantive user turns: the substance check a record has to pass.
    return (f"User: Let's plan the {topic} together today.\nAssistant: Sure.\n"
            f"User: What should the first step of the {topic} be?\nAssistant: Start small.\n")


def _end(conn, chat_id, topic, *, project_id=None, transcript=None):
    observer.run_session_end(conn, transcript or _talk(topic), _Model(topic), project_id=project_id,
                             conversation_id=chat_id)


def _records(conn):
    return [dict(r) for r in conn.execute("SELECT * FROM chat_records ORDER BY id")]


# --- part 1: one record per chat ---------------------------------------------------------------------------------


def test_each_chat_keeps_its_own_record(conn):
    a, b = conversation_store.create_conversation(conn), conversation_store.create_conversation(conn)

    _end(conn, a, ZEPHYR)
    _end(conn, b, LANTERNFISH)

    assert [(r["conversation_id"], r["topic"], r["source"]) for r in _records(conn)] == [
        (a, ZEPHYR, "observer"), (b, LANTERNFISH, "observer")]
    assert json.loads(_records(conn)[0]["open_problems"]) == [f"{ZEPHYR}: the open question"]


def test_a_later_pass_of_the_same_chat_replaces_only_its_own_record(conn):
    a, b = conversation_store.create_conversation(conn), conversation_store.create_conversation(conn)
    _end(conn, a, ZEPHYR)
    _end(conn, b, LANTERNFISH)

    _end(conn, a, "Zephyr cutover plan")

    assert [(r["conversation_id"], r["topic"]) for r in _records(conn)] == [
        (a, "Zephyr cutover plan"), (b, LANTERNFISH)]


def test_a_chat_with_nothing_substantive_writes_no_record(conn):
    a = conversation_store.create_conversation(conn)

    _end(conn, a, "Greetings", transcript="User: hi\nAssistant: Hello! How can I help?\nUser: thanks\n")

    assert _records(conn) == []


def test_a_pass_with_no_chat_adds_a_record_of_its_own(conn):
    _end(conn, None, ZEPHYR)
    _end(conn, None, LANTERNFISH)

    assert [(r["conversation_id"], r["topic"]) for r in _records(conn)] == [(None, ZEPHYR), (None, LANTERNFISH)]


def test_a_record_keeps_its_chats_project(conn):
    project = profile_store.create_project(conn, "Zephyr", "Warehouse migration")
    a = conversation_store.create_conversation(conn, project)

    _end(conn, a, ZEPHYR, project_id=project)

    assert [(r["conversation_id"], r["project_id"]) for r in _records(conn)] == [(a, project)]


def test_the_next_chat_is_still_shown_the_newest_record(conn):
    # Part 1 keeps today's behaviour for the next chat (the newest summary); part 2 chooses by chat and project.
    a, b = conversation_store.create_conversation(conn), conversation_store.create_conversation(conn)
    _end(conn, a, ZEPHYR)
    _end(conn, b, LANTERNFISH)

    assert session_snapshot.load_snapshot(conn)["topic"] == LANTERNFISH


def test_deleting_a_chat_deletes_its_record_and_only_its_record(conn):
    a, b = conversation_store.create_conversation(conn), conversation_store.create_conversation(conn)
    _end(conn, a, ZEPHYR)
    _end(conn, b, LANTERNFISH)

    server.api_delete_conversation(conn, b)

    assert [(r["conversation_id"], r["topic"]) for r in _records(conn)] == [(a, ZEPHYR)]
    assert session_snapshot.load_snapshot(conn)["topic"] == ZEPHYR


def test_a_record_change_moves_the_record_version(conn):
    # chat_records reaches the prompt, so a change has to retire answers cached before it.
    a = conversation_store.create_conversation(conn)
    before = profile_store.record_version(conn)

    _end(conn, a, ZEPHYR)

    assert profile_store.record_version(conn) > before


def test_an_upgraded_databases_single_note_becomes_its_first_record(conn):
    # A database from before #13: no chat_records table, the note in the singleton row.
    conn.execute("DROP TABLE chat_records")
    conn.execute(
        "INSERT INTO session_snapshot (id, topic, open_problems, last_decisions, suggested_next_step, snapshot_date) "
        "VALUES (1, ?, ?, ?, ?, ?)",
        (ZEPHYR, json.dumps(["cutover window"]), json.dumps(["inventory first"]), "draft the plan",
         "2026-10-01T09:00:00Z"),
    )
    conn.commit()

    initialize_schema(conn)
    initialize_schema(conn)  # a second start must not copy it twice

    records = _records(conn)
    assert [(r["conversation_id"], r["project_id"], r["topic"], r["source"], r["record_date"]) for r in records] == [
        (None, None, ZEPHYR, "earlier_note", "2026-10-01T09:00:00Z")]
    assert json.loads(records[0]["open_problems"]) == ["cutover window"]
    assert json.loads(records[0]["last_decisions"]) == ["inventory first"]
    assert records[0]["suggested_next_step"] == "draft the plan"
    assert conn.execute("SELECT COUNT(*) FROM session_snapshot").fetchone()[0] == 0
    assert session_snapshot.load_snapshot(conn)["topic"] == ZEPHYR


# --- part 2: a new chat reads the right record ---------------------------------------------------------------------

from backend.core import pipeline, response_cache  # noqa: E402


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


def _prompt(conn, message, **where):
    recorder = _Recorder()
    pipeline.run_sync(conn, message, providers=[recorder], **where)
    return recorder.prompts[-1] if recorder.prompts else ""


@pytest.fixture
def two_projects(conn):
    """Zephyr's chat ends first, Lanternfish's later: the newest record is Lanternfish's."""
    response_cache.clear()
    zephyr = profile_store.create_project(conn, "Zephyr", "Warehouse migration")
    lanternfish = profile_store.create_project(conn, "Lanternfish", "Budgeting app")
    z_chat = conversation_store.create_conversation(conn, zephyr)
    l_chat = conversation_store.create_conversation(conn, lanternfish)
    _end(conn, z_chat, ZEPHYR, project_id=zephyr)
    conn.execute("UPDATE chat_records SET record_date = '2026-10-01T09:00:00Z' WHERE conversation_id = ?", (z_chat,))
    _end(conn, l_chat, LANTERNFISH, project_id=lanternfish)
    conn.commit()
    yield {"zephyr": zephyr, "lanternfish": lanternfish, "z_chat": z_chat, "l_chat": l_chat}
    response_cache.clear()


def test_a_resumed_chat_is_shown_its_own_record(conn, two_projects):
    p = two_projects
    prompt = _prompt(conn, "where were we?", project_id=p["zephyr"], conversation_id=p["z_chat"])

    assert ZEPHYR in prompt and LANTERNFISH not in prompt


def test_a_new_chat_in_a_project_is_shown_that_projects_last_record(conn, two_projects):
    p = two_projects
    new_chat = conversation_store.create_conversation(conn, p["zephyr"])

    prompt = _prompt(conn, "where were we?", project_id=p["zephyr"], conversation_id=new_chat)

    assert ZEPHYR in prompt and LANTERNFISH not in prompt


@pytest.mark.parametrize("in_a_project", [False, True], ids=["no project", "a project with no record"])
def test_a_new_chat_with_nothing_closer_is_shown_the_newest_record(conn, two_projects, in_a_project):
    project = profile_store.create_project(conn, "Pebblebox", "Recipes") if in_a_project else None
    new_chat = conversation_store.create_conversation(conn, project)

    prompt = _prompt(conn, "where were we?", project_id=project, conversation_id=new_chat)

    assert LANTERNFISH in prompt and ZEPHYR not in prompt


def test_the_record_says_when_it_was_written_and_that_pip_wrote_it(conn, two_projects):
    p = two_projects
    prompt = _prompt(conn, "where were we?", project_id=p["zephyr"], conversation_id=p["z_chat"])

    assert "2026-10-01" in prompt
    assert "written by PIP" in prompt and "may be wrong" in prompt


def test_two_chats_do_not_share_an_answer_cached_from_a_different_record(conn, two_projects):
    # A general question is cached; before #13 every chat got the same note, so the key needed no chat. Now two
    # chats can get different records, and an answer built from one must not be served in the other.
    p = two_projects
    question = "how does a hash map handle collisions?"
    first = _Recorder()
    pipeline.run_sync(conn, question, providers=[first], project_id=p["zephyr"], conversation_id=p["z_chat"])
    second = _Recorder()
    pipeline.run_sync(conn, question, providers=[second], project_id=p["zephyr"],
                      conversation_id=conversation_store.create_conversation(conn, p["zephyr"]))
    third = _Recorder()
    pipeline.run_sync(conn, question, providers=[third], project_id=p["lanternfish"], conversation_id=p["l_chat"])

    assert len(first.prompts) == 1
    assert second.prompts == [], "same record (Zephyr's), so the cached answer is reused"
    assert len(third.prompts) == 1 and LANTERNFISH in third.prompts[0]


@pytest.fixture
def one_project_two_chats(conn):
    """Two chats in one project, each with its own record; the second chat's is newer."""
    response_cache.clear()
    zephyr = profile_store.create_project(conn, "Zephyr", "Warehouse migration")
    first = conversation_store.create_conversation(conn, zephyr)
    second = conversation_store.create_conversation(conn, zephyr)
    _end(conn, first, ZEPHYR, project_id=zephyr)
    conn.execute("UPDATE chat_records SET record_date = '2026-10-01T09:00:00Z' WHERE conversation_id = ?", (first,))
    _end(conn, second, "Zephyr cutover plan", project_id=zephyr)
    conn.commit()
    yield {"zephyr": zephyr, "first": first, "second": second}
    response_cache.clear()


def test_a_resumed_chat_is_shown_its_own_record_not_its_projects_newer_one(conn, one_project_two_chats):
    p = one_project_two_chats
    prompt = _prompt(conn, "where were we?", project_id=p["zephyr"], conversation_id=p["first"])

    assert "warehouse migration" in prompt and "cutover plan" not in prompt


def test_two_chats_in_one_project_do_not_share_an_answer_cached_from_a_different_record(conn, one_project_two_chats):
    # Same message, same project, same record version: only the record each chat is given differs.
    p = one_project_two_chats
    question = "how does a hash map handle collisions?"
    first = _Recorder()
    pipeline.run_sync(conn, question, providers=[first], project_id=p["zephyr"], conversation_id=p["first"])
    second = _Recorder()
    pipeline.run_sync(conn, question, providers=[second], project_id=p["zephyr"], conversation_id=p["second"])

    assert len(first.prompts) == 1 and "warehouse migration" in first.prompts[0]
    assert len(second.prompts) == 1 and "cutover plan" in second.prompts[0]


# --- part 3: not yet summarised --------------------------------------------------------------------------------------


def _say(conn, chat_id, *turns):
    for role, text in turns:
        conversation_store.append_message(conn, chat_id, role, text)


@pytest.fixture
def fresh_cache():
    response_cache.clear()
    yield
    response_cache.clear()


def test_a_new_chat_is_shown_the_previous_chats_messages_not_yet_summarised(conn, fresh_cache):
    # The previous chat has ended but its Observer pass has not run, so it has no record yet: before #13 a chat
    # opened right after it was given an older note, or none.
    project = profile_store.create_project(conn, "Zephyr", "Warehouse migration")
    previous = conversation_store.create_conversation(conn, project)
    _say(conn, previous, ("user", "We agreed the Zephyr cutover happens on a Sunday night."),
         ("assistant", "Sunday night it is; I'll keep the rollback plan short."))
    new_chat = conversation_store.create_conversation(conn, project)

    prompt = _prompt(conn, "where were we?", project_id=project, conversation_id=new_chat)

    assert "Zephyr cutover happens on a Sunday night" in prompt
    assert "not yet summarised" in prompt


def test_messages_already_summarised_are_not_repeated(conn, fresh_cache):
    project = profile_store.create_project(conn, "Zephyr", "Warehouse migration")
    previous = conversation_store.create_conversation(conn, project)
    _say(conn, previous, ("user", "We agreed the Zephyr cutover happens on a Sunday night."))
    conversation_store.mark_observed(conn, previous, timestamp="2099-01-01T00:00:00Z")
    new_chat = conversation_store.create_conversation(conn, project)

    prompt = _prompt(conn, "where were we?", project_id=project, conversation_id=new_chat)

    assert "Sunday night" not in prompt and "not yet summarised" not in prompt


def test_only_the_same_projects_previous_chat_is_used(conn, fresh_cache):
    zephyr = profile_store.create_project(conn, "Zephyr", "Warehouse migration")
    lanternfish = profile_store.create_project(conn, "Lanternfish", "Budgeting app")
    z_chat = conversation_store.create_conversation(conn, zephyr)
    conversation_store.append_message(conn, z_chat, "user", "We agreed the Zephyr cutover happens on a Sunday night.",
                                      timestamp="2026-10-18T10:00:00Z")
    # Lanternfish's chat is the newer one overall, so only the project decides.
    l_chat = conversation_store.create_conversation(conn, lanternfish)
    conversation_store.append_message(conn, l_chat, "user", "Lanternfish should split shared expenses by member.",
                                      timestamp="2026-10-18T11:00:00Z")
    new_chat = conversation_store.create_conversation(conn, zephyr)

    prompt = _prompt(conn, "where were we?", project_id=zephyr, conversation_id=new_chat)

    assert "Sunday night" in prompt and "split shared expenses" not in prompt


def test_a_chat_with_its_own_record_is_not_shown_another_chats_messages(conn, fresh_cache):
    project = profile_store.create_project(conn, "Zephyr", "Warehouse migration")
    resumed = conversation_store.create_conversation(conn, project)
    _end(conn, resumed, ZEPHYR, project_id=project)
    other = conversation_store.create_conversation(conn, project)
    _say(conn, other, ("user", "We agreed the Zephyr cutover happens on a Sunday night."))

    prompt = _prompt(conn, "where were we?", project_id=project, conversation_id=resumed)

    assert "warehouse migration" in prompt and "Sunday night" not in prompt


def test_a_new_unsummarised_message_retires_an_answer_cached_without_it(conn, fresh_cache):
    # Messages do not move the record version (they are written on every turn), so the key has to name them.
    project = profile_store.create_project(conn, "Zephyr", "Warehouse migration")
    previous = conversation_store.create_conversation(conn, project)
    _say(conn, previous, ("user", "We agreed the Zephyr cutover happens on a Sunday night."))
    question = "how does a hash map handle collisions?"
    first = _Recorder()
    pipeline.run_sync(conn, question, providers=[first], project_id=project,
                      conversation_id=conversation_store.create_conversation(conn, project))

    _say(conn, previous, ("user", "Actually, make the Zephyr cutover a Saturday night."))
    second = _Recorder()
    pipeline.run_sync(conn, question, providers=[second], project_id=project,
                      conversation_id=conversation_store.create_conversation(conn, project))

    assert len(first.prompts) == 1
    assert len(second.prompts) == 1 and "Saturday night" in second.prompts[0]


def test_an_empty_chat_does_not_hide_the_chat_before_it(conn, fresh_cache):
    # A chat can exist with nothing said in it yet (created, then left); it has no end to show.
    project = profile_store.create_project(conn, "Zephyr", "Warehouse migration")
    previous = conversation_store.create_conversation(conn, project)
    conversation_store.append_message(conn, previous, "user", "We agreed the Zephyr cutover happens on a Sunday night.",
                                      timestamp="2026-10-18T10:00:00Z")
    empty = conversation_store.create_conversation(conn, project, timestamp="2026-10-18T11:00:00Z")
    new_chat = conversation_store.create_conversation(conn, project)

    prompt = _prompt(conn, "where were we?", project_id=project, conversation_id=new_chat)

    assert empty and "Sunday night" in prompt


# --- part 4: read, correct or clear a chat's record, with what it produced -----------------------------------------

from fastapi.testclient import TestClient  # noqa: E402

from backend.core import auth  # noqa: E402

POSTGRES = "I've decided to move our database to Postgres before the next release."


class _ModelWithDecision(_Model):
    def __init__(self, topic):
        super().__init__(topic)
        answer = json.loads(self.answer)
        answer["decision_candidates"] = [{"decision_text": "Move the database to Postgres before the next release.",
                                          "raw_quote": POSTGRES,
                                          "signals_found": ["explicit_reasoning_in_conversation", "commitment_language"]}]
        self.answer = json.dumps(answer)


@pytest.fixture
def api(tmp_path, monkeypatch):
    """The real routes over one database, as the app reaches them (the shape P-2's route tests use)."""
    db_path = tmp_path / "app.db"
    monkeypatch.setenv("PIP_DB_PATH", str(db_path))
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    token = auth.get_or_create_token(tmp_path / "api_token.txt")
    client = TestClient(server.app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    db = server.open_app_connection(str(db_path), None)
    response_cache.clear()
    try:
        yield client, db
    finally:
        response_cache.clear()
        db.close()


def _record_url(chat_id):
    return f"/api/v1/conversations/{chat_id}/record"


def test_a_chats_record_is_read_with_what_the_chat_produced(api):
    client, db = api
    chat = conversation_store.create_conversation(db)
    transcript = f"User: {POSTGRES}\nAssistant: Postgres will handle the concurrency.\nUser: Good, let's plan the migration.\n"
    observer.run_session_end(db, transcript, _ModelWithDecision(ZEPHYR), conversation_id=chat)

    body = client.get(_record_url(chat)).json()

    assert body["record"]["topic"] == ZEPHYR and body["record"]["source"] == "observer"
    assert [d["decision_text"] for d in body["links"]["decisions"]] == [
        "Move the database to Postgres before the next release."]
    assert body["links"]["outcomes"] == {"accepted": 1}


def test_correcting_a_record_makes_it_the_users(api):
    client, db = api
    chat = conversation_store.create_conversation(db)
    _end(db, chat, ZEPHYR)

    response = client.put(_record_url(chat), json={
        "topic": "Zephyr cutover rehearsal", "open_problems": ["who signs off"], "last_decisions": [],
        "suggested_next_step": "book the rehearsal"})

    assert response.status_code == 200
    record = client.get(_record_url(chat)).json()["record"]
    assert (record["topic"], record["source"], record["open_problems"]) == (
        "Zephyr cutover rehearsal", "user", ["who signs off"])
    prompt = _prompt(db, "where were we?", conversation_id=chat)
    assert "Zephyr cutover rehearsal" in prompt and "corrected by the user" in prompt


def test_the_observer_does_not_overwrite_the_users_correction(api):
    client, db = api
    chat = conversation_store.create_conversation(db)
    _end(db, chat, ZEPHYR)
    client.put(_record_url(chat), json={"topic": "Zephyr cutover rehearsal", "open_problems": [],
                                        "last_decisions": [], "suggested_next_step": ""})

    _end(db, chat, "something the model made up")

    assert client.get(_record_url(chat)).json()["record"]["topic"] == "Zephyr cutover rehearsal"


def test_clearing_a_record_removes_it_from_the_next_prompt(api):
    client, db = api
    chat = conversation_store.create_conversation(db)
    _end(db, chat, ZEPHYR)

    response = client.delete(_record_url(chat))

    assert response.status_code == 200 and response.json() == {"status": "cleared"}
    assert client.get(_record_url(chat)).json()["record"] is None
    assert "Zephyr" not in _prompt(db, "where were we?", conversation_id=chat)


@pytest.mark.parametrize("payload", [
    {"topic": "", "open_problems": [], "last_decisions": [], "suggested_next_step": ""},
    {"topic": "Zephyr", "open_problems": "not a list", "last_decisions": [], "suggested_next_step": ""},
    {"topic": "Zephyr", "open_problems": [], "last_decisions": [3], "suggested_next_step": ""},
    {"topic": "x" * 301, "open_problems": [], "last_decisions": [], "suggested_next_step": ""},
], ids=["empty topic", "problems not a list", "decision not text", "topic too long"])
def test_a_correction_that_is_not_a_record_is_refused_with_a_sentence(api, payload):
    client, db = api
    chat = conversation_store.create_conversation(db)

    response = client.put(_record_url(chat), json=payload)

    assert response.status_code == 422 and isinstance(response.json()["detail"], str)
    assert client.get(_record_url(chat)).json()["record"] is None


def test_an_unknown_chat_has_no_record_to_read_correct_or_clear(api):
    client, _ = api
    good = {"topic": "Zephyr", "open_problems": [], "last_decisions": [], "suggested_next_step": ""}

    assert client.get(_record_url("no-such-chat")).status_code == 404
    assert client.put(_record_url("no-such-chat"), json=good).status_code == 404
    assert client.delete(_record_url("no-such-chat")).status_code == 404
