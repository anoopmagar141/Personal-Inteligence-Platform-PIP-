import pytest

from backend.core import response_cache


@pytest.fixture(autouse=True)
def clear_cache():
    response_cache.clear()
    yield
    response_cache.clear()


def test_cache_key_normalizes_whitespace_and_case():
    a = response_cache.cache_key("  What IS a hash table?  ", "p1")
    b = response_cache.cache_key("what is a hash table?", "p1")
    assert a == b


def test_cache_key_differs_by_project_id():
    a = response_cache.cache_key("hello", "p1")
    b = response_cache.cache_key("hello", "p2")
    assert a != b


@pytest.mark.parametrize("category,expected_ttl", [
    ("general_knowledge", 86400),
    ("technical_explanation", 86400),
    ("external_information", 3600),
    ("project_question", 0),
    ("personal_question", 0),
])
def test_ttl_for_category_matches_settings(category, expected_ttl):
    assert response_cache.ttl_for_category(category) == expected_ttl


@pytest.mark.parametrize("category", ["coding_question", "research_request", "project_continuation"])
def test_categories_absent_from_spec_default_to_never_cache(category):
    assert response_cache.ttl_for_category(category) == 0


def test_get_returns_none_on_miss():
    assert response_cache.get("never asked this", "p1") is None


def test_set_then_get_returns_cached_response():
    response_cache.set("what is a hash table", "p1", "general_knowledge", "A hash table is...", {"cache_hit": False})
    result = response_cache.get("what is a hash table", "p1")
    assert result == {"response_text": "A hash table is...", "stage_hints": {"cache_hit": False}}


def test_set_is_noop_for_zero_ttl_category():
    response_cache.set("what's my project status", "p1", "project_question", "Your project is...", {})
    assert response_cache.get("what's my project status", "p1") is None


def test_set_is_noop_when_decision_log_hit():
    # Part 7.1: Decision Log always overrides - a decision-influenced answer
    # must never be cacheable, even for an otherwise long-TTL category.
    response_cache.set(
        "what is a hash table", "p1", "general_knowledge", "A hash table is...",
        {}, decision_log_hit=True,
    )
    assert response_cache.get("what is a hash table", "p1") is None


def test_entry_expires_after_ttl(monkeypatch):
    fake_time = [1000.0]
    monkeypatch.setattr(response_cache.time, "monotonic", lambda: fake_time[0])

    response_cache.set("what is a hash table", "p1", "external_information", "cached answer", {})
    assert response_cache.get("what is a hash table", "p1") is not None

    fake_time[0] += 3601  # past external_information's 3600s TTL
    assert response_cache.get("what is a hash table", "p1") is None


def test_get_fails_open_on_internal_error(monkeypatch):
    def broken_cache_key(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(response_cache, "cache_key", broken_cache_key)
    assert response_cache.get("anything", "p1") is None
