# PIP Stage 11 - Observer
#
# Non-negotiable rules (Part 12.1):
#   Rule 1: Labels candidates explicit or inferred. NEVER assigns confidence scores.
#   Rule 2: Produces candidates only. NEVER writes to any store directly.
#   Rule 3: Runs at session end only (10-min idle OR process exit). NEVER per-message.
#           NOT enforced by this module - there is no process-lifecycle context here.
#           The caller (Phase 8) is responsible for only invoking run_session_end()
#           when a session has actually ended.
#   Rule 4: Uses llama3.1:8b, same model as generation (ADR-033). MUST be pinned to a
#           LOCAL provider - enforced below, not assumed.
#   Rule 5: Does NOT detect document-decision conflicts. That is Stage 5's job.
#
# Known scope boundary: every memory_candidate below carries evidence_count=1 - a
# single-pass extraction over one transcript can only attest "observed once, this
# session." Part 8.6's REINFORCEMENT step (incrementing evidence_count when a signal
# recurs across sessions) is NOT implemented here or anywhere yet. Until it exists,
# inferred candidates will rarely clear Stage 12's tiered thresholds past Week 1-2,
# and explicit candidates will stop clearing them past Week 3-4 (both require
# evidence_count >= 2). This is a known, flagged gap - see Part 20 Phase 7 status.

import json
import logging
import re
from pathlib import Path
from typing import Any, Optional, TypedDict

from backend.core.constitution_enforcer import ConstitutionEnforcer
from backend.core.types import now_utc
from backend.memory import decision_log, session_snapshot
from backend.providers.base_provider import (
    BaseLLMProvider,
    ProviderExecutionError,
    ProviderUnavailableError,
)
from backend.stages import stage_12_validation_layer as stage_12
from backend.stages import stage_13_profile_update as stage_13

logger = logging.getLogger(__name__)

CONSTITUTION_PATH = str(Path(__file__).parent.parent / "core" / "constitutional.json")

_VALID_LABELS = {"explicit", "inferred"}

# Must exactly match Part 9.1 observer_may_write.fields (constitutional.json)
APPROVED_MEMORY_FIELDS = {
    "skill_memory": ["python_level", "docker_level", "sql_level"],
    "preference_memory": ["preferred_tools", "answer_style"],
    "goal_memory": ["active_goals", "project_objectives"],
    "observer_writable": ["topic_interests", "preferred_tools", "document_access_patterns"],
}

_EXTRACTION_PROMPT_PREFIX = """SYSTEM:
You are an information extraction assistant. Your only job is to analyze
a conversation and extract structured signals from it.
Produce valid JSON only. No commentary. No explanation.

RULES:
  - Label each candidate "explicit" if user directly stated it.
  - Label "inferred" if you observed it from behavior.
  - Do NOT assign confidence scores. Label type only.
  - Do NOT create fields outside the approved list.
  - Do NOT include emotional state, mood, or psychological signals.
  - If uncertain, omit. Never guess.

APPROVED MEMORY FIELDS (target_table: [field_name, ...]):
  skill_memory: [python_level, docker_level, ...]
  preference_memory: [preferred_tools, answer_style, ...]
  goal_memory: [active_goals, project_objectives]
  observer_writable: [topic_interests, preferred_tools, document_access_patterns]

OUTPUT FORMAT:
{
  "memory_candidates": [
    {
      "target_table": "preference_memory",
      "field_name": "preferred_tools",
      "proposed_value": "Neovim",
      "label": "explicit",
      "evidence_count": 1,
      "evidence_text": "the exact quote or paraphrase this was drawn from"
    }
  ],
  "decision_candidates": [
    {
      "decision_text": "one sentence stating the decision",
      "signals_found": ["explicit_reasoning_in_conversation", "commitment_language", "alternative_considered"],
      "raw_quote": "the exact quote this was drawn from"
    }
  ],
  "session_snapshot": {
    "topic": "one sentence",
    "open_problems": [],
    "last_decisions": [],
    "suggested_next_step": "one concrete next action"
  }
}

CONVERSATION TO ANALYZE:
"""


class ObserverLocalProviderError(Exception):
    """Raised when Observer is given a non-local provider (ADR-033 Rule 4)."""


class ObserverOutput(TypedDict):
    memory_candidates: list[dict[str, Any]]
    decision_candidates: list[dict[str, Any]]
    session_snapshot: dict[str, Any]


def _empty_snapshot() -> dict[str, Any]:
    return {
        "topic": "",
        "open_problems": [],
        "last_decisions": [],
        "suggested_next_step": "",
        "snapshot_date": now_utc(),
    }


def _empty_output() -> ObserverOutput:
    return {"memory_candidates": [], "decision_candidates": [], "session_snapshot": _empty_snapshot()}


def _extract_json(raw_text: str) -> Optional[dict]:
    """Models sometimes wrap JSON in markdown fences despite being told not to."""
    text = raw_text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _sanitize_memory_candidate(raw: Any) -> Optional[dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    if not all(k in raw for k in ("target_table", "field_name", "proposed_value")):
        return None
    label = raw.get("label")
    if label not in _VALID_LABELS:
        # Rule 1: anything other than explicit|inferred (including a hallucinated
        # confidence-bearing label) is dropped, never passed downstream.
        return None
    return {
        "target_table": raw["target_table"],
        "field_name": raw["field_name"],
        "proposed_value": raw["proposed_value"],
        "label": label,
        "evidence_count": 1,
        "evidence_text": str(raw.get("evidence_text", "")),
    }


def _sanitize_decision_candidate(raw: Any) -> Optional[dict[str, Any]]:
    if not isinstance(raw, dict) or "decision_text" not in raw:
        return None
    signals = raw.get("signals_found")
    return {
        "decision_text": raw["decision_text"],
        "signals_found": signals if isinstance(signals, list) else [],
        "raw_quote": str(raw.get("raw_quote", "")),
    }


def _as_string_list(value: Any) -> list[str]:
    """
    Coerces a list to a list of strings. Found live: llama3.1:8b sometimes nests
    a full decision_candidate object into session_snapshot.last_decisions instead
    of a plain string, even though the prompt's example shows an empty list with
    no element type spelled out. Dropping non-string items would silently lose the
    snapshot's most important content, so a dict with decision_text is unwrapped to
    that string; anything else falls back to str().
    """
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict) and "decision_text" in item:
            result.append(str(item["decision_text"]))
        else:
            result.append(str(item))
    return result


def _sanitize_snapshot(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return _empty_snapshot()
    return {
        "topic": str(raw.get("topic", "")),
        "open_problems": _as_string_list(raw.get("open_problems")),
        "last_decisions": _as_string_list(raw.get("last_decisions")),
        "suggested_next_step": str(raw.get("suggested_next_step", "")),
        "snapshot_date": now_utc(),
    }


def run(transcript: str, provider: BaseLLMProvider, conn) -> ObserverOutput:
    """
    Single-pass extraction over a full session transcript.
    Failure mode: fails open (Part 7 Stage 11 spec: "profile unchanged, snapshot not
    updated"). Any LLM/network failure or unparseable output returns an empty result
    rather than raising - the only exception is ObserverLocalProviderError, which is
    a caller programming error (Rule 4 violation), not a runtime failure.

    conn is required for the Rule 4 check below - this used to trust
    provider.get_model_info()["is_local"] alone, which is whatever the
    provider CLASS itself self-reports (found in a security review: every
    other trust decision in this codebase, Stage 8's gate included, anchors
    is_cloud in the operator-controlled provider_consent DB table, never in
    the provider object). A future or buggy BaseLLMProvider subclass
    misreporting is_local=True while actually calling out to a cloud endpoint
    would have sent the ENTIRE session transcript there, with this being the
    only thing standing in the way. Now requires BOTH signals to agree the
    provider is local - the self-report AND the verified DB record - and
    fails closed (treats it as non-local) if the provider_id has no
    provider_consent row at all, same fail-closed posture Stage 8 already
    uses for unknown providers.
    """
    model_info = provider.get_model_info()
    provider_id = model_info.get("provider_id")
    row = conn.execute(
        "SELECT is_cloud FROM provider_consent WHERE provider_id = ?", (provider_id,)
    ).fetchone()
    verified_local = row is not None and not bool(row["is_cloud"])
    if not model_info.get("is_local") or not verified_local:
        raise ObserverLocalProviderError(
            f"Observer requires a local provider; got provider_id={provider_id!r} "
            f"is_local={model_info.get('is_local')!r}, "
            f"provider_consent.is_cloud={(None if row is None else bool(row['is_cloud']))!r}"
        )

    try:
        messages = [{"role": "user", "content": _EXTRACTION_PROMPT_PREFIX + transcript}]
        raw_text = "".join(provider.chat(messages, max_tokens=2000, timeout_seconds=180))
    except (ProviderUnavailableError, ProviderExecutionError) as e:
        logger.error(f"Observer LLM call failed, failing open: {e}")
        return _empty_output()

    parsed = _extract_json(raw_text)
    if parsed is None:
        logger.error("Observer output was not valid JSON, failing open")
        return _empty_output()

    raw_memory = parsed.get("memory_candidates")
    memory_candidates = []
    if isinstance(raw_memory, list):
        memory_candidates = [c for c in (_sanitize_memory_candidate(m) for m in raw_memory) if c is not None]

    raw_decisions = parsed.get("decision_candidates")
    decision_candidates = []
    if isinstance(raw_decisions, list):
        decision_candidates = [c for c in (_sanitize_decision_candidate(d) for d in raw_decisions) if c is not None]

    return {
        "memory_candidates": memory_candidates,
        "decision_candidates": decision_candidates,
        "session_snapshot": _sanitize_snapshot(parsed.get("session_snapshot")),
    }


def run_session_end(
    conn,
    transcript: str,
    provider: BaseLLMProvider,
    project_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Full Observer session-end flow: extract -> write snapshot immediately -> reinforce
    evidence_count for repeat observations (Part 8.6) -> route memory_candidates
    through Stage 12 (validate) + Stage 13 (write) -> route decision_candidates
    through decision_log.route_observer_decision (Part 8.7 OR-logic,
    log_threshold_observer).

    Does NOT handle idle-timeout/SIGINT triggering or pending_observer draining -
    those are process-lifecycle concerns that need a running server (Phase 8). This
    is what a caller invokes once it has already decided the session has ended.
    """
    output = run(transcript, provider, conn)

    session_snapshot.write_snapshot(conn, output["session_snapshot"])

    enforcer = ConstitutionEnforcer(CONSTITUTION_PATH)
    memory_results = []
    for candidate in output["memory_candidates"]:
        # Reinforcement must happen before validation and be visible to the write:
        # a single-pass extraction can only ever produce evidence_count=1 on its
        # own, so without this, repeat observations across sessions would never
        # accumulate and would keep failing Stage 12's tiered thresholds forever.
        candidate = stage_12.reinforce_evidence(conn, candidate)
        validation_result = stage_12.run(conn, candidate, enforcer)
        outcome = stage_13.run(conn, candidate, validation_result)
        memory_results.append({
            "candidate": candidate,
            "validation_status": validation_result.status,
            "outcome": outcome,
        })

    decision_results = []
    for dc in output["decision_candidates"]:
        result = decision_log.route_observer_decision(
            conn,
            text=dc["decision_text"],
            signals_found=dc["signals_found"],
            raw_quote=dc["raw_quote"],
            project_id=project_id,
        )
        decision_results.append(result)

    return {
        "snapshot": output["session_snapshot"],
        "memory_results": memory_results,
        "decision_results": decision_results,
    }
