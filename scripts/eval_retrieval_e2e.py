"""
End-to-end check on the similarity cut-off: does lowering it make the model's ANSWERS better or worse?

    python scripts/eval_retrieval_e2e.py generate --out answers.json [--limit 3]
    python scripts/eval_retrieval_e2e.py sheet    --answers answers.json --out-dir grading/
    python scripts/eval_retrieval_e2e.py score    --answers answers.json --grades grades.json --out report.md

The questions, conditions, grading scheme and decision rule are in
docs/eval/retrieval_e2e_protocol_2026-10-08.json, committed before the first run
(docs/eval/retrieval_quality_2026-10-08.md is the measurement this follows up).

WHAT IS HELD FIXED, AND WHY
---------------------------
backend.core.pipeline.run_sync is the app's own path - Stages 0-10, the real Stage 5 retrieval
(12-word hint, top_k 3) and the real Stage 7 prompt. Only two things are changed:

  * the cut-off, by setting vector_store.DEFAULT_SIMILARITY_THRESHOLD (query() resolves it per call);
  * the provider, a subclass of the app's OllamaProvider that adds temperature 0 and a seed to the
    request and keeps what Ollama reports back (prompt_eval_count). With sampling pinned, the same
    prompt gives the same answer, so the ONLY thing that differs between conditions is the
    context. That is a controlled comparison and not what a user sees (their model samples at
    Ollama's default temperature); it is the right design for "does the context change the
    answer", and a wrong one for "what will a user see on a given day".

When two conditions retrieve the same passages for a question, the prompt is identical and its answer
is generated once and shared, so a difference between conditions can only come from a difference in
the passages.

The profile is a fresh in-memory one with no identity, projects, decisions or history, so documents
are the only thing that varies. Nothing here touches a real profile or key.

GRADING is done by a person or an assistant reading each distinct answer once, with the condition
and the retrieved passages hidden (`sheet` shuffles with a fixed seed and writes the key to a
separate file). Hiding is imperfect: an answer that says "according to the documents" gives its
condition away. It is still the same hand that wrote the questions, and the report says so.
"""

import argparse
import hashlib
import json
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PROTOCOL = REPO / "docs" / "eval" / "retrieval_e2e_protocol_2026-10-08.json"
LABELS = REPO / "docs" / "eval" / "retrieval_labels_2026-10-08.json"
SHEET_SEED = 20261008
SAMPLE_CHARS = 1400  # an answer longer than this is cut on the sheet, and marked so


def norm(text: str) -> str:
    return " ".join(text.lower().split())


def read_corpus(commit: str, files: list[str]) -> dict[str, str]:
    out = {}
    for name in files:
        out[name] = subprocess.run(
            ["git", "-C", str(REPO), "show", f"{commit}:{name}"],
            capture_output=True, text=True, encoding="utf-8", check=True,
        ).stdout
    return out


def reference_line(text: str, key: str) -> str:
    """The source line holding the key phrase, plus the one after it (a fact often ends on the next line)."""
    lines = text.split("\n")
    k = norm(key)
    for i, line in enumerate(lines):
        window = norm(" ".join(lines[i:i + 2]))
        if k in window:
            return " ".join(l.strip() for l in lines[max(0, i - 1):i + 3] if l.strip())[:700]
    return "(key not found in a window of lines - see the source document)"


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------


def generate(args) -> None:
    protocol = json.load(open(PROTOCOL, encoding="utf-8"))
    labels = json.load(open(LABELS, encoding="utf-8"))
    conditions = {name: c["similarity_threshold"] for name, c in protocol["conditions"].items()}
    max_tokens = protocol["held_fixed"]["max_tokens"]

    work = Path(tempfile.mkdtemp(prefix="pip_eval_e2e_"))
    os.environ["PIP_DATA_DIR"] = str(work / "data")
    os.environ["PIP_DB_PATH"] = str(work / "data" / "pip.db")
    os.environ["PIP_DOCUMENTS_ROOT"] = str(work / "documents")
    os.environ["PIP_CHROMA_PATH"] = str(work / "chroma")
    os.environ.pop("PIP_DB_KEY", None)
    sys.path.insert(0, str(REPO))

    from backend.core import pipeline, response_cache
    from backend.memory import profile_store, vector_store
    from backend.providers.base_provider import ProviderExecutionError, ProviderUnavailableError
    from backend.providers.ollama_provider import OllamaProvider

    class PinnedOllama(OllamaProvider):
        """OllamaProvider.chat with temperature and seed added, and Ollama's own counts kept."""

        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.last: dict = {}
            self.watch: str | None = None  # the question's key phrase, to see whether the PROMPT holds it

        def chat(self, messages, context=None, max_tokens=2000, timeout_seconds=30, response_format=None):
            if context:
                messages = [{"role": "system", "content": context}] + messages
            # Stage 7 caps the documents section (settings.json context_assembly.rag_chunks_tokens, 800
            # words), so passages Stage 5 returned can be cut before the model sees them. What the
            # model was SHOWN is what counts, not what was retrieved.
            prompt_has_key = None if self.watch is None else self.watch in norm(" ".join(m["content"] for m in messages))
            payload = {
                "model": self.model_name, "messages": messages, "stream": True,
                "options": {"num_predict": max_tokens, "temperature": 0, "seed": 1},
            }
            req = urllib.request.Request(
                f"{self.host}/api/chat", data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST",
            )
            self.last = {"prompt_chars": sum(len(m["content"]) for m in messages), "prompt_has_key": prompt_has_key}
            try:
                with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
                    for line in response:
                        if not line:
                            continue
                        chunk = json.loads(line.decode("utf-8"))
                        if chunk.get("done"):
                            self.last["prompt_eval_count"] = chunk.get("prompt_eval_count")
                            self.last["eval_count"] = chunk.get("eval_count")
                            self.last["done_reason"] = chunk.get("done_reason")
                        piece = chunk.get("message", {}).get("content")
                        if piece:
                            yield piece
            except Exception as e:  # same two classes the app's provider raises
                raise ProviderExecutionError(f"Ollama: {e}")

    model = "qwen2.5:7b"
    if not OllamaProvider(model_name=model).is_available():
        sys.exit("Ollama is not reachable on localhost:11434 - start it first")

    corpus = read_corpus(labels["snapshot_commit"], labels["corpus"])
    docs_root = work / "documents"
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

    key_of = {q["id"]: norm(q["key"]) for q in labels["answerable"]}
    questions = [("answerable", q["id"], q["question"]) for q in labels["answerable"]]
    questions += [("unanswerable", q["id"], q["question"]) for q in protocol["unanswerable"]]
    if args.only:
        wanted = set(args.only.split(","))
        questions = [q for q in questions if q[1] in wanted]
    if args.limit:
        questions = questions[: args.limit]

    # What the pipeline's own Stage 5 returned, whichever threshold is set.
    seen = {}
    real_stage_05_run = pipeline.stage_05.run

    def spy(conn_, hint, project_id=None, threshold=None, top_k=None):
        result = real_stage_05_run(conn_, hint, project_id, threshold, top_k)
        seen["chunks"] = result["chunks"]
        return result

    pipeline.stage_05.run = spy

    out_path = Path(args.out)
    state = json.load(open(out_path, encoding="utf-8")) if out_path.exists() else {
        "model": model, "snapshot_commit": labels["snapshot_commit"], "conditions": conditions,
        "records": [], "answers": {},
    }
    done = {(r["qid"], r["condition"]) for r in state["records"]}

    def save():
        json.dump(state, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # Warm-up: loads the model into memory so the first real call does not time out waiting for it.
    warm = PinnedOllama(model_name=model)
    list(warm.chat([{"role": "user", "content": "Say ready."}], max_tokens=5, timeout_seconds=300))
    print("model warm", flush=True)

    from backend.stages import stage_01_intent_classifier as stage_01

    for group, qid, question in questions:
        hint = stage_01.run(question, conn=conn)["retrieval_hint"]
        plan = {}
        for cond, threshold in conditions.items():
            vector_store.DEFAULT_SIMILARITY_THRESHOLD = threshold
            chunks = real_stage_05_run(conn, hint, None)["chunks"]
            plan[cond] = (threshold, [(c["file_path"], c["chunk_index"]) for c in chunks], chunks)
        for cond, (threshold, ids, chunks) in plan.items():
            if (qid, cond) in done:
                continue
            prompt_key = hashlib.sha1(repr(ids).encode()).hexdigest()[:10]
            answer_id = f"{qid}|{prompt_key}"
            if answer_id not in state["answers"]:
                vector_store.DEFAULT_SIMILARITY_THRESHOLD = threshold
                response_cache.clear()
                provider = PinnedOllama(model_name=model)
                provider.watch = key_of.get(qid)
                t0 = time.time()
                try:
                    result = pipeline.run_sync(
                        conn, question, providers=[provider], max_tokens=max_tokens, timeout_seconds=300,
                    )
                except (ProviderUnavailableError, ProviderExecutionError) as e:
                    sys.exit(f"provider failed on {answer_id}: {e}")
                used = [(c["file_path"], c["chunk_index"]) for c in seen.get("chunks", [])]
                state["answers"][answer_id] = {
                    "qid": qid, "group": group, "question": question,
                    "status": result["status"], "error": result.get("error"),
                    "text": result["response_text"], "seconds": round(time.time() - t0, 1),
                    "pipeline_passages_match_plan": used == ids, **provider.last,
                }
                print(f"{qid} {cond} t={threshold}: {len(ids)} passages, {state['answers'][answer_id]['seconds']}s, "
                      f"prompt_eval={provider.last.get('prompt_eval_count')}, status={result['status']}", flush=True)
            state["records"].append({
                "qid": qid, "group": group, "condition": cond, "threshold": threshold,
                "answer_id": answer_id,
                "passages": [
                    {"file": Path(c["file_path"]).name.replace("__", "/"), "chunk_index": c["chunk_index"],
                     "similarity": round(c["similarity"], 4), "text": c["chunk_text"]}
                    for c in chunks
                ],
            })
            save()
    pipeline.stage_05.run = real_stage_05_run
    shutil.rmtree(work, ignore_errors=True)
    print(f"wrote {out_path}")


# ---------------------------------------------------------------------------
# sheet
# ---------------------------------------------------------------------------


def sheet(args) -> None:
    state = json.load(open(args.answers, encoding="utf-8"))
    labels = json.load(open(LABELS, encoding="utf-8"))
    corpus = read_corpus(labels["snapshot_commit"], labels["corpus"])
    by_q = {q["id"]: q for q in labels["answerable"]}

    ids = sorted(state["answers"])
    random.Random(SHEET_SEED).shuffle(ids)
    key = {}
    parts = ["# Grading sheet\n",
             "Label each answer: CORRECT, DECLINES, WRONG or VAGUE (definitions in docs/eval/retrieval_e2e_protocol_2026-10-08.json).",
             "The condition and the retrieved passages are not shown.\n"]
    for n, aid in enumerate(ids, 1):
        a = state["answers"][aid]
        key[str(n)] = aid
        if a["group"] == "answerable":
            q = by_q[a["qid"]]
            ref = reference_line(corpus[q["source"]], q["key"])
            ref_text = f"REFERENCE (from {q['source']}): {ref}"
        else:
            ref_text = "REFERENCE: no document answers this. A specific answer given as fact is WRONG."
        text = a["text"].strip()
        cut = " [CUT: answer longer than the sheet shows]" if len(text) > SAMPLE_CHARS else ""
        parts.append(f"## {n}\nQ: {a['question']}\n{ref_text}\nANSWER: {text[:SAMPLE_CHARS]}{cut}\n")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sheet.md").write_text("\n".join(parts), encoding="utf-8")
    json.dump(key, open(out_dir / "key.json", "w", encoding="utf-8"))
    print(f"{len(ids)} answers to grade -> {out_dir / 'sheet.md'} (key kept apart in key.json)")


# ---------------------------------------------------------------------------
# score
# ---------------------------------------------------------------------------


def sign_test(better: int, worse: int) -> float:
    import math
    n = better + worse
    if n == 0:
        return 1.0
    k = max(better, worse)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k, n + 1)) / 2**n)


def score(args) -> None:
    state = json.load(open(args.answers, encoding="utf-8"))
    grades_by_number = json.load(open(args.grades, encoding="utf-8"))
    key = json.load(open(Path(args.key), encoding="utf-8"))
    label = {key[n]: g.upper() for n, g in grades_by_number.items()}
    missing = [a for a in state["answers"] if a not in label]
    if missing:
        sys.exit(f"{len(missing)} answers have no grade, e.g. {missing[:3]}")
    labels = json.load(open(LABELS, encoding="utf-8"))
    keys = {q["id"]: norm(q["key"]) for q in labels["answerable"]}
    conds = list(state["conditions"])
    base = conds[0]

    by = {}
    for r in state["records"]:
        by.setdefault((r["group"], r["condition"]), {})[r["qid"]] = r
    out = ["# End-to-end check on the similarity cut-off - results\n"]
    p = out.append
    p(f"Model {state['model']}, snapshot `{state['snapshot_commit']}`, temperature 0. Conditions: "
      + ", ".join(f"{c} = {t}" for c, t in state["conditions"].items()) + ".\n")

    def counts(group, cond):
        c = {"CORRECT": 0, "DECLINES": 0, "WRONG": 0, "VAGUE": 0}
        for qid, r in by[(group, cond)].items():
            c[label[r["answer_id"]]] += 1
        return c

    for group, title in (("answerable", "The 54 answerable questions"), ("unanswerable", "The 12 questions no document answers")):
        p(f"## {title}\n")
        p("| condition | cut-off | questions that got passages | CORRECT | DECLINES | WRONG | VAGUE |")
        p("|---|---|---|---|---|---|---|")
        for cond in conds:
            c = counts(group, cond)
            got = sum(1 for r in by[(group, cond)].values() if r["passages"])
            p(f"| {cond} | {state['conditions'][cond]} | {got} | {c['CORRECT']} | {c['DECLINES']} | {c['WRONG']} | {c['VAGUE']} |")
        p("")

    p("## Paired against condition " + base + " (same question, only the passages differ)\n")
    p("| condition | answerable: more CORRECT / fewer CORRECT (sign test p) | answerable: WRONG rose / fell | unanswerable: WRONG rose / fell | unanswerable: DECLINES rose / fell |")
    p("|---|---|---|---|---|")
    for cond in conds[1:]:
        cells = []
        for group, what in (("answerable", "CORRECT"), ("answerable", "WRONG"), ("unanswerable", "WRONG"), ("unanswerable", "DECLINES")):
            up = down = 0
            for qid, r in by[(group, cond)].items():
                a, b = label[by[(group, base)][qid]["answer_id"]] == what, label[r["answer_id"]] == what
                up += (b and not a)
                down += (a and not b)
            cells.append((up, down))
        p(f"| {cond} | {cells[0][0]} / {cells[0][1]} (p = {sign_test(*cells[0]):.2f}) | {cells[1][0]} / {cells[1][1]} | {cells[2][0]} / {cells[2][1]} | {cells[3][0]} / {cells[3][1]} |")

    p("\n## The pre-registered decision rule\n")
    for cond in conds[1:]:
        gain = rise_wrong_unans = rise_wrong_ans = 0
        up = down = 0
        for qid, r in by[("answerable", cond)].items():
            a = label[by[("answerable", base)][qid]["answer_id"]]
            b = label[r["answer_id"]]
            up += (b == "CORRECT" and a != "CORRECT")
            down += (a == "CORRECT" and b != "CORRECT")
            rise_wrong_ans += (b == "WRONG" and a != "WRONG") - (a == "WRONG" and b != "WRONG")
        for qid, r in by[("unanswerable", cond)].items():
            a = label[by[("unanswerable", base)][qid]["answer_id"]]
            b = label[r["answer_id"]]
            rise_wrong_unans += (b == "WRONG" and a != "WRONG") - (a == "WRONG" and b != "WRONG")
        c1 = (up - down) >= 8 and sign_test(up, down) < 0.05
        c2 = rise_wrong_unans <= 2
        c3 = rise_wrong_ans <= 0
        p(f"- **{cond}** (cut-off {state['conditions'][cond]}): (1) correct answers up by {up - down} (needs 8+, p < 0.05): {'met' if c1 else 'NOT met'}; "
          f"(2) invented answers to unanswerable questions up by {rise_wrong_unans} (needs 2 or fewer): {'met' if c2 else 'NOT met'}; "
          f"(3) wrong answers among the answerable up by {rise_wrong_ans} (needs 0 or fewer): {'met' if c3 else 'NOT met'}. "
          f"**{'SUPPORTED' if (c1 and c2 and c3) else 'NOT supported'}**")

    p("\n## What the model was shown\n")
    p("Stage 7 caps the documents section at 800 words, so passages Stage 5 returns can be cut before the model")
    p("sees them. Split by what the PROMPT held, not what was retrieved:\n")
    p("| condition | answer in the prompt: CORRECT of | answer retrieved but cut by the 800-word cap: CORRECT of | passages without the answer: CORRECT / DECLINES / WRONG / VAGUE | no passages: CORRECT / DECLINES / WRONG / VAGUE |")
    p("|---|---|---|---|---|")
    for cond in conds:
        shown = [0, 0]
        cut = [0, 0]
        without = {"CORRECT": 0, "DECLINES": 0, "WRONG": 0, "VAGUE": 0}
        none_ = dict(without)
        for qid, r in by[("answerable", cond)].items():
            g = label[r["answer_id"]]
            in_prompt = state["answers"][r["answer_id"]].get("prompt_has_key")
            retrieved = any(keys[qid] in norm(x["text"]) for x in r["passages"])
            if in_prompt:
                shown[1] += 1
                shown[0] += g == "CORRECT"
            elif retrieved:
                cut[1] += 1
                cut[0] += g == "CORRECT"
            elif r["passages"]:
                without[g] += 1
            else:
                none_[g] += 1
        fmt = lambda d: " / ".join(str(d[k]) for k in ("CORRECT", "DECLINES", "WRONG", "VAGUE"))
        p(f"| {cond} | {shown[0]} of {shown[1]} | {cut[0]} of {cut[1]} | {fmt(without)} | {fmt(none_)} |")

    p("\n## Checks\n")
    ans = state["answers"].values()
    p(f"- distinct prompts run: {len(state['answers'])}; every status success: {all(a['status'] == 'success' for a in ans)}")
    p(f"- the pipeline's own retrieval matched the plan on {sum(1 for a in ans if a['pipeline_passages_match_plan'])} of {len(state['answers'])}")
    pe = [a.get("prompt_eval_count") or 0 for a in ans]
    p(f"- largest prompt Ollama counted: {max(pe)} tokens (a prompt longer than the model's context window is cut without error; see the context length Ollama loaded the model with)")
    cut = sum(1 for a in ans if a.get("done_reason") == "length")
    p(f"- answers that hit the {400}-token limit: {cut}")
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
    s = sub.add_parser("sheet")
    s.add_argument("--answers", required=True)
    s.add_argument("--out-dir", required=True)
    c = sub.add_parser("score")
    c.add_argument("--answers", required=True)
    c.add_argument("--grades", required=True)
    c.add_argument("--key", required=True)
    c.add_argument("--out", default=None)
    args = ap.parse_args()
    {"generate": generate, "sheet": sheet, "score": score}[args.cmd](args)


if __name__ == "__main__":
    main()
