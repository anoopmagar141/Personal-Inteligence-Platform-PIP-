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
# Every memory_candidate below carries evidence_count=1, and correctly so - a
# single-pass extraction over one transcript can only attest "observed once, this
# session." Accumulating past that is Part 8.6's REINFORCEMENT step, which lives in
# stage_12.reinforce_evidence() and is applied to every candidate before validation
# in run_session_end() below.
#
# This comment previously said reinforcement was "NOT implemented here or anywhere
# yet", and it was half right for longer than it looked: the function existed and
# was called, but it could only raise evidence_count by reading an already-stored
# row, and storing that row is precisely what the thresholds were blocking. So the
# predicted failure happened anyway - explicit candidates stopped clearing past
# Week 3-4, exactly as written here - while the code read as though it had been
# handled. Reinforcement now accumulates in memory_observation_log, so a signal
# repeated across sessions gains evidence without needing a prior write.
#
# What remains true: an INFERRED candidate still cannot auto-write from month 2
# onward, because that threshold also requires confidence >= 0.7 and the inferred
# label caps confidence at 0.4 no matter how much evidence accrues. That is the
# constitution's confidence model rather than a gap - such a signal is meant to
# reach the profile through the user (the memory_candidates_pending review queue),
# not through repetition alone.

import inspect
import json
import logging
import re
from pathlib import Path
from typing import Any, Optional, TypedDict

from backend.config.settings import get_settings
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

# target_tables the Observer may propose candidates for. Every key here must be
# a real table that the whole downstream path can actually handle.
#
# "observer_writable" used to be a key, carried over from constitutional.json's
# observer_may_write.fields - but that is a CATEGORY NAME grouping three tables,
# not a table itself. The prompt taught it to the model as a target_table, the
# model dutifully emitted it, and ConstitutionEnforcer HARD_REJECTed every one
# as a schema violation because no table by that name exists. Seen live: two
# candidates rejected and four "Unhandled target_table in _fetch_existing_state"
# warnings from a single session, every run, guaranteed.
#
# The three tables it named (topic_interests, preferred_tools,
# document_access_patterns) are genuinely permitted by the constitution, and
# they are NOT listed here on purpose. Naming them correctly would only move the
# failure later and make it worse: stage_12's _fetch_existing_state has no
# branch for any of them, and profile_store.write_approved_candidate raises
# "Unsupported target_table for approved write", so an APPROVED candidate would
# throw, be retried once, and land as "failed" - an exception path instead of
# today's clean rejection.
#
# Enabling them means three things, in this order: a _fetch_existing_state
# handler, a write_approved_candidate branch (they are set-membership tables -
# topic/tool_name/document_path with an evidence counter, not the
# name/value shape the others use), and something that actually READS them.
# That last one is the reason this is a removal rather than an implementation:
# nothing in the codebase selects from topic_interests or
# document_access_patterns at all - not get_profile(), not any of stage_04's
# category table sets - so writing to them would produce data no prompt ever
# sees and no profile view ever shows.
#
# Tool preferences are not lost by this: preference_memory.preferred_tools is
# listed below, is observer-writable, and is read by get_profile() and
# stage_04's coding_question - a path that works end to end today.
# target_table -> either a fixed list of field names, or a sentence describing
# what field_name means for an open-ended table. Both render into the prompt
# (see _approved_fields_prompt_block) and the keys drive the constrained-output
# schema's target_table enum.
APPROVED_MEMORY_FIELDS = {
    # field_name is the SKILL'S OWN NAME, matching skill_memory.name - which is
    # what onboarding writes ("Python") and what get_profile and
    # soft_delete_profile_field key on.
    #
    # This used to be the fixed list [python_level, docker_level, sql_level],
    # and it was wrong twice over. It could only ever learn three skills, so a
    # Rust developer's Rust was unlearnable by construction. And the names did
    # not match the store: a candidate for "python_level" found no existing
    # row, was treated as a brand new skill, and INSERTed a second row beside
    # the real one - measured, a profile holding both ("Python", 0.5) and
    # ("python_level", 0.9) after a single session. Same family as the
    # goal:<id> mismatch: two halves of the system disagreeing about what a
    # record is called, with nothing positioned to see both.
    "skill_memory": (
        "the skill's own name, e.g. Python or Rust; proposed_value must be a "
        "number from 0.0 to 1.0 estimating demonstrated ability"
    ),
    "preference_memory": ["preferred_tools", "answer_style"],
    "goal_memory": ["active_goals", "project_objectives"],
    # Open-ended by nature: the field name IS the topic, so there is no fixed
    # list to enumerate. The constrained-output schema only enums target_table,
    # never field_name, so this shape was always expressible.
    "topic_interests": "any short topic name the user keeps returning to",
    # Both of these are supported end to end downstream - _fetch_existing_state
    # reads them, write_approved_candidate and apply_verified_correction write
    # them - and were simply never offered to the model, so a conversation could
    # not teach PIP that a new project had started or that the user wants to be
    # answered differently. Both are gated by the constitution, so neither is
    # written without the user confirming it.
    "active_projects": "the project's name; proposed_value is a one-line description",
    "interaction_style": (
        "always the literal word value; proposed_value is how the user wants to "
        "be answered, e.g. concise"
    ),
}


def _approved_fields_prompt_block() -> str:
    """
    The APPROVED MEMORY FIELDS section of the extraction prompt, generated from
    APPROVED_MEMORY_FIELDS rather than restated by hand.

    The schema's target_table enum was already derived from that dict, with a
    comment claiming this kept "the schema, the prompt and the write path" from
    drifting to three different answers - but the prompt text underneath was a
    hand-written literal that no such derivation touched. Adding a table would
    have updated two of the three and left the model still being told the old
    list.
    """
    lines = []
    for table, fields in APPROVED_MEMORY_FIELDS.items():
        rendered = fields if isinstance(fields, str) else ", ".join(fields)
        lines.append(f"  {table}: [{rendered}]")
    return "\n".join(lines)

_EXTRACTION_PROMPT_TEMPLATE = """SYSTEM:
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
  - When the user names something they are building or working on, record it
    in active_projects. A project is not covered by recording a goal about
    it, a topic of interest in it, or a skill used on it - those are
    different facts, and emitting them instead leaves the project itself
    unrecorded. Emit active_projects as well as, not instead of, those.
  - The OUTPUT FORMAT below shows the SHAPE of a candidate, not the menu of
    tables worth emitting. Any table in the approved list above is equally
    expected; do not favour the ones the example happens to illustrate.

APPROVED MEMORY FIELDS - target_table must be one of these exact names:
__APPROVED_FIELDS__
Use no other target_table. A candidate naming anything else is discarded.

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
    },
    {
      "target_table": "skill_memory",
      "field_name": "Rust",
      "proposed_value": "0.8",
      "label": "inferred",
      "evidence_count": 1,
      "evidence_text": "<the user's own words, copied exactly from the conversation>"
    },
    {
      "target_table": "active_projects",
      "field_name": "Orchard",
      "proposed_value": "a household inventory tracker",
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
                    # Constrained to the tables the whole downstream path can
                    # actually handle, so an unwritable target_table becomes
                    # unemittable rather than something the prompt merely asks
                    # the model not to produce - the same "constrain the
                    # mechanism" move as response_format itself. Derived from
                    # APPROVED_MEMORY_FIELDS so the schema, the prompt and the
                    # write path cannot drift to three different answers.
                    "target_table": {"type": "string", "enum": sorted(APPROVED_MEMORY_FIELDS)},
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


class ObserverUnavailableError(Exception):
    """
    Raised when the LLM could not be reached or errored out, so no extraction
    happened at all.

    Distinct from an extraction that ran and found nothing, and the distinction
    is the entire point. run() used to fail open here, returning an empty
    output that was indistinguishable from "this session contained nothing
    worth remembering" - and every caller believed it:

      - pending_observer.drain() saw no exception, called mark_completed(), and
        retired the queued transcript. Its own docstring says "observer_runner
        must raise on failure"; the function wired into it did not.
      - run_observer_now()'s _extract_and_mark() went on to mark_observed(),
        stamping the conversation as learned-from.

    So an unreachable Ollama silently consumed the transcript and advanced the
    high-water mark past turns nothing had ever read. Confirmed live: a
    recovered conversation was retired with zero candidates extracted, having
    never reached the model.

    That state is common rather than exotic. launch_pip.ps1 starts Ollama and
    the backend concurrently and deliberately does not wait for readiness, so
    startup catch-up can beat Ollama to being reachable - and after the crash
    or force-kill that recovery exists for, Ollama is usually not up yet.

    Failing open is right for a live per-message path, where a chat turn must
    not break because the Observer cannot run. It is wrong for the queue whose
    only job is not losing a transcript. Raising lets each caller choose, and
    they now do.
    """


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


def _is_storable_skill_level(value: Any) -> bool:
    """
    skill_memory.level is REAL NOT NULL CHECK (level >= 0.0 AND level <= 1.0).
    A word like "advanced" survives every check between here and the write, then
    fails that CHECK - and Stage 13 turns the IntegrityError into one retry and
    an outcome of "failed", so the signal is lost with only a log line to say so.
    Dropping it here instead makes it the same clean rejection as any other
    malformed candidate, and the prompt already tells the model to omit rather
    than guess.
    """
    try:
        return 0.0 <= float(value) <= 1.0
    except (TypeError, ValueError):
        return False


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
    if raw["target_table"] == "skill_memory" and not _is_storable_skill_level(raw["proposed_value"]):
        logger.info(
            f"Observer: dropping skill candidate whose level is not a 0.0-1.0 number: "
            f"{raw['field_name']}={raw['proposed_value']!r}"
        )
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


def _only_candidates_stated_this_session(
    output: ObserverOutput, unobserved_transcript: str
) -> ObserverOutput:
    """
    Drops candidates whose evidence lies in turns an earlier session already
    had its own Observer pass over.

    A resumed conversation arrives with its whole history, and that history is
    what the model is shown - deliberately, because the last few turns rarely
    make sense without it. But being SHOWN a turn again is not the user saying
    it again, and Stage 12 could not tell the difference: reinforce_evidence()
    stamps every extraction with the current session_no, so re-reading a
    conversation under a new session made a signal look independently observed
    twice, and the stored-value branch adds its own +1 on top. Two sessions of
    evidence is the week_3_4 auto-write threshold. So reopening an old chat and
    typing anything at all could write a preference the user stated exactly
    once, without them ever repeating it - which inverts what evidence_count is
    for. The constitution counts corroboration; this was counting re-reads.

    Deterministic, and deliberately not a prompt instruction: "only report what
    is new" is precisely the kind of self-report ADR-005 and every grounding
    check in this file already decline to trust. The same _quote_is_grounded()
    that decides whether a quote exists at all is simply asked a narrower
    question - does it exist in the part that is new.

    Safe against _cap_transcript(), which keeps the END of a long transcript:
    the unobserved turns ARE the end, so capping can only ever remove turns
    from the already-observed side. There is no case where a candidate is
    grounded in the new turns but capped out of the text checked here.

    The snapshot is untouched. It summarises the conversation, and a recap
    built from the last few turns alone would be worse for the same reason the
    model is shown the history in the first place.
    """
    unobserved_lower = unobserved_transcript.lower()

    memory_candidates = []
    for candidate in output["memory_candidates"]:
        if _quote_is_grounded(candidate["evidence_text"], unobserved_lower):
            memory_candidates.append(candidate)
        else:
            logger.info(
                "Observer: dropping memory candidate whose evidence is only in "
                f"already-observed turns (re-read, not restated): "
                f"{candidate['target_table']}.{candidate['field_name']}="
                f"{candidate['proposed_value']!r}"
            )

    decision_candidates = []
    for candidate in output["decision_candidates"]:
        if _quote_is_grounded(candidate["raw_quote"], unobserved_lower):
            decision_candidates.append(candidate)
        else:
            logger.info(
                "Observer: dropping decision candidate whose quote is only in "
                f"already-observed turns (re-read, not restated): "
                f"{candidate['decision_text']!r}"
            )

    return {
        "memory_candidates": memory_candidates,
        "decision_candidates": decision_candidates,
        "session_snapshot": output["session_snapshot"],
    }


def _substantive_user_turns(transcript: str, min_words: int = 4) -> int:
    """
    How many user turns carry at least min_words. The counting half of
    _has_any_substantive_user_turn, split out because two different questions
    are asked of the same signal: "is there anything real here at all" (>= 1,
    below) and "did this session go anywhere" (>= 2, see
    _snapshot_may_overwrite_the_standing_one).
    """
    count = 0
    for line in transcript.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("user:"):
            content = stripped.split(":", 1)[1].strip()
            if len(content.split()) >= min_words:
                count += 1
    return count


def _snapshot_may_overwrite_the_standing_one(transcript: str, output: ObserverOutput) -> bool:
    """
    Whether THIS session's snapshot has earned the right to replace the last
    one. session_snapshot is a singleton: writing is destroying, and there is
    no version behind it to fall back to.

    The old gate was "topic is non-empty", which withheld a snapshot only for a
    session that was pure acknowledgment. Found live, and the failure is
    circular in a way that gets worse each time it happens: the user opened a
    new chat and asked "what we were doing last time in pip project", PIP
    answered "I don't have that recorded", and the Observer then dutifully
    summarised THAT two-message exchange over the standing snapshot as

        topic: retrieving information about the pip project
        open_problems: ['User wants to recall previous conversation about pip project']
        suggested_next_step: Try searching previous conversations or ask for clarification

    So a failure to recall became the thing recalled, the session it failed to
    recall was destroyed in the process, and the NEXT attempt would be answered
    with a description of the previous attempt. Every retry ratchets the real
    content further out of reach - and a user whose recall just failed retries,
    which is precisely when this fires.

    A session earns the write by having arrived somewhere: it produced a
    candidate (something was learned), or it had more than one substantive user
    turn (it had an arc, not just a question and an answer). A single question
    that taught nothing is the one shape that must never overwrite a real
    session - it carries strictly less than what it would destroy.

    Counted on the uncapped transcript, unlike run()'s own gate: a session long
    enough for _cap_transcript to bite unquestionably went somewhere, so the
    only direction this errs is permissive, on exactly the sessions that need
    no protecting.
    """
    if not output["session_snapshot"].get("topic"):
        return False
    if output["memory_candidates"] or output["decision_candidates"]:
        return True
    return _substantive_user_turns(transcript) >= 2


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
    return _substantive_user_turns(transcript, min_words) >= 1


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


_EXTRACTION_PROMPT_PREFIX = _EXTRACTION_PROMPT_TEMPLATE.replace(
    "__APPROVED_FIELDS__", _approved_fields_prompt_block()
)


def _cap_transcript(transcript: str) -> str:
    """
    Bounds the transcript at observer.max_session_tokens (settings.json, 8000).
    That setting existed and was read by nothing, so a long session sent the
    whole thing: llama3.1:8b has a finite context window, and the failure when
    you exceed it is not an error but a silently truncated prompt - whichever
    end the runtime decides to drop, with the extraction quietly degrading and
    no way to tell from the output that it happened.

    Keeps the END of the transcript, not the start. A session-end pass is
    summarising what this session arrived at: the closing turns carry the
    decisions and the suggested next step, while the opening turns are the part
    most likely to have already been extracted by an earlier pass over an
    earlier session.

    Cut on line boundaries so the model never receives half a turn, and cut the
    transcript ONCE here so everything downstream - the grounding checks in
    particular - reasons about exactly the text the model was shown. Grounding a
    quote against turns the model never saw would accept a "quote" it could only
    have invented.
    """
    max_tokens = get_settings()["observer"]["max_session_tokens"]
    if len(transcript.split()) <= max_tokens:
        return transcript

    lines = transcript.splitlines()
    kept: list[str] = []
    used = 0
    for line in reversed(lines):
        cost = len(line.split())
        if used + cost > max_tokens and kept:
            break
        kept.append(line)
        used += cost
    kept.reverse()
    logger.warning(
        f"Observer transcript exceeded max_session_tokens ({max_tokens}); "
        f"kept the last {len(kept)} of {len(lines)} lines."
    )
    return "\n".join(kept)


def run(transcript: str, provider: BaseLLMProvider, conn) -> ObserverOutput:
    """
    Single-pass extraction over a full session transcript, capped at
    observer.max_session_tokens - see _cap_transcript().
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
    transcript = _cap_transcript(transcript)

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
        # Raised, not failed open - see ObserverUnavailableError. Nothing was
        # extracted because nothing was asked, and a caller that cannot tell
        # that from "found nothing" throws the transcript away.
        raise ObserverUnavailableError(f"Observer LLM call failed: {e}") from e

    parsed = _extract_json(raw_text)
    if parsed is None:
        # Still fails open, deliberately, and NOT as ObserverUnavailableError.
        # The model was reached and answered - it just answered badly. Treating
        # that as retryable would put an un-parseable transcript back on the
        # queue to fail again on every future start, a poison pill that blocks
        # the drain forever. A session lost to one bad response is the smaller
        # harm than a queue that can never empty.
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
    *,
    unobserved_transcript: Optional[str] = None,
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

    unobserved_transcript is the tail of `transcript` holding only the turns
    this session actually added - what a RESUMED conversation contributes, as
    opposed to the history it arrived carrying. Candidates are extracted from
    the whole transcript (the model needs the context) but only counted as
    evidence if they are grounded in that tail; see
    _only_candidates_stated_this_session for why re-reading is not
    corroborating. None means the whole transcript is new, which is the case
    for a fresh conversation and for the startup drain, and leaves every
    existing caller behaving exactly as before.
    """
    output = run(transcript, provider, conn)

    # Before the snapshot gate below, not after: that gate asks whether this
    # session arrived somewhere, and a pass that produced nothing but re-reads
    # has not.
    if unobserved_transcript is not None:
        output = _only_candidates_stated_this_session(output, unobserved_transcript)

    # An empty-topic snapshot means run() withheld it as ungrounded (no
    # substantive user turn to summarize) - persisting it anyway would
    # clobber the last REAL snapshot with nothing, discarding legitimate
    # prior-session context just because this particular session was thin
    # ("hi" / "thanks" / "bye"). Leaving the last good snapshot in place is
    # strictly better than overwriting it with an empty one. That is now the
    # first of the conditions in _snapshot_may_overwrite_the_standing_one,
    # which extends the same reasoning to a thin session that DOES produce a
    # topic - see it for the live failure that showed an empty topic was not
    # the only way to overwrite something real with nothing.
    # Isolated from the candidate loops below rather than sharing their fate.
    # Snapshot and candidates are independent products of one extraction: a
    # snapshot that fails to persist is a lost recap, and it must not also cost
    # the memory and decision candidates that were extracted alongside it.
    # Measured on the new turns, not the whole transcript: a resumed
    # conversation carries any number of substantive turns it was already
    # summarised from, and counting those would let one throwaway reply to an
    # old chat overwrite the standing snapshot.
    if _snapshot_may_overwrite_the_standing_one(
        transcript if unobserved_transcript is None else unobserved_transcript, output
    ):
        try:
            session_snapshot.write_snapshot(conn, output["session_snapshot"])
        except Exception as e:
            logger.error(f"Observer: session snapshot write failed, continuing with candidates: {e}")

    enforcer = ConstitutionEnforcer(CONSTITUTION_PATH)
    memory_results = []
    for candidate in output["memory_candidates"]:
        # Per-candidate isolation, and the reason is not hypothetical. A None
        # confidence reaching the enforcer's conflict check raised TypeError
        # here, and with nothing between that raise and the caller it escaped
        # run_session_end entirely - the WS handler logged "session transcript
        # discarded" and the ENTIRE session was lost: every other memory
        # candidate, every decision candidate, all of it, over one bad row.
        # That specific bug is fixed (constitution_enforcer.py), but the blast
        # radius was the real defect: these three calls run arbitrary
        # extraction output against the constitution, the profile store and
        # the DB, and one candidate failing is a reason to drop that candidate,
        # never the session around it.
        #
        # Recorded as a result rather than skipped silently - the count in
        # session_lifecycle's log line stays honest about how many candidates
        # were handled, and "ERROR"/"failed" is visible to anyone reading the
        # outcome instead of a candidate that simply vanished. "failed" is the
        # outcome Stage 13 already uses for a candidate that could not be
        # written, so no reader needs a new value to understand this one.
        try:
            # Reinforcement must happen before validation and be visible to the write:
            # a single-pass extraction can only ever produce evidence_count=1 on its
            # own, so without this, repeat observations across sessions would never
            # accumulate and would keep failing Stage 12's tiered thresholds forever.
            candidate = stage_12.reinforce_evidence(conn, candidate)
            validation_result = stage_12.run(conn, candidate, enforcer)
            outcome = stage_13.run(conn, candidate, validation_result)
            status = validation_result.status
        except Exception as e:
            logger.error(
                f"Observer: candidate {candidate.get('target_table')}."
                f"{candidate.get('field_name')} failed, dropping it and continuing: {e}"
            )
            status, outcome = "ERROR", "failed"
        memory_results.append({
            "candidate": candidate,
            "validation_status": status,
            "outcome": outcome,
        })

    decision_results = []
    for dc in output["decision_candidates"]:
        # Same isolation, same reason: one unroutable decision must not take
        # the rest of the session's decisions down with it.
        try:
            result = decision_log.route_observer_decision(
                conn,
                text=dc["decision_text"],
                signals_found=dc["signals_found"],
                raw_quote=dc["raw_quote"],
                project_id=project_id,
            )
        except Exception as e:
            logger.error(f"Observer: decision candidate failed, dropping it and continuing: {e}")
            result = {"status": "failed", "error": str(e), "decision_text": dc.get("decision_text")}
        decision_results.append(result)

    return {
        "snapshot": output["session_snapshot"],
        "memory_results": memory_results,
        "decision_results": decision_results,
    }
