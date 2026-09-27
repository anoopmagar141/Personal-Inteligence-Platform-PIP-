# PIP — Reliability Plan and Governance Freeze

**Canonical document.** Update in place; do not create a second summary.
Location in the repo: `docs/FREEZE_LIST.md`.

**Status: evidence-first freeze.** Five discovery/test tasks sent; All five
tracks returned (§7.2–§7.6); cross-track synthesis done (§7.7); end-to-end
profile boundary test run (§7.8). No fix authorized yet. No production code has been changed under
this freeze.

Contents: 1 Principle · 2 Development strategy · 3 Classification ·
4 The seven promises · 5 Evidence · 6 Rejected methods · 7 Evidence tracks ·
8 Status · 9 Conversation record · 10 Background · 11 Freeze rule

---

## 1. Governing principle

> **Constrain the mechanism; do not merely restate the intent.**

PIP's costly bugs were not the ones that failed loudly. They failed
silently: encryption implemented but never given a key, a recovery path
never invoked, evidence collected but never checked, an Observer that
stopped learning with no error. The aim is not "errorless" development,
which is unachievable. The aim is that errors are caught **early, cheaply,
and by a mechanism** rather than by someone remembering to look.

---

## 2. Development strategy (standing method)

This applies to every change, during and after the freeze.

### 2.1 Decide before building
1. **Write the promise first** — one sentence saying what the change
   guarantees.
2. **Name the enforcing mechanism.** If none can be named, the promise is
   a hope and does not get written into any claim.
3. **Name what "broken" looks like from outside** — a DB row, a request
   count, a file on disk. If a failure would be invisible, make it visible
   before building anything else.

### 2.2 Build in this order
1. **Test first, run it against current code.** It may already pass;
   that saves a fix.
2. **Assert on outcomes, not return values** — DB state, network calls,
   files. Not "the function returned REJECT".
3. **Break it once by hand.** Weaken the guard, confirm the test fails,
   restore the guard. A test never seen failing proves nothing.
4. **Make the smallest change that passes.** No cleanup riding along.
5. **One commit per promise,** test in the same commit, one `docs/LOG.md`
   entry.

### 2.3 Standing rules
- **Fail closed.** Unknown provider, missing key, Ollama down → refuse
  and queue. Never fall back to something less safe.
- **One source of truth per rule.** A policy in both JSON and code means
  one of them is lying.
- **Tests never touch real data.** Every `PIP_*` path isolated in
  `backend/tests/conftest.py`. The unisolated `PIP_SALT_PATH` could have
  made the real database permanently unopenable.
- **Measure a flake before believing it.** Compare against a pinned
  baseline SHA. A "known flaky" symptom has already hidden one real
  regression (the two-minute startup hang).
- **Claims match mechanisms.** If the code cannot prove it, the docs do
  not say it.

### 2.4 Process
- **Freeze features while promises are unverified.**
- **Cap planning at two revisions.** If a spec needs a third, run a small
  version and let the result correct it (see §9, lesson 1).
- **Recommending ≠ implementing.** A discovery report may recommend a
  fix; a separate, explicit decision authorizes it.
- **Reports are read against their own stop condition** before any
  comparison with other reports.

### 2.5 Known limit of this strategy
It protects promises that have been written down. It does not catch bugs
in behavior nobody thought to promise. The only defense there is real
daily use: when something surprises you, turn it into a new promise with a
test.

### 2.6 Where these rules must live to be enforced
- `AGENTS.md` is at its **80-line cap**. Its "Current focus" section now
  points here (done 2026-09-26; still 80 lines, stale packaging text
  removed).
- `docs/LOG.md` is held at **25 entries**; the thirteen oldest are rolled into
  nine Archive summary lines (done 2026-09-26).

---

## 3. Four-way classification

Every returned report resolves into exactly one category. "Gap" on the
original list meant **unverified**, not "bug requiring code".

| # | Category | Meaning | Typical response |
|---|----------|---------|------------------|
| A | Disconnected mechanism | Mechanism exists; the real path does not use it | Reconnect; add regression test |
| B | Missing state | The state needed to verify the guarantee is not stored | Add minimum state; test writer and reader |
| C | Already enforced | Mechanism already does what was promised | No code change; keep the test |
| D | Claim too strong | Code is fine; the written promise overstates it | Correct the wording; state the limitation |

---

## 4. The seven promises

### Promise 1 — Observer writes only through governance
**Claim:** Observer candidates reach memory only via grounding → evidence
gate → Stage 12 → Stage 13.
**Must prove:** reachability — no production path from Observer output to
storage that skips governance. A static import guard is a guard, not a
proof. A valid candidate must still be written; rejecting everything
proves the wrong property.

### Promise 2 — Observer cannot write immutable fields
**Claim:** name, language, timezone change only by the user directly.
**Must prove:** a grounded, gate-passing candidate for these fields cannot
reach a DB write — tested on DB state, not on the enforcer's return value.

### Promise 3 — Gated fields require confirmation
**Claim:** a gated field is not persisted without prior user confirmation.
**Must prove:** the write is unreachable without confirmation, on real DB
state. A JSON rule naming the field is not evidence.

### Promise 4 — Stored memory is supported by the user's words
**Limitation:** grounding proves a quote was said, not that it supports
the claim. Live case: a `python_level` candidate grounded in "I've been
comparing FastAPI and Flask".
**Current honest wording:**
> PIP verifies that Observer evidence was actually said and applies
> evidence-gate and Stage 12 threshold checks. Whether a genuine quote
> actually supports the claim drawn from it has not been separately
> measured.

### Promise 5 — Observer runs only on authorized local providers
**Wording (decided):**
> The Observer runs only against providers recorded as local in
> `provider_consent.is_local`. PIP does not independently verify the
> machine boundary; `is_local` is attested, never inferred from hostname.

**Reason:** a loopback address is not proof of locality (tunnels, remote
`OLLAMA_HOST`). Claiming proof would overclaim.
**Decided behavior:** Ollama down and no local provider → the Observer does
not run and the transcript is queued. Never a cloud fallback. Catch-up
happens at the next launch; no mid-session retry is promised.
**Pinned test (Track 1):**
1. Counting stub on `127.0.0.1`, registered with `is_local = false`.
2. Ollama unavailable; trigger the real Observer path with a non-trivial
   user turn.
3. Assert stub requests = 0 and the session is pending-Observer.
4. Flip only `is_local` to `true`; Ollama stays unavailable.
5. Drive the real startup/lifespan catch-up with isolated data (not a
   direct drain call, not `launch_pip.ps1`).
6. Assert only `conversations.observed_at IS NOT NULL` and the session has
   left the pending queue. Do not assert `memory_observation_log`.
7. Manual break-it: weaken the gate, confirm stub count > 0 and the test
   fails, restore.

**As run (Track 1, §7.2):** step 2 uses the idle-timeout trigger, not
disconnect: under TestClient the disconnect path never reached the
Observer, and a first draft passed with the gate removed. Step 4 sets both
locality records (see §7.2 finding 2). Step 6 was too weak as written and
was strengthened: recovery stamps `observed_at` *before* the Observer runs,
and a `failed` row has also left the pending queue, so the test asserts the
queue row is `completed` and the stub received the extraction call.

### Promise 6 — Nothing leaves the machine without recorded consent
**Claim:** fail-closed, per-provider consent covering generation and web
search; nothing preselected.
**Scope:** test the enforcement boundary; no redesign. **Not** one of the
five current tracks — do not open a sixth investigation from it.

### Promise 7 — Encryption at rest
**Rejected wording:** "Disk access alone yields only ciphertext."
**Corrected wording:**
> The database, document text, and file paths are encrypted at rest under
> a password-derived key. Embeddings are not encrypted. Plaintext written
> before encryption was enabled is not scrubbed. [While running, the key
> reaches the backend through the process environment — **final clause
> depends on Track 2**.]

Track 2 has returned (§7.3), and the final clause cannot stay as drafted.
The key does not *reach* the backend through the environment: the backend
derives it and then *exports* it there, and every child process inherits
it. Chunks can also be written in plaintext after sign-out. The corrected
clause needs an owner decision; a candidate is in §7.3.

---

## 5. Evidence hierarchy

- **Strong:** deterministic test on the real path asserting DB state;
  observed provider calls; import-closure/reachability check; a break-it
  result showing a weakened guard is caught.
- **Medium:** code-path inspection with `file:line`; schema inspection;
  call-site census.
- **Weak (never sufficient alone):** comments, doc claims, function names,
  "implemented" labels, a JSON rule with no traced consumer, a test that
  only asserts config length or content.

> **A guard nobody has watched fail is not a guard.**

---

## 6. Rejected methods (and why)

| Rejected | Reason |
|----------|--------|
| Fixing before the evidence returns | A "gap" may be category C or D; code changes would be wasted or harmful |
| One universal fix ("remove `PIP_DB_KEY` everywhere") | Main DB and `vector_store` are separate consumers with possibly different answers |
| A test that relies on real OS PID recycling | Not controllable; first find what identity the lock stores |
| Merging 4a (routing) with 4b (cache) | Different failure modes; the fabrication incident had three independent causes |
| Trusting a test that uses an injected config | Fixtures and import caches can hide a mutation |
| Upgrading a doc claim into a guarantee | Especially for locality, semantic support, encryption, process identity |
| The full Constitution mutation audit (for now) | Grew past what could be executed; see §9, lesson 1 |

---

## 7. The five evidence tracks

All sent; each has its own stop condition and produces a report only.

| # | Track | Question | Method |
|---|-------|----------|--------|
| 1 | Observer/provider gate | Does the Observer enforce `is_local` on the real path, not via Stage 8 priority or hostname? | Test-first + manual break-it |
| 2 | `PIP_DB_KEY` | Which consumers (main DB vs `vector_store`) depend on the env key; which reads are redundant? | Discovery; two separate findings |
| 3 | PID-reuse lock | Can the lock distinguish the original PIP process from a later process with the same PID? | Discovery-first: what identity is stored |
| 4a | Stage 1 routing | Can classification still route an identity/project question away from the retrieval it needs? | Test-first on retrieval state, not intent label |
| 4b | Cache safety | Can a no-context answer be cached and replayed after correct context exists? | Two-step behavioral test |

Target test file for Track 1:
`backend/tests/test_observer_provider_authorization.py`.

### 7.1 Rules for returned reports
1. Read each report against its own stop condition only.
2. Classify it A–D (§3).
3. A report may **recommend** a fix (Track 3 may name a missing lock
   field). Implementation needs a separate, explicit authorization.
4. After all five are classified, look for cross-track patterns. One is
   **plausible but unverified**: Tracks 2 and 3 may both be category B
   (missing state). Do not write it into any promise until both reports
   confirm it independently.

### 7.2 Track 1 report — Observer/provider gate (2026-09-26)

**Stop condition:** does the Observer enforce locality on the real path, not
via Stage 8 priority or hostname? **Answer: yes. Category C.**

Evidence (strong): `backend/tests/test_observer_provider_authorization.py`,
real WS session → idle timeout → `_default_observer_provider` →
`OpenAICompatibleProvider` → counting stub on `127.0.0.1`. Registered
non-local: 0 stub requests, 0 Ollama calls, the refusal is
`ObserverLocalProviderError`, and `observed_at` stays NULL. Break-it
(gate at `stage_11_observer.py:772` disabled): stub receives
`POST /v1/chat/completions`, both tests fail; restored, both pass. Marked
local in both records, the real lifespan catch-up processes the session
(`completed`, one stub call).

Further findings, found by running the code (two temporary tests, since
deleted) — **recommendations only, nothing implemented:**

1. **Queue-not-fallback breaks at the next launch (category A).** If no
   local provider exists at startup, recovery sets `observed_at`, the drain
   gets `ObserverLocalProviderError`, and the row is marked `failed`, which
   is terminal. A second start does not retry it, so the session is never
   learned from, even after a local provider is added later. The retry
   mechanism exists (`pending_observer.RetryableError` → `deferred`), but
   `drain_pending_on_startup` (`session_lifecycle.py:309`) routes only
   `ObserverUnavailableError` into it. It fails closed (nothing leaves the
   machine), but the "queued for next launch" claim does not hold past the
   first start.
2. **Locality lives in two records, and they can disagree.**
   `llm_endpoints.is_local` (the provider's self-report) and
   `provider_consent.is_cloud`. The Stage 11 gate requires both.
   `add_endpoint` updates the first on re-save, but inserts the consent row
   with `ON CONFLICT DO NOTHING`, and no route changes `is_cloud`. So
   re-saving a non-local endpoint as local leaves it permanently refused.
   It fails closed, and the only way out is to remove and re-add the
   endpoint. This conflicts with §2.3 "one source of truth per rule".
3. **Promise 5 wording names a column that does not exist (category D).**
   There is no `provider_consent.is_local`. The attested record is
   `provider_consent.is_cloud` together with `llm_endpoints.is_local`. The
   wording needs an owner decision; it is not changed here.

Not in scope, noted: `server.py` `_default_observer_provider` carries an
unreachable duplicate of its own fallback block after `return ollama`.

### 7.3 Track 2 report — `PIP_DB_KEY` (2026-09-26)

**Stop condition:** which consumers (main DB vs `vector_store`) depend on
the env key, and which reads are redundant? Two findings, one per
consumer, as required.

**Method.** Baseline full suite at `db2ddd8`: 1191 pass, 3 fail. All
three are in `test_llm_endpoint_store.py`, need a running Ollama, and pass
17/17 with `is_available` patched True. The same run intermittently hangs
in `test_ws_chat_accumulates_conversation_history_across_turns`, a known
flake (see `pytest.ini`); it happened once in three runs today. Then two
mutations, each in a throwaway worktree, full suite each: (A) `_conn()`
reads `session_key.current_key()` instead of the env; (B) the same for
`vector_store._get_db_key()`. Plus two temporary behavioural checks,
since deleted.

**Finding 1 — main DB (`server._conn`, `server.py:1004`): the env read is
redundant in-process. Category C for the read itself.**
- Mutation A changed nothing: 1191 pass, the same 3 fail. That is medium
  evidence ("no test notices").
- The code path agrees. Every in-process write of the variable is paired
  with `session_key._key`: set in `unlock`, `set_initial_password` and
  `change_password` (`session_key.py:190`, `230`, `370`), popped with it in
  `lock` (`:89`), and adopted into it at lifespan start (`:109`).
- No other backend code opens the main DB from the env.

**Finding 2 — `vector_store` (`_get_db_key`, `vector_store.py:124`): the
env read is load-bearing, and it fails open. Category A.**
- **Not redundant.** `scripts/restore_backup.py:318` sets the env purely so
  `vector_store` encrypts the rebuilt index; a script process has no
  `session_key`.
- Mutation B broke 8 `test_vector_store` tests, but they use the env as
  their switch for the encrypted path, so that is test mechanism, not
  production. (A ninth, `test_ws_chat_lazily_creates...`, failed on the
  race its own comment describes; that path does not use `vector_store`.)
- The consequence Mutation B *should* have exposed went unnoticed:
  `test_restore_backup` replaces `rebuild_vector_index` with a stub, so a
  restore that silently builds a plaintext index is not caught by any
  test.
- **Fails open.** With no key in the env, chunk text and the file path are
  written in plaintext even when the main DB is encrypted (the "no-op
  passthrough", `vector_store.py:120`). Confirmed by a run of the real
  functions: signed in, a chunk was stored encrypted; after
  `session_key.lock()` (what `POST /auth/lock` calls) on the same open
  connection, the next chunk's text and path were on disk in plaintext,
  and `check_consistency` then reported the document as drifted.
- **Reachability in the app is by code reading only, not demonstrated.**
  `/auth/lock` neither waits for nor cancels `_catch_up_task` (which runs
  `rebuild_if_drifted`), and a request already running keeps its
  connection. So an index rebuild or ingest in flight at sign-out writes
  plaintext.
- **Prediction, not verified:** a later re-index writes encrypted chunks
  under the HMAC id but does not remove the plaintext ones, so the
  plaintext would persist.

**Also confirmed: the key reaches child processes.** After unlock,
`GET /llm/catalog` runs `nvidia-smi` (`ollama_provider.py:184`) with the
inherited environment. A stand-in executable received the exact key in
`PIP_DB_KEY`.

**What this does to the decided outcome (§8.1).** The pre-accepted
completion was "redundant `vector_store` read + documented main-DB env
transport". The evidence says the reverse: the main-DB read is the
redundant one, and the `vector_store` read is the load-bearing transport,
with a fail-open. The §7.1 warning applied; the expected outcome was not
the result.

**Recommendations only — nothing implemented:**
1. `vector_store` fails closed when the main DB is keyed and no key is
   present, instead of writing plaintext.
2. `/auth/lock` waits for, or cancels, in-flight index writes before
   forgetting the key.
3. Pass the key to `vector_store` explicitly (as `reencrypt` already
   takes it) rather than through the env. Then the env export, and its
   inheritance by `nvidia-smi` or any future child, can go.
4. `test_restore_backup` asserts the rebuilt index is encrypted, not just
   that the rebuild was called with a key.

**Candidate Promise 7 final clause (owner decision):**
> While PIP is unlocked, the key is held in the backend's memory and is
> also exported to its process environment, where child processes inherit
> it. Index writes made without the key in that environment are stored
> unencrypted.

### 7.4 Track 3 report — PID-reuse lock (2026-09-27)

**Stop condition:** can the lock tell the original PIP process from a later
process with the same PID? First, what identity does it store? **Answer:
no. It stores a bare PID and nothing else. Category B (missing state).**

**What exists.**
- `instance_lock.acquire()` (`instance_lock.py:131`) writes `str(os.getpid())`
  to `data/pip.lock`.
- Every consumer reads only that integer and asks whether it is alive:
  - `acquire()` itself, via `_pid_is_running`: GetExitCodeProcess on
    Windows, `kill(pid, 0)` on POSIX;
  - `restore_backup.py:148`, `merge_projects.py:87` and
    `seed_demo_conversation.py:254`, all through `_pid_is_running`;
  - `launch_pip.ps1:84`, via `Get-Process`;
  - `_db.py`, `clear_poisoned_snapshot.py`, `retract_fabricated_candidates.py`
    and the two `seed_project_*` scripts, which only print a note.
- **What is missing:** anything that identifies *which* process, such as
  the process creation time or the executable. With a bare PID, "the PIP
  that wrote this" and "whatever now has that number" are the same state.

**Evidence (strong for the mechanism).** PID reuse was simulated, not waited
for (§6): the lock was pointed at a live `ping.exe`, which is exactly the
state recycling leaves behind. In a temporary test, since deleted:
- The real app lifespan refused to start with `AlreadyRunningError`
  ("PIP backend is already running (pid N) … Stop that instance first").
- `restore_backup.refuse_if_pip_is_running()` exited: "PIP appears to be
  running".
- The launcher's stale-lock block, run verbatim, kept the lock: `Get-Process`
  reported `PING`.
- Control: once `ping` exited, `acquire()` took the lock over.

The existing suite already pins this behaviour without naming it:
`test_acquire_raises_when_a_live_different_pid_holds_the_lock` uses the
pytest *parent* process, which is not PIP, as the holder.

**What broken looks like.** It fails *safe* for data: it refuses and
never steals, so two writers are never allowed. It fails *hard* for the
user:
- The backend does not start, and when the launcher starts it hidden
  that failure is invisible (by the launcher's own comment at `:71`; not
  demonstrated here).
- Restore and merge refuse to run.
- The error tells the user to stop "that instance" by PID, which after
  reuse is an unrelated process.
- The launcher's cleanup cannot help, because it asks the same question
  with the same missing state.

**Not measured:** how often Windows actually reuses a stale PID. That is a
property of the OS and was deliberately not tested (§6).

**Recommendation only — nothing implemented:** store the holder's process
creation time next to the PID, and treat the lock as held only if a live
process with that PID has that creation time. Every Python consumer
already goes through `_pid_is_running`, so one function changes. The
launcher's PowerShell check is a second copy of the rule and would need
the same field (§2.3, one source of truth).

**Noted, out of scope:** `acquire()` checks the file and then writes it
without an atomic create, so two backends starting at the same instant
could both take the lock. That is a race, not PID reuse, and was not
tested.

**Cross-track (§7.1 rule 4):** the prediction that Tracks 2 and 3 would
both be category B does not hold. Track 3 is B; Track 2 came back C and A.

### 7.5 Track 4a report — Stage 1 routing (2026-09-27)

**Stop condition:** can classification still route an identity or project
question away from the retrieval it needs? Asserted on what reaches the
model, not on the intent label. **Answer: yes, for most phrasings tried.
Category A.** Retrieval exists and works; the classifier disconnects it.

**Mechanism.**
- Stages 3 (decision log) and 5 (RAG) always run.
- Only Stage 4 (profile memory) is gated by category, through
  `stage_04._CATEGORY_TABLES`.
- `external_information`, `general_knowledge` and every unmapped category
  fetch `interaction_style` alone. `coding_question` and `research_request`
  fetch neither identity nor projects.
- Stage 1 checks categories in order: continuation, external, coding,
  research, then project, then personal. So any external keyword
  (`current`, `latest`, `recent`, `today`, `right now`), coding verb or
  research verb wins over the words "my" and "project".

**Evidence (strong).** A temporary test, since deleted, ran the real
`pipeline.run_sync` on a real DB seeded with a name (`Zarqa Venn`) and an
active project (`Heliotrope`). A recording provider captured the exact
prompt the model received.

| Question | Category | Name in prompt | Project in prompt |
|---|---|---|---|
| who am I? | personal | yes | yes |
| what's my name? | personal | yes | yes |
| list my projects | project | no | yes |
| what are my goals? | personal | yes | yes |
| what is my current project? | external | **no** | **no** |
| what's the latest on my project? | external | **no** | **no** |
| what have I been working on recently? | external | **no** | **no** |
| what am I working on right now? | external | **no** | **no** |
| what should I do today on my thesis? | external | **no** | **no** |
| what am I working on? | general | **no** | **no** |
| where did we leave off? | general | **no** | **no** |
| help me implement the next step of my project | coding | **no** | **no** |
| debug the login bug in my project | coding | **no** | **no** |
| compare my project vs a typical final year project | research | **no** | **no** |

10 of the 14 lost the project. The failures are the ordinary ways to ask
what you are working on.

**It is worse than missing context.** For "what is my current project?"
the prompt says `WHAT PIP HAS RECORDED ABOUT THIS USER (the complete
record, not a sample):` and then lists only the interaction style. Rule 4
of the same prompt tells the model to answer that it has nothing recorded.
- The expected answer is therefore a confident *"you have no project
  recorded"* while the project is in the database. That is the inverse of
  the fabrication incident: a false negative instead of an invention.
- Cause: `stage_07` renders "none recorded" only for tables in the
  category's expected set (`stage_07_context_assembly.py:173–213`). Tables
  outside it are silently omitted under a header that claims completeness.
- The model's actual reply was not observed; a fake provider was used.

**Side observation, Promise 6 territory — not investigated.** Five of these
personal questions also match the Stage 6 web-search trigger. With web
search consented, the message text would be sent to the search provider.
It is consent-gated, so this is not a leak; but a question about the user
triggering a web search is a routing effect, not an intent.

**Recommendations only — nothing implemented:**
1. Do not let the context header claim a complete record for tables that
   were not fetched. Either say which were not looked up, or drop
   "complete".
2. Fetch identity and active projects for every category. They are small,
   and the §4 "extra harmless context" reasoning already accepted this for
   the word "project".
3. If category precedence is kept, a first-person or "working on" signal
   should outrank the external, coding and research keywords.
4. Turn the table above into a permanent test on prompt content, the same
   shape as the probe.

### 7.6 Track 4b report — cache safety (2026-09-27)

**Stop condition:** can a no-context answer be cached and replayed after
the correct context exists? Two-step behavioural test. **Answer: yes, and
across profiles. Category A.** Freshness rules exist, but the replay path
is not connected to them.

**Mechanism (`response_cache.py`, `pipeline.py:306`).**
- The cache is a module-level dict held in process memory. Its key is
  `sha256(normalised message + project_id)`.
- It is checked after Stage 1 and **before** Stages 3–9. A hit therefore
  skips the decision log, the profile lookup, RAG and the model.
- The TTL is fixed when the answer is written: 24h for `general_knowledge`
  and `technical_explanation`, 1h for `external_information`, 0 for
  personal and project questions.
- The "decision log always overrides" rule (Part 7.1) is enforced only at
  write time (`decision_log_hit=`). The read does not consult the category
  or the decision log.
- Nothing outside `pipeline.py` references the cache. Nothing invalidates
  it on new documents, decisions, profile changes, sign-out or profile
  switch.

**Evidence (strong).** Temporary tests, since deleted, ran the real
pipeline with a recording provider. In each case step 1 asked with no
context and step 2 asked again after the context was added. A control
repeated step 2 with the cache cleared, to show the new context would
have been used.

| Case | Step 2, cache as-is | Control, cache cleared |
|---|---|---|
| Document ingested after caching ("explain how the Heliotrope sync engine works", technical, 24h) | model **not called**; `NO-CONTEXT ANSWER` replayed | model called; document in prompt |
| Decision logged after caching ("what is the best database for a desktop app") | model **not called**; stale answer replayed | model called; decision in prompt |
| Profile A's document-based answer, same question asked against profile B's database in the same process | B received **A's answer**; B's model not called | — |

The decision case breaks two stated rules at once. Once the decision
exists, the question is classified `project_question` (TTL 0, "never
cached"), and it matches the decision that "always overrides". Both
checks come after the cache read, so neither is consulted.

**Cross-profile.** Profiles are separate password-encrypted databases
served by one backend process. The cache key has no profile in it, and
the cache survives sign-out and switching.
So an answer built from one profile's documents or record is served to
another profile that asks the same words within the TTL. **This crosses
the boundary the per-profile encryption exists to keep.** Demonstrated at
the pipeline level with two databases in one process; the real
sign-out → switch → sign-in route sequence was not driven end to end.

**Interaction with 4a (not separately tested).** "what am I working on?"
is `general_knowledge`, so after §7.5's "you have no project recorded"
answer it would be cached and replayed for 24h. "what is my current
project?" (`external_information`) would be replayed for 1h. The two
defects compound; they remain separate causes (§6).

**Bounded by:** process lifetime (the cache is memory-only, so a restart
clears it) and the TTL.

**Recommendations only — nothing implemented:**
1. Include the active profile in the key, and clear the cache on sign-out
   and on profile switch. This is the confidentiality item and the most
   urgent.
2. Consult freshness at read time, not only at write time. Re-check the
   decision log before serving, or version the key by the last change to
   documents, decisions and profile.
3. Do not cache an answer whose context contained no user record, or that
   was produced for a question Stage 1 has since reclassified.
4. A permanent two-step test per case above.

### 7.7 Cross-track synthesis (2026-09-27)

Authorized 2026-09-27, run after all five reports were classified (§7.1
rule 4). Built only from §7.2–§7.6: no new code was run for it. A pattern
is stated as **confirmed** only when at least two reports show it
independently. Anything else is labelled.

#### Classification at a glance

| Track | Result | What breaks, as seen from outside |
|---|---|---|
| 1 Observer gate | C, plus A and D | Nothing leaves the machine; a session queued at startup is lost for good |
| 2 `PIP_DB_KEY` | C (main DB), A (`vector_store`) | Index text and file paths written as plaintext after sign-out |
| 3 PID lock | B | PIP refuses to start when a reused PID is alive |
| 4a Routing | A | "You have no project recorded" while the project is in the DB |
| 4b Cache | A | Stale answers replayed; one profile's answer served to another |

The original "gap" list meant *unverified* (§3). Of six findings, only
one, the Observer gate, turned out to be already enforced.

#### Pattern 1 — the sign-out / profile-switch boundary does not reach work already in memory. Confirmed (Tracks 2, 4b).

- `session_key.lock()` forgets the key, and `/auth/lock` refuses new
  routes.
- What already exists in the process is not touched:
  - Track 2: in-flight index writes read the now-empty env and store
    plaintext;
  - Track 4b: the module-level response cache keeps serving answers, now
    to a different profile.
- Both break the same thing: per-profile confidentiality, which Promise 7
  and the per-profile password exist to provide.
- Neither defect was found by looking at the boundary. They are separate
  mechanisms that fail at one moment.
- **Unverified link shared by both:** neither report drove the real
  `/auth/lock` → `/auth/profile` → unlock route sequence end to end. One
  such test would confirm or refute both at once (see "next evidence").

#### Pattern 2 — one rule, two copies. Confirmed present in all five tracks; confirmed harmful in three.

§2.3 "one source of truth per rule" is broken in every track:

| Track | Rule | Copy 1 | Copy 2 | Observed effect |
|---|---|---|---|---|
| 1 | Is this provider local? | `llm_endpoints.is_local` | `provider_consent.is_cloud` | Re-saving as local leaves the provider permanently refused |
| 2 | What is the key? | `session_key._key` | env `PIP_DB_KEY` | Paired in the backend, but the env copy is also the script transport and is inherited by `nvidia-smi` |
| 3 | Is PIP running? | `_pid_is_running` (Python) | `Get-Process` (launcher) | Both miss reuse; a fix to one leaves the other wrong |
| 4a | What was the model told exists? | `stage_04._CATEGORY_TABLES` | `stage_07` "complete record" header | The header claims completeness for tables never fetched |
| 4b | Is this answer still valid? | Write-time checks (TTL 0, decision override) | Read path (none) | Stale answers served past both rules |

Only Tracks 1 and 4a show the copies actually *disagreeing* in a run, and
4b shows one copy bypassed; in 2 and 3 the copies can drift but were not
seen to. So the confirmed claim is: the duplication is present in all
five, and it produced a wrong outcome in three (1, 4a, 4b).

#### Pattern 3 — mechanisms built as fail-closed held; mechanisms treated as optional carried correctness and failed open. Confirmed (Tracks 1, 3 vs 2, 4a, 4b).

- **Designed to refuse, and did:**
  - the Observer locality gate (1): zero requests, and the break-it was
    caught;
  - the instance lock (3): refuses, never steals.
- **Designed as a convenience, and failed open where correctness depended
  on them:**
  - `vector_store`'s "no-op passthrough" without a key (2);
  - the category default of `interaction_style` only (4a);
  - the response cache, documented as "never load-bearing for
    correctness" (4b), which the §7.6 evidence contradicts.

The safety-critical defects all sit in the second group. Implication,
labelled as a *recommendation* rather than a finding: classify a component
by what it can cause, not by what it was built for. If a component can
change what the user is told, or what reaches disk, §2.3 "fail closed"
applies to it.

#### Pattern 4 — the tests hid the defect; they did not merely miss it. Confirmed (all five).

| Track | How the existing or planned test concealed it |
|---|---|
| 1 | The planned step 6 would pass on failure (`observed_at` is set before the Observer runs); the first draft passed with the gate removed, because the disconnect path never ran under TestClient |
| 2 | `test_restore_backup` stubs the rebuild; `test_vector_store` runs an encrypted DB with a plaintext index as the default case |
| 3 | `test_acquire_raises_when_a_live_different_pid_holds_the_lock` pins "any live PID blocks" using a non-PIP holder, without naming the consequence |
| 4a | `test_stage_01_intent_classifier.py` makes 19 assertions on the category label and none on what reaches the prompt |
| 4b | `test_pipeline.py`'s autouse `isolated_response_cache` fixture was added because a cached answer from one test served a later one. That *is* the production defect; the fixture removed the symptom from the suite |

This is §2.2 ("assert on outcomes, not return values") and §5 ("a guard
nobody has watched fail is not a guard") confirmed from the other side: in
each track the test sat one layer too far in, or cleaned away the state
the defect lives in. The 4b case is the sharpest. Test isolation is right
for the suite, but it removed the only place the defect had ever been
seen, and the fixture's comment was never turned into a product finding.

#### Pattern 5 — keys that identify less than the thing they stand for. Confirmed (Tracks 3, 4b).

- The lock treats a PID as a process, but a PID names a process only for
  its lifetime (3).
- The cache treats message + project as an answer's identity, but the
  answer also depends on profile, documents and decisions (4b).
- Both are missing-state defects (category B in shape, even where the
  track as a whole is A).
- The same fix shape applies to both: add the missing identity (creation
  time; profile and record version) to the key.
- This is the missing-state pattern §7.1 predicted for Tracks 2 and 3.
  That prediction was wrong about Track 2 but right in kind: it appears
  in 3 and 4b.

#### Not confirmed — kept as predictions

- ~~Plaintext chunks survive a later re-index~~ — confirmed in §7.8.
- ~~In-flight writes during sign-out are reachable in practice~~ —
  confirmed on `/rag/ingest` in §7.8.
- A real model answers "no project recorded" (4a; a fake provider was
  used).
- The `test_ws_chat` hang (once in three full runs) is independent of
  Track 1's test file (not measured).

#### What this means for the promises (owner decisions; nothing rewritten here)

- **The largest defects fall outside the seven promises.** Cross-profile
  answers (4b) and wrong answers about the user (4a) break no written
  promise, because none covers them: exactly the §2.5 limit. Candidates:
  - **Promise 8, profile isolation:** nothing derived from one profile's
    data is served to, or stored under, another profile.
  - **Promise 9, current record:** an answer about the user reflects the
    record as it is when asked. Never a cached answer from before it
    changed, and never "none recorded" for data that was not looked up.
- **Promise 5:** "queued for the next launch" holds for one launch only
  (Track 1 A), and the named column does not exist (Track 1 D).
- **Promise 7:** the final clause is decided by Track 2. Pattern 1 adds
  that encryption at rest can be bypassed at the moment of sign-out.
  Candidate wording is in §7.3.

#### Suggested order for authorizing fixes (a recommendation, not a decision)

1. **The profile boundary (Pattern 1):** Track 2 recommendations 1–2 and
   4b recommendation 1. They are confidentiality defects and share one
   boundary, so one regression test covers both.
2. **Answers about the user (4a + 4b, compounding):** 4a recommendations
   1–2 and 4b recommendation 2.
3. **Lost learning:** Track 1 finding 1, a locality refusal at startup
   being terminal.
4. **Availability:** the Track 3 lock identity.
5. **Wording:** Promises 5 and 7, plus the decision on Promises 8–9.

Each fix follows §2.2: test first on the outcome, break it once, one
commit per promise.

#### Single highest-value next evidence

One end-to-end test through the real routes:
1. Sign in to profile A and index a document.
2. Ask a technical question (so the answer is cached).
3. Start an index rebuild and sign out mid-rebuild.
4. Switch to profile B, sign in, and ask the same question.
5. Assert: B's model is called; B's answer contains nothing from A; and
   no plaintext chunk exists in A's index.

It would move two of the "not confirmed" items above to confirmed or
refuted, and it becomes Pattern 1's permanent regression test.

### 7.8 End-to-end profile boundary test (2026-09-27)

This is the §7.7 "single highest-value next evidence" test, run through the
real routes (`/auth/profiles`, `/auth/setup`, `/rag/upload`, `/rag/ingest`,
`/ws/chat`, `/auth/lock`, `/auth/profile`, `/auth/unlock`) under a real
lifespan. It lives outside the suite (see "status of the test").

**Patched, and why:**
- the model provider, replaced by a recorder, so we see exactly what the
  model would be sent;
- the Observer, a no-op here because it is unrelated and would reach for
  Ollama;
- `vector_store.DOCUMENTS_ROOT`, a module constant aimed at the real
  `data/documents`, redirected to a temp folder so the test cannot write
  user data;
- a one-shot pause before the index write, so that sign-out lands while an
  ingest is in flight. It changes timing only.

**Results:**

| Claim under test | Result |
|---|---|
| Profile B is served profile A's answer (4b) | **Confirmed.** Bob, signed into his own new profile, asked the same question and received `ANSWER#1 citing QUOKKA-7`, Alice's answer built from Alice's document. `cache_hit: True`; Bob's model was never called. |
| An index write in flight at sign-out is stored in plaintext (Track 2) | **Confirmed on `/rag/ingest`.** Event order: ingest paused at the index write → `/auth/lock` returned 200 with no key held → ingest returned 200. The chunk text and its file path were stored in plaintext in Alice's index. |
| The plaintext survives a later re-index (Track 2 prediction) | **Confirmed.** Alice signed back in and catch-up finished. The plaintext chunk and plaintext path were still on disk, and no encrypted copy was added (2 chunks before and after). |
| The same through `/rag/upload` | **Not reproduced**, and not reachable in this form. The upload chunk was stored encrypted. `/rag/upload` is an `async` route that runs the embedding synchronously, so it holds the event loop and `/auth/lock` cannot run until it ends. That is **inferred from timing** (44.7s with a 30s pause, against 12.8s via `/rag/ingest`), not measured directly. It also means an upload stalls every other request while it embeds; that is out of scope and noted only. |

**New finding: uploaded documents are neither per-profile nor encrypted
on disk. Category A.**
- `profiles._activate` re-points `PIP_DOCUMENTS_ROOT`.
- But `/rag/upload` writes to `vector_store.DOCUMENTS_ROOT`
  (`server.py:767–775`), a constant fixed at import.
- `_validate_file_path` checks ingest paths against that same constant.
- Observed: Alice's uploads landed in the shared folder, not in
  `profiles/alice/documents`; both profiles' own `documents` folders
  stayed empty; and both files were visible from Bob's side.
- The uploaded file is written as the uploaded bytes: `heliotrope.txt` on
  disk contained `QUOKKA-7` in plaintext.
- This contradicts Promise 7's "document text … encrypted at rest" for
  the upload copy. It also means one profile's documents sit where
  another profile's ingest would accept them.

**Effect on §7.7.**
- Pattern 1 now has three confirmed mechanisms, all through real routes:
  the cache, in-flight index writes, and the upload folder.
- Two of §7.7's four "not confirmed" items are now confirmed:
  in-flight writes are reachable, and plaintext survives a re-index.
- The remaining two (the real model's answer in 4a, the `test_ws_chat`
  hang) are unchanged.
- Candidate Promise 8 (profile isolation) is now broken three ways.

**Status of the test.** It prints observations rather than asserting
correct behaviour, because all three defects are present and a test that
asserts the fix would fail. Kept outside the repository pending a decision:
- commit it as a strict `xfail` that turns green when fixed; or
- commit it with the fix, as Pattern 1's regression test (§2.2: test in
  the same commit as the change).

**Expected outcomes are not results.** "`vector_store` read is probably
redundant" and "the lock probably stores only a PID" are predictions, not
findings.

---

## 8. Status

### 8.1 Decisions made (choices; need no evidence)

| Decision | Status |
|----------|--------|
| Governing principle and development strategy (§1–2) | Adopted |
| Four-way classification (§3) | Adopted |
| Promise 5 wording: attestation, not proof | Decided |
| Ollama down → queue for next launch, never cloud | Decided |
| Promise 4 narrowed wording | Decided |
| Promise 7 wording except the Track 2 clause | Decided |
| Track 2 outcome "redundant `vector_store` read + documented main-DB env transport" counts as a valid completion | Decided |
| Stage 1 split into 4a/4b | Decided |
| `FREEZE_LIST.md` is the single canonical record | Decided |
| Full Constitution mutation audit deferred | Decided |

### 8.2 Evidence status (facts; need reports)

| Track | Report | Classification |
|-------|--------|----------------|
| 1 Observer/provider gate | Returned 2026-09-26 (§7.2) | C; plus A (startup queue) and D (wording) as recommendations |
| 2 `PIP_DB_KEY` | Returned 2026-09-26 (§7.3) | Main DB read: C (redundant). `vector_store` read: A (load-bearing, fails open to plaintext) |
| 3 PID-reuse lock | Returned 2026-09-27 (§7.4) | B: stores a bare PID, so a reused PID blocks startup |
| 4a Stage 1 routing | Returned 2026-09-27 (§7.5) | A: 10 of 14 identity/project questions lose the project; header then claims a complete record |
| 4b Cache safety | Returned 2026-09-27 (§7.6) | A: stale no-context answers replayed after documents/decisions exist; one profile's answer served to another |
| Promises 1–3 tests | Not yet written | — |
| Promise 4 threshold measurement | Not started | — |
| Database census | Not run | — |
| Cross-track synthesis | Done 2026-09-27 (§7.7) | 5 confirmed patterns; 2 candidate promises; fix order recommended |
| End-to-end profile boundary | Run 2026-09-27 (§7.8) | Cross-profile cache and in-flight plaintext confirmed via real routes; uploads not per-profile and plaintext on disk (A) |

---

## 9. Conversation record

How this plan was reached, for future reference.

### 9.1 Sequence
1. **Initial review.** Goal judged sound and the stack defensible. Main
   risk: the governance layer (the graded contribution) was claimed but
   unmeasured, while recent work was mostly shell (installer, icons,
   profile UI).
2. **Evaluation design debated.** Corrections reached: grounding, the
   evidence gate and the Constitution catch *different* error classes;
   the gates run in sequence and the evidence gate must precede
   `reinforce_evidence()`, so they cannot be ablated independently; a
   "policy-only" test set is circular; the Constitution's value may be an
   invariant to test, not a rate to measure.
3. **Constitution audit spec.** Grew over about ten revisions (clause
   table, per-element mutation, guard vs live, canaries, flake protocol,
   census). It was never executed and produced no repository evidence.
4. **Pivot.** Dropped the audit. Adopted seven concrete promises, one
   outcome test and one break-it check each.
5. **Priorities set:** known gaps first, then Promise 7 wording, then the
   remaining promise tests. Everything else frozen.
6. **Gap decisions:** queue-not-fallback; locality as attestation;
   `PIP_DB_KEY` as two consumers; PID lock discovery-first; Stage 1 split
   into routing and cache.
7. **Five task specs sent.** Reports pending.
8. **Documentation.** This file made canonical; strategy (§2) adopted as
   the standing method.

### 9.2 Lessons
1. **Planning can become the sideways expansion it was meant to stop.**
   Ten revisions of the audit spec produced zero evidence; a small test
   would have produced some in an afternoon. Hence the two-revision cap.
2. **Predictions must stay labeled as predictions** until a report
   confirms them — the same "implemented ≠ active" error behind the
   original encryption bug.
3. **The narrowest honest claim beats the strongest unprovable one.**
   Promises 4, 5 and 7 all became stronger documents by claiming less.
4. **Discovery tasks must separate what exists from what is missing.**
   Tracks 2 and 3 may find missing state, not broken wiring, and that
   changes the fix.

### 9.3 Open questions for the owner
- Which recent bug would §2 have caught before shipping, and which would
  it have missed?
- When will the database census run, given it can change what the
  Promise 4 measurement is able to show?

---

## 10. Background (not part of the freeze mechanics)

- **Fine-tuning rejected as a fabrication fix.** The bug was
  deterministic (misleading context); training teaches tendencies, and the
  only corpus was the contaminated history. A smaller stock Observer model
  remains a separate capability experiment.
- **Documented limitations kept visible:** Stage 12 threshold quality
  unmeasured; Stage 1 is regex under a 30 ms budget by design; `PIP_*`
  test isolation not exhaustively audited; decision history keeps only the
  latest `state_reason`; semantic duplicate decisions are not
  deduplicated, by choice.

---

## 11. Freeze rule

Until all five tracks return and are classified:

**No feature work. No speculative cleanup. No fix without evidence.**

Each promise ends in exactly one state: *mechanism + passing evidence*,
*mechanism + documented limitation*, *missing state identified for a
later task*, or *claim narrowed to what the mechanism does*. A promise
that exists only in prose is not resolved.
