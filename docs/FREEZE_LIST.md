# PIP — Reliability Plan and Governance Freeze

**Canonical document.** Update in place; do not create a second summary.
Location in the repo: `docs/FREEZE_LIST.md`.

**Status: evidence-first freeze.** Five discovery/test tasks sent; Tracks 1
and 2 returned (§7.2, §7.3), three pending. No production code has been changed under
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
- `docs/LOG.md` is held at **25 entries**; the seven oldest are rolled into
  three Archive summary lines (done 2026-09-26).

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
| 3 PID-reuse lock | Pending | — |
| 4a Stage 1 routing | Pending | — |
| 4b Cache safety | Pending | — |
| Promises 1–3 tests | Not yet written | — |
| Promise 4 threshold measurement | Not started | — |
| Database census | Not run | — |
| Cross-track synthesis | Not authorized | — |

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
