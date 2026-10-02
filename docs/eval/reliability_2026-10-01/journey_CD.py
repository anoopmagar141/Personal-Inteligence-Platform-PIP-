"""
Journey C (two profiles, one machine) + D (export -> in-app restore on a
second, separate installation -> keep using -> export -> restore again).
Real processes, live qwen2.5:7b, embedding shim.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from journey import API, PY, REPO, Backend, log, turn

base = Path(sys.argv[1]).resolve()
HERE = Path(__file__).parent
DOC = b"Heliotrope design note. The sync engine codename is QUOKKA-7 and it batches writes every 40 seconds."
BOBDOC = b"Bob's private note: the surprise party code is BOB-SECRET-77."


def export(root: Path, slug: str, live_pw: str, backup_pw: str, out: Path):
    env = dict(os.environ)
    env["PIP_SALT_PATH"] = str(root / "profiles" / slug / "salt.bin")
    env.pop("PIP_DB_KEY", None)
    env["J_ANSWERS"] = json.dumps([live_pw, backup_pw, backup_pw])
    code = ("import getpass,json,os,runpy,sys; a=iter(json.loads(os.environ['J_ANSWERS'])); "
            "getpass.getpass=lambda p='': next(a); s=sys.argv[1]; sys.argv=[s]+sys.argv[2:]; "
            "sys.path.insert(0, os.path.dirname(s)); runpy.run_path(s, run_name='__main__')")
    r = subprocess.run([str(PY), "-c", code, str(REPO / "scripts" / "export_backup.py"),
                        "--db-path", str(root / "profiles" / slug / "pip.db"), "--out", str(out)],
                       cwd=str(REPO), env=env, capture_output=True, text=True, timeout=300)
    return r.returncode, (r.stdout + r.stderr)[-300:]


def snapshot(b: Backend):
    convs = b.get(f"{API}/conversations").json()
    msgs = {c["id"]: [(m["role"], m["content"]) for m in b.get(f"{API}/conversations/{c['id']}/messages").json()] for c in convs}
    prof = {f"{p.get('table')}.{p.get('field')}": p.get("value") for p in b.get(f"{API}/memory/profile").json()}
    return {
        "conversations": len(convs),
        "messages": sum(len(v) for v in msgs.values()),
        "msgs": msgs,
        "decisions": sorted(d["decision_text"] for d in b.get(f"{API}/decision/search", params={"q": ""}).json()),
        "projects": sorted(p["name"] for p in b.get(f"{API}/projects").json()),
        "profile": prof,
        "documents": [(Path(d["file_path"]).name, d.get("chunk_count")) for d in b.get(f"{API}/rag/documents").json()],
        "doc_paths": [d["file_path"] for d in b.get(f"{API}/rag/documents").json()],
        "rag_quokka": [str(c.get("text") or c.get("content") or c.get("document") or c)[:60] for c in b.post(f"{API}/rag/query", {"query": "QUOKKA-7 sync engine codename", "threshold": 0.0}).json()],
    }


def new_profile(b, name, pw):
    slug = b.post(f"{API}/auth/profiles", {"name": name}).json()["slug"]
    r = b.post(f"{API}/auth/setup", {"password": pw, "profile": slug})
    assert r.status_code == 200, r.text
    return slug


def upload(b, name, data):
    return httpx_post_file(b, name, data)


def httpx_post_file(b, name, data):
    import httpx
    return httpx.post(b.url(f"{API}/rag/upload"), headers=b.h(), files={"file": (name, data, "text/plain")}, timeout=300)


# ===================== machine 1 =====================
m1 = Backend(base / "machine1")
log("m1_start", m1.start())
z = new_profile(m1, "Zarqa Venn", "zarqa-live-pw-1")
m1.post(f"{API}/onboarding/complete", {"name": "Zarqa Venn", "language_preference": "English"})
m1.post(f"{API}/llm/active-model", {"model_name": "qwen2.5:7b"})
log("m1_project", m1.post(f"{API}/projects", {"name": "Heliotrope", "description": "sync engine"}).status_code)
log("m1_decision", m1.post(f"{API}/decision/create", {"text": "Use FastAPI for the thesis backend", "reasoning": "native async"}).status_code)
log("m1_correct", m1.post(f"{API}/memory/correct", {"field": "favourite_editor", "value": "Helix"}).status_code)
log("m1_upload", upload(m1, "heliotrope.txt", DOC).status_code)
with m1.ws() as ws:
    ws.recv(timeout=30)
    log("m1_turn", turn(ws, "In one sentence: what is the codename of the Heliotrope sync engine?"))
s1 = snapshot(m1)
log("m1_snapshot", {k: v for k, v in s1.items() if k != "msgs"})

# ---------- Journey C: second profile on the same machine ----------
log("lock_zarqa", m1.post(f"{API}/auth/lock").status_code)
bob = new_profile(m1, "Bob", "bob-live-pw-22")
m1.post(f"{API}/llm/active-model", {"model_name": "qwen2.5:7b"})
log("bob_upload", upload(m1, "party.txt", BOBDOC).status_code)
sb = snapshot(m1)
log("bob_sees", {k: v for k, v in sb.items() if k != "msgs"})
with m1.ws() as ws:
    ws.recv(timeout=30)
    t = turn(ws, "What is the codename of the Heliotrope sync engine?")
log("bob_asks_zarqas_secret", t)
log("C_isolation", {"bob_answer_mentions_QUOKKA": "QUOKKA" in t["text"].upper(),
                    "bob_rag_quokka": sb["rag_quokka"], "bob_conversations": sb["conversations"],
                    "bob_decisions": sb["decisions"], "bob_projects": sb["projects"]})
log("bob_reads_zarqa_doc_path", m1.post(f"{API}/rag/ingest", {"file_path": s1["doc_paths"][0]}).status_code if s1["doc_paths"] else None)
log("bob_switch_while_unlocked", m1.post(f"{API}/auth/profile", {"slug": z}).status_code)
m1.post(f"{API}/auth/lock")
log("switch_to_zarqa", m1.post(f"{API}/auth/profile", {"slug": z}).status_code)
log("unlock_zarqa_with_bobs_pw", m1.post(f"{API}/auth/unlock", {"password": "bob-live-pw-22", "profile": z}).status_code)
log("unlock_zarqa", m1.post(f"{API}/auth/unlock", {"password": "zarqa-live-pw-1", "profile": z}).status_code)
s1b = snapshot(m1)
log("zarqa_unchanged_after_bob", {k: s1b[k] == s1[k] for k in s1 if k not in ("msgs",)})
log("zarqa_rag_has_no_bob", [x for x in m1.post(f"{API}/rag/query", {"query": "surprise party code BOB-SECRET"}).json()])

# ---------- export (script, with the profile's own paths) ----------
bak1 = base / "zarqa-1.pipbak"
log("export1", export(base / "machine1", z, "zarqa-live-pw-1", "backup-pw-zz9", bak1))
log("export1_size", bak1.stat().st_size if bak1.exists() else None)
log("export1_plaintext_markers", {m: (m.encode() in bak1.read_bytes()) for m in ("QUOKKA-7", "Zarqa", "FastAPI", "SQLite format 3")} if bak1.exists() else None)
m1.graceful()

# corrupt copies
raw = bak1.read_bytes()
trunc = base / "trunc.pipbak"; trunc.write_bytes(raw[: len(raw) // 2])
garbage = base / "garbage.pipbak"; garbage.write_bytes(os.urandom(len(raw)))
flipped = base / "flipped.pipbak"; fb = bytearray(raw); fb[len(fb) // 2] ^= 0xFF; flipped.write_bytes(bytes(fb))

# ===================== machine 2 =====================
m2 = Backend(base / "machine2")
log("m2_start", m2.start())
zed = new_profile(m2, "Zed", "zed-live-pw-3")
m2.post(f"{API}/memory/correct", {"field": "marker", "value": "ZED-ORIGINAL"})
for label, path, bpw in [("wrong_pw", bak1, "nope-nope-nope"), ("truncated", trunc, "backup-pw-zz9"),
                         ("garbage", garbage, "backup-pw-zz9"), ("bitflip", flipped, "backup-pw-zz9"),
                         ("missing", base / "nope.pipbak", "backup-pw-zz9"), ("traversal", "..\\..\\x.pipbak", "backup-pw-zz9")]:
    r = m2.post(f"{API}/backup/restore", {"path": str(path), "backup_password": bpw, "new_password": "zarqa-new-pw-4"})
    log(f"m2_restore_{label}", (r.status_code, r.text[:140]))
log("m2_pending_after_bad", m2.get(f"{API}/backup/restore").json())
log("m2_short_new_pw", m2.post(f"{API}/backup/restore", {"path": str(bak1), "backup_password": "backup-pw-zz9", "new_password": "short"}).status_code)
r = m2.post(f"{API}/backup/restore", {"path": str(bak1), "backup_password": "backup-pw-zz9", "new_password": "zarqa-new-pw-4"})
log("m2_restore_ok", (r.status_code, r.text[:200]))
log("m2_pending", m2.get(f"{API}/backup/restore").json())
log("m2_zed_still_live_before_restart", m2.get(f"{API}/memory/profile/marker").json())
m2.graceful()
log("m2_restart", m2.start())
log("m2_state", m2.get(f"{API}/auth/state").json())
log("m2_profiles", m2.get(f"{API}/auth/profiles").json())
m2.post(f"{API}/auth/profile", {"slug": zed})
log("m2_unlock_old_zed_pw", m2.post(f"{API}/auth/unlock", {"password": "zed-live-pw-3", "profile": zed}).status_code)
log("m2_unlock_backup_pw", m2.post(f"{API}/auth/unlock", {"password": "backup-pw-zz9", "profile": zed}).status_code)
log("m2_unlock_new_pw", m2.post(f"{API}/auth/unlock", {"password": "zarqa-new-pw-4", "profile": zed}).status_code)
time.sleep(8)  # sign-in catch-up (index rebuild)
s2 = snapshot(m2)
diff = {k: (s1b[k] == s2[k]) for k in s1b if k not in ("doc_paths",)}
log("D_restored_equal", diff)
for k, ok in diff.items():
    if not ok:
        log(f"D_diff_{k}", {"before": s1b[k] if k != "msgs" else len(s1b[k]), "after": s2[k] if k != "msgs" else len(s2[k])})
log("D_zed_marker_gone", m2.get(f"{API}/memory/profile/marker").status_code)
log("D_doc_bytes", [(p, Path(p).exists() and Path(p).read_bytes() == DOC) for p in s2["doc_paths"]])
log("D_doc_under_m2", [str(Path(p)).startswith(str(base / "machine2")) for p in s2["doc_paths"]])
log("m2_files", sorted(str(p.relative_to(base / "machine2")) for p in (base / "machine2").rglob("*") if p.is_file() and "chroma" not in p.parts))

# keep using, then round-trip again
m2.post(f"{API}/llm/active-model", {"model_name": "qwen2.5:7b"})
with m2.ws() as ws:
    ws.recv(timeout=30)
    log("m2_turn", turn(ws, "Say the word 'continuation' and nothing else."))
m2.post(f"{API}/decision/create", {"text": "Ship the beta in May"})
s2b = snapshot(m2)
bak2 = base / "zarqa-2.pipbak"
log("export2", export(base / "machine2", zed, "zarqa-new-pw-4", "backup-pw-zz9", bak2))
m2.graceful()

m3 = Backend(base / "machine3")
m3.start()
y = new_profile(m3, "Y", "y-live-pw-55")
log("m3_restore", m3.post(f"{API}/backup/restore", {"path": str(bak2), "backup_password": "backup-pw-zz9", "new_password": "zarqa-third-pw-6"}).status_code)
m3.graceful(); m3.start()
m3.post(f"{API}/auth/profile", {"slug": y})
log("m3_unlock", m3.post(f"{API}/auth/unlock", {"password": "zarqa-third-pw-6", "profile": y}).status_code)
time.sleep(8)
s3 = snapshot(m3)
log("D2_second_roundtrip_equal", {k: (s2b[k] == s3[k]) for k in s2b if k not in ("doc_paths",)})
m3.graceful()
