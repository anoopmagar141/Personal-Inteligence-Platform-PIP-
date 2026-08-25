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

import inspect
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
  - A decision_candidate must be something the USER decided or committed to.
    Never extract the assistant's own offers, questions, or suggestions
    ("Would you like me to...", "I can help you...") as a decision - those
    are not decisions, they weren't made by the user.
  - evidence_text and raw_quote must be copied WORD FOR WORD from the
    conversation below. Not a paraphrase, not a summary, not a description.
    If you cannot find the user's own words to copy, omit the candidate.
  - The angle-bracketed text in the example below describes what to put
    there. Never copy those descriptions into your answer.

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
      "evidence_text": "<the user's own words, copied exactly from the conversation>"
    }
  ],
  "decision_candidates": [
    {
      "decision_text": "one sentence stating the decision",
      "signals_found": ["explicit_reasoning_in_conversation", "commitment_language", "alternative_considered"],
      "raw_quote": "<the user's own words, copied exactly from the conversation>"
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


# JSON Schema mirroring the OUTPUT FORMAT block above, handed to the provider
# as response_format so the shape is enforced during sampling instead of hoped
# for. Previously the only defence was the prompt saying "Produce valid JSON
# only", with _extract_json() stripping markdown fences after the fact and
# run_session_end() discarding the ENTIRE session's output on a parse failure -
# so one stray sentence of commentary cost every candidate and the snapshot,
# silently, with the transcript already gone.
#
# What this does and does not buy: it guarantees well-formed JSON of the right
# shape. It guarantees nothing about truthfulness - a schema cannot tell an
# observed decision from an invented one. The grounding checks
# (_looks_like_assistant_echo, _quote_is_grounded, _has_any_substantive_user_turn)
# remain the defence against that, and are unaffected by this.
#
# Kept adjacent to _EXTRACTION_PROMPT_PREFIX deliberately: the prompt's example
# and this schema describe the same contract, and editing one without the other
# is how they drift. snapshot_date is absent by design - the code stamps it via
# now_utc(), and asking a model for the current time invites a wrong answer.
_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "memory_candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "target_table": {"type": "string"},
                    "field_name": {"type": "string"},
                    "proposed_value": {"type": "string"},
                    # Constrained to the two labels the validation layer accepts
                    # (_VALID_LABELS). ADR-005 forbids the model scoring its own
                    # confidence; this is the label-only choice it may make.
                    "label": {"type": "string", "enum": ["explicit", "inferred"]},
                    "evidence_count": {"type": "integer"},
                    "evidence_text": {"type": "string"},
                },
                "required": [
                    "target_table", "field_name", "proposed_value",
                    "label", "evidence_count", "evidence_text",
                ],
            },
        },
        "decision_candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "decision_text": {"type": "string"},
                    "signals_found": {"type": "array", "items": {"type": "string"}},
                    # Required, not optional: _quote_is_grounded() checks this
                    # against the real transcript, and a candidate arriving
                    # without one cannot be verified at all.
                    "raw_quote": {"type": "string"},
                },
                "required": ["decision_text", "signals_found", "raw_quote"],
            },
        },
        "session_snapshot": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "open_problems": {"type": "array", "items": {"type": "string"}},
                "last_decisions": {"type": "array", "items": {"type": "string"}},
                "suggested_next_step": {"type": "string"},
            },
            "required": ["topic", "open_problems", "last_decisions", "suggested_next_step"],
        },
    },
    # All three keys required so "nothing to report" arrives as empty arrays -
    # an explicit, parseable answer - rather than as absent keys indistinguishable
    # from a truncated response.
    "required": ["memory_candidates", "decision_candidates", "session_snapshot"],
}


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


def _accepts_response_format(provider: Any) -> bool:
    """
    Whether this provider's chat() takes the response_format keyword. A
    provider accepting **kwargs counts, since the call will bind either way.
    Any introspection failure is treated as "no" - falling back to an
    unconstrained call always works, while guessing "yes" wrongly raises
    TypeError and loses the session's extraction entirely.
    """
    try:
        parameters = inspect.signature(provider.chat).parameters
    except (TypeError, ValueError):
        return False
    if "response_format" in parameters:
        return True
    return any(p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values())


def _extract_json(raw_text: str) -> Optional[dict]:
    """
    Retained as a second line of defence even though response_format now makes
    malformed output impossible on providers that honour it: providers that
    ignore it fall through to exactly this path, which is how the Observer ran
    until now. Cheap, and the alternative on a fenced response is losing the
    whole session's extraction.

    Models sometimes wrap JSON in markdown fences despite being told not to.
    """
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


def _extract_assistant_lines(transcript: str) -> list[str]:
    return [
        line.split(":", 1)[1].strip().lower()
        for line in transcript.splitlines()
        if line.strip().lower().startswith("assistant:")
    ]


def _looks_like_assistant_echo(decision_text: str, assistant_lines: list[str]) -> bool:
    """
    Found live: Observer's extraction sometimes echoes the assistant's own
    prior reply back as a decision_candidate ("Would you like me to
    prioritize the tasks...?" logged as if the user decided it) - the
    RULES prompt instruction against this is not enough on its own (same
    "don't trust the model's own compliance" lesson as ADR-005's confidence
    scoring: instructions get ignored by a small model with nothing better
    to extract). Two independent, deterministic signals, since a genuine
    decision phrased as a question is conceivable but rare, while a
    decision_text that's a near-verbatim assistant line essentially never is:
      1. It's phrased as a question - decisions are statements of what was
         decided, not requests or offers.
      2. It appears verbatim (normalized) inside one of the transcript's own
         "Assistant:" lines (format_transcript()'s role-labeled format,
         session_lifecycle.py).
    """
    normalized = " ".join(decision_text.strip().lower().split())
    if not normalized:
        return True
    if normalized.endswith("?"):
        return True
    return any(normalized in line for line in assistant_lines)


def _quote_is_grounded(raw_quote: str, transcript_lower: str) -> bool:
    """
    Found live, a step past _looks_like_assistant_echo: a low-signal session
    (a few one-word "yes"/"sure"/"hi" replies, nothing substantive) got 7
    decision_candidates auto-logged - none phrased as questions, none a
    verbatim echo of an assistant line, all entirely confabulated (a whole
    fictional "product launch meeting with Figma" scenario with no basis in
    the actual conversation). Rule 1 asks the model for a raw_quote "the
    exact quote this was drawn from" precisely so a candidate can be checked
    against reality instead of trusted at face value (same "don't trust the
    model's own claim" posture as everywhere else this session) - if the
    quote it claims to have drawn from isn't actually anywhere in the
    transcript, the candidate has no real basis and is dropped, regardless
    of how plausible decision_text itself reads.
    """
    normalized = " ".join(raw_quote.strip().lower().split())
    if not normalized:
        return False
    return normalized in transcript_lower


def _has_any_substantive_user_turn(transcript: str, min_words: int = 4) -> bool:
    """
    Companion gate for session_snapshot, which has no per-item raw_quote to
    ground against (it's a holistic topic/decisions/next-step summary, not a
    list of discrete claims). A session made entirely of one-word
    acknowledgments ("hi", "yes", "sure") has nothing real to summarize -
    the same confabulation Rule 1's raw_quote check catches for decisions
    happens here too (an invented "product launch" topic/next-step from a
    transcript that never mentioned one). min_words=4 is deliberately low:
    the goal is ruling out a session that was ONLY trivial acknowledgments,
    not requiring lengthy user turns - "let's go with FastAPI" (4 words) is
    exactly the kind of short-but-real turn that should still pass.
    """
    for line in transcript.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("user:"):
            content = stripped.split(":", 1)[1].strip()
            if len(content.split()) >= min_words:
                return True
    return False


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

    # Asked before calling rather than by catching TypeError from the call: a
    # TypeError raised inside the generator body during iteration would look
    # identical to a rejected keyword, and retrying on that would hide a real
    # bug behind a plausible-looking fallback. base_provider documents
    # response_format as optional for implementers, so a provider that never
    # adopted it still works - unconstrained, exactly as this ran until now.
    kwargs: dict[str, Any] = {"max_tokens": 2000, "timeout_seconds": 180}
    if _accepts_response_format(provider):
        kwargs["response_format"] = _EXTRACTION_SCHEMA
    else:
        logger.warning(
            "Provider does not accept response_format; extracting without constrained output"
        )

    try:
        messages = [{"role": "user", "content": _EXTRACTION_PROMPT_PREFIX + transcript}]
        raw_text = "".join(provider.chat(messages, **kwargs))
    except (ProviderUnavailableError, ProviderExecutionError) as e:
        logger.error(f"Observer LLM call failed, failing open: {e}")
        return _empty_output()

    parsed = _extract_json(raw_text)
    if parsed is None:
        logger.error("Observer output was not valid JSON, failing open")
        return _empty_output()

    # Hoisted above both loops: memory candidates are now grounded against the
    # transcript too, not only decisions.
    assistant_lines = _extract_assistant_lines(transcript)
    transcript_lower = transcript.lower()

    raw_memory = parsed.get("memory_candidates")
    memory_candidates = []
    if isinstance(raw_memory, list):
        for m in raw_memory:
            candidate = _sanitize_memory_candidate(m)
            if candidate is None:
                continue
            # Memory candidates previously bypassed grounding entirely, while
            # decisions had been given two checks - so an invented preference
            # reached Stage 12 on nothing but its own say-so, and the
            # evidence_text shown to the user when reviewing it was never
            # verified to exist.
            #
            # Found live once response_format made the output legible: the
            # model returned the prompt's own placeholder,
            # "the exact quote or paraphrase this was drawn from", as the
            # evidence for a real preference. Grounding subsumes that specific
            # symptom rather than special-casing it - a placeholder string
            # isn't in the transcript either, so it fails the same check any
            # other unverifiable evidence does. Enumerating placeholder
            # spellings would be the whack-a-mole this codebase has already
            # lost once, in Stage 1's project-term matching.
            if not _quote_is_grounded(candidate["evidence_text"], transcript_lower):
                logger.info(
                    f"Observer: dropping memory candidate whose evidence_text is not in the "
                    f"transcript (placeholder or confabulated): "
                    f"{candidate['target_table']}.{candidate['field_name']}={candidate['proposed_value']!r}"
                )
                continue
            memory_candidates.append(candidate)

    raw_decisions = parsed.get("decision_candidates")
    decision_candidates = []
    if isinstance(raw_decisions, list):
        for d in raw_decisions:
            candidate = _sanitize_decision_candidate(d)
            if candidate is None:
                continue
            if _looks_like_assistant_echo(candidate["decision_text"], assistant_lines):
                logger.info(
                    f"Observer: dropping decision candidate that looks like an assistant echo: "
                    f"{candidate['decision_text']!r}"
                )
                continue
            if not _quote_is_grounded(candidate["raw_quote"], transcript_lower):
                logger.info(
                    f"Observer: dropping decision candidate with an unverifiable raw_quote "
                    f"(likely confabulated): {candidate['decision_text']!r}"
                )
                continue
            decision_candidates.append(candidate)

    snapshot = (
        _sanitize_snapshot(parsed.get("session_snapshot"))
        if _has_any_substantive_user_turn(transcript)
        else _empty_snapshot()
    )

    return {
        "memory_candidates": memory_candidates,
        "decision_candidates": decision_candidates,
        "session_snapshot": snapshot,
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

    # An empty-topic snapshot means run() withheld it as ungrounded (no
    # substantive user turn to summarize) - persisting it anyway would
    # clobber the last REAL snapshot with nothing, discarding legitimate
    # prior-session context just because this particular session was thin
    # ("hi" / "thanks" / "bye"). Leaving the last good snapshot in place is
    # strictly better than overwriting it with an empty one.
    if output["session_snapshot"].get("topic"):
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
