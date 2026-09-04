# PIP Message Pipeline - Stage 2: Router
#
# ADR-002: Router is a priority-orderer, not a stage-skipper. Stages 3 (Decision Log),
# 4 (Memory), and 5 (RAG) always run in parallel (asyncio.gather) regardless of what
# this stage outputs - Router only orders/weights their results for Stage 7 Context
# Assembly, it never decides whether they run at all. General knowledge still gets
# the ADR-002 embedding pre-check even when skip_rag=True.
#
# The retrieval priority list's default ordering is anchored to ADR-023's already-
# locked Cache Authority Hierarchy (User correction > Decision Log > Profile > RAG >
# Web > Cache) rather than invented from scratch - decision_log > memory > rag by
# default. Category shifts the emphasis for personal/coding-flavored questions, but
# the underlying authority relationship between the three sources doesn't change.

import logging
from typing import TypedDict

logger = logging.getLogger(__name__)

RETRIEVAL_STAGES = ("decision_log", "memory", "rag")

# ADR-023 authority order, used whenever a category has no more specific override.
_DEFAULT_PRIORITY = ["decision_log", "memory", "rag"]

_CATEGORY_PRIORITY_OVERRIDES = {
    "personal_question": ["memory", "decision_log", "rag"],
    "coding_question": ["rag", "decision_log", "memory"],
}

# v1.0 is local-only (confirmed decision) - there is no cloud provider in the call
# path for Router to route toward. Kept as an explicit field (not hardcoded at the
# Stage 8 call site) so a future cloud-consented provider has somewhere to plug in
# without changing Router's output contract.
_DEFAULT_PROVIDER_PREFERENCE = "local"


class RouterResult(TypedDict):
    retrieval_priority: list[str]
    provider_preference: str


def run(
    category: str,
    skip_rag: bool,
    retrieval_hint: str,
    warm_start_level: str = "none",
) -> RouterResult:
    """
    Orders Stage 3/4/5 results by priority for Stage 7 Context Assembly. Does NOT
    decide whether those stages run (ADR-002) - skip_rag and warm_start_level are
    accepted for future weighting refinement but don't currently change the ordering
    itself, only which category maps to which priority list.

    Failure mode: falls back to an empty retrieval priority (LLM-only path) and the
    default local provider preference, logs the error, never blocks the pipeline.
    """
    try:
        priority = _CATEGORY_PRIORITY_OVERRIDES.get(category, list(_DEFAULT_PRIORITY))
        return {
            "retrieval_priority": priority,
            "provider_preference": _DEFAULT_PROVIDER_PREFERENCE,
        }
    except Exception as e:
        logger.error(f"Router failed, defaulting to LLM-only path: {e}")
        return {"retrieval_priority": [], "provider_preference": _DEFAULT_PROVIDER_PREFERENCE}
