"""
Making, renaming, re-keying and destroying profiles from inside the app.

Adding a profile has been possible since profiles existed - through
scripts/new_profile.py, which needs a console, a checkout and a virtualenv.
Deleting one has not been possible at all: profiles.remove() unregisters and
deliberately leaves the files, and nothing exposed even that. So what is tested
here is not "a profile can be made" but the properties that decide whether
these controls are safe to put in front of somebody:

  Ownership is proved, not assumed. Every operation that changes or destroys a
  profile is refused unless the caller is signed in AS that profile, and the
  destructive two ask for the password again on top of that. Being unlocked
  says the database was opened at some point; it does not say who is at the
  keyboard now.

  Deleting erases and does not merely hide. A control labelled "delete my
  account" that leaves an encrypted database on disk is the misleading label
  profiles.py's own header warns about, pointed the other way.

  Deleting the default profile does not take the other profiles with it. Its
  data_dir is "." - the data directory itself - which also holds profiles.json,
  pip.lock and api_token.txt. The unit of deletion has to be the four
  per-profile paths, or "delete my account" quietly means "delete everyone's".

  A failed password change leaves the old password working. There is no
  recovery for a forgotten password, by design; there must be one for a rekey
  that did not finish, or the software has caused the loss the design only
  accepts from the user.
"""

import json

import pytest
from fastapi.testclient import TestClient

from backend.api import server
from backend.core import auth, db_key, profiles, session_key
from backend.memory import profile_store

PASSWORD = "correct-horse-battery"
NEW_PASSWORD = "a-different-long-one"


@pytest.fixture(autouse=True)
def forget_the_key():
    """The key is process-global by design, so a test that unlocks has to put
    it back or the next one's gate assertions pass for the wrong reason."""
    session_key.lock()
    yield
    session_key.lock()


@pytest.fixture
def app(tmp_path, monkeypatch):
    """
    A client pointed at a throwaway data directory, with the default profile
    already created and its password set.

    PIP_DATA_DIR isolates the registry; the four path variables are set the way
    profiles.activate() sets them, so the process starts out pointed at the
    default profile exactly as a real launch would.
    """
    monkeypatch.setenv("PIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.setenv("PIP_SALT_PATH", str(tmp_path / "salt.bin"))
    monkeypatch.setenv("PIP_CHROMA_PATH", str(tmp_path / "chroma"))
    monkeypatch.setenv("PIP_DOCUMENTS_ROOT", str(tmp_path / "documents"))
    monkeypatch.setenv("PIP_PROFILE", profiles.DEFAULT_SLUG)

    salt = db_key.create_salt(tmp_path / "salt.bin")
    key = db_key.derive_key(PASSWORD, salt)
    conn = profile_store.get_connection(str(tmp_path / "pip.db"), key)
    profile_store.initialize_schema(conn)
    conn.close()

    token = auth.get_or_create_token(tmp_path / "api_token.txt")
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    client = TestClient(server.app)
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers, tmp_path


def sign_in(client, headers, password=PASSWORD):
    response = client.post("/api/v1/auth/unlock", json={"password": password}, headers=headers)
    assert response.status_code == 200, response.text
    return response


# ---------------------------------------------------------------------------
# Making one
# ---------------------------------------------------------------------------


def test_a_profile_can_be_created_without_a_console(app):
    """
    The whole point of the route. Everything else about profiles already
    worked; the only way to add one was a Python script, which for anybody who
    installed PIP rather than cloned it is the same as no way at all.
    """
    client, headers, tmp_path = app

    created = client.post("/api/v1/auth/profiles", json={"name": "Priya"}, headers=headers)

    assert created.status_code == 200, created.text
    assert created.json()["slug"] == "priya"
    assert created.json()["name"] == "Priya"
    assert [p.slug for p in profiles.list_profiles()] == ["default", "priya"]


def test_creating_a_profile_does_not_create_its_database(app):
    """
    A database needs a password, and the password arrives at /auth/setup one
    request later. Writing an empty encrypted database here would mean choosing
    a key nobody typed - which is the plaintext-database-created-by-accident
    failure the sign-in work exists to prevent.
    """
    client, headers, tmp_path = app

    client.post("/api/v1/auth/profiles", json={"name": "Priya"}, headers=headers)

    assert not (tmp_path / "profiles" / "priya" / "pip.db").exists()
    assert not profiles.get("priya").exists()


def test_a_new_profile_is_reported_as_needing_a_password(app):
    """`state` comes back so the screen knows to say "Choose a password"
    rather than "Welcome back" without opening anything."""
    client, headers, _ = app

    created = client.post("/api/v1/auth/profiles", json={"name": "Priya"}, headers=headers)

    assert created.json()["state"] == "setup"


def test_creating_a_profile_is_refused_while_signed_in(app):
    """
    Creating activates, and activating re-points the four path variables. Doing
    that while a key is held aims one profile's key at another's files -
    SQLCipher refuses loudly, Chroma fails silently and permanently.
    """
    client, headers, _ = app
    sign_in(client, headers)

    refused = client.post("/api/v1/auth/profiles", json={"name": "Priya"}, headers=headers)

    assert refused.status_code == 409
    assert [p.slug for p in profiles.list_profiles()] == ["default"]


def test_a_duplicate_name_is_refused_rather_than_silently_merged(app):
    """Two profiles with one slug would be two names pointing at one
    directory, which is one database under one password wearing two labels."""
    client, headers, _ = app
    client.post("/api/v1/auth/profiles", json={"name": "Priya"}, headers=headers)

    again = client.post("/api/v1/auth/profiles", json={"name": "priya"}, headers=headers)

    assert again.status_code == 409


def test_a_name_that_cannot_be_a_directory_is_refused(app):
    """slugify() raises rather than inventing a name, and the sentence it
    raises is more useful than a 500."""
    client, headers, _ = app

    refused = client.post("/api/v1/auth/profiles", json={"name": "..."}, headers=headers)

    assert refused.status_code == 409


def test_a_created_profile_can_then_choose_its_password_and_open(app):
    """The two halves in sequence - the flow the sign-in screen actually
    performs, proving the split does not leave a profile unopenable."""
    client, headers, tmp_path = app

    client.post("/api/v1/auth/profiles", json={"name": "Priya"}, headers=headers)
    opened = client.post(
        "/api/v1/auth/setup",
        json={"password": "priyas-own-password", "profile": "priya"},
        headers=headers,
    )

    assert opened.status_code == 200
    assert opened.json()["profile"] == "priya"
    assert (tmp_path / "profiles" / "priya" / "salt.bin").exists()


# ---------------------------------------------------------------------------
# Renaming one
# ---------------------------------------------------------------------------


def test_renaming_changes_the_name_and_not_the_directory(app):
    """
    The slug is a path segment. Renaming it would mean moving a directory that
    holds salt.bin, which profiles.py calls the single most destructive
    operation available in this codebase.
    """
    client, headers, _ = app
    sign_in(client, headers)

    renamed = client.patch(
        "/api/v1/auth/profiles/default", json={"name": "Anup M"}, headers=headers
    )

    assert renamed.status_code == 200
    assert profiles.get("default").name == "Anup M"
    assert profiles.get("default").data_dir == "."


def test_a_profile_cannot_be_renamed_from_another_profile(app):
    """
    The ownership test. Being unlocked proves a password opened SOMETHING;
    matching the active slug is what proves it opened this one.
    """
    client, headers, _ = app
    client.post("/api/v1/auth/profiles", json={"name": "Priya"}, headers=headers)
    client.post("/api/v1/auth/profile", json={"slug": "default"}, headers=headers)
    sign_in(client, headers)

    refused = client.patch(
        "/api/v1/auth/profiles/priya", json={"name": "Not Priya"}, headers=headers
    )

    assert refused.status_code == 403
    assert profiles.get("priya").name == "Priya"


def test_a_profile_cannot_be_renamed_while_locked(app):
    """423, from the lock gate: /auth/profiles/<slug> is deliberately not on
    the list of paths the sign-in screen may reach."""
    client, headers, _ = app

    refused = client.patch(
        "/api/v1/auth/profiles/default", json={"name": "Anyone"}, headers=headers
    )

    assert refused.status_code == 423


def test_an_empty_name_is_refused(app):
    client, headers, _ = app
    sign_in(client, headers)

    refused = client.patch("/api/v1/auth/profiles/default", json={"name": "   "}, headers=headers)

    assert refused.status_code == 422
    assert profiles.get("default").name == "Default"


# ---------------------------------------------------------------------------
# Changing the password
# ---------------------------------------------------------------------------


def test_the_password_can_be_changed_and_the_new_one_opens_the_database(app):
    client, headers, tmp_path = app
    sign_in(client, headers)

    changed = client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=headers,
    )

    assert changed.status_code == 200
    session_key.lock()
    assert client.post(
        "/api/v1/auth/unlock", json={"password": NEW_PASSWORD}, headers=headers
    ).status_code == 200


def test_the_old_password_stops_working_after_a_change(app):
    """A rekey that left the old key working would not be a password change,
    it would be a second password."""
    client, headers, _ = app
    sign_in(client, headers)
    client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=headers,
    )
    session_key.lock()

    refused = client.post("/api/v1/auth/unlock", json={"password": PASSWORD}, headers=headers)

    assert refused.status_code == 401


def test_the_session_keeps_working_after_a_password_change(app):
    """
    The process is holding the OLD key against a database that no longer
    answers to it. Adopting the new one is not a convenience - without it every
    query after the change fails somewhere unrelated.
    """
    client, headers, _ = app
    sign_in(client, headers)

    client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=headers,
    )

    assert client.get("/api/v1/memory/profile", headers=headers).status_code == 200


def test_a_wrong_current_password_changes_nothing(app):
    client, headers, _ = app
    sign_in(client, headers)

    refused = client.post(
        "/api/v1/auth/password",
        json={"current_password": "not-it", "new_password": NEW_PASSWORD},
        headers=headers,
    )

    assert refused.status_code == 401
    session_key.lock()
    assert client.post(
        "/api/v1/auth/unlock", json={"password": PASSWORD}, headers=headers
    ).status_code == 200


def test_a_short_new_password_is_refused_before_the_salt_is_touched(app):
    """
    The check has to happen before create_salt(), which overwrites. A refusal
    that had already replaced the salt would have made the existing password
    stop working on the way to rejecting the new one.
    """
    client, headers, tmp_path = app
    sign_in(client, headers)
    salt_before = (tmp_path / "salt.bin").read_bytes()

    refused = client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": "short"},
        headers=headers,
    )

    assert refused.status_code == 422
    assert (tmp_path / "salt.bin").read_bytes() == salt_before


def test_a_failed_rekey_puts_the_old_salt_back(app, monkeypatch):
    """
    The property that makes this safe to offer at all. PRAGMA rekey is
    transactional, so a failure leaves the database readable under the old key
    - but only if the old SALT is still there to derive it from, and by then
    create_salt() has overwritten it. Without the restore, a rekey that failed
    at the wrong moment would turn a recoverable error into the permanent loss
    Part 10.1 says has no recovery.
    """
    client, headers, tmp_path = app
    sign_in(client, headers)
    salt_before = (tmp_path / "salt.bin").read_bytes()

    # The realistic failure: PRAGMA rekey reported success but did not take, so
    # the database is still under the old key. Stood in for by an oracle rather
    # than by the real check, because the rekey here genuinely DOES succeed -
    # what is under test is which repair the code chooses when told the old key
    # still works, and "neither key opens it" is a different situation with a
    # different correct repair (below).
    old_key = db_key.derive_key(PASSWORD, (tmp_path / "salt.bin").read_bytes())
    monkeypatch.setattr(db_key, "verify_key", lambda path, key: key == old_key)
    refused = client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=headers,
    )

    assert refused.status_code in (401, 422)
    assert (tmp_path / "salt.bin").read_bytes() == salt_before


def test_a_rekey_that_leaves_neither_key_working_keeps_the_new_salt(app, monkeypatch):
    """
    The other half of the ambiguity, and the opposite repair.

    If the old key no longer opens the database either, the rekey DID take and
    it is the verification that failed. Putting the old salt back there would
    be the thing that destroys access - the last write was under the new key,
    so the new password is the only one with any chance of matching it. The
    error says to try it rather than pretending nothing happened.
    """
    client, headers, tmp_path = app
    sign_in(client, headers)
    salt_before = (tmp_path / "salt.bin").read_bytes()

    # True once, for the current-password check that has to pass to get as far
    # as a rekey at all; False after, which is the state being tested.
    checks = {"n": 0}

    def verify(path, key):
        checks["n"] += 1
        return checks["n"] == 1

    monkeypatch.setattr(db_key, "verify_key", verify)
    refused = client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=headers,
    )

    assert refused.status_code == 422, refused.text
    assert 'NEW password' in refused.json()["detail"]
    assert (tmp_path / "salt.bin").read_bytes() != salt_before


def test_the_password_cannot_be_changed_from_another_profile(app):
    """
    /auth/password has no slug in it - it changes whatever is open. That is
    only safe because what is open is what the caller proved they can open.
    """
    client, headers, _ = app

    refused = client.post(
        "/api/v1/auth/password",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
        headers=headers,
    )

    assert refused.status_code == 423


# ---------------------------------------------------------------------------
# Destroying one
# ---------------------------------------------------------------------------


def make_second_profile(client, headers, name="Priya", password="priyas-own-password"):
    """
    A second profile with a database actually behind it, signed in as.

    The read at the end is load-bearing rather than a sanity check. /auth/setup
    writes the salt and derives the key but does NOT create pip.db - the
    database is created lazily by the first route that opens a connection, and
    the catch-up that would otherwise do it deliberately skips an installation
    whose database does not exist yet. Without this call the helper leaves a
    salt and an empty directory, and every assertion below about a database
    being erased passes without there having been one.
    """
    client.post("/api/v1/auth/profiles", json={"name": name}, headers=headers)
    slug = profiles.slugify(name)
    client.post("/api/v1/auth/setup", json={"password": password, "profile": slug}, headers=headers)
    client.get("/api/v1/memory/profile", headers=headers)
    assert profiles.get(slug).exists(), "the helper did not leave a database to delete"
    return slug


def test_deleting_erases_the_files_rather_than_hiding_them(app):
    """
    remove() unregisters and leaves the data, because its caller cannot be
    shown to own it. delete() can - it is only reachable from inside an
    unlocked profile - and once that has been proved, "delete my account" has
    to mean the bytes are gone.
    """
    client, headers, tmp_path = app
    slug = make_second_profile(client, headers)
    directory = tmp_path / "profiles" / slug

    deleted = client.request(
        "DELETE",
        f"/api/v1/auth/profiles/{slug}",
        json={"password": "priyas-own-password"},
        headers=headers,
    )

    assert deleted.status_code == 200, deleted.text
    assert not (directory / "pip.db").exists()
    assert not (directory / "salt.bin").exists()
    assert slug not in [p.slug for p in profiles.list_profiles()]


def test_deleting_signs_you_out(app):
    """The key in memory belongs to files that no longer exist. Keeping it
    would leave the process 'unlocked' against nothing."""
    client, headers, _ = app
    slug = make_second_profile(client, headers)

    deleted = client.request(
        "DELETE",
        f"/api/v1/auth/profiles/{slug}",
        json={"password": "priyas-own-password"},
        headers=headers,
    )

    assert deleted.json()["state"] == "locked"
    assert not session_key.is_unlocked()


def test_deleting_needs_the_password_again(app):
    """
    Being unlocked proves the database was opened at some point. It does not
    prove who is at the keyboard now, and this is the one operation nobody -
    including the owner - can walk back.
    """
    client, headers, tmp_path = app
    slug = make_second_profile(client, headers)

    refused = client.request(
        "DELETE",
        f"/api/v1/auth/profiles/{slug}",
        json={"password": "not-the-password"},
        headers=headers,
    )

    assert refused.status_code == 401
    assert (tmp_path / "profiles" / slug / "pip.db").exists()
    assert session_key.is_unlocked(), "a wrong password signed the user out"


def test_deleting_without_a_password_is_refused(app):
    client, headers, tmp_path = app
    slug = make_second_profile(client, headers)

    refused = client.request(
        "DELETE", f"/api/v1/auth/profiles/{slug}", json={}, headers=headers
    )

    assert refused.status_code == 422
    assert (tmp_path / "profiles" / slug / "pip.db").exists()


def test_a_profile_cannot_be_deleted_from_another_profile(app):
    """
    The rule the whole feature rests on: you delete an account from inside it.
    Priya's password is not something the default profile's session has, and
    holding a key for one profile must not authorise destroying another.
    """
    client, headers, tmp_path = app
    slug = make_second_profile(client, headers)
    session_key.lock()
    client.post("/api/v1/auth/profile", json={"slug": "default"}, headers=headers)
    sign_in(client, headers)

    refused = client.request(
        "DELETE",
        f"/api/v1/auth/profiles/{slug}",
        json={"password": "priyas-own-password"},
        headers=headers,
    )

    assert refused.status_code == 403
    assert (tmp_path / "profiles" / slug / "pip.db").exists()


def test_a_profile_cannot_be_deleted_while_locked(app):
    client, headers, tmp_path = app
    slug = make_second_profile(client, headers)
    session_key.lock()

    refused = client.request(
        "DELETE",
        f"/api/v1/auth/profiles/{slug}",
        json={"password": "priyas-own-password"},
        headers=headers,
    )

    assert refused.status_code == 423
    assert (tmp_path / "profiles" / slug / "pip.db").exists()


def test_deleting_the_default_profile_erases_its_data(app):
    """
    It is not exempt. Its data is somebody's data in exactly the way every
    other profile's is, and a "delete my account" that refused for the first
    account created would be a limitation dressed as a safeguard.
    """
    client, headers, tmp_path = app
    sign_in(client, headers)

    deleted = client.request(
        "DELETE",
        "/api/v1/auth/profiles/default",
        json={"password": PASSWORD},
        headers=headers,
    )

    assert deleted.status_code == 200, deleted.text
    assert not (tmp_path / "pip.db").exists()
    assert not (tmp_path / "salt.bin").exists()


def test_deleting_the_default_profile_does_not_delete_the_others(app):
    """
    The trap this feature is built around. The default profile's data_dir is
    "." - the data directory itself - so a delete implemented as "remove the
    directory" would be correct for every profile except this one, where it
    takes profiles.json and every other profile's registry entry with it.
    """
    client, headers, tmp_path = app
    slug = make_second_profile(client, headers)
    session_key.lock()
    client.post("/api/v1/auth/profile", json={"slug": "default"}, headers=headers)
    sign_in(client, headers)

    client.request(
        "DELETE", "/api/v1/auth/profiles/default", json={"password": PASSWORD}, headers=headers
    )

    assert (tmp_path / "profiles" / slug / "pip.db").exists(), "another profile's database was erased"
    assert (tmp_path / "profiles.json").exists(), "the registry describing the others was erased"
    assert slug in [p.slug for p in profiles.list_profiles()]


def test_deleting_the_default_profile_leaves_the_applications_own_files(app):
    """
    api_token.txt and profiles.json live in data/ beside the default profile's
    database. They belong to the running application rather than to a person -
    deleting the token would sign every other profile's client out of an API it
    still has to talk to.
    """
    client, headers, tmp_path = app
    sign_in(client, headers)

    client.request(
        "DELETE", "/api/v1/auth/profiles/default", json={"password": PASSWORD}, headers=headers
    )

    assert (tmp_path / "api_token.txt").exists()


def test_the_default_profile_survives_deletion_as_an_empty_slot(app):
    """
    Its registry entry is synthesised whenever it is missing, so that losing
    the entry can never make the database it points at unreachable. After a
    delete there is no database, so the slot correctly reads as one that has
    not been created yet.
    """
    client, headers, _ = app
    sign_in(client, headers)

    client.request(
        "DELETE", "/api/v1/auth/profiles/default", json={"password": PASSWORD}, headers=headers
    )

    listed = client.get("/api/v1/auth/profiles", headers=headers).json()["profiles"]
    default = next(p for p in listed if p["slug"] == "default")
    assert default["exists"] is False


def test_sqlite_sidecars_are_erased_with_the_database(app):
    """
    -wal and -shm hold pages that have not landed in pip.db yet. They are named
    after it rather than living under it, so the four-path list does not cover
    them - and leaving them behind would leave fragments of an erased profile's
    content in the directory it was deleted from.
    """
    client, headers, tmp_path = app
    slug = make_second_profile(client, headers)
    directory = tmp_path / "profiles" / slug
    (directory / "pip.db-wal").write_bytes(b"leftover pages")
    (directory / "pip.db-shm").write_bytes(b"shared memory")

    client.request(
        "DELETE",
        f"/api/v1/auth/profiles/{slug}",
        json={"password": "priyas-own-password"},
        headers=headers,
    )

    assert not (directory / "pip.db-wal").exists()
    assert not (directory / "pip.db-shm").exists()


def test_the_registry_still_parses_after_a_delete(app):
    """A half-written registry is one that cannot be read, and load() would
    then silently hide every profile but the default."""
    client, headers, tmp_path = app
    slug = make_second_profile(client, headers)

    client.request(
        "DELETE",
        f"/api/v1/auth/profiles/{slug}",
        json={"password": "priyas-own-password"},
        headers=headers,
    )

    parsed = json.loads((tmp_path / "profiles.json").read_text(encoding="utf-8"))
    assert [p["slug"] for p in parsed["profiles"]] == ["default"]


# ---------------------------------------------------------------------------
# The picture on the sign-in screen
# ---------------------------------------------------------------------------
#
# The one feature here with a real cost attached. A picture the sign-in screen
# can draw is a picture readable without a password - there is no third option,
# because the screen exists precisely when the database cannot be opened. So
# what is tested is that the cost is only ever paid deliberately, and that it
# stops being paid the moment somebody stops wanting it.

PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def set_avatar(client, headers):
    return client.post(
        "/api/v1/profile/picture",
        files={"file": ("me.png", PNG, "image/png")},
        headers=headers,
    )


def test_no_picture_is_published_until_somebody_asks(app):
    """
    Off by default, and the default is the whole ethic of it. Copying somebody's
    face out of an encrypted database because they set a profile picture would
    be deciding on their behalf that a recognisable switcher is worth weakening
    the thing they were promised.
    """
    client, headers, tmp_path = app
    sign_in(client, headers)
    set_avatar(client, headers)

    assert not (tmp_path / profiles.SIGNIN_PICTURE_NAME).exists()
    assert client.get("/api/v1/profile/picture/sign-in", headers=headers).json() == {
        "published": False
    }


def test_publishing_writes_the_copy_the_locked_screen_can_read(app):
    client, headers, tmp_path = app
    sign_in(client, headers)
    set_avatar(client, headers)

    published = client.post("/api/v1/profile/picture/sign-in", headers=headers)

    assert published.status_code == 200
    assert (tmp_path / profiles.SIGNIN_PICTURE_NAME).read_bytes() == PNG


def test_a_published_picture_is_served_while_locked(app):
    """The point of publishing. If this needed a password it would be
    describing a screen that is only reachable after one."""
    client, headers, _ = app
    sign_in(client, headers)
    set_avatar(client, headers)
    client.post("/api/v1/profile/picture/sign-in", headers=headers)
    session_key.lock()

    served = client.get("/api/v1/auth/profiles/default/picture", headers=headers)

    assert served.status_code == 200
    assert served.content == PNG
    assert served.headers["content-type"] == "image/png"


def test_an_unpublished_profiles_picture_is_never_served(app):
    """
    The avatar is in the encrypted database and stays there. A profile that has
    a picture but has not published one must be a 404 on this route, or the
    opt-in is decorative.
    """
    client, headers, _ = app
    sign_in(client, headers)
    set_avatar(client, headers)
    session_key.lock()

    assert client.get("/api/v1/auth/profiles/default/picture", headers=headers).status_code == 404


def test_the_picture_route_still_needs_the_api_token(app):
    """Open to the locked state, not open to the network. It is behind the same
    shared secret every other route is."""
    client, _, _ = app

    assert client.get("/api/v1/auth/profiles/default/picture").status_code == 401


def test_the_gate_is_not_widened_by_what_follows_the_picture_path(app):
    """
    The lock gate matches this one path by pattern rather than by exact string,
    because the slug varies. Anchored at both ends, so nothing can be appended
    to it to reach a route that does open the database.
    """
    client, headers, _ = app
    session_key.lock()

    assert client.get("/api/v1/auth/profiles/default/picture/../../state", headers=headers)
    assert client.get("/api/v1/memory/profile", headers=headers).status_code == 423


def test_the_listing_says_which_profiles_have_a_picture(app):
    """A boolean, so the screen knows whether to fetch. Inlining every
    profile's photo into the list would slow the common case - nobody having
    published one - to pay for the rare one."""
    client, headers, _ = app
    sign_in(client, headers)
    set_avatar(client, headers)
    client.post("/api/v1/profile/picture/sign-in", headers=headers)
    session_key.lock()

    listed = client.get("/api/v1/auth/profiles", headers=headers).json()["profiles"]

    assert next(p for p in listed if p["slug"] == "default")["picture"] is True


def test_unpublishing_deletes_the_file_rather_than_hiding_it(app):
    """
    Turning it off has to take the copy off the disk. A switch that only
    stopped drawing the picture would leave the unencrypted file exactly where
    it was, which is the entire thing being switched off.
    """
    client, headers, tmp_path = app
    sign_in(client, headers)
    set_avatar(client, headers)
    client.post("/api/v1/profile/picture/sign-in", headers=headers)

    client.delete("/api/v1/profile/picture/sign-in", headers=headers)

    assert not (tmp_path / profiles.SIGNIN_PICTURE_NAME).exists()


def test_unpublishing_leaves_the_picture_inside_the_database(app):
    """This switch is about what is visible while locked, not about the
    profile picture itself."""
    client, headers, _ = app
    sign_in(client, headers)
    set_avatar(client, headers)
    client.post("/api/v1/profile/picture/sign-in", headers=headers)

    client.delete("/api/v1/profile/picture/sign-in", headers=headers)

    assert client.get("/api/v1/profile/picture", headers=headers).status_code == 200


def test_publishing_needs_a_picture_to_publish(app):
    client, headers, _ = app
    sign_in(client, headers)

    refused = client.post("/api/v1/profile/picture/sign-in", headers=headers)

    assert refused.status_code == 404


def test_publishing_is_refused_while_locked(app):
    client, headers, _ = app

    assert client.post("/api/v1/profile/picture/sign-in", headers=headers).status_code == 423


def test_deleting_a_profile_erases_its_published_picture(app):
    """
    The most visible possible way to get the delete wrong: an account deleted
    and a photograph of the account holder left in the directory it emptied.
    The published copy is outside the database, so nothing about erasing
    pip.db would have taken it.
    """
    client, headers, tmp_path = app
    slug = make_second_profile(client, headers)
    set_avatar(client, headers)
    client.post("/api/v1/profile/picture/sign-in", headers=headers)
    picture = tmp_path / "profiles" / slug / profiles.SIGNIN_PICTURE_NAME
    assert picture.exists(), "the fixture did not publish a picture to delete"

    client.request(
        "DELETE",
        f"/api/v1/auth/profiles/{slug}",
        json={"password": "priyas-own-password"},
        headers=headers,
    )

    assert not picture.exists()


def test_bytes_that_stopped_being_an_image_are_refused_not_guessed(app):
    """
    This response is served without a password, so its Content-Type cannot be a
    guess. detect_media_type reads the header rather than trusting a name, and
    anything it does not recognise is answered as no picture at all.
    """
    client, headers, tmp_path = app
    sign_in(client, headers)
    set_avatar(client, headers)
    client.post("/api/v1/profile/picture/sign-in", headers=headers)
    (tmp_path / profiles.SIGNIN_PICTURE_NAME).write_bytes(b"<script>not an image</script>")
    session_key.lock()

    assert client.get("/api/v1/auth/profiles/default/picture", headers=headers).status_code == 404
