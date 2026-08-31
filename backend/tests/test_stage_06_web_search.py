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


# --- the total ceiling ------------------------------------------------------
# timeout_seconds is handed to the search client and covers ONE request; the
# client may try several backends and each gets its own budget, so the total was
# unbounded. Measured: a real search passed timeout_seconds=10 returned after
# 15.4s. This stage sits on the request path.


def test_a_hanging_search_is_abandoned_at_the_ceiling(monkeypatch):
    import time as _time

    monkeypatch.setattr(stage_06, "_total_timeout_seconds", lambda: 1)

    def never_returns(query, limit, timeout):
        _time.sleep(60)
        return [{"title": "too late"}]

    started = _time.perf_counter()
    assert stage_06.run("q", search_fn=never_returns) == []
    assert _time.perf_counter() - started < 10, "the ceiling did not bound the wait"


def test_the_abandoned_worker_cannot_block_process_exit():
    """
    A daemon thread, not a ThreadPoolExecutor worker. Its threads are
    non-daemon and the interpreter joins them at exit, so abandoning a hung
    search there still held the process open - measured at five minutes in a
    test that had correctly abandoned the search at 30s. ADR-033 already says
    shutdown cannot wait on slow work.
    """
    import threading as _threading

    before = {t.name for t in _threading.enumerate()}
    stage_06.run("q", search_fn=lambda *a: [{"title": "x", "url": "u", "snippet": "s"}])
    workers = [t for t in _threading.enumerate()
               if t.name == "stage06-web-search" and t.name not in before]
    assert all(t.daemon for t in workers), "a non-daemon worker would delay shutdown"


def test_a_slow_but_finishing_search_still_returns_its_results(monkeypatch):
    monkeypatch.setattr(stage_06, "_total_timeout_seconds", lambda: 5)

    def slow(query, limit, timeout):
        import time as _t
        _t.sleep(0.3)
        return [{"title": "worth waiting for", "url": "u", "snippet": "s"}]

    assert stage_06.run("patient query", search_fn=slow)[0]["title"] == "worth waiting for"
