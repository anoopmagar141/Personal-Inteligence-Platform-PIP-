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
from typing import Any, Callable, Generator, Optional, Union

from backend.core import response_cache, trace
from backend.memory import session_snapshot
from backend.providers.base_provider import BaseLLMProvider
from backend.providers.ollama_provider import OllamaProvider
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
from shared.ws_spec import PipelineCompleteEvent, WSChatEvent

logger = logging.getLogger(__name__)

_DEFAULT_PROVIDER_ID = "ollama"
DEFAULT_MODEL_NAME = "llama3.1:8b"


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


def _default_providers(conn) -> list[BaseLLMProvider]:
    return [OllamaProvider(model_name=get_active_model_name(conn))]


def _load_last_session_timestamp(conn):
    from datetime import datetime, timezone

    snapshot = session_snapshot.load_snapshot(conn)
    if not snapshot or not snapshot.get("snapshot_date"):
        return None
    try:
        dt = datetime.fromisoformat(snapshot["snapshot_date"].replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception as e:
        logger.warning(f"Pipeline: failed to parse session_snapshot.snapshot_date, treating as first run: {e}")
        return None


def _gate_providers(conn, trace_id: str, providers: list[BaseLLMProvider]) -> list[BaseLLMProvider]:
    """Stage 8: only providers that pass consent make it into Stage 9's fallback list."""
    gated = []
    for provider in providers:
        provider_id = provider.get_model_info().get("provider_id", _DEFAULT_PROVIDER_ID)
        try:
            stage_08.run(conn, provider_id, requested_scope="full_inference")
            gated.append(provider)
        except stage_08.ProviderConsentError as e:
            trace.stage_log(conn, trace_id, "stage_08_provider_gate", "error", f"{provider_id} blocked", error_detail=str(e))
            logger.warning(f"Pipeline: provider '{provider_id}' blocked by Stage 8: {e}")
    return gated


def run(
    conn,
    user_message: str,
    *,
    project_id: Optional[str] = None,
    conversation_history: Optional[list[dict[str, str]]] = None,
    providers: Optional[list[BaseLLMProvider]] = None,
    max_tokens: int = 2000,
    timeout_seconds: int = 30,
    should_stop: Optional[Callable[[], bool]] = None,
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
    """
    trace_id = trace.generate_trace_id()
    # Logs the message's LENGTH, never its text.
    #
    # That began as a security fix. The trace used to carry the first 80 chars
    # of the raw message, and it was written to backend/logs/trace_log.json - a
    # plain file on disk, outside the SQLCipher boundary the rest of
    # "structured data" gets - so names and anything else typed sat there in
    # plaintext.
    #
    # That reason no longer holds: the trace lives in the encrypted database
    # now (see core/trace.py), and the file is gone. Message text could be
    # recorded here safely, so what remains is a choice rather than a
    # constraint - a trace is read to find out which stages ran and what each
    # retrieved, and a length answers that without keeping a second copy of
    # every message the conversations/messages tables already hold.
    trace.stage_log(conn, trace_id, "pipeline", "ok", f"Starting pipeline for message ({len(user_message)} chars)")

    # Stage 0
    try:
        last_session_dt = _load_last_session_timestamp(conn)
        gap_result = stage_00.run(last_session_dt)
    except Exception as e:
        logger.error(f"Pipeline: Stage 0 raised unexpectedly, failing open: {e}")
        gap_result = {"warm_start_level": "none", "context_depth_modifier": 0}
    trace.stage_log(conn, trace_id, "stage_00_gap_detector", "ok", f"warm_start_level={gap_result['warm_start_level']}")

    # Stage 1
    try:
        intent_result = stage_01.run(user_message, gap_result["warm_start_level"], conn=conn)
    except Exception as e:
        logger.error(f"Pipeline: Stage 1 raised unexpectedly, failing open: {e}")
        intent_result = {"category": "general_knowledge", "skip_rag": False, "retrieval_hint": ""}
    trace.stage_log(conn, trace_id, "stage_01_intent_classifier", "ok", f"category={intent_result['category']}")

    # Stage 2
    try:
        router_result = stage_02.run(
            intent_result["category"], intent_result["skip_rag"], intent_result["retrieval_hint"], gap_result["warm_start_level"]
        )
    except Exception as e:
        logger.error(f"Pipeline: Stage 2 raised unexpectedly, defaulting to LLM-only: {e}")
        router_result = {"retrieval_priority": [], "provider_preference": "local"}
    trace.stage_log(conn, trace_id, "stage_02_router", "ok", f"priority={router_result['retrieval_priority']}")

    # Response Cache (Part 7.1) - positioned here (between Stage 2 and Stage 7)
    # deliberately: a hit skips Stages 3-9 entirely, not just Stage 9's LLM call.
    cached = response_cache.get(user_message, project_id)
    if cached is not None:
        trace.stage_log(conn, trace_id, "response_cache", "ok", "cache hit, skipping Stages 3-9")
        cache_hint = dict(cached["stage_hints"])
        cache_hint["cache_hit"] = True
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
    trace.stage_log(conn, trace_id, "response_cache", "ok", "cache miss")

    # Stages 3/4/5/6 - sequential here; see module docstring on parallelization.
    try:
        decision_entries = stage_03.run(conn, intent_result["retrieval_hint"], project_id)
    except Exception as e:
        logger.error(f"Pipeline: Stage 3 raised unexpectedly, returning empty: {e}")
        decision_entries = []
    trace.stage_log(conn, trace_id, "stage_03_decision_log_lookup", "ok", f"{len(decision_entries)} entries")

    try:
        profile_fields = stage_04.run(conn, intent_result["category"], intent_result["retrieval_hint"])
    except Exception as e:
        logger.error(f"Pipeline: Stage 4 raised unexpectedly, returning empty: {e}")
        profile_fields = []
    trace.stage_log(conn, trace_id, "stage_04_memory_lookup", "ok", f"{len(profile_fields)} fields")

    try:
        # ADR-002: Stage 5 always runs regardless of skip_rag - the Mechanism 2
        # safety net this satisfies is a superset of a lightweight pre-check, not a
        # separate code path (see stage_05's own module docstring).
        rag_result = stage_05.run(conn, intent_result["retrieval_hint"], project_id)
    except Exception as e:
        logger.error(f"Pipeline: Stage 5 raised unexpectedly, returning empty: {e}")
        rag_result = {"chunks": [], "conflict_flag": False}
    trace.stage_log(conn, trace_id, "stage_05_rag_retrieval", "ok", f"{len(rag_result['chunks'])} chunks, conflict={rag_result['conflict_flag']}")

    # Security fix: Stage 6 used to fire on trigger-keyword match alone, with no
    # consent check at all - the ONLY gate ever applied was to the LLM provider
    # list below (Stage 8 -> Stage 9), never to web_search. config/provider_consent.json
    # documents "ADR-030: hard_stop gate at Stage 8" for web_search right in its
    # seed comment - the code didn't do it. Default seed state is
    # user_consented=0, so this fired for real, off a fresh install, before
    # anyone had granted anything, and revoking consent had zero effect on
    # whether searches actually happened. Fail-closed, same pattern as
    # _gate_providers: a blocked/missing consent record means no search fires,
    # not a degraded one.
    web_results: list[dict[str, Any]] = []
    try:
        if stage_06.matches_trigger(user_message):
            try:
                stage_08.run(conn, "web_search", requested_scope="web_search_only")
            except stage_08.ProviderConsentError as e:
                trace.stage_log(conn, trace_id, "stage_08_provider_gate", "error", "web_search blocked", error_detail=str(e))
                logger.warning(f"Pipeline: web_search blocked by Stage 8: {e}")
            else:
                web_results = stage_06.run(intent_result["retrieval_hint"] or user_message)
    except Exception as e:
        logger.error(f"Pipeline: Stage 6 raised unexpectedly, returning empty: {e}")
    trace.stage_log(conn, trace_id, "stage_06_web_search", "ok", f"{len(web_results)} results")

    # Stage 7
    try:
        snapshot = session_snapshot.load_snapshot(conn)
        assembled = stage_07.run(
            user_message,
            profile_fields=profile_fields,
            session_snapshot=snapshot,
            decision_log_entries=decision_entries,
            rag_chunks=rag_result["chunks"],
            web_results=web_results,
            conversation_history=conversation_history,
            context_depth_modifier=gap_result.get("context_depth_modifier", 2),
            category=intent_result["category"],
        )
    except Exception as e:
        logger.error(f"Pipeline: Stage 7 raised unexpectedly, falling back to minimal prompt: {e}")
        assembled = {"context": "", "messages": [{"role": "user", "content": user_message}]}
    trace.stage_log(conn, trace_id, "stage_07_context_assembly", "ok", "context assembled")

    # Stage 8
    gated_providers = _gate_providers(conn, trace_id, providers or _default_providers(conn))
    if not gated_providers:
        trace.stage_log(conn, trace_id, "stage_08_provider_gate", "error", "no consented providers available")
        result = stage_10.run(
            trace_id,
            {"response_text": "", "status": "error", "error": "No consented provider available", "stage_hints": {}},
            conn,
        )
        yield {"type": "pipeline_complete", "data": result}
        return

    # Stage 9 - streamed live to the caller.
    events = stage_09.run(
        assembled["context"],
        assembled["messages"],
        gated_providers,
        decision_log_hit=bool(decision_entries),
        web_search_used=bool(web_results),
        cache_hit=False,  # reaching here means the cache check above already missed
        model_loading=False,  # no reliable warm/cold detection without extending BaseLLMProvider
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
        should_stop=should_stop,
    )

    response_text = ""
    status = "error"
    error: Optional[str] = None
    stage_hints: dict[str, Any] = {}
    for event in events:
        yield event
        if event["type"] == "stage_hint":
            stage_hints = event["data"]
        elif event["type"] == "token":
            response_text += event["data"]
        elif event["type"] == "done":
            status = "success"
        elif event["type"] == "error":
            status = "error"
            error = event["data"]
        elif event["type"] == "stopped":
            status = "stopped"

    trace.stage_log(conn, trace_id, "stage_09_llm_streaming", "error" if status == "error" else "ok", f"status={status}", error_detail=error or "")

    if status == "success":
        response_cache.set(
            user_message, project_id, intent_result["category"], response_text, stage_hints,
            decision_log_hit=bool(decision_entries),
        )

    # Stage 10
    result = stage_10.run(
        trace_id,
        {"response_text": response_text, "status": status, "error": error, "stage_hints": stage_hints},
        conn,
    )
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
