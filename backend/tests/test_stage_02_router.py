from backend.stages import stage_02_router as router


def test_default_priority_matches_adr_023_authority_order():
    result = router.run(category="general_knowledge", skip_rag=True, retrieval_hint="")
    assert result["retrieval_priority"] == ["decision_log", "memory", "rag"]


def test_personal_question_prioritizes_memory():
    result = router.run(category="personal_question", skip_rag=False, retrieval_hint="my preference")
    assert result["retrieval_priority"] == ["memory", "decision_log", "rag"]


def test_coding_question_prioritizes_rag():
    result = router.run(category="coding_question", skip_rag=False, retrieval_hint="debug this")
    assert result["retrieval_priority"] == ["rag", "decision_log", "memory"]


def test_project_question_uses_default_priority():
    result = router.run(category="project_question", skip_rag=False, retrieval_hint="inventory sync")
    assert result["retrieval_priority"] == ["decision_log", "memory", "rag"]


def test_priority_list_never_skips_a_stage():
    # ADR-002: Router orders, never skips - every category's output must contain
    # all three retrieval stages, never a subset, even when skip_rag is True.
    for category in [
        "general_knowledge", "technical_explanation", "project_question",
        "personal_question", "coding_question", "research_request",
        "external_information", "project_continuation",
    ]:
        result = router.run(category=category, skip_rag=True, retrieval_hint="")
        assert set(result["retrieval_priority"]) == set(router.RETRIEVAL_STAGES)


def test_provider_preference_defaults_to_local():
    result = router.run(category="general_knowledge", skip_rag=True, retrieval_hint="")
    assert result["provider_preference"] == "local"


def test_unknown_category_falls_back_to_default_priority():
    result = router.run(category="totally_unrecognized_category", skip_rag=False, retrieval_hint="")
    assert result["retrieval_priority"] == ["decision_log", "memory", "rag"]
