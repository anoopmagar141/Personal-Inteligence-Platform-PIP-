# Architecture

What the code does today. Where something is inconsistent or half-built, it is
flagged rather than smoothed over.

## Layers

Four, with a dependency rule enforced by a git hook (`scripts/pre-commit`,
ADR-025): **nothing under `backend/stages/` or `backend/api/` may import
`sqlite3`, `chromadb` or `ollama` directly.** The hook guards only those two
directories. In practice, inside `backend/`, `sqlite3`/`sqlcipher3` are imported
in `backend/memory/profile_store.py` and, lazily, in `backend/core/restore.py`
(which opens a `.pipbak` itself); `chromadb` only in
`backend/memory/vector_store.py`. Several `scripts/` also import `sqlcipher3`
directly. Nothing imports the `ollama` package even though `requirements.txt`
lists it: `backend/providers/ollama_provider.py` speaks Ollama's HTTP API
through `urllib`.

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

## Launch paths

- `scripts/launch_pip.ps1` is the normal user launcher. It starts Ollama and
  the backend hidden, then opens the built Windows app.
- `scripts/run_dev.ps1` is the developer launcher. It opens visible Ollama and
  backend terminals, runs Uvicorn with `--reload`, and starts Flutter in debug
  mode for hot reload.
- Both launchers start the backend locked. They do not select a profile or
  request a password in PowerShell. The Flutter sign-in screen selects an
  initial registered profile, offers switching, and requests that profile's
  password. Additionally, the normal launcher performs a pre-flight stale lock
  cleanup so the backend does not silently crash in its hidden window.
  `data/pip.lock` holds `<pid> <creation time>`, and stale means
  `instance_lock.holder()` finds no live process with both - a bare PID is
  reused, and a reused one used to block PIP from starting. The launcher asks
  that function through Python rather than repeating the rule in PowerShell,
  whose local-time `StartTime` can misjudge a live lock across a DST change.

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
before serving. Every sign-in gets its own: one still running from a previous
session queues the next behind it rather than standing in for it. A queued
transcript names its chat (`pending_observer.conversation_id`); deleting a chat
removes its queued transcripts and clears the "where we left off" note
(`session_snapshot`, one row per profile), and the session-end pass does not run
for a chat that no longer exists.

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

**Trace timing:** `backend/core/trace.py` writes pipeline stage outcomes and
elapsed `duration_ms` values to the encrypted `trace_log` table. Durations are
rounded wall-clock milliseconds; a quick stage may therefore show `0`. The
column is nullable so older rows and trace writers outside the message
pipeline can remain unmeasured. Startup migrations add it to existing tables,
and the legacy composite-key rebuild preserves it and the rows already there.

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
  `0`, `general_knowledge` is 86400. The key also carries
  `profile_store.record_version()`, a counter that database triggers bump on
  any write to a table the context can draw from (`RECORD_TABLES`), so an
  answer cached before a document, decision or profile change is never
  served after it - the TTL and decision-log rules alone are only checked
  when an answer is stored. And it carries the signed-in session's
  generation (`response_cache.generation()`), which every sign-out moves:
  each chat connection reads and writes under the one it took when it opened,
  so nothing a session stores or asks for crosses into a later one
  (FREEZE_LIST §7.20). The selected model name is also part of the key, so a
  cached answer from the previous model is not reused after a model switch
  (FREEZE_LIST §7.38).
- **Provider order is policy, but order is not consent.** `pipeline.OLLAMA_PRIORITY = 50`
  and `llm_endpoints.priority` defaults to 100, so an enabled cloud endpoint
  normally follows local Ollama. If Ollama is unreachable and another endpoint
  exists, the pipeline skips Ollama and may automatically use the first enabled
  endpoint in priority order. Stage 8 allows that endpoint only when its saved
  consent permits `full_inference`; otherwise it blocks the endpoint and tries
  another gated provider. This fallback can send prompts and assembled context
  off the machine under consent granted earlier. Ollama is kept in the chain
  when it is the only configured provider, even if unreachable, so the failure
  remains visible. Stage 8 counts a provider as local - needing no consent -
  only when both the provider's own report and its consent record say so, the
  rule Stage 11 already applies to the Observer; a disagreement is a refusal.
  An endpoint cannot be saved under the id of a built-in provider (`ollama`,
  `web_search`), since consent is recorded per id (FREEZE_LIST §7.21).
  The built-in Ollama is local for a model that runs here: an Ollama `*-cloud`
  model is refused at pull and at selection, and the provider reports itself
  not local for one already stored, so Stage 8 and the Observer's own check
  refuse it too (FREEZE_LIST §7.48).
- **One settings block for the local model** (`settings.json` `llm`, BLUEPRINT
  W-1): the default model is `qwen2.5:7b`, the model every measured number is
  on (`pipeline.DEFAULT_MODEL_NAME` and `OllamaProvider`'s default both read
  it); every Ollama request, chat and Observer alike, asks for the same
  `num_ctx` window, 16384 tokens (a different window would reload the model;
  observed fully on the GPU, FREEZE_LIST §7.56); the temperature is 0.0, chosen
  by a measurement whose rule was fixed first (§7.56). PIP budgets in words; `tokens_per_word` (2.0) is
  a safe ratio above every one measured on this tokenizer (1.41 prose, 1.86 the
  Observer's instructions), and the Observer's transcript cap is derived from
  it so instructions, transcript and reply fit the window. Before this, Ollama
  used its own default window, 4096 tokens on an 8 GB GPU, and cut a longer
  prompt from the front - the Observer's instructions first (FREEZE_LIST
  §7.55). The chat (Stage 9) and Observer trace lines record the prompt tokens
  Ollama read, the window, and whether PIP's estimate said it would not fit.
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
- **A chat turn always ends on the socket, and a chat that cannot be saved
  is not answered into.** `stream_pipeline_to_websocket` guards the
  pipeline's next event and ends a turn that failed with one generic
  `error`, the connection kept (FREEZE_LIST §7.23, §7.25, §7.44); a Stop
  with nothing streaming is dropped. The writes around a turn go through
  `_run_write`, which rolls a failed write back on the connection's own
  thread. What has to be written before a message is answered - the
  messages of an earlier turn the database had not taken, the session
  count, the conversation row - refuses the message with one `error` if it
  fails. A turn's own messages are queued and written after it, and a
  queue that cannot be written refuses the next message (§7.45).
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
  423 means the token is fine but no password has opened the database. That
  includes a backend that has just started with profiles registered and none
  chosen (the base slot is empty) and a profile that has been created and
  chosen but has no password yet: `state()` says "setup" for both, and with a
  registry `_is_locked()` counts it as locked, in the gate, at the chat socket
  and in `_conn()`, so no request creates a database that has no password
  (FREEZE_LIST §7.47, §7.49). The first-run import is on `_UNLOCKED_PATHS`
  with the sign-in routes: it opens no live database and refuses for itself.
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
- **New installations have no implicit account.** The profile list is empty
  until the person creates one. `Default` is retained only for an older
  installation whose database still lives directly in `data/`; it is never an
  empty selectable placeholder beside a newly created profile.
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
  operation. The swap, here and in `scripts/restore_backup.py`, moves the
  replaced database's `-wal`, `-shm` and `-journal` aside with it, named after
  the kept copy (`profiles.SQLITE_SIDECAR_SUFFIXES`, the list `delete()` also
  erases by). SQLite pairs those files with a database by name alone, so a
  crash's WAL left beside the restored file was replayed onto it
  (FREEZE_LIST §7.17).
- **A backup is accepted only if something outside its own contents says it
  is a whole export.** Both restores used to check a `.pipbak` against itself,
  and SQLCipher opens a zero-length file as an empty database under any key, so
  an empty or part-written file passed and replaced a real profile.
  `backend/core/backup_mark.py` is the one rule for both restores and the
  export: before copying anything the export writes a one-row `pip_backup_mark`
  table into the backup saying `writing`, and only after `verify()` flips it to
  `complete` with the table counts. A backup with no mark predates marks and is
  accepted if it holds PIP's `identity` table; one marked `writing`, or whose
  counts disagree with its mark, is refused with a sentence. The mark describes
  the file, not the profile, so both restores drop it from the database they
  build and leave it out of the counts they compare. The chosen file is opened
  read-only (`backup_mark.open_read_only`), so a leftover rollback journal beside
  it is refused rather than played back into the person's own backup.
- **Closing the window does not stop the backend, so anything that says "close
  PIP" has to.** `launch_pip.ps1` starts uvicorn hidden; the Flutter app has no
  exit hook and the backend no shutdown route. `scripts/_backend.ps1` finds PIP's
  backend by the owner of the port *and* a command line naming
  `backend.api.server` (a bare port number is somebody else's program until
  proved otherwise) and stops it. `launch_pip.ps1` uses it only when
  `pending-restore.json` exists, so a staged restore is installed by a new
  backend's lifespan instead of waiting for a reboot; `restore_pip.ps1` offers it
  before a restore, because `restore_backup.py` refuses while the backend holds
  the lock (FREEZE_LIST D-09). The stop is a hard one by design - nothing can ask
  for a graceful one - and what it costs is already recovered at the next start.
- **The first-run import is the one restore that is done at once.**
  `POST /backup/import` (welcome screen) is allowed only while no profile has a
  database and nobody is signed in: there is nothing to replace, and nothing holds a
  database open, so the swap that the in-app restore defers to the next start is done
  immediately. `restore.preflight()` makes every check staging makes *before* a profile
  is registered (both call `_open_checked_backup`, so they cannot disagree), which is
  what lets a refusal leave the installation empty. The profile is named from the
  backup's `identity` row, or "Imported profile"; its folder name comes from
  `profiles.slugify`, which gives a name in another script `profile-` plus eight hex
  digits of a hash (a name with no letter or digit at all takes `imported-profile`), so
  no backup is refused for its owner's name. Imports run one at a time: activating a
  profile points the whole process at it, so a second one gets a 409. A swap whose process died between
  its last two renames is finished by the next start (`drain_pending_restore` recognises
  "temporary database gone, temporary salt present, a database in place, no salt in
  place"); `restore_backup.py` removes its temporary copy however it ends.
- **Secrets are compared as bytes.** `hmac.compare_digest` and `secrets.compare_digest`
  raise `TypeError` for a `str` with any non-ASCII character, so a password or bearer
  token in an accented language, Devanagari, Chinese or with an emoji used to kill the
  export prompt, the shortcut restore's prompt and the token check (a request with a
  non-ASCII token was a server error, not a 401). All three encode to UTF-8 first
  (FREEZE_LIST §7.29); a new comparison of user-typed text must do the same.
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
  surviving database with no salt is unopenable forever. Before any of that,
  `delete()` cancels a restore staged for the profile
  (`restore.cancel_pending_restore_for`): left staged, it was installed into
  the deleted profile's place at the next start (FREEZE_LIST §7.22).
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
- **Sign-out takes the session's in-process state with it.** One backend
  process serves every profile, so the key is not the only thing a session
  leaves behind. `session_key.lock()` - the path every sign-out, delete and
  switch goes through - also empties the response cache, whose key names no
  profile and would otherwise answer the next profile with the last one's
  replies, and moves its generation: emptying covers what was stored before
  the sign-out, the generation what a session still answering at sign-out
  stores after it, or a chat socket left open through it asks. Work already
  running when the key goes keeps its database
  connection, so `vector_store` refuses to read or write the index when the
  active profile has a salt but no key is held (`IndexLockedError`) instead of
  falling back to plaintext. And the next sign-in's catch-up is queued behind
  any still running rather than skipped. All three were measured through the
  real routes (FREEZE_LIST §7.8) and are pinned by
  `backend/tests/test_profile_boundary.py`.
- **A profile's documents live in its own folder, read at call time.**
  `vector_store.documents_root()` is `profile_store.documents_root()`, which
  follows `PIP_DOCUMENTS_ROOT` as `profiles.activate()` sets it; uploads are
  written there and ingest accepts nothing outside it. It used to be a
  `DOCUMENTS_ROOT` constant fixed at import to `data/documents`, so every
  profile shared one upload folder and any profile could ingest another's
  files. Documents an older version recorded under that shared folder are
  copied into the profile's own and re-indexed by the sign-in catch-up
  (`vector_store.adopt_shared_documents`) - copied, not moved, since another
  profile may name the same file, so those originals stay where they were.
  Deleting a document removes its file there and its bytes in `document_blobs`
  as well as its chunks; only a file inside that folder is ever removed, and
  one that cannot be removed stops the delete (FREEZE_LIST §7.50).
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
  place a backend test reaches into `frontend/`); `frontend/web/` has no test
  harness, only `test_web_client_consent.py`, which reads what the server
  serves and pins that the client does not grant consent (FREEZE_LIST §7.51).
- **`ollama` is a declared dependency that nothing imports** (see Layers).
