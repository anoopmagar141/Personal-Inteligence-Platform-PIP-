# PIP Message Pipeline - Stage 1: Intent Classifier
#
# ADR-019 / Intent Classifier design:
# Mechanism 1 (skip_rag flag): Keyword/token match vs active_projects names + decision-log
#   keyword cache to produce skip_rag bool. Saves ~35ms.
# Mechanism 2 (ADR-002 safety net): Lightweight title-only embedding pre-check running
#   regardless of skip_rag result. These are NOT the same check - Mechanism 2 is Stage 5's
#   responsibility to always run, not something this stage implements or can skip.
#
# B4: Intent Classifier is keyword/regex, not a generative LLM call (30ms target). This is
# a first-pass heuristic, same spirit as similarity_threshold and the Stage 5 conflict-check
# heuristic elsewhere in this pipeline - expected to be calibrated against real usage, not a
# solved NLP problem out of the gate.

import logging
import re
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)

CATEGORIES = (
    "general_knowledge",
    "technical_explanation",
    "project_question",
    "personal_question",
    "coding_question",
    "research_request",
    "external_information",
    "project_continuation",
)

# Shared with Stage 6's web-search trigger list (Part 7 Stage 6 spec).
EXTERNAL_INFO_KEYWORDS = (
    "latest", "today", "current", "news", "price", "who won", "recent", "weather", "right now",
)

_CONTINUATION_PATTERNS = (
    r"\bcontinue\b", r"\bwhere were we\b", r"\blast time\b", r"\bpick up\b", r"\bkeep going\b",
)

_CODING_PATTERNS = (
    r"\bwrite (a |the )?(function|class|code|script)\b",
    r"\bdebug\b",
    r"\bfix (this|the|my) (bug|error|code)\b",
    r"\brefactor\b",
    r"\btraceback\b",
    r"\bstack trace\b",
    r"\bsyntax error\b",
    r"\bimplement\b",
)

_RESEARCH_PATTERNS = (
    r"\bresearch\b", r"\bfind out\b", r"\blook into\b", r"\bcompare\b.*\bvs\b", r"\bpros and cons\b",
)

_PERSONAL_PATTERNS = (
    r"\bmy\b", r"\bi am\b", r"\bi'm\b", r"\bdo i\b", r"\bwhat did i\b",
    r"\bremind me\b", r"\bmy preference\b", r"\bwhat do i prefer\b",
)

_TECHNICAL_EXPLANATION_PATTERNS = (
    # Deliberately no bare "what is" pattern - it's too generic and overlaps heavily
    # with plain general-knowledge questions ("what is the capital of France" is not
    # a technical explanation). "how does X work" / "why does X" are more reliably
    # technical framings than a bare "what is".
    r"^explain\b", r"\bhow does\b.*\bwork\b", r"\bwhy does\b", r"\bdifference between\b",
)


class IntentResult(TypedDict):
    category: str
    skip_rag: bool
    retrieval_hint: str


def _matches_active_project(lowered_message: str, conn) -> bool:
    if conn is None:
        return False
    try:
        rows = conn.execute("SELECT name FROM active_projects WHERE status = 'active'").fetchall()
    except Exception as e:
        logger.warning(f"Intent Classifier: active_projects lookup failed, treating as no match: {e}")
        return False
    return any(row["name"] and row["name"].lower() in lowered_message for row in rows)


def _matches_decision_keywords(lowered_message: str, conn) -> bool:
    """
    Mechanism 1's decision-log half: cheap keyword overlap against recent active
    decisions, not a real search (that's Stage 3's FTS5 job). Requires at least one
    shared word longer than 3 characters so trivial stopword overlap ("the", "and")
    doesn't count as a match.
    """
    if conn is None:
        return False
    try:
        rows = conn.execute(
            "SELECT decision_text FROM decision_log WHERE state = 'active' ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
    except Exception as e:
        logger.warning(f"Intent Classifier: decision_log keyword lookup failed, treating as no match: {e}")
        return False

    message_words = set(re.findall(r"[a-z0-9]+", lowered_message))
    for row in rows:
        decision_words = set(re.findall(r"[a-z0-9]+", (row["decision_text"] or "").lower()))
        shared = message_words & decision_words
        if any(len(w) > 3 for w in shared):
            return True
    return False


def _matches_any(patterns, text: str) -> bool:
    return any(re.search(p, text) for p in patterns)


def _extract_retrieval_hint(message: str, max_words: int = 12) -> str:
    """
    Short phrase pre-seeding Stage 3/4/5 lookups. A bounded word-count trim, not a
    summarization pass - Stage 1 is keyword/regex only (B4), no LLM call here.
    """
    words = message.strip().split()
    return " ".join(words[:max_words])


def run(message: str, warm_start_level: str = "none", conn=None) -> IntentResult:
    """
    Deterministic category + skip_rag + retrieval_hint classification.
    Failure mode: fails open to category=general_knowledge, skip_rag=False per the
    Part 7 Stage 1 spec - never blocks the pipeline.
    """
    try:
        lowered = message.lower()

        has_project_terms = _matches_active_project(lowered, conn) or _matches_decision_keywords(lowered, conn)

        if _matches_any(_CONTINUATION_PATTERNS, lowered):
            category = "project_continuation"
        elif any(kw in lowered for kw in EXTERNAL_INFO_KEYWORDS):
            category = "external_information"
        elif _matches_any(_CODING_PATTERNS, lowered):
            category = "coding_question"
        elif _matches_any(_RESEARCH_PATTERNS, lowered):
            category = "research_request"
        elif has_project_terms:
            category = "project_question"
        elif _matches_any(_PERSONAL_PATTERNS, lowered):
            category = "personal_question"
        elif _matches_any(_TECHNICAL_EXPLANATION_PATTERNS, lowered):
            category = "technical_explanation"
        else:
            category = "general_knowledge"

        # Spec: skip_rag = general_knowledge OR (technical_explanation AND confidence
        # >= 0.9 AND no project-specific terms). An explicit regex match IS the
        # high-confidence signal here (deterministic match, not a fuzzy fallback), so
        # "confidence >= 0.9" is satisfied by construction whenever a pattern matched.
        # The has_project_terms check is redundant given the if/elif ordering above
        # (project_question would already have claimed the category otherwise), but
        # kept explicit to match the spec literally and stay correct if that ordering
        # ever changes.
        skip_rag = category == "general_knowledge" or (
            category == "technical_explanation" and not has_project_terms
        )

        return {
            "category": category,
            "skip_rag": skip_rag,
            "retrieval_hint": _extract_retrieval_hint(message),
        }
    except Exception as e:
        logger.error(f"Intent Classifier failed, failing open: {e}")
        return {"category": "general_knowledge", "skip_rag": False, "retrieval_hint": ""}
