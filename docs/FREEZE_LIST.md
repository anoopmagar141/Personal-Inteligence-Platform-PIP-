# PIP — Reliability Plan and Governance Freeze

**Canonical document.** Update in place; do not create a second summary.
Location in the repo: `docs/FREEZE_LIST.md`.

**Status: evidence-first freeze, fixing by explicit authorization.** All
five evidence tracks returned (§7.2–§7.6); cross-track synthesis done
(§7.7); end-to-end profile boundary test run (§7.8). Production code has
changed only under four explicit authorizations, each fix test-first with
the test seen failing: profile boundary (§7.9), answers about the user
(§7.10), lost learning (§7.11), lock identity (§7.12). §7.7's fix order is
complete: the promise wording was decided 2026-09-28 (§4 now holds nine
promises). Anything further needs a new authorization.

Contents: 1 Principle · 2 Development strategy · 3 Classification ·
4 The nine promises · 5 Evidence · 6 Rejected methods · 7 Evidence tracks ·
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
- `docs/LOG.md` is held at **25 entries**; the thirty-one oldest are rolled into
  twenty-seven Archive summary lines (done 2026-09-26).

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

## 4. The nine promises

### Promise 1 — Observer writes only through governance
**Claim:** Observer candidates reach memory only via grounding → evidence
gate → Stage 12 → Stage 13.
**Must prove:** reachability — no production path from Observer output to
storage that skips governance. A static import guard is a guard, not a
proof. A valid candidate must still be written; rejecting everything
proves the wrong property.
**Evidence (2026-09-28):** holds for memory candidates -
`backend/tests/test_observer_governance.py`, break-its seen failing (§7.13).
Decision candidates and the snapshot take separate gates (§7.13 finding 1).

### Promise 2 — Observer cannot write immutable fields
**Claim:** name, language, timezone change only by the user directly.
**Must prove:** a grounded, gate-passing candidate for these fields cannot
reach a DB write — tested on DB state, not on the enforcer's return value.
**Evidence (2026-09-28):** holds - the identity row never changes, three
independent layers (§7.13). A same-named preference can still be learned and
shown beside it (§7.13 finding 2).

### Promise 3 — Gated fields require confirmation
**Claim:** a gated field is not persisted without prior user confirmation.
**Must prove:** the write is unreachable without confirmation, on real DB
state. A JSON rule naming the field is not evidence.
**Evidence (2026-09-28):** holds for all four gated patterns, using shapes
the real gate accepts; written only after `resolve_pending` (§7.13).

### Promise 4 — Stored memory is supported by the user's words
**Limitation:** grounding proves a quote was said, not that it supports
the claim. Live case: a `python_level` candidate grounded in "I've been
comparing FastAPI and Flask".
**Current honest wording:**
> PIP verifies that Observer evidence was actually said and applies
> evidence-gate and Stage 12 threshold checks. Whether a genuine quote
> actually supports the claim drawn from it has not been separately
> measured.

**Evidence (2026-09-28):** measured end to end on 37 labelled conversations
with the real model (§7.14): 88–90% of learned memories true, the one false
memory being sarcasm; recall 30–39%, mostly lost at the gate. The gate alone
(`scripts/eval_evidence_gate.py`): 0 false accepts on 40 tuned and 25
held-out cases. The wording above predates both.

### Promise 5 — Observer runs only on authorized local providers
**Wording (decided 2026-09-28):**
> The Observer runs only against a provider recorded as local in both of
> its records: the endpoint's own entry (`llm_endpoints.is_local`; Ollama
> is local by definition) and its consent entry
> (`provider_consent.is_cloud = 0`). Both are attested by whoever configured
> the endpoint, never inferred from the hostname; PIP does not verify the
> machine boundary. When no provider passes, nothing is sent and the
> session stays queued; it is processed at a later start or sign-in once
> one does. No mid-session retry is promised.

**Limitation:** re-saving an existing endpoint as local updates only
`llm_endpoints`, so it stays refused until it is removed and added again
(§7.2 finding 2, not fixed).

**Reason:** a loopback address is not proof of locality (tunnels, remote
`OLLAMA_HOST`). Claiming proof would overclaim.
**Enforced by:** the Stage 11 gate (`stage_11_observer.py`, `run()`),
which requires both records; `drain_pending_on_startup` keeps a refused
session queued (§7.11).
**Evidence:** `backend/tests/test_observer_provider_authorization.py` - zero
requests to a loopback provider recorded as not local, break-it caught
(§7.2); a refused session processed at a later start (§7.11).
**History:** the first decided wording named `provider_consent.is_local`,
which does not exist (§7.2 finding 3), and "catch-up at the next launch"
held for one launch only until §7.11.
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
**Wording (decided 2026-09-28):**
> Each profile's database is encrypted at rest under a key derived from
> its password. The document index stores chunk text and file paths
> encrypted under the same key; embeddings are not encrypted. Uploaded
> documents are also kept as ordinary files in the profile's documents
> folder, unencrypted - the encrypted copy is the one inside the database.
> Unencrypted by design: profile names in the profile registry, and a
> sign-in picture if the user publishes one. Plaintext written before a
> password was set, or by versions before §7.9, is not scrubbed. While a
> profile is signed in, its key is held in the backend's memory and also
> in its process environment, which every child process inherits.

**Limitation kept by decision:** the uploaded-file copy stays unencrypted
on disk. The alternative - keeping only the database copy and writing
files out only when a rebuild needs them - is a code change and was not
authorized.
**Enforced by:** SQLCipher on the database; Fernet/HMAC in `vector_store`
under the same key, which refuses to write without it (§7.9).
**Evidence:** §7.3 (key consumers and child-process inheritance, measured);
§7.8 (upload file on disk in plaintext, measured); `test_profile_boundary.py`
(no plaintext index writes after sign-out).
**History:** "document text is encrypted" overstated it - true of the
database copy, not of the uploaded file (§7.8); the key clause waited on
Track 2, which found the backend exports the key rather than receiving it.

### Promise 8 — Profile isolation
**Claim (adopted 2026-09-28):** nothing derived from one profile's data is
served to another profile or stored under it.
**Enforced by** the sign-out boundary every profile switch passes through:
`session_key.lock()` empties the response cache; `vector_store` refuses
index reads and writes when the active profile has a password but no key is
held (`IndexLockedError`); uploads and ingestion are confined to the active
profile's own documents folder (`vector_store.documents_root()`).
**Evidence:** `backend/tests/test_profile_boundary.py`, through the real
routes, each test seen failing first (§7.8, §7.9).
**Limitations:** one backend process serves every profile, so isolation
rests on these mechanisms, not on OS process separation. A chat connection
already open at sign-out keeps its connection until the client drops it -
the guarantee is that no *new* work reaches the data. Files an older
version put in the shared `data/documents` folder stay there.
**Origin:** not in the original seven; the defects it covers were found by
the tracks and broke no written promise (§7.7, the §2.5 limit).

### Promise 9 — Answers reflect the current record
**Claim (adopted 2026-09-28):** an answer about the user reflects their
record as it is when asked.
**Enforced by:** every question reaches the model with the user's identity
and active projects (`stage_04._ALWAYS_TABLES`); the context never presents
what was looked up as the whole record, and names the sections it did not
look up (Stage 7 header, rule 4); a cached answer is never served after the
record changes (`record_version`, bumped by triggers on every table the
context draws from).
**Evidence:** `backend/tests/test_answers_about_the_user.py`, asserting on
the prompt the model receives (§7.10).
**Limitations:** goals, skills, preferences and tools are still fetched by
question category, so a phrasing Stage 1 misroutes gets "not in front of
me" for them rather than the answer. The tests check what the model is
told, not what it says; its replies are not measured.
**Origin:** as Promise 8 - found by Tracks 4a and 4b, outside the original
seven.

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
   first start. **Fixed 2026-09-28 in `2306831` (§7.11).**
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
   wording needs an owner decision; it is not changed here. **Resolved
   2026-09-28: Promise 5 reworded in §4 (`2003817`).**

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
asserts the fix would fail. It was kept outside the repository pending a
decision, and was superseded by `test_profile_boundary.py` (§7.9):
- commit it as a strict `xfail` that turns green when fixed; or
- commit it with the fix, as Pattern 1's regression test (§2.2: test in
  the same commit as the change).

### 7.9 Profile boundary fixes (authorized 2026-09-27)

This is the first fix authorization under the freeze: §7.7's suggested
item 1, plus the §7.8 upload finding. Each fix followed §2.2:
- a promise, and the mechanism that enforces it;
- an end-to-end test through the real routes, **seen failing on the
  unfixed code** for the stated reason (which is the break-it);
- the smallest change, then the full suite;
- one commit per promise.

All five tests are in `backend/tests/test_profile_boundary.py`, which is
now Pattern 1's regression test.

| Commit | Promise | Mechanism | Seen failing before the fix as |
|---|---|---|---|
| `a1a1a6b` | An answer cached in one session is never served after it ends, in particular to the next profile | `session_key.lock()` empties the response cache | Bob's question never reached his model |
| `a37da7c` | No chunk or file path is written to the index in plaintext while the profile's DB is encrypted | `vector_store._get_db_key()` raises `IndexLockedError` when the profile has a salt but no key is held | chunk text reached disk in plaintext |
| `be74d70` | A document uploaded in a profile is stored in that profile's folder, and no other profile can ingest it | `vector_store.documents_root()` follows the profile; the `DOCUMENTS_ROOT` constant is removed; `adopt_shared_documents()` copies legacy records in at sign-in | the upload was stored in the shared folder; the legacy record was never adopted |
| `9327887` | Each sign-in runs its own catch-up | `_start_catch_up()` queues behind a running catch-up instead of skipping | Bob's unobserved conversation was never recovered |

The full suite passed after every commit; the last run was 1199 passed.

**The fourth promise was not in the authorized list.** It was found while
fixing the second one. The catch-up started by `/auth/setup` was still
running at sign-out, and it hit the new refusal, which was correct. But
the next sign-in then skipped its own catch-up because one "was running".
- This corrects the claim made when the fixes were planned, that
  fail-closed "covers" Track 2 recommendation 2. The refusal stopped the plaintext,
  but the refused work was never redone until catch-ups were queued.
- It was fixed under the same authorization, because it sits on the same
  boundary and a sign-in with no catch-up is a new session left without
  its recovery. Flagged here so the owner can object.

**Deliberately not covered (still open):**
- **Plaintext already on disk is not scrubbed.** That covers:
  - chunks written by the old in-flight path;
  - the originals left in the old shared folder (copied, not moved,
    because another profile may name the same file);
  - uploaded files, which are still written to the profile's folder as
    the uploaded bytes.

  The last contradicts Promise 7's "document text … encrypted at rest"
  for the file copy. It now needs a wording decision or a separate fix.
- **Same-profile staleness** (§7.6 recommendation 2): a new document or
  decision still does not invalidate a cached answer within one session.
  That is item 2 of the fix order.
- **`/rag/upload` holds the event loop while it embeds** (§7.8, inferred
  from timing). This is out of scope, and it is also why that route could
  not interleave with sign-out.
- **Promise 8 wording.** Profile isolation now has mechanisms and tests
  for the four paths above. Writing it as a promise is still an owner
  decision (§7.7).

### 7.10 Answers-about-the-user fixes (authorized 2026-09-28)

§7.7's suggested item 2: §7.5 (4a) recommendations 1–2 and §7.6 (4b)
recommendation 2. The same method as §7.9: each test was seen failing on
the unfixed code, then the smallest change, then the full suite, one
commit per promise. The tests are in
`backend/tests/test_answers_about_the_user.py` and assert on the prompt the
model receives through the real pipeline.

| Commit | Promise | Mechanism | Seen failing before the fix as |
|---|---|---|---|
| `55d1523` | Every question reaches the model with the user's identity and active projects | `stage_04._ALWAYS_TABLES` added to every category's table set | 11 of the 14 Track 4a questions |
| `3173f60` | The prompt never presents what was looked up as the whole record | The Stage 7 header says each section is complete and names the sections not looked up; rule 4 now says "not in front of you" instead of "not recorded" | "the complete record" still in the prompt |
| `111c43e` | A cached answer is never served after the user's record changes | A `record_version` counter bumped by triggers on `RECORD_TABLES` is part of the cache key | Stale answer served, with the model never called, after a document, a decision and a new project |

The last full-suite run was 1219 passed.

**Two test-design corrections, recorded because §5 applies to our own
tests too:**
- The first cache tests asked about "the Heliotrope sync engine" while
  Heliotrope was the seeded project. That made the question a project
  question, which is never cached, so the control failed and every
  staleness case passed on the unfixed code. The questions were changed
  until the control passed and the cases failed.
- The control (`test_an_unchanged_record_is_still_answered_from_the_cache`)
  stays as a guard. A trigger on a table written on the per-message path
  would quietly switch the cache off, and this test would catch it.

**Flake measured, not assumed.** `test_ws_chat_lazily_creates_…` failed
once under full-suite load during this work (its second failure today).
It replaces `pipeline.run`, so none of these changes run inside it. Run in
isolation it passed 15/15 on the change and 15/15 on the previous commit.

**Deliberately not covered (still open):**
- **Whether a real model behaves better with the new header and rule 4 is
  not measured.** The tests check what the model is told, not what it
  says. The fabrication incident is why rule 4 exists; its protection
  against guessing is kept word for word, and only "recorded" became "in
  front of you".
- §7.5 recommendation 3 (letting first-person signals outrank Stage 1's
  external, coding and research keywords) was not authorized. With
  identity and projects always sent, it now matters only for the other
  tables (goals, skills, preferences), which the prompt now names as not
  looked up.
- Personal questions that match the web-search trigger (§7.5 side note,
  Promise 6) are unchanged.
- The cache key still ignores conversation history, as before this work.
- **Candidate Promise 9 (current record)** now has mechanisms and tests
  for all three of its parts. Writing it down is an owner decision.

### 7.11 Lost-learning fix (authorized 2026-09-28)

§7.7's suggested item 3: §7.2 finding 1.

- **Promise:** a session the Observer could not process for lack of a
  local provider stays queued, and is processed at a later start once one
  exists, with nothing sent anywhere in between.
- **Mechanism:** `drain_pending_on_startup` translates
  `ObserverLocalProviderError` into `pending_observer.RetryableError`, as it
  already did for `ObserverUnavailableError`, so the row is deferred instead
  of `failed`.
- **Test:**
  `test_a_session_refused_at_startup_for_locality_stays_queued_for_a_later_start`
  in `backend/tests/test_observer_provider_authorization.py`. It uses the
  real lifespan catch-up twice, with a loopback stub recorded as not local
  and then as local. On the unfixed code it failed with `['failed']`. It
  passes now, and the stub receives nothing until the second start.
- **Commit:** `2306831`. It also corrects two Stage 11 docstrings that
  called the locality error a caller programming error and said LLM
  failures fail open.
- **Full suite:** 1217 passed and 3 failed. The three are the
  `test_llm_endpoint_store` tests that need a running Ollama (down on this
  machine, same assertion as the §7.3 baseline).

**Still open from Track 1:**
- Finding 2 (locality in two records that re-saving can leave in
  disagreement).
- Finding 3 (the Promise 5 wording names a column that does not exist).
- The unreachable duplicate block in `_default_observer_provider`.

**Unchanged by design:** a row deferred for locality is re-checked at every
start until a local provider exists. The check happens before any call, so
a start with none still sends nothing.

### 7.12 Lock identity fix (authorized 2026-09-28)

§7.7's suggested item 4: the §7.4 recommendation.

- **Promise:** the instance lock counts as held only by the process that
  took it. A later process handed the same PID does not block PIP.
- **Mechanism:** `data/pip.lock` holds `<pid> <creation time>`.
  `instance_lock.holder()` is the only place the rule is decided: held
  means that PID is alive **and** was created at that time. A creation
  time that cannot be read counts as held, so it fails toward refusing a
  free lock, never taking a held one. Every gate asks `holder()`:
  - `acquire()`;
  - the `restore_backup`, `merge_projects` and `seed_demo_conversation`
    gates;
  - the launcher, through the backend's own Python.
  A bare-PID file keeps its old meaning.
- **Tests:** `backend/tests/test_lock_identity.py`. A real holder takes
  the lock and exits, then the PID in the file is pointed at a live
  `ping.exe`, which is the state reuse leaves. On the unfixed code the
  backend, the restore script and the launcher's real block, cut from
  `launch_pip.ps1`, each refused. They were three tests, seen failing
  separately, and each passes now. The control, a live holder, is still
  refused by all three.
- **Commit:** `c940bed`.
- **Full suite:** 1220 passed and 4 failed. One was a lifespan test that
  read the file with `int()`; it was fixed in the same commit, and its
  file now passes 65/65. The other three are the Ollama-dependent tests
  (§7.3).

**Two decisions made during the fix (the owner may object):**
- **The launcher no longer repeats the rule in PowerShell.** The obvious
  port compares `Process.StartTime`, which is local time. Converting it
  back can be an hour off for a process started in the hour the clocks go
  back, and that error deletes a *live* lock, which is the one failure
  this lock exists to prevent. The launcher now asks `holder()` through
  Python, so the rule has one copy (§2.3).
- **Every script that parsed the file with `int()` had to change with the
  format.** Otherwise they would have read the new format as "not
  running", and a restore would have run over a live database.

**Not covered (still open):**
- `acquire()` still checks the file and then writes it without an atomic
  create. That is the §7.4 race note; it is not PID reuse, and it was not
  tested.
- The Linux branch of `_process_started_at` (`/proc/<pid>/stat`) is
  untested; this machine is Windows. Anywhere else the time is not
  recorded, and the lock behaves as before.
- Five note-only scripts (`_db.py` and four seed/cleanup scripts) print
  the file's raw contents, now including the creation time. That is
  cosmetic.

### 7.13 Promises 1–3 tests (authorized 2026-09-28)

This was the council's "one thing to do first" (council transcript,
2026-09-28). The work is tests, not fixes. Result: **all three promises
hold on the current code. Category C.**

**Method.** `backend/tests/test_observer_governance.py` drives the real
session-end path, `stage_11_observer.run_session_end`, on an onboarded
profile.
- A scripted stand-in plays the Observer's LLM, which is the untrusted
  part; everything after it is real (grounding, the evidence gate, Stage 12
  with the Constitution, and Stage 13).
- Every assertion is on database state.
- Promise 3 uses candidate shapes the **real** gate accepts, taken from the
  held-out evaluation set.
- Promise 2 forces the gate to say yes: that is the worst case the promise
  has to survive.

| Promise | Test | Result on the current code | Break-it (throwaway worktree) |
|---|---|---|---|
| 1 | A supported candidate is written (so the chain doesn't just reject everything) | Pass | — |
| 1 | In a mixed extraction, every profile write is one the Constitution approved, and the profile changes by exactly those writes | Pass | Stage 13 also writing DISCARD/HARD_REJECT: **fails** |
| 1 | Census: outside the tests, only Stage 13 calls `write_approved_candidate`, and only Stage 13 and the verification loop call `create_memory_candidate` | Pass (medium evidence, §5) | A second caller added in Stage 11: **fails** |
| 2 | name, language_preference and timezone: a gate-passing candidate never changes `identity`, and is not queued as a question | Pass ×3 | The immutable rule alone removed: still passes, because the two other layers hold. Every layer opened: fails on the *queue* assertion (the conflict path queued it). Identity approved outright: **fails on identity unchanged** ×3 |
| 3 | goal_memory.\*, interaction_style.\*, active_projects.\*, skill_memory.\*.level: not written until confirmed, queued once, written after `resolve_pending` | Pass ×4 | The gated rule removed: **fails** ×4 |

**Identity is guarded three times over.** The immutable-field rule; the
writable-tables list, which excludes `identity`; and
`write_approved_candidate`, which has no identity branch at all. Breaking
any one of them leaves the promise intact.

**Findings from the probes (temporary tests, since deleted).
Recommendations only; each needs an owner decision.**

1. **Promise 1 is narrower in the code than in its wording (category D).**
   The claim covers the Observer's *memory candidates*, and for those it
   holds. But the Observer also produces **decision candidates** and a
   **session snapshot**, and neither goes through the evidence gate or the
   Constitution.
   - A decision must quote words the user actually said (an ungrounded one
     was dropped).
   - It is then scored on deterministic signals.
   - With two or more signals it is **auto-logged** into the decision log,
     which Stage 3 puts into prompts. Probe: "I'm going with FastAPI
     because Flask has no native async, instead of Django" → logged
     directly.

   The snapshot has its own grounding gate (`_snapshot_may_overwrite…`).
   Either the wording of Promise 1 names these separate gates, or decisions
   are routed through the evidence gate.
2. **The immutable fields can be shadowed in preferences (category A or
   D).** The Constitution matches immutable fields by *field name*, in any
   table. `preference_memory` is Observer-writable, and there is no stored
   preference named `language_preference` for the rule to see. On the real
   path (real gate, real Constitution), "I prefer French, please answer me
   in French from now on" wrote `preference_memory.language_preference =
   French`; `language` and `timezone` did the same. The prompt then holds
   both `language_preference: English` (identity) and
   `language_preference: French` (preferences).
   - The identity row itself never changed, so Promise 2 holds as worded.
   - The user did say it, so this may be legitimate learning.
   - But the model is shown two conflicting values for a field the promise
     calls immutable.
   - Options: refuse immutable field names in every table; map them to a
     pending question for the user; or state it as a limitation.

**Not covered:** the snapshot's own gate is not separately tested; and the
verification loop's queue writes were only counted in the census, not
exercised.

### 7.14 End-to-end Observer measurement (authorized 2026-09-28)

This was the council's main recommendation: measure the learning path as a
person meets it, rather than the gate alone.

**Method.** `scripts/eval_observer_end_to_end.py` runs each of 37 labelled
conversations (`backend/tests/observer_cases.py`) through the real local
model and `run_session_end()`, on a fresh isolated profile, and reads what
was learned from the database. The conversations contain 23 facts the user
states and 25 traps:
- third parties, hypotheticals and questions;
- negation, the past, retractions and sarcasm;
- words only the assistant said;
- the immutable fields;
- small talk, and mixed sessions.

The labels were committed in `1256b51`, before the first full run. Three
runs, because the model samples. The raw per-case output is in
`docs/eval/observer_end_to_end_2026-09-28.md`.

**Conditions:** model `qwen2.5:7b`, the only one pulled on this machine;
the code defaults to `llama3.1:8b`, which was not measured. Every profile
was in its first two weeks, where the Constitution accepts only candidates
the model labels *explicit*.

**Results.** The three runs agree closely.

| | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| Precision, memory tables (true / true + false) | 8/9 | 9/10 | 7/8 |
| Precision, including decision-log entries (hand-reviewed) | 10/12 (83%) | 10/13 (77%) | 10/12 (83%) |
| **Recall**: stated facts learned (written or queued for confirmation) | 8/23 (35%) | 9/23 (39%) | 7/23 (30%) |
| …of which written outright | 3 | 4 | 3 |
| Traps reaching a belief table | 1/25 | 1/25 | 1/25 |

**Precision is high, and its one failure is systematic.** The same false
memory appeared in all three runs. "Sure, because Internet Explorer is my
favourite browser. Obviously." was stored as a preferred tool: the gate
judged it `EVIDENCE_SUFFICIENT` and the Constitution approved it. The
Firefox the user actually tests on was hard-rejected. **The gate cannot
read sarcasm**, which the council predicted; the gate corpus has no
sarcasm cases. Every other trap category held in every run: third
parties, hypotheticals, questions, negation, the past, the assistant's
words, a forged role line, and the immutable fields.

**Decisions are the weaker gate, as §7.13 predicted.** The keyword labels
could not classify 3–4 rows per run; all of them were decision-log
entries, auto-logged without the evidence gate. Reviewed by hand:
- Six stated a decision the user did make ("ship the beta in May", "run a
  half marathon in April", "continue using pytest", "won't learn Java"
  after "I'll pass").
- Four overstated a tentative remark as a decision:
  - "I'm not convinced" about Java was logged twice as a decision;
  - "probably not worth it" became "decided against rewriting in Elixir";
  - "to stay with Go" was logged though the user never said it.

The overstatements are what pull the combined precision down to 77–83%.

**Recall is low, and it has three causes.** Each cause is visible in the
funnel of every run.
1. **The evidence gate rejects plain true statements (the largest loss).**
   All of these were judged `EVIDENCE_NOT_ENTAILING` and discarded:
   - "Please keep your answers short from now on";
   - "I keep all my notes in Obsidian these days";
   - "I work mostly in TypeScript";
   - "I really like detailed explanations";
   - "I'm learning Rust";
   - "I write all my essays in LaTeX";
   - "a payments service" (as a project).

   The gate's support-language lists do not recognise ordinary phrasings.
   The gate evaluation's one held-out false reject,
   `held_accept_tool_habit`, is this same Obsidian phrasing. What looked
   like one miss there is most of the recall loss here.
2. **The model labels first-person facts as "inferred", inconsistently.**
   "I've been writing Python professionally for six years" and Go "for
   four years" passed the gate but were labelled *inferred*, and a
   first-two-weeks profile discards those
   (`threshold_violation_week_1_2`). Re-run, the same Go statement was
   labelled *explicit* and correctly queued for confirmation. With the
   label *explicit*, all three affected facts would have been queued
   (checked directly against Stage 12).
3. **The model extracts nothing** for some facts: repeated questions about
   vector clocks (a topic interest), "It's Kotlin", and "I deploy
   everything with Docker Compose" (extracted, then dropped by grounding).

**What this means for the thesis.** "Learns only what the user actually
said" is close to true for memory: about 9 in 10 of what it learns is
true, and the one failure is sarcasm, every time. But it learns roughly a
third of what users plainly say, and writes outright fewer than a fifth of
the facts stated. Most of the rest is either queued for confirmation or
lost at the gate. The gate trades recall for precision more steeply than
the gate-only evaluation showed. Decisions, which skip the gate, are
where overstatement gets in.

**Limitations of this measurement:**
- n is small: 23 facts and 25 traps.
- The labels were written by the measuring agent, not independently.
- Keyword matching could misclassify a row. Every non-TRUE row was
  reviewed by hand (listed above); the TRUE rows were not.
- One model (not the code's default), a first-two-weeks profile only, and
  English only.
- The queued-for-confirmation facts are counted as learned, but whether
  a user confirms them is not measured.

**Recommendations only; nothing changed:**
1. Add sarcasm cases to the gate corpus, and decide how the gate should
   treat them.
2. Widen the gate's support language for plain first-person statements
   ("I keep…", "I work mostly in…", "please keep…"), measured against both
   corpora so that precision is watched while recall rises.
3. Stop relying on the model's explicit/inferred label for first-person
   statements, or relax the weeks 1–2 rule for gated tables, which already
   ask the user.
4. Route decisions through the evidence gate (§7.13 finding 1). That is
   where the overstatements come from.

### 7.15 Launch-checklist UI fixes (authorized 2026-10-01)

A read-only audit of the Flutter client against the half of a web launch
checklist that applies to a desktop app (LOG 2026-10-01) found four
problems. The owner authorized all four, in this order, one commit each.

**Fix 1 - text contrast.**
- **Promise:** every text colour (text, muted, faint) in both palettes and
  on the sign-in stage is at least 4.5:1 on every surface it can sit on.
- **Mechanism:** the colour values themselves; `test/theme_test.dart` is
  the guard. Faint had been held to 3:1 as "metadata", but 3:1 is the
  large-text bar and faint is set at 11-13.5px in about sixty places.
- **Evidence:** the raised bar failed on the old palette in four places
  (light faint 2.86:1 and light muted 4.38:1 on surfaceRaised, dark faint
  3.22:1, sign-in faint 3.87:1 on the card). New values: light muted
  #5A5F6E, light faint #676C7C, dark faint #858A9A, sign-in faint
  #7B8195, all >= 4.61:1. A second test keeps faint quieter than muted.
  Full Flutter suite 302/302.
- **Not covered:** colours set as literals outside the palette (the
  sign-in screen's error red, chart and glow tints) are not in the test.

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
| Promise 5 reworded: both locality records; queued until a later start or sign-in (2026-09-28) | Decided |
| Promise 7 final wording, including the key-in-environment clause; uploaded file copy stated as a limitation, not fixed (2026-09-28) | Decided |
| Promise 8, profile isolation, adopted (2026-09-28) | Decided |
| Promise 9, answers reflect the current record, adopted (2026-09-28) | Decided |

### 8.2 Evidence status (facts; need reports)

| Track | Report | Classification |
|-------|--------|----------------|
| 1 Observer/provider gate | Returned 2026-09-26 (§7.2) | C; plus A (startup queue, fixed §7.11) and D (wording, fixed in §4 Promise 5). Finding 2, two locality records, still open |
| 2 `PIP_DB_KEY` | Returned 2026-09-26 (§7.3) | Main DB read: C (redundant, unchanged). `vector_store` read: A (load-bearing, failed open to plaintext; now fails closed, §7.9). Key still exported to the environment, stated in Promise 7 |
| 3 PID-reuse lock | Returned 2026-09-27 (§7.4) | B: stores a bare PID, so a reused PID blocks startup (fixed §7.12) |
| 4a Stage 1 routing | Returned 2026-09-27 (§7.5) | A: 10 of 14 identity/project questions lost the project; header claimed a complete record. Recommendations 1–2 fixed (§7.10); 3, Stage 1 precedence, open |
| 4b Cache safety | Returned 2026-09-27 (§7.6) | A: stale answers replayed after documents or decisions existed; one profile's answer served to another. Cross-profile fixed (§7.9), staleness fixed (§7.10) |
| Promises 1–3 tests | Written 2026-09-28 (§7.13) | C: all three hold, each break-it seen failing; two findings (decisions skip the gate; immutable names shadowed in preferences) |
| End-to-end Observer measurement | Run 2026-09-28 (§7.14) | 37 conversations, 3 runs, qwen2.5:7b: precision 88–90% (memory), 77–83% with decisions; recall 30–39%; sarcasm gets through |
| Promise 4 threshold measurement | Not started | — |
| Database census | Not run | — |
| Cross-track synthesis | Done 2026-09-27 (§7.7) | 5 confirmed patterns; 2 candidate promises; fix order recommended |
| End-to-end profile boundary | Run 2026-09-27 (§7.8); now `test_profile_boundary.py` | Cross-profile cache and in-flight plaintext confirmed via real routes; uploads not per-profile and plaintext on disk (A) |
| Profile boundary fixes | Landed 2026-09-27 (§7.9) | 4 promises enforced and tested; plaintext already on disk and same-profile staleness still open |
| Answers-about-the-user fixes | Landed 2026-09-28 (§7.10) | 3 promises enforced and tested; real-model effect of the new header unmeasured |
| Lost-learning fix | Landed 2026-09-28 (§7.11) | Locality-refused sessions stay queued; Track 1 findings 2-3 still open |
| Lock identity fix | Landed 2026-09-28 (§7.12) | Reused PIDs no longer block PIP; atomic-create race and Linux branch untested |
| Launch-checklist UI fixes | Landing 2026-10-01 (§7.15) | Fix 1 contrast landed |

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
