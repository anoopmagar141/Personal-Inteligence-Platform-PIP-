# PIP Message Pipeline - Stage 7: Context Assembly
#
# Resolves a real inconsistency in the spec rather than silently picking a side:
# the itemized per-source budget (150+400+250+600+800+800+1000+400 = 4400 content
# + 2000 reserved-for-response = 6400) does NOT sum to the stated 6000 total - it's
# 400 tokens over, and the same numbers are baked into settings.json too, not just
# doc prose. Resolution: the per-source numbers are MAXIMUM ceilings per source, not
# guaranteed fixed reservations. Not every source is ever maxed out simultaneously in
# practice (e.g. RAG contributes 0 tokens when nothing matched), and when the
# worst case does happen, the overflow-priority trimming below is exactly the
# mechanism that reconciles 4400 down to the true 4000 available for content
# (6000 total - 2000 reserved for the response). If every trimmable section gets
# fully dropped, what remains is system_instructions + user_message - which is
# word-for-word the documented ultimate failure mode ("minimal prompt = system +
# message only"), confirming this reading is consistent with the rest of the spec.
#
# Also resolves an ambiguous numbering: "Overflow priority (what gets dropped
# first): 1. User message (never drop) ... 7. Web results" is self-contradictory
# read as a literal drop sequence (rank 1 listed first but never dropped). Read
# instead as a priority RANK (1 = most protected, 7 = least protected, dropped
# first) - the same convention already used for ADR-023's Cache Authority
# Hierarchy and Stage 2's default retrieval priority elsewhere in this project.

import logging
from typing import Any, Optional, TypedDict

from backend.config.settings import get_settings

logger = logging.getLogger(__name__)

_DEFAULT_SYSTEM_INSTRUCTIONS = (
    "You are PIP, a locally-run personal assistant with access to the user's "
    "project history, decisions, and preferences. Use the context provided below "
    "when relevant. Never invent decisions or preferences that aren't given to you."
)

# Priority rank order, 1 (most protected) to 7 (dropped first). system_instructions
# and user_message aren't in this list at all - both are always included in full,
# never subject to trimming (system_instructions is "(fixed)" per spec; user_message
# is explicitly "(never drop)").
_PRIORITY_RANK = [
    "decision_log",
    "profile",
    "rag_chunks",
    "session_snapshot",
    "conversation_history",
    "web_results",
]


class AssembledContext(TypedDict):
    context: str
    messages: list[dict[str, str]]


def _estimate_tokens(text: str) -> int:
    """
    Word-count approximation, not a real tokenizer - same documented tradeoff as
    vector_store.py's chunker. Good enough for budget bookkeeping; real tokenizer
    counts would run somewhat higher due to subword splitting.
    """
    return len(text.split())


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    words = text.split()
    if len(words) <= max_tokens:
        return text
    return " ".join(words[:max_tokens]) + " ..."


def _format_profile(fields: list[dict[str, Any]], max_tokens: int) -> str:
    if not fields:
        return ""
    lines = [f"- {f['table']}.{f['field']}: {f['value']}" for f in fields]
    return _truncate_to_tokens("USER PROFILE:\n" + "\n".join(lines), max_tokens)


def _format_snapshot(snapshot: Optional[dict[str, Any]], max_tokens: int) -> str:
    if max_tokens <= 0 or not snapshot or not snapshot.get("topic"):
        return ""
    lines = [f"Last session topic: {snapshot['topic']}"]
    if snapshot.get("last_decisions"):
        lines.append("Recent decisions: " + "; ".join(snapshot["last_decisions"]))
    if snapshot.get("open_problems"):
        lines.append("Open problems: " + "; ".join(snapshot["open_problems"]))
    if snapshot.get("suggested_next_step"):
        lines.append(f"Suggested next step: {snapshot['suggested_next_step']}")
    return _truncate_to_tokens("SESSION SNAPSHOT:\n" + "\n".join(lines), max_tokens)


def _format_decisions(entries: list[dict[str, Any]], max_tokens: int) -> str:
    if not entries:
        return ""
    lines = [f"- {e['decision_text']}" for e in entries]
    return _truncate_to_tokens("RELEVANT DECISIONS:\n" + "\n".join(lines), max_tokens)


def _format_rag_chunks(chunks: list[dict[str, Any]], max_tokens: int) -> str:
    if not chunks:
        return ""
    lines = [f"- ({c.get('file_path', 'unknown')}) {c['chunk_text']}" for c in chunks]
    return _truncate_to_tokens("RELEVANT DOCUMENTS:\n" + "\n".join(lines), max_tokens)


def _format_web_results(results: list[dict[str, Any]], max_tokens: int) -> str:
    if not results:
        return ""
    lines = [f"- {r['title']}: {r['snippet']} ({r['url']})" for r in results]
    return _truncate_to_tokens("WEB SEARCH RESULTS:\n" + "\n".join(lines), max_tokens)


def _trim_conversation_history(history: list[dict[str, str]], max_tokens: int) -> list[dict[str, str]]:
    """Rolling window: keeps the most recent messages, drops oldest first."""
    kept: list[dict[str, str]] = []
    total = 0
    for message in reversed(history):
        tokens = _estimate_tokens(message.get("content", ""))
        if total + tokens > max_tokens:
            break
        kept.append(message)
        total += tokens
    return list(reversed(kept))


def run(
    user_message: str,
    *,
    system_instructions: str = _DEFAULT_SYSTEM_INSTRUCTIONS,
    profile_fields: Optional[list[dict[str, Any]]] = None,
    session_snapshot: Optional[dict[str, Any]] = None,
    decision_log_entries: Optional[list[dict[str, Any]]] = None,
    rag_chunks: Optional[list[dict[str, Any]]] = None,
    web_results: Optional[list[dict[str, Any]]] = None,
    conversation_history: Optional[list[dict[str, str]]] = None,
    context_depth_modifier: int = 2,
) -> AssembledContext:
    """
    Assembles a token-budgeted context string and message list, ready for
    BaseLLMProvider.chat(messages=result["messages"], context=result["context"]) -
    that method's existing (messages, context) split (OllamaProvider already
    prepends context as a system message) is exactly what this stage targets, not
    a single flat prompt string.

    context_depth_modifier (0-3) is Stage 0's gap-detector output ("scales
    session_snapshot allocation" per the glossary) - it scales
    session_snapshot_tokens by modifier/2, so modifier=2 (the 24h-7d "summary"
    gap) reproduces the original fixed budget exactly, modifier=0 (<1h "none")
    drops the snapshot entirely (the live conversation_history already covers
    that gap, a snapshot recap would be redundant), and modifier=3 (>7d "full")
    gets 1.5x the base budget for a longer-absence recap. Defaults to 2 so any
    caller that doesn't pass it (tests, direct callers) keeps the pre-existing
    fixed-budget behavior unchanged.

    Failure mode: any exception during assembly falls back to the documented
    minimal prompt (system instructions + user message only), matching the
    Part 7 Stage 7 spec, and is logged rather than silently swallowed.
    """
    try:
        budget = get_settings()["pipeline"]

        snapshot_budget = int(budget["session_snapshot_tokens"] * (context_depth_modifier / 2))

        profile_text = _format_profile(profile_fields or [], budget["user_profile_tokens"])
        snapshot_text = _format_snapshot(session_snapshot, snapshot_budget)
        decisions_text = _format_decisions(decision_log_entries or [], budget["decision_log_tokens"])
        rag_text = _format_rag_chunks(rag_chunks or [], budget["rag_chunks_tokens"])
        web_text = _format_web_results(web_results or [], budget["web_search_tokens"])
        history = _trim_conversation_history(conversation_history or [], budget["conversation_history_tokens"])

        sections: dict[str, Any] = {
            "decision_log": decisions_text,
            "profile": profile_text,
            "rag_chunks": rag_text,
            "session_snapshot": snapshot_text,
            "conversation_history": history,
            "web_results": web_text,
        }

        def _section_tokens(key: str) -> int:
            value = sections[key]
            if key == "conversation_history":
                return sum(_estimate_tokens(m.get("content", "")) for m in value)
            return _estimate_tokens(value)

        system_tokens = _estimate_tokens(system_instructions)
        message_tokens = _estimate_tokens(user_message)
        available_for_content = budget["context_token_budget"] - budget["response_reserved_tokens"]

        total = system_tokens + message_tokens + sum(_section_tokens(k) for k in sections)

        # Drop from lowest priority (rank 6, web_results) upward until it fits, or
        # everything trimmable is gone - at which point what remains is exactly
        # system_instructions + user_message, the documented failure-mode floor.
        for key in reversed(_PRIORITY_RANK):
            if total <= available_for_content:
                break
            if key == "conversation_history" and sections[key]:
                # Oldest-first partial trim, not whole-section removal, per spec.
                while sections[key] and total > available_for_content:
                    dropped = sections[key].pop(0)
                    total -= _estimate_tokens(dropped.get("content", ""))
            elif sections[key]:
                total -= _section_tokens(key)
                sections[key] = [] if key == "conversation_history" else ""

        context_parts = [system_instructions]
        for key in _PRIORITY_RANK:
            if key != "conversation_history" and sections[key]:
                context_parts.append(sections[key])
        context = "\n\n".join(context_parts)

        messages = list(sections["conversation_history"]) + [{"role": "user", "content": user_message}]

        return {"context": context, "messages": messages}

    except Exception as e:
        logger.error(f"Stage 7 context assembly failed, falling back to minimal prompt: {e}")
        return {
            "context": system_instructions,
            "messages": [{"role": "user", "content": user_message}],
        }
