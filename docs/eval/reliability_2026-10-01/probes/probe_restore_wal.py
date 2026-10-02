"""
PROBE: an in-app restore installed over a profile whose database still has a
-wal sidecar (uncheckpointed writes - a crash, a force-kill, or a shutdown
that did not checkpoint). restore._install() moves pip.db and salt.bin only.
"""
import os
import shutil
from pathlib import Path

import pytest

from backend.core import db_key, restore
from backend.memory import profile_store

BACKUP = Path(os.environ.get("PIP_PROBE_BACKUP", "zarqa-1.pipbak"))  # produced by journey_CD.py
OLD_PW, NEW_PW, BACKUP_PW = "old-profile-pw-1", "restored-new-pw-2", "backup-pw-zz9"


def _old_profile(target: Path, leave_wal: bool):
    """The profile being replaced, frozen in the state a crash leaves it in."""
    work = target.parent / "live"
    work.mkdir(parents=True)
    salt = db_key.create_salt(work / "salt.bin")
    key = db_key.derive_key(OLD_PW, salt)
    conn = profile_store.get_connection(str(work / "pip.db"), key)
    conn.execute("PRAGMA wal_autocheckpoint = 0")
    profile_store.initialize_schema(conn)
    conn.commit()
    target.mkdir(exist_ok=True)
    for name in ("pip.db", "pip.db-wal", "salt.bin"):
        if (work / name).exists() and (leave_wal or name != "pip.db-wal"):
            shutil.copy2(work / name, target / name)  # snapshot while the connection is still open
    if not leave_wal:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        shutil.copy2(work / "pip.db", target / "pip.db")
    conn.close()
    return [p.name for p in target.iterdir()]


@pytest.mark.parametrize("leave_wal", [False, True], ids=["control-no-wal", "stale-wal"])
def test_RW1_restored_profile_opens_with_its_new_password(tmp_path, leave_wal):
    if not BACKUP.exists():
        pytest.skip("journey_CD backup not present")
    target = tmp_path / "profiles" / "p"
    before = _old_profile(target, leave_wal)
    staged = restore.stage_restore(str(BACKUP), BACKUP_PW, NEW_PW,
                                   db_path=str(target / "pip.db"), salt_path=str(target / "salt.bin"))
    installed = restore.drain_pending_restore()
    after = sorted(p.name for p in target.iterdir())
    new_key = db_key.derive_key(NEW_PW, (target / "salt.bin").read_bytes())
    opens_new = db_key.verify_key(str(target / "pip.db"), new_key)
    rows = None
    if opens_new:
        c = profile_store.get_connection(str(target / "pip.db"), new_key)
        rows = {t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("conversations", "messages", "decision_log", "identity")}
        c.close()
    old_salt = next(target.glob("salt.bin.superseded-*")).read_bytes()
    opens_old = db_key.verify_key(str(target / "pip.db"), db_key.derive_key(OLD_PW, old_salt))
    print(f"\n[{'stale-wal' if leave_wal else 'control'}] files before={sorted(before)} staged_rows={staged['rows']} installed={bool(installed)}")
    print(f"  files after={after}")
    print(f"  opens with NEW password: {opens_new}; rows={rows}; opens with OLD password+old salt: {opens_old}")
    assert opens_new, "the restored profile does not open with the password the restore was given"
    assert rows and rows["messages"] > 0 and rows["decision_log"] > 0
