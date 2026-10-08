"""
Measure how well PIP's document search finds the passage that answers a question.

    python scripts/eval_retrieval.py run    --labels docs/eval/retrieval_labels_2026-10-08.json --out results.json
    python scripts/eval_retrieval.py run    ... --shim          # the hashed bag-of-words stand-in, for comparison
    python scripts/eval_retrieval.py report --results results.json

WHAT IS MEASURED, AND WHY IT IS NOT JUST "DOES SEARCH WORK"
-----------------------------------------------------------
Three layers, because a question can fail to be answered at any of them:

  1. Ranking. vector_store.query() returns the nearest chunks by cosine similarity and drops
     any below similarity_threshold (0.6, marked in settings.json and vector_store.py as "start
     0.6, calibrate from real usage" - this is that calibration). It is called here with
     threshold 0 and top_k 10 so ONE run yields every threshold's behaviour; the sweep is
     computed afterwards.
  2. Chunking. Documents are cut into chunk_size_tokens-word chunks, but all-MiniLM-L6-v2 reads
     at most 256 tokens (vector_store.py names this a KNOWN TRADEOFF). A fact deep inside a
     500-word chunk may be invisible to search. Measured by chunk size, and by where in its chunk
     the answer sits.
  3. What is searched with. The pipeline searches with only the first 12 words of the question
     (stage_01 _extract_retrieval_hint), so both the full question and its 12-word trim are run.

Stage 1 also computes skip_rag, and a first draft of this script reported how many questions it
would keep from reaching search. That was wrong and was removed before any result was recorded:
pipeline.py runs Stage 5 on EVERY turn (ADR-002, "Router is a priority-orderer, not a
stage-skipper"), and stage_02 accepts skip_rag without using it. skip_rag is computed and
affects nothing today, so it is not a factor in whether a document is found.

HOW A QUESTION COUNTS AS ANSWERED
---------------------------------
By a returned chunk CONTAINING a short key phrase that occurs in exactly the stated source
document. That keeps the label valid whatever the chunk size, which a chunk-id label could not.
It is a lexical test of a semantic system: a chunk that holds the answer in other words is
counted as a miss, so the numbers are a floor on usefulness, not a ceiling.

The labelled questions are committed BEFORE the first run (the Observer measurement's rule,
1256b51), so they cannot be tuned to the results. The corpus is the project's own documents at
a pinned commit, read with `git show`, so a later edit to a document cannot move the result.

Nothing here touches real data: every path is a temporary directory, and no PIP_DB_KEY is set.
"""

import argparse
import json
import math
import os
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOP_K = 10
HINT_WORDS = 12  # stage_01_intent_classifier._extract_retrieval_hint
THRESHOLDS = [round(0.05 * i, 2) for i in range(0, 19)]  # 0.00 .. 0.90
PRODUCTION_TOP_K = 3  # settings.json rag.top_k_results
OFFSET_BUCKETS = [(0, 100), (100, 200), (200, 300), (300, 10_000)]


def norm(text: str) -> str:
    return " ".join(text.lower().split())


def hint(question: str) -> str:
    return " ".join(question.split()[:HINT_WORDS])


def read_corpus(commit: str, files: list[str]) -> dict[str, str]:
    out = {}
    for name in files:
        shown = subprocess.run(
            ["git", "-C", str(REPO), "show", f"{commit}:{name}"],
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
        out[name] = shown.stdout
    return out


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


def run(args) -> None:
    labels = json.load(open(args.labels, encoding="utf-8"))
    work = Path(tempfile.mkdtemp(prefix="pip_eval_retrieval_"))
    # Isolated BEFORE anything from backend/ is imported: these are read at call time, but a
    # path that was ever the real one is a path somebody can write to by mistake.
    os.environ["PIP_DATA_DIR"] = str(work / "data")
    os.environ["PIP_DB_PATH"] = str(work / "data" / "pip.db")
    os.environ["PIP_DOCUMENTS_ROOT"] = str(work / "documents")
    os.environ["PIP_CHROMA_PATH"] = str(work / "chroma")
    os.environ.pop("PIP_DB_KEY", None)
    sys.path.insert(0, str(REPO))
    if args.shim:
        sys.path.insert(0, str(REPO / "docs" / "eval" / "reliability_2026-10-01"))
        import pip_embed_shim  # noqa: F401  (installs the stand-in sentence_transformers)

    import sentence_transformers

    from backend.memory import profile_store, vector_store

    embedder = "shim (hashed bag-of-words)" if getattr(sentence_transformers, "__pip_shim__", False) else "all-MiniLM-L6-v2"
    print(f"embedder: {embedder}", flush=True)

    corpus = read_corpus(labels["snapshot_commit"], labels["corpus"])
    docs_root = work / "documents"
    docs_root.mkdir(parents=True)
    on_disk = {}
    for name, text in corpus.items():
        flat = name.replace("/", "__")
        (docs_root / flat).write_text(text, encoding="utf-8")
        on_disk[name] = docs_root / flat

    answerable = labels["answerable"]
    off_topic = labels["off_topic"]
    near_topic = labels["near_topic"]

    results = {
        "embedder": embedder,
        "snapshot_commit": labels["snapshot_commit"],
        "top_k": TOP_K,
        "configs": [],
    }

    # The model reads at most max_seq_length tokens of a chunk (vector_store.py, KNOWN TRADEOFF).
    # The stand-in has no tokenizer, so the token analysis is simply absent for it.
    model = vector_store._get_model()
    tokenizer = getattr(model, "tokenizer", None)
    window = getattr(model, "max_seq_length", None)
    results["max_seq_length"] = window

    def token_count(text: str) -> int | None:
        if tokenizer is None:
            return None
        return len(tokenizer(text, add_special_tokens=False)["input_ids"])

    for size in [int(s) for s in args.chunk_sizes.split(",")]:
        overlap = max(size // 10, 5)
        os.environ["PIP_CHROMA_PATH"] = str(work / f"chroma_{size}")
        vector_store.reset_client()
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        profile_store.initialize_schema(conn)

        t = time.time()
        for name, path in on_disk.items():
            vector_store.ingest_document(conn, str(path), chunk_size_tokens=size, overlap_tokens=overlap)
        ingest_seconds = time.time() - t
        chunk_total = vector_store._get_collection().count()
        print(f"chunk size {size}/{overlap}: {chunk_total} chunks, ingested in {ingest_seconds:.1f}s", flush=True)

        # Where each answer sits inside the chunk that holds it - independent of retrieval, so the
        # denominator of the "blind spot" analysis is every question, not only the ones found.
        # A key that sits across two chunks is in no single chunk, so no search could ever find it;
        # such a question is absent from `positions` and the report counts it as unwinnable rather
        # than letting it silently lower the score of a small chunk size.
        positions = {}
        chunk_token_counts = []
        for q in answerable:
            key = norm(q["key"])
            for i, chunk in enumerate(vector_store._chunk_text(corpus[q["source"]], size, overlap)):
                c = norm(chunk)
                at = c.find(key)
                if at >= 0:
                    pos = {"chunk": i, "word_offset": len(c[:at].split()), "chunk_words": len(c.split())}
                    tokens_before = token_count(c[:at])
                    if tokens_before is not None:
                        pos["token_offset"] = tokens_before
                        pos["chunk_tokens"] = token_count(c)
                    positions[q["id"]] = pos
                    break
        if tokenizer is not None:
            for name in on_disk:
                chunk_token_counts += [token_count(norm(c)) for c in vector_store._chunk_text(corpus[name], size, overlap)]

        records = []
        latencies = []

        def search(text: str):
            t0 = time.time()
            found = vector_store.query(conn, text, threshold=0.0, top_k=TOP_K)
            latencies.append(time.time() - t0)
            return found

        for q in answerable:
            key = norm(q["key"])
            for mode, text in (("raw", q["question"]), ("hint12", hint(q["question"]))):
                found = search(text)
                ranked = [
                    {
                        "sim": round(f["similarity"], 4),
                        "hit": key in norm(f["chunk_text"]),
                        "file": Path(f["file_path"]).name.replace("__", "/"),
                    }
                    for f in found
                ]
                first = next((i + 1 for i, r in enumerate(ranked) if r["hit"]), None)
                records.append({
                    "id": q["id"], "kind": q["kind"], "source": q["source"], "mode": mode,
                    "words": len(q["question"].split()), "first_hit_rank": first, "ranked": ranked,
                })
        for group, items in (("off_topic", off_topic), ("near_topic", near_topic)):
            for q in items:
                for mode, text in (("raw", q["question"]), ("hint12", hint(q["question"]))):
                    found = search(text)
                    records.append({
                        "id": q["id"], "kind": group, "mode": mode,
                        "ranked": [{"sim": round(f["similarity"], 4), "file": Path(f["file_path"]).name.replace("__", "/")} for f in found],
                    })

        results["configs"].append({
            "chunk_size": size, "overlap": overlap, "chunks": chunk_total,
            "ingest_seconds": round(ingest_seconds, 1),
            "median_query_ms": round(statistics.median(latencies) * 1000, 1),
            "chunk_token_counts": chunk_token_counts,
            "positions": positions, "records": records,
        })
        conn.close()

    json.dump(results, open(args.out, "w", encoding="utf-8"), separators=(",", ":"), ensure_ascii=False)
    shutil.rmtree(work, ignore_errors=True)
    print(f"wrote {args.out}")


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def pct(n, d):
    return f"{100 * n / d:.0f}%" if d else "-"


def sign_test(better: int, worse: int) -> float:
    """Two-sided exact p for 'these differences are as likely to go either way', ties ignored."""
    n = better + worse
    if n == 0:
        return 1.0
    k = max(better, worse)
    tail = sum(math.comb(n, i) for i in range(k, n + 1)) / 2**n
    return min(1.0, 2 * tail)


def quantiles(values):
    if not values:
        return "-"
    v = sorted(values)
    q = lambda p: v[min(len(v) - 1, int(p * len(v)))]
    return f"min {v[0]:.2f} | p25 {q(0.25):.2f} | median {statistics.median(v):.2f} | p75 {q(0.75):.2f} | max {v[-1]:.2f}"


def answerable(records, mode):
    return [r for r in records if r["kind"] not in ("off_topic", "near_topic") and r["mode"] == mode]


def at_threshold(record, t, top_k=PRODUCTION_TOP_K):
    return [r for r in record["ranked"][:top_k] if r["sim"] >= t]


def report(args) -> None:
    res = json.load(open(args.results, encoding="utf-8"))
    out = []
    p = out.append
    p(f"# Retrieval measurement - {res['embedder']}")
    p(f"\nCorpus snapshot `{res['snapshot_commit']}`. Search depth {res['top_k']} for ranking; production top_k {PRODUCTION_TOP_K}.\n")

    p("## 1. Chunk sizes")
    p("\n| chunk words (overlap) | chunks | ingest | median query |")
    p("|---|---|---|---|")
    for c in res["configs"]:
        p(f"| {c['chunk_size']} ({c['overlap']}) | {c['chunks']} | {c['ingest_seconds']} s | {c['median_query_ms']} ms |")

    prod = next((c for c in res["configs"] if c["chunk_size"] == 500), res["configs"][0])

    for mode, title in (("raw", "full question"), ("hint12", "first 12 words (what the pipeline really searches with)")):
        p(f"\n## 2{'a' if mode == 'raw' else 'b'}. Ranking by chunk size (500 words is the current setting), searching with the {title}")
        p("\n| chunking | hit@1 | hit@3 | hit@5 | hit@10 | MRR@10 |")
        p("|---|---|---|---|---|---|")
        for c in res["configs"]:
            recs = answerable(c["records"], mode)
            n = len(recs)
            hits = lambda k: sum(1 for r in recs if r["first_hit_rank"] and r["first_hit_rank"] <= k)
            mrr = sum(1 / r["first_hit_rank"] for r in recs if r["first_hit_rank"]) / n
            mark = " (current)" if c["chunk_size"] == 500 else ""
            p(f"| {c['chunk_size']}{mark} | {pct(hits(1), n)} | {pct(hits(3), n)} | {pct(hits(5), n)} | {pct(hits(10), n)} | {mrr:.2f} |")

    p("\n## 2c. Checks on the measurement itself")
    p("\nA hit needs the key phrase inside ONE returned chunk, which can make a score look worse than the")
    p("search really is (a small chunk can cut the phrase in two; a passage can state the answer in other")
    p("words), and a difference between two chunk sizes can be luck on 54 questions. Each is counted here")
    p("instead of being left to be guessed at.\n")
    p("| chunking | key split across two chunks (unwinnable) | right DOCUMENT in top 3 | right CHUNK (key) in top 3 | better than 500 / worse than 500 (key, top 3; sign test p) |")
    p("|---|---|---|---|---|")
    base = {r["id"]: r for r in answerable(prod["records"], "hint12")}
    in3 = lambda r: bool(r["first_hit_rank"] and r["first_hit_rank"] <= PRODUCTION_TOP_K)
    for c in res["configs"]:
        recs = answerable(c["records"], "hint12")
        n = len(recs)
        unwinnable = n - len(c["positions"])
        doc3 = sum(1 for r in recs if any(x["file"] == r["source"] for x in r["ranked"][:PRODUCTION_TOP_K]))
        better = sum(1 for r in recs if in3(r) and not in3(base[r["id"]]))
        worse = sum(1 for r in recs if not in3(r) and in3(base[r["id"]]))
        versus = "-" if c is prod else f"{better} / {worse} (p = {sign_test(better, worse):.2f})"
        p(f"| {c['chunk_size']} | {unwinnable} | {pct(doc3, n)} | {pct(sum(1 for r in recs if in3(r)), n)} | {versus} |")
    p("\nThe right-document column is the generous reading (the passage may be elsewhere in the right file); the")
    p("key column is the strict one. The truth about usefulness lies between them. The last column is a paired")
    p("comparison on the same 54 questions: with 54 questions one question is 1.9 percentage points, and a")
    p("difference only means something if the 'better' count clearly exceeds the 'worse' count.")

    p("\n## 3. By kind of question (current chunking, 12-word search)")
    p("\n| kind | questions | hit@3 | hit@10 |")
    p("|---|---|---|---|")
    recs = answerable(prod["records"], "hint12")
    for kind in sorted({r["kind"] for r in recs}):
        rs = [r for r in recs if r["kind"] == kind]
        p(f"| {kind} | {len(rs)} | {pct(sum(1 for r in rs if r['first_hit_rank'] and r['first_hit_rank'] <= 3), len(rs))} | {pct(sum(1 for r in rs if r['first_hit_rank']), len(rs))} |")
    p("\n| source document | questions | hit@3 |")
    p("|---|---|---|")
    for src in sorted({r["source"] for r in recs}):
        rs = [r for r in recs if r["source"] == src]
        p(f"| {src} | {len(rs)} | {pct(sum(1 for r in rs if r['first_hit_rank'] and r['first_hit_rank'] <= 3), len(rs))} |")

    p("\n## 4. Does the 12-word trim cost anything?")
    long_ids = {r["id"] for r in answerable(prod["records"], "raw") if r["words"] > HINT_WORDS}
    p(f"\n{len(long_ids)} of {len(answerable(prod['records'], 'raw'))} questions are longer than {HINT_WORDS} words.")
    for mode in ("raw", "hint12"):
        rs = [r for r in answerable(prod["records"], mode) if r["id"] in long_ids]
        p(f"- {mode}: hit@3 on those questions = {pct(sum(1 for r in rs if r['first_hit_rank'] and r['first_hit_rank'] <= 3), len(rs))}")

    p("\n## 5. The threshold (production top_k = 3, current chunking, 12-word search)")
    p("\nWhat each cut-off would do. 'answered' = a returned chunk holds the answer. 'off-topic returned' = an off-topic question still got something back.\n")
    p("'passages that hold the answer' counts every returned passage, so it is what the model is actually handed:")
    p("the rest is context that does not answer the question (this project's own record, FREEZE_LIST section 10,")
    p("'Fine-tuning rejected', is that misleading context - not a missing fact - made the model fabricate).\n")
    p("| threshold | answered | chunks returned per question | passages that hold the answer | off-topic returned | near-topic returned |")
    p("|---|---|---|---|---|---|")
    a_recs = answerable(prod["records"], "hint12")
    off = [r for r in prod["records"] if r["kind"] == "off_topic" and r["mode"] == "hint12"]
    near = [r for r in prod["records"] if r["kind"] == "near_topic" and r["mode"] == "hint12"]
    for t in THRESHOLDS:
        answered = sum(1 for r in a_recs if any(x["hit"] for x in at_threshold(r, t)))
        returned = statistics.mean(len(at_threshold(r, t)) for r in a_recs)
        total = sum(len(at_threshold(r, t)) for r in a_recs)
        holding = sum(sum(1 for x in at_threshold(r, t) if x["hit"]) for r in a_recs)
        o = sum(1 for r in off if at_threshold(r, t))
        n = sum(1 for r in near if at_threshold(r, t))
        mark = "  <- current" if abs(t - 0.6) < 1e-9 else ""
        p(f"| {t:.2f}{mark} | {pct(answered, len(a_recs))} ({answered} of {len(a_recs)}) | {returned:.1f} | {pct(holding, total)} | {pct(o, len(off))} | {pct(n, len(near))} |")

    p("\n## 6. How well the scores separate right from wrong")
    hit_sims = [next(x["sim"] for x in r["ranked"] if x["hit"]) for r in a_recs if r["first_hit_rank"]]
    top1_off = [r["ranked"][0]["sim"] for r in off if r["ranked"]]
    top1_near = [r["ranked"][0]["sim"] for r in near if r["ranked"]]
    top1_miss = [r["ranked"][0]["sim"] for r in a_recs if r["ranked"] and not (r["first_hit_rank"] and r["first_hit_rank"] <= 3)]
    p(f"\n- similarity of the chunk that holds the answer: {quantiles(hit_sims)}")
    p(f"- best similarity for an OFF-TOPIC question: {quantiles(top1_off)}")
    p(f"- best similarity for a NEAR-TOPIC question: {quantiles(top1_near)}")
    p(f"- best similarity for answerable questions that were NOT found in the top 3: {quantiles(top1_miss)}")

    p("\n## 7. The 256-token blind spot (answer position inside its chunk)")
    window = res.get("max_seq_length")
    if window:
        usable = window - 2  # [CLS] and [SEP] take two of the model's positions
        p(f"\nThe model reads {window} tokens of a chunk ({usable} of them text). Counted with the model's own tokenizer:\n")
        p("| chunking | median chunk length (tokens) | share of all chunk text the model cannot see | answer starts inside the readable part: hit@3 | answer starts beyond it: hit@3 |")
        p("|---|---|---|---|---|")
        for c in res["configs"]:
            counts = c.get("chunk_token_counts") or []
            if not counts:
                continue
            unseen = sum(max(0, t - usable) for t in counts) / sum(counts)
            by_id = {r["id"]: r for r in answerable(c["records"], "hint12")}
            inside = [i for i, pos in c["positions"].items() if pos["token_offset"] < usable and i in by_id]
            beyond = [i for i, pos in c["positions"].items() if pos["token_offset"] >= usable and i in by_id]
            h = lambda ids: sum(1 for i in ids if by_id[i]["first_hit_rank"] and by_id[i]["first_hit_rank"] <= PRODUCTION_TOP_K)
            p(f"| {c['chunk_size']} | {statistics.median(counts):.0f} | {100 * unseen:.0f}% | {pct(h(inside), len(inside))} of {len(inside)} | {pct(h(beyond), len(beyond))} of {len(beyond)} |")
    else:
        p("\n(no tokenizer for this embedder, so the token-level test is not available; word positions only)")
    for c in res["configs"]:
        if c["chunk_size"] not in (500, 300, 200):
            continue
        p(f"\n**{c['chunk_size']}-word chunks** - hit@3 by where the answer starts in its chunk (12-word search):\n")
        p("| answer starts at word | questions | hit@3 |")
        p("|---|---|---|")
        by_id = {r["id"]: r for r in answerable(c["records"], "hint12")}
        for lo, hi in OFFSET_BUCKETS:
            ids = [i for i, pos in c["positions"].items() if lo <= pos["word_offset"] < hi and i in by_id]
            hits = sum(1 for i in ids if by_id[i]["first_hit_rank"] and by_id[i]["first_hit_rank"] <= 3)
            label = f"{lo}-{hi}" if hi < 10_000 else f"{lo}+"
            p(f"| {label} | {len(ids)} | {pct(hits, len(ids))} |")

    p("\n## 8. Misses (current chunking, 12-word search): answerable but not in the top 3")
    for r in a_recs:
        if not (r["first_hit_rank"] and r["first_hit_rank"] <= 3):
            best = r["ranked"][0] if r["ranked"] else None
            p(f"- `{r['id']}` first hit rank {r['first_hit_rank']}; best chunk {best['sim'] if best else '-'} from {best['file'] if best else '-'}")

    text = "\n".join(out)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--labels", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--chunk-sizes", default="500,300,200,150,100")
    r.add_argument("--shim", action="store_true", help="use the hashed bag-of-words stand-in instead of the real model")
    rep = sub.add_parser("report")
    rep.add_argument("--results", required=True)
    rep.add_argument("--out", default=None)
    args = ap.parse_args()
    run(args) if args.cmd == "run" else report(args)


if __name__ == "__main__":
    main()
