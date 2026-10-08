"""
A staged restore belongs to the profile it was staged for (FREEZE_LIST D-19).

There is one pending-restore.json per installation, but the three routes acted
on it as the signed-in profile's:

  GET     reported another profile's staged restore to whoever was signed in,
          with that profile's file name, as "Ready to restore on the next start".
  DELETE  cancelled it for whoever was signed in. Zed stages a restore and signs
          out; Yara signs in and her "Cancel the restore" erased his, and he was
          never told.
  POST    replaced it without reading it, leaving the earlier staging's files
          behind, and accepted a restore for Yara while Zed's was waiting - Zed's
          was then never installed (his old password still opened his profile and
          the one he had chosen did not) and its files stayed in his folder.

And a deleted profile's folder could keep a staged copy: a full re-encrypted copy
of the backup's data under a password chosen while staging, which the delete of
that profile could not remove because its erasable paths did not name it.

The outcomes held are on disk: whose marker survives, which files exist, and
that nobody is shown or told anything about a restore that is not theirs.
"""

import pytest
import sqlcipher3
from fastapi.testclient import TestClient

from backend.api import server
from backend.core import auth, db_key, profiles, restore, session_key
from backend.memory import profile_store

PASSWORD = "correct-horse-battery"
BACKUP_PASSWORD = "the-backup-password"
NEW_PASSWORD = "a-different-long-one"
PRIYA_PASSWORD = "priyas-own-password"


@pytest.fixture(autouse=True)
def forget_the_key():
    session_key.lock()
    yield
    session_key.lock()


@pytest.fixture
def app(tmp_path, monkeypatch):
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
    return client, {"Authorization": f"Bearer {token}"}, tmp_path


def _backup(tmp_path, name="backup.pipbak"):
    path = tmp_path / name
    conn = sqlcipher3.connect(str(path))
    conn.execute(f"PRAGMA key = '{BACKUP_PASSWORD}'")
    conn.execute("CREATE TABLE identity (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO identity (id, name) VALUES (1, 'restored')")
    conn.commit()
    conn.close()
    return path


def _stage(client, headers, tmp_path, name="backup.pipbak"):
    return client.post(
        "/api/v1/backup/restore",
        json={"path": str(_backup(tmp_path, name)), "backup_password": BACKUP_PASSWORD,
              "new_password": NEW_PASSWORD},
        headers=headers,
    )


def _sign_in_default(client, headers):
    client.post("/api/v1/auth/lock", headers=headers)
    client.post("/api/v1/auth/profile", json={"slug": profiles.DEFAULT_SLUG}, headers=headers)
    response = client.post("/api/v1/auth/unlock", json={"password": PASSWORD}, headers=headers)
    assert response.status_code == 200, response.text


def _priya_stages_then_default_signs_in(app):
    """Priya's restore is staged, she signs out, and the default profile signs in."""
    client, headers, tmp_path = app
    client.post("/api/v1/auth/profiles", json={"name": "Priya"}, headers=headers)
    client.post("/api/v1/auth/setup", json={"password": PRIYA_PASSWORD, "profile": "priya"}, headers=headers)
    client.get("/api/v1/memory/profile", headers=headers)
    staged = _stage(client, headers, tmp_path, "priyas.pipbak")
    assert staged.status_code == 200, staged.text
    marker = restore.pending_restore()
    _sign_in_default(client, headers)
    return client, headers, tmp_path, marker


def _staged_files(tmp_path):
    return sorted(p.name for p in (tmp_path / "profiles" / "priya").glob("restore-*.tmp.*"))


# ---------------------------------------------------------------------------
# Whose restore it is
# ---------------------------------------------------------------------------


def test_another_profiles_staged_restore_is_not_shown(app):
    client, headers, tmp_path, _ = _priya_stages_then_default_signs_in(app)

    status = client.get("/api/v1/backup/restore", headers=headers)

    assert status.status_code == 200
    assert status.json() == {"pending": False}, "one profile was shown another's staged restore"


def test_cancelling_does_not_cancel_another_profiles_restore(app):
    client, headers, tmp_path, marker = _priya_stages_then_default_signs_in(app)
    files = _staged_files(tmp_path)

    cancelled = client.delete("/api/v1/backup/restore", headers=headers)

    assert cancelled.json() == {"cancelled": False}
    assert restore.pending_restore() == marker, "her cancel erased his marker"
    assert _staged_files(tmp_path) == files and files, "her cancel erased his staged files"


def test_a_restore_is_refused_while_another_profiles_waits_and_the_other_survives(app):
    client, headers, tmp_path, marker = _priya_stages_then_default_signs_in(app)

    response = _stage(client, headers, tmp_path, "mine.pipbak")

    assert response.status_code == 422, response.text
    assert "another profile" in response.json()["detail"].lower()
    assert restore.pending_restore() == marker, "the other profile's restore was replaced"
    assert not list(tmp_path.glob("restore-*.tmp.*")), "the refused staging left its files in this profile's folder"


def test_the_profile_that_staged_it_still_sees_and_cancels_it(app):
    client, headers, tmp_path = app
    client.post("/api/v1/auth/profiles", json={"name": "Priya"}, headers=headers)
    client.post("/api/v1/auth/setup", json={"password": PRIYA_PASSWORD, "profile": "priya"}, headers=headers)
    client.get("/api/v1/memory/profile", headers=headers)
    _stage(client, headers, tmp_path, "priyas.pipbak")

    seen = client.get("/api/v1/backup/restore", headers=headers).json()
    cancelled = client.delete("/api/v1/backup/restore", headers=headers).json()

    assert seen["pending"] is True and seen["source"] == "priyas.pipbak"
    assert cancelled == {"cancelled": True}
    assert restore.pending_restore() is None
    assert _staged_files(tmp_path) == []


# ---------------------------------------------------------------------------
# Staging twice
# ---------------------------------------------------------------------------


def test_staging_again_replaces_the_profiles_own_earlier_staging_cleanly(app):
    """The app hides 'Choose a .pipbak' while one is pending; the API, or a
    second window that has not refreshed, does not."""
    client, headers, tmp_path = app
    client.post("/api/v1/auth/unlock", json={"password": PASSWORD}, headers=headers)
    first = _stage(client, headers, tmp_path, "first.pipbak")
    assert first.status_code == 200, first.text
    first_files = {p.name for p in tmp_path.glob("restore-*.tmp.*")}

    import time
    time.sleep(1.1)  # staged files are named by the second
    second = _stage(client, headers, tmp_path, "second.pipbak")

    assert second.status_code == 200, second.text
    assert restore.pending_restore()["source"].endswith("second.pipbak")
    left = {p.name for p in tmp_path.glob("restore-*.tmp.*")}
    assert not (left & first_files), "the earlier staging's files were left behind"
    assert len(left) == 2, "the new staging's own files are missing"

    # and the cancel the app offers removes everything
    client.delete("/api/v1/backup/restore", headers=headers)
    assert not list(tmp_path.glob("restore-*.tmp.*"))


# ---------------------------------------------------------------------------
# An orphan does not outlive its profile
# ---------------------------------------------------------------------------


def test_deleting_a_profile_erases_staged_files_nothing_points_at(app):
    client, headers, tmp_path = app
    client.post("/api/v1/auth/profiles", json={"name": "Wren"}, headers=headers)
    client.post("/api/v1/auth/setup", json={"password": "wrens-own-password", "profile": "wren"}, headers=headers)
    client.get("/api/v1/memory/profile", headers=headers)
    folder = tmp_path / "profiles" / "wren"
    # What an older build left behind: staged files with no marker naming them.
    (folder / "restore-20261002T101010Z.tmp.db").write_bytes(b"a full copy of the data")
    (folder / "restore-20261002T101010Z.tmp.salt").write_bytes(b"s" * 16)

    deleted = client.request(
        "DELETE", "/api/v1/auth/profiles/wren", json={"password": "wrens-own-password"}, headers=headers,
    )

    assert deleted.status_code == 200, deleted.text
    assert not folder.exists() or not list(folder.iterdir()), "a staged copy of the data outlived its profile"


def test_a_stale_marker_for_another_profile_does_not_block_a_restore(app):
    """A marker whose staged files are gone is cleared at the next start; until
    then it must not stop everybody else restoring for the rest of the session."""
    client, headers, tmp_path, marker = _priya_stages_then_default_signs_in(app)
    for path in (marker["db"], marker["salt"]):
        __import__("pathlib").Path(path).unlink()

    response = _stage(client, headers, tmp_path, "mine.pipbak")

    assert response.status_code == 200, response.text
    assert restore.pending_restore()["source"].endswith("mine.pipbak")


def test_two_stagings_in_the_same_second_both_work_and_the_later_one_stands(tmp_path, monkeypatch):
    """
    Staged files used to be named by the second. A second staging inside the same
    second reused the first's temporary database - encrypted under the first
    salt - and failed opening it under its own new key: "file is not a database",
    surfaced as a damaged backup. A person never stages twice in a second; an API
    client or a double click does.
    """
    monkeypatch.setattr(restore, "now_utc", lambda: "2026-10-08T01:00:00Z")
    folder = tmp_path / "profile"
    folder.mkdir()

    for name in ("one.pipbak", "two.pipbak"):
        staged = restore.stage_restore(
            _backup(tmp_path, name), BACKUP_PASSWORD, NEW_PASSWORD,
            db_path=folder / "pip.db", salt_path=folder / "salt.bin",
        )

    assert staged["source"].endswith("two.pipbak")
    assert restore.pending_restore()["source"].endswith("two.pipbak")
    assert sorted(p.name for p in folder.glob("restore-*.tmp.*")) == sorted(
        [__import__("pathlib").Path(staged["db"]).name, __import__("pathlib").Path(staged["salt"]).name]
    ), "the earlier staging's files were left beside the new one's"
