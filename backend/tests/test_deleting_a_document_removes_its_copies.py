"""
G-2 / D-06 (docs/FREEZE_LIST.md §7.16, §7.50): deleting a document removes the
copies PIP made of it.

Beside the person's own file, PIP holds a document in three places:
- its chunks in the index (encrypted);
- the uploaded copy, written into the profile's documents folder as an ordinary
  readable file (Promise 7 says so);
- its bytes in document_blobs, inside the encrypted database, so that a backup is
  complete.

DELETE /rag/documents removed the chunks and marked the registry row "removed",
and stopped there. So after "Delete" in the app the file was still in the
documents folder, readable by anyone with the disk, and the bytes were still in
document_blobs - and so in every backup made afterwards, for a document the
person had been told was gone.

Driven through the real routes with a real signed-in profile, the way the
Documents screen does it: upload, then delete. What is asserted is what is left
on disk and in the database, not a return value. The last tests are about the
other side of the same rule: only a file inside this profile's own documents
folder is ever removed, and a file that cannot be removed is reported, not hidden.
"""

import importlib.util
import os
import sys
from pathlib import Path
from urllib.parse import quote

import pytest
import sqlcipher3
from fastapi.testclient import TestClient

from backend.api import server
from backend.core import auth, response_cache, session_key
from backend.memory import vector_store

API = "/api/v1"
SECRET = b"Project QUOKKA-7 budget is 41,000 and the vendor is Larkspur."
PROFILE_PASSWORD = "alice-password-1"
BACKUP_PASSWORD = "the-backup-password"


@pytest.fixture(autouse=True)
def forget_the_key():
    session_key.lock()
    response_cache.clear()
    yield
    session_key.lock()
    response_cache.clear()


@pytest.fixture
def signed_in(monkeypatch):
    async def no_observer(*args, **kwargs):
        return {"memory_results": [], "decision_results": []}

    monkeypatch.setattr(server.session_lifecycle, "run_observer_now", no_observer)
    token = auth.get_or_create_token(Path(os.environ["PIP_TOKEN_PATH"]))
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(server.app, raise_server_exceptions=False) as client:
        slug = client.post(f"{API}/auth/profiles", json={"name": "Alice"}, headers=headers).json()["slug"]
        made = client.post(f"{API}/auth/setup", json={"password": PROFILE_PASSWORD, "profile": slug}, headers=headers)
        assert made.status_code == 200, made.text
        yield client, headers


def _upload(client, headers, name="budget.txt", content=SECRET) -> str:
    response = client.post(f"{API}/rag/upload", files={"file": (name, content, "text/plain")}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["file_path"]


def _delete(client, headers, file_path):
    return client.delete(f"{API}/rag/documents/{quote(file_path, safe='')}", headers=headers)


def _listed(client, headers) -> list[str]:
    return [d["file_path"] for d in client.get(f"{API}/rag/documents", headers=headers).json()]


def _stored_bytes() -> list[dict]:
    """Every document_blobs row, with the registry row it belongs to."""
    with server._conn() as conn:
        rows = conn.execute(
            "SELECT b.document_id, b.byte_size, d.file_path, d.status "
            "FROM document_blobs b JOIN documents d ON d.id = b.document_id"
        ).fetchall()
        return [dict(r) for r in rows]


def _export_script():
    root = Path(__file__).parent.parent.parent
    scripts_dir = str(root / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("export_backup", root / "scripts" / "export_backup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _blob_rows_in_a_fresh_backup(monkeypatch, tmp_path, name) -> int:
    """
    Export the signed-in profile the way the Backup screen does, then open the result.

    A profile with a password is asked for it by the script (the key in the
    environment is deliberately ignored), and then for the backup's own password
    twice.
    """
    export = _export_script()
    out = tmp_path / name
    answers = iter([PROFILE_PASSWORD, BACKUP_PASSWORD, BACKUP_PASSWORD])
    monkeypatch.setattr(export.getpass, "getpass", lambda prompt="": next(answers))
    monkeypatch.setattr(export.sys, "argv", ["export_backup.py", "--db-path", os.environ["PIP_DB_PATH"], "--out", str(out)])
    export.main()
    assert out.exists() and out.stat().st_size > 0, "the export wrote nothing"
    conn = sqlcipher3.connect(str(out))
    try:
        conn.execute(f"PRAGMA key = '{BACKUP_PASSWORD}'")
        return conn.execute("SELECT COUNT(*) FROM document_blobs").fetchone()[0]
    finally:
        conn.close()


# --- what a delete has to remove ---------------------------------------------


def test_deleting_a_document_removes_the_uploaded_file(signed_in):
    client, headers = signed_in
    file_path = _upload(client, headers)
    assert Path(file_path).read_bytes() == SECRET, "the upload is not where the test expects it"

    response = _delete(client, headers, file_path)

    assert response.status_code == 200, response.text
    assert not Path(file_path).exists(), "the deleted document's file is still in the documents folder"
    documents = Path(os.environ["PIP_DOCUMENTS_ROOT"])
    assert not [p for p in documents.rglob("*") if p.is_file()], "something is left in the documents folder"
    assert file_path not in _listed(client, headers)


def test_deleting_a_document_removes_its_stored_bytes(signed_in):
    client, headers = signed_in
    file_path = _upload(client, headers)
    assert [row["file_path"] for row in _stored_bytes()] == [file_path], "the upload did not store its bytes"

    assert _delete(client, headers, file_path).status_code == 200

    assert _stored_bytes() == [], "the deleted document's bytes are still in the database"


def test_a_backup_made_after_deleting_carries_no_bytes_of_the_document(signed_in, monkeypatch, tmp_path):
    client, headers = signed_in
    file_path = _upload(client, headers)
    assert _blob_rows_in_a_fresh_backup(monkeypatch, tmp_path, "before.pipbak") == 1, (
        "the export does not carry a stored document at all, so the check below would prove nothing"
    )

    assert _delete(client, headers, file_path).status_code == 200

    assert _blob_rows_in_a_fresh_backup(monkeypatch, tmp_path, "after.pipbak") == 0


def test_deleting_one_document_leaves_another_alone(signed_in):
    client, headers = signed_in
    keep = _upload(client, headers, "keep.txt", b"The Larkspur contract renews in March.")
    drop = _upload(client, headers, "drop.txt", SECRET)

    assert _delete(client, headers, drop).status_code == 200

    assert Path(keep).read_bytes() == b"The Larkspur contract renews in March."
    assert [row["file_path"] for row in _stored_bytes()] == [keep]
    assert _listed(client, headers) == [keep]


def test_deleting_one_document_keeps_the_stored_bytes_of_another(signed_in):
    """
    Asked on the SAME connection as the delete, on purpose. Opening a database runs
    the start-up backfill, which stores again the bytes of any active document whose
    file is still on disk; a second connection would therefore put back what a delete
    that took too much had removed, and the test above could not see it.
    """
    client, headers = signed_in
    keep = _upload(client, headers, "keep.txt", b"The Larkspur contract renews in March.")
    drop = _upload(client, headers, "drop.txt", SECRET)

    with server._conn() as conn:
        assert vector_store.delete_document(conn, drop) is True
        left = [
            r["file_path"]
            for r in conn.execute("SELECT d.file_path FROM document_blobs b JOIN documents d ON d.id = b.document_id")
        ]

    assert left == [keep], f"the stored bytes left after deleting one document: {left}"


# --- only this profile's own files, and no silent failure --------------------


def test_a_file_outside_the_documents_folder_is_never_removed(signed_in, tmp_path):
    """
    A registry row can point somewhere else - a backup restored into a second
    profile on the same machine records paths into the first profile's folder
    (FREEZE_LIST D-07). That file belongs to someone else, so deleting the
    document may forget it but must not delete the file.
    """
    client, headers = signed_in
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    foreign = elsewhere / "other.txt"
    foreign.write_bytes(b"belongs to another folder")
    registered = str(foreign.resolve())
    with server._conn() as conn:
        added = conn.execute(
            "INSERT INTO documents (project_id, file_path, content_hash, chunk_count, status, ingested_at) "
            "VALUES (NULL, ?, 'h', 0, 'active', 't')",
            (registered,),
        )
        conn.execute(
            "INSERT INTO document_blobs (document_id, content, byte_size, stored_at) VALUES (?, ?, 25, 't')",
            (added.lastrowid, b"belongs to another folder"),
        )
        conn.commit()

    response = _delete(client, headers, registered)

    assert response.status_code == 200, response.text
    assert foreign.read_bytes() == b"belongs to another folder", "a file outside the documents folder was removed"
    assert _stored_bytes() == [], "the registry's own copy of it was not removed"
    assert registered not in _listed(client, headers)


def test_a_path_that_is_not_a_document_touches_nothing(signed_in, tmp_path):
    client, headers = signed_in
    victim = tmp_path / "victim.txt"
    victim.write_text("keep me")
    documents = Path(os.environ["PIP_DOCUMENTS_ROOT"])

    outside = _delete(client, headers, str(victim))
    sideways = _delete(client, headers, str(documents / ".." / ".." / "victim.txt"))

    assert outside.status_code == 404 and sideways.status_code == 404
    assert victim.read_text() == "keep me"


def test_a_file_that_cannot_be_removed_keeps_the_document_and_says_so(signed_in, monkeypatch):
    """
    The person asked for it to be gone. If the file is held open by something and
    cannot be removed, saying "removed" would be untrue, and forgetting the
    document first would leave a file nothing in the app can reach. So nothing
    is forgotten, they are told, and trying again works.
    """
    client, headers = signed_in
    file_path = _upload(client, headers)
    real_unlink = Path.unlink

    def held_open(self, *args, **kwargs):
        if self.name == "budget.txt":
            raise PermissionError(13, "The process cannot access the file because it is being used by another process")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", held_open)
    refused = _delete(client, headers, file_path)
    monkeypatch.setattr(Path, "unlink", real_unlink)

    assert refused.status_code == 500, refused.text
    assert "budget.txt" in refused.json()["detail"] and "could not be removed" in refused.json()["detail"], refused.text
    assert file_path in _listed(client, headers), "the document was forgotten although its file is still there"
    assert [row["file_path"] for row in _stored_bytes()] == [file_path]

    retried = _delete(client, headers, file_path)

    assert retried.status_code == 200, retried.text
    assert not Path(file_path).exists()
    assert _stored_bytes() == []


def test_a_sign_out_in_the_middle_of_a_delete_removes_nothing(signed_in):
    """
    The index refuses without a key (IndexLockedError), and a sign-out can land
    after the registry lookup. The file must not have been touched by then: the
    person is signed out, the document is still there, and nothing is half-done.
    """
    client, headers = signed_in
    file_path = _upload(client, headers)

    with server._conn() as conn:
        session_key.lock()
        with pytest.raises(vector_store.IndexLockedError):
            vector_store.delete_document(conn, file_path)

    assert Path(file_path).read_bytes() == SECRET, "a locked profile lost the document's file"


# --- controls: what must not change ------------------------------------------


def test_control_a_document_whose_file_is_already_gone_is_still_deleted(signed_in):
    client, headers = signed_in
    file_path = _upload(client, headers)
    Path(file_path).unlink()

    response = _delete(client, headers, file_path)

    assert response.status_code == 200, response.text
    assert _stored_bytes() == []
    assert file_path not in _listed(client, headers)


def test_control_a_deleted_document_is_not_found_again(signed_in):
    client, headers = signed_in
    file_path = _upload(client, headers)
    assert _delete(client, headers, file_path).status_code == 200

    assert _delete(client, headers, file_path).status_code == 404


def test_control_a_name_can_be_uploaded_again_after_its_document_was_deleted(signed_in):
    """Visible: the first upload's file used to stay, so the second was stored as "budget (1).txt"."""
    client, headers = signed_in
    first = _upload(client, headers)
    assert _delete(client, headers, first).status_code == 200

    second = _upload(client, headers, content=b"A newer budget: QUOKKA-8 is 52,000.")

    assert second == first
    assert Path(second).read_bytes() == b"A newer budget: QUOKKA-8 is 52,000."
    assert _listed(client, headers) == [second]
    assert [row["file_path"] for row in _stored_bytes()] == [second]
