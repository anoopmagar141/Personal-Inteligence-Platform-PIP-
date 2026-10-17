"""
Probe: how big a window does Ollama give PIP, and what happens to a prompt that is longer?

Why this exists. OllamaProvider.chat() sends only options.num_predict, never num_ctx, so every
chat turn and every Observer pass runs in whatever window Ollama picks by default. PIP budgets in
words, not tokens (stage_07_context_assembly._estimate_tokens is a word count): chat up to 6000
with 2000 reserved for the reply, the Observer a 488-word instruction block plus up to 8000 words
of transcript. stage_11_observer._cap_transcript's own docstring says an overflow is not an error
but a silently truncated prompt. scripts/eval_retrieval_levers.py pins num_ctx 8192 for exactly
that reason; the app does not. This probe measures the shipped behaviour instead of assuming it.

Three calls, all local, nothing private in them (the long prompt is generated filler):
  A  the long prompt with NO num_ctx (what PIP ships): is it cut, and which end is lost?
  B  the same prompt with num_ctx 16384: is the whole prompt read?
  C  the Observer's real instruction block with num_ctx 16384: real tokens per word for PIP text.
After A and B, /api/ps reports the window the loaded model actually got and the memory it uses.

The long prompt puts a secret word in its FIRST line and asks for it in its LAST line. A model
that answers correctly saw the top; one that cannot was handed only the end.

Run (Ollama running, qwen2.5:7b pulled, no test suite running at the same time):
    .venv\\Scripts\\python.exe docs\\eval\\context_window_2026-10-16\\probe_num_ctx.py
Writes results.json next to this file, or to PROBE_OUT if set.
"""
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, REPO)

sys.path.insert(0, os.path.join(REPO, "scripts"))
import _stamp  # noqa: E402  (BLUEPRINT S-1: every result carries the run stamp)

HOST = "http://127.0.0.1:11434"
MODEL = os.environ.get("PROBE_MODEL", "qwen2.5:7b")
BIG_CTX = 16384
SECRET = "PINEAPPLE"


def _call(path, payload=None, timeout=600):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        HOST + path, data=data, method="GET" if payload is None else "POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _filler(n_sentences):
    colours = ["red", "green", "blue", "grey", "yellow", "white", "brown"]
    animals = ["fox", "heron", "goat", "otter", "sparrow", "badger", "horse"]
    places = ["old mill", "stone bridge", "river bank", "north field", "school gate", "market"]
    lines = []
    for i in range(n_sentences):
        lines.append(
            f"Note {i + 1}: the {colours[i % 7]} {animals[(i * 3) % 7]} walked past the "
            f"{places[(i * 5) % 6]} on day {i + 1} and nobody wrote anything else about it."
        )
    return "\n".join(lines)


def long_prompt():
    head = f"Remember this for later: the secret word is {SECRET}."
    tail = "Question: what is the secret word given in the very first line? Answer with the word only."
    return head + "\n\n" + _filler(380) + "\n\n" + tail


def run_chat(label, content, num_ctx=None, num_predict=12):
    options = {"num_predict": num_predict, "temperature": 0, "seed": 1}
    if num_ctx is not None:
        options["num_ctx"] = num_ctx
    payload = {"model": MODEL, "messages": [{"role": "user", "content": content}],
               "stream": False, "options": options}
    t0 = time.monotonic()
    try:
        r = _call("/api/chat", payload)
        err = None
    except Exception as e:  # recorded, not raised: an error IS a result here
        r, err = {}, repr(e)
    wall = time.monotonic() - t0
    try:
        ps = _call("/api/ps", timeout=10).get("models", [])
    except Exception as e:
        ps = [{"error": repr(e)}]
    loaded = [m for m in ps if m.get("name", "").startswith(MODEL.split(":")[0])] or ps
    out = {
        "label": label,
        "num_ctx_sent": num_ctx,
        "words_sent": len(content.split()),
        "prompt_eval_count": r.get("prompt_eval_count"),
        "eval_count": r.get("eval_count"),
        "answer": (r.get("message") or {}).get("content"),
        "error": err,
        "wall_seconds": round(wall, 1),
        "load_seconds": round(r.get("load_duration", 0) / 1e9, 1) if r else None,
        "prompt_eval_seconds": round(r.get("prompt_eval_duration", 0) / 1e9, 2) if r else None,
        "loaded_model": [{k: m.get(k) for k in ("name", "context_length", "size", "size_vram")} for m in loaded],
    }
    print(json.dumps(out, indent=1))
    return out


def main():
    version = _call("/api/version", timeout=10).get("version")
    tags = [m.get("name") for m in _call("/api/tags", timeout=10).get("models", [])]
    print(f"Ollama {version}; models: {tags}")
    if MODEL not in tags:
        sys.exit(f"{MODEL} is not pulled; stopping (this probe downloads nothing).")

    # The options differ per call (runs[].num_ctx_sent), so the stamp says so rather than naming one.
    stamp = _stamp.run_stamp(MODEL, host=HOST, options_sent={
        "temperature": 0, "seed": 1, "num_ctx": "per call: none, 16384, 16384 (runs[].num_ctx_sent)"})

    from backend.stages import stage_11_observer
    observer_prefix = stage_11_observer._EXTRACTION_PROMPT_PREFIX

    prompt = long_prompt()
    results = {
        "stamp": stamp,
        "ollama_version": version,
        "model": MODEL,
        "run_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "long_prompt_words": len(prompt.split()),
        "runs": [
            run_chat("A_default_window_as_shipped", prompt, num_ctx=None),
            run_chat("B_num_ctx_16384", prompt, num_ctx=BIG_CTX),
            run_chat("C_observer_prompt_tokens_per_word", observer_prefix, num_ctx=BIG_CTX, num_predict=1),
        ],
    }
    c = results["runs"][2]
    if c["prompt_eval_count"]:
        results["observer_tokens_per_word"] = round(c["prompt_eval_count"] / c["words_sent"], 2)
    b = results["runs"][1]
    if b["prompt_eval_count"]:
        results["filler_tokens_per_word"] = round(b["prompt_eval_count"] / b["words_sent"], 2)
    with open(os.environ.get("PROBE_OUT") or os.path.join(HERE, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
    print("wrote results.json")


if __name__ == "__main__":
    main()
