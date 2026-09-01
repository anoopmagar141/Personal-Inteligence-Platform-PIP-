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
    # Measures the profile block alone, not the whole context. Asserting on the
    # total conflated two unrelated things and only held while the system
    # instructions happened to be one sentence: rewriting them for grounding
    # (longer by design - four numbered rules) pushed the total to 522 and
    # failed this, despite the profile block itself still being truncated
    # correctly to its 400-token budget. The prelude's length is not what this
    # test is about.
    profile_block = result["context"][len(stage_07._DEFAULT_SYSTEM_INSTRUCTIONS):]
    # 400-token budget plus the block's own heading words and the "..." marker.
    assert stage_07._estimate_tokens(profile_block) < 450


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


def test_context_depth_modifier_zero_drops_snapshot_when_live_history_covers_it():
    # The premise modifier=0 rests on: the user never really left, and the
    # conversation they are still in already carries the recap.
    snapshot = {"topic": "Building inventory sync", "last_decisions": [], "open_problems": [], "suggested_next_step": ""}
    result = stage_07.run(
        "q",
        session_snapshot=snapshot,
        context_depth_modifier=0,
        conversation_history=[{"role": "user", "content": "earlier in this same chat"}],
    )
    assert "SESSION SNAPSHOT" not in result["context"]
    assert "Building inventory sync" not in result["context"]


def test_context_depth_modifier_zero_keeps_snapshot_in_a_fresh_conversation():
    # A new chat window is a new session, so Stage 0 reports a sub-hour gap and
    # hands down modifier=0 - but there is no history in this conversation for
    # the recap to be redundant WITH. Dropping it here is what made "what we
    # were doing last time" unanswerable within an hour of the last message.
    snapshot = {"topic": "Building inventory sync", "last_decisions": [], "open_problems": [], "suggested_next_step": ""}
    result = stage_07.run("q", session_snapshot=snapshot, context_depth_modifier=0, conversation_history=[])
    assert "SESSION SNAPSHOT" in result["context"]
    assert "Building inventory sync" in result["context"]


def test_continuation_question_keeps_snapshot_even_mid_conversation():
    # Asked outright, the snapshot is the answer - a live history does not make
    # it redundant, it just means the gap was short.
    snapshot = {"topic": "Building inventory sync", "last_decisions": [], "open_problems": [], "suggested_next_step": ""}
    result = stage_07.run(
        "what were we doing last time?",
        session_snapshot=snapshot,
        context_depth_modifier=0,
        conversation_history=[{"role": "user", "content": "earlier in this same chat"}],
        category="project_continuation",
    )
    assert "SESSION SNAPSHOT" in result["context"]
    assert "Building inventory sync" in result["context"]


def test_context_depth_modifier_two_matches_default_fixed_budget():
    snapshot = {"topic": "Building inventory sync", "last_decisions": [], "open_problems": [], "suggested_next_step": ""}
    default_result = stage_07.run("q", session_snapshot=snapshot)
    modifier_two_result = stage_07.run("q", session_snapshot=snapshot, context_depth_modifier=2)
    assert default_result["context"] == modifier_two_result["context"]


def test_context_depth_modifier_three_allows_a_larger_snapshot_than_default():
    # A snapshot big enough to get truncated at the default (modifier=2) budget
    # must survive intact at modifier=3's 1.5x budget.
    snapshot = {"topic": _words(300), "last_decisions": [], "open_problems": [], "suggested_next_step": ""}
    default_result = stage_07.run("q", session_snapshot=snapshot, context_depth_modifier=2)
    full_result = stage_07.run("q", session_snapshot=snapshot, context_depth_modifier=3)
    assert "..." in default_result["context"]  # truncated at the base 250-token budget
    assert "..." not in full_result["context"]  # fits whole at the 375-token budget


def test_fails_open_to_minimal_prompt_on_error(monkeypatch):
    monkeypatch.setattr(stage_07, "get_settings", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    result = stage_07.run("hello", system_instructions="SYS")
    assert result == {"context": "SYS", "messages": [{"role": "user", "content": "hello"}]}


# --- Grounding: the anti-confabulation contract (regression tests) ---
#
# These cover a live end-to-end failure, not a hypothetical. Asked "list the
# projects I have" against a profile holding exactly one real project, the
# model returned three invented ones with fabricated progress reports - and did
# so again after the fabricated data had been cleaned out of the database,
# because the prompt itself was the remaining cause. Nothing in this file
# tested what the assembled context ASSERTS, only which substrings it
# contained, so the format could (and did) drift into something a model read as
# a database dump rather than a statement of record.


def test_profile_marks_lists_complete_so_the_model_cannot_extend_them():
    result = stage_07.run(
        "list my projects",
        profile_fields=[{"table": "active_projects", "field": "PIP", "value": "a personalised system"}],
        category="project_question",
    )
    assert "complete list" in result["context"]
    assert "PIP: a personalised system" in result["context"]


def test_empty_expected_table_is_asserted_as_none_not_silently_omitted():
    # The distinction that decides whether the model answers "you have none" or
    # invents a plausible set: an absent heading reads as "not retrieved", which
    # invites the model to supply what it assumes it wasn't shown.
    result = stage_07.run(
        "what goals do I have?",
        profile_fields=[{"table": "active_projects", "field": "PIP", "value": "a personalised system"}],
        category="project_question",
    )
    assert "Goals: none recorded." in result["context"]


def test_no_category_keeps_the_previous_omit_empty_behaviour():
    # Callers that don't pass a category (tests, direct users) must not suddenly
    # start getting "none recorded" lines for tables they never asked about.
    # Scoped to the profile block on purpose: rule 3 of the system instructions
    # explains what "none recorded" means, so searching the whole context
    # matches the prelude every time and asserts nothing about the profile.
    result = stage_07.run(
        "hello",
        profile_fields=[{"table": "active_projects", "field": "PIP", "value": "a personalised system"}],
    )
    profile_block = result["context"][len(stage_07._DEFAULT_SYSTEM_INSTRUCTIONS):]
    assert "none recorded" not in profile_block


def test_system_instructions_do_not_claim_memory_the_context_may_not_hold():
    # The original wording opened by telling the model it had "access to the
    # user's project history" before showing any, and it duly produced a
    # history to match. The prompt must not assert holdings the context itself
    # has to substantiate.
    text = stage_07._DEFAULT_SYSTEM_INSTRUCTIONS.lower()
    assert "access to the user's project history" not in text
    assert "you have no other memory" in text


def test_system_instructions_require_admitting_missing_data():
    text = stage_07._DEFAULT_SYSTEM_INSTRUCTIONS.lower()
    assert "do not have it recorded" in text


def test_set_membership_rows_are_not_rendered_as_redundant_pairs():
    # preferred_tools stores the tool name in both field and value; "vs code:
    # vs code" is noise that spends budget and reads as malformed.
    result = stage_07.run(
        "what tools do I use?",
        profile_fields=[{"table": "preferred_tools", "field": "vs code", "value": "vs code"}],
    )
    assert "- vs code" in result["context"]
    assert "vs code: vs code" not in result["context"]


def test_grounding_rules_do_not_gag_general_knowledge():
    # The first version of these rules bound to the whole reply rather than to
    # claims about the user, and was tested live: "what is a hash table?"
    # returned "I don't have that recorded." Refusing from an empty profile is
    # the same defect as inventing from one - both substitute the profile for
    # the model's own knowledge.
    text = stage_07._DEFAULT_SYSTEM_INSTRUCTIONS.lower()
    assert "facts about the user only" in text
    assert "not a reason to refuse" in text


def test_instructions_forbid_echoing_the_context_scaffolding():
    # The annotations exist to bound what the model may claim, not to be read
    # aloud; without this the reply opened with the literal words "complete list".
    assert "never repeat them back" in stage_07._DEFAULT_SYSTEM_INSTRUCTIONS.lower()


def test_decision_lines_carry_their_date():
    # created_at was on every row and never reached the prompt, so the log
    # could say what was decided but never when.
    result = stage_07.run(
        "when did we choose it?",
        decision_log_entries=[
            {"decision_text": "We chose FastAPI over Flask", "created_at": "2026-08-16T12:00:00Z"}
        ],
    )
    assert "[2026-08-16] We chose FastAPI over Flask" in result["context"]


def test_decision_without_a_date_still_renders():
    result = stage_07.run(
        "what did we decide?",
        decision_log_entries=[{"decision_text": "We chose FastAPI over Flask"}],
    )
    assert "- We chose FastAPI over Flask" in result["context"]


def test_reasoning_reaches_the_prompt_for_the_top_entries_only():
    entries = [
        {"decision_text": f"Decision {i}", "created_at": "2026-08-16T12:00:00Z",
         "reasoning": f"because of reason{i}"}
        for i in range(stage_07._DECISIONS_WITH_REASONING + 3)
    ]
    context = stage_07.run("why?", decision_log_entries=entries)["context"]

    for i in range(stage_07._DECISIONS_WITH_REASONING):
        assert f"why: because of reason{i}" in context
    # Past the cutoff the decision still appears; only its reasoning is dropped.
    assert f"Decision {stage_07._DECISIONS_WITH_REASONING}" in context
    assert f"reason{stage_07._DECISIONS_WITH_REASONING}" not in context


def test_long_reasoning_is_trimmed_not_dropped():
    entries = [{"decision_text": "Decision", "reasoning": _words(400, prefix="r")}]
    context = stage_07.run("why?", decision_log_entries=entries)["context"]
    assert "why: r0" in context
    assert f"r{stage_07._REASONING_WORDS + 10}" not in context


def test_decision_block_stays_within_its_budget_and_keeps_its_structure():
    # Built up to the budget rather than built whole and truncated: the old
    # path joined on whitespace, which flattened every date and reasoning line
    # into one run-on line as soon as the budget was exceeded.
    entries = [
        {"decision_text": _words(30, prefix=f"d{i}_"), "created_at": "2026-08-16T12:00:00Z",
         "reasoning": _words(100, prefix=f"r{i}_")}
        for i in range(40)
    ]
    budget = stage_07.get_settings()["pipeline"]["decision_log_tokens"]
    block = stage_07._format_decisions(entries, budget)

    assert stage_07._estimate_tokens(block) <= budget
    assert block.count("\n- ") >= 2  # several whole entries, not one flattened line
    assert "..." not in block.splitlines()[1]  # first entry survives intact


def test_single_oversized_decision_is_truncated_rather_than_dropped():
    block = stage_07._format_decisions([{"decision_text": _words(900)}], 600)
    assert block.startswith("RELEVANT DECISIONS")
    assert block.endswith("...")
    assert stage_07._estimate_tokens(block) <= 600


def test_alternatives_considered_reaches_the_prompt():
    """
    The column answering "why X instead of Y" was rendered nowhere, so a
    question naming the rejected option got "I do not have that recorded"
    from a row that stored the answer verbatim.
    """
    entries = [{
        "created_at": "2026-08-18T12:00:00Z",
        "decision_text": "Per-source context ceilings reconciled by overflow trimming.",
        "reasoning": "Phase 8. The itemised budget summed to 6400 against a stated 6000.",
        "alternatives_considered": "Fixed reservations, which cannot be made to sum correctly.",
    }]
    out = stage_07._format_decisions(entries, max_tokens=600)
    assert "instead of: Fixed reservations" in out


def test_alternatives_are_dropped_past_their_window():
    entries = [
        {
            "created_at": "2026-08-18T12:00:00Z",
            "decision_text": f"Decision {i}",
            "alternatives_considered": f"Rejected option {i}",
        }
        for i in range(stage_07._DECISIONS_WITH_ALTERNATIVES + 2)
    ]
    out = stage_07._format_decisions(entries, max_tokens=4000)
    assert "Rejected option 0" in out
    last = stage_07._DECISIONS_WITH_ALTERNATIVES + 1
    assert f"Rejected option {last}" not in out


def test_alternatives_respect_the_token_budget():
    entries = [
        {
            "created_at": "2026-08-18T12:00:00Z",
            "decision_text": f"Decision {i}",
            "alternatives_considered": " ".join(["word"] * 60),
        }
        for i in range(6)
    ]
    out = stage_07._format_decisions(entries, max_tokens=80)
    assert stage_07._estimate_tokens(out) <= 80
