"""
Test two levers on the 0.30 similarity cut-off: a prompt rule for documents (D) and a larger documents
budget (E), alone and together (F), against the shipped setting (A) and plain 0.30 (C).

    python scripts/eval_retrieval_levers.py generate --out answers.json
    python scripts/eval_retrieval_levers.py sheet    --answers answers.json --out-dir grading/
    python scripts/eval_retrieval_levers.py score    --answers answers.json --grades grading/grades.json \
                                                     --key grading/key.json --out report.md

Everything that fixes the question is in docs/eval/retrieval_levers_protocol_2026-10-08.json and
docs/eval/retrieval_heldout_labels_2026-10-08.json, both committed before the first run: the levers'
exact wording, the five conditions, the 40 held-out questions the verdict is drawn from, and the
decision rule. The 66 development questions are run under D and E too and reported, but cannot
support or reject a lever, because rule 7 was written after seeing their wrong answers.

HOW THE LEVERS ARE SWITCHED ON WITHOUT EDITING THE PIPELINE
------------------------------------------------------------
* D wraps stage_07.run so that system_instructions is the app's own text plus rule 7.
* E wraps stage_07.get_settings so pipeline.rag_chunks_tokens is 1800 instead of 800.
* The cut-off is vector_store.DEFAULT_SIMILARITY_THRESHOLD, which query() resolves per call.
Retrieval is identical under every lever; only what Stage 7 builds from it differs.

ANSWERS ARE SHARED BY EXACT PROMPT. The provider hashes the whole prompt (system context plus
messages); a question whose prompt is the same under two conditions gets one generated answer, so a
difference between conditions can only come from a difference in the prompt. Temperature 0 and a
seed make a rerun of one prompt reproducible; num_ctx is 8192 on every call so a long E prompt is
not silently cut by Ollama's default window.

GRADING is blind to condition (the sheet shows the question, the reference line and the answer, and
nothing else; the key is a separate file), one answer at a time, by the same hand that wrote the
questions. An answer whose text equals an already graded answer for the same question is graded
once. Development answers identical to the earlier run's answers inherit its grade.
"""

import argparse
import copy
import hashlib
import json
import os
import random
import shutil
import sqlite3
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

# Fail with the interpreter you used, not a wrong install instruction.
import _venv

_venv.require("sqlcipher3")

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
import eval_retrieval_e2e as e2e  # noqa: E402  (norm, read_corpus, reference_line, sign_test)

EVAL = REPO / "docs" / "eval"
PROTOCOL = EVAL / "retrieval_levers_protocol_2026-10-08.json"
HELD = EVAL / "retrieval_heldout_labels_2026-10-08.json"
DEV = EVAL / "retrieval_labels_2026-10-08.json"
DEV_PROTOCOL = EVAL / "retrieval_e2e_protocol_2026-10-08.json"
PREV_ANSWERS = EVAL / "retrieval_e2e_answers_2026-10-08.json"
PREV_GRADING = EVAL / "retrieval_e2e_grading_2026-10-08"
SHEET_SEED = 20261009
NUM_CTX = 8192
norm = e2e.norm


def load_sets(own=None):
    """{'held_out': {...}, 'development': {...}} each with answerable, unanswerable, corpus, snapshot.

    With `own` (a folder holding labels.json and the documents, kept out of git because they are
    somebody's own) the only set is 'own' and the corpus is read from that folder."""
    if own:
        lab = json.load(open(Path(own) / "labels.json", encoding="utf-8"))
        return {"own": {"answerable": lab["answerable"], "unanswerable": lab["unanswerable"]}}, "local", lab["documents"]
    held = json.load(open(HELD, encoding="utf-8"))
    dev = json.load(open(DEV, encoding="utf-8"))
    dev_una = json.load(open(DEV_PROTOCOL, encoding="utf-8"))["unanswerable"]
    return {
        "held_out": {"answerable": held["answerable"], "unanswerable": held["unanswerable"]},
        "development": {"answerable": dev["answerable"], "unanswerable": dev_una},
    }, held["snapshot_commit"], held["corpus"]


def read_corpus(snapshot, files, own=None):
    if own:
        return {name: (Path(own) / name).read_text(encoding="utf-8") for name in files}
    return e2e.read_corpus(snapshot, files)


def previous_labels():
    """Earlier run's answer_id -> label, and (qid, normalised text) -> answer_id, with strict/lenient maps."""
    answers = json.load(open(PREV_ANSWERS, encoding="utf-8"))
    key = json.load(open(PREV_GRADING / "key.json"))
    out = {}
    for variant, fname in (("main", "grades.json"), ("strict", "grades_strict.json"), ("lenient", "grades_lenient.json")):
        g = json.load(open(PREV_GRADING / fname))
        out[variant] = {key[n]: v for n, v in g.items()}
    return answers, out


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------


def generate(args) -> None:
    proto = json.load(open(PROTOCOL, encoding="utf-8"))
    own = args.own
    sets, snapshot, corpus_files = load_sets(own)
    conds = proto["conditions"]
    rule_text = proto["levers"]["D_document_rule"]["text"]

    replication = set()
    work = []  # (set, group, qid, question, [conditions])
    if own:
        # The owner's own document: all five conditions on every question, no development set.
        for group in ("answerable", "unanswerable"):
            for q in sets["own"][group]:
                work.append(("own", group, q["id"], q["question"], ["A", "C", "D", "E", "F"]))
    else:
        prev_answers, prev_labels = previous_labels()
        prev_by = {(r["condition"], r["qid"]): r for r in prev_answers["records"]}
        dev_ids = [q["id"] for q in sets["development"]["answerable"]]
        main = prev_labels["main"]
        newly_wrong = [q for q in dev_ids
                       if main[prev_by[("C", q)]["answer_id"]] == "WRONG" and main[prev_by[("A_as_shipped", q)]["answer_id"]] != "WRONG"]
        correct_at_c = [q for q in sorted(dev_ids) if main[prev_by[("C", q)]["answer_id"]] == "CORRECT"][:6]
        replication = set(newly_wrong + correct_at_c)

        for q in sets["held_out"]["answerable"]:
            work.append(("held_out", "answerable", q["id"], q["question"], ["A", "C", "D", "E", "F"]))
        for q in sets["held_out"]["unanswerable"]:
            work.append(("held_out", "unanswerable", q["id"], q["question"], ["A", "C", "D", "E", "F"]))
        for q in sets["development"]["answerable"]:
            work.append(("development", "answerable", q["id"], q["question"],
                         ["D", "E"] + (["A", "C"] if q["id"] in replication else [])))
        for q in sets["development"]["unanswerable"]:
            work.append(("development", "unanswerable", q["id"], q["question"], ["D", "E"]))
    if args.only:
        wanted = set(args.only.split(","))
        work = [w for w in work if w[2] in wanted]
    if args.limit:
        work = work[: args.limit]

    tmp = Path(tempfile.mkdtemp(prefix="pip_eval_levers_"))
    os.environ["PIP_DATA_DIR"] = str(tmp / "data")
    os.environ["PIP_DB_PATH"] = str(tmp / "data" / "pip.db")
    os.environ["PIP_DOCUMENTS_ROOT"] = str(tmp / "documents")
    os.environ["PIP_CHROMA_PATH"] = str(tmp / "chroma")
    os.environ.pop("PIP_DB_KEY", None)
    sys.path.insert(0, str(REPO))

    from backend.core import pipeline, response_cache
    from backend.memory import profile_store, vector_store
    from backend.providers.base_provider import ProviderExecutionError, ProviderUnavailableError
    from backend.providers.ollama_provider import OllamaProvider

    model = "qwen2.5:7b"
    if not OllamaProvider(model_name=model).is_available():
        sys.exit("Ollama is not reachable on localhost:11434 - start it first")

    out_path = Path(args.out)
    state = json.load(open(out_path, encoding="utf-8")) if out_path.exists() else {
        "model": model, "num_ctx": NUM_CTX, "snapshot_commit": snapshot,
        "conditions": conds, "replication_ids": sorted(replication), "records": [], "answers": {},
    }
    done = {(r["set"], r["qid"], r["condition"]) for r in state["records"]}

    class PinnedOllama(OllamaProvider):
        """Ollama with temperature 0, a seed and num_ctx pinned; reuses the answer to an identical prompt."""

        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.last: dict = {}
            self.qid = ""
            self.watch: str | None = None

        def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
            if context:
                messages = [{"role": "system", "content": context}] + messages
            blob = json.dumps(messages, sort_keys=True, ensure_ascii=False)
            aid = f"{self.qid}|{hashlib.sha1(blob.encode()).hexdigest()[:10]}"
            full = " ".join(m["content"] for m in messages)
            marker = full.find("RELEVANT DOCUMENTS:")
            info = {
                "aid": aid,
                "rag_words_in_prompt": len(full[marker:].split()) if marker >= 0 else 0,
                "prompt_has_key": None if self.watch is None else self.watch in norm(full),
                "prompt_chars": len(full),
            }
            if aid in state["answers"]:
                self.last = {**info, "reused": True}
                yield state["answers"][aid]["text"]
                return
            payload = {"model": self.model_name, "messages": messages, "stream": True,
                       "options": {"num_predict": max_tokens, "temperature": 0, "seed": 1, "num_ctx": NUM_CTX}}
            req = urllib.request.Request(f"{self.host}/api/chat", data=json.dumps(payload).encode("utf-8"),
                                         headers={"Content-Type": "application/json"}, method="POST")
            self.last = {**info, "reused": False}
            try:
                with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                    for line in response:
                        if not line:
                            continue
                        chunk = json.loads(line.decode("utf-8"))
                        if chunk.get("done"):
                            self.last.update(prompt_eval_count=chunk.get("prompt_eval_count"),
                                             eval_count=chunk.get("eval_count"), done_reason=chunk.get("done_reason"))
                        piece = chunk.get("message", {}).get("content")
                        if piece:
                            yield piece
            except Exception as e:
                raise ProviderExecutionError(f"Ollama: {e}")

    corpus = read_corpus(snapshot, corpus_files, own)
    docs_root = tmp / "documents"
    docs_root.mkdir(parents=True)
    for name, text in corpus.items():
        (docs_root / name.replace("/", "__")).write_text(text, encoding="utf-8")
    vector_store.reset_client()
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    profile_store.initialize_schema(conn)
    conn.execute("INSERT INTO llm_settings (id, model_name) VALUES (1, ?)", (model,))
    conn.commit()
    for name in corpus:
        vector_store.ingest_document(conn, str(docs_root / name.replace("/", "__")))
    print(f"ingested {vector_store._get_collection().count()} chunks", flush=True)

    key_of = {q["id"]: norm(q["key"]) for s in sets.values() for q in s["answerable"]}

    # --- the two levers -----------------------------------------------------------------------
    cur = {"doc_rule": False, "rag": 800}
    real_stage_07_run = pipeline.stage_07.run
    real_get_settings = pipeline.stage_07.get_settings
    default_instructions = pipeline.stage_07._DEFAULT_SYSTEM_INSTRUCTIONS

    def stage_07_run(*a, **k):
        if cur["doc_rule"]:
            k["system_instructions"] = default_instructions + "\n" + rule_text
        return real_stage_07_run(*a, **k)

    def get_settings_patched():
        s = copy.deepcopy(real_get_settings())
        s["pipeline"]["rag_chunks_tokens"] = cur["rag"]
        return s

    pipeline.stage_07.run = stage_07_run
    pipeline.stage_07.get_settings = get_settings_patched

    seen = {}
    real_stage_05_run = pipeline.stage_05.run

    def spy(conn_, hint, project_id=None, threshold=None, top_k=None):
        result = real_stage_05_run(conn_, hint, project_id, threshold, top_k)
        seen["chunks"] = result["chunks"]
        return result

    pipeline.stage_05.run = spy

    def save():
        json.dump(state, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

    warm = PinnedOllama(model_name=model)
    list(warm.chat([{"role": "user", "content": "Say ready."}], max_tokens=5, timeout_seconds=300))
    print("model warm", flush=True)

    for set_name, group, qid, question, cond_names in work:
        for cname in cond_names:
            if (set_name, qid, cname) in done:
                continue
            c = conds[cname]
            vector_store.DEFAULT_SIMILARITY_THRESHOLD = c["similarity_threshold"]
            cur["doc_rule"] = bool(c.get("document_rule"))
            cur["rag"] = c.get("rag_chunks_tokens", 800)
            response_cache.clear()
            provider = PinnedOllama(model_name=model)
            provider.qid = qid
            provider.watch = key_of.get(qid)
            t0 = time.time()
            try:
                result = pipeline.run_sync(conn, question, providers=[provider], max_tokens=400, timeout_seconds=300)
            except (ProviderUnavailableError, ProviderExecutionError) as e:
                sys.exit(f"provider failed on {qid} {cname}: {e}")
            info = provider.last
            aid = info["aid"]
            if aid not in state["answers"]:
                state["answers"][aid] = {
                    "qid": qid, "group": group, "set": set_name, "question": question,
                    "status": result["status"], "error": result.get("error"), "text": result["response_text"],
                    "seconds": round(time.time() - t0, 1),
                    **{k: v for k, v in info.items() if k not in ("aid", "reused")},
                }
            state["records"].append({
                "set": set_name, "group": group, "qid": qid, "condition": cname,
                "threshold": c["similarity_threshold"], "answer_id": aid,
                "rag_words_in_prompt": info["rag_words_in_prompt"], "prompt_has_key": info["prompt_has_key"],
                "passages": [{"file": Path(p["file_path"]).name.replace("__", "/"), "chunk_index": p["chunk_index"],
                              "similarity": round(p["similarity"], 4), "text": p["chunk_text"]}
                             for p in seen.get("chunks", [])],
            })
            print(f"{set_name[:4]} {qid} {cname}: {len(seen.get('chunks', []))} passages, rag_words={info['rag_words_in_prompt']}, "
                  f"{'reused' if info['reused'] else str(state['answers'][aid]['seconds']) + 's'}, status={result['status']}", flush=True)
            save()
    pipeline.stage_07.run, pipeline.stage_07.get_settings, pipeline.stage_05.run = (
        real_stage_07_run, real_get_settings, real_stage_05_run)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"wrote {out_path}")


# ---------------------------------------------------------------------------
# sheet
# ---------------------------------------------------------------------------


def reference_for(qid, sets, corpus):
    for s in sets.values():
        for q in s["answerable"]:
            if q["id"] == qid:
                return f"REFERENCE (from {q['source']}): {e2e.reference_line(corpus[q['source']], q['key'])}"
    return "REFERENCE: no document answers this. A specific answer given as fact is WRONG."


def sheet(args) -> None:
    state = json.load(open(args.answers, encoding="utf-8"))
    sets, snapshot, corpus_files = load_sets(args.own)
    corpus = read_corpus(snapshot, corpus_files, args.own)
    prev_text = {}  # (qid, normalised text) -> previous answer id
    prev_labels = {}
    if not args.own:  # only the development set can inherit an earlier run's grades
        prev_answers, prev_labels = previous_labels()
        for aid, a in prev_answers["answers"].items():
            prev_text[(a["qid"], norm(a["text"]))] = aid

    inherited = {}
    groups = {}  # (qid, normalised text) -> [answer ids]
    for aid, a in state["answers"].items():
        k = (a["qid"], norm(a["text"]))
        if a["set"] == "development" and k in prev_text:
            pid = prev_text[k]
            inherited[aid] = {v: prev_labels[v][pid] for v in ("main", "strict", "lenient")}
            continue
        groups.setdefault(k, []).append(aid)

    order = sorted(groups)
    random.Random(SHEET_SEED).shuffle(order)
    key = {}
    parts = ["# Grading sheet - levers\n",
             "Label each answer: CORRECT, DECLINES, WRONG or VAGUE (definitions in docs/eval/retrieval_e2e_protocol_2026-10-08.json; "
             "a DECLINES that says the documents do not state the answer counts as DECLINES).",
             "The condition and the retrieved passages are not shown.\n"]
    for n, k in enumerate(order, 1):
        aids = groups[k]
        a = state["answers"][aids[0]]
        key[str(n)] = aids
        text = a["text"].strip()
        cut = " [CUT: answer longer than the sheet shows]" if len(text) > e2e.SAMPLE_CHARS else ""
        parts.append(f"## {n}\nQ: {a['question']}\n{reference_for(a['qid'], sets, corpus)}\nANSWER: {text[:e2e.SAMPLE_CHARS]}{cut}\n")
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sheet.md").write_text("\n".join(parts), encoding="utf-8")
    json.dump(key, open(out / "key.json", "w"))
    json.dump(inherited, open(out / "inherited.json", "w"))
    print(f"{len(state['answers'])} distinct prompts; {len(inherited)} inherit an earlier grade; "
          f"{len(order)} answers to grade -> {out / 'sheet.md'}")


# ---------------------------------------------------------------------------
# score
# ---------------------------------------------------------------------------


def score(args) -> None:
    state = json.load(open(args.answers, encoding="utf-8"))
    key = json.load(open(args.key))
    inherited = json.load(open(Path(args.key).parent / "inherited.json"))
    vset = "own" if args.own else "held_out"  # the set the verdict is drawn from
    variants = {}
    for variant, gfile in (("main", args.grades), ("strict", args.grades_strict or args.grades), ("lenient", args.grades_lenient or args.grades)):
        g = json.load(open(gfile))
        label = {}
        for n, aids in key.items():
            for aid in aids:
                label[aid] = g[n].upper()
        for aid, d in inherited.items():
            label[aid] = d[variant]
        missing = [a for a in state["answers"] if a not in label]
        if missing:
            sys.exit(f"{len(missing)} answers have no grade, e.g. {missing[:3]}")
        variants[variant] = label

    by = {}
    for r in state["records"]:
        by.setdefault((r["set"], r["group"], r["condition"]), {})[r["qid"]] = r

    def counts(label, set_name, group, cond):
        c = {"CORRECT": 0, "DECLINES": 0, "WRONG": 0, "VAGUE": 0}
        for r in by.get((set_name, group, cond), {}).values():
            c[label[r["answer_id"]]] += 1
        return c

    def paired(label, set_name, group, cond, base, what):
        up = down = 0
        for qid, r in by[(set_name, group, cond)].items():
            a = label[by[(set_name, group, base)][qid]["answer_id"]] == what
            b = label[r["answer_id"]] == what
            up += b and not a
            down += a and not b
        return up, down

    def verdict(label, cond):
        s = vset
        ca, cc = counts(label, s, "answerable", "A"), counts(label, s, "answerable", "C")
        cx = counts(label, s, "answerable", cond)
        up, down = paired(label, s, "answerable", cond, "A", "CORRECT")
        ua, ux = counts(label, s, "unanswerable", "A"), counts(label, s, "unanswerable", cond)
        c1 = (up - down) >= 6 and e2e.sign_test(up, down) < 0.05
        c2 = cx["WRONG"] <= ca["WRONG"]
        c3 = (ux["WRONG"] - ua["WRONG"]) <= 1
        c4 = cx["CORRECT"] >= cc["CORRECT"] - 3
        valid = cc["WRONG"] > ca["WRONG"] + 1
        if not valid:
            word = "INCONCLUSIVE"
        else:
            word = "SUPPORTED" if (c1 and c2 and c3 and c4) else "NOT SUPPORTED"
        return word, (c1, c2, c3, c4), (up, down), valid

    out = ["# Levers - results\n"]
    p = out.append
    p(f"Model {state['model']}, num_ctx {state['num_ctx']}, temperature 0, snapshot `{state['snapshot_commit']}`. "
      "Conditions: " + "; ".join(f"{k} = {v}" for k, v in state["conditions"].items()) + ".\n")
    main = variants["main"]
    for set_name, title in (("held_out", "Held-out set (the verdict is drawn from this)"),
                            ("development", "Development set (reported only)"),
                            ("own", "The owner's own document (the verdict is drawn from this)")):
        if not any(k[0] == set_name for k in by):
            continue
        p(f"## {title}\n")
        for group, gtitle in (("answerable", "answerable"), ("unanswerable", "no document answers it")):
            conds_here = [c for c in state["conditions"] if (set_name, group, c) in by]
            n = len(by[(set_name, group, conds_here[0])])
            p(f"**{gtitle}, {n} questions**\n")
            p("| condition | questions that got passages | document words in prompt (mean) | CORRECT | DECLINES | WRONG | VAGUE |")
            p("|---|---|---|---|---|---|---|")
            for c in conds_here:
                rs = by[(set_name, group, c)].values()
                got = sum(1 for r in rs if r["passages"])
                words = sum(r["rag_words_in_prompt"] for r in rs) / len(by[(set_name, group, c)])
                k = counts(main, set_name, group, c)
                p(f"| {c} | {got} | {words:.0f} | {k['CORRECT']} | {k['DECLINES']} | {k['WRONG']} | {k['VAGUE']} |")
            p("")

    p("## Decision rule (held-out set, relative to A)\n")
    ca = counts(main, vset, "answerable", "A")
    cc = counts(main, vset, "answerable", "C")
    p(f"Validity guard: WRONG under C = {cc['WRONG']}, under A = {ca['WRONG']}; the problem is reproduced when C exceeds A by 2 or more: "
      f"**{'yes' if cc['WRONG'] > ca['WRONG'] + 1 else 'NO - every verdict is INCONCLUSIVE'}**.\n")
    for cond in ("D", "E", "F"):
        w, (c1, c2, c3, c4), (up, down), valid = verdict(main, cond)
        ws = {v: verdict(variants[v], cond)[0] for v in ("strict", "lenient")}
        cx = counts(main, vset, "answerable", cond)
        ux = counts(main, vset, "unanswerable", cond)
        ua = counts(main, vset, "unanswerable", "A")
        p(f"- **{cond}**: (1) CORRECT {ca['CORRECT']} -> {cx['CORRECT']}, {up} up / {down} down, p = {e2e.sign_test(up, down):.3f}, needs net 6+ and p < 0.05: {'met' if c1 else 'NOT met'}; "
          f"(2) WRONG {ca['WRONG']} -> {cx['WRONG']} (must not rise): {'met' if c2 else 'NOT met'}; "
          f"(3) invented on the unanswerable {ua['WRONG']} -> {ux['WRONG']} (rise of at most 1): {'met' if c3 else 'NOT met'}; "
          f"(4) CORRECT {cx['CORRECT']} against C's {cc['CORRECT']} (at most 3 lower): {'met' if c4 else 'NOT met'}. "
          f"**{w}** (strict reading: {ws['strict']}; lenient reading: {ws['lenient']})")

    p("\n## Held-out answers that changed grade relative to C\n")
    for cond in ("D", "E", "F"):
        rows = []
        for qid, r in by[(vset, "answerable", cond)].items():
            b = main[r["answer_id"]]
            a = main[by[(vset, "answerable", "C")][qid]["answer_id"]]
            if a != b:
                rows.append(f"{qid}: {a} -> {b}")
        p(f"- {cond}: " + ("; ".join(rows) if rows else "none"))

    p("\n## What the model was shown (held-out, answerable)\n")
    p("| condition | answer in the prompt: CORRECT of | answer retrieved but cut: CORRECT of | passages without the answer: CORRECT / DECLINES / WRONG / VAGUE | no passages: CORRECT / DECLINES / WRONG / VAGUE |")
    p("|---|---|---|---|---|")
    keys = {q["id"]: norm(q["key"]) for q in load_sets(args.own)[0][vset]["answerable"]}
    for c in state["conditions"]:
        shown, cut = [0, 0], [0, 0]
        without = {"CORRECT": 0, "DECLINES": 0, "WRONG": 0, "VAGUE": 0}
        none_ = dict(without)
        for qid, r in by[(vset, "answerable", c)].items():
            g = main[r["answer_id"]]
            retrieved = any(keys[qid] in norm(x["text"]) for x in r["passages"])
            if r["prompt_has_key"]:
                shown[1] += 1
                shown[0] += g == "CORRECT"
            elif retrieved:
                cut[1] += 1
                cut[0] += g == "CORRECT"
            elif r["passages"]:
                without[g] += 1
            else:
                none_[g] += 1
        f = lambda d: " / ".join(str(d[k]) for k in ("CORRECT", "DECLINES", "WRONG", "VAGUE"))
        p(f"| {c} | {shown[0]} of {shown[1]} | {cut[0]} of {cut[1]} | {f(without)} | {f(none_)} |")

    p("\n## Checks\n")
    ans = state["answers"].values()
    p(f"- distinct prompts run: {len(state['answers'])}; every status success: {all(a['status'] == 'success' for a in ans)}")
    p(f"- largest prompt Ollama counted: {max((a.get('prompt_eval_count') or 0) for a in ans)} tokens (num_ctx {state['num_ctx']})")
    p(f"- answers that hit the 400-token limit: {sum(1 for a in ans if a.get('done_reason') == 'length')}")
    if state["replication_ids"]:
        p(f"- development replication (A and C re-run under the new options on {len(state['replication_ids'])} questions): "
          f"answers identical to the earlier run's for {sum(1 for a in state['answers'].values() if a['set'] == 'development' and a['qid'] in state['replication_ids'] and (a['qid'], norm(a['text'])) in {(x['qid'], norm(x['text'])) for x in json.load(open(PREV_ANSWERS, encoding='utf-8'))['answers'].values()})} "
          f"of {sum(1 for r in state['records'] if r['set'] == 'development' and r['condition'] in ('A', 'C'))} A/C runs")
    text = "\n".join(out)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--out", required=True)
    g.add_argument("--limit", type=int, default=0)
    g.add_argument("--only", default="")
    g.add_argument("--own", default=None, help="folder with labels.json and the owner's documents (kept out of git)")
    s = sub.add_parser("sheet")
    s.add_argument("--answers", required=True)
    s.add_argument("--out-dir", required=True)
    s.add_argument("--own", default=None)
    c = sub.add_parser("score")
    c.add_argument("--own", default=None)
    c.add_argument("--answers", required=True)
    c.add_argument("--grades", required=True)
    c.add_argument("--grades-strict", default=None)
    c.add_argument("--grades-lenient", default=None)
    c.add_argument("--key", required=True)
    c.add_argument("--out", default=None)
    args = ap.parse_args()
    {"generate": generate, "sheet": sheet, "score": score}[args.cmd](args)


if __name__ == "__main__":
    main()
