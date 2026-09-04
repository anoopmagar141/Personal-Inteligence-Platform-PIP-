# PIP — Current State

**Last updated:** 2026-09-02
**Status:** Working, locally-run, single-user. Backend test suite: 861/861 passing.

This is a living snapshot of what PIP actually is and does *right now*. For the
original locked architecture spec and ADRs, see `PIP_ARCHITECTURE_PRD_ADR.md`
and `PIP_MASTER_REFERENCE.md` — those are historical/foundational and are not
edited to track ongoing changes. This one is.

---

## 1. What PIP Is

PIP (Personal Intelligence Platform) is a local-first, privacy-focused
personal AI assistant. Everything — chat, memory, documents, decisions —
lives on the user's own machine. No data leaves the device without explicit,
recorded consent (enforced by a provider consent gate, not just a promise).

Core thesis contribution: a **governance layer** — a Constitution
(`constitutional.json`) and deterministic enforcer that decide what the AI is
permitted to learn and retain about the user, with auditable enforcement.
That's the part that gets graded; the app shell exists to demonstrate it
working, not as the contribution itself.

**The recurring defect class, and the design principle that answers it.**
Nearly every real bug found in this codebase has had one shape: *the code
declared an intention that no mechanism enforced.* Encryption that was
implemented, tested, and never given a key. A retraction reason that was
demanded, validated, then discarded for want of a column. A prompt instructing
"never invent" while its own opening sentence promised the model records it had
not been shown. "Produce valid JSON only" with nothing but hope behind it.
Evidence fields collected and never checked against reality. A comment naming
log leakage as a threat, sitting directly above code that logged the token.

The fix in every case was the same, and it is worth stating as a principle
rather than a changelog: **constrain the mechanism, do not restate the intent.**
A schema enum instead of asking the model to use valid table names. Grounding
against the transcript instead of instructing it not to fabricate. A key
actually passed to the connection instead of a documented capability. This is
also the substantive argument against fine-tuning as a fix for any of it — a
LoRA changes what a model *tends* to do, and none of these were tendencies.

---

## 2. Architecture

- **Backend**: FastAPI (`backend/api/server.py`), Python. REST for all CRUD
  (`/api/v1/*`); a single WebSocket (`/ws/chat`) for chat — deliberately the
  only chat transport (ADR-028).
- **Pipeline**: a 14-stage message pipeline (`backend/core/pipeline.py` +
  `backend/stages/`) — intent classification, memory/decision/RAG lookup,
  provider consent gate, context assembly, LLM streaming, response delivery,
  validation, profile write, and an async session-end Observer.
- **Storage**: SQLite via SQLCipher (`data/pip.db`) for all structured data
  (profile, decisions, conversations, provider consent). ChromaDB
  (`data/chroma/`) for RAG document embeddings — never authoritative,
  rebuildable from SQLite's `documents` registry table. Uploaded files live
  under `data/documents/` (sandboxed — ingestion rejects any path outside it).
- **Schema migrations**: `profile_store.apply_column_migrations()` adds columns
  that were introduced after databases already existed in the wild. Every
  `CREATE TABLE` in `schema.sql` is `IF NOT EXISTS`, so it shapes *new*
  databases only — an existing one silently keeps its original columns and
  fails later at query time with "no such column". Migrations run from
  `initialize_schema()`, which every connection calls, so a database repairs
  itself on the next start with nothing to remember to run. Additive nullable
  columns only; anything needing a table rebuild does not belong in a startup
  path. A column can carry a one-time backfill, applied only on the pass that
  actually adds it.
- **LLM**: local only, via Ollama. Default model `llama3.1:8b`, selectable
  from whatever's pulled locally (Providers tab). The session-end Observer is
  pinned to a verified-local provider only (never inherits whatever
  generation is using, checked against the `provider_consent` DB table, not
  the provider's own self-report).
- **Frontend**: Flutter, native Windows desktop build (`frontend/flutter/`).
  A separate plain HTML/JS client (`frontend/web/`) exists as an earlier
  contract-proving client and is not the active deliverable.
- **Governance**: `backend/core/constitutional.json` (rules) +
  `constitution_enforcer.py` (deterministic enforcement — immutable fields,
  gated fields, validation thresholds by profile age, behavioral-override
  detection). The Observer never writes directly; it only produces
  candidates that pass through this gate.

---

## 3. Running It

**Normal use (no terminal, no dev tools):**
Double-click the **PIP** shortcut on the Desktop, or run:
```powershell
.\scripts\launch_pip.ps1
```
Starts Ollama and the backend fully hidden (no console windows), then opens
the native app. The launcher's only job is starting processes; waiting belongs
to the app.

The launch screen shows what is actually happening while it waits — Ollama,
unlocking your data, starting PIP Core, the instance-lock check, backend
listening — each ticking off as it completes. Phases are appended to
`data/startup.jsonl`: by `launch_pip.ps1` for everything before uvicorn exists,
and by `backend/core/startup_progress.py` from the lock onwards. A file rather
than an endpoint because FastAPI's lifespan blocks serving until it finishes,
so nothing HTTP-shaped can report on a server that is not up yet — and the app
already polls a file on that path for the same reason (`api_token.txt`).

The launcher's phases are the ones that matter. Measured on a real cold start,
the two the *backend* writes land in the same second and it answers immediately
after, so the client reads them and succeeds at `/status` in the same poll —
the checklist never paints. What covers the wait is `backend` being written ten
seconds earlier, before Python starts importing:

```
14:03:24  backend   uvicorn launched      <- launch_pip.ps1
   ... ten seconds of imports ...
14:03:34  lock                            <- server.py
```

`backend/tests/test_startup_phase_contract.py` holds the launcher to that, for
exactly this reason: drop those writes and the screen silently reverts to the
spinner-and-a-guess it replaced, with every other test still green.

**Development (hot reload):**
```powershell
.\scripts\run_dev.ps1
```
Starts Ollama + backend (visible windows, `--reload` — Python edits apply
automatically without a manual restart) and launches Flutter in debug mode
against the native Windows target. In that Flutter terminal: `r` = hot
reload (fast, preserves app state), `R` = hot restart, `q` = quit.

Both scripts read the backend's API token from `data/api_token.txt` at
runtime (not baked into the build — a fresh install generates a new random
token on first run, which doesn't exist at compile time).

**Both scripts also set `PIP_DB_KEY`**, which is what actually turns SQLCipher
on (see §4) — launching `uvicorn` directly, without it, fails against an
encrypted database rather than silently opening a plaintext one. Where the key
comes from depends on which model this installation is on, and the shared
helper `scripts/_db_key.ps1` distinguishes three states rather than collapsing
them:

| On disk | Behaviour |
|---|---|
| `salt.bin` present | Prompts for the database password, derives the key, verifies it opens the database, and retries up to three times on a wrong one |
| `db_key.txt` present | Uses it, and warns that the key is sitting beside the database it decrypts |
| Neither | Nothing is encrypted yet; says so rather than quietly generating a random key, since that would silently recreate the weaker model |

Derivation is always delegated to Python (`scripts/derive_db_key.py`), never
reimplemented in PowerShell: PBKDF2 only reproduces if hash, iteration count,
output length and salt handling all match exactly, and a version differing in
any one would produce a different key **silently** — presenting as "wrong
password" against a database you had typed the right password for. The password
travels on stdin, never as an argument, since command lines are readable by
other processes.

**Close the app window rather than force-killing it.** A clean close runs the
Observer immediately; a kill defers it to a background catch-up on the next
launch (see §6). Nothing is lost either way, but the clean path is faster.

---

## 4. Security Posture

- **Auth**: every REST route and the WS endpoint require a bearer token
  (`data/api_token.txt`, generated on first run, `secrets.compare_digest`
  constant-time check). CORS locked to localhost origins.
- **Origin allowlist is anchored.** The regex shared by CORS and the WS
  upgrade check was unanchored and both consumers matched it as a *prefix*, so
  `http://localhost.attacker.tld` — any subdomain an attacker can register —
  passed as a trusted local origin. The bearer token still gated every request,
  so this was never an auth bypass on its own; it silently removed the
  defence-in-depth layer the code's own comments describe as protecting against
  a leaked token being usable from an arbitrary origin.
- **Encryption at rest — now actually enabled.** This entry previously
  described SQLCipher as active when it was not. `get_connection()` only keys
  SQLCipher when handed a hex `db_key`, and nothing outside the test suite ever
  generated one: neither launcher set `PIP_DB_KEY`, so every real launch took
  the unencrypted `sqlite3` fallback and wrote `data/pip.db` in plaintext, with
  ChromaDB's Fernet layer disabled by the same missing key. The machinery was
  real, tested, and entirely dead in the shipped product. Both launchers now
  generate a random 32-byte hex key once, persist it to `data/db_key.txt`
  (gitignored), and export it before starting the backend — the same
  persisted-local-secret pattern `auth.py` already used for the API token.
  ChromaDB chunk text and file paths are Fernet-encrypted from the same key,
  with an HMAC-derived lookup key for delete-by-path since Fernet is
  non-deterministic. Embeddings stay plaintext (Chroma needs real vector math
  over them; no practical way around it with this library).
- **Existing databases migrate in place**: `scripts/migrate_encrypt_db.py`
  converts a plaintext `pip.db` using `sqlcipher_export()` (ADR-027). Two
  things in the schema defeat a naive dump-and-replay: three
  `GENERATED ALWAYS AS ... STORED` confidence columns cannot be inserted into,
  and `decision_fts` is an FTS5 virtual table whose five shadow tables corrupt
  if copied as ordinary tables. Nothing is destroyed before the encrypted copy
  verifies (`integrity_check`, per-table row counts, a live FTS query), and the
  plaintext original is kept as a sidecar until explicitly removed.
- **The API token no longer reaches the logs.** Browsers cannot set headers on
  a WebSocket handshake, so `/ws/chat` takes the token as a query parameter —
  and uvicorn's access logger wrote the full request path, putting the live
  token in plaintext in `data/backend.err.log` on every connection. The risk is
  not a local attacker (who can already read `api_token.txt`) but that **logs
  travel**: they get pasted into bug reports, forums and submissions in a way a
  file named `api_token.txt` never is. `RedactTokenFilter` rewrites
  `token=...` to `token=[REDACTED]`, applied to `record.args` as well as
  `record.msg` because uvicorn logs with lazy `%`-formatting and the path
  arrives as an argument.
- **Single-instance lock**: `backend/core/instance_lock.py`, a PID file at
  `data/pip.lock`. A second backend start fails loudly naming the PID
  already running, instead of racing on the same DB. Stale locks (a crashed
  process) are detected and taken over automatically.
- **Provider consent gate**: fail-closed — an unknown provider is a hard
  stop, not a silent pass. Web search is gated the same way generation
  providers are (this was a real, since-fixed gap: web search used to fire
  on keyword match alone, with no consent check at all).
- **Path sandboxing**: document ingestion resolves and rejects anything
  outside `data/documents/` (`Path.resolve()` closes off `..` traversal and
  symlink tricks).

**Known limitations, disclosed rather than implied away — and this section is
deliberately blunt, because an earlier draft of it overstated the protection.**

The random-key model encrypts, but puts `db_key.txt` in `data/` — the same
directory as the `pip.db` it decrypts. **Anything that captures `data/`
captures both**: a stolen disk, a disk image, a backup or cloud-sync tool
pointed at that folder. Those are precisely the threats Part 10.4 claims, so
that model did not meet them, and saying otherwise would be security theatre.

**Part 10.1's password-derived key is now implemented** — see
`backend/core/db_key.py`, PBKDF2-HMAC-SHA512 at 256,000 iterations to a 32-byte
key, both parameters marked `EMPIRICALLY VERIFIED` in the spec and now pinned
by a test. Only the salt lands on disk, and salts are not secret. An attacker
with the disk gets ciphertext and a salt, and still needs a password that
exists only in the user's head.

> **STATUS ON THIS INSTALLATION: the migration HAS been run.**
> `data/salt.bin` is present (16 bytes, written 2026-08-31) and
> `data/db_key.txt` no longer exists, which is the state
> `scripts/set_db_password.py` leaves behind on success — it removes the key
> file only after the rekey is proven. `data/pip.db` does not begin with
> `SQLite format 3`, so it is genuinely encrypted. The two `.pipbak` files dated
> minutes earlier are what a careful person makes before running it.
>
> This paragraph said the opposite until 2026-09-02, and had done since the
> migration was run. It matters more than a stale line usually would, because
> everything downstream of it reasons about which model is active: the
> paragraph told a reader they were on the weak model while the data directory
> said otherwise, and the whole point of Part 10.1's "implemented is not the
> same as active" is that this file is where that question gets answered. The
> lesson is the one the encryption drift already taught once — **check the data
> directory, do not trust the prose about it.**
>
> To re-run or verify:
> ```
> .venv\Scripts\python.exe scripts\set_db_password.py --check
> ```
> **There is no recovery.** A forgotten password means the profile, decision log
> and conversation history are permanently unreadable — Part 10.1 states this as
> a feature, not an oversight. Write it down somewhere that is not this machine
> before running it.
>
> Keeping this distinction sharp rather than rounding it to "done" matters,
> because collapsing it is exactly what produced the original encryption bug:
> SQLCipher was implemented, tested, and marked verified while every real launch
> ran unencrypted, because nothing supplied the key. **Implemented is not the
> same as in the path**, and a capability gated behind a manual step has not
> taken effect until someone takes that step.

Remaining limitations, before and after that migration:

- **After it**, nothing on disk decrypts the database — but the key still
  reaches the backend through an environment variable, and process environments
  are readable by other processes running as the same user. Part 10.1's "held in
  process memory only" is **not fully achieved**. What is achieved is the part
  the threat model turns on: disk access alone yields ciphertext and a salt.
- **Migrating in place cannot scrub the plaintext previously on disk.**
  Unlinking a file does not erase its blocks, and this database existed as
  plaintext from 19–26 Aug. Full-disk encryption (BitLocker) addresses prior
  exposure; neither of these changes does.
- `chmod 600` is applied best-effort to the key and salt, which means little
  against Windows ACLs.
- **`launch_pip.ps1` stops being silent** once a password is set. Its premise
  was "double-click an icon, no console" — and a prompt is a console. A key that
  never touches disk cannot be obtained without asking, and the spec chose that
  trade explicitly ("User types password at app launch").

---

## 5. Governance / Memory Correctness

- **Constitution**: immutable fields (name, language, timezone — hard
  reject), gated fields (require confirmation), per-field-age validation
  thresholds, a memory-source trust hierarchy (user correction > explicit
  stated > repeated behavior > single inference).
- **Behavioral override**: was completely dead code until fixed — the trigger
  depended on `preference_memory.behavioral_signal_count` (never incremented
  anywhere) and `preference_contradiction_log` (never appended to outside test
  fixtures). Both dead inputs meant the mechanism could never fire from real
  usage, no matter how many times a user's behavior contradicted a stated
  preference. Fixed: Stage 13 now logs a contradiction on the DISCARD path; the
  enforcer derives count/date from that log instead of the dead scalar column.
  Proven end-to-end with a test that fires the trigger from real writes, not
  hand-seeded state.
- **Observer confabulation guards**: the session-end Observer's LLM
  extraction pass was found — live, more than once — inventing entire
  fictional decisions and session summaries when a session had little real
  content. Fixed with deterministic grounding, not better prompting alone
  (prompting alone was already tried and didn't hold):
  - A decision candidate is dropped unless its own `raw_quote` actually
    appears in the real transcript (the model has to cite real evidence, not
    just claim it).
  - A decision candidate phrased as a question, or that's a verbatim echo of
    the assistant's own prior reply, is dropped (catches the assistant's own
    rhetorical filler getting logged as if the user said it).
  - `session_snapshot` is withheld entirely (keeping the last real one, not
    blanking it) when a session had no user turn beyond a few trivial words.
  - **Memory candidates are grounded too.** Decisions had two checks; memory
    candidates had none, so an invented preference reached Stage 12 on nothing
    but the model's say-so, and the `evidence_text` a reviewer sees when
    approving a profile write was never verified to exist. Found once
    constrained output made the extraction legible: the model returned the
    prompt's own field description — *"the exact quote or paraphrase this was
    drawn from"* — as the evidence for a real preference. `evidence_text` is
    now required to be a verbatim quote and checked against the transcript.
    Grounding subsumes the placeholder rather than special-casing it: a
    placeholder string is not in the transcript either. Live, this immediately
    caught a `docker_level` candidate with empty evidence from a conversation
    that never mentions Docker, and two candidates quoting a sentence assembled
    by splicing two separate user turns together — plausible-reading, never
    said.
- **Observer output is schema-constrained, not parsed hopefully.** The only
  previous defence was the prompt asking for "valid JSON only", a regex that
  stripped markdown fences after the fact, and `_empty_output()` on a parse
  failure — which discarded *the entire session's work*, every candidate and
  the snapshot, silently, with the transcript already consumed and no retry
  possible. `BaseLLMProvider.chat()` now takes an optional `response_format`
  and Ollama constrains sampling to a JSON Schema, so malformed output is
  impossible at the sampler rather than discouraged in the prompt. Support is
  detected with `inspect.signature` rather than by catching `TypeError`:
  `chat()` is a generator function, so a `TypeError` raised inside its body
  during iteration is indistinguishable from a rejected keyword, and retrying
  on that would hide a real bug behind a plausible fallback. The schema
  guarantees shape, never truthfulness — the grounding checks above remain the
  defence there.
- **`target_table` is constrained to tables that actually work.**
  `APPROVED_MEMORY_FIELDS` listed `observer_writable`, which is a *category
  name* from the constitution grouping three tables, not a table. The model
  emitted it and every such candidate was `HARD_REJECT`ed — two rejections and
  four "Unhandled target_table" warnings per session, guaranteed. Removed
  rather than corrected: naming the three tables properly would move the
  failure later and make it worse, since Stage 12 has no handler and
  `write_approved_candidate` raises "Unsupported target_table", turning a clean
  rejection into an exception path. Enabling them needs a validation handler, a
  write branch, and — the actual blocker — a *reader*: nothing selects from
  `topic_interests` or `document_access_patterns` anywhere, so writing to them
  would produce data no prompt sees and no profile view shows. Tool preferences
  are unaffected; `preference_memory.preferred_tools` is observer-writable and
  read by `get_profile()` and Stage 4.
- **Decision log integrity**:
  - **Retractions record why.** `update_decision_state()` required a `reason`
    for `superseded`/`abandoned`, validated it non-empty, then discarded it —
    `decision_log` had no column for one. Under ADR-022 nothing is ever
    deleted, so these rows get read months later by someone who must tell "a
    fabrication we cleaned up" from "real, and we changed our mind"; from
    `state` alone the two are identical. `state_reason` now stores it, for
    every state including `active` (re-activating is itself worth explaining,
    and a stale retraction reason on a re-activated row reads as a live
    justification for the opposite of what happened).
  - **Duplicates are suppressed on write.** The log held two decisions twice
    each: the Observer proposed the same decision in consecutive sessions and
    nothing compared it against what was already recorded, so Stage 3 then
    retrieved each twice and spent context budget saying the same thing twice.
    Matching is on case- and whitespace-normalised text, scoped to *active*
    decisions (re-adopting something previously abandoned is a genuine new
    decision, and folding it back into the retracted original would erase that)
    and to the *same project* (one sentence under two projects describes two
    different commitments). The check sits in `insert_decision()`, which every
    write path reaches, so a path added later cannot bypass it by forgetting.

---

## 6. Session Lifecycle and Crash Recovery

The Observer runs at session end, and "session end" has three distinct shapes.
Two were handled; the third silently lost work.

| How a session ends | What happens |
|---|---|
| Idle timeout (10 min) or normal disconnect | Observer runs immediately — there is time, nothing else waits on that connection |
| Clean server shutdown | Transcript persisted to `pending_observer`; a ~130s pass per open connection cannot block exit (ADR-033) |
| **Killed outright** — `Stop-Process -Force`, crash, power loss | **Previously: nothing.** Both paths above live in code that never executes, and `conversation_history` exists only in the WS handler's memory |

Hit live: a session was killed mid-test and the conversation sat in the sidebar
looking entirely normal while nothing in it had been learned from. **Silent
non-learning is the worst shape this failure can take in a system built to
remember** — a crash that loses data at least announces itself.

Recovery works because messages are committed per turn, so a transcript can be
rebuilt from the database rather than from the memory that died.
`conversations.observed_at` records whether the Observer has been over a
conversation; NULL with messages present means it never has. Those are rebuilt
at startup and handed to `pending_observer` — deliberately the same queue the
shutdown path already fills, since it already retries, retains failures, and
has tested draining.

**Catch-up runs in the background, not inline before serving traffic.** This is
the substantive part. Draining inline was defensible only while
`pending_observer` was filled by clean shutdowns alone — rare, nearly always
empty, so the drain was a no-op. Recovery breaks that assumption: any killed
session lands in the same queue, and draining one is a ~130s LLM pass. Inline,
that is an app that hangs for over two minutes on launch.

That was measured, not predicted. The WS test suite began intermittently
hanging the moment recovery was added; a git-stash comparison gave a clean
baseline against roughly 1-in-5 hangs with the change, and the logs showed why —
a second TestClient within one test found the first's conversation and drained
it against a real Ollama. Part 7's "drain before Stage 0" ordering only ever
existed so a recovered session is not missed on the *next* turn, which a
minutes-long pass cannot deliver for a user who starts typing immediately;
**ADR-003's "zero response-speed impact" is the stronger constraint and points
the other way.**

Shutdown cancels catch-up rather than waiting for it. Nothing is lost:
`drain()` marks a row `processing` before running it and `_list_for_drain()`
picks `processing` rows back up, so an interrupted entry is retried on the next
start instead of being silently consumed.

**Existing databases are backfilled as observed** when the column is added, or
the first start after the upgrade would treat every conversation ever held as
unprocessed and queue an LLM pass for each.

---

## 7. Live-Chat Grounding (separate from the Observer)

A second, distinct class of bug: the **live chat response** itself fabricating
content. This had two independent causes, and fixing only the first was not
enough — which is the most instructive finding in this document.

**Cause 1 — retrieval.** Stage 1's intent classifier misrouted questions away
from `project_question`, the only category that fetched `active_projects`. Hit
three times with three different phrasings, each producing a *different* fully
fictional project narrative. Fixed: any literal mention of "project" or
"program" routes to `project_question`; `personal_question` also fetches
`active_projects`. Separately, `who am I?` and `tell me about myself` matched no
personal pattern at all and fell through to `general_knowledge`, which never
fetches identity — the questions most purely about identity were answered from
nothing.

Compounded by a cache-TTL trap: `general_knowledge` caches for 24 hours,
`project_question` never does. A misclassified fabricated answer didn't just
happen once — it got frozen and replayed verbatim for a day.

**Cause 2 — the stored memory was itself fiction.** The database contained a
session snapshot naming a "Project Genesis" that never existed, six decisions
about smart-home threat detection unrelated to anything the user works on, and
pending candidates citing a "Smith Project" and a "Johnson Report". All of it
harvested by the pre-fix Observer from the model's own invented replies. Those
fixes plugged the intake, but could not retract what was already written, so
Stage 7 kept assembling the fiction into every prompt and the model kept
reporting it — correctly, given its context.
`scripts/cleanup_fabricated_memory.py` retracts it: decisions to
`state='abandoned'` per ADR-022 rather than deleted, matched on text as well as
id so it declines to act if the database has moved on.

**Cause 3 — the prompt itself.** Cleaning the data was *still* not sufficient:
the model invented three projects from a context containing exactly one. The
instructions opened by telling it that it had "access to the user's project
history" before showing any, so it supplied the history it had been told it
had; the prohibition covered only "decisions or preferences", never projects;
and the profile rendered as `active_projects.PIP: a personalised system` — a
database row, not a statement about a person, with nothing marking the list
complete. Stage 7 now renders the profile under real headings marked as
complete lists, states "none recorded" for looked-up tables that are empty (an
absent heading reads as "not retrieved", which invites filling the gap), and
binds its rules explicitly to claims *about the user*.

That last scoping needed its own correction, found by live testing: binding the
rules to the whole reply made *"what is a hash table?"* return "I don't have
that recorded." **Refusing from an empty profile is the same defect as
inventing from one** — both substitute the profile for the model's own
knowledge. Rule 5 now puts general knowledge explicitly out of scope, and rule
6 stops the model reading the context's own scaffolding aloud.

**Verified live, end to end:**

| Question | Before | After |
|---|---|---|
| list the projects I have | three invented projects | *PIP — a personalised system* |
| what projects am I working on? | "Project X/Y/Z" with fabricated progress | *"You have one project recorded in your file: PIP"* |
| what goals do I have? | — | *"I do not have that recorded."* |
| who am I? | — | *"You are BatMan."* |
| what is a hash table? | — | a full, correct explanation |

**Revised residual limitation.** This document previously stated that retrieval
fixes "do not guarantee the model never embellishes beyond what it's given —
that's a standing behavior characteristic of running a small (8B) local model."
That claim was too pessimistic and is retracted. The embellishment was not an
irreducible property of the model; it was caused by a prompt that promised
records it had not supplied and formatted the profile as an unlabelled data
dump. Once the context asserted completeness and the rules bound to user-claims,
the 8B model followed them. The real residual limitation is narrower and
different: **grounding verifies that a quote was said, not that it supports the
claim drawn from it.** Live, a `python_level` candidate cited "I've been
comparing FastAPI and Flask" — a genuine sentence that says nothing about
Python skill — and passed. Stage 12's tiered thresholds are the gate for that,
and their quality has not been separately examined.

---

## 8. Feature Status

| Feature | Status |
|---|---|
| WS chat with streaming, stop-generation | Done |
| Conversation history (multi-chat sidebar, like Claude/ChatGPT) | Done |
| Model selection (any locally-pulled Ollama model) | Done |
| Download any Ollama model from inside PIP, with progress and VRAM warnings | Done — curated list plus free text, so the list guides without limiting; warns and never refuses |
| Document upload + RAG retrieval | Done |
| Decision log (manual + Observer-derived, OR-logic confidence scoring) | Done |
| Profile / preferences / skills / goals | Done |
| Projects (active project tracking) | Done |
| Provider consent management UI | Done |
| Pipeline trace viewer (why PIP answered as it did) | Done |
| Profile correction / retraction from the UI | Done |
| Decision retract / supersede / reactivate, with reason | Done |
| Project archive / complete | Done |
| Dark mode (follows OS, overridable, remembered) | Done |
| Interaction-style history (the profile's only audit trail) | Done |
| Retrieval preview - what RAG would return, with scores | Done |
| Per-provider consent scope (least privilege, no default) | Done |
| Correct a skill or goal, not just forget it | Done |
| Markdown rendering in chat (no new dependency) | Done |
| Launch screen showing real startup phases | Done |
| Native Windows desktop app + one-click launcher | Done |
| Encryption at rest (SQLCipher + ChromaDB), with in-place migration | Done |
| Backup export / restore — `/export`, `/restore [file]` (ADR-027) | Done |
| Backup screen in the app — export button, backup list, restore instructions | Done — the button launches a console; ADR-027 keeps the export off the API |
| Multiple profiles, each a separately encrypted database | Done — `scripts/new_profile.py`; the launcher asks which, and each has its own password. Switching needs a restart, which is the honest cost of the separation being cryptographic rather than a filter |
| Desktop shortcuts (`scripts/install_shortcuts.ps1`) | Done — PIP, and "Restore PIP from backup", which cannot be a button in a running app |
| Cross-machine continuity: install PIP elsewhere, `/restore`, everything present | Done — round trip proven end to end, including a write left in the `-wal` and the ingested documents themselves |
| Document content stored in the DB (`document_blobs`) | Done — closes the one place ADR-026’s “no plaintext” did not hold, and makes a `.pipbak` self-sufficient |
| Plaintext JSON dump — `/export --readable` | Done — no default path, refuses to write into `data/`, warns and waits for `yes` |
| Password-derived key (Part 10.1) | Done — **migration has been run on this installation** (`salt.bin` present, `db_key.txt` gone) |
| Export requires authentication | Done — `/export` demands the live password and proves it against the database; an inherited `PIP_DB_KEY` does not satisfy it |
| Crash/force-kill recovery of unobserved sessions | Done |
| Voice input | Not built |
| Notifications/reminders | Not built |
| Distribution packaging (PyInstaller, installer, Ollama-detection UX) | Not built — deliberately out of scope unless this needs to run on a machine you don't control |

---

## 9. Testing

Backend: **861 tests**, `pytest backend/tests/`. Frontend: **151 tests**,
`flutter analyze` / `flutter test` clean, and `flutter build windows` succeeds.

`test_phase9_roundtrip.py` is worth naming for the same reason the palette test
is. Every other backup test checks one leg of the journey against a live
database that is still sitting there working, which is not the situation any of
this exists for. That file writes a decision, leaves it in the `-wal` where a
file-copy backup would miss it, exports, **destroys the database**, restores,
and asks whether the uncheckpointed write came back. It also proves the row was
genuinely WAL-resident first — by copying the `.db` file alone and finding it
absent — because without that control, "the row came back" would pass just as
happily on a row that had been checkpointed all along.

One of its cases removes `PRAGMA wal_checkpoint(TRUNCATE)` from the export
entirely and demands the row anyway. That is what keeps Part 10.2's claim
honest: the checkpoint is defence in depth, and `sqlcipher_export()` reading
through the page layer is what actually carries recent writes. Swap the export
for a file copy and the checkpoint silently becomes load-bearing again; this is
the test that would notice.

Frontend coverage used to be the Review screen only. It now covers every screen
that writes: Trace, Profile, Decisions, Projects, plus the palette. The last of
those is worth naming because it tests something a reading of the code cannot
settle — `test/theme_test.dart` computes WCAG contrast ratios for every colour
pairing in both palettes and fails below 4.5:1 for body text, 3:1 for
metadata. It caught two real defects in the *existing* light palette on its
first run: `textFaint` at 2.49:1 (used for the timestamps and source labels
that carry provenance) and `danger` on `dangerSoft` at 4.23:1 (used for
refusal messages). Both were darkened rather than the threshold being
lowered.

Pre-commit hook enforces ADR-025 (no direct `sqlite3`/`chromadb`/`ollama`
imports outside `backend/memory`/`backend/providers`).

`test_ws_chat_connection_closes_db_on_disconnect_with_no_activity` has been
documented as flaky under system load (a Starlette TestClient +
ThreadPoolExecutor teardown timing interaction). That note stands, but with an
important caveat: **the same test failing is not automatically that known
flake.** When it began failing during the crash-recovery work, a git-stash
comparison showed a clean baseline against roughly 1-in-5 failures with the
change — a genuine regression that a two-minute startup hang was hiding behind
a familiar-looking symptom. Attributing it to the known flakiness would have
shipped that hang. **Measure the baseline before believing a flake.**

That rule paid out a second time, on a different test. Before merging the
frontend branch, `test_resuming_marks_the_carried_history_as_already_observed`
failed intermittently — passing alone, failing inside its file. It is not the
documented flake, so it was measured rather than assumed:

| commit | failures |
|---|---|
| baseline, before the executor change | 0 / 21 runs |
| with the executor change | ~3 / 12 runs |

Two things came out of it. The first is procedural: **the branch was being
committed to while the measurement ran**, and a commit that rewrote
`test_ws_chat.py` landed mid-experiment, briefly making the numbers say the
opposite. Pinning both sides in detached worktrees is what settled it — measure
against fixed SHAs, not a branch name, when anyone else is working.

The second is the actual cause, and it was not the executor. The suite was
writing to the developer's **real data directory**: `data/startup.jsonl` held
120 lock/ready pairs, one for every app lifespan the suite had ever started.
Shared mutable state across tests is exactly what produces order-dependent
failures, and fixing the isolation (`test_data_dir_isolation.py`) took the
failure rate to 0 in 14 subsequent runs.

That hole was found only because the launch-screen work added a file the tests
started writing to. Four other overrides had the same shape, and one of them
was dangerous: **`PIP_SALT_PATH` was unisolated**. `db_key.create_salt()`
overwrites the salt, the salt is half the key derivation, and Part 10.1 states
there is no recovery by design — so one unisolated test calling it would leave
the real database permanently unopenable *with the correct password*. A new
feature's test exposed a latent way for the suite to destroy the user's data.

One more lesson, from writing the phase-contract tests: **a guard nobody has
watched fail is not a guard.** Those tests were checked by mutating each file
the way a careless refactor would. Four of five regressions were caught; the
fifth — the most important, the launcher dropping its `backend` phase — was
not, because the phase is written on two branches and set membership could not
see one of them disappear. It counts per branch now. The same mistake had
already appeared once this session in a Flutter test that asserted an error
message was on screen without checking that anything else still was — it was
passing against a completely blank page.

---

## 10. Recent Commit History (most recent first)

```
111061b Merge branch 'flutter-frontend-gaps'
b871ad0 Add this session's evidence once, however many passes it makes
2c10e7f Merge branch 'flutter-frontend-gaps'
8ff7caa Ignore the scratch database the schema tests leave behind
209f72e Stop the suite writing to the developer's own data directory
69c991c Count what the user said, not what the Observer re-read
9fa36c5 Ignore the scratch database the schema tests leave behind
b88f559 Let an abandoned database call actually be abandoned
46e1faa Give the wrong snapshot a way out, and cover the helper that removes it
a77f818 Stop a failed recall overwriting the session it failed to recall
977a25a Hold the launcher to the phases the launch screen needs
1fe308a Stop the launch phases repeating themselves
e8e35c3 Tell the launch screen what is actually happening
413d0b7 Stop a failed action taking the screen down with it
1a72ecb Render the Markdown the model was already sending
ecbf358 Reach the last three endpoints nothing was calling
7fc76fa Send a correction to the table that owns the field
436ce70 Teach the Observer to see a project, not just a skill used on it
7f3569d Let one bad candidate cost one candidate, not the session
3251f70 Stop an unscored field from killing the whole Observer pass
8046ab0 Give the Flutter client the write half it never had
72a0d20 Report a refused write instead of a bare 500
d17cfc9 Make the backup password prompts tell the truth
607cae7 Name the wrong interpreter instead of blaming a missing package
```

---

## 11. On Fine-Tuning (LoRA), and Why It Was Not Used

Raised as a candidate fix for the fabrication problem, and rejected on
evidence rather than principle — worth recording, because it is a question an
examiner may ask.

It could not have fixed the fabrication. The model was handed a system message
literally containing `Last session topic: Project Genesis` and asked to list
projects; reporting it was the *obedient* answer given that context. Training
would have meant teaching a model to distrust its own retrieval layer — the
layer whose entire job is to be the source of truth — and doing so
probabilistically where the bug was deterministic.

Worse, the only available training corpus was the contaminated conversation
history. Training on it would have baked the hallucinations into weights, where
they are no longer one `DELETE` away.

It also cuts against this project's own ADRs, which consistently push model
judgment *out* of the trust path: the Observer never self-scores confidence
(ADR-005), proactive triggers are deterministic and "model judgment of
relevance/urgency is forbidden" (ADR-014), the scored decision graph was
rejected for traceability (ADR-015). "It answers correctly because the
enumeration path reads the table and structurally cannot do otherwise" is
demonstrable; "because we fine-tuned it to prefer the profile section" is not.

**One use remains genuinely open**, and is a different argument: running the
Observer on a *smaller* model. That is a capability question, not a trust
question — the grounding checks run afterward regardless of which model
produced the candidates, so the trust path stays deterministic. The model is
swappable *precisely because it is not trusted*. Two caveats before pursuing
it: the VRAM claim points the wrong way (8B alone is ~4.9GB; 8B generation plus
a 3.8B Observer is ~7.1GB on an 8GB card, i.e. tighter, so the win is speed —
58s vs 131s measured — not memory), and `format: json` now does much of what
the LoRA would, since the small model no longer has to *learn* the output
shape. **Measure stock `phi3:mini` with the schema against `llama3.1:8b` first**
— counting how many candidates survive `_quote_is_grounded` is now an objective
metric. If it's close, "constrained decoding closed the capability gap" is a
better finding than "we fine-tuned it."

---

## 12. Open Questions / Things to Decide

- **Distribution scope**: is PIP ever demoed on hardware you don't control,
  or always your own machine? Decides whether PyInstaller packaging, an
  installer, and Ollama-detection UX are worth building at all.
- **Cache TTL design**: `general_knowledge`'s 24h TTL is fine for genuinely
  timeless answers, but it can trap a misclassified, fabricated answer for a
  full day. Worth deciding whether the cache should have a stronger safety
  valve (e.g. never cache a category that reached Stage 9 without any real
  profile/RAG/decision context) rather than relying entirely on classification
  being right.
- **Whack-a-mole classification**: Stage 1 is keyword/regex by design (B4,
  30ms budget) — a deliberate architectural choice, but new phrasings can still
  slip through untested. No systemic fix planned beyond "report it, widen the
  pattern."
- **Stage 12 threshold quality — unexamined.** Grounding proves a quote was
  said; the tiered evidence thresholds are the only thing standing between a
  real quote and an unsupported inference drawn from it. Whether they actually
  hold has not been tested.
- **Test isolation is fixed but not proven exhaustive.** Five environment
  overrides were being applied per-test in whichever file happened to notice.
  `test_data_dir_isolation.py` now guards them centrally, but the way they were
  found was a new feature happening to write to one of them — not an audit. If
  a sixth exists, the same accident is how it will surface.
- **Decision state history**: only the latest `state_reason` is kept. A full
  audit trail of every state change would need its own table.
- **Semantic duplicate decisions**: dedup catches textually identical entries.
  "We chose FastAPI" and "We'll go with FastAPI" remain two rows. Semantic
  dedup would need embeddings — and would move a correctness decision into a
  similarity threshold, which is the same trade this project consistently
  declines.
- ~~**Three stale doc references**~~ — fixed. All three pointers to
  `docs/PIP_MASTER_REFERENCE.md` are gone: the two Flutter comments now state
  the fact they were deferring to, and `test_provider_consent.py:28` says why
  its scope list is a literal (importing `VALID_CONSENT_SCOPES` would make the
  test agree with itself).
- ~~**Provider consent scope is still the broadest one**~~ — fixed. Granting
  now asks which of the three meaningful scopes applies, with nothing
  preselected: a default here would be the client making the least-privilege
  decision that `stage_8_before_network_call` exists to leave to the user.
  Building it surfaced a second defect — the Grant button lived in a
  `DataTable` cell and was **visible but not clickable**, so that screen's
  only action had been inert. The list is cards now, like every other list in
  the app.
- ~~**Markdown is still not rendered in chat**~~ — done, without taking a
  dependency. `flutter_markdown` is discontinued and its replacements are
  third-party, which is a poor trade for a privacy-first local app that
  already says "no new package" in its own design system. `lib/markdown.dart`
  covers the subset an 8B model actually emits; anything outside it renders as
  the text it already was. The hard part was streaming, not formatting: the
  parser runs on half-written Markdown many times per reply, so an unclosed
  marker stays literal and an unterminated fence renders as the code so far —
  otherwise the tail of every reply would visibly disappear and come back.
  User messages are deliberately *not* parsed: what they typed is theirs, and
  re-rendering it would silently eat the asterisks out of a filename.
