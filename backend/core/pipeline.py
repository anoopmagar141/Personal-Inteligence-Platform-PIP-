# PIP Core - 14-Stage Message Pipeline Orchestrator
#
# Wires Stages 0-10 for a single user message. Stages 11-13 (Observer, Validation,
# Write) are session-end only (Rule 3: never per-message) - triggered separately by
# whatever process-lifecycle code eventually calls stage_11_observer.run_session_end(),
# not from here.
#
# Known, deliberate simplification: Part 7's spec has Stages 3/4/5 running in
# parallel via asyncio.gather, and Stage 6 firing in a background thread at Stage 1
# detection. Stages 3/4/5/6 run sequentially here. The async server layer this was
# originally waiting on (Phase 8) now exists, but re-checked before attempting the
# parallelization anyway, since "the async wrapper exists now" turned out not to be
# the whole story: Stages 3, 4, AND 5 all take the same `conn` and use it for real
# reads (decision_log FTS lookup, profile_store, vector_store, and Stage 5 ALSO
# calls decision_log for its conflict check) - the exact SQLite/SQLCipher
# thread-affinity constraint this same session hit as a live production bug in the
# WS endpoint (connections can only be used on the thread that created them).
# Naively `asyncio.gather`-ing three functions that share one connection across
# different executor threads would reintroduce that bug class, not avoid it. Doing
# this safely needs either a dedicated connection per stage (extra open/close cost,
# and WAL-mode concurrent-reader behavior would need verifying) or moving DB access
# to something actually async - a real design decision, not the "mechanical
# follow-up" this comment used to claim. Left sequential; the honest cost is Stage
# 5's embedding query (the only even mildly slow one of the three) blocking Stages 3
# and 4's fast local DB reads for its duration, not the reverse.
#
# Conversation history is NOT persisted by this module. The caller - /ws/chat -
# accumulates conversation_history across turns and passes it in on each call.
#
# It IS persisted, just not here: schema.sql has had conversations and messages
# tables since chat history gained a sidebar, and ws_chat writes every turn to
# them as it happens. This comment used to say no such table existed and name
# the handler as a future arrival, which mattered beyond tidiness - startup
# recovery of an unobserved session depends on those tables, and a reader
# trusting this note would have concluded that rebuilding a lost transcript was
# impossible.

import logging
import time
from datetime import date, datetime
from typing import Any, Callable, Generator, Optional, Union

from backend.core import response_cache, trace
from backend.memory import llm_endpoint_store, profile_store
from backend.memory import conversation_store, session_snapshot
from backend.providers.base_provider import BaseLLMProvider
from backend.providers.ollama_provider import OllamaProvider, default_model_name, window_detail
from backend.providers.openai_compatible_provider import OpenAICompatibleProvider
from backend.stages import stage_00_gap_detector as stage_00
from backend.stages import stage_01_intent_classifier as stage_01
from backend.stages import stage_02_router as stage_02
from backend.stages import stage_03_decision_log_lookup as stage_03
from backend.stages import stage_04_memory_lookup as stage_04
from backend.stages import stage_05_rag_retrieval as stage_05
from backend.stages import stage_06_web_search as stage_06
from backend.stages import stage_07_context_assembly as stage_07
from backend.stages import stage_08_provider_gate as stage_08
from backend.stages import stage_09_llm_streaming as stage_09
from backend.stages import stage_10_response_delivery as stage_10
from shared.ws_spec import PipelineCompleteEvent, StageEvent, WSChatEvent

logger = logging.getLogger(__name__)


def _stage_event(stage: str, label: str, detail: str, status: str = "ok") -> StageEvent:
    """
    One line of "what PIP is doing", for a client to show while it waits.

    This is the same information trace.stage_log already records, sent live
    instead of only after the fact. The trace answers "what happened" once it
    has happened; a person watching a spinner is asking a different question,
    in the present tense, and nothing was answering it - stage_hint carries
    four booleans, arrives once as streaming STARTS, and the client buffers it
    until the answer is finished.

    Deliberately says when a stage found NOTHING (status "empty") rather than
    reporting only what succeeded. A retrieval that returns no chunks and a
    retrieval that was never run produce the same silence downstream, and the
    difference between them is the whole diagnosis when an answer is wrong.
    """
    return {"type": "stage", "data": {"stage": stage, "label": label, "detail": detail, "status": status}}


_DEFAULT_PROVIDER_ID = "ollama"
# From the settings block, like OllamaProvider's own default: qwen2.5:7b, the
# model every measured number is on (DEC-17, BLUEPRINT W-1). It was a literal
# "llama3.1:8b" here, one of three places that could each drift.
DEFAULT_MODEL_NAME = default_model_name()


def get_active_model_name(conn) -> str:
    """
    Reads the user's selected Ollama model from llm_settings (schema.sql),
    falling back to DEFAULT_MODEL_NAME if no row exists yet - a fresh DB, or
    an existing DB from before this table existed, both read as "use the
    default" rather than an error (schema.sql's CREATE TABLE IF NOT EXISTS
    means the table itself is always present once initialize_schema() has
    run, just possibly empty). Shared by _default_providers() below and
    server.py's Observer provider - ADR-033 requires Observer to use the same
    model as generation, so both read through this one function rather than
    each hardcoding their own default.
    """
    row = conn.execute("SELECT model_name FROM llm_settings WHERE id = 1").fetchone()
    return row["model_name"] if row else DEFAULT_MODEL_NAME


# Where the local model sits in the fallback order, so a configured endpoint
# can be placed either side of it. llm_endpoints.priority defaults to 100 -
# behind this - because adding an endpoint must never silently start sending a
# conversation off the machine. Someone who wants a cloud provider to lead has
# to say so, by giving it a lower number than this.
OLLAMA_PRIORITY = 50


def _default_providers(conn) -> list[BaseLLMProvider]:
    """
    The fallback chain: the local model (when reachable), plus every endpoint
    the user has configured and left enabled, in priority order.

    Stage 9 tries these in sequence and moves on when one is unreachable, so
    order is the whole of the policy here. Nothing in this function decides
    whether a provider is ALLOWED - _gate_providers does that next, and it
    fails closed - which is why an unconsented cloud endpoint can be built
    here without being used.

    A row that cannot be turned into a provider is skipped rather than raised
    on. One malformed endpoint should cost the user that endpoint, not the
    ability to hold a conversation, and the local model is usually still in
    the list behind it.

    Ollama is included unconditionally when it is reachable, or when no other
    provider is configured at all (so the error is "Ollama is unreachable",
    not a silent empty list). When it IS unreachable and alternatives exist,
    it is skipped entirely - saving Stage 9 the 2s TCP-timeout penalty that
    would otherwise hit every message.
    """
    ollama = OllamaProvider(model_name=get_active_model_name(conn))

    endpoints: list[tuple[int, BaseLLMProvider]] = []
    for row in llm_endpoint_store.list_endpoints(conn, enabled_only=True):
        try:
            endpoints.append((
                row["priority"],
                OpenAICompatibleProvider(
                    model_name=row["model_name"],
                    base_url=row["base_url"],
                    provider_id=row["provider_id"],
                    api_key=row["api_key"],
                    is_local=bool(row["is_local"]),
                    supports_response_format=bool(row["supports_response_format"]),
                ),
            ))
        except Exception as e:
            logger.warning(
                f"Pipeline: skipping endpoint '{row.get('provider_id')}' - {e}"
            )

    # Ollama: always included when reachable, or when it's the only option.
    # Skipped when unreachable AND the user has other providers configured,
    # so a down Ollama does not add a timeout to every message.
    if ollama.is_available() or not endpoints:
        endpoints.append((OLLAMA_PRIORITY, ollama))
    else:
        logger.info("Pipeline: Ollama unreachable, skipping (other providers configured)")

    # Sorted by priority only, and stably, so endpoints sharing a priority keep
    # the order list_endpoints already put them in rather than being reordered
    # by a tiebreak this function invented.
    endpoints.sort(key=lambda pair: pair[0])
    return [provider for _, provider in endpoints]


def _load_last_session_timestamp(conn):
    """
    When the previous session was last active - what Stage 0 measures the
    warm-start gap from.

    Read from profile_meta.previous_session_date, which begin_session() captures
    at the start of each session. It used to come from
    session_snapshot.snapshot_date, and that was wrong in one direction only but
    persistently: the Observer withholds a snapshot for a session with no
    substantive turn ("hi" / "thanks" / "bye"), so a run of thin sessions left
    the date frozen and the gap kept growing as though the user had been away
    the whole time. Ten short check-ins over a fortnight read as a fortnight of
    silence, and Stage 0 answered with a full warm start every time.

    Deliberately NOT profile_meta.last_session_date, which is the obvious
    candidate and is wrong: it is set on the first message of the CURRENT
    session, which happens before the pipeline runs, so reading it here would
    report a gap of zero on every message forever - warm start silently
    disabled rather than merely inaccurate.

    Falls back to snapshot_date while previous_session_date is still NULL, which
    is the case only until the first session on an upgraded database completes
    its migration backfill.
    """
    from datetime import datetime, timezone

    raw = None
    try:
        row = conn.execute("SELECT previous_session_date FROM profile_meta WHERE id = 1").fetchone()
        raw = row["previous_session_date"] if row else None
    except Exception as e:
        logger.warning(f"Pipeline: could not read previous_session_date: {e}")

    if not raw:
        snapshot = session_snapshot.load_snapshot(conn)
        raw = snapshot.get("snapshot_date") if snapshot else None
    if not raw:
        return None

    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception as e:
        logger.warning(f"Pipeline: failed to parse the previous session date, treating as first run: {e}")
        return None


def _today() -> date:
    """Today on this machine's clock: PIP runs on the user's own computer, so its local date is theirs."""
    return datetime.now().astimezone().date()


def _search_text(user_message: str, conversation_history: Optional[list[dict[str, str]]]) -> str:
    """
    What decisions and documents are searched with (#7): the previous user
    message and the whole current one. Stage 1's hint is the first 12 words
    of the current message only, so a follow-up ("and the other one?",
    "and why?") searched with words that say nothing about what it refers
    to. The web query does not use this: it stays the hint (DEC-14), so
    nothing from an earlier message is sent off the machine.
    """
    previous = next((m.get("content", "") for m in reversed(conversation_history or [])
                     if m.get("role") == "user"), "")
    return f"{previous} {user_message}".strip() if previous else user_message


def _gate_providers(conn, trace_id: str, providers: list[BaseLLMProvider]) -> list[BaseLLMProvider]:
    """Stage 8: only providers that pass consent make it into Stage 9's fallback list."""
    gated = []
    for provider in providers:
        model_info = provider.get_model_info()
        provider_id = model_info.get("provider_id", _DEFAULT_PROVIDER_ID)
        gate_started = time.perf_counter()
        try:
            # The provider's own claim, so the gate can check it against the
            # consent record (D-04). A provider that does not report one
            # counts as not local.
            stage_08.run(
                conn, provider_id, requested_scope="full_inference",
                provider_is_local=bool(model_info.get("is_local")),
            )
            gated.append(provider)
        except stage_08.ProviderConsentError as e:
            gate_duration_ms = int(round((time.perf_counter() - gate_started) * 1000))
            trace.stage_log(
                conn, trace_id, "stage_08_provider_gate", "error",
                f"{provider_id} blocked", error_detail=str(e), duration_ms=gate_duration_ms,
            )
            logger.warning(f"Pipeline: provider '{provider_id}' blocked by Stage 8: {e}")
    return gated


def run(
    conn,
    user_message: str,
    *,
    project_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    conversation_history: Optional[list[dict[str, str]]] = None,
    providers: Optional[list[BaseLLMProvider]] = None,
    max_tokens: int = 2000,
    timeout_seconds: int = 30,
    should_stop: Optional[Callable[[], bool]] = None,
    cache_generation: Optional[int] = None,
) -> Generator[Union[WSChatEvent, PipelineCompleteEvent], None, None]:
    """
    Runs Stages 0-10 for one user message. A generator: yields every Stage 9 event
    live (for a future WS handler to forward as-is), then yields exactly one final
    {"type": "pipeline_complete", "data": <Stage 10 result>} sentinel so callers
    that don't drive a raw generator-return-value dance can just watch for it while
    iterating normally.

    Each stage call is wrapped defensively even though every stage already fails
    open internally per its own spec - this is defense in depth against a stage
    raising something it wasn't supposed to, so one unexpected exception doesn't
    take down the whole pipeline. Falls back to that stage's documented empty/safe
    output and logs to trace_log rather than propagating.

    cache_generation names the signed-in session this question belongs to; the
    chat connection passes the one it captured when it opened. Without one it
    is taken now, as the question arrives - never later, at the cache write,
    by which time a sign-out may have ended the session (FREEZE_LIST §7.19).
    """
    if cache_generation is None:
        cache_generation = response_cache.generation()
    trace_id = trace.generate_trace_id()
    # The conversation already stores message text; a trace only needs enough
    # information to show which stages ran, not a second copy of the message.
    trace.stage_log(
        conn, trace_id, "pipeline", "ok",
        f"Starting pipeline for message ({len(user_message)} chars)",
        duration_ms=0,
    )

    # Stage 0
    t0 = time.perf_counter()
    try:
        last_session_dt = _load_last_session_timestamp(conn)
        gap_result = stage_00.run(last_session_dt)
    except Exception as e:
        logger.error(f"Pipeline: Stage 0 raised unexpectedly, failing open: {e}")
        gap_result = {"warm_start_level": "none", "context_depth_modifier": 0}
    dur_0 = int(round((time.perf_counter() - t0) * 1000))
    trace.stage_log(
        conn, trace_id, "stage_00_gap_detector", "ok",
        f"warm_start_level={gap_result['warm_start_level']}",
        duration_ms=dur_0,
    )

    # Stage 1
    t1 = time.perf_counter()
    try:
        intent_result = stage_01.run(user_message, gap_result["warm_start_level"], conn=conn)
    except Exception as e:
        logger.error(f"Pipeline: Stage 1 raised unexpectedly, failing open: {e}")
        intent_result = {"category": "general_knowledge", "skip_rag": False, "retrieval_hint": ""}
    dur_1 = int(round((time.perf_counter() - t1) * 1000))
    trace.stage_log(
        conn, trace_id, "stage_01_intent_classifier", "ok",
        f"category={intent_result['category']}",
        duration_ms=dur_1,
    )

    # Stage 2
    t2 = time.perf_counter()
    try:
        router_result = stage_02.run(
            intent_result["category"], intent_result["skip_rag"], intent_result["retrieval_hint"], gap_result["warm_start_level"]
        )
    except Exception as e:
        logger.error(f"Pipeline: Stage 2 raised unexpectedly, defaulting to LLM-only: {e}")
        router_result = {"retrieval_priority": [], "provider_preference": "local"}
    dur_2 = int(round((time.perf_counter() - t2) * 1000))
    trace.stage_log(
        conn, trace_id, "stage_02_router", "ok",
        f"priority={router_result['retrieval_priority']}",
        duration_ms=dur_2,
    )
    yield _stage_event(
        "intent",
        "Working out what you're asking",
        intent_result["category"].replace("_", " "),
    )

    # Response Cache (Part 7.1) - positioned here (between Stage 2 and Stage 7)
    # deliberately: a hit skips Stages 3-9 entirely, not just Stage 9's LLM call.
    # The record version prevents serving an answer after profile data changes.
    # If it cannot be read, skip cache both ways rather than risk stale output.
    tc = time.perf_counter()
    # The "where we left off" record this chat is given (BLUEPRINT #13): this
    # chat's own, else its project's latest, else the newest. Chosen here,
    # before the cache, because it is part of the answer's context: two chats
    # can now be given different records, so the key names which one.
    chat_record = session_snapshot.load_record_for(conn, conversation_id=conversation_id, project_id=project_id)
    context_key = f"chat_record:{chat_record['record_id']}" if chat_record else "chat_record:none"
    # The prompt names the day (#12), so an answer is cached for the day it was
    # built on and not replayed tomorrow.
    today = _today()
    context_key += f"|date:{today.isoformat()}"
    # Only a chat's first message is cached (#10): a follow-up ("why?") means
    # something only in its own chat, and its text alone said nothing about
    # which chat, so another chat's saved answer could come back for it.
    cache_allowed = not conversation_history
    # And, for a chat with no record of its own, the end of the previous chat
    # that its Observer pass has not summarised yet (#13 part 3). Messages do
    # not move the record version (they are written every turn), so the key
    # names the last one shown.
    unsummarised = None
    if not chat_record or chat_record["record_scope"] != session_snapshot.SCOPE_THIS_CHAT:
        try:
            unsummarised = conversation_store.unsummarised_tail(conn, exclude=conversation_id, project_id=project_id)
        except Exception as e:
            logger.error(f"Pipeline: could not read the previous chat's unsummarised end, leaving it out: {e}")
    if unsummarised:
        context_key += f"|unsummarised:{unsummarised['last_message_id']}"
    try:
        record_version = profile_store.record_version(conn)
    except Exception as e:
        logger.error(f"Pipeline: could not read the record version, bypassing the cache: {e}")
        record_version = None
    try:
        active_model_name = get_active_model_name(conn)
    except Exception as e:
        logger.error(f"Pipeline: could not read the active model, bypassing the cache: {e}")
        active_model_name = None
    cached = (
        response_cache.get(
            user_message, project_id, record_version,
            generation=cache_generation, model_name=active_model_name, context_key=context_key,
        )
        if record_version is not None and active_model_name is not None and cache_allowed
        else None
    )
    dur_c = int(round((time.perf_counter() - tc) * 1000))
    if cached is not None:
        trace.stage_log(
            conn, trace_id, "response_cache", "ok",
            "cache hit, skipping Stages 3-9",
            duration_ms=dur_c,
        )
        cache_hint = dict(cached["stage_hints"])
        cache_hint["cache_hit"] = True
        # Reuse must be visible: a cached answer can look like a fast new one,
        # but Stages 3-9 did not run for this turn.
        yield _stage_event("cache", "Answered this before", "reusing the saved response")
        yield {"type": "stage_hint", "data": cache_hint}
        yield {"type": "token", "data": cached["response_text"]}
        yield {"type": "done", "data": None}
        result = stage_10.run(
            trace_id,
            {"response_text": cached["response_text"], "status": "success", "error": None, "stage_hints": cache_hint},
            conn,
        )
        yield {"type": "pipeline_complete", "data": result}
        return
    trace.stage_log(
        conn, trace_id, "response_cache", "ok",
        "cache miss",
        duration_ms=dur_c,
    )

    # Stages 3/4/5/6 - sequential here; see module docstring on parallelization.
    t3 = time.perf_counter()
    try:
        decision_entries = stage_03.run(conn, _search_text(user_message, conversation_history), project_id)
    except Exception as e:
        logger.error(f"Pipeline: Stage 3 raised unexpectedly, returning empty: {e}")
        decision_entries = []
    dur_3 = int(round((time.perf_counter() - t3) * 1000))
    trace.stage_log(
        conn, trace_id, "stage_03_decision_log_lookup", "ok",
        f"{len(decision_entries)} entries",
        duration_ms=dur_3,
    )
    yield _stage_event(
        "decisions",
        "Checking your decisions",
        f"{len(decision_entries)} recorded" if decision_entries else "nothing on this",
        "ok" if decision_entries else "empty",
    )

    t4 = time.perf_counter()
    try:
        profile_fields = stage_04.run(conn, intent_result["category"], intent_result["retrieval_hint"])
    except Exception as e:
        logger.error(f"Pipeline: Stage 4 raised unexpectedly, returning empty: {e}")
        profile_fields = []
    dur_4 = int(round((time.perf_counter() - t4) * 1000))
    trace.stage_log(
        conn, trace_id, "stage_04_memory_lookup", "ok",
        f"{len(profile_fields)} fields",
        duration_ms=dur_4,
    )
    yield _stage_event(
        "profile",
        "Reading what it knows about you",
        f"{len(profile_fields)} detail{'s' if len(profile_fields) != 1 else ''}"
        if profile_fields
        else "nothing relevant",
        "ok" if profile_fields else "empty",
    )

    t5 = time.perf_counter()
    try:
        # ADR-002: Stage 5 always runs, even when skip_rag is set. Its safety
        # check is broader than the lightweight intent pre-check.
        rag_result = stage_05.run(conn, _search_text(user_message, conversation_history), project_id)
    except Exception as e:
        logger.error(f"Pipeline: Stage 5 raised unexpectedly, returning empty: {e}")
        rag_result = {"chunks": [], "conflict_flag": False}
    dur_5 = int(round((time.perf_counter() - t5) * 1000))
    trace.stage_log(
        conn, trace_id, "stage_05_rag_retrieval", "ok",
        f"{len(rag_result['chunks'])} chunks, conflict={rag_result['conflict_flag']}",
        duration_ms=dur_5,
    )
    _chunks = rag_result["chunks"]
    _files = {c.get("file_path") for c in _chunks if c.get("file_path")}
    # An empty retrieval must be visible; otherwise a missing index looks like
    # an ordinary question with no matching document.
    yield _stage_event(
        "documents",
        "Searching your documents",
        (
            f"{len(_chunks)} passage{'s' if len(_chunks) != 1 else ''} "
            f"from {len(_files)} document{'s' if len(_files) != 1 else ''}"
        )
        if _chunks
        else "nothing close enough",
        "ok" if _chunks else "empty",
    )

    t6 = time.perf_counter()
    # Web search is external, so Stage 8 must approve its scope before Stage 6
    # sends a query. Report that query only after the gate passes.
    web_results: list[dict[str, Any]] = []
    search_query: str | None = None
    try:
        no_search_categories = {
            "personal_question",
            "project_question",
            "project_continuation",
        }
        if (
            stage_06.matches_trigger(user_message)
            and intent_result["category"] not in no_search_categories
        ):
            web_gate_started = time.perf_counter()
            try:
                stage_08.run(
                    conn, "web_search", requested_scope="web_search_only", provider_is_local=False
                )
            except stage_08.ProviderConsentError as e:
                gate_duration_ms = int(round((time.perf_counter() - web_gate_started) * 1000))
                trace.stage_log(
                    conn, trace_id, "stage_08_provider_gate", "error",
                    "web_search blocked", error_detail=str(e), duration_ms=gate_duration_ms,
                )
                logger.warning(f"Pipeline: web_search blocked by Stage 8: {e}")
            else:
                search_query = intent_result["retrieval_hint"] or user_message
                web_results = stage_06.run(search_query)
    except Exception as e:
        logger.error(f"Pipeline: Stage 6 raised unexpectedly, returning empty: {e}")
    dur_6 = int(round((time.perf_counter() - t6) * 1000))
    trace.stage_log(
        conn, trace_id, "stage_06_web_search", "ok",
        f"{len(web_results)} results",
        duration_ms=dur_6,
    )
    # Report the exact query whenever it was sent, including when the search
    # returned no results, so the user can see what left the machine.
    if search_query is not None:
        yield _stage_event(
            "web",
            "Searching the web",
            f"query sent: {search_query!r}",
            "ok" if web_results else "empty",
        )

    # Stage 7
    t7 = time.perf_counter()
    try:
        assembled = stage_07.run(
            user_message,
            profile_fields=profile_fields,
            session_snapshot={**(chat_record or {}), "unsummarised": unsummarised} if unsummarised else chat_record,
            decision_log_entries=decision_entries,
            rag_chunks=rag_result["chunks"],
            web_results=web_results,
            conversation_history=conversation_history,
            context_depth_modifier=gap_result.get("context_depth_modifier", 2),
            category=intent_result["category"],
            today=today,
        )
    except Exception as e:
        logger.error(f"Pipeline: Stage 7 raised unexpectedly, falling back to minimal prompt: {e}")
        assembled = {"context": "", "messages": [{"role": "user", "content": user_message}]}
    dur_7 = int(round((time.perf_counter() - t7) * 1000))
    trace.stage_log(
        conn, trace_id, "stage_07_context_assembly", "ok",
        "context assembled",
        duration_ms=dur_7,
    )

    # Stage 8
    t8 = time.perf_counter()
    gated_providers = _gate_providers(conn, trace_id, providers or _default_providers(conn))
    dur_8 = int(round((time.perf_counter() - t8) * 1000))
    if not gated_providers:
        trace.stage_log(
            conn, trace_id, "stage_08_provider_gate", "error",
            "no consented providers available",
            duration_ms=dur_8,
        )
        no_provider = "No consented provider available"
        # The final pipeline result is internal to the server. Send a terminal
        # error event so the WebSocket client does not remain in writing state.
        yield {"type": "error", "data": no_provider}
        result = stage_10.run(
            trace_id,
            {"response_text": "", "status": "error", "error": no_provider, "stage_hints": {}},
            conn,
        )
        yield {"type": "pipeline_complete", "data": result}
        return

    # Before the call, not after: everything above is milliseconds of local
    # lookups and this is the part somebody actually waits through, so it has
    # to be on screen while it happens rather than announced once it is over.
    provider_info = gated_providers[0].get_model_info()
    writing_detail = (
        f"{provider_info.get('provider_id', 'unknown')} / "
        f"{provider_info.get('model_name', 'unknown')}"
    )
    yield _stage_event("writing", "Writing", writing_detail)

    # Stage 9 - streamed live to the caller.
    t9 = time.perf_counter()
    ttft_ms = None
    events = stage_09.run(
        assembled["context"],
        assembled["messages"],
        gated_providers,
        decision_log_hit=bool(decision_entries),
        web_search_used=bool(web_results),
        cache_hit=False,  # reaching here means the cache check above missed
        model_loading=False,  # no reliable warm/cold signal exists on the provider API
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        should_stop=should_stop,
    )

    # Fold live events through Stage 9's shared accumulator so this streamed
    # path and collect() use the same terminal status and response text.
    aggregate = stage_09.new_aggregate()
    for event in events:
        if ttft_ms is None and event.get("type") == "token":
            ttft_ms = int(round((time.perf_counter() - t9) * 1000))
        yield event
        stage_09.accumulate(aggregate, event)

    dur_9 = int(round((time.perf_counter() - t9) * 1000))
    status = aggregate["status"]
    ttft_detail = f", ttft_ms={ttft_ms}" if ttft_ms is not None else ""
    trace.stage_log(
        conn, trace_id, "stage_09_llm_streaming",
        "error" if status == "error" else "ok",
        f"status={status}{ttft_detail}{window_detail(gated_providers)}",
        error_detail=aggregate["error"] or "",
        duration_ms=dur_9,
    )

    if status == "success" and record_version is not None and active_model_name is not None and cache_allowed:
        response_cache.set(
            user_message, project_id, intent_result["category"],
            aggregate["response_text"], aggregate["stage_hints"],
            decision_log_hit=bool(decision_entries),
            record_version=record_version,
            generation=cache_generation,
            model_name=active_model_name,
            context_key=context_key,
        )

    # Stage 10
    result = stage_10.run(trace_id, aggregate, conn)
    yield {"type": "pipeline_complete", "data": result}


def run_sync(conn, user_message: str, **kwargs) -> dict[str, Any]:
    """
    Drains run() and returns just the final Stage 10 result - for callers that
    don't need live token-by-token forwarding (tests, a CLI, a future non-streaming
    REST fallback). A live WS caller should iterate run() directly instead.
    """
    for event in run(conn, user_message, **kwargs):
        if event["type"] == "pipeline_complete":
            return event["data"]
    raise RuntimeError("pipeline.run() ended without yielding pipeline_complete")
