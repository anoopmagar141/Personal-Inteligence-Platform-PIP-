from backend.stages import stage_07_context_assembly as stage_07


def _words(n: int, prefix: str = "word") -> str:
    return " ".join(f"{prefix}{i}" for i in range(n))


def test_minimal_call_produces_system_and_message_only():
    result = stage_07.run("Hello there")
    assert result["messages"] == [{"role": "user", "content": "Hello there"}]
    assert "Hello there" not in result["context"]  # message lives in messages, not context
    assert len(result["context"]) > 0  # system instructions still present


def test_includes_all_sections_when_under_budget():
    result = stage_07.run(
        "What did we decide?",
        profile_fields=[{"table": "preference_memory", "field": "editor", "value": "Neovim"}],
        session_snapshot={"topic": "Building inventory sync", "last_decisions": ["Chose FastAPI"], "open_problems": [], "suggested_next_step": "write tests"},
        decision_log_entries=[{"decision_text": "We chose FastAPI over Flask"}],
        rag_chunks=[{"file_path": "notes.txt", "chunk_text": "PIP uses SQLCipher"}],
        web_results=[{"title": "FastAPI docs", "snippet": "Modern async framework", "url": "https://fastapi.tiangolo.com"}],
        conversation_history=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}],
    )
    assert "Neovim" in result["context"]
    assert "Building inventory sync" in result["context"]
    assert "FastAPI over Flask" in result["context"]
    assert "SQLCipher" in result["context"]
    assert "FastAPI docs" in result["context"]
    assert result["messages"][0] == {"role": "user", "content": "hi"}
    assert result["messages"][-1] == {"role": "user", "content": "What did we decide?"}


def test_profile_truncated_to_its_own_budget():
    huge_profile = [{"table": "preference_memory", "field": f"pref{i}", "value": _words(20)} for i in range(50)]
    result = stage_07.run("question", profile_fields=huge_profile)
    # user_profile_tokens budget is 400 - the formatted block (plus its own header
    # words) must not run wildly past that.
    assert stage_07._estimate_tokens(result["context"]) < 500


def test_conversation_history_keeps_most_recent_not_oldest():
    history = [{"role": "user", "content": f"message {i} " + _words(200)} for i in range(20)]
    result = stage_07.run("current question", conversation_history=history)
    contents = [m["content"] for m in result["messages"]]
    assert "message 19" in contents[-2]  # most recent kept (last before the final user message)
    assert "message 0" not in " ".join(contents)  # oldest dropped


def test_overflow_drops_web_results_before_decision_log():
    # Deliberately oversized sections so post-per-source-truncation totals exceed
    # the 4000-token content budget (6000 total - 2000 reserved), forcing the
    # overflow trim to actually run. History is many small messages, not one huge
    # one - a single message bigger than the whole history budget gets dropped as
    # a whole unit by the rolling window (reasonable: you don't truncate mid-turn),
    # which would zero out its contribution before the overflow pass even runs and
    # undershoot the budget instead of exceeding it.
    history = [{"role": "user", "content": _words(120)} for _ in range(10)]
    result = stage_07.run(
        "question " + _words(50),
        system_instructions=_words(150),
        profile_fields=[{"table": "preference_memory", "field": "p", "value": _words(500)}],
        session_snapshot={"topic": _words(300), "last_decisions": [], "open_problems": [], "suggested_next_step": ""},
        decision_log_entries=[{"decision_text": _words(700)}],
        rag_chunks=[{"file_path": "f", "chunk_text": _words(900)}],
        web_results=[{"title": "t", "snippet": _words(900), "url": "u"}],
        conversation_history=history,
    )
    assert "RELEVANT DECISIONS" in result["context"]  # rank 1 (most protected) survives
    assert "WEB SEARCH RESULTS" not in result["context"]  # rank 6 (least protected) dropped first
    assert stage_07._estimate_tokens(result["context"]) <= stage_07.get_settings()["pipeline"]["context_token_budget"]


def test_worst_case_everything_maxed_falls_back_to_system_and_message_only():
    result = stage_07.run(
        "the question",
        system_instructions=_words(150),
        profile_fields=[{"table": "preference_memory", "field": "p", "value": _words(500)}],
        session_snapshot={"topic": _words(300), "last_decisions": [], "open_problems": [], "suggested_next_step": ""},
        decision_log_entries=[{"decision_text": _words(700)}],
        rag_chunks=[{"file_path": "f", "chunk_text": _words(900)}],
        web_results=[{"title": "t", "snippet": _words(900), "url": "u"}],
        conversation_history=[{"role": "user", "content": _words(1100)}],
    )
    total = stage_07._estimate_tokens(result["context"]) + sum(
        stage_07._estimate_tokens(m["content"]) for m in result["messages"]
    )
    available = stage_07.get_settings()["pipeline"]["context_token_budget"] - stage_07.get_settings()["pipeline"]["response_reserved_tokens"]
    assert total <= available


def test_empty_session_snapshot_produces_no_section():
    result = stage_07.run("q", session_snapshot={"topic": "", "last_decisions": [], "open_problems": [], "suggested_next_step": ""})
    assert "SESSION SNAPSHOT" not in result["context"]


def test_fails_open_to_minimal_prompt_on_error(monkeypatch):
    monkeypatch.setattr(stage_07, "get_settings", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    result = stage_07.run("hello", system_instructions="SYS")
    assert result == {"context": "SYS", "messages": [{"role": "user", "content": "hello"}]}
