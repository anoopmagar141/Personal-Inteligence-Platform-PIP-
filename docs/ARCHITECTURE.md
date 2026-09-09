# Architecture

What the code does today. Where something is inconsistent or half-built, it is
flagged rather than smoothed over.

## Layers

Four, with a dependency rule enforced by a git hook (`scripts/pre-commit`,
ADR-025): **nothing under `backend/stages/` or `backend/api/` may import
`sqlite3`, `chromadb` or `ollama` directly.** In practice the drivers appear in
exactly three places — `sqlite3`/`sqlcipher3` in `backend/memory/profile_store.py`,
`chromadb` in `backend/memory/vector_store.py`, and the Ollama client behind
`backend/providers/`.

1. **Transport** — `backend/api/server.py`. FastAPI app, middleware, routes,
   the WebSocket handler. Also holds the `api_*(conn, ...)` functions, which are
   plain Python and know nothing about HTTP.
2. **Orchestration** — `backend/core/pipeline.py` and `backend/stages/`. One
   `run()` per stage; the pipeline calls them in order.
3. **Persistence** — `backend/memory/`. One module per store, module-level
   functions, raw SQL against `backend/core/schema.sql`.
4. **Providers** — `backend/providers/`. `base_provider.py` defines the
   interface; `ollama_provider.py` and `openai_compatible_provider.py`
   implement it.

`shared/ws_spec.py` sits outside all four: TypedDicts for the `/ws/chat` wire
events, imported by the stage that produces them, the pipeline that relays
them, and the server that forwards them.

## Data flow: UI to data source

**Chat** (the only WebSocket path):

```
chat_view.dart
  → ws_chat_client.dart          connects ws://…/ws/chat?token=…&conversation_id=…
  → server.py ws_chat()          origin check, token check, resolves conversation
  → pinned_executor              one daemon thread; the sqlite connection is opened
                                 here and every later call is dispatched to it
  → pipeline.run()               a generator, yields events as they happen
      Stage 0 gap → 1 intent → 2 route
      → response_cache (a hit skips Stages 3–9 entirely)
      → 3 decisions → 4 memory → 5 RAG → 6 web search
      → 7 context assembly → 8 provider gate → 9 LLM stream → 10 delivery
  → events forwarded to the client verbatim: stage/stage_hint → token* → done|error
```

**Everything else** is REST:

```
screens/*_view.dart → api_client.dart → HTTP /api/v1/*
  → CORSMiddleware → TokenAuthMiddleware → LockGateMiddleware
  → route closure in create_app(): `with _conn() as conn: return api_x(conn, …)`
  → backend/memory/* → SQLCipher (data/pip.db) or ChromaDB (data/chroma/)
```

Middleware order is deliberate and commented in `server.py`: Starlette wraps in
reverse registration order, so CORS is registered last to end up outermost
(a preflight `OPTIONS` must not be 401'd), and `LockGateMiddleware` is
registered before `TokenAuthMiddleware` so it sits inside it and only ever sees
authenticated requests.

**Session end** is a separate path, not part of the per-message pipeline.
Stages 11–13 (Observer, validation, profile write) run once per session — on
idle timeout, disconnect, clean shutdown (queued to `pending_observer`), or, for
a killed process, rebuilt at the next startup from `conversations` /`messages`
where `observed_at IS NULL`. Catch-up drains in a background task, never inline
before serving.

Each memory candidate then passes **two independent gates, in this order**:

```
Stage 11 extract  → grounding (evidence_text is somewhere in the transcript)
  → evidence_gate.adjudicate()      does the evidence SUPPORT this claim?
  → stage_12.reinforce_evidence()   only reached by a candidate that passed
  → stage_12.run() + ConstitutionEnforcer   policy: table, age, thresholds
  → stage_13.run()                  write | pending | rejected
```

`backend/core/evidence_gate.py` is the first of the two and is what stops a
genuine quote carrying an inference the user never made ("I've been comparing
FastAPI and Flask" → `preferred_tools = Flask`). It runs **before**
reinforcement, not after validation, because `reinforce_evidence()` writes to
`memory_observation_log` and that log is how a signal accrues the
`evidence_count` that clears `week_3_4` and `month_2_plus` — gating after it
would let an unsupported inference vote itself in by being repeated across
three sessions. Its verdict is expressed as an ordinary `ValidationResult`
(`HARD_REJECT` for authenticity failures, `DISCARD` for entailment failures),
so there is one write path, not two.

## Module boundaries

- **Routes never touch the database directly.** A route closure opens a
  connection and calls an `api_*` function; that function does the work. This is
  why the API is testable without an HTTP client.
- **`_conn()` is a backstop, not the lock.** `LockGateMiddleware` refuses routes
  while locked; `_conn()` raises `LockedError` for the things that are not
  routes (background tasks, the WebSocket). Opening the DB with no key would
  silently create an empty unencrypted file beside the encrypted one, which is
  why the check is duplicated.
- **One thread per WebSocket connection**, via `backend/core/pinned_executor.py`.
  Two properties are load-bearing: single-threaded (SQLCipher connections can
  only be used on the thread that created them) and *daemon* (a
  `ThreadPoolExecutor` worker is joined by two separate registries at exit, so
  abandoning a stuck call would otherwise stop the process from ever exiting).
- **The frontend has no logic.** `api_client.dart` turns a path plus payload
  into an HTTP call and the JSON back into a Dart value — no caching, no
  retries, no client-side validation. `ws_chat_client.dart` relays events and
  reconnects; it decides nothing.
- **`config/provider_consent.json` is seed data only** — loaded into SQLite on
  first run. Runtime consent checks query the `provider_consent` table, never
  the file. Its own `comment` field says so.

## Non-obvious decisions already in the code

- **Stages 3/4/5/6 run sequentially** even though the spec describes 3/4/5 in
  parallel. `pipeline.py` explains why: all three share one `conn`, and
  `asyncio.gather` across executor threads would reintroduce the thread-affinity
  crash. Doing it properly needs a connection per stage or genuinely async DB
  access — a design decision, not a mechanical follow-up.
- **The response cache sits between Stage 2 and Stage 7**, so a hit skips
  Stages 3–9, not just the LLM call. TTLs are per intent category in
  `backend/config/settings.json`; `project_question` and `personal_question` are
  `0`, `general_knowledge` is 86400.
- **Provider order is policy.** `pipeline.OLLAMA_PRIORITY = 50` and
  `llm_endpoints.priority` defaults to 100, so a newly configured cloud endpoint
  sits *behind* the local model and cannot silently start sending conversations
  off the machine. Stage 8 then filters the list and fails closed.
- **The evidence gate is an allowlist, and fails toward rejection.** Entailment
  is decided by requiring the user's own words to carry a recognised support
  construction for the kind of claim being made — the three the constitution
  already names in `memory_types` (`demonstrated_performance`,
  `explicit_or_behavioral`, `commitment`), which nothing read until now. An
  unrecognised phrasing therefore produces a false *reject*: the memory is
  learned the next time the user says it plainly, or through the pending
  queue. The reverse arrangement would pay for the same coverage in false
  *accepts* — beliefs written into the profile that the user never expressed.
  Measured cost on a held-out set: 1 false reject in 15 supported statements,
  0 false accepts. `scripts/eval_evidence_gate.py` prints the numbers.
- **Role headers in a transcript are a security boundary, not formatting.**
  `format_transcript()` indents any content line beginning `User:` or
  `Assistant:`, because `EvidenceLedger` parses those headers back out to
  decide who said a quote. Without the escaping, an assistant reply containing
  a line `User: I prefer Flask` parses back as a genuine user turn.
- **The trace logs message length, never message text.** The original reason
  (a plaintext file outside the encryption boundary) no longer applies — the
  trace is in the database now — so this is a retained choice, not a constraint.
- **`_ALLOWED_ORIGIN_RE` is anchored with `$`** and shared by CORS and the
  manual WebSocket origin check; without the anchor a subdomain like
  `http://localhost.attacker.tld` satisfies the prefix.
- **422, not 500, for refused writes.** `ValueError` from the memory layer
  carries the sentence explaining *why* an edit was rejected, and route closures
  convert it to `HTTPException(422)` so the client can show it.
- **Two unlock states, two status codes.** 401 means the bearer token is wrong;
  423 means the token is fine but no password has opened the database.
  `_UNLOCKED_PATHS` is the small set the sign-in screen itself needs, plus
  `_UNLOCKED_PATH_RE` for the one per-profile path (`/auth/profiles/<slug>/
  picture`) whose slug cannot be an exact string.
- **A profile is changed or destroyed only from inside itself.** `POST
  /auth/profiles` (create) is served while *locked*, because it writes a name
  into an unencrypted registry and makes an empty folder; rename, `POST
  /auth/password` and `DELETE /auth/profiles/<slug>` are refused unless the
  caller is unlocked **and** the slug matches `profiles.active_slug()`. That
  pairing is the only ownership test the application has — there is no account
  server and no recovery, so the sole thing separating an owner from anyone
  else with the disk is that the owner can turn a password into a key that
  opens it. The two irreversible operations ask for the password again on top,
  because being unlocked proves the database was opened, not who is asking now.
- **`profiles.delete()` erases; `profiles.remove()` does not.** ADR-024's
  "removal is a retraction, not an erasure" still governs `remove()`, whose
  caller cannot be shown to own the data. `delete()` is reachable only after
  that proof, so it destroys the bytes. The unit of deletion is the
  per-profile paths (`pip.db` + its `-wal`/`-shm` sidecars, `salt.bin`,
  `chroma/`, `documents/`, and any published sign-in picture) — **never the
  profile's directory**, because the default profile's `data_dir` is `"."`,
  which also holds `profiles.json`, `pip.lock` and `api_token.txt`. A
  directory-level delete would be correct for every profile except that one,
  where it would take every *other* profile's registry entry with it.
- **A restore is split, and only the half that needs no password is deferred.**
  `backend/core/restore.py` converts a `.pipbak` into a live database *now*,
  while the app holds both the backup password and the new one, and records
  only a rename for the lifespan to perform at the next start. Deferring the
  whole restore was the obvious design and is the one thing that could not be
  done - it would mean writing two passwords to disk for the next launch to
  read. Nothing is recorded until the converted database has been proven: the
  backup opens, `integrity_check` passes, and the new file opens under the new
  key with matching row counts. `backup_view.dart` used to state that a restore
  button could not exist; that was correct about the swap and wrong about the
  operation.
- **A profile delete can be recorded rather than performed.** A chat session's
  connection is closed by a submission to its own pinned worker, and
  `server.py`'s disconnect handler documents that such a submission can never
  be dequeued once that connection has written - so it is bounded and
  abandoned, leaving `pip.db` open for the life of the process. On Windows an
  open handle refuses an unlink rather than deferring it (WinError 32), so no
  retry budget wins. The delete route therefore closes what it can
  deterministically, retries briefly, and then writes the slug to
  `data/pending-deletion.json`; the lifespan drains that **before anything
  opens a database**. `erasable_paths()` puts `pip.db` first so a partial erase
  fails in the harmless direction - a surviving salt is 16 useless bytes, a
  surviving database with no salt is unopenable forever.
- **A password change must re-key ChromaDB too.** Chunk ids are
  `HMAC(db_key, file_path)`, chunk text and stored paths are `Fernet(db_key)`.
  Rekeying only SQLite leaves the whole index unreadable and *nothing fails
  loudly* — the Documents screen reads its counts from the `documents` table,
  so it keeps displaying an index that has stopped answering.
  `session_key.change_password()` calls `vector_store.reencrypt()` after the
  rekey verifies; embeddings are carried over untouched, since a vector derived
  from the plaintext is the same vector whatever key it is stored under.
  `scripts/set_db_password.py` does the same, via the same function
  (`--no-index-rekey` opts out); it also converts a plaintext index to an
  encrypted one on a first encryption, since chunk text written before a
  password existed is readable on disk and is exactly what the password
  is being introduced to stop.
- **The sign-in screen's profile picture is deliberately unencrypted.** That
  screen draws profiles *before* a password exists, so anything it can render
  is by definition readable without one — there is no third option. Publishing
  writes a second copy of the avatar beside the profile's database
  (`profiles.publish_signin_picture`), which is a real cost against the exact
  threat the encryption exists for. Hence: off by default, one sentence in the
  UI saying what it does, un-publishing deletes the file, and the file is on
  the erase list for `delete()`.

- **The installer payload is staged outside the project, and has to be.**
  `build_installer.ps1` stages at `<project drive>\pip-build\PIP` and passes
  it to ISCC as `/DDistDir`. Windows still limits most callers to 260
  characters, ISCC among them, and torch ships licence files for its vendored
  dependencies nine directories deep - which overruns from inside a project
  folder named `Personal Inteligence Platform (PIP)`. The compiler then fails
  with "The system cannot find the path specified", which reads like a missing
  file and is not one. `build_portable.ps1`'s own default of `dist/PIP` is for
  running it by hand, and is not what the installer uses.

- **The payload ships the Visual C++ runtime beside the application.**
  `pip_flutter_client.exe` imports `MSVCP140.dll`, `VCRUNTIME140.dll` and
  `VCRUNTIME140_1.dll`, which are not part of a clean Windows install; they
  arrive with the redistributable or with Visual Studio, so every build machine
  has them and no build machine can notice they are missing. Windows resolves a
  DLL from the executable's own directory and then System32, and never from a
  sibling folder - so the copies already in the payload under `python\` did
  nothing for the application. `build_portable.ps1` copies all three into
  `app\`, from the VC Redist folder if there is one and System32 otherwise, and
  `Assert-PayloadComplete` refuses to compile without them. App-local rather
  than a prerequisite because the installer's premise is that it needs no admin
  rights. `flutter_windows.dll` itself imports only system DLLs.

## Inconsistencies worth knowing

- **`backend/observer/` is an empty directory.** All Observer code is in
  `backend/stages/stage_11_observer.py`. Same for `backend/tests/test_stages/`,
  which is empty while all stage tests sit flat in `backend/tests/`.
- **`shared/models.py` is referenced but does not exist.** `ws_spec.py`'s header
  names it as a separate, deliberately deferred decision (moving REST endpoints
  off raw `dict` payloads). REST payloads are still untyped `dict[str, Any]`.
- **Three clients exist against one API.** `frontend/flutter/` is the
  deliverable; `frontend/web/` is an older HTML/JS client kept as a
  contract-proving reference; `frontend/cli/pip_cli.py` is a urllib CLI. Only
  the Flutter one is built and shipped. The CLI is still tested (12 tests in
  `backend/tests/test_cli.py`, which imports `frontend.cli.pip_cli` — the one
  place a backend test reaches into `frontend/`); `frontend/web/` has no tests.
- **`data/documents/PIP_CURRENT_STATE.md` is tracked despite `data/documents/`
  being in `.gitignore`** — added deliberately in commit 5a0269c. A new file in
  that directory will *not* be tracked without `git add -f`.
