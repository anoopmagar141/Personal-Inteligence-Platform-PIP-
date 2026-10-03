"""
D-17 probe: an export taken from the Backup screen while PIP is running.

The real launcher and the real export_backup.py, in a throwaway installation,
against that installation's own running backend. export_backup.py counts rows,
asks for the backup password, then exports and requires the counts to match
exactly. Here the application writes one row while the backup password is
being typed (a decision, through the API) - standing in for what the journey
caught it doing on its own: a session snapshot and a trace row written as a
chat closed.

    python probe_export_while_running.py <empty dir> [commit, default HEAD]

Three runs, each on a fresh installation:
  control  - nothing written during the prompt: expect exit 0, "verified".
  write    - one row written during the prompt: records exit code, message,
             whether a file was left, and whether that file is a usable backup.
  retry    - the same person trying again the same day: records the outcome.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import journey_migration as jm  # noqa: E402
from journey_migration import API, BACKUP_PW, InstBackend, make_installation, new_profile  # noqa: E402

import sqlcipher3  # noqa: E402


def export(inst, answers):
    import subprocess
    before = set((inst / "data").glob("pip_backup_*.pipbak"))
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(inst / "scripts" / "export_pip.ps1")],
        input="\n", capture_output=True, text=True, errors="replace", env=jm.script_env(answers), timeout=600,
    )
    after = sorted((inst / "data").glob("pip_backup_*.pipbak"))
    return r, after, sorted(set(after) - before)


def opens_with(path, password):
    try:
        c = sqlcipher3.connect(str(path))
        c.execute("PRAGMA key = '" + password.replace("'", "''") + "'")
        ok = c.execute("PRAGMA integrity_check").fetchone()[0]
        decisions = [r[0] for r in c.execute("SELECT decision_text FROM decision_log ORDER BY decision_text")]
        c.close()
        return {"integrity": ok, "decisions": decisions}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def tail(r):
    out = (r.stdout + "\n" + r.stderr).strip().splitlines()
    return [l.strip() for l in out if l.strip()][-6:]


def main(base: Path, commit: str = "HEAD"):
    base.mkdir(parents=True)
    jm.export_commit(base, commit)
    results = {"commit": jm.COMMIT}
    for case in ("control", "write"):
        inst = make_installation(base / case)
        b = InstBackend(inst)
        b.start()
        new_profile(b, "Zarqa Venn", "zarqa-live-pw-1")
        b.post(f"{API}/decision/create", {"text": "Use FastAPI for the thesis backend"})
        second = BACKUP_PW
        if case == "write":
            second = {"answer": BACKUP_PW, "post": b.url(f"{API}/decision/create"), "token": b.token,
                      "json": {"text": "Written while the backup password was typed"}}
        r, all_files, new = export(inst, ["zarqa-live-pw-1", second, BACKUP_PW])
        results[case] = {
            "exit": r.returncode,
            "said_nothing_written": "Nothing was written" in r.stdout + r.stderr,
            "said_verified": "verified: integrity ok" in r.stdout,
            "files_left": [p.name for p in new],
            "left_file_opens": opens_with(new[0], BACKUP_PW) if new else None,
            "tail": tail(r),
        }
        if case == "write":
            r2, _, new2 = export(inst, ["zarqa-live-pw-1", BACKUP_PW, BACKUP_PW])
            results["retry same day"] = {"exit": r2.returncode, "new_files": [p.name for p in new2], "tail": tail(r2)}
        b.graceful()
    print(json.dumps(results, indent=2))
    (base / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), sys.argv[2] if len(sys.argv) > 2 else "HEAD")
