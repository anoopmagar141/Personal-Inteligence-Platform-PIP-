import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Any, Union

from backend.config.settings import get_settings
from backend.core import auth, pipeline, session_lifecycle
from backend.memory import decision_log, profile_store, vector_store
from backend.providers.ollama_provider import OllamaProvider
from backend.stages import stage_08_provider_gate as provider_gate
from backend.stages.stage_08_provider_gate import ProviderConsentError
from shared.ws_spec import ChatRequest, PipelineCompleteEvent, WSChatEvent

logger = logging.getLogger(__name__)


BASE_PREFIX = "/api/v1"
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "pip.db"

VALID_CONSENT_SCOPES = {"full_inference", "web_search_only", "embedding_only", "none"}

# Shared by CORSMiddleware (REST) and ws_chat()'s own manual check (WS upgrades
# never go through CORSMiddleware at all - it's HTTP-only in Starlette).
_ALLOWED_ORIGIN_RE = re.compile(r"http://(localhost|127\.0\.0\.1)(:\d+)?")


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
    return {
        "status": "ok",
        "onboarding_complete": bool(meta["onboarding_complete"]) if meta else False,
        "active_decisions": decision_count,
        "pending_decisions": pending_count,
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


def api_ingest_document(conn, payload: dict[str, Any]) -> dict[str, Any]:
    file_path = payload.get("file_path")
    if not file_path:
        raise ValueError("file_path is required")
    return vector_store.ingest_document(conn, file_path, payload.get("project_id"))


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
    of the documented WS wire protocol (Part 14.3: token/stage_hint/error/done
    only).
    """
    loop = asyncio.get_event_loop()
    gen = pipeline.run(conn, user_message, conversation_history=conversation_history, project_id=project_id)

    while True:
        try:
            event: Union[WSChatEvent, PipelineCompleteEvent] = await loop.run_in_executor(executor, next, gen)
        except StopIteration:
            raise RuntimeError("pipeline.run() ended without yielding pipeline_complete")

        if event["type"] == "pipeline_complete":
            return event["data"]

        # event is a WSChatEvent here (the pipeline_complete branch above is the
        # only other member of the union) - forwarded verbatim, Part 14.3.
        await websocket.send_json(event)


def _default_observer_provider():
    # ADR-033: Observer uses the same model as generation now. Always local
    # (stage_11_observer.run() enforces Rule 4 itself - raises if given a
    # non-local provider - this is just supplying a real local one).
    return OllamaProvider(model_name="llama3.1:8b")


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
        # Startup: drain any pending_observer rows a previous shutdown left behind
        # (Part 7: drain before Stage 0 - there's no live traffic yet to delay).
        startup_conn = _conn()
        try:
            result = session_lifecycle.drain_pending_on_startup(startup_conn, _default_observer_provider())
            if result["completed"] or result["failed"]:
                logger.info(f"Startup pending_observer drain: {result}")
        except Exception as e:
            # Fail open - a drain problem must never block the app from starting.
            logger.error(f"Startup pending_observer drain failed, continuing anyway: {e}")
        finally:
            startup_conn.close()

        # Ensures the token file exists before the first request arrives.
        # Never logged: the file at auth.TOKEN_PATH (or PIP_TOKEN_PATH) is
        # the only place this value is meant to be read from.
        auth.get_or_create_token(_token_path())
        logger.info(f"PIP is ready. API token file: {_token_path() or auth.TOKEN_PATH}")

        yield

        # Shutdown: too slow to run a ~130s-class Observer pass per open
        # connection (ADR-033 condition 2) - persist instead, drained for real
        # on the next startup.
        _session_registry.shutting_down = True
        loop = asyncio.get_event_loop()
        for session in await _session_registry.snapshot():
            try:
                await session_lifecycle.enqueue_for_shutdown(loop, session)
            except Exception as e:
                logger.error(f"Shutdown: failed to enqueue a session's transcript, it will be lost: {e}")

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

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=_ALLOWED_ORIGIN_RE.pattern,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        conn = await loop.run_in_executor(executor, _conn)
        conversation_history: list[dict[str, str]] = []
        session_id = id(websocket)
        await _session_registry.register(session_id, conn, executor, conversation_history)

        try:
            while True:
                try:
                    data: ChatRequest = await asyncio.wait_for(websocket.receive_json(), timeout=_idle_timeout_seconds())
                except asyncio.TimeoutError:
                    # Rule 3: 10-min idle triggers Observer session-end. There's
                    # time here (nothing else is waiting on this connection), so
                    # run it now rather than persist-and-defer.
                    if conversation_history:
                        try:
                            await session_lifecycle.run_observer_now(
                                loop, executor, conn, conversation_history, _default_observer_provider(),
                            )
                        except Exception as e:
                            logger.error(f"Idle-timeout Observer run failed, session transcript discarded: {e}")
                        conversation_history.clear()
                    continue

                user_message = (data or {}).get("message", "")
                project_id = (data or {}).get("project_id")
                if not user_message:
                    await websocket.send_json({"type": "error", "data": "message is required"})
                    continue

                # conversation_history holds PRIOR turns only - stage_07 appends
                # user_message as the final message itself (Part 7 Stage 7). Passing
                # a history that already includes the current message would
                # duplicate it in every prompt sent to the LLM.
                result = await stream_pipeline_to_websocket(
                    websocket, conn, user_message,
                    conversation_history=conversation_history,
                    project_id=project_id,
                    executor=executor,
                )
                conversation_history.append({"role": "user", "content": user_message})
                if result.get("status") == "success" and result.get("response_text"):
                    conversation_history.append({"role": "assistant", "content": result["response_text"]})
        except WebSocketDisconnect:
            pass
        finally:
            await _session_registry.unregister(session_id)
            # Normal disconnect, not a shutdown race: there's time, run Observer
            # now rather than leaving it to a shutdown that may never come. If a
            # whole-server shutdown is racing this exact disconnect, the shutdown
            # handler's snapshot() may have already captured (and be enqueuing)
            # this same session - a best-effort, not a perfectly atomic guarantee,
            # for a single local process serving one user.
            if conversation_history and not _session_registry.shutting_down:
                try:
                    await session_lifecycle.run_observer_now(
                        loop, executor, conn, conversation_history, _default_observer_provider(),
                    )
                except Exception as e:
                    logger.error(f"Disconnect Observer run failed, session transcript discarded: {e}")
            await loop.run_in_executor(executor, conn.close)
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

    @app.post(f"{BASE_PREFIX}/memory/correct")
    def correct_memory(payload: dict[str, Any]):
        with _conn() as conn:
            return api_correct_memory(conn, payload)

    @app.delete(f"{BASE_PREFIX}/memory/profile/{{field}}")
    def delete_profile_field(field: str):
        with _conn() as conn:
            return api_delete_profile_field(conn, field)

    @app.post(f"{BASE_PREFIX}/decision/create")
    def create_decision(payload: dict[str, Any]):
        with _conn() as conn:
            return api_create_decision(conn, payload)

    @app.get(f"{BASE_PREFIX}/decision/search")
    def search_decisions(q: str = "", state: str = "active", project_id: str | None = None):
        with _conn() as conn:
            return api_search_decisions(conn, q=q, state=state, project_id=project_id)

    @app.patch(f"{BASE_PREFIX}/decision/{{decision_id}}/state")
    def update_decision_state(decision_id: int, payload: dict[str, Any]):
        with _conn() as conn:
            return api_update_decision_state(conn, decision_id, payload)

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
        with _conn() as conn:
            return api_update_project_status(conn, project_id, payload)

    @app.post(f"{BASE_PREFIX}/projects/{{project_id}}/activate")
    def activate_project(project_id: str):
        with _conn() as conn:
            return api_activate_project(conn, project_id)

    @app.get(f"{BASE_PREFIX}/providers")
    def list_providers():
        with _conn() as conn:
            return api_list_providers(conn)

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
