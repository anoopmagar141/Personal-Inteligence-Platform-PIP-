import os
from pathlib import Path
from typing import Any

from backend.memory import decision_log, profile_store


BASE_PREFIX = "/api/v1"
DEFAULT_DB_PATH = Path(__file__).parent.parent.parent / "data" / "pip.db"


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


try:
    from fastapi import FastAPI

    app = FastAPI(title="PIP Core API")

    def _conn():
        return open_app_connection(os.environ.get("PIP_DB_PATH"), os.environ.get("PIP_DB_KEY"))

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

except ImportError:
    app = None
