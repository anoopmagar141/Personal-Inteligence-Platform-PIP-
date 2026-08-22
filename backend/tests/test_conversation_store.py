import sqlite3

import pytest

from backend.memory import conversation_store, profile_store


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "pip.db"
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    profile_store.initialize_schema(connection)
    yield connection
    connection.close()


def test_create_conversation_defaults_to_new_chat_title(conn):
    conversation_id = conversation_store.create_conversation(conn)
    conversations = conversation_store.list_conversations(conn)
    assert len(conversations) == 1
    assert conversations[0]["id"] == conversation_id
    assert conversations[0]["title"] == "New chat"
    assert conversations[0]["project_id"] is None


def test_append_message_auto_titles_from_first_user_message(conn):
    conversation_id = conversation_store.create_conversation(conn)
    conversation_store.append_message(conn, conversation_id, "user", "What's the plan for tomorrow?")

    conversations = conversation_store.list_conversations(conn)
    assert conversations[0]["title"] == "What's the plan for tomorrow?"


def test_append_message_truncates_long_titles(conn):
    conversation_id = conversation_store.create_conversation(conn)
    long_message = "x" * 200
    conversation_store.append_message(conn, conversation_id, "user", long_message)

    title = conversation_store.list_conversations(conn)[0]["title"]
    assert len(title) <= conversation_store.TITLE_MAX_LENGTH + 3  # + "..."
    assert title.endswith("...")


def test_append_message_never_retitles_after_first_user_message(conn):
    conversation_id = conversation_store.create_conversation(conn)
    conversation_store.append_message(conn, conversation_id, "user", "First message")
    conversation_store.append_message(conn, conversation_id, "assistant", "A reply")
    conversation_store.append_message(conn, conversation_id, "user", "Second message, should not retitle")

    title = conversation_store.list_conversations(conn)[0]["title"]
    assert title == "First message"


def test_get_messages_returns_in_order(conn):
    conversation_id = conversation_store.create_conversation(conn)
    conversation_store.append_message(conn, conversation_id, "user", "hello")
    conversation_store.append_message(conn, conversation_id, "assistant", "hi there")

    messages = conversation_store.get_messages(conn, conversation_id)
    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "hello"),
        ("assistant", "hi there"),
    ]


def test_get_messages_empty_for_unknown_conversation(conn):
    assert conversation_store.get_messages(conn, "does-not-exist") == []


def test_list_conversations_orders_most_recently_updated_first(conn):
    first = conversation_store.create_conversation(conn, timestamp="2026-01-01T00:00:00Z")
    second = conversation_store.create_conversation(conn, timestamp="2026-01-02T00:00:00Z")
    # Touch the first one AFTER the second was created - it should now sort first.
    conversation_store.append_message(conn, first, "user", "hi", timestamp="2026-01-03T00:00:00Z")

    ids = [c["id"] for c in conversation_store.list_conversations(conn)]
    assert ids == [first, second]


def test_list_conversations_filters_by_project(conn):
    from backend.memory import profile_store as ps

    project_a_id = ps.create_project(conn, "Project A")
    project_b_id = ps.create_project(conn, "Project B")
    conversation_a = conversation_store.create_conversation(conn, project_id=project_a_id)
    conversation_store.create_conversation(conn, project_id=project_b_id)

    results = conversation_store.list_conversations(conn, project_id=project_a_id)
    assert [c["id"] for c in results] == [conversation_a]


def test_conversation_exists(conn):
    conversation_id = conversation_store.create_conversation(conn)
    assert conversation_store.conversation_exists(conn, conversation_id) is True
    assert conversation_store.conversation_exists(conn, "not-a-real-id") is False


def test_delete_conversation_removes_it_and_its_messages(conn):
    conversation_id = conversation_store.create_conversation(conn)
    conversation_store.append_message(conn, conversation_id, "user", "hello")

    deleted = conversation_store.delete_conversation(conn, conversation_id)
    assert deleted is True
    assert conversation_store.list_conversations(conn) == []
    assert conversation_store.get_messages(conn, conversation_id) == []


def test_delete_conversation_returns_false_for_unknown_id(conn):
    assert conversation_store.delete_conversation(conn, "not-a-real-id") is False
