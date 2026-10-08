"""
Importing a backup from the welcome screen (POST /backup/import).

The welcome screen's "Import existing PIP" used to be a signpost: it said close PIP,
run a shortcut, and sign in to a profile called "Default". It could not do the import
itself because the in-app restore replaces the profile you are signed in to, and a
screen with nobody signed in has no proof of ownership of anything. At first run that
objection has nothing to protect: no profile has a database, so there is nothing to
replace. This route is allowed ONLY then.

What is held, as outcomes a person meets:

  - the profile arrives named after the person inside the backup, not "Default", and
    can be signed in to with the NEW password and no other;
  - it is refused, with a sentence, the moment any profile has a database or somebody
    is signed in - the in-app restore, which asks for a signed-in profile, is the way
    to replace one;
  - a refusal or a failure leaves nothing behind: no registered profile, no folder,
    no staged file, and the empty installation is still an empty installation.
"""

import importlib.util
import pathlib
import sys

import pytest
import sqlcipher3
from fastapi.testclient import TestClient

from backend.api import server
from backend.core import auth, profiles, restore, session_key
from backend.memory import conversation_store, decision_log, profile_store

LIVE_KEY = "11" * 32
BACKUP_PASSWORD = "the-backup-password"
NEW_PASSWORD = "a-brand-new-live-password"


def _load(name):
    root = pathlib.Path(__file__).parent.parent.parent
    scripts_dir = str(root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(name, root / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def forget_the_key():
    session_key.lock()
    yield
    session_key.lock()


@pytest.fixture
def fresh(tmp_path, monkeypatch):
    """An installation nobody has set up: no registry, no database."""
    data = tmp_path / "install"
    data.mkdir()
    monkeypatch.setenv("PIP_DATA_DIR", str(data))
    monkeypatch.setenv("PIP_DB_PATH", str(data / "pip.db"))
    monkeypatch.setenv("PIP_SALT_PATH", str(data / "salt.bin"))
    monkeypatch.setenv("PIP_CHROMA_PATH", str(data / "chroma"))
    monkeypatch.setenv("PIP_DOCUMENTS_ROOT", str(data / "documents"))
    monkeypatch.delenv("PIP_PROFILE", raising=False)
    token = auth.get_or_create_token(data / "api_token.txt")
    monkeypatch.setenv("PIP_TOKEN_PATH", str(data / "api_token.txt"))
    return TestClient(server.app), {"Authorization": f"Bearer {token}"}, data


def _make_backup(tmp_path, monkeypatch, *, name="BatMan", with_identity=True):
    """A real, marked .pipbak, made by the real export script."""
    source = tmp_path / "source.db"
    conn = profile_store.get_connection(str(source), db_key=LIVE_KEY)
    profile_store.initialize_schema(conn)
    if with_identity:
        profile_store.complete_onboarding(conn, name=name, language_preference="English", skills=[])
    decision_log.insert_decision(conn, text="Import from the welcome screen", reasoning="first run has nothing to replace")
    cid = conversation_store.create_conversation(conn)
    conversation_store.append_message(conn, cid, "user", "Hello from the other machine")
    conn.commit()
    conn.close()

    export = _load("export_backup")
    out = tmp_path / "carried.pipbak"
    monkeypatch.setenv("PIP_DB_KEY", LIVE_KEY)
    monkeypatch.setattr(export.getpass, "getpass", lambda prompt="": BACKUP_PASSWORD)
    monkeypatch.setattr(export.sys, "argv", ["export_backup.py", "--db-path", str(source), "--out", str(out)])
    export.main()
    monkeypatch.delenv("PIP_DB_KEY")
    return out


def _post(client, headers, **overrides):
    body = {"backup_password": BACKUP_PASSWORD, "new_password": NEW_PASSWORD}
    body.update(overrides)
    return client.post("/api/v1/backup/import", json=body, headers=headers)


def _empty(data):
    """Nothing registered, no profile folder, no staged file."""
    return (
        not profiles.registry_path().exists()
        and not list(data.glob("restore-*.tmp.*"))
        and not (data / "profiles").exists()
        and not restore.pending_restore_path().exists()
        and not (data / "pip.db").exists()
    )


# ---------------------------------------------------------------------------
# The import itself
# ---------------------------------------------------------------------------


def test_the_backup_arrives_as_a_profile_named_after_the_person_in_it(fresh, tmp_path, monkeypatch):
    client, headers, data = fresh
    backup = _make_backup(tmp_path, monkeypatch)

    response = _post(client, headers, path=str(backup))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["slug"] == "batman" and body["name"] == "BatMan"
    assert body["state"] == "locked"
    listed = client.get("/api/v1/auth/profiles", headers=headers).json()
    assert [(p["slug"], p["name"], p["exists"]) for p in listed["profiles"]] == [("batman", "BatMan", True)]


def test_only_the_new_password_opens_it_and_everything_came_with_it(fresh, tmp_path, monkeypatch):
    client, headers, data = fresh
    backup = _make_backup(tmp_path, monkeypatch)
    assert _post(client, headers, path=str(backup)).status_code == 200

    for wrong in (BACKUP_PASSWORD, "not-it-at-all"):
        refused = client.post("/api/v1/auth/unlock", json={"password": wrong, "profile": "batman"}, headers=headers)
        assert refused.status_code == 401, f"{wrong!r} opened the imported profile"
    opened = client.post("/api/v1/auth/unlock", json={"password": NEW_PASSWORD, "profile": "batman"}, headers=headers)
    assert opened.status_code == 200, opened.text

    titles = [c["title"] for c in client.get("/api/v1/conversations", headers=headers).json()]
    assert "Hello from the other machine" in titles
    decisions = [d["decision_text"] for d in client.get("/api/v1/decision/search", params={"q": ""}, headers=headers).json()]
    assert "Import from the welcome screen" in decisions


def test_a_backup_with_no_name_in_it_is_called_imported_profile(fresh, tmp_path, monkeypatch):
    client, headers, data = fresh
    backup = _make_backup(tmp_path, monkeypatch, with_identity=False)

    response = _post(client, headers, path=str(backup))

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Imported profile"


# ---------------------------------------------------------------------------
# When it is not allowed, and what a refusal leaves behind
# ---------------------------------------------------------------------------


def _a_profile_with_a_database(client, headers):
    client.post("/api/v1/auth/profiles", json={"name": "Priya"}, headers=headers)
    client.post("/api/v1/auth/setup", json={"password": "priyas-own-password", "profile": "priya"}, headers=headers)
    client.get("/api/v1/memory/profile", headers=headers)
    client.post("/api/v1/auth/lock", headers=headers)
    assert profiles.get("priya").exists()


def test_it_is_refused_once_any_profile_has_a_database(fresh, tmp_path, monkeypatch):
    """The route's own refusal, reached when the profile on screen is an empty one
    but ANOTHER already holds data: the welcome screen is not where that is replaced."""
    client, headers, data = fresh
    backup = _make_backup(tmp_path, monkeypatch)
    _a_profile_with_a_database(client, headers)
    client.post("/api/v1/auth/profiles", json={"name": "Empty"}, headers=headers)  # becomes the active one

    response = _post(client, headers, path=str(backup))

    assert response.status_code == 409, response.text
    assert "Backup" in response.json()["detail"]
    assert sorted(p.slug for p in profiles.list_profiles()) == ["empty", "priya"], "an imported profile was registered anyway"
    assert not list(data.glob("restore-*.tmp.*"))


def test_it_is_refused_when_the_active_profile_is_a_locked_one(fresh, tmp_path, monkeypatch):
    """The lock gate answers first (423) when the profile on screen holds data; either
    way nothing is imported and nothing is registered."""
    client, headers, data = fresh
    backup = _make_backup(tmp_path, monkeypatch)
    _a_profile_with_a_database(client, headers)

    response = _post(client, headers, path=str(backup))

    assert response.status_code in (409, 423), response.text
    assert [p.slug for p in profiles.list_profiles()] == ["priya"]
    assert not list(data.glob("restore-*.tmp.*"))


def test_it_is_refused_while_somebody_is_signed_in(fresh, tmp_path, monkeypatch):
    client, headers, data = fresh
    backup = _make_backup(tmp_path, monkeypatch)
    client.post("/api/v1/auth/profiles", json={"name": "Priya"}, headers=headers)
    client.post("/api/v1/auth/setup", json={"password": "priyas-own-password", "profile": "priya"}, headers=headers)

    response = _post(client, headers, path=str(backup))

    assert response.status_code == 409, response.text


@pytest.mark.parametrize("overrides, sentence", [
    ({"backup_password": "wrong-password"}, "did not open"),
    ({"new_password": BACKUP_PASSWORD}, "different"),
    ({"new_password": "short"}, "at least 8"),
    ({"backup_password": ""}, "password"),
])
def test_a_refused_import_leaves_the_installation_empty(fresh, tmp_path, monkeypatch, overrides, sentence):
    client, headers, data = fresh
    backup = _make_backup(tmp_path, monkeypatch)

    response = _post(client, headers, path=str(backup), **overrides)

    assert response.status_code == 422, response.text
    assert sentence in response.json()["detail"]
    assert _empty(data), "a refused import left a profile, a folder or a staged file behind"


def test_an_empty_file_is_refused_and_leaves_nothing(fresh, tmp_path):
    client, headers, data = fresh
    empty = tmp_path / "empty.pipbak"
    empty.write_bytes(b"")

    response = _post(client, headers, path=str(empty))

    assert response.status_code == 422, response.text
    assert _empty(data)


def test_a_missing_file_is_a_sentence(fresh, tmp_path):
    client, headers, data = fresh

    response = _post(client, headers, path=str(tmp_path / "nowhere.pipbak"))

    assert response.status_code == 422, response.text
    assert _empty(data)


def test_a_failure_after_the_profile_was_registered_unregisters_it(fresh, tmp_path, monkeypatch):
    """Everything that can be refused is refused first, but a disk can still fail
    between registering the profile and installing into it. The person must be
    left with no half-made 'BatMan' on the sign-in screen."""
    client, headers, data = fresh
    backup = _make_backup(tmp_path, monkeypatch)

    def disk_full(*args, **kwargs):
        raise OSError("No space left on device")

    monkeypatch.setattr(restore, "stage_restore", disk_full)
    response = _post(client, headers, path=str(backup))

    assert response.status_code == 500, response.text
    assert profiles.list_profiles() == [], "a profile the failed import registered was left behind"
    assert not (data / "profiles" / "batman" / "pip.db").exists()
    assert not list(data.glob("restore-*.tmp.*"))
