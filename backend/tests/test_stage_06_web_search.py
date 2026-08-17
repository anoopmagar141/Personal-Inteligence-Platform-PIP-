import pytest

from backend.stages import stage_06_web_search as stage_06


@pytest.fixture(autouse=True)
def clear_cache():
    stage_06._cache.clear()
    yield
    stage_06._cache.clear()


def test_matches_trigger_keywords():
    assert stage_06.matches_trigger("What's the latest news on this?") is True
    assert stage_06.matches_trigger("What's the weather like today?") is True
    assert stage_06.matches_trigger("Explain how a hash table works") is False


def test_run_returns_search_fn_results():
    def fake_search(query, result_limit, timeout_seconds):
        return [{"title": "Result", "url": "http://example.com", "snippet": "..."}]

    results = stage_06.run("latest AI news", search_fn=fake_search)
    assert results == [{"title": "Result", "url": "http://example.com", "snippet": "..."}]


def test_run_fails_open_on_search_error():
    def broken_search(query, result_limit, timeout_seconds):
        raise RuntimeError("simulated network failure")

    assert stage_06.run("anything", search_fn=broken_search) == []


def test_run_caches_results_within_ttl():
    calls = []

    def counting_search(query, result_limit, timeout_seconds):
        calls.append(query)
        return [{"title": "Result", "url": "u", "snippet": "s"}]

    first = stage_06.run("latest news", search_fn=counting_search)
    second = stage_06.run("latest news", search_fn=counting_search)
    assert first == second
    assert len(calls) == 1  # second call served from cache, not re-searched


def test_run_cache_expires_after_ttl(monkeypatch):
    calls = []

    def counting_search(query, result_limit, timeout_seconds):
        calls.append(query)
        return [{"title": f"Result {len(calls)}", "url": "u", "snippet": "s"}]

    fake_time = [1000.0]
    monkeypatch.setattr(stage_06.time, "monotonic", lambda: fake_time[0])

    stage_06.run("latest news", search_fn=counting_search)
    fake_time[0] += stage_06.CACHE_TTL_SECONDS + 1
    stage_06.run("latest news", search_fn=counting_search)

    assert len(calls) == 2  # cache expired, re-searched


def test_run_does_not_cache_a_failed_search():
    call_count = {"n": 0}

    def flaky_search(query, result_limit, timeout_seconds):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated failure")
        return [{"title": "Recovered", "url": "u", "snippet": "s"}]

    first = stage_06.run("latest news", search_fn=flaky_search)
    second = stage_06.run("latest news", search_fn=flaky_search)
    assert first == []
    assert second == [{"title": "Recovered", "url": "u", "snippet": "s"}]
    assert call_count["n"] == 2  # failure was not cached, second call actually retried


def test_different_queries_cache_independently():
    def fake_search(query, result_limit, timeout_seconds):
        return [{"title": query, "url": "u", "snippet": "s"}]

    results_a = stage_06.run("latest news", search_fn=fake_search)
    results_b = stage_06.run("current weather", search_fn=fake_search)
    assert results_a[0]["title"] == "latest news"
    assert results_b[0]["title"] == "current weather"
