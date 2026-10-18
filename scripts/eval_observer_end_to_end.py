"""
Measure the whole learning path on labelled conversations, with the real
local model. Run from the repo root, with Ollama running:

    python scripts/eval_observer_end_to_end.py [--model qwen2.5:7b] [--out report.md]

scripts/eval_evidence_gate.py scores the evidence gate alone, on candidates
written by hand. That leaves the question an examiner will actually ask
unanswered: when a person talks to PIP, what does it come away believing?
Here the model does the extracting, and grounding, the evidence gate, the
Constitution and Stage 13 decide what is kept - the same run_session_end()
the app calls when a session ends. Cases: backend/tests/observer_cases.py.

Every case runs on a fresh profile in a temporary directory, onboarded the
same way (so every case is a profile in its first two weeks, where the
Constitution only accepts candidates the model labels explicit). Every
PIP_* path is pointed there before anything from backend/ is imported - the
same table conftest.py isolates - so a run cannot touch real data.

What is learned is read from the database, not from the pipeline's return
value: new or changed rows in the profile tables, new questions in the
pending queue, and new decision-log entries (the Observer's decisions reach
prompts too, through a different gate - FREEZE_LIST section 7.13).

    precision  learned rows that match a fact the user stated, over learned
               rows that match either a stated fact or a trap. UNLABELLED
               rows are listed for a person to judge and reported apart,
               never folded in silently.
    recall     stated facts learned (written, or queued for the user's
               confirmation), over stated facts.
    traps      traps that reached a belief table, over traps.

The model samples, so one run is one draw. --repeat runs every case N times
and reports the spread.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

# Fail with the interpreter you used, not a wrong install instruction.
import _venv

_venv.require("sqlcipher3")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_ISOLATED = tempfile.mkdtemp(prefix="pip-observer-eval-")
for variable, name in {
    "PIP_LOCK_PATH": "pip.lock", "PIP_DB_PATH": "pip.db", "PIP_TOKEN_PATH": "api_token.txt",
    "PIP_SALT_PATH": "salt.bin", "PIP_STARTUP_PROGRESS_PATH": "startup.jsonl",
    "PIP_DOCUMENTS_ROOT": "documents", "PIP_CHROMA_PATH": "chroma", "PIP_DATA_DIR": ".",
}.items():
    os.environ[variable] = str(Path(_ISOLATED) / name)
os.environ.pop("PIP_DB_KEY", None)

from backend.memory import profile_store  # noqa: E402
from backend.memory.profile_store import get_connection, initialize_schema  # noqa: E402
from backend.providers.ollama_provider import OllamaProvider  # noqa: E402
from backend.stages import stage_11_observer as observer  # noqa: E402
from backend.tests.observer_cases import CASES  # noqa: E402

LEARNED_TABLES = (
    "identity", "skill_memory", "preference_memory", "goal_memory", "interaction_style",
    "active_projects", "topic_interests", "preferred_tools", "document_access_patterns",
    "decision_log",
)


import hashlib
import _stamp
from backend.config.settings import get_settings
from backend.stages.stage_11_observer import _EXTRACTION_PROMPT_PREFIX, _EXTRACTION_SCHEMA


def _observer_fields() -> dict:
    """What this harness adds to the shared run stamp: the Observer's own inputs."""
    text = _EXTRACTION_PROMPT_PREFIX + json.dumps(_EXTRACTION_SCHEMA, sort_keys=True)
    return {
        "transcript_token_cap": get_settings()["observer"]["max_session_tokens"],
        "prompt_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "wall_clock_seconds": [],
        "validity_condition": "Valid for gate-only comparisons; any change to the Observer prompt, the extraction schema, the model or grounding voids it.",
    }


def get_stamp(model: str) -> dict:
    """
    The stamp of a live run (BLUEPRINT S-1): the shared one from _stamp, which
    refuses a model whose digest or Ollama version it cannot read, plus the
    Observer's own fields. The app's OllamaProvider, which this harness uses,
    sends neither a temperature nor num_ctx, so both are recorded as not sent.
    """
    stamp = _stamp.run_stamp(model, options_sent={"temperature": None, "num_ctx": None})
    stamp.update(_observer_fields())
    return stamp


def replay_stamp(recorded) -> dict:
    """A replay calls no model; it says which recording it replayed instead."""
    stamp = _stamp.run_stamp(None)
    stamp.update(_observer_fields())
    stamp["replayed_from"] = recorded
    return stamp

_OLLAMA_COUNTS = ("prompt_eval_count", "eval_count", "done_reason", "load_duration",
                  "prompt_eval_duration", "eval_duration", "total_duration")


class _CountingResponse:
    """
    Ollama's streamed response, passed through line for line, keeping the counts
    from its final line (V-2 part a). prompt_eval_count is how many prompt
    tokens the model actually read: when a prompt is longer than the window,
    Ollama cuts it silently and this is the only place the cut shows.
    """

    def __init__(self, response, sink: dict):
        self._response = response
        self._sink = sink

    def __enter__(self):
        self._response.__enter__()
        return self

    def __exit__(self, *exc):
        return self._response.__exit__(*exc)

    def __iter__(self):
        for line in self._response:
            if line:
                try:
                    chunk = json.loads(line.decode("utf-8"))
                except ValueError:
                    chunk = {}
                if chunk.get("done"):
                    self._sink.update({k: chunk.get(k) for k in _OLLAMA_COUNTS})
            yield line


class RecordingProvider(OllamaProvider):
    """
    The real Ollama provider, keeping the raw extraction for the funnel, and
    Ollama's own counts for the call. The request itself is the app's, unchanged:
    the counts are read by wrapping the response, not by building a second
    payload that could drift from OllamaProvider.chat's.
    """

    def __init__(self, model_name, replay_text=None):
        super().__init__(model_name=model_name)
        self.raw = replay_text or ""
        self._is_replay = replay_text is not None
        self.counts: dict = {}
        self.messages: list = []

    def chat(self, messages, *args, **kwargs):
        if self._is_replay:
            yield self.raw
            return
        self.messages = messages
        module = sys.modules[OllamaProvider.__module__]
        real_urlopen = module.urllib.request.urlopen
        module.urllib.request.urlopen = lambda req, *a, **k: _CountingResponse(real_urlopen(req, *a, **k), self.counts)
        parts = []
        try:
            for token in super().chat(messages, *args, **kwargs):
                parts.append(token)
                yield token
        finally:
            module.urllib.request.urlopen = real_urlopen
        self.raw = "".join(parts)


def _ollama_post(host: str, path: str, payload: dict, timeout: int = 600) -> dict:
    import urllib.request
    request = urllib.request.Request(host + path, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def unload_model(host: str, model: str) -> None:
    """
    Unloads the model so the next case starts with an empty cache. Ollama reuses
    the cached start of a previous prompt and then counts only the new tokens,
    which would make prompt_eval_count look like a cut when nothing was cut.
    Costs one model load per case, reported apart (load_duration). The reply
    is read and not parsed: nothing in it is needed.
    """
    import urllib.request
    request = urllib.request.Request(host + "/api/generate",
                                     data=json.dumps({"model": model, "keep_alive": 0}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=120) as response:
        response.read()


def count_prompt_tokens(host: str, model: str, messages: list, num_ctx: int) -> int | None:
    """
    How many tokens the WHOLE prompt is: the same messages, in a window big
    enough to hold them, one output token, and the model unloaded afterwards so
    the next count starts from an empty cache. Compared with the
    prompt_eval_count the shipped call reported, it shows how much was cut.
    """
    reply = _ollama_post(host, "/api/chat", {
        "model": model, "messages": messages, "stream": False, "keep_alive": 0,
        "options": {"num_ctx": num_ctx, "num_predict": 1, "temperature": 0},
    })
    return reply.get("prompt_eval_count")


def _rows(conn) -> dict[str, set[tuple]]:
    rows = {t: {tuple(r) for r in conn.execute(f"SELECT * FROM {t}")} for t in LEARNED_TABLES}
    rows["pending"] = {
        tuple(r) for r in conn.execute(
            "SELECT id, target_table, field_name, proposed_value FROM memory_candidates_pending WHERE state = 'pending'"
        )
    }
    return rows


def _learned(before, after) -> list[dict]:
    """New or changed rows, as (kind, table, text) - pending rows keep the
    table they are waiting to be written to."""
    items = []
    for table in LEARNED_TABLES:
        for row in after[table] - before[table]:
            items.append({"kind": "written", "table": table,
                          "text": " ".join(str(v) for v in row if v is not None).lower()})
    for row in after["pending"] - before["pending"]:
        _, target, field, value = row
        items.append({"kind": "queued", "table": target, "text": f"{field} {value}".lower()})
    return items


def _matches(spec, item) -> bool:
    return item["table"] in spec["tables"] and any(k in f" {item['text']} " for k in spec["keywords"])


def _set_profile_age(conn, days: int) -> None:
    """
    Makes the profile `days` old as the Constitution reads it
    (stage_12_validation_layer._get_profile_age_weeks: first_session_date).
    Every case used to run on a profile in its first two weeks, where one
    explicit statement is enough; from week 3 two are needed, after week 4 three.
    """
    import datetime
    first = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    conn.execute("UPDATE profile_meta SET first_session_date = ? WHERE id = 1",
                 (first.strftime("%Y-%m-%dT%H:%M:%SZ"),))
    conn.commit()


def _spec_tags(spec) -> dict:
    """Where a planted statement sits and what it is, carried into the results (long-chat cases)."""
    return {k: spec[k] for k in ("position", "kind", "id") if k in spec}


def run_case(case, model, replay_text=None) -> dict:
    db = Path(tempfile.mkdtemp(dir=_ISOLATED)) / "pip.db"
    conn = get_connection(str(db), None)
    try:
        initialize_schema(conn)
        profile_store.complete_onboarding(conn, name="Asha Rai", language_preference="English",
                                          timezone="Asia/Kathmandu")
        if case.get("profile_age_days"):
            _set_profile_age(conn, case["profile_age_days"])
        before = _rows(conn)
        provider = RecordingProvider(model, replay_text=replay_text)
        started = time.monotonic()
        error = None
        try:
            outcome = observer.run_session_end(conn, case["transcript"], provider)
        except Exception as e:  # recorded, not raised: one failure must not end the run
            outcome, error = {"memory_results": [], "decision_results": []}, f"{type(e).__name__}: {e}"
        seconds = time.monotonic() - started
        after = _rows(conn)
    finally:
        conn.close()

    try:
        raw_count = len(json.loads(provider.raw).get("memory_candidates", []))
    except Exception:
        raw_count = None

    learned = _learned(before, after)
    for item in learned:
        true = any(_matches(s, item) for s in case["learn"])
        trap = any(_matches(s, item) for s in case["avoid"])
        item["label"] = "TRUE" if true else "TRAP" if trap else "UNLABELLED"

    facts = [{"keywords": s["keywords"], "learned": [i["kind"] for i in learned if _matches(s, i)], **_spec_tags(s)}
             for s in case["learn"]]
    traps = [{"keywords": s["keywords"], "hit": any(_matches(s, i) for i in learned), **_spec_tags(s)}
             for s in case["avoid"]]
    prompt_words = sum(len(m.get("content", "").split()) for m in provider.messages)

    return {
        "id": case["id"], "category": case["category"], "seconds": round(seconds, 1), "error": error, "raw_text": provider.raw,
        "raw_candidates": raw_count,
        "funnel": [(r["candidate"].get("target_table"), r["candidate"].get("field_name"),
                    r["candidate"].get("proposed_value"), r["evidence_state"], r["validation_status"],
                    r["outcome"]) for r in outcome["memory_results"]],
        "decisions": [d.get("status") for d in outcome["decision_results"]],
        "learned": learned, "facts": facts, "traps": traps,
        "ollama": dict(provider.counts), "prompt_words": prompt_words or None,
        "_messages": provider.messages,
    }


def summarise(results) -> dict:
    items = [i for r in results for i in r["learned"]]
    labels = Counter(i["label"] for i in items)
    facts = [f for r in results for f in r["facts"]]
    traps = [t for r in results for t in r["traps"]]
    judged = labels["TRUE"] + labels["TRAP"]
    return {
        "cases": len(results),
        "errors": sum(1 for r in results if r["error"]),
        "learned_rows": len(items),
        "labels": dict(labels),
        "precision": labels["TRUE"] / judged if judged else None,
        "facts": len(facts),
        "facts_learned": sum(1 for f in facts if f["learned"]),
        "facts_written": sum(1 for f in facts if "written" in f["learned"]),
        "facts_queued_only": sum(1 for f in facts if f["learned"] and "written" not in f["learned"]),
        "traps": len(traps),
        "traps_hit": sum(1 for t in traps if t["hit"]),
        "funnel_evidence": dict(Counter(f[3] for r in results for f in r["funnel"])),
        "funnel_validation": dict(Counter(f[4] for r in results for f in r["funnel"])),
        "funnel_outcome": dict(Counter(f[5] for r in results for f in r["funnel"])),
        "raw_candidates": sum(r["raw_candidates"] or 0 for r in results),
        "grounded_candidates": sum(len(r["funnel"]) for r in results),
        "seconds": round(sum(r["seconds"] for r in results), 1),
    }


def _pct(n, d):
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else f"{n}/{d}"


def report(model, runs) -> str:
    lines = [f"# End-to-end Observer measurement - model `{model}`", ""]
    
    def print_run(index, results, title):
        s = summarise(results)
        res_lines = [
            f"## {title}", "",
            f"- cases: {s['cases']} ({s['errors']} errored), total model time {s['seconds']}s",
            f"- funnel: {s['raw_candidates']} candidates extracted by the model, {s['grounded_candidates']} survived grounding",
            f"  - evidence gate: {s['funnel_evidence']}",
            f"  - Constitution: {s['funnel_validation']}",
            f"  - Stage 13: {s['funnel_outcome']}",
            f"- learned rows: {s['learned_rows']}, labelled {s['labels']}",
            f"- **precision** (TRUE / TRUE+TRAP): {_pct(s['labels'].get('TRUE', 0), s['labels'].get('TRUE', 0) + s['labels'].get('TRAP', 0))}",
            f"- **recall** (stated facts learned): {_pct(s['facts_learned'], s['facts'])} - written {s['facts_written']}, only queued for confirmation {s['facts_queued_only']}",
            f"- **traps reaching a belief table**: {_pct(s['traps_hit'], s['traps'])}",
            "",
            "| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |",
            "|---|---|---|---|---|---|"
        ]
        for r in results:
            learned = "; ".join(f"{i['kind']} {i['table']}: {i['text'][:60]} ({i['label']})" for i in r['learned']) or "-"
            facts = f"{sum(1 for f in r['facts'] if f['learned'])}/{len(r['facts'])}" if r['facts'] else "-"
            traps = f"{sum(1 for t in r['traps'] if t['hit'])}/{len(r['traps'])}" if r['traps'] else "-"
            funnel = "; ".join(f"{f[0]}.{f[1]}={str(f[2])[:25]} {f[3]}/{f[4]}/{f[5]}" for f in r['funnel']) or "-"
            if r['error']:
                funnel = f"ERROR {r['error'][:80]}"
            res_lines.append(f"| {r['id']} | {r['category']} | {learned} | {facts} | {traps} | {funnel} |")
        res_lines.append("")
        return res_lines

    for index, results in enumerate(runs, 1):
        lines += print_run(index, results, f"Run {index}")
        
    if len(runs) > 1:
        pooled = [r for run in runs for r in run]
        lines += print_run("Pooled", pooled, "Pooled")
        
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--only", nargs="*", help="case ids to run")
    parser.add_argument("--out", help="write the markdown report here as well")
    parser.add_argument("--json", help="write the raw results here")
    parser.add_argument("--save-raw", help="save raw model outputs to this file")
    parser.add_argument("--replay", help="replay raw model outputs from this file")
    # V-2 part (a): the long chats, and what Ollama read of them.
    parser.add_argument("--cases", help="a JSON list of cases to use instead of backend/tests/observer_cases.py")
    parser.add_argument("--unload-between", action="store_true",
                        help="unload the model before each live case, so prompt_eval_count is not shortened by "
                             "Ollama's cache of the previous prompt")
    parser.add_argument("--count-prompt-tokens", type=int, metavar="NUM_CTX",
                        help="after the runs, count each distinct prompt's full length in a window this big")
    args = parser.parse_args(argv)

    if args.cases:
        try:
            all_cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            parser.error(f"invalid cases file: {exc}")
    else:
        all_cases = CASES
    cases = [c for c in all_cases if not args.only or c["id"] in args.only]
    runs = []
    
    replay_data = None
    if args.replay:
        try:
            with open(args.replay, "r", encoding="utf-8") as f:
                replay_data = json.load(f)
            replay_runs = replay_data["runs"]
            if not isinstance(replay_runs, list) or not replay_runs:
                raise ValueError("runs must be a non-empty list")
            expected = {case["id"] for case in cases}
            for run_index, run in enumerate(replay_runs, 1):
                if not isinstance(run, list):
                    raise ValueError(f"run {run_index} must be a list")
                mapped = {}
                for item in run:
                    if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                        raise ValueError(f"run {run_index} contains an invalid case entry")
                    case_id = item["id"]
                    if case_id in mapped:
                        raise ValueError(f"run {run_index} repeats case {case_id!r}")
                    if not isinstance(item.get("raw"), str):
                        raise ValueError(f"run {run_index} is missing raw text for {case_id!r}")
                    mapped[case_id] = item["raw"]
                if set(mapped) != expected:
                    missing = sorted(expected - set(mapped))
                    extra = sorted(set(mapped) - expected)
                    raise ValueError(f"run {run_index} case ids do not match; missing={missing}, extra={extra}")
                replay_runs[run_index - 1] = mapped
            args.repeat = len(replay_runs)
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            parser.error(f"invalid replay file: {exc}")
        
    # Every run is stamped at its start, before any number exists; this used to
    # happen only with --save-raw, so a report or --json result said nothing
    # about which weights, Ollama or commit produced it (BLUEPRINT S-1).
    if replay_data is not None:
        stamp = replay_stamp(replay_data.get("stamp"))
    else:
        try:
            stamp = get_stamp(args.model)
        except ValueError as exc:
            parser.error(str(exc))

    for index in range(args.repeat):
        results = []
        wall_clock = 0.0
        
        replay_run = replay_data["runs"][index] if replay_data else None
            
        for case in cases:
            replay_text = replay_run[case["id"]] if replay_run is not None else None
            if args.unload_between and replay_text is None:
                unload_model(OllamaProvider().host, args.model)

            result = run_case(case, args.model, replay_text)
            results.append(result)
            wall_clock += result["seconds"]
            print(f"[run {index + 1}] {case['id']:<32} {result['seconds']:>6}s  "
                  f"{'ERROR' if result['error'] else len(result['learned'])} learned", flush=True)
                  
        runs.append(results)
        stamp["wall_clock_seconds"].append(round(wall_clock, 1))

    if args.save_raw:
        raw_runs = []
        for index in range(args.repeat):
            raw_run = []
            for result in runs[index]:
                raw_run.append({"id": result["id"], "raw": result["raw_text"]})
            raw_runs.append(raw_run)
            
        out_data = {
            "stamp": stamp,
            "runs": raw_runs
        }
        with open(args.save_raw, "w", encoding="utf-8") as f:
            json.dump(out_data, f, indent=1)

    # One count per distinct prompt (the same transcript at three profile ages
    # is one prompt), after every run, so switching the window - which reloads
    # the model - never happens between the measured calls.
    full_prompt_tokens = {}
    if args.count_prompt_tokens and replay_data is None:
        by_prompt = {}
        for results in runs:
            for result in results:
                if result["_messages"]:
                    key = hashlib.sha256(json.dumps(result["_messages"], sort_keys=True).encode("utf-8")).hexdigest()
                    by_prompt.setdefault(key, (result["_messages"], []))[1].append(result["id"])
        for key, (messages, ids) in by_prompt.items():
            tokens = count_prompt_tokens(OllamaProvider().host, args.model, messages, args.count_prompt_tokens)
            for case_id in ids:
                full_prompt_tokens[case_id] = tokens
            print(f"full prompt {key[:10]}: {tokens} tokens ({len(ids)} case runs)", flush=True)
        stamp["count_prompt_tokens_num_ctx"] = args.count_prompt_tokens
    for results in runs:
        for result in results:
            result.pop("_messages", None)
            if result["id"] in full_prompt_tokens:
                result["full_prompt_tokens"] = full_prompt_tokens[result["id"]]

    text = _stamp.markdown(stamp) + "\n" + report(args.model, runs)
    print("\n" + text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    if args.json:
        Path(args.json).write_text(json.dumps({"stamp": stamp, "runs": runs}, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
