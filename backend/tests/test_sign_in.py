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
from backend.core import auth, db_key, profiles, session_key
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

    # The switcher's two routes are open for the same reason: choosing WHO to
    # sign in as cannot require being signed in. Neither opens a database -
    # one reads an unencrypted registry, the other sets path variables.
    assert api.get("/api/v1/auth/profiles", headers=headers).status_code == 200
    assert api.post(
        "/api/v1/auth/profile", headers=headers, json={"slug": "default"}
    ).status_code == 200


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
    # The profile comes back with the state because the client may have sent
    # one - the sign-in screen's switcher does - and a request that changed
    # which database is open should say which one it left open.
    assert response.json()["state"] == "unlocked"
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



def test_a_first_run_does_not_create_a_database_before_it_has_a_password(tmp_path, monkeypatch):
    """
    The regression this closes, found by running the portable build rather than
    by any test here.

    The lifespan starts the catch-up, catch-up calls _conn(), and opening a
    database that does not exist CREATES it - so on a first run, before any
    password existed, PIP wrote itself a plaintext pip.db. /auth/setup then
    correctly refused to choose a password, because it could see an unencrypted
    database with data in it: the first run of a new install was unusable, and
    what it left behind was exactly the unencrypted database the sign-in work
    exists to prevent.

    TestClient is entered as a context manager here, unlike everywhere else in
    this file, and that is the whole test. Without it Starlette never runs the
    lifespan, catch-up never starts, and this passes against the bug - which
    the first version of it did.
    """
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.setenv("PIP_SALT_PATH", str(tmp_path / "salt.bin"))
    token = auth.get_or_create_token(tmp_path / "api_token.txt")
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    headers = {"Authorization": f"Bearer {token}"}

    with TestClient(server.app) as api:
        assert api.get("/api/v1/auth/state", headers=headers).json()["state"] == "setup"

    assert not (tmp_path / "pip.db").exists(), (
        "starting the backend created a database before there was a password for it"
    )


def test_choosing_a_first_password_produces_an_encrypted_database(tmp_path, monkeypatch):
    """
    The other half, and the point of all of it: what a fresh install ends up
    with. Before the sign-in work this was a plaintext database that stayed
    plaintext until somebody remembered to run a script.
    """
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.setenv("PIP_SALT_PATH", str(tmp_path / "salt.bin"))
    token = auth.get_or_create_token(tmp_path / "api_token.txt")
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    headers = {"Authorization": f"Bearer {token}"}

    with TestClient(server.app) as api:
        assert api.post(
            "/api/v1/auth/setup", headers=headers, json={"password": "a-real-password"}
        ).status_code == 200
        assert api.get("/api/v1/status", headers=headers).status_code == 200

    header = (tmp_path / "pip.db").read_bytes()[:16]
    assert not header.startswith(b"SQLite format 3"), (
        "a fresh install produced an unencrypted database"
    )


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


# --- Signing out -----------------------------------------------------------
#
# session_key.lock() has always worked and was reachable only from tests, so
# unlock had an endpoint and a screen while lock had neither: once PIP was
# open, ending the process was the only way to close it.


def test_signing_out_locks_everything_again(tmp_path, monkeypatch, client):
    api, headers = client
    make_encrypted_db(tmp_path)
    api.post("/api/v1/auth/unlock", headers=headers, json={"password": PASSWORD})
    assert api.get("/api/v1/status", headers=headers).status_code == 200

    response = api.post("/api/v1/auth/lock", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"state": "locked"}
    assert session_key.is_unlocked() is False
    assert api.get("/api/v1/status", headers=headers).status_code == 423


def test_the_same_password_opens_it_again_afterwards(tmp_path, monkeypatch, client):
    """
    Signing out closes the data; it does not change what opens it. Worth
    asserting rather than assuming, because lock() also clears PIP_DB_KEY from
    the environment - and a lock that damaged the path back in would be
    indistinguishable from one that worked, right up until somebody tried.
    """
    api, headers = client
    make_encrypted_db(tmp_path)
    api.post("/api/v1/auth/unlock", headers=headers, json={"password": PASSWORD})
    api.post("/api/v1/auth/lock", headers=headers)

    reopened = api.post("/api/v1/auth/unlock", headers=headers, json={"password": PASSWORD})

    assert reopened.status_code == 200
    assert api.get("/api/v1/status", headers=headers).status_code == 200


def test_signing_out_is_not_a_way_in(tmp_path, monkeypatch, client):
    """
    /auth/lock is deliberately NOT in _UNLOCKED_PATHS. Locking a locked
    session has nothing to do, and that list is only what the sign-in screen
    needs in order to get in - a route that widens it earns its place or stays
    out.
    """
    api, headers = client
    make_encrypted_db(tmp_path)

    assert api.post("/api/v1/auth/lock", headers=headers).status_code == 423


def test_signing_out_still_needs_the_api_token(tmp_path, monkeypatch, client):
    api, _ = client
    make_encrypted_db(tmp_path)

    assert api.post("/api/v1/auth/lock").status_code == 401


# --- choosing a profile -----------------------------------------------------
#
# This was a numbered menu printed by scripts/_profiles.ps1 before uvicorn
# started, and it is now two routes and a control on the sign-in screen. What
# is tested here is what the move made possible and what it must not have made
# possible: that the backend can be re-pointed while locked, that it refuses to
# be while unlocked, and that the separation the profiles module exists to
# provide - one password per database - is not weakened by the switch being a
# click rather than a restart.


def second_profile(name="Second", password="a-different-password"):
    """A registered profile with a database of its own, under its own password."""
    profile = profiles.register(name)
    make_encrypted_db(profile.paths()["db"].parent, password=password)
    return profile


def test_the_profile_list_names_who_can_sign_in(tmp_path, client):
    api, headers = client
    make_encrypted_db(tmp_path)
    profiles.register("Second")

    payload = api.get("/api/v1/auth/profiles", headers=headers).json()

    assert payload["active"] == "default"
    assert [p["name"] for p in payload["profiles"]] == ["Default", "Second"]
    # Registered but never opened. This is what lets the screen say "Choose a
    # password" for one name and "Welcome back" for another without opening
    # anything - the distinction the console menu drew with "(no database yet)".
    assert payload["profiles"][0]["exists"] is True
    assert payload["profiles"][1]["exists"] is False


def test_the_list_carries_no_paths(tmp_path, client):
    """A directory layout is not something a sign-in screen needs, so it is not
    something the route hands out."""
    api, headers = client
    make_encrypted_db(tmp_path)
    profiles.register("Second")

    body = api.get("/api/v1/auth/profiles", headers=headers).text

    assert "pip.db" not in body
    assert "salt" not in body


def test_switching_reports_the_state_of_the_profile_switched_to(tmp_path, client):
    """
    The whole reason the switcher can exist. A name with no database behind it
    is a "choose a password" screen even when the one before it was not, and
    the client learns that from the same call that does the switching rather
    than from a second question that could be answered after another switch.
    """
    api, headers = client
    make_encrypted_db(tmp_path)
    fresh = profiles.register("Second")

    switched = api.post("/api/v1/auth/profile", headers=headers, json={"slug": fresh.slug})

    assert switched.status_code == 200
    assert switched.json() == {"profile": fresh.slug, "name": "Second", "state": "setup"}
    assert api.get("/api/v1/auth/state", headers=headers).json()["state"] == "setup"

    back = api.post("/api/v1/auth/profile", headers=headers, json={"slug": "default"})
    assert back.json()["state"] == "locked"


def test_switching_is_refused_while_unlocked(tmp_path, client):
    """
    The safety property the whole feature rests on. The key in memory belongs
    to the profile it was derived for, and it is also in PIP_DB_KEY, which
    vector_store reads. Re-pointing underneath it would aim one profile's key
    at another's files - SQLCipher refuses the database loudly, but the Chroma
    directory would be opened and written under the wrong key's HMAC, which
    fails silently and permanently.
    """
    api, headers = client
    make_encrypted_db(tmp_path)
    other = profiles.register("Second")
    api.post("/api/v1/auth/unlock", headers=headers, json={"password": PASSWORD})

    refused = api.post("/api/v1/auth/profile", headers=headers, json={"slug": other.slug})

    assert refused.status_code == 409
    # And nothing moved: the database that was open is still the one open.
    assert profiles.active_slug() == "default"
    assert api.get("/api/v1/status", headers=headers).status_code == 200


def test_an_unknown_profile_is_refused_rather_than_created(tmp_path, client):
    """
    404, not a new directory. slugify() keeps a name from climbing out of the
    profiles directory, but a route that registered whatever it was sent would
    let anything holding the API token litter the data directory with profiles
    nobody asked for.
    """
    api, headers = client
    make_encrypted_db(tmp_path)

    refused = api.post("/api/v1/auth/profile", headers=headers, json={"slug": "nobody"})

    assert refused.status_code == 404
    assert profiles.active_slug() == "default"


def test_a_profiles_own_password_is_the_only_one_that_opens_it(tmp_path, client):
    """
    The separation, unchanged by the switch being a click. Two profiles are two
    databases under two keys derived from two passwords; making the choice
    easier to reach must not make one password reach further.
    """
    api, headers = client
    make_encrypted_db(tmp_path)
    other = second_profile()

    refused = api.post(
        "/api/v1/auth/unlock",
        headers=headers,
        json={"password": PASSWORD, "profile": other.slug},
    )
    assert refused.status_code == 401

    opened = api.post(
        "/api/v1/auth/unlock",
        headers=headers,
        json={"password": "a-different-password", "profile": other.slug},
    )
    assert opened.status_code == 200
    assert opened.json()["profile"] == other.slug


def test_the_password_and_the_profile_it_is_for_arrive_together(tmp_path, client):
    """
    unlock() honours a profile in its own body rather than trusting a selection
    made in an earlier request. Two calls leave a window between them, and
    "typed one profile's password at another's database" should be reachable by
    a mistake, never by timing.
    """
    api, headers = client
    make_encrypted_db(tmp_path)
    other = second_profile()

    # Never selected; named only in the unlock itself.
    opened = api.post(
        "/api/v1/auth/unlock",
        headers=headers,
        json={"password": "a-different-password", "profile": other.slug},
    )

    assert opened.status_code == 200
    assert profiles.active_slug() == other.slug


def test_only_a_password_that_worked_records_the_last_used_profile(tmp_path, client):
    """
    The half of this that got better rather than only moving. The launcher
    wrote last_used at the MENU, because the password was typed into the
    application long after the script had exited - so a selection that never
    opened anything still became "last opened". It is now written after a key
    has been proven to open the database.
    """
    api, headers = client
    make_encrypted_db(tmp_path)
    other = second_profile()

    api.post("/api/v1/auth/profile", headers=headers, json={"slug": other.slug})
    api.post(
        "/api/v1/auth/unlock",
        headers=headers,
        json={"password": "not-it", "profile": other.slug},
    )
    assert profiles.last_used() == "default"

    api.post(
        "/api/v1/auth/unlock",
        headers=headers,
        json={"password": "a-different-password", "profile": other.slug},
    )
    assert profiles.last_used() == other.slug


def test_choosing_a_first_password_lands_in_the_profile_it_was_chosen_for(tmp_path, client):
    """
    Setup takes a profile for the same reason unlock does. A new profile's
    first password is the case the switcher makes reachable at all - before
    this, a profile registered by scripts/new_profile.py could only be opened
    by restarting the launcher and answering its menu.
    """
    api, headers = client
    make_encrypted_db(tmp_path)
    fresh = profiles.register("Second")

    created = api.post(
        "/api/v1/auth/setup",
        headers=headers,
        json={"password": "a-brand-new-password", "profile": fresh.slug},
    )

    assert created.status_code == 200
    assert created.json()["profile"] == fresh.slug
    # In the new profile's directory, and nowhere near the original's.
    assert fresh.paths()["salt"].exists()
    assert fresh.exists()
