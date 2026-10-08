"""
Shared by the tests of the hunt for unrecorded import/export defects (FREEZE_LIST 7.29): a real,
marked .pipbak made by the real export script with a chosen identity name and password, and the
first-run import call. Not collected as tests (the leading underscore).
"""

from backend.tests.test_first_run_import import LIVE_KEY, _load  # noqa: F401
from backend.memory import conversation_store, decision_log, profile_store

NEW = "a-brand-new-live-password"
OLD = "the-backup-password"

NON_ASCII_PASSWORDS = [
    "päss wörd ünï",
    "密码密码密码密码",
    "😀😀😀😀😀😀😀😀",
    "पासवर्डपासवर्ड",
]


def _backup(tmp_path, monkeypatch, *, name="BatMan", password=OLD, filename="carried.pipbak"):
    """A real marked .pipbak made by the real export script, with a chosen identity name and password."""
    source = tmp_path / f"source-{filename}.db"
    conn = profile_store.get_connection(str(source), db_key=LIVE_KEY)
    profile_store.initialize_schema(conn)
    profile_store.complete_onboarding(conn, name=name, language_preference="English", skills=[])
    decision_log.insert_decision(conn, text="probe", reasoning="probe")
    cid = conversation_store.create_conversation(conn)
    conversation_store.append_message(conn, cid, "user", "hello")
    conn.commit()
    conn.close()
    export = _load("export_backup")
    out = tmp_path / filename
    monkeypatch.setenv("PIP_DB_KEY", LIVE_KEY)
    monkeypatch.setattr(export.getpass, "getpass", lambda prompt="": password)
    monkeypatch.setattr(export.sys, "argv", ["export_backup.py", "--db-path", str(source), "--out", str(out)])
    export.main()
    monkeypatch.delenv("PIP_DB_KEY")
    return out


def _import(client, headers, path, backup_password=OLD, new_password=NEW):
    return client.post(
        "/api/v1/backup/import",
        json={"path": str(path), "backup_password": backup_password, "new_password": new_password},
        headers=headers,
    )
