# PIP Message Pipeline - Stage 6: Web Search
#
# "Fires in background thread at Stage 1 detection" (Part 7 Stage 6 spec) - trigger
# keywords are shared with Stage 1's external_information category
# (stage_01_intent_classifier.EXTERNAL_INFO_KEYWORDS), not duplicated here.
#
# Provider is duckduckgo (locked in settings.json), via the ddgs package (the
# actively-maintained successor to duckduckgo-search, which is now years behind).
# search_fn is injectable so this stage's own logic - the 3600s TTL cache, trigger
# detection, fail-open behavior - is fully testable without a real network call.
#
# Scope note: the 3600s cache here is a stage-local safety net against redundant
# real HTTP calls for repeated/similar queries within an hour. It is separate from
# Part 7.1's broader Response Cache (core/response_cache.py), which caches whole
# responses by category between Stage 2 and Stage 7 - a hit there skips this stage
# along with everything else from Stage 3 to Stage 9. The two do not overlap: that
# cache is keyed on the user's message, this one on the search query Stage 1
# derived from it, so a different question that produces the same query still
# reuses these results.

import logging
import threading
import time
from typing import Any, Callable, Optional

from backend.config.settings import get_settings
from backend.stages.stage_01_intent_classifier import EXTERNAL_INFO_KEYWORDS

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 3600


def _total_timeout_seconds() -> int:
    """
    A ceiling on the whole search, distinct from the per-request timeout.

    They are genuinely different numbers. timeout_seconds is handed to the
    search client and applies to one request; the client may try several
    backends, and each attempt gets its own budget - so the total is unbounded
    no matter what that value says. Measured here: a search passed
    timeout_seconds=10 returned after 15.4 seconds, and this stage sits on the
    request path, so an external service having a bad day could hold up a
    response for as long as it liked.

    An explicit setting rather than a multiple of the per-request one, because
    any multiplier would be a number invented to look principled.
    """
    return int(get_settings()["web_search"].get("total_timeout_seconds", 30))

_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}


def matches_trigger(message: str) -> bool:
    lowered = message.lower()
    return any(kw in lowered for kw in EXTERNAL_INFO_KEYWORDS)


def _cache_get(query: str) -> Optional[list[dict[str, Any]]]:
    entry = _cache.get(query)
    if entry is None:
        return None
    cached_at, results = entry
    if time.monotonic() - cached_at > CACHE_TTL_SECONDS:
        del _cache[query]
        return None
    return results


def _cache_set(query: str, results: list[dict[str, Any]]) -> None:
    _cache[query] = (time.monotonic(), results)


def _duckduckgo_search(query: str, result_limit: int, timeout_seconds: int) -> list[dict[str, Any]]:
    from ddgs import DDGS

    with DDGS(timeout=timeout_seconds) as client:
        raw = list(client.text(query, max_results=result_limit))
    return [
        {"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")}
        for r in raw
    ]


def run(
    query: str,
    result_limit: int = 3,
    timeout_seconds: int = 10,
    search_fn: Optional[Callable[[str, int, int], list[dict[str, Any]]]] = None,
) -> list[dict[str, Any]]:
    """
    Runs a web search for query, TTL-cached at the stage level (3600s per spec).
    search_fn defaults to the real DuckDuckGo-backed search; tests inject a fake.
    Failure mode: return empty (Part 7 Stage 6: "return empty, note in response" -
    the "note in response" half is Stage 7/9's job when assembling the final
    answer, not this stage's).
    """
    cached = _cache_get(query)
    if cached is not None:
        return cached

    fn = search_fn or _duckduckgo_search

    # Run it on a DAEMON thread so a slow search can be abandoned rather than
    # waited out. The search client is a compiled extension doing its own DNS
    # and connect, so there is no Python-level timeout to reach into it with -
    # the only lever from here is to stop waiting.
    #
    # A daemon thread specifically, not ThreadPoolExecutor. Its workers are
    # non-daemon and the interpreter joins them at exit, so abandoning a hung
    # search there still blocks the process from shutting down - measured, a
    # test abandoned a search at 30s exactly as intended and then sat for five
    # minutes waiting for the worker before it could exit. ADR-033 already says
    # shutdown cannot wait on slow work; this is the same rule.
    #
    # The thread finishes on its own once the search returns. Abandoning means
    # abandoning: waiting for it to notice would reintroduce the delay this
    # exists to bound, the same posture the WebSocket disconnect path takes with
    # a stuck conn.close().
    outcome: dict[str, Any] = {}

    def _worker() -> None:
        try:
            outcome["results"] = fn(query, result_limit, timeout_seconds)
        except Exception as exc:  # noqa: BLE001 - reported on the main thread
            outcome["error"] = exc

    ceiling = _total_timeout_seconds()
    worker = threading.Thread(target=_worker, name="stage06-web-search", daemon=True)
    worker.start()
    worker.join(timeout=ceiling)

    if worker.is_alive():
        logger.error(
            f"Stage 6 web search exceeded {ceiling}s, returning empty. The stage "
            f"fails open by design, so the answer proceeds without it."
        )
        return []
    if "error" in outcome:
        logger.error(f"Stage 6 web search failed, returning empty: {outcome['error']}")
        return []
    results = outcome.get("results", [])

    _cache_set(query, results)
    return results
