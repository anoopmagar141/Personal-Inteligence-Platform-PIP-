"""
Signing in from inside the application.

The password used to be typed into a PowerShell console before uvicorn
started, and arrived as PIP_DB_KEY. The backend now starts with no key and
serves three routes until one is provided, which moves a security boundary
into HTTP - so what is tested here is mostly the boundary, not the happy path:
that a locked backend refuses everything else, that it refuses the WebSocket
too (middleware never sees that), that a wrong password changes nothing, and
that the key never comes back out in a response.
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.api import server
from backend.core import auth, db_key, session_key
from backend.memory import profile_store

PASSWORD = "correct-horse-battery"


@pytest.fixture(autouse=True)
def forget_the_key():
    """
    The key is process-global by design - it is the process's key. Tests have
    to put it back, or an unlock in one leaks into the next and every gate
    assertion after it passes for the wrong reason.
    """
    session_key.lock()
    yield
    session_key.lock()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.setenv("PIP_SALT_PATH", str(tmp_path / "salt.bin"))
    token = auth.get_or_create_token(tmp_path / "api_token.txt")
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    return TestClient(server.app), {"Authorization": f"Bearer {token}"}


def make_encrypted_db(tmp_path, password=PASSWORD):
    """An installation that has a password: a salt, and a database only that
    password's derived key can open."""
    salt = db_key.create_salt(tmp_path / "salt.bin")
    key = db_key.derive_key(password, salt)
    conn = profile_store.get_connection(str(tmp_path / "pip.db"), key)
    profile_store.initialize_schema(conn)
    conn.close()
    return key


# --- which situation is this ------------------------------------------------


def test_a_bare_installation_needs_a_password_chosen(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_SALT_PATH", str(tmp_path / "salt.bin"))
    assert session_key.state(str(tmp_path / "pip.db")) == "setup"


def test_an_installation_with_a_salt_is_locked(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_SALT_PATH", str(tmp_path / "salt.bin"))
    make_encrypted_db(tmp_path)
    assert session_key.state(str(tmp_path / "pip.db")) == "locked"


def test_a_plaintext_database_is_reported_not_repaired(tmp_path, monkeypatch):
    """
    Encrypting data somebody already has is a rekey with backup implications,
    and scripts/set_db_password.py does it carefully. A button that did it
    silently would be the least ceremonious irreversible action in the product.
    """
    monkeypatch.setenv("PIP_SALT_PATH", str(tmp_path / "salt.bin"))
    plain = sqlite3.connect(str(tmp_path / "pip.db"))
    plain.execute("CREATE TABLE something (x TEXT)")
    plain.commit()
    plain.close()

    assert session_key.state(str(tmp_path / "pip.db")) == "needs_migration"


def test_an_empty_database_file_is_not_mistaken_for_data(tmp_path, monkeypatch):
    """get_connection() creates the file the moment it is pointed at a path,
    so 'the file exists' cannot be the test for 'there is data here'."""
    monkeypatch.setenv("PIP_SALT_PATH", str(tmp_path / "salt.bin"))
    (tmp_path / "pip.db").write_bytes(b"")

    assert session_key.state(str(tmp_path / "pip.db")) == "setup"


# --- the gate ---------------------------------------------------------------


def test_a_locked_backend_refuses_every_other_route(tmp_path, monkeypatch, client):
    api, headers = client
    make_encrypted_db(tmp_path)

    for path in ["/api/v1/status", "/api/v1/memory/profile", "/api/v1/conversations",
                 "/api/v1/llm/catalog", "/api/v1/trace"]:
        response = api.get(path, headers=headers)
        assert response.status_code == 423, f"{path} answered {response.status_code} while locked"


def test_the_sign_in_routes_stay_open_while_locked(tmp_path, monkeypatch, client):
    """They are how it stops being locked. A gate that closed these would have
    no key-shaped hole in it."""
    api, headers = client
    make_encrypted_db(tmp_path)

    assert api.get("/api/v1/auth/state", headers=headers).status_code == 200
    assert api.get("/api/v1/auth/state", headers=headers).json()["state"] == "locked"


def test_the_gate_is_not_a_substitute_for_the_token(tmp_path, monkeypatch, client):
    """
    The token is checked OUTSIDE the lock gate, so an unauthenticated request
    is refused as unauthenticated - not told, by a 423, that there is a
    database here worth unlocking.
    """
    api, _ = client
    make_encrypted_db(tmp_path)

    assert api.get("/api/v1/auth/state").status_code == 401
    assert api.get("/api/v1/status").status_code == 401


def test_the_websocket_is_refused_while_locked(tmp_path, monkeypatch, client):
    """
    Starlette middleware is HTTP-only and never sees the WS handshake - the
    same gap that once left it with no origin check. Without its own check the
    chat socket would be the one way into a locked database.
    """
    api, _ = client
    token = auth.get_or_create_token(tmp_path / "api_token.txt")
    make_encrypted_db(tmp_path)

    with pytest.raises(Exception):
        with api.websocket_connect(f"/ws/chat?token={token}") as ws:
            ws.receive_json()


# --- unlocking --------------------------------------------------------------


def test_the_right_password_opens_it(tmp_path, monkeypatch, client):
    api, headers = client
    make_encrypted_db(tmp_path)

    response = api.post("/api/v1/auth/unlock", headers=headers, json={"password": PASSWORD})

    assert response.status_code == 200
    assert response.json() == {"state": "unlocked"}
    assert api.get("/api/v1/status", headers=headers).status_code == 200


def test_the_wrong_password_changes_nothing(tmp_path, monkeypatch, client):
    api, headers = client
    make_encrypted_db(tmp_path)

    response = api.post("/api/v1/auth/unlock", headers=headers, json={"password": "not-it"})

    assert response.status_code == 401
    assert session_key.is_unlocked() is False
    assert api.get("/api/v1/status", headers=headers).status_code == 423


def test_an_empty_password_is_refused_without_deriving_anything(tmp_path, monkeypatch, client):
    api, headers = client
    make_encrypted_db(tmp_path)

    assert api.post("/api/v1/auth/unlock", headers=headers, json={"password": ""}).status_code == 401
    assert api.post("/api/v1/auth/unlock", headers=headers, json={}).status_code == 401


def test_no_response_ever_contains_the_key(tmp_path, monkeypatch, client):
    """
    The key is derived here now, which it never was before - so this is the
    first version of PIP where a careless response body could hand it out.
    """
    api, headers = client
    key = make_encrypted_db(tmp_path)

    bodies = [
        api.get("/api/v1/auth/state", headers=headers).text,
        api.post("/api/v1/auth/unlock", headers=headers, json={"password": "wrong"}).text,
        api.post("/api/v1/auth/unlock", headers=headers, json={"password": PASSWORD}).text,
        api.get("/api/v1/auth/state", headers=headers).text,
    ]

    for body in bodies:
        assert key not in body
        assert PASSWORD not in body


# --- choosing the first password -------------------------------------------


def test_setup_creates_a_password_on_a_bare_installation(tmp_path, monkeypatch, client):
    api, headers = client

    response = api.post("/api/v1/auth/setup", headers=headers, json={"password": PASSWORD})

    assert response.status_code == 200
    assert (tmp_path / "salt.bin").exists()
    assert session_key.is_unlocked() is True


def test_setup_refuses_when_a_password_already_exists(tmp_path, monkeypatch, client):
    """
    create_salt() overwrites, and a replaced salt makes an existing database
    permanently unopenable with the correct password. This endpoint must never
    be a way to reach it.
    """
    api, headers = client
    make_encrypted_db(tmp_path)
    original_salt = (tmp_path / "salt.bin").read_bytes()

    response = api.post("/api/v1/auth/setup", headers=headers, json={"password": "something-else"})

    assert response.status_code == 422
    assert "already has a password" in response.json()["detail"]
    assert (tmp_path / "salt.bin").read_bytes() == original_salt


def test_setup_refuses_to_silently_encrypt_existing_data(tmp_path, monkeypatch, client):
    api, headers = client
    plain = sqlite3.connect(str(tmp_path / "pip.db"))
    plain.execute("CREATE TABLE something (x TEXT)")
    plain.commit()
    plain.close()

    response = api.post("/api/v1/auth/setup", headers=headers, json={"password": PASSWORD})

    assert response.status_code == 422
    assert "set_db_password.py" in response.json()["detail"]
    assert not (tmp_path / "salt.bin").exists()


@pytest.mark.parametrize("bad", ["", "   ", "short"])
def test_setup_refuses_a_password_that_is_not_one(tmp_path, monkeypatch, client, bad):
    api, headers = client

    response = api.post("/api/v1/auth/setup", headers=headers, json={"password": bad})

    assert response.status_code == 422
    assert not (tmp_path / "salt.bin").exists()


# --- the older launcher -----------------------------------------------------


def test_a_key_inherited_from_the_environment_is_adopted(tmp_path, monkeypatch):
    """
    An older scripts/launch_pip.ps1 still exports PIP_DB_KEY. Adopting it means
    that launcher keeps working rather than showing a sign-in screen for a
    database it has already opened.
    """
    monkeypatch.setenv("PIP_SALT_PATH", str(tmp_path / "salt.bin"))
    key = make_encrypted_db(tmp_path)
    monkeypatch.setenv("PIP_DB_KEY", key)

    assert session_key.adopt_environment_key() is True
    assert session_key.state(str(tmp_path / "pip.db")) == "unlocked"


def test_nothing_is_adopted_when_there_is_nothing_to_adopt(tmp_path, monkeypatch):
    monkeypatch.delenv("PIP_DB_KEY", raising=False)
    assert session_key.adopt_environment_key() is False
