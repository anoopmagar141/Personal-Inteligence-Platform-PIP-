"""
PROBE (not part of the suite): authentication census over every route, the
WebSocket handshake, path traversal on path parameters, profile ownership,
and the document delete lifecycle - all through the real app and lifespan.
"""
import os
import re
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.api import server
from backend.core import auth, response_cache, session_key

API = "/api/v1"
UNLOCKED = {f"{API}/auth/state", f"{API}/auth/profiles", f"{API}/auth/profile",
            f"{API}/auth/unlock", f"{API}/auth/setup"}
PIC_RE = re.compile(rf"^{API}/auth/profiles/[^/]+/picture$")


@pytest.fixture(autouse=True)
def forget():
    session_key.lock(); response_cache.clear()
    yield
    session_key.lock(); response_cache.clear()


@pytest.fixture
def no_observer(monkeypatch):
    async def nop(*a, **k):
        return {"memory_results": [], "decision_results": []}
    monkeypatch.setattr(server.session_lifecycle, "run_observer_now", nop)


@pytest.fixture
def token():
    return auth.get_or_create_token(Path(os.environ["PIP_TOKEN_PATH"]))


def H(t):
    return {"Authorization": f"Bearer {t}"}


def new_profile(c, t, name, pw):
    slug = c.post(f"{API}/auth/profiles", json={"name": name}, headers=H(t)).json()["slug"]
    r = c.post(f"{API}/auth/setup", json={"password": pw, "profile": slug}, headers=H(t))
    assert r.status_code == 200, r.text
    return slug


def all_routes():
    out = []
    for r in server.app.routes:
        if isinstance(r, APIRoute) and r.path.startswith(API):
            path = re.sub(r"\{[^}]+\}", "x1", r.path)
            for m in sorted(r.methods - {"HEAD"}):
                out.append((m, path, r.path))
    return out


def test_R1_every_route_requires_the_token(token, no_observer):
    bad = []
    routes = all_routes()
    with TestClient(server.app) as c:
        for m, path, tmpl in routes:
            for hdr in ({}, {"Authorization": "Bearer wrong"}, {"Authorization": f"Basic {token}"}):
                r = c.request(m, path, headers=hdr, json={})
                if r.status_code != 401:
                    bad.append((m, tmpl, hdr and list(hdr.values())[0][:6], r.status_code))
    print(f"ROUTES CHECKED: {len(routes)} method+path pairs x 3 bad credentials")
    assert not bad, bad


def test_R2_every_route_refused_while_locked(token, no_observer):
    bad, served = [], []
    routes = all_routes()
    with TestClient(server.app) as c:
        new_profile(c, token, "Alice", "alice-password-1")
        assert c.post(f"{API}/auth/lock", headers=H(token)).status_code == 200
        for m, path, tmpl in routes:
            r = c.request(m, path, headers=H(token), json={})
            open_ = path in UNLOCKED or PIC_RE.match(path)
            if open_:
                served.append((m, tmpl, r.status_code))
            elif r.status_code != 423:
                bad.append((m, tmpl, r.status_code))
    print(f"LOCKED CENSUS: {len(routes)} pairs; open while locked: {served}")
    assert not bad, bad


@pytest.mark.parametrize("path", [
    "//api/v1/memory/profile", "/api/v1//memory/profile", "/API/v1/memory/profile",
    "/api/v1/memory/profile/", "/api/v1/./memory/profile", "/api/v1/%6Demory/profile",
    "/api/v1/auth/../memory/profile",
])
def test_R3_path_variants_never_serve_data_without_token(path, token, no_observer):
    with TestClient(server.app) as c:
        new_profile(c, token, "Alice", "alice-password-1")
        r = c.get(path, follow_redirects=True)
        print(path, "->", r.status_code)
        assert r.status_code in (401, 404, 405), (path, r.status_code, r.text[:200])


@pytest.mark.parametrize("origin,expect", [
    (None, None), ("http://localhost:5173", None), ("http://127.0.0.1", None),
    ("http://localhost.attacker.tld", 4403), ("https://localhost", 4403),
    ("null", 4403), ("http://evil.example", 4403), ("http://LOCALHOST:1", 4403),
])
def test_WS1_origin_check(origin, expect, token, no_observer):
    with TestClient(server.app) as c:
        new_profile(c, token, "Alice", "alice-password-1")
        hdr = {"origin": origin} if origin else {}
        if expect is None:
            with c.websocket_connect(f"/ws/chat?token={token}", headers=hdr) as ws:
                assert ws.receive_json()["type"] == "session_info"
        else:
            with pytest.raises(WebSocketDisconnect) as e:
                with c.websocket_connect(f"/ws/chat?token={token}", headers=hdr) as ws:
                    ws.receive_json()
            assert e.value.code == expect


@pytest.mark.parametrize("q,code", [("", 4401), ("?token=wrong", 4401), ("?token=", 4401)])
def test_WS2_token_check(q, code, token, no_observer):
    with TestClient(server.app) as c:
        new_profile(c, token, "Alice", "alice-password-1")
        with pytest.raises(WebSocketDisconnect) as e:
            with c.websocket_connect(f"/ws/chat{q}") as ws:
                ws.receive_json()
        assert e.value.code == code


@pytest.mark.parametrize("slug", ["..", "..%2F..%2Fapi_token.txt", "%2e%2e", "default", "..\\..", "C:%5CWindows"])
def test_T1_picture_slug_cannot_escape(slug, token, no_observer):
    with TestClient(server.app) as c:
        new_profile(c, token, "Alice", "alice-password-1")
        r = c.get(f"{API}/auth/profiles/{slug}/picture", headers=H(token))
        print(slug, r.status_code)
        assert r.status_code == 404, (slug, r.status_code, r.content[:80])


def test_P1_unlocked_alice_cannot_rename_or_delete_bob(token, no_observer):
    with TestClient(server.app) as c:
        bob = new_profile(c, token, "Bob", "bob-password-22")
        c.post(f"{API}/auth/lock", headers=H(token))
        new_profile(c, token, "Alice", "alice-password-1")
        r1 = c.patch(f"{API}/auth/profiles/{bob}", json={"name": "Hacked"}, headers=H(token))
        r2 = c.request("DELETE", f"{API}/auth/profiles/{bob}", json={"password": "alice-password-1"}, headers=H(token))
        r3 = c.post(f"{API}/auth/password", json={"profile": bob, "current_password": "alice-password-1",
                                                   "new_password": "zzzzzzzzzz"}, headers=H(token))
        names = [p["name"] for p in c.get(f"{API}/auth/profiles", headers=H(token)).json()["profiles"]]
    print("rename", r1.status_code, "delete", r2.status_code, "password", r3.status_code, names)
    assert r1.status_code >= 400 and r2.status_code >= 400
    assert "Bob" in names


def test_D1_document_delete_lifecycle(token, no_observer):
    """What remains of a document after the user deletes it in the app."""
    secret = b"Project QUOKKA-7 budget is 41,000 and the vendor is Larkspur."
    with TestClient(server.app) as c:
        new_profile(c, token, "Alice", "alice-password-1")
        up = c.post(f"{API}/rag/upload", files={"file": ("budget.txt", secret, "text/plain")}, headers=H(token))
        assert up.status_code == 200, up.text
        fp = up.json()["file_path"]
        from urllib.parse import quote
        d = c.delete(f"{API}/rag/documents/{quote(fp, safe='')}", headers=H(token))
        listed = c.get(f"{API}/rag/documents", headers=H(token)).json()
        q = c.post(f"{API}/rag/query", json={"query": "QUOKKA-7 budget vendor"}, headers=H(token)).json()
        with server._conn() as conn:
            blob = conn.execute(
                "SELECT b.byte_size, d.status FROM document_blobs b JOIN documents d ON d.id=b.document_id"
            ).fetchall()
            blob = [dict(r) for r in blob]
    on_disk = Path(fp).exists() and Path(fp).read_bytes() == secret
    print("DELETE status:", d.status_code, d.text[:120])
    print("listed after delete:", listed)
    print("query after delete:", q)
    print("file still on disk in plaintext:", on_disk, fp)
    print("blob rows after delete:", blob)
    assert d.status_code == 200
    assert not on_disk, "deleted document's plaintext file remains on disk"
    assert not blob, "deleted document's content remains in document_blobs"


def test_D2_delete_ref_outside_documents_touches_nothing(token, no_observer, tmp_path):
    victim = tmp_path / "victim.txt"
    victim.write_text("keep me")
    with TestClient(server.app) as c:
        new_profile(c, token, "Alice", "alice-password-1")
        from urllib.parse import quote
        r = c.delete(f"{API}/rag/documents/{quote(str(victim), safe='')}", headers=H(token))
        r2 = c.post(f"{API}/rag/ingest", json={"file_path": str(tmp_path / 'documents' / '..' / 'victim.txt')}, headers=H(token))
    print("delete outside:", r.status_code, "ingest via ..:", r2.status_code, r2.text[:120])
    assert victim.read_text() == "keep me"
    assert r.status_code == 404 and r2.status_code == 422
