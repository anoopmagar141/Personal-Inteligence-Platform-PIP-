"""
G-1 / D-05 (docs/FREEZE_LIST.md §7.16): no request creates or writes a database
before anyone has signed in.

After a restart nothing has activated a profile yet - the sign-in screen does
that, and it has not run. The process points at the base slot (data/pip.db,
data/salt.bin), where the installation lived before profiles existed. When
profiles are registered that slot holds nothing, so session_key.state() calls it
"setup": no salt, no data. LockGateMiddleware only gates "locked", so every
route was let through, _conn() opened the missing database, and
open_app_connection() created an empty UNENCRYPTED pip.db there. Two things
followed:
- the chat socket accepted a connection, and a message sent in that window was
  stored in plaintext beside the encrypted profiles;
- the file's existence made profiles.load() list a "Default" account on a
  needs-migration screen, for a profile nobody ever made.

The installation here is built the way a person builds one - two profiles made
through the real routes, each with a password - and then restarted: locked, and
the process pointed back at the base slot, which is how a launcher leaves it.
The second start is a real lifespan.

test_empty_installation_creates_nothing.py is the neighbouring case, an
installation whose registry lists nobody. This one is a registry that lists
people and a process that is pointed at none of them.
"""

import os
import re
import urllib.request
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.api import server
from backend.core import auth, response_cache, session_key

API = "/api/v1"

# What a launcher leaves behind: the process pointed at the base slot. The
# conftest points these at the test's own temp folder, so they are base-slot
# paths that are safe to create and to look for.
_POINTERS = ("PIP_DB_PATH", "PIP_SALT_PATH", "PIP_CHROMA_PATH", "PIP_DOCUMENTS_ROOT", "PIP_PROFILE")


@pytest.fixture(autouse=True)
def forget_the_key():
    session_key.lock()
    response_cache.clear()
    yield
    session_key.lock()
    response_cache.clear()


def _headers():
    token = auth.get_or_create_token(Path(os.environ["PIP_TOKEN_PATH"]))
    return {"Authorization": f"Bearer {token}"}


def _make_profile(client, headers, name, password):
    """What a person does: make the profile, choose its password, sign out. Signing out matters
    to the test as much as to the person - the app refuses to make a second profile while one
    is open."""
    created = client.post(f"{API}/auth/profiles", json={"name": name}, headers=headers)
    assert created.status_code == 200, created.text
    slug = created.json()["slug"]
    response = client.post(f"{API}/auth/setup", json={"password": password, "profile": slug}, headers=headers)
    assert response.status_code == 200, response.text
    assert client.post(f"{API}/auth/lock", headers=headers).status_code == 200
    return slug


@pytest.fixture
def restarted(monkeypatch):
    """Two real profiles with passwords, then a restart that has signed nobody in."""
    base = {name: os.environ[name] for name in _POINTERS}
    headers = _headers()

    with TestClient(server.app) as first:
        _make_profile(first, headers, "Alice", "alice-password-1")
        _make_profile(first, headers, "Bob", "bob-password-2")

    # The process ends. The next one is started by a launcher that selects no
    # profile, so the paths are the base slot's again and no key is held.
    for name, value in base.items():
        monkeypatch.setenv(name, value)
    session_key.lock()
    base_db = Path(base["PIP_DB_PATH"])
    assert not base_db.exists(), "the first run left a database in the base slot: the test is not the situation it names"

    # A route that is served when it should not be may well fail inside, on the empty
    # payload the census sends; that is still "served", and it is the answer to record,
    # not an exception to rethrow into the middle of the loop.
    with TestClient(server.app, raise_server_exceptions=False) as second:
        yield second, headers, base_db


def _routes():
    out = []
    for route in server.app.routes:
        if isinstance(route, APIRoute) and route.path.startswith(API):
            path = re.sub(r"\{[^}]+\}", "x1", route.path)
            for method in sorted(route.methods - {"HEAD"}):
                out.append((method, path, route.path))
    return out


def _nothing_in_the_base_slot(base_db):
    """The database, and what SQLite writes beside one."""
    return not any(base_db.parent.glob(base_db.name + "*"))


def test_no_route_is_served_and_nothing_is_created_while_profiles_exist_and_nobody_is_signed_in(restarted, monkeypatch):
    """
    The census the validation pass ran by hand, over every route the app has.
    The sign-in screen's own routes are exempt, by the gate's own list. Every
    other answers 423, and none of them leaves a file in the base slot. A route
    that reaches for the network fails fast: the point is what is written, not
    what is fetched.
    """
    client, headers, base_db = restarted

    def no_network(*args, **kwargs):
        raise OSError("no network in this test")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)

    served = []
    for method, path, template in _routes():
        response = client.request(method, path, headers=headers, json={})
        exempt = path in server._UNLOCKED_PATHS or server._UNLOCKED_PATH_RE.match(path)
        if not exempt and response.status_code != 423:
            served.append((method, template, response.status_code))

    assert not served, f"routes that answered while nobody was signed in: {served}"
    assert _nothing_in_the_base_slot(base_db), (
        f"a request created a database in the base slot: {sorted(p.name for p in base_db.parent.glob(base_db.name + '*'))}"
    )


def test_the_chat_socket_is_refused_before_it_is_accepted(restarted):
    """
    Accepted, it opened the base slot and a message sent into it was stored
    unencrypted. Refused the way a locked backend refuses it: before accept(),
    with 4423, the WebSocket's own 423.
    """
    client, headers, base_db = restarted
    token = headers["Authorization"].split()[1]

    with pytest.raises(WebSocketDisconnect) as refused:
        with client.websocket_connect(f"/ws/chat?token={token}") as ws:
            ws.receive_json()

    assert refused.value.code == 4423
    assert _nothing_in_the_base_slot(base_db), "the socket created a database in the base slot"


def test_the_backstop_refuses_what_is_not_a_route(restarted):
    """
    _conn() is the backstop behind the gate, for what is not a route: a
    background task, a WebSocket, something added later that forgets. A status
    code cannot tell which of the two answered a request, so this asks it
    directly.
    """
    client, headers, base_db = restarted

    with pytest.raises(server.LockedError):
        server._conn()

    assert _nothing_in_the_base_slot(base_db)


def test_no_default_profile_appears_that_nobody_made(restarted):
    """
    The phantom the file made: with a database in the base slot,
    profiles.load() counted the installation as legacy data and listed a
    "Default" account on a needs-migration screen.
    """
    client, headers, base_db = restarted

    client.get(f"{API}/status", headers=headers)
    listed = client.get(f"{API}/auth/profiles", headers=headers).json()

    assert [p["slug"] for p in listed["profiles"]] == ["alice", "bob"]
    assert _nothing_in_the_base_slot(base_db)


def test_control_starting_the_backend_creates_nothing_in_the_base_slot(restarted):
    """Before any request at all. Startup already took care of this (the catch-up
    refuses to create a database that is not there), and it stays that way."""
    client, headers, base_db = restarted

    assert _nothing_in_the_base_slot(base_db)


def test_control_signing_in_after_the_restart_still_works(restarted):
    """
    What the fix must not cost: the sign-in screen picks a profile, the password
    opens it, and from then on the routes are served, from that profile's own
    folder. Nothing is ever written to the base slot.
    """
    client, headers, base_db = restarted

    listed = client.get(f"{API}/auth/profiles", headers=headers).json()
    assert [p["slug"] for p in listed["profiles"]] == ["alice", "bob"]
    selected = client.post(f"{API}/auth/profile", json={"slug": "alice"}, headers=headers)
    assert selected.status_code == 200 and selected.json()["state"] == "locked"

    opened = client.post(f"{API}/auth/unlock", json={"password": "alice-password-1", "profile": "alice"}, headers=headers)
    assert opened.status_code == 200, opened.text
    assert client.get(f"{API}/status", headers=headers).status_code == 200

    assert _nothing_in_the_base_slot(base_db)
