import asyncio
import contextlib
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Optional, Union

from backend.config.settings import get_settings
from backend.core import (
    auth,
    instance_lock,
    pinned_executor,
    pipeline,
    proactive,
    session_lifecycle,
    startup_progress,
    trace,
)
from backend.memory import (
    conversation_store,
    decision_log,
    profile_store,
    vector_store,
    verification,
)
from backend.providers.ollama_provider import OllamaProvider
from backend.stages import stage_08_provider_gate as provider_gate
from backend.stages import stage_13_profile_update as stage_13
from backend.stages.stage_08_provider_gate import ProviderConsentError
from shared.ws_spec import ChatRequest, PipelineCompleteEvent, WSChatEvent

logger = logging.getLogger(__name__)


BASE_PREFIX = "/api/v1"
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "pip.db"

VALID_CONSENT_SCOPES = {"full_inference", "web_search_only", "embedding_only", "none"}

# Shared by CORSMiddleware (REST) and ws_chat()'s own manual check (WS upgrades
# never go through CORSMiddleware at all - it's HTTP-only in Starlette).
# Anchored with a trailing $: both consumers match this against the start of
# the Origin string (CORSMiddleware's allow_origin_regex and the manual
# .match() call below), so without the anchor "http://localhost.attacker.tld"
# would satisfy the prefix and be treated as a trusted local origin.
_ALLOWED_ORIGIN_RE = re.compile(r"http://(localhost|127\.0\.0\.1)(:\d+)?$")


# Security fix: the API token was being written to disk in plaintext by
# uvicorn's access log. Browsers cannot set headers on a WebSocket handshake,
# so /ws/chat takes the token as a query parameter (see ws_chat) - and uvicorn
# logs the full request path, producing lines like:
#
#   "WebSocket /ws/chat?token=ae4fda2629...b6f4" [accepted]
#
# in data/backend.err.log. auth.py states the token file is "the only place
# this value is meant to be read from", and ws_chat's own origin check exists
# to limit the damage of "a leaked token (logs, shoulder-surfed URL, browser
# history)" - the code named this exact threat and then produced it.
#
# The severity is not that a local attacker gains anything (api_token.txt is
# already readable by anything running as this user) but that LOGS TRAVEL: they
# get pasted into bug reports, forums and submissions, in a way a file called
# api_token.txt never does. One of those lines hands over full API access to
# the contents of an otherwise-encrypted database.
#
# Redaction rather than --no-access-log: knowing which requests arrived is
# genuinely useful for debugging, and the connection log is how this was found
# in the first place. Applied to record.args as well as record.msg because
# uvicorn logs with lazy %-formatting - the path arrives as an argument, and a
# filter that only rewrote record.msg would leave the token untouched in every
# real access-log line.
_TOKEN_IN_QUERY_RE = re.compile(r"(token=)[^&\s\"'\\]+", re.IGNORECASE)


def _redact(value: Any) -> Any:
    if isinstance(value, str):
        return _TOKEN_IN_QUERY_RE.sub(r"\1[REDACTED]", value)
    return value


class RedactTokenFilter(logging.Filter):
    """Strips `token=...` query values out of log records. Never drops a record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_redact(a) for a in record.args)
        elif isinstance(record.args, dict):
            record.args = {k: _redact(v) for k, v in record.args.items()}
        return True


def install_log_redaction() -> None:
    """
    Attaches RedactTokenFilter to the loggers that can carry a request URL.

    Called from the lifespan startup rather than at import: uvicorn configures
    its own logging when it starts, and a filter attached before that can be
    discarded by the reconfiguration. By the time lifespan runs, uvicorn's
    loggers exist and are final - and the first WebSocket connection, which is
    what actually carries the token, cannot have happened yet.

    Idempotent, since the lifespan runs once per TestClient in the test suite.
    """
    for name in ("uvicorn.access", "uvicorn.error", "uvicorn", ""):
        logger_obj = logging.getLogger(name)
        if not any(isinstance(f, RedactTokenFilter) for f in logger_obj.filters):
            logger_obj.addFilter(RedactTokenFilter())
        # A filter on a logger only runs for records logged directly to it, not
        # for records propagating up from children - so the handlers get one
        # too, which is what actually catches uvicorn.access's output.
        for handler in logger_obj.handlers:
            if not any(isinstance(f, RedactTokenFilter) for f in handler.filters):
                handler.addFilter(RedactTokenFilter())


def open_app_connection(db_path: str | None = None, db_key: str | None = None):
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = profile_store.get_connection(str(path), db_key)
    profile_store.initialize_schema(conn)
    return conn


def api_status(conn) -> dict[str, Any]:
    meta = conn.execute("SELECT * FROM profile_meta WHERE id = 1").fetchone()
    decision_count = conn.execute("SELECT COUNT(*) FROM decision_log WHERE state = 'active'").fetchone()[0]
    pending_count = conn.execute(
        "SELECT COUNT(*) FROM decision_candidates_pending WHERE state = 'pending'"
    ).fetchone()[0]
    # Memory candidates the constitution requires a user decision on. Reported
    # alongside pending_decisions so a client can badge both from one call -
    # without it, the only way to discover there is memory waiting on you is to
    # already know the endpoint exists and poll it.
    pending_memory_count = conn.execute(
        "SELECT COUNT(*) FROM memory_candidates_pending WHERE state = 'pending'"
    ).fetchone()[0]
    return {
        "status": "ok",
        "onboarding_complete": bool(meta["onboarding_complete"]) if meta else False,
        # Exposed so the counter is observable rather than only inferable from
        # its effects - and because the memory verification loop, when it is
        # built, needs to know where in the 30-session cycle it is.
        "session_count": meta["session_count"] if meta else 0,
        "last_session_date": meta["last_session_date"] if meta else None,
        "active_decisions": decision_count,
        "pending_decisions": pending_count,
        "pending_memory": pending_memory_count,
    }


def api_complete_onboarding(conn, payload: dict[str, Any]) -> dict[str, Any]:
    message = profile_store.complete_onboarding(
        conn,
        name=payload["name"],
        language_preference=payload["language_preference"],
        timezone=payload.get("timezone"),
        current_project=payload.get("current_project"),
        skills=payload.get("skills"),
        interaction_style=payload.get("interaction_style"),
        preferred_tools=payload.get("preferred_tools"),
    )
    return {"message": message}


def api_get_profile(conn) -> list[dict[str, Any]]:
    return profile_store.get_profile(conn)


def api_get_profile_field(conn, field: str) -> dict[str, Any] | None:
    return profile_store.get_profile_field(conn, field)


def api_correct_memory(conn, payload: dict[str, Any]) -> dict[str, str]:
    profile_store.correct_profile_field(conn, payload["field"], payload["value"])
    return {"status": "updated"}


def api_delete_profile_field(conn, field: str) -> dict[str, Any]:
    deleted = profile_store.soft_delete_profile_field(conn, field)
    return {"status": "deleted" if deleted else "not_found", "field": field}


def api_get_interaction_style_history(conn, limit: int = 50) -> list[dict[str, Any]]:
    return profile_store.get_interaction_style_history(conn, limit=limit)


def api_get_pending_memory(conn):
    return stage_13.list_pending(conn)


def api_confirm_pending_memory(conn, candidate_id: int):
    return stage_13.resolve_pending(conn, candidate_id)


def api_dismiss_pending_memory(conn, candidate_id: int):
    return stage_13.dismiss_pending(conn, candidate_id)


def api_create_decision(conn, payload: dict[str, Any]) -> dict[str, Any]:
    return decision_log.create_decision(
        conn,
        text=payload["text"],
        reasoning=payload.get("reasoning"),
        alternatives=payload.get("alternatives"),
        project_id=payload.get("project_id"),
    )


def api_search_decisions(conn, q: str = "", state: str = "active", project_id: str | None = None):
    if q:
        return decision_log.search_decisions(conn, query=q, state=state, project_id=project_id)
    return decision_log.list_decisions(conn, state=state, project_id=project_id)


def api_update_decision_state(conn, decision_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    decision_log.update_decision_state(
        conn,
        decision_id,
        state=payload["state"],
        reason=payload["reason"],
        superseded_by=payload.get("superseded_by"),
    )
    return {"status": "updated", "decision_id": decision_id}


def api_get_pending(conn):
    return decision_log.list_pending(conn)


def api_promote_pending(conn, candidate_id: int):
    return decision_log.promote_pending(conn, candidate_id)


def api_dismiss_pending(conn, candidate_id: int):
    return decision_log.dismiss_pending(conn, candidate_id)


def api_list_projects(conn):
    return profile_store.list_projects(conn)


def api_create_project(conn, payload: dict[str, Any]):
    project_id = profile_store.create_project(
        conn,
        payload["name"],
        payload.get("description", ""),
    )
    return {"project_id": project_id}


def api_update_project_status(conn, project_id: str, payload: dict[str, Any]):
    profile_store.update_project_status(conn, project_id, payload["status"])
    return {"status": "updated", "project_id": project_id}


def api_activate_project(conn, project_id: str):
    profile_store.activate_project(conn, project_id)
    return {"status": "active", "project_id": project_id}


def api_list_providers(conn) -> list[dict[str, Any]]:
    """Return all rows from provider_consent.

    is_cloud/user_consented/revoked are stored as SQLite INTEGER (0/1) - SQLite
    has no native boolean type - so they come back from the driver as Python
    int, not bool. dict(row) alone would ship raw 0/1 over the wire as JSON
    numbers, not JSON booleans. config/provider_consent.json's own test suite
    (test_provider_consent.py) documents "is_cloud is a native JSON boolean in
    all rows" as a locked contract, but only validates the seed file itself,
    never this actual API response - the two silently diverged. Found live via
    the Flutter client: JS's truthy coercion let app.js's `is_cloud ? 'cloud'
    : 'local'` paper over the int/bool difference, but Dart's strict `== true`
    correctly does not, which is what surfaced this. Coercing here fixes the
    contract for every client, not just the strict one that happened to catch it.
    """
    rows = conn.execute(
        "SELECT provider_id, is_cloud, user_consented, consent_scope, revoked "
        "FROM provider_consent ORDER BY provider_id"
    ).fetchall()
    result = []
    for r in rows:
        row = dict(r)
        row["is_cloud"] = bool(row["is_cloud"])
        row["user_consented"] = bool(row["user_consented"])
        row["revoked"] = bool(row["revoked"])
        result.append(row)
    return result


def api_grant_consent(conn, provider_id: str, consent_scope: str) -> dict[str, Any]:
    """Grant consent to a cloud provider.

    Raises ValueError for:
      - consent_scope not in the valid enum (validated before any DB write)
      - unknown provider_id (no row in provider_consent)

    Only updates user_consented, consent_scope, revoked, consent_date.
    Never touches is_cloud.
    """
    if consent_scope not in VALID_CONSENT_SCOPES:
        raise ValueError(
            f"Invalid consent_scope '{consent_scope}'. "
            f"Must be one of: {sorted(VALID_CONSENT_SCOPES)}"
        )
    row = conn.execute(
        "SELECT provider_id FROM provider_consent WHERE provider_id = ?",
        (provider_id,),
    ).fetchone()
    if row is None:
        raise ValueError(
            f"Unknown provider '{provider_id}'. "
            "Add it to config/provider_consent.json and re-run the migration script."
        )
    conn.execute(
        """
        UPDATE provider_consent
           SET user_consented = 1,
               consent_scope  = ?,
               revoked        = 0,
               consent_date   = datetime('now')
         WHERE provider_id = ?
        """,
        (consent_scope, provider_id),
    )
    conn.commit()
    return {"status": "consented", "provider_id": provider_id, "consent_scope": consent_scope}


def api_revoke_consent(conn, provider_id: str) -> dict[str, Any]:
    """Revoke previously granted consent for a provider.

    Only updates revoked and revoked_date. Never touches is_cloud.
    """
    row = conn.execute(
        "SELECT provider_id FROM provider_consent WHERE provider_id = ?",
        (provider_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown provider '{provider_id}'.")
    conn.execute(
        """
        UPDATE provider_consent
           SET revoked      = 1,
               revoked_date = datetime('now')
         WHERE provider_id = ?
        """,
        (provider_id,),
    )
    conn.commit()
    return {"status": "revoked", "provider_id": provider_id}


def api_list_llm_models() -> dict[str, Any]:
    """
    Every model Ollama has locally pulled - what a model picker shows to
    choose from. Fails open with an empty list rather than a 500 when Ollama
    is unreachable (e.g. not started yet): the picker screen should still
    render, just with nothing to pick, not crash the whole request.
    """
    from backend.providers.ollama_provider import list_models

    try:
        models = list_models()
    except Exception as e:
        return {"models": [], "error": str(e)}
    return {"models": [{"name": m.get("name"), "size": m.get("size")} for m in models]}


def api_get_active_model(conn) -> dict[str, Any]:
    return {"model_name": pipeline.get_active_model_name(conn)}


def api_set_active_model(conn, payload: dict[str, Any]) -> dict[str, Any]:
    model_name = payload.get("model_name")
    if not model_name:
        raise ValueError("model_name is required")

    # Validated against what Ollama actually has pulled - but only when
    # Ollama answers at all. If it's unreachable right now, the choice is
    # still saved (fails open, same reasoning as api_list_llm_models above) -
    # an unreachable Ollama shouldn't block picking a model for when it's
    # back up, it just can't confirm the name is real yet.
    from backend.providers.ollama_provider import list_models

    try:
        available = {m.get("name") for m in list_models()}
    except Exception:
        available = None
    if available is not None and model_name not in available:
        raise ValueError(f"'{model_name}' isn't pulled in Ollama yet - run `ollama pull {model_name}` first.")

    conn.execute(
        """
        INSERT INTO llm_settings (id, model_name) VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET model_name = excluded.model_name
        """,
        (model_name,),
    )
    conn.commit()
    return {"status": "updated", "model_name": model_name}


def api_list_conversations(conn, project_id: Optional[str] = None) -> list[dict[str, Any]]:
    return conversation_store.list_conversations(conn, project_id=project_id)


def api_get_conversation_messages(conn, conversation_id: str) -> list[dict[str, Any]]:
    if not conversation_store.conversation_exists(conn, conversation_id):
        raise ValueError(f"Unknown conversation '{conversation_id}'.")
    return conversation_store.get_messages(conn, conversation_id)


def api_create_conversation(conn, payload: dict[str, Any]) -> dict[str, Any]:
    conversation_id = conversation_store.create_conversation(conn, project_id=payload.get("project_id"))
    return {"id": conversation_id, "title": "New chat"}


def api_delete_conversation(conn, conversation_id: str) -> dict[str, Any]:
    deleted = conversation_store.delete_conversation(conn, conversation_id)
    if not deleted:
        raise ValueError(f"Unknown conversation '{conversation_id}'.")
    return {"status": "deleted", "id": conversation_id}


def _resolve_connection_state(conn, conversation_id: Optional[str]) -> tuple[str, Optional[str], str, list[dict[str, str]]]:
    """
    Everything ws_chat() needs to know from the DB before it can start
    handling turns, resolved in ONE executor round-trip rather than two
    separate run_in_executor calls - fewer thread hops regardless, but also
    found live while chasing an unrelated disconnect-cleanup hang (see
    ws_chat()'s finally: block for the actual fix and what's still not
    fully understood about it - a Starlette TestClient interaction, not
    something traced to this function specifically in the end).

    conversation_id resume logic: a known id resumes it - loads every prior
    message so the caller can both replay them to the client and seed
    conversation_history for LLM prompting. Anything else (None, or an id
    that doesn't exist - e.g. stale from a deleted conversation) returns
    conversation_id=None - "not created yet" - rather than eagerly creating
    a row for a connection that might disconnect without ever sending a
    message, which would otherwise litter the history sidebar with empty
    "New chat" entries. The main loop creates the real row lazily, on the
    first actual message (see ws_chat()'s main loop).
    """
    model_name = pipeline.get_active_model_name(conn)

    if conversation_id and conversation_store.conversation_exists(conn, conversation_id):
        rows = conversation_store.get_messages(conn, conversation_id)
        title_row = conn.execute("SELECT title FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        title = title_row["title"] if title_row else "New chat"
        messages = [{"role": r["role"], "content": r["content"]} for r in rows]
        return model_name, conversation_id, title, messages

    return model_name, None, "New chat", []


def api_list_traces(conn, limit: int = 20) -> list[dict[str, Any]]:
    return trace.list_recent_traces(conn, limit=limit)


def api_get_trace(conn, trace_id: str) -> list[dict[str, Any]]:
    entries = trace.get_trace(conn, trace_id)
    if not entries:
        raise ValueError(f"no trace with id {trace_id}")
    return entries


def api_proactive(conn) -> list[dict[str, Any]]:
    return proactive.evaluate(conn)


def start_session(conn) -> int | None:
    """
    Everything that happens once, at the start of a session: count it, then run
    any governance work that becomes due because of the count.

    One function so ws_chat makes ONE executor round trip for the lot - conn is
    pinned to that connection's single worker thread, and this file already
    documents what splitting one logical step into several submissions cost
    last time (see _resolve_connection_state).

    Verification failures are swallowed by run_if_due itself; begin_session is
    a single UPDATE. Neither can stop a chat from opening.
    """
    session_no = profile_store.begin_session(conn)
    verification.run_if_due(conn, session_no)
    return session_no


def api_ingest_document(conn, payload: dict[str, Any]) -> dict[str, Any]:
    file_path = payload.get("file_path")
    if not file_path:
        raise ValueError("file_path is required")
    return vector_store.ingest_document(conn, file_path, payload.get("project_id"))


def api_upload_document(conn, filename: str, content: bytes, project_id: str | None = None) -> dict[str, Any]:
    """
    Accepts raw uploaded bytes (a desktop file picker returns a path outside
    DOCUMENTS_ROOT, which ingest_document's sandbox check would reject) and
    writes them under DOCUMENTS_ROOT before ingesting - the only way a picked
    file can legally enter PIP's memory. filename is taken only for its
    basename+extension: Path(filename).name discards any directory component,
    so a crafted "../../evil.py" can't escape DOCUMENTS_ROOT here either.
    """
    safe_name = Path(filename).name
    if not safe_name or safe_name in {".", ".."}:
        raise ValueError("Invalid filename.")
    ext = Path(safe_name).suffix.lower()
    if ext not in vector_store.SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported document extension: {ext}")

    vector_store.DOCUMENTS_ROOT.mkdir(parents=True, exist_ok=True)
    dest = vector_store.DOCUMENTS_ROOT / safe_name
    if dest.exists():
        stem = Path(safe_name).stem
        n = 1
        while dest.exists():
            dest = vector_store.DOCUMENTS_ROOT / f"{stem} ({n}){ext}"
            n += 1
    dest.write_bytes(content)
    return vector_store.ingest_document(conn, str(dest), project_id)


def api_query_rag(conn, payload: dict[str, Any]) -> list[dict[str, Any]]:
    query_text = payload.get("query")
    if not query_text:
        raise ValueError("query is required")
    return vector_store.query(
        conn,
        query_text,
        project_id=payload.get("project_id"),
        threshold=payload.get("threshold", 0.6),
    )


def api_list_documents(conn) -> list[dict[str, Any]]:
    return vector_store.list_documents(conn)


def api_delete_document(conn, file_path: str) -> dict[str, Any]:
    deleted = vector_store.delete_document(conn, file_path)
    if not deleted:
        raise ValueError(f"No active document at '{file_path}'.")
    return {"status": "removed", "file_path": file_path}


async def stream_pipeline_to_websocket(
    websocket,
    conn,
    user_message: str,
    *,
    conversation_history: list[dict[str, str]],
    project_id: str | None = None,
    executor=None,
    incoming: Optional[asyncio.Queue] = None,
) -> dict[str, Any]:
    """
    Bridges pipeline.run()'s synchronous generator into the async WebSocket
    connection without blocking the event loop between yields.

    Part 13.1 already flagged the sync/async tension: BaseLLMProvider.chat()
    streams synchronously by design, and integrating it with an async server
    means wrapping the blocking calls, not rewriting the provider interface.
    `run_in_executor(executor, next, gen)` calls one `next()` at a time off the
    event loop, so other WebSocket connections aren't starved for the whole
    duration of one response.

    `executor` MUST be a dedicated single-worker executor, never the default
    shared pool (found live, not by inspection): sqlite3/sqlcipher3 connections
    can only be used on the thread that created them. The default pool can
    dispatch different next() calls to different worker threads, which crashed
    Stage 8 with "SQLite objects created in a thread can only be used in that
    same thread" on the very first real end-to-end test - Stage 8 doesn't (and
    shouldn't) fail open around that, since it's a hard security gate, so it
    surfaced immediately instead of being silently swallowed like Stage 3/4's
    fail-open paths absorbed the same underlying issue upstream. The caller
    (ws_chat) is responsible for opening conn on that same dedicated executor
    too, and for keeping one executor for the connection's whole lifetime.

    The pipeline_complete sentinel event is consumed here, not forwarded - it's
    an internal Python convenience (see pipeline.run()'s docstring), not part
    of the documented WS wire protocol (Part 14.3: token/stage_hint/error/done/
    stopped only).

    Stop support: `incoming` is a queue fed by ws_chat()'s single, permanent
    reader task (see that function) - this is the SECOND design tried here.
    The first used its own websocket.receive_json() call racing the pipeline's
    next() call each iteration; found live, cancelling that receive when a
    turn finished (to hand the socket back to ws_chat()'s own loop) could
    still lose whatever message arrived right as the cancel landed - the
    disconnect test that closes the connection right after one turn started
    failing intermittently once this was in place, exactly the class of bug a
    "shared queue, one true reader" design can't have (nothing here ever calls
    receive_json() or cancels an in-flight one - it only ever does a
    non-blocking get_nowait() on a queue). pipeline.run()'s should_stop is a
    plain Callable[[], bool] (not asyncio-aware) because Stage 9's token loop
    runs synchronously inside the executor thread - a threading.Event is the
    primitive that's actually safe to poll from there.
    """
    loop = asyncio.get_event_loop()
    stop_event = threading.Event()
    gen = pipeline.run(
        conn, user_message, conversation_history=conversation_history,
        project_id=project_id, should_stop=stop_event.is_set,
    )

    while True:
        if incoming is not None:
            while True:
                try:
                    msg = incoming.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if isinstance(msg, dict) and msg.get("type") == "stop":
                    stop_event.set()
                # Anything else arriving mid-stream is unexpected per protocol
                # (one request per turn) - dropped, not queued for later.

        try:
            event: Union[WSChatEvent, PipelineCompleteEvent] = await loop.run_in_executor(executor, next, gen)
        except StopIteration:
            raise RuntimeError("pipeline.run() ended without yielding pipeline_complete")

        if event["type"] == "pipeline_complete":
            return event["data"]

        # event is a WSChatEvent here (the pipeline_complete branch above is the
        # only other member of the union) - forwarded verbatim, Part 14.3.
        await websocket.send_json(event)


def _default_observer_provider(model_name: str):
    # ADR-033: Observer uses the same model as generation now - takes the
    # model_name the caller already resolved via pipeline.get_active_model_name()
    # rather than querying conn itself. Deliberately NOT a conn param + its own
    # conn.execute() call: found live, awaiting a fresh run_in_executor(...,
    # conn.execute...) submitted from inside ws_chat()'s disconnect-handling
    # finally: block hung indefinitely - the worker thread completed and
    # returned a value (confirmed by instrumenting it), but the awaiting
    # coroutine never woke to receive it, a Starlette TestClient/anyio
    # interaction specific to that teardown path (every OTHER run_in_executor
    # call on this same executor, including the very next line's conn.close(),
    # works fine). Taking a plain str here avoids touching conn - and needing
    # the executor at all - during that path; see the three call sites below
    # for where model_name actually gets resolved (always earlier, off the
    # disconnect/idle-timeout hot path).
    return OllamaProvider(model_name=model_name)


def _idle_timeout_seconds() -> float:
    return get_settings()["observer"]["idle_timeout_minutes"] * 60


_session_registry = session_lifecycle.SessionRegistry()


try:
    import concurrent.futures
    from contextlib import asynccontextmanager

    from fastapi import FastAPI, WebSocket, WebSocketDisconnect

    def _conn():
        return open_app_connection(os.environ.get("PIP_DB_PATH"), os.environ.get("PIP_DB_KEY"))

    def _token_path() -> Path | None:
        # Test isolation, same pattern as PIP_DB_PATH - unset means "use the
        # real persisted token in data/api_token.txt" (production behavior).
        override = os.environ.get("PIP_TOKEN_PATH")
        return Path(override) if override else None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Security review finding: nothing previously stopped a second backend
        # process from starting up against the same DB - see instance_lock.py.
        # Raises loudly (AlreadyRunningError) rather than continuing, same
        # "fail loud, not silent" posture as the SQLCipher wrong-key check.
        instance_lock.acquire()
        startup_progress.report("lock", "no other copy of PIP is running")
        # Before anything can log a request URL - the /ws/chat handshake carries
        # the token in its query string and uvicorn logs the full path.
        install_log_redaction()
        try:
            # Catch-up (recover unobserved conversations, then drain
            # pending_observer) runs in the BACKGROUND, not inline before yield.
            #
            # It used to be inline, on the Part 7 reasoning that there is no
            # live traffic yet to delay. That held only while pending_observer
            # was populated by clean shutdowns alone - rare, usually empty, so
            # the drain was almost always a no-op. Startup recovery breaks that
            # assumption: any conversation left unobserved by a kill now lands
            # in the same queue, and draining one is a ~130s-class LLM pass
            # (ADR-033). Inline, that is an app which hangs for over two minutes
            # on launch - measured, not predicted: the WS test suite began
            # intermittently timing out the moment recovery was added, because a
            # second TestClient in the same test found the first one's
            # conversation and drained it against a real Ollama.
            #
            # Backgrounding it costs nothing that was actually guaranteed:
            # Part 7's "before Stage 0" ordering only ever mattered so a
            # recovered session's memory is not missed on the NEXT turn, and a
            # pass that takes minutes could never satisfy that for a user who
            # starts typing immediately anyway. ADR-003's "zero response-speed
            # impact" is the stronger constraint, and it points here.
            #
            # asyncio.to_thread runs the whole function on ONE worker thread, so
            # the connection it opens is created and used and closed there -
            # the sqlite3/sqlcipher3 thread-affinity rule this file documents
            # elsewhere. Nothing outside that function ever touches that conn.
            def _catch_up_blocking() -> None:
                conn = _conn()
                try:
                    # Cheap (one UPDATE), and it belongs before the drain rather
                    # than after: the drain can run for minutes, and a goal that
                    # went stale while the app was closed should be marked by
                    # the time the first turn assembles context, not after.
                    profile_store.decay_stale_goals(conn)
                    # trace.hard_delete_after_days, which nothing enforced while
                    # traces lived in a file that only ever grew.
                    trace.purge_old_entries(conn)
                    recovered = session_lifecycle.recover_unobserved_conversations(conn)
                    if recovered:
                        logger.info(
                            f"Recovered {len(recovered)} conversation(s) an unclean shutdown left "
                            f"unprocessed; queued for the Observer."
                        )
                    result = session_lifecycle.drain_pending_on_startup(
                        conn, _default_observer_provider(pipeline.get_active_model_name(conn))
                    )
                    if result["completed"] or result["failed"]:
                        logger.info(f"Startup pending_observer drain: {result}")
                except Exception as e:
                    # Fail open - catch-up must never stop the app working.
                    logger.error(f"Startup catch-up failed, continuing anyway: {e}")
                finally:
                    conn.close()

            catch_up_task = asyncio.create_task(asyncio.to_thread(_catch_up_blocking))

            # Ensures the token file exists before the first request arrives.
            # Never logged: the file at auth.TOKEN_PATH (or PIP_TOKEN_PATH) is
            # the only place this value is meant to be read from.
            auth.get_or_create_token(_token_path())
            logger.info(f"PIP is ready. API token file: {_token_path() or auth.TOKEN_PATH}")
            # Last thing before serving, so the launch screen turns this into
            # "listening" only when a request would genuinely be answered. The
            # catch-up task started above is deliberately NOT reported: it runs
            # in the background precisely so nobody waits on it, and a launch
            # screen that listed it would reintroduce the two-minute hang that
            # backgrounding it removed.
            startup_progress.report("ready")

            yield

            # Shutdown: too slow to run a ~130s-class Observer pass per open
            # connection (ADR-033 condition 2) - persist instead, drained for real
            # on the next startup.
            _session_registry.shutting_down = True

            # Abandon catch-up rather than wait for it: a drain in flight is a
            # ~130s LLM pass, and shutdown cannot block on that (the same
            # ADR-033 constraint that put the queue there to begin with).
            # Nothing is lost by abandoning it - pending_observer.drain marks a
            # row 'processing' before running it, and _list_for_drain picks
            # 'processing' rows back up, so an interrupted entry is retried on
            # the next start instead of being silently consumed. cancel() only
            # detaches the awaiting coroutine; the worker thread itself runs to
            # completion or dies with the process, which is why that retry
            # behaviour is what actually makes this safe.
            catch_up_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await catch_up_task

            loop = asyncio.get_event_loop()
            for session in await _session_registry.snapshot():
                try:
                    await session_lifecycle.enqueue_for_shutdown(loop, session)
                except Exception as e:
                    logger.error(f"Shutdown: failed to enqueue a session's transcript, it will be lost: {e}")
        finally:
            instance_lock.release()

    app = FastAPI(title="PIP Core API", lifespan=lifespan)

    # Local-only clients served from a different origin than this server -
    # e.g. `flutter run -d web-server` on its own port, vs. the HTML/JS web
    # client, which is same-origin because StaticFiles mounts it onto this
    # same app below. Browsers block cross-origin fetch() without CORS
    # headers regardless of how trusted the target is; PIP is entirely
    # localhost-only (no public deployment, no cookie-based auth to leak), so
    # this is scoped to localhost/127.0.0.1 on any port rather than a bare
    # wildcard - permissive enough for any local dev client, not open to the
    # public internet. Found live: the Flutter web client's GET /status
    # failed with "ClientException: Failed to fetch" from an actual browser
    # - a REST client running on the Dart VM (dart:io, no browser involved)
    # can't hit this, since CORS is a browser-enforced mechanism, not a
    # server- or VM-side one, which is exactly why this session's earlier
    # tool/validate_live.dart run passed cleanly despite the bug being real.
    from fastapi.middleware.cors import CORSMiddleware

    # Security fix: every /api/v1/* route was reachable with zero
    # authentication - CORS above stops a cross-origin script from *reading*
    # the response, it does nothing to stop the request from being sent and
    # having side effects (the classic CSRF gap). A single middleware here
    # covers every current and future route under BASE_PREFIX uniformly,
    # rather than adding a Depends() to ~20 individual route functions one at
    # a time and risking missing one. The WS route is handled separately
    # inside ws_chat() itself - BaseHTTPMiddleware only sees HTTP requests,
    # not the WebSocket upgrade. Static file serving (the "/" mount below)
    # deliberately stays open - it's just the JS/HTML/CSS bundle, not
    # sensitive, and the client needs it to load before it has anywhere to
    # send a token from.
    #
    # Standard `Authorization: Bearer <token>` header, not a custom one - the
    # 401 body below never echoes back whatever was provided, only a fixed
    # message, so a bad token can never round-trip into a response/log line
    # via this path.
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    def _bearer_token(request) -> str | None:
        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer "):
            return None
        return header[len("Bearer "):]

    class TokenAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.url.path.startswith(BASE_PREFIX):
                if not auth.verify_token(_bearer_token(request), _token_path()):
                    return JSONResponse({"detail": "missing or invalid bearer token"}, status_code=401)
            return await call_next(request)

    app.add_middleware(TokenAuthMiddleware)

    # Registered last so it's the OUTERMOST middleware (Starlette wraps in
    # reverse add order) - it must see the browser's CORS preflight OPTIONS
    # request before TokenAuthMiddleware does, or the preflight gets 401'd
    # with no Access-Control-Allow-Origin header and the browser blocks the
    # real request. Reproduced live: Flutter web client on :5173 against this
    # backend on :8765 failed with a CORS console error until this reorder.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=_ALLOWED_ORIGIN_RE.pattern,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.websocket("/ws/chat")
    async def ws_chat(websocket: WebSocket):
        # Part 15.2: CHAT is WebSocket-only, no REST /chat exists (ADR-028). One
        # connection = one conversation: conversation_history accumulates in memory
        # for the connection's lifetime, matching pipeline.py's own note that there
        # is no message-history table - the caller owns that state, and here the
        # caller is this connection.
        #
        # Security fix: TokenAuthMiddleware only sees HTTP requests, not the WS
        # upgrade, so this connection had zero auth of its own. Browser
        # WebSocket clients can't set custom headers on connect, so the token
        # travels as a query param instead (?token=...) - checked, and the
        # socket refused via close() BEFORE accept(), rather than accepting
        # and then closing, so an unauthenticated caller never gets a live
        # connection at all.
        if not auth.verify_token(websocket.query_params.get("token"), _token_path()):
            await websocket.close(code=4401, reason="missing or invalid token")
            return

        # Defense in depth alongside the token check above: CORSMiddleware
        # never applied to the WS upgrade at all (a separate gap from the
        # missing-auth one - it's HTTP-only in Starlette), so there was no
        # origin check here whatsoever. A leaked token (logs, shoulder-surfed
        # URL, browser history) would otherwise still work from any origin.
        # No Origin header at all is accepted - non-browser clients
        # (tool/validate_live.dart's raw WebSocketChannel, a native desktop
        # build) generally don't send one; only a *present but mismatched*
        # Origin is rejected.
        origin = websocket.headers.get("origin")
        if origin and not _ALLOWED_ORIGIN_RE.match(origin):
            await websocket.close(code=4403, reason="origin not allowed")
            return
        await websocket.accept()
        loop = asyncio.get_event_loop()
        # Dedicated single-worker executor: conn is opened here and must only ever
        # be touched from this one thread for the rest of the connection's
        # lifetime (see stream_pipeline_to_websocket's docstring for why - found
        # live, a real crash, not a defensive guess).
        #
        # PinnedExecutor rather than ThreadPoolExecutor(max_workers=1), which
        # this used to be: both give one thread, only one gives a DAEMON
        # thread, and the disconnect path below abandons a conn.close() that it
        # documents as able to never return. A non-daemon worker left inside
        # that call cannot be abandoned at all - the interpreter joins it before
        # exiting - so the process that stopped waiting for it still could not
        # shut down. See pinned_executor.py for the measurement.
        executor = pinned_executor.PinnedExecutor(name=f"pip-ws-{id(websocket)}")
        conn = await loop.run_in_executor(executor, _conn)
        # observer_model_name: resolved once here, not re-queried from the
        # idle-timeout/disconnect paths below - see _default_observer_provider's
        # docstring for why a fresh conn.execute() from those specific spots
        # hangs. The active model can't meaningfully change mid-connection
        # anyway (no route re-reads it after this), so one lookup per
        # connection is correct, not just a workaround.
        #
        # conversation_id/title/resumed_messages: resumes a past conversation
        # (?conversation_id=...) or creates a new one - every turn from here on
        # is persisted against this id (see the main loop below), giving chat
        # history a Claude/ChatGPT-style sidebar instead of dying with the
        # connection like before this feature. conversation_history seeds from
        # whatever was resumed so the LLM has the same context a continued
        # conversation should.
        #
        # Both resolved in ONE run_in_executor call - see
        # _resolve_connection_state's docstring for why splitting this into two
        # separate submissions (as originally written) broke disconnect
        # cleanup.
        requested_conversation_id = websocket.query_params.get("conversation_id")
        observer_model_name, conversation_id, conversation_title, resumed_messages = await loop.run_in_executor(
            executor, _resolve_connection_state, conn, requested_conversation_id
        )
        conversation_history: list[dict[str, str]] = list(resumed_messages)
        # profile_meta.session_count is bumped once per connection, on the first
        # real message - see profile_store.begin_session() for why there and not
        # on connect or at session end. Resuming a past conversation still
        # starts a new session: it is a new connection with its own Observer
        # pass at the end of it, so this flag is per-connection and is
        # deliberately not tied to whether conversation_id already existed.
        session_counted = False
        # Whether this connection has produced a turn no Observer pass has seen.
        #
        # The three session-end triggers below used to fire on
        # `conversation_history` being non-empty, and a RESUMED conversation
        # arrives with that already full - so opening a past chat in the
        # sidebar and clicking away re-ran the whole ~130s Observer pass over a
        # transcript that had already been observed, having learned nothing new.
        # Found in the trace log: four such passes in one afternoon, two of them
        # 11 seconds apart, none with a single new message between them. The
        # expensive part is not the wasted minutes - it is that each pass
        # rewrites session_snapshot, so "what were we doing last time" could be
        # answered with a summary of a conversation from days ago, freshly
        # re-observed by a click.
        #
        # A dict rather than a bare bool because the registry holds it by
        # reference for the shutdown path (see enqueue_for_shutdown).
        session_state = {"has_unobserved_turns": False}
        session_id = id(websocket)
        await _session_registry.register(session_id, conn, executor, conversation_history, session_state)

        # Sent once, before the main loop - not part of the per-turn
        # stage_hint -> token* -> (done|error|stopped) sequence (Part 14.3).
        # See SessionInfoEvent's docstring in shared/ws_spec.py.
        await websocket.send_json({
            "type": "session_info",
            "data": {"conversation_id": conversation_id, "title": conversation_title, "messages": resumed_messages},
        })

        # Single permanent reader for this connection's whole lifetime - the
        # only thing anywhere in this handler that calls websocket.receive_json().
        # Both a new-turn ChatRequest and a mid-stream {"type": "stop"} arrive
        # through this same queue; stream_pipeline_to_websocket only ever
        # peeks it non-blockingly while streaming (see its docstring - a
        # second concurrent receive_json() caller was tried first and found
        # live to be unsafe on Starlette's WebSocket). A disconnect or any
        # other receive failure is turned into the _DISCONNECT sentinel
        # rather than raised here, so the consumer loop below has one
        # uniform shape to check regardless of why the reader stopped.
        _DISCONNECT = object()

        async def _read_forever():
            try:
                while True:
                    msg = await websocket.receive_json()
                    await incoming.put(msg)
            except Exception:
                await incoming.put(_DISCONNECT)

        incoming: asyncio.Queue = asyncio.Queue()
        reader_task = asyncio.ensure_future(_read_forever())

        try:
            while True:
                try:
                    data: ChatRequest = await asyncio.wait_for(incoming.get(), timeout=_idle_timeout_seconds())
                except asyncio.TimeoutError:
                    # Rule 3: 10-min idle triggers Observer session-end. There's
                    # time here (nothing else is waiting on this connection), so
                    # run it now rather than persist-and-defer.
                    if session_state["has_unobserved_turns"]:
                        try:
                            await session_lifecycle.run_observer_now(
                                loop, executor, conn, conversation_history,
                                _default_observer_provider(observer_model_name),
                                conversation_id=conversation_id,
                            )
                        except Exception as e:
                            logger.error(f"Idle-timeout Observer run failed, session transcript discarded: {e}")
                        # Cleared here already; the flag has to follow it, or the
                        # disconnect trigger would observe the same turns again
                        # (and rewrite the snapshot from an empty transcript).
                        session_state["has_unobserved_turns"] = False
                        conversation_history.clear()
                    continue

                if data is _DISCONNECT:
                    break

                user_message = (data or {}).get("message", "")
                project_id = (data or {}).get("project_id")
                if not user_message:
                    await websocket.send_json({"type": "error", "data": "message is required"})
                    continue

                if not session_counted:
                    session_counted = True
                    await loop.run_in_executor(executor, start_session, conn)

                # Lazy conversation creation: see _resolve_connection_state's
                # docstring - a brand-new connection arrives here with
                # conversation_id still None, and only gets a real (committed)
                # row now that there's an actual first message to attach it to.
                # Done BEFORE streaming starts, not after, so the client learns
                # the real id promptly rather than only once the whole reply
                # has already streamed in.
                if conversation_id is None:
                    conversation_id = await loop.run_in_executor(executor, conversation_store.create_conversation, conn)
                    await websocket.send_json({
                        "type": "session_info",
                        "data": {"conversation_id": conversation_id, "title": "New chat", "messages": []},
                    })

                # conversation_history holds PRIOR turns only - stage_07 appends
                # user_message as the final message itself (Part 7 Stage 7). Passing
                # a history that already includes the current message would
                # duplicate it in every prompt sent to the LLM.
                result = await stream_pipeline_to_websocket(
                    websocket, conn, user_message,
                    conversation_history=conversation_history,
                    project_id=project_id,
                    executor=executor,
                    incoming=incoming,
                )

                conversation_history.append({"role": "user", "content": user_message})
                session_state["has_unobserved_turns"] = True
                await loop.run_in_executor(
                    executor, conversation_store.append_message, conn, conversation_id, "user", user_message
                )
                if result.get("status") in ("success", "stopped") and result.get("response_text"):
                    conversation_history.append({"role": "assistant", "content": result["response_text"]})
                    await loop.run_in_executor(
                        executor, conversation_store.append_message,
                        conn, conversation_id, "assistant", result["response_text"],
                    )
        except WebSocketDisconnect:
            # Belt-and-suspenders alongside the reader's own _DISCONNECT
            # sentinel above: this path catches a disconnect surfaced through
            # a *send* (e.g. websocket.send_json() inside
            # stream_pipeline_to_websocket failing because the client is
            # already gone), which the reader task never sees since it only
            # ever calls receive_json().
            pass
        finally:
            reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reader_task
            await _session_registry.unregister(session_id)
            # Normal disconnect, not a shutdown race: there's time, run Observer
            # now rather than leaving it to a shutdown that may never come. If a
            # whole-server shutdown is racing this exact disconnect, the shutdown
            # handler's snapshot() may have already captured (and be enqueuing)
            # this same session - a best-effort, not a perfectly atomic guarantee,
            # for a single local process serving one user.
            if session_state["has_unobserved_turns"] and not _session_registry.shutting_down:
                try:
                    # conversation_id marks it observed inside the same executor
                    # call (see run_observer_now) - deliberately not a second
                    # await here, since this is the path documented below as
                    # able to leave a submission never dequeued.
                    await session_lifecycle.run_observer_now(
                        loop, executor, conn, conversation_history,
                        _default_observer_provider(observer_model_name),
                        conversation_id=conversation_id,
                    )
                except Exception as e:
                    logger.error(f"Disconnect Observer run failed, session transcript discarded: {e}")
            # Bounded, not a bare await: found live, a connection that did any
            # DB writes during its life (conversation history persistence)
            # can leave this specific run_in_executor(conn.close) submission
            # never dequeued by the single worker thread - reproduced
            # deterministically under Starlette's TestClient (30s+, not just
            # slow - genuinely never completes), narrowed to "any commit
            # happened on this connection" but not fully root-caused beyond
            # that. Whatever the exact framework interaction, a resource
            # cleanup step must never be able to hang this connection's
            # handler coroutine indefinitely - the process-level fallback
            # (the OS reclaims the fd on process exit) is an acceptable
            # backstop for the local single-user server this is, and the
            # bug this guards is the entire ASGI task wedging, not a leaked
            # connection silently accumulating across many disconnects.
            #
            # That backstop only holds because the worker is a daemon thread
            # (pinned_executor). It was written when this was a
            # ThreadPoolExecutor, whose non-daemon worker the interpreter joins
            # before exiting - so "the OS reclaims it on process exit" was
            # describing an exit the abandoned call was itself preventing.
            try:
                await asyncio.wait_for(loop.run_in_executor(executor, conn.close), timeout=5.0)
            except asyncio.TimeoutError:
                logger.error("conn.close() did not complete within 5s on disconnect - abandoning it, not blocking shutdown on it.")
            executor.shutdown(wait=False)

    @app.get(f"{BASE_PREFIX}/status")
    def status():
        with _conn() as conn:
            return api_status(conn)

    @app.post(f"{BASE_PREFIX}/onboarding/complete")
    def complete_onboarding(payload: dict[str, Any]):
        with _conn() as conn:
            return api_complete_onboarding(conn, payload)

    @app.get(f"{BASE_PREFIX}/memory/profile")
    def get_profile():
        with _conn() as conn:
            return api_get_profile(conn)

    @app.get(f"{BASE_PREFIX}/memory/profile/{{field}}")
    def get_profile_field(field: str):
        with _conn() as conn:
            return api_get_profile_field(conn, field)

    # The only profile field that keeps a history at all. It was recorded from
    # three places and readable from none.
    @app.get(f"{BASE_PREFIX}/memory/interaction-style/history")
    def get_interaction_style_history(limit: int = 50):
        with _conn() as conn:
            return api_get_interaction_style_history(conn, limit=limit)

    # 422, not a bare 500: correct_profile_field refuses the three identity
    # fields by design, and "immutable identity fields cannot be edited after
    # onboarding" IS the answer to why an edit did not take. Uncaught, that
    # sentence never leaves the server and a client can only report that
    # something unspecified went wrong. Same reasoning, same status code as
    # /memory/pending/{candidate_id}/confirm above.
    @app.post(f"{BASE_PREFIX}/memory/correct")
    def correct_memory(payload: dict[str, Any]):
        from fastapi import HTTPException
        with _conn() as conn:
            try:
                return api_correct_memory(conn, payload)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))

    @app.delete(f"{BASE_PREFIX}/memory/profile/{{field}}")
    def delete_profile_field(field: str):
        from fastapi import HTTPException
        with _conn() as conn:
            try:
                return api_delete_profile_field(conn, field)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))

    # Mirrors /decision/pending's shape deliberately: the two review queues are
    # the same interaction (PIP proposes, the user accepts or rejects) and a
    # client should not have to learn two idioms for it. "confirm" rather than
    # "promote" because a memory candidate is not moved into another table -
    # it is applied to the profile as a user-attested value.
    # The trace log is the answer to "why did PIP reply like that" - which stages
    # ran, what each retrieved, where a run failed. It was being written to a
    # file no interface read, so the answer existed and was unreachable; moving
    # it into the database without a way to get it back out would only have
    # changed where it was unreachable from.
    @app.get(f"{BASE_PREFIX}/trace")
    def list_traces(limit: int = 20):
        with _conn() as conn:
            return api_list_traces(conn, limit=limit)

    @app.get(f"{BASE_PREFIX}/trace/{{trace_id}}")
    def get_trace(trace_id: str):
        from fastapi import HTTPException
        with _conn() as conn:
            try:
                return api_get_trace(conn, trace_id)
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc))

    # Read-only: reports which allowed proactive triggers are currently firing
    # and does not act on any of them. Deciding whether to raise something with
    # the user is the client's call - keeping that decision out of the backend
    # is what keeps proactive_triggers.forbidden (model judgment of relevance or
    # urgency) structurally impossible here rather than merely discouraged.
    @app.get(f"{BASE_PREFIX}/proactive")
    def get_proactive():
        with _conn() as conn:
            return api_proactive(conn)

    @app.get(f"{BASE_PREFIX}/memory/pending")
    def get_pending_memory():
        with _conn() as conn:
            return api_get_pending_memory(conn)

    @app.post(f"{BASE_PREFIX}/memory/pending/{{candidate_id}}/confirm")
    def confirm_pending_memory(candidate_id: int):
        from fastapi import HTTPException
        with _conn() as conn:
            try:
                return api_confirm_pending_memory(conn, candidate_id)
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc))
            except ValueError as exc:
                # The candidate exists but cannot be applied - a 404 here would
                # send the caller hunting for a row that is still in the queue.
                raise HTTPException(status_code=422, detail=str(exc))

    @app.post(f"{BASE_PREFIX}/memory/pending/{{candidate_id}}/dismiss")
    def dismiss_pending_memory(candidate_id: int):
        from fastapi import HTTPException
        with _conn() as conn:
            try:
                return api_dismiss_pending_memory(conn, candidate_id)
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc))

    @app.post(f"{BASE_PREFIX}/decision/create")
    def create_decision(payload: dict[str, Any]):
        with _conn() as conn:
            return api_create_decision(conn, payload)

    @app.get(f"{BASE_PREFIX}/decision/search")
    def search_decisions(q: str = "", state: str = "active", project_id: str | None = None):
        with _conn() as conn:
            return api_search_decisions(conn, q=q, state=state, project_id=project_id)

    # update_decision_state() rejects an unknown state, and rejects retracting
    # without a reason - ADR-022 keeps the row forever, so the reason is what
    # tells a later reader "this was a fabrication we cleaned up" from "this
    # was real and we changed our mind". Both refusals are worth reading.
    @app.patch(f"{BASE_PREFIX}/decision/{{decision_id}}/state")
    def update_decision_state(decision_id: int, payload: dict[str, Any]):
        from fastapi import HTTPException
        with _conn() as conn:
            try:
                return api_update_decision_state(conn, decision_id, payload)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))

    @app.get(f"{BASE_PREFIX}/decision/pending")
    def get_pending():
        with _conn() as conn:
            return api_get_pending(conn)

    @app.post(f"{BASE_PREFIX}/decision/pending/{{candidate_id}}/promote")
    def promote_pending(candidate_id: int):
        with _conn() as conn:
            return api_promote_pending(conn, candidate_id)

    @app.post(f"{BASE_PREFIX}/decision/pending/{{candidate_id}}/dismiss")
    def dismiss_pending(candidate_id: int):
        with _conn() as conn:
            return api_dismiss_pending(conn, candidate_id)

    @app.get(f"{BASE_PREFIX}/projects")
    def list_projects():
        with _conn() as conn:
            return api_list_projects(conn)

    @app.post(f"{BASE_PREFIX}/projects")
    def create_project(payload: dict[str, Any]):
        with _conn() as conn:
            return api_create_project(conn, payload)

    @app.patch(f"{BASE_PREFIX}/projects/{{project_id}}/status")
    def update_project_status(project_id: str, payload: dict[str, Any]):
        from fastapi import HTTPException
        with _conn() as conn:
            try:
                return api_update_project_status(conn, project_id, payload)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))

    @app.post(f"{BASE_PREFIX}/projects/{{project_id}}/activate")
    def activate_project(project_id: str):
        with _conn() as conn:
            return api_activate_project(conn, project_id)

    @app.get(f"{BASE_PREFIX}/providers")
    def list_providers():
        with _conn() as conn:
            return api_list_providers(conn)

    @app.get(f"{BASE_PREFIX}/llm/models")
    def list_llm_models():
        return api_list_llm_models()

    @app.get(f"{BASE_PREFIX}/llm/active-model")
    def get_active_model():
        with _conn() as conn:
            return api_get_active_model(conn)

    @app.post(f"{BASE_PREFIX}/llm/active-model")
    def set_active_model(payload: dict[str, Any]):
        from fastapi import HTTPException
        try:
            with _conn() as conn:
                return api_set_active_model(conn, payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

    @app.get(f"{BASE_PREFIX}/conversations")
    def list_conversations(project_id: str | None = None):
        with _conn() as conn:
            return api_list_conversations(conn, project_id=project_id)

    @app.get(f"{BASE_PREFIX}/conversations/{{conversation_id}}/messages")
    def get_conversation_messages(conversation_id: str):
        from fastapi import HTTPException
        with _conn() as conn:
            try:
                return api_get_conversation_messages(conn, conversation_id)
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc))

    @app.post(f"{BASE_PREFIX}/conversations")
    def create_conversation(payload: dict[str, Any] | None = None):
        with _conn() as conn:
            return api_create_conversation(conn, payload or {})

    @app.delete(f"{BASE_PREFIX}/conversations/{{conversation_id}}")
    def delete_conversation(conversation_id: str):
        from fastapi import HTTPException
        with _conn() as conn:
            try:
                return api_delete_conversation(conn, conversation_id)
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc))

    @app.post(f"{BASE_PREFIX}/providers/{{provider_id}}/consent")
    def grant_consent(provider_id: str, payload: dict[str, Any]):
        from fastapi import HTTPException
        with _conn() as conn:
            try:
                return api_grant_consent(conn, provider_id, payload["consent_scope"])
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))

    @app.post(f"{BASE_PREFIX}/providers/{{provider_id}}/revoke")
    def revoke_consent(provider_id: str):
        from fastapi import HTTPException
        with _conn() as conn:
            try:
                return api_revoke_consent(conn, provider_id)
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc))

    from fastapi import File, Form, UploadFile

    @app.post(f"{BASE_PREFIX}/rag/upload")
    async def upload_document(file: UploadFile = File(...), project_id: str | None = Form(None)):
        from fastapi import HTTPException
        content = await file.read()
        with _conn() as conn:
            try:
                return api_upload_document(conn, file.filename or "", content, project_id)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))

    @app.post(f"{BASE_PREFIX}/rag/ingest")
    def ingest_document(payload: dict[str, Any]):
        from fastapi import HTTPException
        with _conn() as conn:
            try:
                return api_ingest_document(conn, payload)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))

    @app.post(f"{BASE_PREFIX}/rag/query")
    def query_rag(payload: dict[str, Any]):
        from fastapi import HTTPException
        with _conn() as conn:
            try:
                return api_query_rag(conn, payload)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc))

    @app.get(f"{BASE_PREFIX}/rag/documents")
    def list_documents():
        with _conn() as conn:
            return api_list_documents(conn)

    @app.delete(f"{BASE_PREFIX}/rag/documents/{{ref}}")
    def delete_document(ref: str):
        from fastapi import HTTPException
        with _conn() as conn:
            try:
                return api_delete_document(conn, ref)
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc))

    # Part 14.1: plain HTML/JS web client, built and proven before Flutter.
    # Mounted LAST so it never shadows the /api/v1/* and /ws/chat routes above -
    # Starlette matches routes in registration order and StaticFiles is a
    # catch-all.
    _WEB_CLIENT_DIR = Path(__file__).parent.parent.parent / "frontend" / "web"
    if _WEB_CLIENT_DIR.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(_WEB_CLIENT_DIR), html=True), name="web")

except ImportError:
    app = None
