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
from backend.stages import stage_04_memory_lookup as stage_04

logger = logging.getLogger(__name__)

# Rewritten after a live end-to-end failure that the previous wording caused
# rather than merely failed to prevent. The old text opened with "a locally-run
# personal assistant with access to the user's project history, decisions, and
# preferences" - asserting to the model that it HOLDS that history, before any
# of it was shown. Asked to list projects while the profile block contained a
# single terse row, the model resolved the contradiction the way the prompt
# invited: it produced the history it had been told it had, inventing three
# projects with fabricated progress reports. Removing the capability claim
# matters as much as adding the prohibition - a model told it has records will
# supply records.
#
# The old prohibition ("never invent decisions or preferences") also enumerated
# the wrong nouns: projects, goals, skills and tools were all absent from it,
# and projects were exactly what got invented. This states the rule over the
# context as a whole instead of by category, so it cannot be outgrown by adding
# a table.
# The grounding rules deliberately bind only to claims ABOUT THE USER, not to
# the whole reply. A first version applied them to everything and was tested
# live: "what is a hash table?" came back "I don't have that recorded." That is
# the same failure as confabulation seen from the other side - the model
# treating its own general knowledge as off-limits because nothing in the
# profile mentioned hash tables. The pipeline has always distinguished these
# (general_knowledge and technical_explanation are their own categories, cached
# for 24h precisely because the model answers them from training), so the
# prompt has to as well. Rule 5 exists to make the boundary explicit rather
# than leaving the model to infer it from rules 1-4.
_DEFAULT_SYSTEM_INSTRUCTIONS = (
    "You are PIP, a locally-run personal assistant. Everything you know about "
    "THIS USER appears in the context below - you have no other memory of them.\n"
    "Rules for statements about the user (their projects, decisions, goals, "
    "skills, preferences, identity):\n"
    "1. State only what the context contains. Do not add, extrapolate, or "
    "illustrate with plausible examples.\n"
    "2. A section marked 'complete list' is exhaustive. Never add entries to it, "
    "and never present it as partial.\n"
    "3. A section marked 'none recorded' means the user genuinely has none. Say "
    "so plainly - do not treat it as missing data to fill in.\n"
    "4. If the context does not contain a fact about the user that was asked "
    "for, say you do not have it recorded, and stop. An honest 'I don't have "
    "that recorded' is always correct; a plausible guess is always wrong.\n"
    "5. These rules cover facts about the user only. For general questions - "
    "how something works, what a term means, help with a problem - answer "
    "normally and fully from your own knowledge. Absence from the context is "
    "not a reason to refuse; it only means the question was not about the "
    "user's records.\n"
    "6. Write in your own words to the user. The headings and annotations below "
    "('complete list', '3 recorded') are notes to you about how far the record "
    "extends - never repeat them back as if they were part of the answer."
)

# Human-readable section names. The profile arrives as flat (table, field,
# value) triples, which rendered as "active_projects.PIP: a personalised
# system" - a database row, not a statement about the user, and empirically not
# recognised as a project list at all.
_TABLE_LABELS = {
    "identity": "Identity",
    "active_projects": "Projects",
    "goal_memory": "Goals",
    "skill_memory": "Skills",
    "preference_memory": "Preferences",
    "preferred_tools": "Preferred tools",
    "topic_interests": "Topics they keep returning to",
    "document_access_patterns": "Documents they consult most",
    "interaction_style": "Interaction style",
}

# Tables where an empty result is itself information worth stating. Absence of
# a "Projects" heading reads as "not retrieved"; "Projects: none recorded"
# reads as a fact, and is the difference between the model reporting none and
# inventing three. Not applied to every table - "Interaction style: none
# recorded" is noise, since nothing hinges on its absence.
_ASSERT_EMPTY_FOR = {"active_projects", "goal_memory", "skill_memory", "preferred_tools"}

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


# How many of the (bm25-ranked) decision entries carry their reasoning into
# the prompt, and how much of it. Sized against decision_log_tokens (600): the
# top three at ~45 words each leave room for a dozen more headline lines.
_DECISIONS_WITH_REASONING = 3
_REASONING_WORDS = 45
# alternatives_considered is one short sentence, not a paragraph, so it costs a
# fraction of what reasoning does per entry - which is why it is given a wider
# window than _DECISIONS_WITH_REASONING rather than sharing it.
_DECISIONS_WITH_ALTERNATIVES = 6
_ALTERNATIVES_WORDS = 35


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
    # The ellipsis counts. Appending it after taking max_tokens words returned
    # max_tokens + 1, so every section this trims sat one word over the budget
    # it was being trimmed to - small, but it made "<= budget" false for the
    # one path that exists to make it true.
    return " ".join(words[: max_tokens - 1]) + " ..."


def _profile_line(r: dict[str, Any]) -> str:
    field, value = str(r["field"]), str(r["value"])
    line = f"  - {field}" if field == value else f"  - {field}: {value}"
    if r.get("stale"):
        line += "  [not mentioned recently - may no longer be current]"
    return line


def _format_profile(
    fields: list[dict[str, Any]],
    max_tokens: int,
    expected_tables: Optional[set[str]] = None,
) -> str:
    """
    Renders the profile grouped under human-readable headings, each labelled
    with how many entries it holds and that the list is complete.

    expected_tables is what Stage 4 looked up (see its tables_for_category).
    Tables in that set with no rows are rendered "none recorded" rather than
    omitted, so the model is told the user has none instead of being left to
    infer it simply wasn't shown them - the distinction that decides whether it
    answers "you have no projects" or invents some.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for f in fields:
        grouped.setdefault(f["table"], []).append(f)

    for table in expected_tables or set():
        if table in _ASSERT_EMPTY_FOR:
            grouped.setdefault(table, [])

    if not grouped:
        return ""

    blocks = []
    for table in sorted(grouped, key=lambda t: list(_TABLE_LABELS).index(t) if t in _TABLE_LABELS else 99):
        rows = grouped[table]
        label = _TABLE_LABELS.get(table, table)

        if not rows:
            blocks.append(f"{label}: none recorded.")
            continue

        header = f"{label} ({len(rows)} recorded, complete list):"
        # field == value for set-membership tables (preferred_tools stores the
        # tool name in both), where "vs code: vs code" is just noise.
        #
        # Stale entries are marked, not dropped. A goal that has gone quiet past
        # goal_decay_inactive_days may be finished, abandoned, or simply not
        # discussed lately, and the model guessing which is exactly the
        # invention this block is built to prevent - so it is told the age of
        # the record and left to treat it accordingly. Dropping it would be
        # worse still: the header promises a complete list.
        body = "\n".join(_profile_line(r) for r in rows)
        blocks.append(f"{header}\n{body}")

    return _truncate_to_tokens(
        "WHAT PIP HAS RECORDED ABOUT THIS USER (the complete record, not a sample):\n\n"
        + "\n\n".join(blocks),
        max_tokens,
    )


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
    """
    Dated decision lines, with the reasoning behind the most relevant few.

    This used to render decision_text alone. Both of the other columns it
    dropped are the ones a question about the decision log actually asks for:

    created_at, so "when did I build the RAG part?" is answerable at all. The
    date was on every row and never left the database, so the log could say
    what was decided but never when - which is most of what a history is for.

    reasoning, so "why" questions get the argument rather than the headline.
    An entry reading "The Observer runs on llama3.1:8b instead of a separate
    small model" is the conclusion of an A/B test whose numbers are sitting in
    reasoning, unread, while the model is left to guess at the justification -
    exactly the gap that invites it to invent one.

    alternatives_considered, so "why did we choose X" gets the thing X was
    chosen over. This column was rendered nowhere at all, while holding the
    most directly useful sentence in the row for exactly that question. Found
    live: "why did we choose per-source token budgets instead of fixed
    reservations?" answered "I do not have that recorded" against a row whose
    alternatives column reads "Treating the per-source budgets as fixed
    reservations, which cannot be made to sum correctly and would have starved
    whichever source was listed last." The model was refusing to guess, which
    is correct behaviour - it had simply never been shown the answer. Ten
    active entries carry one, and none of them reached the prompt.

    Only the top few carry reasoning. Entries arrive bm25-ranked from Stage 3,
    so the first ones are the most relevant, and reasoning is far longer than
    decision_text - giving it to every entry would spend the whole budget on
    two or three of them.

    Built up to the budget rather than built whole and truncated, because
    _truncate_to_tokens() joins on whitespace and would flatten the dates and
    indented reasoning into one run-on line. Stopping at the budget keeps the
    structure and drops whole entries from the least relevant end, which is
    the same thing the rolling-window trim does for conversation history.
    """
    if not entries:
        return ""

    header = "RELEVANT DECISIONS (most relevant first):"
    used = _estimate_tokens(header)
    lines: list[str] = []

    for position, entry in enumerate(entries):
        # .get() throughout: Stage 3 hands over whole decision_log rows, but
        # this function is called directly with partial dicts too, and a
        # missing date is not a reason to drop a real decision.
        date = (entry.get("created_at") or "")[:10]
        text = entry.get("decision_text", "")
        if not text:
            continue

        block = [f"- [{date}] {text}" if date else f"- {text}"]

        reasoning = (entry.get("reasoning") or "").strip()
        if reasoning and position < _DECISIONS_WITH_REASONING:
            words = reasoning.split()
            if len(words) > _REASONING_WORDS:
                reasoning = " ".join(words[:_REASONING_WORDS]) + " ..."
            else:
                reasoning = " ".join(words)
            block.append(f"    why: {reasoning}")

        alternatives = (entry.get("alternatives_considered") or "").strip()
        if alternatives and position < _DECISIONS_WITH_ALTERNATIVES:
            words = alternatives.split()
            if len(words) > _ALTERNATIVES_WORDS:
                alternatives = " ".join(words[:_ALTERNATIVES_WORDS]) + " ..."
            else:
                alternatives = " ".join(words)
            block.append(f"    instead of: {alternatives}")

        cost = sum(_estimate_tokens(line) for line in block)
        if lines and used + cost > max_tokens:
            break
        used += cost
        lines.extend(block)

    if not lines:
        return ""
    # The first entry can exceed the budget on its own; truncate that one case
    # rather than returning nothing at all for it.
    return _truncate_to_tokens(header + "\n" + "\n".join(lines), max_tokens)


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
    category: Optional[str] = None,
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
    drops the snapshot (the live conversation_history already covers that gap,
    a snapshot recap would be redundant) unless nothing is actually covering it
    - see the floor at the top of the body - and modifier=3 (>7d "full") gets
    1.5x the base budget for a longer-absence recap. Defaults to 2 so any
    caller that doesn't pass it (tests, direct callers) keeps the pre-existing
    fixed-budget behavior unchanged.

    Failure mode: any exception during assembly falls back to the documented
    minimal prompt (system instructions + user message only), matching the
    Part 7 Stage 7 spec, and is logged rather than silently swallowed.
    """
    try:
        budget = get_settings()["pipeline"]

        # modifier=0 (a gap under an hour) zeroes the snapshot on the premise
        # that the live conversation is already carrying the recap. Found live,
        # in the one case where that premise does not hold: a new chat opened
        # minutes after the previous one, asked "what we were doing last time in
        # pip project", answered "I don't have that recorded". Every new chat
        # window is its own session (one WS connection each, begin_session on
        # its first message), so previous_session_date is always minutes old and
        # Stage 0 always returns 0 - while a brand-new conversation starts with
        # an empty history, so nothing was carrying the recap the modifier
        # assumed redundant. The snapshot is the only section that can answer
        # that question, and it was budgeted to zero on every attempt inside the
        # hour - deterministically, not intermittently.
        #
        # So the floor applies exactly where the premise fails: no live history
        # to lean on, or the user asking for the recap outright
        # (project_continuation is Stage 1's category for "continue" / "where
        # were we" / "last time" - the question this section exists to answer;
        # withholding it there is the same defect as refusing from an empty
        # profile). max(), not an override, so modifier=3's wider window for a
        # long absence still wins.
        snapshot_budget = int(budget["session_snapshot_tokens"] * (context_depth_modifier / 2))
        if category == "project_continuation" or not conversation_history:
            snapshot_budget = max(snapshot_budget, budget["session_snapshot_tokens"])

        # category is optional so existing callers (tests, direct users) keep
        # working unchanged; without it, empty tables are simply omitted as
        # before rather than asserted as "none recorded".
        expected_tables = stage_04.tables_for_category(category) if category else None
        profile_text = _format_profile(profile_fields or [], budget["user_profile_tokens"], expected_tables)
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
