"""
An installation with no profiles must not grow a "Default" one by itself.

After the last profile is deleted - or data/ is wiped - nothing is signed in, no
salt exists and no database does. session_key.state() calls that "setup", which
LockGateMiddleware does not gate, so /status (asked by the app while it is still
on the create-a-profile screen) reached _conn(), which opened the missing
database and created an empty unencrypted pip.db at the base path. That file
made profiles.load() count the installation as legacy data and list a "Default"
account on a needs-migration screen.
"""

import pytest
from fastapi.testclient import TestClient

from backend.api import server
from backend.core import auth, profiles, session_key


@pytest.fixture(autouse=True)
def forget_the_key():
    session_key.lock()
    yield
    session_key.lock()


@pytest.fixture
def empty_installation(tmp_path, monkeypatch):
    monkeypatch.setenv("PIP_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PIP_DB_PATH", str(tmp_path / "pip.db"))
    monkeypatch.setenv("PIP_SALT_PATH", str(tmp_path / "salt.bin"))
    monkeypatch.setenv("PIP_CHROMA_PATH", str(tmp_path / "chroma"))
    monkeypatch.setenv("PIP_DOCUMENTS_ROOT", str(tmp_path / "documents"))
    monkeypatch.setenv("PIP_PROFILE", profiles.DEFAULT_SLUG)
    monkeypatch.setenv("PIP_TOKEN_PATH", str(tmp_path / "api_token.txt"))
    # An installation that has had profiles and has none now: a registry exists
    # and lists nobody. This is the file profiles.delete() leaves behind.
    profiles._save([], profiles.DEFAULT_SLUG)
    token = auth.get_or_create_token(tmp_path / "api_token.txt")
    return TestClient(server.app), {"Authorization": f"Bearer {token}"}, tmp_path


def test_status_with_no_profile_creates_no_database(empty_installation):
    client, headers, tmp_path = empty_installation

    response = client.get("/api/v1/status", headers=headers)

    assert response.status_code == 423
    assert not (tmp_path / "pip.db").exists()
    assert profiles.list_profiles() == []


def test_the_sign_in_screen_still_reports_no_profiles(empty_installation):
    client, headers, tmp_path = empty_installation

    body = client.get("/api/v1/auth/profiles", headers=headers).json()

    assert body["profiles"] == []
    assert not (tmp_path / "pip.db").exists()
