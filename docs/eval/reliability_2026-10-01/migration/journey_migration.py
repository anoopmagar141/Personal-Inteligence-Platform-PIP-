"""
End-to-end migration journey, re-run after the D-01 and D-03 fixes.

Real backend processes (uvicorn, embedding stand-in), a live local model for
chat, the REAL export launcher (scripts/export_pip.ps1 -> export_backup.py)
and the REAL shortcut restore launcher (restore_pip.ps1 -> restore_backup.py).
Each machine is a throwaway installation: copies of scripts/, backend/,
shared/ and config/, a real interpreter in .venv, and its own data/. Only the
console password prompts are answered by a test hook (sitecustomize.py).

Never touches the repository's data/: every default data path is computed from
the module's own location, so a copied backend resolves inside its copy; the
launchers run with PIP_* and PYTHONPATH scrubbed; and the real data/ is
fingerprinted (names, sizes, times - never contents) before and after.

    python journey_migration.py <variant> <empty dir> [commit, default HEAD]

Variants (FREEZE_LIST section 7.24 has the results):
    main-killed        export, in-app restore, force-kill with an open chat,
                       verify, keep using, export again, restore again
    main-graceful      the same with a clean stop
    shortcut           export, then restore_pip.ps1 onto a bare installation
    same-machine       restore where the original document still exists (D-07)
    inputs-and-delete  11 bad backups/passwords, each on its own; D-14 in a
                       real process, with a control
    staging            an empty file staged and installed (D-18); a restore
                       staged twice, and for two profiles; whose restore the
                       status and cancel routes act on; an orphaned staged
                       copy and its profile's deletion (D-19); an empty file
                       through the shortcut

    multi-profile-export  two profiles, the app launched on the first, the
                       export taken from the second with the first's PIP_*
    restore-over-used  an in-app restore over a profile with its own documents
    shortcut-shipped   the shortcut as installed (no arguments): two backups
                       from one day; onto an installation with a named profile

Needs Ollama with qwen2.5:7b for the variants that chat. sitecustomize.py,
beside this file, is the test hook the throwaway interpreters load.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx

EVAL = Path(__file__).resolve().parents[1]
REPO = EVAL.parents[2]
sys.path.insert(0, str(EVAL))
from journey import API, PY, Backend, turn  # noqa: E402

HERE = Path(__file__).resolve().parent
DOC1 = b"Heliotrope design note. The sync engine codename is QUOKKA-7 and it batches writes every 40 seconds."
DOC2 = b"Second note, written after the restore. The release codename is MARMOT-9."
BACKUP_PW = "backup-pw-zz9"
RESULTS: list[dict] = []


def check(name, ok, detail=""):
    RESULTS.append({"check": name, "ok": bool(ok), "detail": str(detail)[:600]})
    print(("PASS " if ok else "FAIL ") + name + (f" :: {str(detail)[:400]}" if detail else ""), flush=True)


def note(name, value):
    print(f"[{name}] {json.dumps(value, default=str)[:900]}", flush=True)


# --- safety ------------------------------------------------------------------

REAL_DATA = REPO / "data"


def real_data_fingerprint():
    return sorted(
        (str(p.relative_to(REAL_DATA)), p.stat().st_size, p.stat().st_mtime_ns)
        for p in REAL_DATA.rglob("*") if p.is_file()
    )


# --- machines ----------------------------------------------------------------

# Every installation is built from one commit, exported once per run, never
# from the working tree: another session editing the checkout mid-run would
# otherwise put its half-finished change into some machines and not others.
SOURCE: Path | None = None
COMMIT = ""


def export_commit(base: Path, commit: str) -> None:
    global SOURCE, COMMIT
    COMMIT = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--verify", f"{commit}^{{commit}}"],
                            capture_output=True, text=True, check=True).stdout.strip()
    SOURCE = base / "source"
    SOURCE.mkdir(parents=True)
    tar = base / "source.tar"
    subprocess.run(["git", "-C", str(REPO), "archive", "--format=tar", "-o", str(tar), COMMIT,
                    "backend", "shared", "config", "scripts"], check=True)
    import tarfile
    with tarfile.open(tar) as t:
        t.extractall(SOURCE, filter="data")
    tar.unlink()
    print(f"[source] {COMMIT}", flush=True)


def make_installation(root: Path) -> Path:
    root.mkdir(parents=True)
    for d in ("backend", "shared", "config"):
        shutil.copytree(SOURCE / d, root / d, ignore=shutil.ignore_patterns("__pycache__", "tests"))
    (root / "scripts").mkdir()
    # _backend.ps1 is dot-sourced by restore_pip.ps1 (and launch_pip.ps1); a copy that
    # leaves it out fails at the first line of the shortcut, which is how this list
    # was found to be one file short once D-09 added it.
    for f in ("export_pip.ps1", "restore_pip.ps1", "_python.ps1", "_profiles.ps1", "_backend.ps1",
              "export_backup.py", "restore_backup.py", "_venv.py"):
        shutil.copyfile(SOURCE / "scripts" / f, root / "scripts" / f)
    subprocess.run([str(PY), "-m", "venv", "--without-pip", str(root / ".venv")], check=True)
    site = root / ".venv" / "Lib" / "site-packages"
    # Python 3.12 reads .pth files in the locale encoding, so a run under a path
    # with non-ASCII characters needs this one written in it too.
    (site / "zz_pip_test.pth").write_text(
        f"{REPO / '.venv' / 'Lib' / 'site-packages'}\n{HERE}\n{EVAL}\n", encoding="locale"
    )
    (root / "data").mkdir()
    probe = subprocess.run(
        [str(root / ".venv" / "Scripts" / "python.exe"), "-c",
         "import sys, backend, backend.core.auth as a, sqlcipher3; "
         "print(';'.join(backend.__path__)); print(a.TOKEN_PATH); print('sitecustomize' in sys.modules, 'pip_embed_shim' in sys.modules)"],
        cwd=str(root), capture_output=True, text=True, env=clean_env(), timeout=120,
    )
    lines = probe.stdout.split("\n")
    assert probe.returncode == 0 and all(str(root) in x for x in lines[0].split(';') + [lines[1]]) and lines[2] == "True True", \
        f"installation does not resolve inside itself: {probe.stdout} {probe.stderr[-500:]}"
    return root


def clean_env():
    return {k: v for k, v in os.environ.items() if not k.startswith("PIP_") and k != "PYTHONPATH"}


def script_env(answers):
    env = clean_env()
    env["PIP_TEST_ANSWERS"] = json.dumps(answers)
    return env


class InstBackend(Backend):
    """This installation's own copied backend, started the way launch_pip.ps1
    starts it: its own interpreter, the installation root as the working
    directory, and only the profile variables Set-PipProfileEnvironment sets
    for the last-opened profile. Everything else falls to the module defaults,
    which a copied backend resolves inside its own installation."""

    def __init__(self, inst: Path):
        super().__init__(inst / "data")
        self.inst = inst

    def launcher_profile_env(self):
        # UTF-8 out, UTF-8 in: a redirected PowerShell writes in the console's
        # OEM code page, which Python would read as cp1252 - and a path with
        # "u-umlaut" (0x81 in OEM, undefined in cp1252) then reads as nothing.
        ps = ("[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false; "
              f". '{self.inst / 'scripts' / '_profiles.ps1'}'; "
              f"$p = Resolve-PipLastProfile -Root '{self.inst}'; "
              "if ($p) { Set-PipProfileEnvironment -Paths $p | Out-Null }; "
              "@{PIP_DB_PATH=$env:PIP_DB_PATH; PIP_SALT_PATH=$env:PIP_SALT_PATH; PIP_CHROMA_PATH=$env:PIP_CHROMA_PATH; "
              "PIP_DOCUMENTS_ROOT=$env:PIP_DOCUMENTS_ROOT; PIP_PROFILE=$env:PIP_PROFILE} | ConvertTo-Json -Compress")
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                           capture_output=True, encoding="utf-8", env=clean_env(), timeout=60)
        if r.returncode != 0:
            raise RuntimeError(f"profile resolution failed: {r.stderr}")
        return {k: v for k, v in json.loads(r.stdout.strip()).items() if v}

    def start(self, wait=120):
        env = clean_env()
        self.profile_env = self.launcher_profile_env()
        env.update(self.profile_env)
        env["PYTHONUNBUFFERED"] = "1"
        for v in self.profile_env.values():
            assert str(self.inst) in v or "\\" not in v, f"launcher pointed outside the installation: {v}"
        log_file = open(self.root / f"backend-{int(time.time() * 1000)}.log", "w")
        self.proc = subprocess.Popen(
            [str(self.inst / ".venv" / "Scripts" / "python.exe"), "-m", "uvicorn", "backend.api.server:app",
             "--host", "127.0.0.1", "--port", str(self.port)],
            cwd=str(self.inst), env=env, stdout=log_file, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        import journey
        journey._ALL.append(self.proc)
        token_file = self.root / "api_token.txt"
        t0 = time.time()
        while time.time() - t0 < wait:
            if self.proc.poll() is not None:
                raise RuntimeError(f"backend exited {self.proc.returncode}")
            try:
                tok = token_file.read_text().strip()
                r = httpx.get(self.url(f"{API}/auth/state"), headers={"Authorization": f"Bearer {tok}"}, timeout=2)
                if r.status_code == 200:
                    self.token = tok
                    return time.time() - t0
            except Exception:
                pass
            time.sleep(0.5)
        raise TimeoutError("backend did not come up")


def export_via_launcher(inst: Path, live_pw: str, inherited: dict | None = None):
    """inherited: the PIP_* the app's own process would pass down to the console
    it starts (launch_pip.ps1 sets them for the profile opened at launch)."""
    before = set((inst / "data").glob("pip_backup_*.pipbak"))
    env = script_env([live_pw, BACKUP_PW, BACKUP_PW])
    env.update(inherited or {})
    r = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(inst / "scripts" / "export_pip.ps1")],
        input="\n", capture_output=True, text=True, errors="replace", env=env, timeout=600,
    )
    new = sorted(set((inst / "data").glob("pip_backup_*.pipbak")) - before)
    return r, new


def restore_via_shortcut(inst: Path, backup: Path | None, new_pw: str, shipped: bool = False):
    """shipped=False: --from and --yes, as the first runs did. shipped=True: what the
    desktop shortcut runs (installer/PIP.iss, install_shortcuts.ps1) - no arguments,
    the script's own pick, and a typed "yes"."""
    args = [] if shipped else ["--from", str(backup), "--yes"]
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(inst / "scripts" / "restore_pip.ps1"), *args],
        input="yes\n\n" if shipped else "\n", capture_output=True, text=True, errors="replace",
        env=script_env([BACKUP_PW, new_pw, new_pw]), timeout=900,
    )


# --- app helpers ---------------------------------------------------------------

def new_profile(b, name, pw):
    slug = b.post(f"{API}/auth/profiles", {"name": name}).json()["slug"]
    r = b.post(f"{API}/auth/setup", {"password": pw, "profile": slug})
    assert r.status_code == 200, r.text
    return slug


def upload(b, name, data):
    return httpx.post(b.url(f"{API}/rag/upload"), headers=b.h(), files={"file": (name, data, "text/plain")}, timeout=300)


def sign_in(b, slug, pw):
    b.post(f"{API}/auth/profile", {"slug": slug})
    return b.post(f"{API}/auth/unlock", {"password": pw, "profile": slug}).status_code


def snapshot(b):
    convs = b.get(f"{API}/conversations").json()
    return {
        "conversations": {
            c["id"]: [(m["role"], m["content"]) for m in b.get(f"{API}/conversations/{c['id']}/messages").json()]
            for c in convs
        },
        "decisions": sorted((d["decision_text"], d.get("reasoning"))
                            for d in b.get(f"{API}/decision/search", params={"q": ""}).json()),
        "projects": sorted((p["name"], p.get("description")) for p in b.get(f"{API}/projects").json()),
        "active_model": b.get(f"{API}/llm/active-model").json(),
        "profile": {f"{p.get('table')}.{p.get('field')}": p.get("value") for p in b.get(f"{API}/memory/profile").json()},
        "documents": sorted(Path(d["file_path"]).name for d in b.get(f"{API}/rag/documents").json()),
    }


def marker_value(b):
    """The profile's "marker" field, or None when it has none (the route answers null)."""
    return (b.get(f"{API}/memory/profile/marker").json() or {}).get("value")


def doc_paths(b):
    return [d["file_path"] for d in b.get(f"{API}/rag/documents").json()]


def retrieves(b, query, token, wait=120):
    deadline = time.time() + wait
    while True:
        hits = b.post(f"{API}/rag/query", {"query": query, "threshold": 0.0}).json()
        if isinstance(hits, list) and any(token in (h.get("chunk_text") or "") for h in hits):
            return True
        if time.time() > deadline:
            return False
        time.sleep(3)


def files_written_back(b, inst, expected: dict, wait=120):
    """Every registered document is a file under this machine's data/ holding the
    bytes that were uploaded. Polled: the sign-in catch-up writes them back."""
    deadline = time.time() + wait
    while True:
        paths = doc_paths(b)
        state = {}
        for p in paths:
            q = Path(p)
            state[q.name] = (str(q).startswith(str(inst / "data")), q.exists() and q.read_bytes() == expected.get(q.name))
        if state and all(a and c for a, c in state.values()) and set(state) == set(expected):
            return True, state
        if time.time() > deadline:
            return False, {"paths": paths, "state": state}
        time.sleep(3)


def compare(label, before, after):
    for key in before:
        check(f"{label}: {key} identical", before[key] == after.get(key),
              "" if before[key] == after.get(key) else {"before": before[key], "after": after.get(key)})


# --- machine 1: the user's own computer --------------------------------------

def populate(base: Path, chat=True):
    inst1 = make_installation(base / "machine1")
    b1 = InstBackend(inst1)
    b1.start()
    slug = new_profile(b1, "Zarqa Venn", "zarqa-live-pw-1")
    b1.post(f"{API}/onboarding/complete", {"name": "Zarqa Venn", "language_preference": "English"})
    b1.post(f"{API}/llm/active-model", {"model_name": "qwen2.5:7b"})
    b1.post(f"{API}/projects", {"name": "Heliotrope", "description": "sync engine"})
    b1.post(f"{API}/decision/create", {"text": "Use FastAPI for the thesis backend", "reasoning": "native async"})
    b1.post(f"{API}/memory/correct", {"field": "favourite_editor", "value": "Helix"})
    check("m1: document uploaded", upload(b1, "heliotrope.txt", DOC1).status_code == 200)
    if chat:
        with b1.ws() as ws:
            ws.recv(timeout=30)
            t1 = turn(ws, "In one sentence: what is a sync engine?")
            t2 = turn(ws, "And in one sentence: why batch writes?")
        check("m1: two chat turns answered by the live model", t1["final"] == t2["final"] == "done", [t1, t2])
    check("m1: retrieval finds the document before export", retrieves(b1, "QUOKKA-7 sync engine codename", "QUOKKA-7"))
    s1 = snapshot(b1)
    note("m1 snapshot", s1)
    return inst1, b1, slug, s1


def export_and_move_away(base, inst, b, profile_name, live_pw, label):
    r, new = export_via_launcher(inst, live_pw)
    check(f"{label}: export launcher exits 0", r.returncode == 0, (r.stdout + r.stderr)[-500:])
    check(f"{label}: export launcher chose the signed-in profile", f"Profile: {profile_name}" in r.stdout,
          r.stdout[-300:])
    check(f"{label}: exactly one new .pipbak written", len(new) == 1, new)
    if len(new) != 1:
        raise SystemExit("no backup to carry on with")
    # The driver carries on after a failed verification (D-17) with the file it
    # left, so whether each restore below used a verified export is recorded.
    note(f"{label}: the carried file passed the export's own verification", r.returncode == 0)
    raw = new[0].read_bytes()
    check(f"{label}: the backup holds no plaintext", not any(m in raw for m in
          (b"QUOKKA-7", b"MARMOT-9", b"Zarqa", b"FastAPI", b"SQLite format 3")))
    carried = base / "transfer" / f"{label}.pipbak"
    carried.parent.mkdir(exist_ok=True)
    shutil.copyfile(new[0], carried)
    b.graceful()
    # Another computer: the old machine's absolute paths must not exist there.
    away = inst.with_name(inst.name + "-elsewhere")
    inst.rename(away)
    return carried, away


def restore_in_app(base, name, backup, restart, new_pw, label):
    inst = make_installation(base / name)
    b = InstBackend(inst)
    b.start()
    slug = new_profile(b, "Zed", "zed-live-pw-3")
    b.post(f"{API}/memory/correct", {"field": "marker", "value": "ZED-ORIGINAL"})
    r = b.post(f"{API}/backup/restore", {"path": str(backup), "backup_password": BACKUP_PW, "new_password": new_pw})
    check(f"{label}: restore staged in the app", r.status_code == 200 and r.json().get("pending") is True, r.text[:300])

    if restart == "killed":
        # The usual way the next start is reached: the backend ends without a
        # checkpoint, with a chat still open (FREEZE_LIST §7.16 D-09, D-01).
        b.post(f"{API}/llm/active-model", {"model_name": "qwen2.5:7b"})
        ws = b.ws()
        ws.recv(timeout=30)
        t = turn(ws, "Say the word 'before' and nothing else.")
        check(f"{label}: a chat turn on the old profile before the kill", t["final"] == "done", t)
        wal = inst / "data" / "profiles" / slug / "pip.db-wal"
        note(f"{label} wal before kill", {"exists": wal.exists(), "bytes": wal.stat().st_size if wal.exists() else 0})
        b.kill()
        try:
            ws.close()
        except Exception:
            pass
    else:
        b.graceful()
    b.start()

    check(f"{label}: the replaced profile's old password no longer opens it",
          sign_in(b, slug, "zed-live-pw-3") == 401)
    check(f"{label}: the backup's password does not open it", sign_in(b, slug, BACKUP_PW) == 401)
    check(f"{label}: the new password opens the restored profile", sign_in(b, slug, new_pw) == 200)
    kept = sorted(p.name for p in (inst / "data" / "profiles" / slug).glob("*.superseded-*"))
    note(f"{label} kept beside the restored profile", kept)
    check(f"{label}: the replaced database was kept, not deleted",
          any(n.startswith("pip.db.superseded-") and not n.endswith(("-wal", "-shm", "-journal")) for n in kept), kept)
    return inst, b, slug


def verify_restored(label, b, inst, expected_snapshot, expected_docs, tokens):
    ok, state = files_written_back(b, inst, expected_docs)
    check(f"{label}: every document is back as a file under this machine's data, byte for byte", ok, state)
    for query, token in tokens:
        check(f"{label}: retrieval finds {token} after the restore", retrieves(b, query, token))
    compare(label, expected_snapshot, snapshot(b))


def main_journey(base: Path, restart: str):
    inst1, b1, _, s1 = populate(base)
    bak1, _ = export_and_move_away(base, inst1, b1, "Zarqa Venn", "zarqa-live-pw-1", "export-1")

    inst2, b2, slug2 = restore_in_app(base, "machine2", bak1, restart, "zarqa-new-pw-4", f"restore-1 ({restart})")
    verify_restored("machine2", b2, inst2, s1, {"heliotrope.txt": DOC1}, [("QUOKKA-7 sync engine codename", "QUOKKA-7")])

    # Keep using the restored profile, then carry it on again.
    b2.post(f"{API}/llm/active-model", {"model_name": "qwen2.5:7b"})
    with b2.ws() as ws:
        ws.recv(timeout=30)
        t = turn(ws, "Say the word 'continuation' and nothing else.")
    check("machine2: the restored profile answers a new chat turn", t["final"] == "done", t)
    b2.post(f"{API}/decision/create", {"text": "Ship the beta in May"})
    check("machine2: a new document after the restore", upload(b2, "marmot.txt", DOC2).status_code == 200)
    check("machine2: retrieval finds the new document", retrieves(b2, "MARMOT-9 release codename", "MARMOT-9"))
    s2 = snapshot(b2)
    # machine2 has exactly one profile, in its own folder: the D-03 case.
    bak2, _ = export_and_move_away(base, inst2, b2, "Zed", "zarqa-new-pw-4", "export-2 (one-profile install)")

    inst3, b3, _ = restore_in_app(base, "machine3", bak2, "graceful", "zarqa-third-pw-6", "restore-2")
    verify_restored("machine3", b3, inst3, s2, {"heliotrope.txt": DOC1, "marmot.txt": DOC2},
                    [("QUOKKA-7 sync engine codename", "QUOKKA-7"), ("MARMOT-9 release codename", "MARMOT-9")])
    b3.graceful()


def shortcut_journey(base: Path):
    inst1, b1, _, s1 = populate(base, chat=True)
    bak, _ = export_and_move_away(base, inst1, b1, "Zarqa Venn", "zarqa-live-pw-1", "export-1")

    # A computer with PIP installed and nothing in it yet: the desktop shortcut.
    inst4 = make_installation(base / "machine4")
    r = restore_via_shortcut(inst4, bak, "zarqa-shortcut-pw-7")
    check("shortcut: restore launcher exits 0", r.returncode == 0, (r.stdout + r.stderr)[-600:])
    check("shortcut: restored into the original layout", (inst4 / "data" / "pip.db").exists()
          and (inst4 / "data" / "salt.bin").exists(), sorted(p.name for p in (inst4 / "data").iterdir()))
    b4 = InstBackend(inst4)
    b4.start()
    listed = [p["slug"] for p in b4.get(f"{API}/auth/profiles").json()["profiles"]]
    check("shortcut: the restored profile is offered at sign-in", "default" in listed, listed)
    check("shortcut: the new password opens it", sign_in(b4, "default", "zarqa-shortcut-pw-7") == 200)
    verify_restored("machine4", b4, inst4, s1, {"heliotrope.txt": DOC1}, [("QUOKKA-7 sync engine codename", "QUOKKA-7")])

    # The shortcut restores into the original layout (data/pip.db), so the
    # natural next step - keep using it, export, restore elsewhere - takes
    # export_pip.ps1's other branch.
    b4.post(f"{API}/memory/correct", {"field": "marker", "value": "LEGACY-CONTINUED"})
    s4 = snapshot(b4)
    # Under Windows PowerShell 5.1 Resolve-PipLastProfile's one-profile branch
    # never runs, so a lone legacy profile is reached through last_used and
    # named "Default" - the same data/pip.db and salt (FREEZE_LIST section 7.18).
    bak4, _ = export_and_move_away(base, inst4, b4, "Default", "zarqa-shortcut-pw-7", "export from the original layout")
    inst5, b5, _ = restore_in_app(base, "machine5", bak4, "graceful", "zarqa-fifth-pw-9", "restore from the original layout")
    verify_restored("machine5", b5, inst5, s4, {"heliotrope.txt": DOC1}, [("QUOKKA-7 sync engine codename", "QUOKKA-7")])
    b5.graceful()


def staged_files(inst):
    data = inst / "data"
    return sorted(str(p.relative_to(data)) for p in data.rglob("*")
                  if p.name == "pending-restore.json" or (p.name.startswith("restore-") and ".tmp" in p.name))


def marker(inst):
    p = inst / "data" / "pending-restore.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def delete_profile(b, slug, pw):
    return httpx.request("DELETE", b.url(f"{API}/auth/profiles/{slug}"), headers=b.h(), json={"password": pw}, timeout=120)


def inputs_and_delete_journey(base: Path):
    inst1, b1, _, s1 = populate(base, chat=False)
    bak, _ = export_and_move_away(base, inst1, b1, "Zarqa Venn", "zarqa-live-pw-1", "export-1")

    inst = make_installation(base / "machine5")
    b = InstBackend(inst)
    b.start()
    yara = new_profile(b, "Yara", "yara-live-pw-8")
    b.post(f"{API}/memory/correct", {"field": "marker", "value": "YARA-KEEP"})

    # 1. Backups and passwords that must be refused, each leaving nothing staged.
    bad = base / "bad-inputs"
    bad.mkdir()
    raw = bak.read_bytes()
    flipped = bytearray(raw)
    flipped[len(raw) // 2] ^= 0x01

    def put(name, data):
        (bad / name).write_bytes(data)
        return str(bad / name)

    cases = [
        ("a file that does not exist", str(bad / "nope.pipbak"), BACKUP_PW, "fine-new-pw-9"),
        ("a folder", str(bad), BACKUP_PW, "fine-new-pw-9"),
        ("an empty file", put("empty.pipbak", b""), BACKUP_PW, "fine-new-pw-9"),
        ("a text file named .pipbak", put("notes.pipbak", b"just some notes\n" * 64), BACKUP_PW, "fine-new-pw-9"),
        ("the backup cut in half", put("half.pipbak", raw[: len(raw) // 2]), BACKUP_PW, "fine-new-pw-9"),
        ("the backup with one bit flipped", put("flipped.pipbak", bytes(flipped)), BACKUP_PW, "fine-new-pw-9"),
        ("the live encrypted database itself", str(inst / "data" / "profiles" / yara / "pip.db"), "yara-live-pw-8", "fine-new-pw-9"),
        ("the wrong backup password", str(bak), "not-the-backup-pw", "fine-new-pw-9"),
        ("no backup password", str(bak), "", "fine-new-pw-9"),
        ("a new password that is too short", str(bak), BACKUP_PW, "short"),
        ("no new password", str(bak), BACKUP_PW, ""),
    ]
    codes = {}
    for label, path, bpw, npw in cases:
        r = b.post(f"{API}/backup/restore", {"path": path, "backup_password": bpw, "new_password": npw})
        codes[label] = r.status_code
        check(f"bad input answered 4xx: {label}", 400 <= r.status_code < 500, f"{r.status_code} {r.text[:200]}")
        check(f"bad input left nothing staged: {label}", marker(inst) is None and not staged_files(inst),
              {"code": r.status_code, "body": r.text[:160], "staged": staged_files(inst)})
        # Each case on its own: whatever one staged is cancelled the app's way,
        # and anything the cancel leaves is recorded and then removed by hand.
        if marker(inst) is not None:
            httpx.request("DELETE", b.url(f"{API}/backup/restore"), headers=b.h(), timeout=60)
            if staged_files(inst):
                note(f"left after the app's own cancel ({label})", staged_files(inst))
        for f in staged_files(inst):
            (inst / "data" / f).unlink()
    note("bad input status codes", codes)
    check("Yara still signed in with her data after every refusal",
          marker_value(b) == "YARA-KEEP",
          b.get(f"{API}/memory/profile/marker").text[:200])

    # 2. D-14 in a real process: a restore staged for a profile that is then deleted.
    b.post(f"{API}/auth/lock")
    zed = new_profile(b, "Zed", "zed-live-pw-3")
    r = b.post(f"{API}/backup/restore", {"path": str(bak), "backup_password": BACKUP_PW, "new_password": "zarqa-new-pw-4"})
    check("D-14: restore staged for Zed", r.status_code == 200, r.text[:200])
    note("staged for Zed", staged_files(inst))
    r = delete_profile(b, zed, "zed-live-pw-3")
    check("D-14: Zed deleted", r.status_code == 200, r.text[:200])
    # Read from disk: the delete signs out, and the status route is locked then.
    check("D-14: the staged restore went with Zed", marker(inst) is None and not staged_files(inst),
          {"marker": marker(inst), "staged": staged_files(inst)})
    b.graceful()
    b.start()
    listed = [p["slug"] for p in b.get(f"{API}/auth/profiles").json()["profiles"]]
    check("D-14: Zed is not back after the restart", zed not in listed, listed)
    zed_dir = inst / "data" / "profiles" / zed
    check("D-14: nothing was installed where Zed was", not (zed_dir / "pip.db").exists(),
          sorted(p.name for p in zed_dir.iterdir()) if zed_dir.exists() else "folder gone")
    check("D-14: Yara opens with her own password", sign_in(b, yara, "yara-live-pw-8") == 200)
    check("D-14: Yara's data is intact", marker_value(b) == "YARA-KEEP")

    # 3. Control: a restore staged for Yara survives another profile's deletion.
    r = b.post(f"{API}/backup/restore", {"path": str(bak), "backup_password": BACKUP_PW, "new_password": "yara-restored-pw-5"})
    check("control: restore staged for Yara", r.status_code == 200, r.text[:200])
    b.post(f"{API}/auth/lock")
    wren = new_profile(b, "Wren", "wren-live-pw-2")
    check("control: Wren deleted", delete_profile(b, wren, "wren-live-pw-2").status_code == 200)
    m = marker(inst)
    check("control: Yara's staged restore survived Wren's deletion",
          m is not None and Path(m["target_db"]) == inst / "data" / "profiles" / yara / "pip.db"
          and all(Path(m[k]).exists() for k in ("db", "salt")), m)
    b.graceful()
    b.start()
    check("control: Yara's old password no longer opens her profile", sign_in(b, yara, "yara-live-pw-8") == 401)
    check("control: the restore was installed for Yara", sign_in(b, yara, "yara-restored-pw-5") == 200)
    verify_restored("control", b, inst, s1, {"heliotrope.txt": DOC1}, [("QUOKKA-7 sync engine codename", "QUOKKA-7")])
    b.graceful()


def staging_journey(base: Path):
    """What the bad-input pass pointed at, each shown to its end:
    1. an empty file staged as a backup, then the restart;
    2. a second restore staged over a first, same profile;
    3. a restore staged for one profile, then another for a second profile;
    5. whose staged restore the status and cancel routes act on;
    6. an orphaned staged copy, and the deletion of its profile;
    4. an empty file through the desktop-shortcut restore (run last, on its
       own installation)."""
    inst1, b1, _, s1 = populate(base, chat=False)
    bak, _ = export_and_move_away(base, inst1, b1, "Zarqa Venn", "zarqa-live-pw-1", "export-1")
    empty = base / "empty.pipbak"
    empty.write_bytes(b"")

    # 1. Empty file, in the app.
    inst = make_installation(base / "machine6")
    b = InstBackend(inst)
    b.start()
    yara = new_profile(b, "Yara", "yara-live-pw-8")
    b.post(f"{API}/onboarding/complete", {"name": "Yara Moss", "language_preference": "English"})
    b.post(f"{API}/memory/correct", {"field": "marker", "value": "YARA-KEEP"})
    b.post(f"{API}/decision/create", {"text": "Yara keeps her own decisions"})
    before = snapshot(b)
    r = b.post(f"{API}/backup/restore", {"path": str(empty), "backup_password": "anything-at-all", "new_password": "empty-new-pw-1"})
    note("empty file: staging answered", {"code": r.status_code, "body": r.text[:200]})
    check("empty file: refused at staging", r.status_code >= 400, r.text[:200])
    b.graceful()
    b.start()
    old_pw = sign_in(b, yara, "yara-live-pw-8")
    note("empty file after restart: old password", old_pw)
    if old_pw != 200:
        new_pw = sign_in(b, yara, "empty-new-pw-1")
        note("empty file after restart: password chosen at staging", new_pw)
    try:
        after = snapshot(b)
    except Exception as e:  # an empty database may not answer every route
        after = {"error": f"{type(e).__name__}: {e}",
                 "routes": {p: b.get(f"{API}{p}").status_code for p in
                            ("/conversations", "/decision/search?q=", "/projects", "/memory/profile", "/rag/documents")}}
    note("empty file after restart: what Yara sees", after)
    note("empty file after restart: auth state", b.get(f"{API}/auth/state").json())
    check("empty file: Yara's data is still what she sees after the restart", after == before,
          {"before": before, "after": after})
    kept = sorted(p.name for p in (inst / "data" / "profiles" / yara).glob("*.superseded-*"))
    note("empty file: kept beside the profile", kept)
    b.post(f"{API}/auth/lock")

    # 2. A second restore staged over a first, same profile.
    zed = new_profile(b, "Zed", "zed-live-pw-3")
    b.post(f"{API}/backup/restore", {"path": str(bak), "backup_password": BACKUP_PW, "new_password": "zed-first-pw-1"})
    first = staged_files(inst)
    # Staged files are named by the second; two stagings inside one second share
    # names and the second overwrites the first. A person is always slower.
    time.sleep(1.2)
    b.post(f"{API}/backup/restore", {"path": str(bak), "backup_password": BACKUP_PW, "new_password": "zed-second-pw-2"})
    second = staged_files(inst)
    note("staged twice, same profile", {"after first": first, "after second": second})
    check("staged twice: only one restore's files remain", len([f for f in second if f.endswith(".tmp.db")]) == 1, second)
    httpx.request("DELETE", b.url(f"{API}/backup/restore"), headers=b.h(), timeout=60)
    check("staged twice: the app's cancel leaves nothing behind", not staged_files(inst), staged_files(inst))
    for f in staged_files(inst):
        (inst / "data" / f).unlink()

    # 3. Staged for Zed, then for Yara: what happens to Zed's?
    r = b.post(f"{API}/backup/restore", {"path": str(bak), "backup_password": BACKUP_PW, "new_password": "zed-restored-pw-3"})
    check("cross-profile: staged for Zed", r.status_code == 200, r.text[:200])
    b.post(f"{API}/auth/lock")
    check("cross-profile: Yara signs in", sign_in(b, yara, "empty-new-pw-1" if old_pw != 200 else "yara-live-pw-8") == 200)
    r = b.post(f"{API}/backup/restore", {"path": str(bak), "backup_password": BACKUP_PW, "new_password": "yara-restored-pw-5"})
    note("cross-profile: staging for Yara while Zed's waits", {"code": r.status_code, "body": r.text[:200],
                                                               "marker": marker(inst), "staged": staged_files(inst)})
    check("cross-profile: Yara is told a restore is waiting, or none is left orphaned",
          r.status_code >= 400 or len([f for f in staged_files(inst) if f.endswith(".tmp.db")]) == 1, staged_files(inst))
    b.graceful()
    b.start()
    zed_now = {pw: sign_in(b, zed, pw) for pw in ("zed-live-pw-3", "zed-restored-pw-3")}
    note("cross-profile after restart: Zed's passwords", zed_now)
    check("cross-profile: Zed's restore was installed, or Zed was told it would not be",
          zed_now.get("zed-restored-pw-3") == 200 or r.status_code >= 400, zed_now)
    b.post(f"{API}/auth/lock")
    note("cross-profile after restart: orphaned staging files", staged_files(inst))

    # 5. Whose restore is it? One marker serves the installation, and the status
    #    and cancel routes act on it for whoever is signed in. Zed stages and
    #    signs out; Yara signs in - which is what her Backup screen loads.
    yara_pw = next(pw for pw in ("yara-restored-pw-5", "empty-new-pw-1", "yara-live-pw-8") if sign_in(b, yara, pw) == 200)
    b.post(f"{API}/auth/lock")
    check("whose: Zed signs in", sign_in(b, zed, "zed-live-pw-3") == 200)
    r = b.post(f"{API}/backup/restore", {"path": str(bak), "backup_password": BACKUP_PW, "new_password": "zed-again-pw-4"})
    check("whose: staged for Zed", r.status_code == 200, r.text[:200])
    zed_staged = staged_files(inst)
    b.post(f"{API}/auth/lock")
    check("whose: Yara signs in", sign_in(b, yara, yara_pw) == 200)
    shown = b.get(f"{API}/backup/restore").json()
    note("whose: the restore status Yara's Backup screen is given", shown)
    check("whose: Yara is not shown Zed's restore as pending for her", shown.get("pending") is not True, shown)
    r = httpx.request("DELETE", b.url(f"{API}/backup/restore"), headers=b.h(), timeout=60)
    note("whose: Yara presses Cancel the restore", {"code": r.status_code, "body": r.text[:200],
                                                    "marker": marker(inst), "staged": staged_files(inst)})
    check("whose: Yara's cancel does not discard Zed's restore",
          marker(inst) is not None and staged_files(inst) == zed_staged,
          {"before": zed_staged, "after": staged_files(inst)})
    if marker(inst) is not None:
        httpx.request("DELETE", b.url(f"{API}/backup/restore"), headers=b.h(), timeout=60)
    for f in staged_files(inst):
        (inst / "data" / f).unlink()

    # 6. An orphaned staged copy, and the deletion of the profile it sits in.
    b.post(f"{API}/auth/lock")
    wren = new_profile(b, "Wren", "wren-live-pw-2")
    for pw in ("wren-first-pw-1", "wren-second-pw-2"):
        b.post(f"{API}/backup/restore", {"path": str(bak), "backup_password": BACKUP_PW, "new_password": pw})
        time.sleep(1.2)   # see "staged twice" above
    httpx.request("DELETE", b.url(f"{API}/backup/restore"), headers=b.h(), timeout=60)
    orphan = staged_files(inst)
    note("orphan: left in Wren's folder after staging twice and cancelling", orphan)
    r = delete_profile(b, wren, "wren-live-pw-2")
    note("orphan: deleting Wren", {"code": r.status_code, "body": r.text[:200]})
    wren_dir = inst / "data" / "profiles" / wren
    left = sorted(p.name for p in wren_dir.iterdir()) if wren_dir.exists() else []
    check("orphan: deleting Wren leaves nothing of Wren behind", not left, {"folder": str(wren_dir), "left": left})
    b.graceful()
    b.start()
    listed = [p["slug"] for p in b.get(f"{API}/auth/profiles").json()["profiles"]]
    left = sorted(p.name for p in wren_dir.iterdir()) if wren_dir.exists() else []
    note("orphan: after the next start", {"profiles": listed, "left in Wren's folder": left})
    check("orphan: nothing of Wren after the next start either", wren not in listed and not left, {"profiles": listed, "left": left})
    b.graceful()

    # 4. Empty file, through the desktop shortcut onto a bare installation.
    inst7 = make_installation(base / "machine7")
    r = restore_via_shortcut(inst7, empty, "shortcut-empty-pw-1")
    note("shortcut empty file", {"exit": r.returncode, "tail": [l for l in (r.stdout + r.stderr).splitlines() if l.strip()][-8:],
                                 "data": sorted(p.name for p in (inst7 / "data").iterdir())})
    check("shortcut empty file: refused", r.returncode != 0)


def multi_profile_journey(base: Path):
    """Export from an installation with two profiles, signed into the second, from
    an app launched while the first was the last opened - so the console inherits
    the first profile's PIP_* (section 7.18's promise: "however many there are")."""
    bo_doc = b"Bo's note. The garden code is WREN-31."
    inst = make_installation(base / "machine1")
    b = InstBackend(inst)
    b.start()
    ava = new_profile(b, "Ava Lind", "ava-live-pw-1")
    b.post(f"{API}/memory/correct", {"field": "marker", "value": "AVA-ONLY"})
    b.post(f"{API}/auth/lock")
    bo = new_profile(b, "Bo Reyes", "bo-live-pw-2")
    b.post(f"{API}/onboarding/complete", {"name": "Bo Reyes", "language_preference": "English"})
    b.post(f"{API}/memory/correct", {"field": "marker", "value": "BO-ONLY"})
    b.post(f"{API}/projects", {"name": "Bo's project", "description": "kept apart"})
    check("multi: Bo's document uploaded", upload(b, "bo.txt", bo_doc).status_code == 200)
    b.post(f"{API}/auth/lock")
    check("multi: Ava signs in (the last opened before the app is launched)", sign_in(b, ava, "ava-live-pw-1") == 200)
    b.graceful()
    b.start()
    launch_env = dict(b.profile_env)
    check("multi: the launcher started the backend for Ava", launch_env.get("PIP_PROFILE") == ava, launch_env)
    b.post(f"{API}/auth/lock")
    check("multi: Bo signs in in the app", sign_in(b, bo, "bo-live-pw-2") == 200)
    s_bo = snapshot(b)
    inherited = {**launch_env, "PIP_DATA_DIR": str(inst / "data")}
    r, new = export_via_launcher(inst, "bo-live-pw-2", inherited=inherited)
    check("multi: export launcher exits 0", r.returncode == 0, (r.stdout + r.stderr)[-500:])
    check("multi: it exported Bo, the signed-in profile, not Ava", "Profile: Bo Reyes" in r.stdout, r.stdout[-300:])
    check("multi: exactly one new .pipbak", len(new) == 1, new)
    if len(new) != 1:
        raise SystemExit("no backup to carry on with")
    carried = base / "transfer" / "bo.pipbak"
    carried.parent.mkdir(exist_ok=True)
    shutil.copyfile(new[0], carried)
    b.graceful()
    inst.rename(inst.with_name("machine1-elsewhere"))
    inst2, b2, _ = restore_in_app(base, "machine2", carried, "graceful", "bo-new-pw-4", "multi restore")
    verify_restored("multi", b2, inst2, s_bo, {"bo.txt": bo_doc}, [("WREN-31 garden code", "WREN-31")])
    marker_now = b2.get(f"{API}/memory/profile/marker").json() or {}
    check("multi: the restored profile is Bo's, with nothing of Ava's", marker_now.get("value") == "BO-ONLY", marker_now)
    b2.graceful()


def restore_over_used_journey(base: Path):
    """An in-app restore over a profile that already has documents and an index,
    one of them under the same file name as a document in the backup."""
    inst1, b1, _, s1 = populate(base, chat=False)
    bak, _ = export_and_move_away(base, inst1, b1, "Zarqa Venn", "zarqa-live-pw-1", "export-1")
    inst = make_installation(base / "machine2")
    b = InstBackend(inst)
    b.start()
    zed = new_profile(b, "Zed", "zed-live-pw-3")
    same = b"Zed's own note that happens to share the name. ZEDSAME-55 belongs to Zed."
    only = b"Another of Zed's notes. ZEDONLY-77 belongs to Zed."
    check("over-used: Zed's same-named document uploaded", upload(b, "heliotrope.txt", same).status_code == 200)
    check("over-used: Zed's other document uploaded", upload(b, "zed-only.txt", only).status_code == 200)
    check("over-used: Zed's documents are retrievable before", retrieves(b, "ZEDSAME-55 note", "ZEDSAME-55")
          and retrieves(b, "ZEDONLY-77 note", "ZEDONLY-77"))
    r = b.post(f"{API}/backup/restore", {"path": str(bak), "backup_password": BACKUP_PW, "new_password": "zarqa-new-pw-4"})
    check("over-used: restore staged", r.status_code == 200, r.text[:200])
    b.kill()
    b.start()
    check("over-used: the new password opens the restored profile", sign_in(b, zed, "zarqa-new-pw-4") == 200)
    verify_restored("over-used", b, inst, s1, {"heliotrope.txt": DOC1}, [("QUOKKA-7 sync engine codename", "QUOKKA-7")])
    docs_dir = inst / "data" / "profiles" / zed / "documents"
    note("over-used: files in the profile's documents folder",
         {p.name: p.read_bytes()[:40].decode("utf-8", "replace") for p in docs_dir.iterdir()} if docs_dir.exists() else None)
    for token in ("ZEDSAME-55", "ZEDONLY-77"):
        check(f"over-used: the replaced profile's {token} does not answer in the restored one",
              not retrieves(b, f"{token} note", token, wait=15))
    b.graceful()


def shortcut_shipped_journey(base: Path):
    """The desktop shortcut as installed: no arguments. (1) Two backups from the
    same day in data/, the second newer. (2) An installation that already has a
    named profile."""
    inst1, b1, _, _ = populate(base, chat=False)
    r1, first = export_via_launcher(inst1, "zarqa-live-pw-1")
    check("shipped: first export of the day", r1.returncode == 0 and len(first) == 1, (r1.stdout + r1.stderr)[-300:])
    b1.post(f"{API}/memory/correct", {"field": "marker", "value": "AFTER-FIRST-EXPORT"})
    r2, second = export_via_launcher(inst1, "zarqa-live-pw-1")
    check("shipped: second export of the day", r2.returncode == 0 and len(second) == 1, (r2.stdout + r2.stderr)[-300:])
    note("shipped: the two backups", [p.name for p in first + second])
    b1.graceful()
    if not (first and second):
        raise SystemExit("need two backups")

    inst4 = make_installation(base / "machine4")
    for p in first + second:
        shutil.copy2(p, inst4 / "data" / p.name)   # names and times as carried
    r = restore_via_shortcut(inst4, None, "zarqa-shortcut-pw-7", shipped=True)
    out = r.stdout + r.stderr
    restored_from = next((l.strip() for l in out.splitlines() if l.strip().startswith("Restoring from")), None)
    note("shipped: what the shortcut said", {"exit": r.returncode, "restoring": restored_from,
                                             "listing": [l.strip() for l in out.splitlines() if ".pipbak" in l][:4]})
    check("shipped: restore launcher exits 0", r.returncode == 0, out[-400:])
    check("shipped: it restored the newest backup, as it says it will",
          restored_from is not None and second[0].name in restored_from, restored_from)
    b4 = InstBackend(inst4)
    b4.start()
    check("shipped: the new password opens the restored profile", sign_in(b4, "default", "zarqa-shortcut-pw-7") == 200)
    marker_now = b4.get(f"{API}/memory/profile/marker").json() or {}
    check("shipped: the restored data is the newer backup's", marker_now.get("value") == "AFTER-FIRST-EXPORT", marker_now)
    b4.graceful()

    # (2) onto an installation where a named profile already lives.
    inst5 = make_installation(base / "machine5")
    b5 = InstBackend(inst5)
    b5.start()
    zed = new_profile(b5, "Zed", "zed-live-pw-3")
    b5.post(f"{API}/memory/correct", {"field": "marker", "value": "ZED-OWN"})
    b5.graceful()
    for p in first + second:
        shutil.copy2(p, inst5 / "data" / p.name)
    r = restore_via_shortcut(inst5, None, "zarqa-shortcut-pw-8", shipped=True)
    out = r.stdout + r.stderr
    note("shipped onto a named profile: shortcut", {"exit": r.returncode,
                                                    "tail": [l.strip() for l in out.splitlines() if l.strip()][-6:],
                                                    "data": sorted(p.name for p in (inst5 / "data").iterdir())})
    b5.start()
    note("shipped onto a named profile: the launcher starts the backend for", b5.profile_env.get("PIP_PROFILE"))
    listed = [p["slug"] for p in b5.get(f"{API}/auth/profiles").json()["profiles"]]
    tries = {f"{slug} / {pw}": sign_in(b5, slug, pw) for slug in listed
             for pw in ("zed-live-pw-3", "zarqa-shortcut-pw-8")}
    note("shipped onto a named profile: sign-in screen and passwords", {"profiles": listed, "tries": tries})
    opened = [k for k, v in tries.items() if v == 200 and k.endswith("zarqa-shortcut-pw-8")]
    check("shipped onto a named profile: the restored data is offered and opens with the new password", bool(opened), tries)
    check("shipped onto a named profile: Zed's own profile still opens with his password",
          tries.get(f"{zed} / zed-live-pw-3") == 200, tries)
    b5.graceful()


def same_machine_journey(base: Path):
    """Restore on the computer the backup was made on, the original document
    still where it was: the D-07 condition (FREEZE_LIST §7.16), open, measured
    here rather than avoided."""
    inst1, b1, _, s1 = populate(base, chat=False)
    r, new = export_via_launcher(inst1, "zarqa-live-pw-1")
    check("same machine: export launcher exits 0", r.returncode == 0, (r.stdout + r.stderr)[-400:])
    original = Path(doc_paths(b1)[0])
    b1.post(f"{API}/auth/lock")
    zed = new_profile(b1, "Zed", "zed-live-pw-3")
    r = b1.post(f"{API}/backup/restore", {"path": str(new[0]), "backup_password": BACKUP_PW, "new_password": "zarqa-new-pw-4"})
    check("same machine: restore staged into a second profile", r.status_code == 200, r.text[:200])
    b1.graceful()
    b1.start()
    check("same machine: the new password opens it", sign_in(b1, zed, "zarqa-new-pw-4") == 200)
    check("same machine: the original document file still exists", original.exists(), original)
    note("same machine: registered document paths", doc_paths(b1))
    compare("same machine", s1, snapshot(b1))
    check("same machine: retrieval finds QUOKKA-7 after the restore (D-07)",
          retrieves(b1, "QUOKKA-7 sync engine codename", "QUOKKA-7", wait=90))
    b1.graceful()


def run(variant: str, base: Path, commit: str = "HEAD"):
    before = real_data_fingerprint()
    started = time.time()
    base.mkdir(parents=True)
    export_commit(base, commit)
    try:
        if variant == "main-graceful":
            main_journey(base, "graceful")
        elif variant == "main-killed":
            main_journey(base, "killed")
        elif variant == "shortcut":
            shortcut_journey(base)
        elif variant == "inputs-and-delete":
            inputs_and_delete_journey(base)
        elif variant == "same-machine":
            same_machine_journey(base)
        elif variant == "staging":
            staging_journey(base)
        elif variant == "multi-profile-export":
            multi_profile_journey(base)
        elif variant == "restore-over-used":
            restore_over_used_journey(base)
        elif variant == "shortcut-shipped":
            shortcut_shipped_journey(base)
        else:
            raise SystemExit(f"unknown variant {variant}")
    except SystemExit:
        raise
    except Exception as e:  # recorded, not swallowed
        check("journey ran to the end", False, f"{type(e).__name__}: {e}")
    finally:
        check("the repository's real data/ was not touched", real_data_fingerprint() == before)
        failed = [r for r in RESULTS if not r["ok"]]
        summary = {"variant": variant, "commit": COMMIT, "checks": len(RESULTS), "failed": len(failed),
                   "failures": failed, "seconds": round(time.time() - started)}
        (base / "results.json").write_text(json.dumps({"summary": summary, "results": RESULTS}, indent=2), encoding="utf-8")
        print("SUMMARY " + json.dumps(summary), flush=True)


if __name__ == "__main__":
    run(sys.argv[1], Path(sys.argv[2]).resolve(), sys.argv[3] if len(sys.argv) > 3 else "HEAD")
