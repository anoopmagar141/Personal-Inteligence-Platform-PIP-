"""
A restore that cannot proceed answers with a sentence, never a 500 (FREEZE_LIST D-11).

POST /backup/restore turns RestoreError into a 422 whose detail is the
sentence the person reads; anything else became a 500 "The backup could not be
read: <driver message>". Three inputs reached the second kind and are the
subject here:

  a folder given as the backup     "unable to open database file"
  an empty backup password         "PRAGMA key requires a key of one or more characters"
  a bit-flipped backup             "SQL logic error"

The first two are reachable only through the API (the file picker cannot return
a folder, and the dialog refuses an empty password), which is what an API is
for - and the 500 stranded a message that was perfectly good. The third is
reachable by anybody whose backup was damaged in a copy, which is the case a
restore exists for.

One more input is in the same family and is held here: a new password equal to
the backup password. restore_backup.py refuses it ("losing either secret loses
both"); stage_restore accepted it, so the two ways of restoring disagreed about
what a valid pair of passwords is.

Outcomes, not return values: every refusal leaves nothing staged - no marker,
no temporary files - and says why in a sentence.
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
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/api/v1/auth/unlock", json={"password": PASSWORD}, headers=headers)
    assert response.status_code == 200, response.text
    return client, headers, tmp_path


def _backup(tmp_path, rows=400):
    """Big enough to span several pages, so a flipped byte can land in one that
    is neither the header nor the schema."""
    path = tmp_path / "backup.pipbak"
    conn = sqlcipher3.connect(str(path))
    conn.execute(f"PRAGMA key = '{BACKUP_PASSWORD}'")
    conn.execute("CREATE TABLE identity (id INTEGER PRIMARY KEY, name TEXT)")
    conn.executemany(
        "INSERT INTO identity (id, name) VALUES (?, ?)",
        [(i, f"person-{i}-" + "x" * 80) for i in range(1, rows + 1)],
    )
    conn.commit()
    conn.close()
    return path


def _post(client, headers, **overrides):
    body = {"backup_password": BACKUP_PASSWORD, "new_password": NEW_PASSWORD}
    body.update(overrides)
    return client.post("/api/v1/backup/restore", json=body, headers=headers)


def _nothing_staged(tmp_path):
    return (
        not restore.pending_restore_path().exists()
        and not list(tmp_path.glob("restore-*.tmp.*"))
    )


def test_a_folder_is_a_sentence_not_a_500(app):
    client, headers, tmp_path = app
    folder = tmp_path / "my-backups"
    folder.mkdir()

    response = _post(client, headers, path=str(folder))

    assert response.status_code == 422, response.text
    assert "is a folder" in response.json()["detail"]
    assert _nothing_staged(tmp_path)


def test_an_empty_backup_password_is_a_sentence_not_a_500(app):
    client, headers, tmp_path = app

    response = _post(client, headers, path=str(_backup(tmp_path)), backup_password="")

    assert response.status_code == 422, response.text
    assert "password" in response.json()["detail"].lower()
    assert _nothing_staged(tmp_path)


def test_a_damaged_backup_is_a_sentence_not_a_500(app):
    """A byte flipped in the middle of the file, as a bad copy leaves it."""
    client, headers, tmp_path = app
    path = _backup(tmp_path)
    raw = bytearray(path.read_bytes())
    for offset in range(8192 + 40, 8192 + 60):
        raw[offset] ^= 0xFF
    path.write_bytes(bytes(raw))

    response = _post(client, headers, path=str(path))

    assert response.status_code == 422, response.text
    assert "damaged" in response.json()["detail"].lower() or "did not open" in response.json()["detail"].lower()
    assert _nothing_staged(tmp_path)


def test_a_new_password_equal_to_the_backup_password_is_refused(app):
    """restore_backup.py has always refused this; stage_restore did not."""
    client, headers, tmp_path = app

    response = _post(client, headers, path=str(_backup(tmp_path)), new_password=BACKUP_PASSWORD)

    assert response.status_code == 422, response.text
    assert "different" in response.json()["detail"].lower()
    assert _nothing_staged(tmp_path)


def test_a_good_backup_still_stages(app):
    client, headers, tmp_path = app

    response = _post(client, headers, path=str(_backup(tmp_path)))

    assert response.status_code == 200, response.text
    assert restore.pending_restore() is not None


def test_a_failure_after_the_temporary_copy_is_written_leaves_none_of_it(app, monkeypatch):
    """
    "Nothing was replaced" was true and "nothing was left" was not: a failure
    once the converted database existed (the row counts, the marker write, a
    full disk) raised with the re-encrypted copy of the person's data still in
    their profile folder, beside a salt that opens it.
    """
    client, headers, tmp_path = app
    path = _backup(tmp_path)

    def disk_full(*args, **kwargs):
        raise OSError("No space left on device")

    monkeypatch.setattr(restore.json, "dumps", disk_full)
    with pytest.raises(OSError):
        restore.stage_restore(
            path, BACKUP_PASSWORD, NEW_PASSWORD,
            db_path=tmp_path / "pip.db", salt_path=tmp_path / "salt.bin",
        )

    assert _nothing_staged(tmp_path)
