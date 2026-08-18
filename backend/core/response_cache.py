# PIP Core - Response Cache (Part 7.1)
#
# Position: between Stage 2 Router and Stage 7 Context Assembly - a cache HIT is
# meant to short-circuit Stages 3-9 entirely (no RAG, no web search, no LLM call
# needed). Key: hash(normalized_message + project_id). Authority: lowest in the
# pipeline - Part 7.1's own "Authority" line says a Decision Log hit always
# overrides a cache hit, so a response influenced by a decision-log match is
# never cached and never served from cache, regardless of category.
#
# Resolves a real gap in the spec, same class as Stage 7's token-budget
# inconsistency: Part 7.1's TTL table only lists 6 names (general_knowledge,
# technical_explanation, web_search, project_question, personal_question,
# decision_lookup), but Stage 1 has 8 real categories (general_knowledge,
# technical_explanation, project_question, personal_question, coding_question,
# research_request, external_information, project_continuation) - neither
# "web_search" nor "decision_lookup" is an actual Stage 1 category name.
# Resolved as: "web_search" in the TTL table maps to Stage 1's
# "external_information" category (the one that actually triggers Stage 6 Web
# Search - there is no "web_search" category anywhere in this pipeline).
# "decision_lookup" isn't a category at all - it's the decision_log_hit override
# already described in the same section's "Authority" line, implemented below as
# a hard bypass rather than a category table entry. The three categories
# genuinely absent from the table (coding_question, research_request,
# project_continuation) default to never-cache (0) - the conservative choice:
# under-caching costs a little performance, over-caching a personalized or
# project-specific answer risks serving stale or simply wrong content, which is
# the worse failure mode given this project's own "Reliability Over Features"
# and "Fail Visibly, Never Silently" principles.

import hashlib
import logging
import time
from typing import Any, Optional

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)

_CATEGORY_TO_TTL_KEY = {
    "general_knowledge": "ttl_general_knowledge_seconds",
    "technical_explanation": "ttl_technical_explanation_seconds",
    "external_information": "ttl_web_search_seconds",
    "project_question": "ttl_project_question_seconds",
    "personal_question": "ttl_personal_question_seconds",
}
# coding_question, research_request, project_continuation: absent from Part
# 7.1's table - default to never-cache (0) via ttl_for_category()'s fallback.

# key -> (expires_at, response_text, stage_hints)
_cache: dict[str, tuple[float, str, dict[str, Any]]] = {}


def _normalize(message: str) -> str:
    return " ".join(message.strip().lower().split())


def cache_key(user_message: str, project_id: Optional[str]) -> str:
    raw = _normalize(user_message) + "|" + (project_id or "")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def ttl_for_category(category: str) -> int:
    settings = get_settings()["cache"]
    ttl_key = _CATEGORY_TO_TTL_KEY.get(category)
    if ttl_key is None:
        return 0
    return settings[ttl_key]


def get(user_message: str, project_id: Optional[str] = None) -> Optional[dict[str, Any]]:
    """
    Returns {"response_text": str, "stage_hints": dict} for a live cache entry,
    else None. Failure mode: any lookup error returns None (fail open - the
    cache is a strict performance optimization, never load-bearing for
    correctness, so a broken cache must never block a response).
    """
    try:
        key = cache_key(user_message, project_id)
        entry = _cache.get(key)
        if entry is None:
            return None
        expires_at, response_text, stage_hints = entry
        if time.monotonic() > expires_at:
            del _cache[key]
            return None
        return {"response_text": response_text, "stage_hints": stage_hints}
    except Exception as e:
        logger.error(f"Response cache lookup failed, treating as a miss: {e}")
        return None


def set(
    user_message: str,
    project_id: Optional[str],
    category: str,
    response_text: str,
    stage_hints: dict[str, Any],
    decision_log_hit: bool = False,
) -> None:
    """
    Writes a response at the category's TTL, unless the response involved a
    Decision Log hit (Part 7.1: "Decision Log always overrides" - a decision-
    log-influenced answer must never be servable from cache, so a later
    decision-state change - superseded, abandoned - can never be masked by a
    stale cached response). A TTL of 0 (project/personal questions, or any
    category absent from the spec's table) is a no-op, not a zero-duration entry.
    """
    if decision_log_hit:
        return
    ttl = ttl_for_category(category)
    if ttl <= 0:
        return
    key = cache_key(user_message, project_id)
    _cache[key] = (time.monotonic() + ttl, response_text, stage_hints)


def clear() -> None:
    """Test/ops convenience - not called anywhere in the pipeline itself."""
    _cache.clear()
