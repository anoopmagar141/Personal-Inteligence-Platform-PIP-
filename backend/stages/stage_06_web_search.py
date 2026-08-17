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
# Part 7.1's broader Response Cache (core/response_cache.py, not built yet), which
# caches by category across the whole pipeline, not just web search results.

import logging
import time
from typing import Any, Callable, Optional

from backend.stages.stage_01_intent_classifier import EXTERNAL_INFO_KEYWORDS

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 3600

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
    try:
        results = fn(query, result_limit, timeout_seconds)
    except Exception as e:
        logger.error(f"Stage 6 web search failed, returning empty: {e}")
        return []

    _cache_set(query, results)
    return results
