# PIP — PERSONAL INTELLIGENCE PLATFORM
## Master Reference Document
### Version: 3.0 — Post-Schema-Finalization
### Status: Architecture Complete, Implementation Starting

> **PURPOSE OF THIS DOCUMENT**
> This document is the single authoritative reference for PIP. It supersedes all earlier
> versions of the architecture document. Any AI, engineer, or reviewer reading this cold
> should have complete context to continue development without prior conversation history.
> Decisions marked [EMPIRICALLY VERIFIED] were tested in a live sandbox. Decisions marked
> [FINALIZED] are locked. Decisions marked [OPEN] require action before proceeding.

---

## DOCUMENT MAP

```
Part 1  — Core Idea and Problem Statement
Part 2  — Design Philosophy and Hard Constraints
Part 3  — What PIP Is Not (Permanent Exclusions)
Part 4  — Success Definition (Tiered)
Part 5  — Feature Priority Order
Part 6  — System Architecture
Part 7  — 14-Stage Message Pipeline
Part 8  — Memory Architecture
Part 9  — Constitutional System
Part 10 — Security Architecture (UPDATED: SQLCipher)
Part 11 — Storage Architecture (FINALIZED after 5 review rounds)
Part 12 — Observer Architecture
Part 13 — Provider Architecture
Part 14 — Frontend and Client Architecture
Part 15 — API and Transport Specification
Part 16 — All ADRs (001–025+)
Part 17 — Folder Structure (FROZEN)
Part 18 — Phase Roadmap (Phase 0–10)
Part 19 — Settings Reference (settings.json)
Part 20 — Finalization Status (What is locked vs open)
Part 21 — Implementation Sequence for Phase 0
Part 22 — Onboarding Question Script
Part 23 — Command Reference
Part 24 — Glossary
```

---

# PART 1 — CORE IDEA AND PROBLEM STATEMENT

## 1.1 The Problem

Every existing AI assistant has the same structural failure: **amnesia**.

The user explains themselves every session. Their goals, project history, communication
preferences, decisions — nothing persists. Cloud memory features exist behind subscriptions,
send personal data to third parties, and store only shallow preferences like formatting style.

The result: every session starts at zero. The LLM is smart but blind.

For users doing long-term intellectual work — engineers, researchers, architects — this
means spending 10–15 minutes per session re-establishing context that existed in the
previous one. The AI is helpful once context is rebuilt. It is useless before that.

## 1.2 The Solution

    The LLM knows the world. PIP knows YOU.
    Together they form one intelligent system —
    deeply personalized, fully local, completely private.

PIP is a locally-hosted software layer that wraps around an existing LLM and provides it
with a structured, persistent, encrypted memory system. The LLM handles reasoning and
language generation. PIP handles everything the LLM cannot:

- Who the user is (skills, preferences, interaction style)
- What they are working on (active projects, architecture decisions)
- What decisions they have made (and why)
- Where they left off (session snapshot, open problems)

**PIP does not generate answers. PIP builds the context that makes the LLM's answer
intelligent.**

## 1.3 The Core Mechanism

    Without PIP:
      User: "Why did we choose ChromaDB?"
      LLM:  "I don't have context about your project..."

    With PIP:
      User: "Why did we choose ChromaDB?"
      PIP:  [injects decision log entry into prompt]
      LLM:  "You chose ChromaDB on May 15th because of local-first
             requirements and simple setup. You rejected FAISS as too
             complex and Pinecone as cloud-only."

Same LLM. Same model weights. Completely different output. The difference is entirely the
context PIP assembled from its memory system.

## 1.4 The Core Rule

    PIP recommends → User approves → PIP records.
    Never the other way around. Never silently.

---

# PART 2 — DESIGN PHILOSOPHY AND HARD CONSTRAINTS

These principles govern every design decision. When a choice conflicts with a principle,
the principle wins.

**Personalization Over Raw Model Size**
A smaller model with deep personal context outperforms a larger model that has never met
the user. Context quality is the primary variable in response quality.

**Reliability Over Features**
A half-built system that works correctly on three things delivers more real value than a
fully-designed system that is 40% implemented across everything. Each phase must be
genuinely useful before the next begins.

**Local-First**
Everything runs on the user's machine. Nothing leaves without explicit, per-provider,
per-scope consent. Privacy is a system architecture constraint enforced in code, not
a policy statement.

**Decisions Are First-Class Memory**
The hardest thing to reconstruct is not code. It is the reasoning behind the code. PIP
treats decisions as the most valuable memory type — explicitly recorded, never silently
deleted, queryable by natural language.

**Fail Visibly, Never Silently**
Every failure mode must produce a visible signal. Wrong password produces an error, not
an empty DB. Observer crash leaves profile unchanged, not corrupted. Context overflow
trims lowest-priority content, never corrupts or drops silently.

**The Copilot Principle**
PIP recommends, user approves, PIP records. No autonomous action. No silent writes.
Every consequential action is transparent and user-controlled.

**DB-Level Enforcement Over App-Layer Assumptions**
Where correctness matters, enforce at the DB layer (triggers, CHECK constraints, FK
constraints, single-row guards) not just at the application layer.

**One Writer Per Data Resource**
Every table has exactly one owner module. Every other module is a caller, not a writer.
This is enforced by ADR-025 and a pre-commit hook.

---

# PART 3 — WHAT PIP IS NOT (PERMANENT EXCLUSIONS)

These are permanent design exclusions, not deferred features. Do not suggest them. Do
not implement them under any framing.

| Excluded | Reason |
|---|---|
| Emotion/mood detection | Privacy violation, scope creep, permanently forbidden |
| Psychological profiling | Same as above |
| Mood trend tracking | Same as above |
| Per-message Observer | Noisy, resource-intensive, RAM pressure on 8GB VRAM |
| Scored decision graph | Makes debugging harder, not better |
| Two-pass retrieval | Doubles latency for marginal gain |
| Ephemeral consent tokens | Enterprise solution for wrong scale |
| Four-primitives architecture reframe | Hides complexity, no implementation value |
| Silent cloud fallback | Violates privacy guarantee |
| Autonomous action without approval | Violates Copilot Principle |

**Tool Execution Layer (filesystem, code exec, scheduling)**: DEFERRED to post-v1.0.
Not excluded. Will arrive eventually. When it does, it should use the existing consent
model (extend consent_scope or a sibling tool_consent table), not a new permission
system. PRD Part 1.6 must distinguish non-goals (never) from deferred (later) explicitly.

---

# PART 4 — SUCCESS DEFINITION (TIERED) [FINALIZED]

These two statements are the official success criteria for PIP. Both are locked and must
appear in PRD Part 1.8.

**v0.5 (Academic minimum viable deliverable):**
> PIP correctly enforces constitutional memory rules — it rejects attempts to overwrite
> immutable fields, gates preference updates behind user confirmation, and validates
> Observer candidates against tiered evidence thresholds. `/decide` logs a decision with
> correct confidence scoring. `/profile` shows stored fields with source label and
> confidence.

**v1.0 (Full release target):**
> A user can ask "why did I decide X?" and PIP returns the original decision with
> reasoning, date, and source, retrieved from a searchable persistent log across sessions.

**Why tiered success statements matter:**
The original PRD 1.8 headline claim ("ask why did I decide X six months ago") requires
FTS5 decision search, which does not exist until Phase 6. If the timeline collapses to
v0.5, the original headline cannot be demoed at defense. The tiered statement closes
this risk.

---

# PART 5 — FEATURE PRIORITY ORDER [LOCKED]

```
Priority 1 — Decision Log
Priority 2 — Project Memory
Priority 3 — RAG (Document Retrieval)
Priority 4 — Session Continuity
Priority 5 — Personal Profile
Priority 6 — Observer (Auto-learning)
Priority 7 — Depth Detection (LOW — users can type "briefly" or "in detail")
```

**Tiebreaker rule:** Implementation order prioritizes architectural dependencies and
reliability over feature ranking. If RAG (Priority 3) must be cut for time, that is
a logged conscious decision, not a side effect of running out of weeks.

---

# PART 6 — SYSTEM ARCHITECTURE

## 6.1 High-Level Architecture

```
+-----------+
|   USER    |
+-----+-----+
      |
      v
+-----+------+
| PIP CLIENT |
| CLI (P1-5) |
| Web (P8)   |
| Flutter(P8+|
+-----+------+
      |
      v (WebSocket for chat, REST for CRUD)
+-----+------------------+
|       FASTAPI BACKEND   |
|   (localhost, Phase 2+) |
+-----+------------------+
      |
+-----+-------------------+--------+----------+
|                          |        |          |
v                          v        v          v
14-STAGE PIPELINE    MEMORY/DB   CHROMADB   PROVIDERS
(core intelligence)  (SQLCipher) (RAG only) (Ollama+)
```

## 6.2 Three-Layer Memory Model

```
PERSONAL LAYER
├── identity          (immutable — name, language, timezone)
├── skill_memory      (measurable — performance signals)
├── preference_memory (subjective — explicit + behavioral)
├── goal_memory       (temporal — decays after 14 days inactive)
└── interaction_style (gated — evolves with confirmation)

PROJECT LAYER
├── active_projects       (gated)
├── decision_log          (manual Phase 1, Observer Phase 7)
├── session_snapshot      (JSON — observer-written at session end)
├── topic_interests       (observer-writable, Phase 7+)
└── document_access_patterns (observer-writable, Phase 7+)

KNOWLEDGE LAYER
├── ChromaDB vector store (RAG — derived, rebuildable, NEVER authoritative)
├── preferred_tools       (observer-writable)
└── decision_fts          (FTS5 virtual table for decision search)
```

## 6.3 Hardware Constraints [VERIFIED]

- GPU: RTX 4060, 8GB VRAM
- llama3.1:8b Q4_K_M: ~4.9GB VRAM — main generation model AND Observer (ADR-033, supersedes B1)
- phi3:mini Q4_K_M: ~2.2–2.4GB VRAM — retained only as a candidate model for a future ML-based
  Intent Classifier (B4 currently keeps Intent Classifier as keyword/regex, not generative;
  phi3:mini is not used anywhere in the pipeline today)
- No model-swap orchestration between Observer and generation: both roles run the same
  llama3.1:8b weights, so there is no VRAM-overrun window and no forced cold reload between
  session-end (Observer) and next-session generation
- sentence-transformers (RAG embeddings): CPU-only by default to preserve GPU headroom
- Model-swap benchmark: RETIRED (ADR-033) — no swap exists to benchmark. See ADR-033
  A/B test timing instead (phi3:mini 58.05s vs llama3.1:8b 130.92s, cold-load included,
  n=1 synthetic transcript) for the numbers that replaced it.

---

# PART 7 — 14-STAGE MESSAGE PIPELINE [LOCKED]

```
User Message
     |
     v
[STAGE 0] Gap Detector
  Input:  session_snapshot.json timestamp (Orchestrator must parse the ISO string via datetime.fromisoformat() handling 'Z' suffix before calling gap_detector.run())
  Output: warm_start_level (none|brief|summary|full)
          context_depth_modifier (0-3)
  Gap table:
    < 1 hour        → none, 0
    1 to < 24 hours → brief, 1
    24h to 7 days   → summary, 2  (continuous at 24h, inclusive of exactly 7 days)
    > 7 days        → full, 3
  Failure: none/0, logged, never blocks pipeline
     |
     v
[STAGE 1] Intent Classifier
  Input:  user message, warm_start_level
  Output: category, retrieval_hint, skip_rag (bool)
  Categories: general_knowledge, technical_explanation,
              project_question, personal_question,
              coding_question, research_request,
              external_information, project_continuation
  skip_rag = true when: category = general_knowledge OR
             technical_explanation AND confidence >= 0.9
             AND no project-specific terms detected
  NOTE: Two distinct skip_rag mechanisms:
    Mechanism 1 (skip_rag flag): keyword/token match vs
      active_projects names + decision-log keyword cache.
      This produces the skip_rag bool. Saves ~35ms.
    Mechanism 2 (ADR-002 safety net): lightweight
      title-only embedding pre-check. Runs regardless
      of skip_rag result. These are NOT the same check.
  Failure: category=general_knowledge, skip_rag=false
     |
     v
[STAGE 2] Router
  Input:  category, skip_rag, retrieval_hint, warm_start_level
  Output: ordered retrieval priority list, provider preference
  NOTE: Priority-orderer, not stage-skipper.
        General knowledge still gets ADR-002 pre-check.
  Failure: default LLM-only path, log decision
     |
     +-------+-------+
     |       |       |   (asyncio.gather — parallel)
     v       v       v
  [S3]    [S4]    [S5]
  Dec.    Mem.    RAG+
  Log     Look    Conf
  Look    up      lict
  up              check
     |       |       |
     +-------+-------+
             |
             v
[STAGE 6] Web Search (fires in background thread at Stage 1 detection)
  Trigger keywords: latest, today, current, news, price, who won,
                    recent, weather, right now
  Cache TTL: 3600s
  Failure: return empty, note in response
             |
             v
[STAGE 7] Context Assembly
  Token Budget (6000 total):
    System instructions:   150  (fixed)
    User profile:          400  (selective only)
    Session snapshot:      250  (pre-built by Observer)
    Decision Log entries:  600  (matched entries)
    RAG chunks:            800
    Web results:           800  (top 3)
    Conversation history:  1000 (rolling window)
    User message:          400
    Reserved for response: 2000
  NOTE (resolved during implementation): the per-source lines above sum to 4400
    (+2000 reserved = 6400), not the stated 6000 - a real inconsistency, also baked
    into settings.json's "pipeline" section, not just this prose. Resolution: these
    are per-source MAXIMUM ceilings, not guaranteed fixed reservations. Not every
    source is maxed simultaneously in practice (e.g. RAG contributes 0 tokens when
    nothing matched). When the worst case does happen, the overflow priority below
    is exactly the mechanism that reconciles 4400 down to the true 4000 available
    for content (6000 total - 2000 reserved). If every trimmable section is fully
    dropped, what remains is system_instructions + user_message - which is
    word-for-word the documented failure-mode floor below, confirming this reading.
  Overflow priority (what gets dropped first) - READ AS PRIORITY RANK (1 = most
    protected/dropped last, 7 = least protected/dropped first), NOT a literal
    top-to-bottom drop sequence: rank 1 is annotated "(never drop)", which is
    self-contradictory if the list were read as sequential drop order starting at
    the top. This is the same rank convention already used for ADR-023's Cache
    Authority Hierarchy and Stage 2 Router's default retrieval priority elsewhere
    in this doc - implemented consistently with those, not invented fresh here.
    1. User message (never drop)
    2. Decision Log entries
    3. Profile fields
    4. RAG chunks
    5. Session snapshot
    6. Conversation history (oldest first)
    7. Web results
  Failure: minimal prompt = system + message only
             |
             v
[STAGE 8] Provider Gate
  if is_cloud AND (NOT user_consented OR revoked) → HARD STOP
  if is_cloud AND consented → check consent_scope
  if not is_cloud → proceed
  Failure: config missing → Ollama local, log warning
             |
             v
[STAGE 9] LLM Streaming
  Streams token by token via BaseLLMProvider.chat()
  stage_hint events sent via WS during processing:
    decision_log_hit, web_search_used, cache_hit, model_loading
  model_loading: true whenever llama3.1:8b must be cold-loaded (e.g. first
    message after Ollama's keep_alive has evicted it) — no longer a two-model
    swap signal post-ADR-033, but still needed: a cold load is still real
    wall-clock time the user would otherwise perceive as a silent hang
  Failure: try next local provider, never cloud without consent
             |
             v
[STAGE 10] Response Delivery
  User receives output. Main pipeline complete.
  All learning happens AFTER this stage.
             |
       [10-min idle OR process exit]
             |
             v
[STAGE 11] Observer (async thread, session-end only)
  Single-pass analysis of full session transcript
  Model: llama3.1:8b (ADR-033, supersedes B1 — always LOCAL, never inherits
    the active generation provider; moot while v1.0 is local-only, but the
    boundary must still be enforced explicitly, not assumed)
  Output (three simultaneously):
    memory_candidates: [{target_table, field_name, proposed_value, label,
                         evidence_count, evidence_text}]
    decision_candidates: [{decision_text, signals_found, raw_quote}]
    session_snapshot: {topic, open_problems, last_decisions,
                       suggested_next_step, snapshot_date}
  session_snapshot → written to data/session_snapshot.json immediately
  memory_candidates + decision_candidates → Stage 12
  Non-negotiable rules:
    NEVER self-scores confidence (labels explicit|inferred only)
    NEVER writes directly to any store
    NEVER runs per-message
    NEVER detects document-decision conflicts (Stage 5 job)
  Failure: profile unchanged, snapshot not updated
             |
          +--+--+
          |     |
          v     v
       Memory  Decision
       Cands   Cands
          |     |
          v     v
[STAGE 12] Validation Layer
  Tier 1 (rule-based, always runs):
    Immutable field violation    → HARD_REJECT
    Forbidden schema key         → HARD_REJECT
    Evidence below threshold     → DISCARD
    Gated field                  → REQUIRES_CONFIRMATION
    Behavioral override trigger  → PROMPT_RECONCILIATION
    High-confidence conflict     → TIER_2_REQUIRED
  Tier 2 (small model, only when Tier 1 returns TIER_2_REQUIRED):
    Same field exists at confidence > 0.7 AND Tier 1 did not reject
  Tiered thresholds by profile age:
    Weeks 1–2:  evidence >= 1, explicit label required
    Weeks 3–4:  evidence >= 2
    Month 2+:   evidence >= 3, confidence >= 0.7
  REQUIRES_CONFIRMATION → written to memory_candidates_pending
  (survives session close, picked up next session)
  Failure: reject all candidates (safe failure)
             |
             v
[STAGE 13] Profile + Decision Log Update (parallel writes)
  Only validated, approved candidates write
  Gated field writes wait for user confirmation
  user_verified writes get maximum confidence
  All writes go through memory/ modules only
  Failure: retry once, then log and discard, never corrupt
```

## 7.0a Pipeline Failure Mode Conventions (Fail-Open vs Fail-Closed)

Two deliberately different failure policies exist in the pipeline. This note records the reasoning so future stages are implemented consistently.

**Stage 0 (Gap Detector) — Fail-Open**
Returns `warm_start_level=none`, `context_depth_modifier=0`, logs the error, and never blocks the pipeline. Rationale: Stage 0's only output is a context-scaling signal — how much session history to inject into the prompt. If it fails (missing `session_snapshot.json`, corrupt timestamp, filesystem error), the pipeline degrades to a cold-start: the user gets a correct answer with slightly less conversational continuity. No security property, no privacy guarantee, and no data integrity invariant depends on Stage 0 succeeding. Blocking the entire pipeline over a missing warm-start signal would trade a recoverable UX degradation for a hard user-visible failure — a strictly worse outcome in every case.

**Stage 8 (Provider Consent Gate) — Fail-Closed**
Hard-stops the pipeline if the provider row is missing, `user_consented = 0`, or `revoked = 1`. Rationale: Stage 8 enforces a privacy guarantee — data must not leave the device and reach a cloud provider without the user's explicit, recorded consent. If Stage 8 has any doubt about consent status, the correct answer is never "proceed anyway." The cost of a false positive (user must grant consent before the call proceeds) is a one-time friction event. The cost of a false negative (a cloud call goes out without consent) is a privacy violation that cannot be undone. The asymmetry of consequences mandates fail-closed. The unknown-provider case (no row at all) is treated identically to unconsented: fail-closed, not fail-open, because allowing an unregistered provider through would silently break the guarantee every time a new provider is added before its consent row is seeded.

**Convention for future stages:**
- A stage's failure mode is **fail-open** if the pipeline can produce a correct, safe result without that stage's output (context, hints, ranking signals, cache hits).
- A stage's failure mode is **fail-closed** if skipping the stage could violate a privacy guarantee, a data integrity invariant, or a constitutional constraint.
- Stages 9–13 default to fail-open unless they enforce a constitutional check (e.g. Stage 12 Validation Layer already uses `HARD_REJECT` for immutable field violations — that is fail-closed behaviour within the stage, but the stage itself runs).

## 7.1 Response Cache

```
Position: Between Stage 2 Router and Stage 7 Context Assembly
Key:      hash(normalized_message + active_project_id)
TTL by category:
  general_knowledge:     86400s
  technical_explanation: 86400s
  web_search:             3600s
  project_question:          0 (never cache)
  personal_question:         0 (never cache)
  decision_lookup:           0 (never cache)
Authority: Lowest in hierarchy. Decision Log always overrides.
```

## 7.2 Stage 3: Decision Log Lookup

```
Input:  retrieval_hint
Output: matching active entries (state=active only)
Search: FTS5 MATCH query (LIKE fallback if FTS5 unavailable)
Failure: return empty, continue
```

## 7.3 Stage 4: Memory Lookup

```
Input:  category, retrieval_hint
Output: relevant profile fields only (NEVER full profile dump)
Access: via profile_store.py only
Failure: return empty profile fields, continue
```

## 7.4 Stage 5: RAG Retrieval + Conflict Check

```
Input:  retrieval_hint, document-paste flag from Router
Output: relevant chunks above threshold
        conflict flag if document vs Decision Log conflict
Threshold: Start 0.6, calibrate from 100 real interactions
Conflict detection: runs HERE, not in Observer
Failure: return empty chunks, continue
```

---

# PART 8 — MEMORY ARCHITECTURE

## 8.1 Three-Way Memory Split [LOCKED — separate validation per type]

```
SKILL MEMORY
  What:    Measurable capability levels (0.0 to 1.0)
  Updates: Demonstrated task performance
  Decay:   None
  Schema:  skill_memory table
  Confidence: GENERATED ALWAYS (formula-derived from evidence_count + source_label)

PREFERENCE MEMORY
  What:    Subjective work and communication preferences
  Updates: Explicit statements OR behavioral patterns (3+ sessions, 14+ days)
  Decay:   None (behavioral override instead)
  Schema:  preference_memory table
  Confidence: GENERATED ALWAYS (same formula)

GOAL MEMORY
  What:    Stated objectives and intentions
  Updates: Conversational commitment language
  Decay:   Automatic — decay_flag=true after 14 days inactive
  Schema:  goal_memory table (NOTE: when reading/writing via candidate APIs, field_name uses the convention "goal:<id>")
  Confidence: STORED MANUALLY (decay adjusts it independently of evidence_count)
```

These three types MUST NOT share validation logic. Separate ConstitutionEnforcer
rule branches for each type.

## 8.2 Confidence Formula [LOCKED]

```
Observer labels candidates as: explicit | inferred

Base scores:
  explicit  → 0.9
  inferred  → 0.4
  (user_verified, user_correction also use 0.9 base when written)

Formula:
  confidence = base_score * min(evidence_count, 5) / 5.0

Examples:
  explicit,  1 session  = 0.9 * 0.20 = 0.18
  explicit,  3 sessions = 0.9 * 0.60 = 0.54
  explicit,  5 sessions = 0.9 * 1.00 = 0.90
  inferred,  5 sessions = 0.4 * 1.00 = 0.40

For skill_memory, preference_memory, interaction_style:
  Implemented as SQLite GENERATED ALWAYS AS ... STORED column.
  Never compute or update manually — the DB recomputes on every write.

For goal_memory:
  confidence is a plain STORED column.
  Reason: decay reduces confidence independently of evidence_count.
  Stage 13 decay logic adjusts it directly.
  A generated column cannot express this pattern.
```

## 8.3 Memory Source Trust Hierarchy [ADR-021, LOCKED]

When sources conflict, this order is absolute:

```
1. User correction           (explicit in-session override)
2. Explicit stated preference ("I prefer X")
3. Repeated behavioral pattern (3+ sessions, 14+ days)
4. Single-session inference   (lowest authority)

Recency alone does not win.
Confidence score alone does not win.
```

## 8.4 Behavioral Override Mechanism

```
Trigger: Behavioral evidence contradicts a stated preference
         for 3+ sessions over 14+ consecutive days.

Result: PROMPT_RECONCILIATION
  "Your behavior suggests X. You stated Y. Which is correct?"

Options:
  User confirms new → user_correction write, maximum confidence
  User confirms old → discard, contradiction logged

Never: silent overwrite of an explicit preference.
Never: automatic update after 3 sessions without user review.
```

## 8.5 Memory Verification Loop

Every 30 sessions (`total_sessions % 30 == 0`):
- Surface 3 randomly sampled profile fields
- User confirms, corrects, or removes each
- `user_verified` writes get maximum confidence, override Observer-derived values
- `/verify` command triggers on demand (for testing and thesis defense demo)
- Production loop fires automatically at the 30-session threshold

## 8.6 Memory Lifecycle

```
Signal detected by Observer
         |
         v
CANDIDATE CREATED (explicit | inferred label)
         |
         v
STAGE 12 VALIDATION
  Immutable?      → HARD_REJECT
  Forbidden key?  → HARD_REJECT
  Below threshold?→ DISCARD
  Gated field?    → REQUIRES_CONFIRMATION (written to memory_candidates_pending)
  Override trigger? → PROMPT_RECONCILIATION
  Conflict >0.7?  → TIER_2_REQUIRED (small model check)
         |
         v
[USER CONFIRMATION if gated]
         |
         v
STAGE 13 WRITE
  source_label: explicit|inferred|user_verified|user_correction
         |
         v
REINFORCEMENT (evidence_count increments on repeat observations)
         |
         v
DECAY CHECK (goal_memory only — 14 days inactive → decay_flag=true)
         |
         v
SOFT DELETE (never hard delete for profile fields or Decision Log)
```

## 8.7 Decision Log Details

```
Phase 1 write path: MANUAL ONLY via /decide command.
Populate 20–30 manual decisions before any automation.

Classification uses OR logic (not AND):
  Signal A: explicit_reasoning_in_conversation
  Signal B: commitment_language
  Signal C: alternative_considered

  A + B + C → confidence 1.0 → auto-logged
  Any two   → confidence 0.7 → auto-logged
  Any one   → confidence 0.4 → auto-logged (manual trigger)
  None      → confidence 0.0 → decision_candidates_pending

Log thresholds by source [LOCKED]:
  manual /decide:           log_threshold = 0.4 (any one signal)
  Observer-detected:        log_threshold_observer = 0.7 (two+ signals)
  Observer single-signal:   → decision_candidates_pending (not auto-logged)
  Reason: avoids noise from casual commitment language in Observer output

Both keys defined in settings.json from Phase 0 with activation comments.
log_threshold_observer is INACTIVE until Phase 7 (Observer ships).

Decision candidates pending surface order [LOCKED]:
  ORDER BY confidence ASC, created_at ASC
  (lowest-evidence oldest candidates first — most likely wrong, most
   worth culling. High-evidence candidates are closest to auto-log
   threshold and need less review. NOT pure oldest-first.)

Pending candidate 60-day aging:
  Surfaced max 3 per session. Prompt shown once.
  "This pending decision is aging. Promote, dismiss, or keep?"
```

---

# PART 9 — CONSTITUTIONAL SYSTEM [LOCKED — file not yet written]

## 9.1 constitutional.json Structure

```json
{
  "version": "1.0",
  "changelog": [
    {"version": "1.0", "date": "2026-06",
     "reason": "Initial constitution — locked before Observer build"}
  ],
  "immutable_fields": {
    "fields": ["name", "language_preference", "timezone"],
    "enforcement": "hard_reject"
  },
  "gated_fields": {
    "fields": ["interaction_style.*", "goal_memory.*",
               "active_projects.*", "skill_memory.*.level"],
    "enforcement": "prompt_confirm"
  },
  "observer_may_write": {
    "fields": ["topic_interests",
               "preferred_tools", "document_access_patterns"]
  },
  "forbidden_categories": {
    "enforcement": "hard_reject",
    "exception": "onboarding_bootstrap"
  },
  "onboarding_bootstrap": {
    "bypasses": ["observer", "validation"],
    "permitted_writes": "any_non_forbidden_field",
    "deactivates": "permanent_after_onboarding_complete"
  },
  "memory_types": {
    "skill_memory":      {"validation": "demonstrated_performance"},
    "preference_memory": {"validation": "explicit_or_behavioral"},
    "goal_memory":       {"validation": "commitment", "decay": true}
  },
  "validation_thresholds": {
    "week_1_2":     {"evidence": 1, "requires": "explicit_label"},
    "week_3_4":     {"evidence": 2},
    "month_2_plus": {"evidence": 3, "confidence": 0.7}
  },
  "confidence_model": {
    "explicit": 0.9,
    "inferred": 0.4,
    "formula":  "base * min(evidence_count, 5) / 5"
  },
  "behavioral_override": {
    "trigger_sessions": 3,
    "trigger_days": 14,
    "action": "prompt_reconciliation"
  },
  "decision_log": {
    "write_path_phase_1": "manual_only",
    "logic": "OR",
    "confidence": {"all_three": 1.0, "any_two": 0.7, "any_one": 0.4},
    "log_threshold_manual": 0.4,
    "log_threshold_observer": 0.7
  },
  "provider_consent": {
    "scope_values": ["full_inference", "web_search_only",
                     "embedding_only", "none"],
    "gate_position": "stage_8_before_network_call",
    "enforcement": "hard_stop"
  },
  "proactive_triggers": {
    "allowed": ["session_gap_exceeds_48h",
                "document_decision_conflict_detected",
                "goal_inactive_14_days"],
    "forbidden": ["model_judgment_of_relevance",
                  "model_judgment_of_urgency"]
  },
  "memory_verification": {
    "frequency_sessions": 30,
    "fields_sampled": 3,
    "authority": "overrides_observer_derived"
  },
  "amendment_process": {
    "on_change": "bump version, add changelog entry",
    "on_startup": "check profile.constitution_version vs current"
  }
}
```

## 9.2 ConstitutionEnforcer Class

```python
class ConstitutionEnforcer:
    def __init__(self, constitution_path: str):
        self.rules = load_json(constitution_path)

    # Note: override check precedes threshold check — this order is deliberate and was the subject of a fixed Phase 1 defect. Do not reorder.
    def validate(
        self,
        candidate: MemoryCandidate,
        existing_field: Optional[ExistingFieldState],
        profile_age_weeks: int
    ) -> ValidationResult:

        field = candidate.field_name  # table-qualified, e.g. "preference_memory.x"

        if field in self.rules["immutable_fields"]["fields"]:
            return ValidationResult.HARD_REJECT("immutable_field")

        if not self._is_writable_field(field) and not onboarding_active():
            return ValidationResult.HARD_REJECT("schema_violation")

        # Override check MUST precede threshold check.
        if self._triggers_override(candidate, existing_field):
            return ValidationResult.PROMPT_RECONCILIATION

        threshold = self._get_threshold(profile_age_weeks)
        confidence = self._compute_confidence(candidate)

        if not threshold.passes(candidate, confidence):
            return ValidationResult.DISCARD

        if self._matches_gated_field(field):
            return ValidationResult.REQUIRES_CONFIRMATION

        if self._conflicts_with_existing(candidate, existing_field):
            return ValidationResult.TIER_2_REQUIRED

        return ValidationResult.APPROVED

    def _compute_confidence(self, candidate: MemoryCandidate) -> float:
        base = 0.9 if candidate.label in (
            "explicit", "user_verified", "user_correction"
        ) else 0.4
        return base * min(candidate.evidence_count, 5) / 5.0
```

ValidationResult values and meanings:
```
HARD_REJECT           — immutable field or schema violation (blocked, never written)
DISCARD               — below threshold (not an error, not written)
REQUIRES_CONFIRMATION — gated field (written to memory_candidates_pending, surfaced next session)
PROMPT_RECONCILIATION — behavioral override triggered (surfaced for user decision)
TIER_2_REQUIRED       — conflict with high-confidence existing field (small model called)
APPROVED              — passes all checks (written to profile)
```

**Constitution must be written and all ConstitutionEnforcer tests must pass BEFORE
Observer is built. This is the one hard technical dependency in the entire project (ADR-011).**

---

# PART 10 — SECURITY ARCHITECTURE (UPDATED — replaces all Fernet references)

## 10.1 Encryption Model [EMPIRICALLY VERIFIED]

**Previous design (OBSOLETE, do not reference):**
~~Fernet symmetric encryption per-file with PBKDF2 key derivation~~

**Current design (FINAL):**

```
User types password at app launch
         |
         v
App-level PBKDF2 derives a 256-bit hex key
  Salt: stored on disk in salt.bin (not secret — salt is never secret)
  Held in process memory only for the session lifetime
  Discarded on exit — re-derived every launch
         |
         v
SQLCipher whole-database transparent encryption
  KDF: PBKDF2_HMAC_SHA512 [EMPIRICALLY VERIFIED: confirmed twice]
  Iterations: 256,000 [EMPIRICALLY VERIFIED]
  All tables encrypted as one unit
  No per-file keys, no per-row keys
         |
         v
Each connection opens with raw-hex key syntax:
  PRAGMA key = "x'<hexkey>'"
  (skips SQLCipher's redundant internal KDF pass on the hot path)
         |
         v
Key discarded on process exit
No recovery if password is forgotten — by design.
```

**No recovery mechanism is a feature, not a limitation.** Forgotten password = permanent
profile loss. This is the privacy guarantee. The onboarding flow warns users explicitly
and prompts them to create a backup within the first week.

## 10.2 Backup Export Mechanism [FINALIZED, EMPIRICALLY VERIFIED]

```
/export command:
  1. PRAGMA wal_checkpoint(TRUNCATE)  — defense-in-depth (proven non-load-bearing
                                        for sqlcipher_export() path, but retained
                                        as free protection for any future raw-copy
                                        backup method)
  2. User types a separate backup password (different from live DB password)
  3. ATTACH DATABASE 'backup.pipbak' AS backup KEY '<user-password>'
     NOTE: Backup key uses passphrase syntax (not raw-hex) because it is a one-time
     operation and the full internal KDF pass is an acceptable cost here.
  4. SELECT sqlcipher_export('backup')
  5. DETACH DATABASE backup
  6. .pipbak file delivered to user

Why sqlcipher_export() via ATTACH, not decrypt-then-Fernet-wrap:
  - One encryption technology end to end
  - No plaintext intermediate state (even in memory)
  - Fernet is not a dependency in this codebase at all
  - Separate backup password means live-key compromise does not
    compromise backups

EMPIRICALLY VERIFIED (sandbox test):
  - Generated columns (GENERATED ALWAYS AS STORED) survive
    sqlcipher_export() correctly [tested, confidence recomputed in backup]
  - WAL-resident data (written but not checkpointed) also survives
    sqlcipher_export() without an explicit checkpoint [tested, WAL file
    was >20KB, backup contained the unckeckpointed row]
  - PRAGMA wal_checkpoint(TRUNCATE) is therefore defense-in-depth,
    not the primary mechanism — sqlcipher_export() reads through the
    SQLite page layer, not raw file bytes
```

## 10.3 Connection Setup [LOCKED — single call site: profile_store.py get_connection()]

```python
def get_connection(db_path: str, db_key: str) -> sqlcipher3.Connection:
    # db_key must be a hex string. Enforced:
    assert re.fullmatch(r'[0-9a-fA-F]+', db_key), \
        "db_key must be hex-encoded"

    conn = sqlcipher3.connect(db_path)
    conn.execute(f"PRAGMA key = \"x'{db_key}'\"")  # 1st — must be first
    conn.execute("PRAGMA foreign_keys = ON")         # 2nd — not default in SQLite
    conn.execute("PRAGMA journal_mode = WAL")         # 3rd — concurrent reads
    conn.execute("PRAGMA busy_timeout = 5000")        # 4th — writer queuing
    return conn
```

**Why each PRAGMA is necessary:**

| PRAGMA | Why |
|---|---|
| key (1st) | SQLCipher unlock. Must be first — wrong order = empty DB |
| foreign_keys (2nd) | SQLite does NOT enforce FK by default. Must be explicit |
| journal_mode WAL (3rd) | Readers don't block writers |
| busy_timeout (4th) | Writer collisions wait 5s instead of throwing SQLITE_BUSY |

WAL mode and busy_timeout together make dropping `asyncio.Lock()` safe:
WAL prevents reader/writer blocking. busy_timeout prevents writer-vs-writer exceptions.
SQLite still serializes writes — busy_timeout makes that safe to ignore at app level.

**Wrong-key behavior (critical to test):** A wrong PRAGMA key does NOT throw an exception.
SQLite silently presents an empty database. Required test: open with wrong key,
`SELECT count(*) FROM sqlite_master` — must fail loudly.

## 10.4 Threat Model (Updated)

**T1 — Encryption Key / Database Compromise [UPDATED for SQLCipher]**
- Threat: Attacker gains filesystem access to the SQLCipher database file
- Mitigations:
  - SQLCipher AES-256, PBKDF2_HMAC_SHA512, 256,000 iterations [verified]
  - PRAGMA key is mandatory first connection statement, single call site
  - Wrong key returns empty DB silently — test explicitly (see Phase 0 tests)
  - Live session hex key held in process memory only, never written to disk
  - Backup export uses separate backup password (live-key compromise ≠ backup compromise)
- Residual: Attacker with both filesystem access AND correct key = full access
  (equivalent to account compromise — outside scope for single-user local app)

**T2 — Prompt Injection**
- Threat: Malicious content in documents or user input influences memory writes
- Mitigations:
  - ConstitutionEnforcer at Validation Layer (not LLM judgment)
  - Memory writes never from LLM output alone — Observer → Validation required
  - Provider Gate enforced in code
- Residual: Session-level influence possible. Memory write without Validation: impossible.

**T3 — Corrupted Embeddings**
- Threat: Malicious document chunks influence retrieval
- Mitigations:
  - Local filesystem ingestion only
  - Similarity threshold gating
  - RAG output is read-only context (cannot write to profile)
- Residual: User deliberately ingesting malicious docs — out of scope

**T4 — Profile Tampering [UPDATED for SQLCipher]**
- Threat: Direct filesystem manipulation of database
- Mitigations:
  - Encrypted at rest — edits without key produce corruption, not valid data
  - PRAGMA foreign_keys = ON — referential violations rejected at DB level
  - constitution_version checked on every startup
  - Append-only contradiction logs provide tamper evidence
  - decision_text immutability enforced at DB level via BEFORE UPDATE trigger
    (`RAISE(ABORT, 'decision_text is write-once and cannot be modified')`)
- Gap closed: decision_text immutability trigger confirmed working in schema test
- Residual: Attacker with key = equivalent to full application access

**T5 — Accidental Cloud Leakage**
- Threat: Data sent to cloud without user knowledge
- Mitigations:
  - Stage 8 Provider Gate: HARD STOP if is_cloud AND (NOT user_consented OR revoked)
  - No silent fallback to cloud
  - Per-provider consent objects with scope control
- Residual: Zero if Provider Gate correctly implemented

**T6 — Observer Profile Corruption**
- Threat: Observer produces incorrect candidates that corrupt profile
- Mitigations:
  - Observer never writes directly
  - Multi-tier Validation Layer
  - Behavioral override requires reconciliation
  - 30-session verification loop provides external ground truth
- Residual: Slow drift if user never engages with verification prompts

---

# PART 11 — STORAGE ARCHITECTURE [FINALIZED after 5 review rounds + empirical testing]

## 11.1 Storage Technology Decisions

| Data | Storage | Reason |
|---|---|---|
| User profile (all memory types) | SQLite via SQLCipher | Encrypted, relational, atomic, auditable |
| Decision log | SQLite via SQLCipher | Same — queryable by state, project, FTS5 |
| Provider consent | SQLite via SQLCipher | Auditable, durable |
| Trace log | JSON (logs/trace_log.json) | **Corrected 2026-08-17**: this row previously said SQLite, contradicting both Part 17's folder structure (which already correctly documented `trace_log.json`) and the actual `core/trace.py` implementation, shipped and tested since Phase 1. A `trace_log` table exists in `schema.sql` (table 15) but is unused dead weight, not the real write path — not removed here since that's a separate storage-migration decision, out of scope for a doc correction. Trace data isn't user-facing memory (no confidentiality/atomicity requirement the other SQLite tables have), so plain JSON matching the pipeline's own per-message append pattern is defensible as-is. |
| Pending candidates | SQLite via SQLCipher | Durable across session close |
| Session continuity | JSON (session_snapshot.json) | Single overwritten object, ~5ms load |
| Constitutional rules | JSON (constitutional.json) | Human-readable config, not transactional |
| Application settings | JSON (settings.json) | Human-editable config |
| Document embeddings | ChromaDB | RAG index only — derived, rebuildable |

**ChromaDB is NEVER authoritative.** If ChromaDB drifts from SQLite, rebuild from SQLite
at startup. ChromaDB down = RAG unavailable, system continues normally without it.

## 11.2 Storage Ownership Table [LOCKED]

One module owns each resource. All others are callers, never raw SQL writers.
ADR-025 pre-commit hook enforces this.

| Table(s) | Owner Module | Callers |
|---|---|---|
| `skill_memory`, `skill_contradiction_log` | `memory/profile_store.py` | Stage 13 |
| `preference_memory`, `preference_contradiction_log` | `memory/profile_store.py` | Stage 13 |
| `goal_memory` | `memory/profile_store.py` | Stage 13 |
| `interaction_style`, `interaction_style_history` | `memory/profile_store.py` | Stage 13 |
| `identity`, `profile_meta`, `active_projects` | `memory/profile_store.py` | Onboarding, Stage 13 |
| `decision_log`, `decision_fts` | `memory/decision_log.py` | Stage 3 (read), Stage 13 (write) |
| `decision_candidates_pending` | `memory/candidate_store.py` | Stage 11 Observer (create), decision_log.py (/pending cmds) |
| `memory_candidates_pending` | `memory/candidate_store.py` | Stage 12 (create), Stage 13 (resolve) |
| `provider_consent` | `memory/profile_store.py` | Stage 8 Provider Gate (read) |
| `trace_log` | `core/trace.py` | All stages (write) |
| `topic_interests`, `preferred_tools`, `document_access_patterns` | `memory/profile_store.py` | Stage 11 Observer (write, Phase 7+) |
| ChromaDB | `memory/vector_store.py` | Stage 5 RAG (read), /ingest (write) |
| `documents` | `memory/vector_store.py` | Stage 5 (indirect, via ChromaDB), /ingest /documents /remove (write); source-of-truth registry for ChromaDB rebuild-on-drift |
| `pending_observer` | `memory/pending_observer.py` | Stage 11 Observer (enqueue, Phase 7+), startup drain (before Stage 0) |
| `session_snapshot.json` | `memory/session_snapshot.py` | Stage 0 (read), Stage 11 (write) |
| `constitutional.json` | Read-only after creation | ConstitutionEnforcer |
| `settings.json` | Read-only at runtime | `config/settings.py` canonical loader |

## 11.3 Complete Schema Summary

21 tables, 7 views, 1 trigger (validated against real SQLCipher; `documents` added in Phase 6, `pending_observer` added by ADR-033, see below):

**Profile tables:**
- `profile_meta` — session count, version fields, first/last session dates
- `identity` — name, language, timezone (immutable, single-row via CHECK id=1)
- `skill_memory` — levels + generated confidence
- `skill_contradiction_log` — append-only FK to skill_memory.id
- `preference_memory` — values + generated confidence + behavioral_signal_count
- `preference_contradiction_log` — append-only FK to preference_memory.id
- `goal_memory` — confidence STORED (decay-managed), decay_flag, status
- `interaction_style` — single-row (CHECK id=1), generated confidence
- `interaction_style_history` — previous values on change
- `active_projects` — project_id (UUID4), name, description, status

**Decision tables:**
- `decision_log` — write-once decision_text (trigger enforces), state only mutable field
- `decision_fts` — FTS5 virtual table (decision_text, reasoning, alternatives_considered UNINDEXED decision_id)
- `decision_candidates_pending` — low-confidence candidates awaiting review

**Memory candidate pending:**
- `memory_candidates_pending` — gated memory candidates surviving session close

**System tables:**
- `provider_consent` — per-provider flags (user_consented + revoked separate)
- `trace_log` — status + error_detail columns, 3 indexes
- `pending_observer` (ADR-033) — crash-safety queue for Observer passes that can't
  finish before process exit. status: pending → processing → completed/failed.
  Drain query includes 'processing' rows, not just 'pending' — a row stuck in
  'processing' means a previous drain itself crashed, which must be retried, not
  ignored. Never hard-deleted (ADR-024).

**Knowledge layer:**
- `documents` (Phase 6) — SQLite source-of-truth registry for what's ingested into
  ChromaDB: file_path, content_hash (staleness detection), chunk_count, status.
  Not chunk text — ChromaDB holds that. Unique index on file_path where active.

**Observer-may-write (defined Phase 0, populated Phase 7):**
- `topic_interests`
- `preferred_tools`
- `document_access_patterns`

**Soft-delete views (query through these, never base tables):**
- `active_skills`, `active_preferences`, `active_goals`
- `active_topics`, `active_tools`, `active_document_patterns`, `active_documents`

**Critical schema design decisions:**

| Decision | What | Why |
|---|---|---|
| confidence GENERATED | skill/preference/interaction_style | Prevents sync bugs between evidence_count and confidence |
| goal_memory.confidence STORED | goal_memory only | Decay adjusts confidence independently of evidence_count |
| CHECK(id=1) on identity and interaction_style | Single-row enforcement | DB-level, not convention |
| INSERT OR REPLACE for single-row tables | All writes to identity/interaction_style | The only safe write pattern |
| Surrogate id on skill/preference (not name) | FK targets | String PKs create join drift |
| decision_text BEFORE UPDATE trigger | decision_log | DB-level write-once enforcement |
| alternatives_considered preprocessed to space-separated | FTS5 insert | Raw JSON tokenizes as JSON not content |
| profile_age_weeks NOT stored | profile_meta | Computed from first_session_date at call time |
| FTS5 fallback = LIKE inside encrypted DB | If FTS5 unavailable | Unencrypted shadow index violates T1 |
| decision_candidates_pending ORDER BY confidence ASC, created_at ASC | Surface order | Low-evidence oldest = most likely wrong |
| documents stores metadata only, not chunk text | documents table | ChromaDB is the only place chunk text lives - keeps the split clean (SQLite = registry, Chroma = index) |
| ingest_document() force= param | vector_store.py | Hash-match shortcut would silently no-op during a rebuild-from-drift, which exists specifically to fix cases where the file didn't change but ChromaDB did |

---

# PART 12 — OBSERVER ARCHITECTURE

## 12.1 Non-Negotiable Rules

```
Rule 1: Labels candidates explicit or inferred. NEVER assigns confidence scores.
Rule 2: Produces candidates only. NEVER writes to any store directly.
Rule 3: Runs at session end only (10-min idle OR process exit). NEVER per-message.
Rule 4: Uses llama3.1:8b, same model as generation (ADR-033, supersedes B1).
        MUST be pinned to a LOCAL provider — never inherits the active
        generation provider, even though v1.0 being local-only currently
        makes this structurally moot.
Rule 5: Does NOT detect document-decision conflicts. That is Stage 5's job.
```

## 12.2 Extraction Prompt Structure

```
SYSTEM:
  You are an information extraction assistant. Your only job is to analyze
  a conversation and extract structured signals from it.
  Produce valid JSON only. No commentary. No explanation.

RULES:
  - Label each candidate "explicit" if user directly stated it.
  - Label "inferred" if you observed it from behavior.
  - Do NOT assign confidence scores. Label type only.
  - Do NOT create fields outside the approved list.
  - Do NOT include emotional state, mood, or psychological signals.
  - If uncertain, omit. Never guess.

APPROVED MEMORY FIELDS (target_table: [field_name, ...]):
  skill_memory: [python_level, docker_level, ...]
  preference_memory: [preferred_tools, answer_style, ...]
  goal_memory: [active_goals, project_objectives]
  observer_writable: [topic_interests, preferred_tools, document_access_patterns]  # NOTE: Must exactly match Part 9.1 observer_may_write.fields list

OUTPUT FORMAT:
{
  "memory_candidates": [
    {
      "target_table": "preference_memory",
      "field_name": "preferred_tools",
      "proposed_value": "Neovim",
      "label": "explicit",
      "evidence_count": 1,
      "evidence_text": "the exact quote or paraphrase this was drawn from"
    }
  ],
  "decision_candidates": [
    {
      "decision_text": "one sentence stating the decision",
      "signals_found": ["explicit_reasoning_in_conversation", "commitment_language", "alternative_considered"],
      "raw_quote": "the exact quote this was drawn from"
    }
  ],
  "session_snapshot": {
    "topic": "one sentence",
    "open_problems": [],
    "last_decisions": [],
    "suggested_next_step": "one concrete next action"
  }
}
```

**Found by ADR-033's A/B test, not by inspection:** earlier versions of this spec never told the model to emit `target_table`, matching the exact key names `MemoryCandidate` (Part 9.2/`types.py`) requires. Neither `phi3:mini` nor `llama3.1:8b` produced schema-correct output against the old prompt — `phi3:mini` failed structurally (echoed the field-name list instead of populating candidates), `llama3.1:8b` produced real candidates but with different key names (`field`/`value`/`type` instead of `field_name`/`proposed_value`/`label`). Neither output would have parsed into Stage 12 as written. The `memory_candidates` example above is now explicit about every key Stage 12/13 actually consume.

Refine this prompt after first 50 real sessions with real data. Never fine-tune
Observer speculatively.

---

# PART 13 — PROVIDER ARCHITECTURE

## 13.1 BaseLLMProvider Interface

**Sync vs Async Integration Plan**: The `chat()` generator strictly yields synchronously (`Iterator[str]`). When integrated with the asynchronous FastAPI server layer in Stage 9 (Phase 8), calls to `chat()` will be wrapped inside `asyncio.to_thread` or `run_in_threadpool` at the call site. This isolates blocking HTTP calls from the main event loop while retaining a simpler sync interface for local non-server CLI use.

```python
from abc import ABC, abstractmethod
from typing import Iterator, Optional

class BaseLLMProvider(ABC):

    @abstractmethod
    def chat(
        self,
        messages: list[dict],
        context: Optional[str] = None,
        max_tokens: int = 2000,
        timeout_seconds: int = 30
    ) -> Iterator[str]:
        """
        Stream response tokens one by one.
        messages: list of {role: str, content: str}
        Yields: str — one token or word fragment at a time
        Raises: ProviderUnavailableError, ProviderTimeoutError
        Contract: Must yield at least one token or raise.
                  Must not return None.
                  Must not buffer all tokens before yielding.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if provider can accept requests.
        Must complete within 2 seconds. Must not raise."""

    @abstractmethod
    def get_model_info(self) -> dict:
        """Returns: {model_name, context_window, is_local, provider_id}
        Must not make network calls."""

class ProviderUnavailableError(Exception): pass
class ProviderTimeoutError(Exception): pass
```

## 13.2 Provider Consent Schema

```
provider_id    TEXT    (ollama, groq, openai, claude)
is_cloud       INTEGER (0=local, 1=cloud)
user_consented INTEGER (0=never consented, 1=consented)
consent_date   TEXT    (ISO 8601)
revoked        INTEGER (0=not revoked, 1=revoked)
revoked_date   TEXT    (ISO 8601)
consent_scope  TEXT    (full_inference|web_search_only|embedding_only|none)
```

Stage 8 gate logic: `if is_cloud AND (NOT user_consented OR revoked) → HARD STOP`

"Never consented" and "consented then revoked" are distinct states — both blocked by
the gate, but distinguishable in the audit trail and in `/providers` display.

## 13.3 Model Loading (formerly "Model-Swap Constraints" — RETIRED by ADR-033)

Observer and generation both run llama3.1:8b (ADR-033, supersedes B1). There is no
second model to swap to, no VRAM-overrun window, and no forced cold reload at the
Observer/generation boundary — both roles share the same resident weights.

- `model_loading: true` stage_hint still applies, but only for a genuine cold load
  (e.g. Ollama's `keep_alive` evicted the model after enough idle time). Same UX
  problem as before (a silent wait reads as a hang), narrower cause.
- Real timing data (ADR-033 A/B test, 2026-08-16, cold-load included, n=1 transcript):
  phi3:mini 58.05s, llama3.1:8b 130.92s. Both exceed the (never-validated) 30s
  `observer_max_seconds` target — corrected in settings.json.
- `pending_observer` crash-safety mechanism (ADR-033 condition 2) is now required
  before Phase 7 ships: an 8B pass this long cannot block SIGINT/SIGTERM.

---

# PART 14 — FRONTEND AND CLIENT ARCHITECTURE [LOCKED]

## 14.1 Client Build Order

```
Phase 2:  Thin Python CLI client
          Calls local REST API only
          Exercises all /decide, /profile, /pending, /decisions commands
          Proves REST CRUD surface before web client exists

Phase 8:  Web client (HTML/JS first)
          Must be proven before Flutter starts
          Exercises both REST (CRUD) and WebSocket (chat)

Weeks 3-4: Throwaway Flutter spike (2–3 days)
            Connects to fake echo WebSocket server
            Renders streamed tokens in Dart
            Tests async stream handling
            DISCARDED after — de-risks Dart before Phase 8

Phase 8+: Flutter client (second real client)
           Built after web client is proven
           Shares the same API surface
```

## 14.2 Transport Split [LOCKED]

```
WebSocket (/ws/chat):   ALL chat interactions (streaming required)
REST (all other):       CRUD only (/decision, /memory, /provider, /trace, /project)

REST /chat is DROPPED entirely.
Maintaining two streaming code paths (REST + WS) doubles surface area.
One streaming path (WS) proven, then reused for Flutter.
```

## 14.3 WebSocket Message Spec (manual — FastAPI does not auto-document WS)

```
Event types (server → client):
  { "type": "token",       "data": "word or fragment" }
  { "type": "stage_hint",  "data": {
      "decision_log_hit": bool,
      "web_search_used":  bool,
      "cache_hit":        bool,
      "model_loading":    bool   ← true when llama3.1:8b needs a cold load (ADR-033)
  }}
  { "type": "error",       "data": "error message string" }
  { "type": "done",        "data": null }
```

Right sidebar in web/Flutter UI shows stage_hints. Ships as static display (populated
once response completes). Live animated per-stage updates are optional polish, not budgeted.

## 14.4 UI Philosophy

Frontend has zero intelligence. All logic in PIP Core backend.
Client always goes through POST/WS to PIP Core.
Client never talks directly to DB, ChromaDB, or Ollama.

---

# PART 15 — API SPECIFICATION

## 15.1 Base URL

`http://localhost:8765/api/v1` (Phase 2+, local only)

## 15.2 Endpoints

```
CHAT (WebSocket only — no REST /chat)
  WS     /ws/chat

MEMORY
  GET    /memory/profile
  GET    /memory/profile/{field}
  POST   /memory/correct          {field, value}
  DELETE /memory/profile/{field}
  POST   /memory/reset            {confirm, backup_path}
  POST   /memory/verify           {field_id, confirmed, corrected_value?}

DECISION LOG
  POST   /decision/create         {text, reasoning?, alternatives?, project_id?}
  GET    /decision/search         ?q=&state=active&project_id=
  PATCH  /decision/{id}/state     {state, reason, superseded_by?}
  GET    /decision/pending
  POST   /decision/pending/{id}/promote
  POST   /decision/pending/{id}/dismiss

PROJECTS
  GET    /projects
  POST   /projects                {name, description}
  PATCH  /projects/{id}/status    {status}
  POST   /projects/{id}/activate

RAG
  POST   /rag/ingest              {file_path, project_id}
  POST   /rag/query               {query, project_id, threshold?}
  GET    /rag/documents
  DELETE /rag/documents/{ref}

PROVIDERS
  GET    /providers
  POST   /providers/{id}/consent  {consent_scope}
  DELETE /providers/{id}/consent

OBSERVER CANDIDATES
  GET    /observer/candidates
  POST   /observer/candidates/{id}/approve
  POST   /observer/candidates/{id}/reject

TRACE
  GET    /trace/{trace_id}
  GET    /trace/recent            ?limit=20
  DELETE /trace                   ?older_than_days=90

SYSTEM
  GET    /status
```

---

# PART 16 — ALL ARCHITECTURAL DECISION RECORDS (ADRs)

Format: **Decision | Problem | Chosen | Reason | Consequences**

---

**ADR-001 — Gap Detector as Stage 0**
Decision: Gap Detector before Intent Classifier, not inside Stage 7.
Problem: Gap affects entire pipeline behavior, not just context injection. A 10-day gap
changes routing assumptions.
Chosen: Stage 0, non-negotiable.
Consequences: (+) Gap correctly shapes all downstream behavior. (−) Adds 5–10ms.

**ADR-002 — Router as Priority-Orderer, Not Stage-Skipper**
Decision: Router sets retrieval priority order. General knowledge still gets a lightweight
title-only embedding pre-check (separate from skip_rag mechanism).
Problem: Skipping RAG entirely for general knowledge creates project context blind spot.
Consequences: (+) No missed project context. (−) Slight latency increase vs full skip.

**ADR-003 — Observer Fires at Session End Only**
Decision: Single pass at 10-min idle or process exit.
Problem: Per-message Observer burns RAM, produces noisy candidates.
Consequences: (+) Zero impact on response speed. (−) Profile updates at session end only.

**ADR-004 — Observer Never Writes Directly to Memory**
Decision: Candidates only. Validation + user confirmation required.
Consequences: (+) Observer cannot corrupt without Validation approval.

**ADR-005 — Observer Never Self-Scores Confidence**
Decision: Observer labels explicit/inferred only. Validation computes confidence.
Problem: Self-scoring is circular.
Consequences: (+) Confidence reproducible and auditable.

**ADR-006 — Decision Log Write Path is Manual-Only in Phase 1**
Decision: /decide command is the only write path until Phase 7.
Problem: Automating without real examples produces garbage.
Consequences: (+) Log starts with trusted, high-quality entries.

**ADR-007 — Decision Classification Uses OR Logic**
Decision: Any signal qualifies. Confidence weighted by signal count.
Problem: AND logic rejects most real decisions.
Consequences: (+) Captures realistic decision patterns.

**ADR-008 — Provider Gate at Stage 8 (Before LLM, After Assembly)**
Decision: Gate after Context Assembly, before LLM call.
Problem: Gate earlier means Assembly doesn't know target provider.
Consequences: (+) Context assembled correctly for target. (−) Assembly done before gate.

**ADR-009 — Provider Consent is Per-Provider Object**
Decision: Per-provider object with consent_scope, not global boolean.
Problem: Global flag cannot represent nuanced consent.
Consequences: (+) User can grant narrow consent without full exposure.

**ADR-010 — Ephemeral Consent Tokens Rejected**
Decision: Static per-provider flag with revoke command.
Problem: Ephemeral tokens solve multi-user web app problems — wrong scale.
Consequences: (+) Simple, inspectable consent config.

**ADR-011 — Constitutional Rules Built Before Observer**
Decision: constitutional.json + ConstitutionEnforcer tested first.
Problem: Without rules, all downstream components have no boundaries.
Consequences: (+) Everything downstream built against testable rules.
Note: This is the ONE hard technical dependency. Everything else is value-ordered.

**ADR-012 — interaction_style Is Gated, Not Immutable**
Decision: interaction_style in gated_fields, not immutable_fields.
Problem: Immutable prevents adapting to genuine preference evolution.
Consequences: (+) System adapts to real communication style evolution with confirmation.

**ADR-013 — Document-Decision Conflict Detection in Stage 5**
Decision: Conflict check in Stage 5 RAG, not Observer.
Problem: Post-session detection means user learns after moving on.
Consequences: (+) Conflict surfaces during session while context is live.

**ADR-014 — Proactive Triggers Are Deterministic Only**
Decision: Fire ONLY when specific coded conditions are met.
Allowed: session_gap > 48h, conflict_detected, goal_inactive > 14 days.
Forbidden: model judgment of relevance or urgency.
Consequences: (+) Proactive behavior auditable and predictable.

**ADR-015 — Scored Decision Graph Rejected**
Decision: Sequential pipeline with trace IDs.
Problem: Graph makes debugging harder — the very problem it claimed to solve.
Consequences: (+) Fully deterministic and traceable.

**ADR-016 — Two-Pass Retrieval Rejected**
Decision: Single pass with retrieval_hint from Intent Classifier.
Problem: Two-pass doubles latency on RTX 4060.
Consequences: (+) Pre-LLM latency within target.

**ADR-017 — Three-Way Memory Split**
Decision: skill_memory, preference_memory, goal_memory with separate validation.
Problem: One validation model cannot serve all three correctly.
Consequences: (+) Each type validated with appropriate criteria.

**ADR-018 — Validation Thresholds Tiered by Profile Age**
Decision: Thresholds increase as profile matures.
Problem: Fixed thresholds keep profile empty for weeks.
Consequences: (+) Profile accumulates from day one.

**ADR-019 — Intent Classifier Outputs skip_rag Flag**
Decision: skip_rag:bool added to Intent Classifier output.
Note: Two separate mechanisms — Mechanism 1 (keyword cache → skip_rag bool),
Mechanism 2 (ADR-002 embedding pre-check, runs regardless of skip_rag).
Consequences: (+) ~35ms saved per non-project query.

**ADR-020 — Observer Produces session_snapshot as Third Output**
Decision: Observer writes session_snapshot at session end.
Problem: On-demand reconstruction requires heavy work while user waits.
Consequences: (+) Long-gap return latency dramatically reduced (~5ms load).

**ADR-021 — Memory Source Trust Hierarchy**
Decision: User correction > Explicit stated > Repeated behavior > Single inference.
Problem: No rule for which source wins when sources conflict.
Consequences: (+) Explicit preferences always respected. (−) Slow adaptation to silent habit changes.

**ADR-022 — Decision Lifecycle States**
Decision: active | superseded | abandoned. Hard deletion NEVER permitted.
Problem: Old decisions appear equally authoritative without lifecycle state.
Consequences: (+) Log stays accurate as project evolves.

**ADR-023 — Cache Authority Hierarchy**
Decision: User correction > Decision Log > Profile > RAG > Web > Cache.
Problem: Cache silently serves stale content contradicting Decision Log.
Consequences: (+) Clear lookup order for debugging.

**ADR-024 — Memory Deletion Philosophy**
Decision: Profile = soft delete + archive. Decision Log = soft only (never hard delete).
Trace logs = hard delete permitted after 90 days on user request.
Full profile = reset with confirmation (irreversible without prior backup).

**ADR-025 — Dependency Rule (Clean Architecture)**
Decision: Pipeline stages and UI import ONLY interfaces in memory/ and providers/.
Direct imports of sqlite3, chromadb, ollama outside backend/memory and backend/providers
are banned. Enforced by pre-commit hook.
Consequence: One infra swap = update one module, not hunt through 14 stage files.

**ADR-026 — Storage: SQLCipher Whole-Database (supersedes all JSON/Fernet decisions)**
Decision: SQLite via SQLCipher for all structured data. No per-file Fernet. No plaintext
SQLite. ChromaDB is derived index only, never authoritative.
Problem: Plaintext SQLite was a privacy regression against Threat Model T1. Per-file
Fernet creates read-modify-write atomic issues at scale.
Consequences: (+) One encrypted unit. One connection sequence. No plaintext intermediate.

**ADR-027 — Backup Export via sqlcipher_export()**
Decision: /export uses ATTACH DATABASE + sqlcipher_export() with separate backup password.
Problem: Raw file copy misses WAL-resident data. Fernet re-wrap requires Fernet dependency.
Empirically verified: generated columns and WAL-resident data both survive correctly.
Consequences: (+) Encrypted-to-encrypted, no plaintext, separate passwords.

**ADR-028 — REST/WS Transport Split**
Decision: WS for chat only. REST for all CRUD. REST /chat dropped entirely.
Problem: Two streaming implementations for one feature doubles surface area.
Consequences: (+) One streaming implementation, proven twice (web then Flutter).

---

**ADR-032 - TICKET-012 Crash Safety via SQLite/SQLCipher Transactions**
TICKET-012's original 'write-ahead buffer for crash safety' language is superseded. profile_store.py implements no application-level write-ahead buffer. Crash safety is provided by SQLite/SQLCipher transactional atomicity (rollback on interrupted commit) combined with WAL mode, per the locked connection sequence in profile_store.get_connection(). This was proven by test_profile_write_interrupted_before_commit_reopens_with_prewrite_state. Rationale: SQLite's transactional guarantees make an application-level buffer redundant; adding one would be unjustified complexity for a guarantee already provided by the storage engine.

---

**ADR-033 — Observer Collapses Onto llama3.1:8b (Supersedes B1)**

Decision: Observer uses the same llama3.1:8b model as generation. There is no
longer a separate small model (phi3:mini) in the pipeline.

Problem: The original two-model design (phi3:mini for Observer, llama3.1:8b for
generation) required strict sequential VRAM swapping on an 8GB card (combined
~7.1–7.3GB, cannot coexist), an unmeasured model-swap benchmark sitting on the
critical path, and — discovered only by actually running it — a real quality
gap: phi3:mini's extraction output on a real prompt was not just weaker but
structurally broken (it echoed the approved-fields schema back as if it were a
candidate, producing zero usable memory_candidates and missing a decision with
two extractable signals that should have auto-logged per Part 8.7's OR-logic).

Chosen: Single local llama3.1:8b for both roles.

Reason: A/B test run 2026-08-16 (n=1 synthetic transcript — PIP has no real
production sessions yet; extraction prompt per Part 12.2, before this ADR's
prompt-schema fix). phi3:mini: 58.05s, memory_candidates unusable (wrong shape
entirely), decision_candidates empty (missed an extractable decision).
llama3.1:8b: 130.92s, 3 correctly-labeled memory_candidates (explicit/inferred
distinction correct), decision extraction still imperfect (miscategorized a
goal as a decision candidate) but structurally valid and parseable. The gate
rule ("if 8B is not clearly better, kill the decision") was met — the gap is
not marginal. Both timings include cold model load, not isolated inference;
re-benchmark warm once Phase 7 has real usage.

Two conditions carried over from the original proposal, now locked:
  1. Observer is pinned to a LOCAL provider — this is now the operative rule
     ("Observer is always local"), not the retired "Observer is always a small
     model." Currently structurally moot since v1.0 is confirmed local-only
     (no cloud generation provider exists in the call path to accidentally
     inherit), but must still be enforced explicitly at the Stage 8/Observer
     boundary when implemented, not left as an assumption.
  2. A `pending_observer` table + drain-on-startup mechanism is required before
     Phase 7 Observer code ships. An 8B pass (130.92s measured, likely 30-60s+
     even warm) cannot block SIGINT/SIGTERM that long. Transcript persists to
     SQLCipher (never a plain file), process exits immediately, drain runs
     before Stage 0 on next launch. This also closes the existing ADR-003 gap
     (unexpected process death during the Observer pass loses that session's
     learning) — a gap that technically existed under the two-model design too,
     just less urgently.

Consequences: (+) No VRAM-swap orchestration, no swap-window overrun risk on an
8GB card, no guaranteed cold reload at every session boundary, retires the
model-swap benchmark entirely. (−) Slower single Observer pass than phi3:mini
would have been; `observer_max_seconds` raised from an untested 30 to 180
pending a warm-run re-benchmark; `pending_observer` is new scope that must ship
before Phase 7. Also surfaced, independent of which model won: Part 12.2's
extraction prompt never specified the exact `MemoryCandidate` key names
(`target_table`, `field_name`, `proposed_value`) — fixed in this ADR's pass,
see Part 12.2.

Supersedes: B1 (Observer = phi3:mini, "always a small model" principle).

Updated by this ADR: Part 6.3, Part 7 Stage 11, Part 12.1 Rule 4, Part 12.2,
Part 13.3, Part 14.3 WS spec, Part 18 Phase 0 checklist, Part 19 settings.json
(`observer.model`, `observer_max_seconds`), Glossary `model_loading` entry.

---
# PART 17 — FOLDER STRUCTURE [FROZEN]

```
pip/
├── backend/
│   ├── api/
│   │   └── server.py                    (Phase 2)
│   ├── core/
│   │   ├── constitutional.json          ← FIRST FILE CREATED
│   │   ├── constitution_enforcer.py     ← SECOND FILE CREATED
│   │   ├── pipeline.py
│   │   ├── response_cache.py
│   │   ├── session_lifecycle.py         (Phase 8 - idle-timeout/disconnect/shutdown Observer triggering)
│   │   ├── trace.py
│   │   ├── schema.sql                   ← FINALIZED (already written)
│   │   └── types.py                     ← STARTED (TIMESTAMP_FORMAT etc.)
│   ├── stages/
│   │   ├── stage_00_gap_detector.py
│   │   ├── stage_01_intent_classifier.py
│   │   ├── stage_02_router.py
│   │   ├── stage_03_decision_log_lookup.py
│   │   ├── stage_04_memory_lookup.py
│   │   ├── stage_05_rag_retrieval.py
│   │   ├── stage_06_web_search.py
│   │   ├── stage_07_context_assembly.py
│   │   ├── stage_08_provider_gate.py
│   │   ├── stage_09_llm_streaming.py
│   │   ├── stage_10_response_delivery.py
│   │   ├── stage_11_observer.py
│   │   ├── stage_12_validation_layer.py
│   │   └── stage_13_profile_update.py
│   ├── memory/
│   │   ├── profile_store.py             ← get_connection() lives here
│   │   ├── decision_log.py
│   │   ├── candidate_store.py           ← owns both pending tables
│   │   ├── vector_store.py
│   │   └── session_snapshot.py
│   ├── providers/
│   │   ├── base_provider.py
│   │   ├── ollama_provider.py
│   │   ├── llamacpp_provider.py
│   │   ├── groq_provider.py
│   │   ├── openai_provider.py
│   │   └── claude_provider.py
│   ├── observer/
│   │   └── extractor.py
│   ├── config/
│   │   ├── settings.json               ← TO BE WRITTEN (Phase 0)
│   │   └── settings.py                 ← canonical loader (Phase 0)
│   ├── logs/
│   │   ├── trace_log.json              (written by trace.py)
│   │   └── startup_log.json            (FTS5 availability cached here)
│   └── tests/
│       ├── test_constitution_enforcer.py
│       ├── test_schema.py              (FTS5 roundtrip, wrong-key)
│       ├── test_stages/
│       ├── test_integration.py
│       └── test_observer_accuracy.py
├── frontend/
│   ├── web/                            (Phase 8 — built first)
│   └── flutter/                        (Phase 8+ — after web proven)
├── shared/
│   ├── models.py                       (Pydantic models)
│   └── ws_spec.py                      (WS message type definitions)
├── data/
│   ├── pip.db                          (SQLCipher database)
│   ├── salt.bin                        (KDF salt — not secret)
│   └── session_snapshot.json           (Observer output, ~5ms load)
├── scripts/
│   └── pre-commit                      (ADR-025 enforcement hook)
├── docs/
├── requirements.txt
└── .env.example                        (PIP_DEV_KEY for dev only)
```

**Rules:**
- No stage file imports sqlite3, chromadb, or ollama directly (pre-commit enforced)
- Each data file has exactly one owner module
- All modules import from config/settings.py, never do their own json.load()
- session_snapshot.json is the only JSON data file (not config)

---

# PART 18 — PHASE ROADMAP

| Phase | What | Time | Git Tag | Notes |
|---|---|---|---|---|
| 0 | Project setup + schema + config skeleton | 2–3 days | v0.0 | No code, only infrastructure |
| 1 | Constitutional Core | 1 week | v0.1 | First real code |
| 2 | Onboarding + Decision Log + Profile | 1 week | v0.2 | First user-facing features |
| 3 | Provider Layer + Provider Gate | 1 week | v0.3 | Privacy guarantee in code |
| 4 | Gap Detector + Session Snapshot | 3–4 days | v0.4 | Session continuity |
| 5 | Validation Layer + Memory Protection | 1 week | v0.5 | ← ACADEMIC MINIMUM |
| 6 | RAG + Parallel Retrieval | 1.5 weeks | v0.6 | |
| 7 | Observer | 2 weeks | v0.7 | Largest single phase |
| 8 | Full Pipeline Integration + Web + Flutter spike | 1.5 weeks | v0.8–v0.9 | |
| 9 | Integration Testing + Debug | 1 week | v1.0 | |
| 10 | Documentation + Final Report | 4 weeks | — | Can overlap Phase 8–9 |
| **Total** | | **~17 weeks** | | |

**Self-imposed target:** v1.0 with both clients by week 20–22. Weeks 22–24+ = genuine buffer.

## Phase 0 Specific Tasks [IMMEDIATE]

```
[ ] git init, create dev and main branches
[ ] Python venv (Python 3.11+)
[ ] Install: sqlcipher3-binary, chromadb, sentence-transformers,
             cryptography, pytest, asyncio, fastapi, ollama
[ ] Create full folder skeleton
[ ] Copy backend/core/schema.sql (already written, finalized)
[ ] Write backend/core/constitutional.json
[ ] Write backend/config/settings.json (ALL keys including
    log_threshold_manual=0.4 and log_threshold_observer=0.7
    with activation comment for Phase 7)
[ ] Write backend/config/settings.py (canonical loader)
[ ] Deploy scripts/pre-commit hook (after git init)
    chmod +x .git/hooks/pre-commit
[ ] Write FTS5-in-SQLCipher roundtrip test:
    open encrypted DB → create FTS5 virtual table → insert →
    MATCH query → assert non-empty result
[ ] Write SQLCipher wrong-key test:
    wrong key → SELECT count(*) FROM sqlite_master → must fail loudly
[x] Verify Ollama running locally, pull phi3:mini and llama3.1:8b — done during
    Phase 5 environment recovery + ADR-033 A/B test (2026-08-16)
[x] requirements.txt committed — done during Phase 5 environment recovery
    (see commit c558893; sqlcipher3-binary is gone from PyPI, corrected to sqlcipher3)
[x] Model-swap benchmark — RETIRED by ADR-033. No swap exists to benchmark since
    Observer and generation now share llama3.1:8b. See ADR-033 for the A/B timing
    data that replaced this item (58.05s vs 130.92s, cold-load included).
[ ] First commit: v0.0 tag (folder skeleton only)
```

**Phase 0 comment skeleton tasks (zero implementation, high architectural value):**
```
[ ] Two-line comment in stage_01_intent_classifier.py distinguishing
    Mechanism 1 (skip_rag flag) from Mechanism 2 (ADR-002 safety net)
[ ] Comment in vector_store.py: startup rebuild-on-mismatch trigger
[ ] Comment in decision_log.py schema:
    active_projects → direct DB query, no cache
    decision_text → write-once, state is only mutable field
```

## Phase 1 Specific Tasks (Constitutional Core)

```
[x] TICKET-001: backend/core/constitutional.json (exact spec from Part 9.1)
[x] TICKET-002: backend/core/constitution_enforcer.py (full class)
[x] TICKET-003: Tests - immutable field HARD_REJECT (name, language, timezone)
[x] TICKET-004: Tests - gated field REQUIRES_CONFIRMATION (all 4 gated fields)
[x] TICKET-005: Tests - tiered thresholds
    Week 1 explicit -> APPROVED
    Week 1 inferred -> DISCARD
    Month 2 evidence=2 -> DISCARD
    Month 2 evidence=3 confidence=0.75 -> APPROVED
[x] TICKET-006: Tests - behavioral override
    explicit/user_verified/user_correction source + behavioral_signal_count >= 3 + first_contradiction_date >= 14 days -> PROMPT_RECONCILIATION
[x] TICKET-007: backend/core/trace.py
    generate_trace_id() works
    stage_log() appends valid JSON to trace_log
    mock pipeline run produces readable full trace
Exit condition: COMPLETE - ConstitutionEnforcer tests pass. Trace ID logged for mock run.
```

---

# PART 19 — SETTINGS.JSON COMPLETE REFERENCE

All tunable values. These are NOT ADRs. Change by measurement, not opinion.

```json
{
  "observer": {
    "idle_timeout_minutes": 10,
    "model": "llama3.1:8b",
    "max_session_tokens": 8000
  },
  "rag": {
    "similarity_threshold": 0.6,
    "chunk_size_tokens": 500,
    "chunk_overlap_tokens": 50,
    "top_k_results": 3,
    "max_document_size_mb": 50,
    "supported_extensions": [".pdf", ".md", ".txt", ".py", ".json", ".html"]
  },
  "cache": {
    "ttl_general_knowledge_seconds": 86400,
    "ttl_technical_explanation_seconds": 86400,
    "ttl_web_search_seconds": 3600,
    "ttl_project_question_seconds": 0,
    "ttl_personal_question_seconds": 0,
    "ttl_decision_lookup_seconds": 0
  },
  "memory": {
    "goal_decay_inactive_days": 14,
    "behavioral_override_sessions": 3,
    "behavioral_override_days": 14,
    "verification_loop_frequency_sessions": 30,
    "verification_loop_sample_size": 3
  },
  "decision_log": {
    "log_threshold_manual": 0.4,
    "log_threshold_observer": 0.7
    // log_threshold_observer is INACTIVE until Phase 7 (Observer ships).
    // Single-signal Observer detections route to decision_candidates_pending
    // rather than auto-logging. Do not activate ad-hoc — it activates
    // automatically when Observer is built in Phase 7.
  },
  "pipeline": {
    "context_token_budget": 6000,
    "system_instructions_tokens": 150,
    "user_profile_tokens": 400,
    "session_snapshot_tokens": 250,
    "decision_log_tokens": 600,
    "rag_chunks_tokens": 800,
    "web_search_tokens": 800,
    "conversation_history_tokens": 1000,
    "user_message_tokens": 400,
    "response_reserved_tokens": 2000
  },
  "proactive": {
    "session_gap_trigger_hours": 48,
    "goal_inactive_trigger_days": 14
  },
  "trace": {
    "hard_delete_after_days": 90,
    "db_table": "trace_log"
  },
  "web_search": {
    "provider": "duckduckgo",
    "result_limit": 3,
    "timeout_seconds": 10
  },
  "database": {
    "kdf_algorithm": "PBKDF2_HMAC_SHA512",
    "kdf_iterations": 256000,
    "fts5_fallback": "LIKE"
  },
  "performance_targets": {
    "stage_0_ms": 10,
    "stage_1_ms": 30,
    "stage_2_ms": 15,
    "stages_3_5_parallel_ms": 80,
    "stage_7_ms": 50,
    "observer_max_seconds": 180,
    "snapshot_load_ms": 5,
    "cache_hit_ms": 100,
    "simple_query_total_seconds": 2,
    "complex_query_total_seconds": 5
  }
}
```

**`observer.model` and `observer_max_seconds` note:** updated by ADR-033 (supersedes B1).
`observer_max_seconds` was raised from the never-validated 30 to 180, based on a measured
130.92s llama3.1:8b pass (ADR-033 A/B test, cold-load included, n=1 transcript) plus headroom.
This should be re-benchmarked warm (model already resident) once Phase 7 has real usage —
180 is a safe starting ceiling, not a tuned steady-state number.

**config/settings.py canonical loader (single source of truth for all config values):**
```python
import json
from pathlib import Path

_settings = None

def get_settings() -> dict:
    global _settings
    if _settings is None:
        settings_path = Path(__file__).parent / "settings.json"
        with open(settings_path) as f:
            _settings = json.load(f)
    return _settings
```

All modules call `get_settings()["section"]["key"]`. No module does its own `json.load()`.

---

# PART 20 — FINALIZATION STATUS

## Locked and Implemented (files exist, tested)

| Item | Status |
|---|---|
| backend/core/schema.sql | DONE — 5 rounds review + empirical SQLCipher test |
| backend/core/types.py | DONE — TIMESTAMP_FORMAT, now_utc(), base TypedDicts |
| sqlcipher_export() + generated columns | EMPIRICALLY VERIFIED (two sandboxes) |
| WAL-resident data + sqlcipher_export() | EMPIRICALLY VERIFIED |
| KDF: PBKDF2_HMAC_SHA512, 256k iterations | EMPIRICALLY VERIFIED (two sandboxes) |
| decision_text immutability trigger | DONE — tested in schema validation |
| ADRs 001–028 | LOCKED |
| All schema design decisions | LOCKED |
| v0.5 / v1.0 success statements | LOCKED |
| Storage ownership table | LOCKED |
| Connection 4-PRAGMA sequence | LOCKED |
| FTS5 fallback decision (LIKE, never shadow index) | LOCKED |
| Backup export mechanism (sqlcipher_export) | LOCKED + EMPIRICALLY VERIFIED |
| master-key-at-rest model | LOCKED |
| Transport split (WS chat, REST CRUD) | LOCKED |
| Phase 2 CLI execution model | LOCKED |
| model_loading WS stage_hint | LOCKED |
| decision_candidates_pending sort order | LOCKED (confidence ASC, created_at ASC) |
| Tool Execution Layer: deferred post-v1.0 | LOCKED |
| Folder structure | FROZEN |
| Pre-commit hook script | DRAFTED (not deployed - git not initialized yet) |
| Phase 1 constitutional core | DONE - TICKET-001 through TICKET-007 accepted |
| backend/core/constitutional.json | DONE - Phase 1 accepted |
| backend/core/constitution_enforcer.py | DONE - validated existing_field contract, table-level observer allowlist, fnmatch gated patterns, behavioral override before thresholds |
| backend/core/trace.py | DONE - trace ID generation and JSON stage logging tested |
| Phase 1 pytest run | PASS - 27 passed, 1 skipped (SQLCipher-dependent wrong-key test skipped because SQLCipher is not installed in current test environment) |
| Phase 2 /decide decision log | DONE - `backend/tests/test_decision_log.py::test_decision_confidence_uses_or_logic` and `backend/tests/test_decision_log.py::test_manual_decide_logs_with_any_one_signal` passing |
| Phase 2 /profile display | DONE - `backend/tests/test_profile_store.py::test_profile_view_includes_confidence_and_source_label` passing |
| Phase 2 decision_text immutability | DONE - `backend/tests/test_decision_log.py::test_decision_text_is_write_once` passing |
| Phase 2 onboarding encrypted profile | NOT COMPLETE - `backend/tests/test_profile_store.py::test_onboarding_writes_identity_profile_and_completion_flag` verifies profile writes, but encrypted-profile behavior is unverified because `backend/tests/test_schema.py::test_wrong_key_behavior` is skipped without SQLCipher |
| Phase 2 crash survival | DONE - `backend/tests/test_profile_store.py::test_profile_write_interrupted_before_commit_reopens_with_prewrite_state` passing; interrupted profile write rolls back to pre-write state on reopen |
| Phase 3 Ticket 1 — BaseLLMProvider ABC | DONE — `backend/providers/base_provider.py`; `ProviderExecutionError`, `ProviderUnavailableError` custom exceptions; tested in `test_base_provider.py` |
| Phase 3 Ticket 2 — OllamaProvider | DONE — `backend/providers/ollama_provider.py`; urllib-only, no extra deps; HTTPError 404 raises descriptive message; tested in `test_ollama_provider.py` |
| Phase 3 Ticket 3 — provider_consent.json seed data | DONE — `config/provider_consent.json` restructured as plain seed array (no JSON Schema wrapper); locked by `test_no_schema_key`, `test_no_examples_key`; ADR-030 web_search row exact-match tested |
| Phase 3 Ticket 4 — seed_provider_consent() + Stage 8 gate | DONE — `memory/profile_store.py::seed_provider_consent()` idempotent; called from `initialize_schema()`; `backend/stages/stage_08_provider_gate.py` fail-closed (unknown provider = hard stop); scope enforcement; revoked overrides consented; 15 tests passing |
| Phase 3 Ticket 4 — DB migration (pre-Phase-3 DBs) | DONE — `scripts/migrate_seed_provider_consent.py`; local dev DB `data/pip.db` migrated: 0→2 rows confirmed; idempotency confirmed; documented in Phase 3 DB Migration Note section |
| Phase 3 Ticket 5 — /providers /consent /revoke | DONE — `api_list_providers`, `api_grant_consent` (scope-validated before DB write), `api_revoke_consent` in `backend/api/server.py`; CLI commands `_providers`, `_consent`, `_revoke` in `frontend/cli/pip_cli.py`; 16 tests passing including 2 end-to-end gate tests |
| Phase 3 full-suite post-merge | PASS — 81 passed, 1 skipped (SQLCipher) on main at `6f1efa5`, tag `v0.3` |

## Phase 3 Release — COMPLETE

| Field | Value |
|---|---|
| Tag | `v0.3` |
| Commit (main) | `6f1efa5` |
| Full hash | `6f1efa593b66c5f701f44a942cf62cb953903369` |
| Merge type | Squash merge from `phase-3-provider-layer` into `main` |
| Audit branch | `phase-3-provider-layer` (retained, ticket-by-ticket history: `6685d00` → `5a2aac0` → `3039300` → `90c67f0`) |
| Test result at tag | 81 passed, 1 skipped (pre-existing SQLCipher skip), 0 failed |
| Scope | Provider abstraction layer, OllamaProvider, consent seed data, Stage 8 gate (fail-closed), DB migration script, /providers /consent /revoke CLI+API |
| Phase 4 Tickets 1 & 2 — Gap Detector & session_snapshot.json | DONE — `backend/stages/stage_00_gap_detector.py` continuous boundary logic; fail-open confirmed. `backend/memory/session_snapshot.py` schema and load/write logic; fail-open on missing/corrupt confirmed; 5ms load budget tested. |
| Phase 4 full-suite post-merge | PASS — 97 passed, 1 skipped on main at `2583c4f`, tag `v0.4` |

## Phase 4 Release — COMPLETE

| Field | Value |
|---|---|
| Tag | `v0.4` |
| Commit (main) | `2583c4f` |
| Full hash | `2583c4f...` |
| Merge type | Squash merge from `phase-4-gap-detector` into `main` |
| Audit branch | `phase-4-gap-detector` (retained) |
| Test result at tag | 97 passed, 1 skipped (pre-existing SQLCipher skip), 0 failed |
| Scope | Stage 0 Gap Detector, session_snapshot.json read/write helpers, fail-open handling, deterministic continuous boundary resolution |

## Phase 5 Release — COMPLETE

| Field | Value |
|---|---|
| Tag | `v0.5` (academic minimum) |
| Commit (main) | `b2fc6df` |
| Test result at tag | 121 passed, 0 skipped, 0 failed — first fully-real run against SQLCipher (previous phases' suites ran against a silent plaintext-SQLite fallback; see environment-fix commit `c558893`) |
| Scope | Stage 12 Validation Layer wired to real DB state; `apply_verified_correction` (verified/corrected writes at max confidence); `memory_candidates_pending` schema fix (added `target_table`, `validation_status`, `state`); Stage 13 write orchestration (APPROVED writes now, gated/conflict/override candidates persist to pending, rejects write nothing) |
| Environment note | Dev environment had never run real SQLCipher before this phase: no `requirements.txt` existed, `sqlcipher3-binary` is gone from PyPI, and Python 3.14 (previously in use) has no compatible SQLCipher wheel at all. Rebuilt on Python 3.12 with the correctly-named `sqlcipher3` package. Two real bugs surfaced only once encryption actually ran: `sqlite3.Row` cannot wrap a `sqlcipher3` cursor, and `get_connection()` silently fell back to plaintext SQLite instead of failing loudly when SQLCipher was unavailable. Both fixed. |

## Phase 6 — COMPLETE (RAG + Parallel Retrieval)

| Item | Status |
|---|---|
| `documents` table (schema.sql) | DONE — SQLite source-of-truth registry for ChromaDB ingestion |
| `memory/vector_store.py` | DONE — ingest/query/delete/list/rebuild-from-drift, real ChromaDB + sentence-transformers (`all-MiniLM-L6-v2`, CPU-only), `.pdf`/`.md`/`.txt`/`.py`/`.json`/`.html` extraction, `max_document_size_mb` enforced |
| `backend/stages/stage_05_rag_retrieval.py` | DONE — threshold-filtered retrieval + lexical conflict-check heuristic against active Decision Log (fail-open per Part 7.4) |
| `/ingest`, `/documents`, `/remove` CLI commands | DONE — `frontend/cli/pip_cli.py` |
| `POST /rag/ingest`, `/rag/query`, `GET /rag/documents`, `DELETE /rag/documents/{ref}` REST endpoints | DONE — `backend/api/server.py`, confirmed registered on the real FastAPI app, not just business-logic functions in isolation |
| Known tradeoff | `all-MiniLM-L6-v2` max_seq_length is 256 tokens; `chunk_size_tokens` is 500. Chunks past ~256 tokens are truncated for embedding purposes only — full text is still stored/returned, only mid-chunk semantic search quality degrades. Same class of imprecision as `similarity_threshold` (already documented as "calibrate from real usage") |
| Conflict-check heuristic | Lexical overlap-coefficient between chunk and active decision keywords, not semantic contradiction detection — no LLM call in this stage. Flags "worth a human double-check," not a proven contradiction. Threshold (0.3) needs real-usage calibration same as `similarity_threshold` |
| `/remove`'s REST identifier | file_path itself (percent-encoded), not a separate document id — there is no document id in this schema |
| Test coverage | 21 tests (`test_vector_store.py`, `test_stage_05_rag_retrieval.py`, plus additions to `test_api_server.py`/`test_cli.py`), core engine tested against real ChromaDB + real embedding model, not mocks |
| Router (Stage 2) wiring to actually call Stage 5 during a live pipeline run | DONE — `core/pipeline.py` (Phase 8) calls Stage 5 unconditionally for every message, per ADR-002 |

## Phase 7 Prerequisite — DONE (ADR-033 condition 2)

| Item | Status |
|---|---|
| `pending_observer` table (schema.sql, table 21) | DONE — crash-safety queue, status: pending → processing → completed/failed, never hard-deleted |
| `memory/pending_observer.py` | DONE — `enqueue`, `list_pending`, `mark_processing/completed/failed`, `drain(conn, observer_runner)`. `drain()` takes the extraction function as a parameter rather than importing Stage 11 directly, keeping the queue decoupled from Stage 11's own implementation |
| Crash-recovery detail | `drain()` retries rows stuck in `'processing'`, not just `'pending'` — a stuck `'processing'` row means a previous drain itself crashed mid-run, which is exactly the case this table exists to survive |
| Test coverage | 8 tests, including one-failure-doesn't-block-the-rest and stale-processing-row recovery |
| Not built yet, correctly deferred | Actual SIGINT/SIGTERM signal handling and the "call drain() before Stage 0 at startup" wiring — both need a running server/process lifecycle that doesn't exist until Phase 8. This module is the tested primitive Phase 8 will call, not the process-lifecycle integration itself |

## Phase 7 — Observer (DONE — its two Phase-8-deferred rows below are now closed too)

| Item | Status |
|---|---|
| `backend/stages/stage_11_observer.py::run()` | DONE — single-pass extraction against `llama3.1:8b` via `BaseLLMProvider`. Enforces Rule 4 (raises `ObserverLocalProviderError` if given a non-local provider) and Rule 1 (only `explicit`/`inferred` labels survive sanitization; anything else, including a hallucinated confidence-bearing label, is dropped). Fails open on any LLM/parse failure per spec. |
| `run_session_end()` | DONE — full flow: extract → write `session_snapshot.json` immediately → route each memory candidate through Stage 12 (validate) + Stage 13 (write) → route each decision candidate through `decision_log.route_observer_decision()` |
| `decision_log.route_observer_decision()` | DONE (new) — Part 8.7's Observer path: signals come from the LLM's own reading of the conversation (not keyword-matched, unlike the manual `/decide` path), but confidence is still always computed deterministically via `score_confidence()`, never assigned by the model (ADR-005). Unknown/hallucinated signal names are filtered before scoring. |
| `session_snapshot.py` schema fix | Its `SessionSnapshot` TypedDict used `last_topic`/`last_session_timestamp` and had no `last_decisions` key at all — didn't match Part 7/12.2's canonical Observer output shape (`topic`/`snapshot_date`/`last_decisions`). Same bug class as the RAG `target_table` issue; fixed before wiring Stage 11 to it, not after. |
| Live validation against real `llama3.1:8b` | Ran twice, not just against a fake provider: `run()` alone, then the full `run_session_end()` against a real encrypted DB. Found one real bug live: `session_snapshot.last_decisions` came back as a list of full decision objects, not strings — `_sanitize_snapshot` checked "is this a list" but not "is each item a string." Fixed with `_as_string_list()`, re-verified against real output afterward. |
| Empirically confirmed, not just documented | The evidence_count=1 discard problem that motivated the reinforcement fix below actually happened on the live run: both memory candidates came back `DISCARD` because `profile_age_weeks` for the test profile was past month 2 (requires evidence_count >= 3), and a single-session extraction can only ever produce evidence_count=1. The decision candidate (2 signals, confidence 0.7) correctly auto-logged. |
| **Cross-session evidence reinforcement** (Part 8.6) | DONE — `stage_12_validation_layer.reinforce_evidence(conn, candidate)`. Called by `run_session_end()` before `stage_12.run()`; the reinforced candidate (not the original) flows through to `stage_13.run()` so the increment is visible to both the threshold check and the actual write, not just the check. Reinforces only when the existing stored value matches the candidate's `proposed_value` exactly — a *different* value is a conflict, not a repeat observation, and is left alone for the existing TIER_2_REQUIRED/behavioral-override paths to handle. `identity` and `active_projects` have no `evidence_count` column and are returned unchanged. Verified with a simulated two-session test: a fresh evidence_count=1 candidate DISCARDs at week_3_4 on its own, then APPROVEs once reinforced against a prior session's stored row — both the in-memory check and the persisted DB row reflect the reinforced count. |
| `pending_observer.enqueue()` wiring into `run_session_end` | Was NOT DONE at this point in the build (correctly deferred — that trigger point needs a process-lifecycle context this module doesn't have). **Since resolved** by Phase 8's `core/session_lifecycle.py::enqueue_for_shutdown()`, which calls `pending_observer.enqueue()` directly at the shutdown trigger, not from inside `run_session_end` itself (enqueueing happens *instead of* running Observer, when there's no time left to run it at all — see the Phase 8 section below). Leaving this row as a historical record of the sequencing rather than deleting it. |
| Idle-timeout / process-exit triggering (Rule 3) | Was NOT enforced at this point (no process-lifecycle context existed yet for a plain function to hook into). **Since resolved** by Phase 8's `session_lifecycle.py` — idle-timeout and disconnect both run Observer synchronously via `run_observer_now()`; whole-server shutdown enqueues instead, per the row above. |
| Test coverage | 19 new tests total: 13 in the initial Stage 11 pass (`test_stage_11_observer.py`, plus 3 in `test_decision_log.py` for `route_observer_decision`), plus 6 more for reinforcement (5 in `test_stage_12_validation_layer.py`, 1 full-orchestrator integration test in `test_stage_11_observer.py`). All against a fake provider for speed, plus two live smoke-test runs against real `llama3.1:8b` (not part of the permanent suite — too slow to run every time, ~60-130s per call) |

## Phase 8 — COMPLETE (Full Pipeline Integration + Web + Flutter Spike)

Every stage (0–10), the orchestrator, the WebSocket endpoint, process-lifecycle
wiring, the Response Cache, the plain HTML/JS web client, and the throwaway
Flutter spike are all built and tested against real infrastructure (real
model, real DB, real search, a real server process, a real browser, a real
Dart WebSocket client). Part 18's Phase 8 scope — "Full Pipeline Integration +
Web + Flutter spike" — is now fully closed. What follows is the backend work,
then the web client, then the Flutter spike.

Building in scoped, tested increments rather than all at once. Started with the
stages that had no dependencies left to satisfy, in pipeline order.

| Item | Status |
|---|---|
| **`stage_01_intent_classifier.py`** | Was a 4-line comment stub with zero implementation despite being referenced everywhere (B4, Router's spec) — built for real. Keyword/regex classification (B4: never generative) across all 8 categories. Mechanism 1 (`skip_rag`) checks message tokens against `active_projects` names and a recent-active-decisions keyword cache; Mechanism 2 (ADR-002 embedding pre-check) is explicitly Stage 5's job to always run, not implemented here. Fails open to `general_knowledge`/`skip_rag=False` per spec. |
| Found while testing Stage 1 | The bare `\bwhat is\b` pattern for `technical_explanation` matched "What is the capital of France?" — too generic, overlaps heavily with plain general-knowledge questions. Narrowed to `how does X work` / `why does X` / `difference between X`, which are more reliably technical framings; dropped the bare "what is" pattern rather than trying to special-case around it. |
| `stage_02_router.py` | Priority-orders Stage 3/4/5 results for Context Assembly (ADR-002: orders, never skips — all three always run in parallel regardless of category). Default ordering is anchored to ADR-023's already-locked Cache Authority Hierarchy (`decision_log > memory > rag`), not invented from scratch; `personal_question` and `coding_question` get category-specific reorderings. `provider_preference` defaults to `"local"` — moot while v1.0 is local-only, same reasoning as ADR-033's condition 1, but the field exists so a future cloud-consented provider has somewhere to plug in. |
| `stage_03_decision_log_lookup.py` | Thin wrapper around `decision_log.search_decisions()`, which already implements the FTS5-with-LIKE-fallback this stage's spec calls for. Its only real job is the fail-open contract Stage 3 needs but `decision_log.py` itself correctly doesn't provide (a direct `/decisions` CLI call *should* let a real error surface; a parallel pipeline stage must not). |
| Found while testing Stage 3 | My own first test inserted a row via raw SQL instead of `decision_log.insert_decision()` — the FTS5 index only gets synced by that function (or `create_decision()`/`route_observer_decision()`, which call it too), so the raw insert left the row unsearchable. Not a Stage 3 bug: the test violated the project's own one-writer-per-table rule (ADR-025) by writing to `decision_log` outside `decision_log.py`. Fixed the test to go through `insert_decision()`, which is also a live demonstration of why that rule matters. |
| `stage_04_memory_lookup.py` | Part 7.3's "relevant profile fields only, NEVER full profile dump" needed a selective query `profile_store.py` didn't have (only `get_profile()` = everything, or `get_profile_field()` = one named field). Fetches the full profile via `profile_store.py` (the only allowed access path per spec) and filters to a category→table map before anything leaves the function, so a full dump is never actually returned. Unmapped categories fall back to `interaction_style` alone (how to respond is broadly useful; still far short of a full dump). |
| Test coverage | 33 new tests across the four stages (13 Stage 1, 7 Stage 2, 5 Stage 3, 5 Stage 4), all fast (no LLM calls involved in these four stages) |
| `stage_06_web_search.py` | DONE — `settings.json` already locked the provider (`duckduckgo`); implemented via `ddgs` (new dependency — the actively-maintained successor to `duckduckgo-search`, which is years behind on releases). `search_fn` is injectable, same pattern as Stage 11's provider and `pending_observer`'s `observer_runner` — the stage's own logic (TTL cache, trigger detection, fail-open) is fully testable without a network call. Trigger keywords are imported from Stage 1's `EXTERNAL_INFO_KEYWORDS`, not duplicated. Verified against the real DuckDuckGo API, not just a fake — `title`/`href`/`body` response keys matched what the code assumed on the first live call, no fix needed. Stage-local 3600s TTL cache (in-process dict) is separate from Part 7.1's broader Response Cache, which still doesn't exist. |
| `stage_07_context_assembly.py` | DONE — resolved a real arithmetic inconsistency in Part 7's own spec before implementing (see the NOTE added to the Stage 7 spec block above): the per-source budget lines sum to 6400, not the stated 6000, in both the doc prose and `settings.json`. Resolved as per-source *maximum ceilings* reconciled by overflow trimming, not fixed guaranteed reservations — confirmed self-consistent because the documented failure-mode floor (system + message only) is exactly what remains if every trimmable section gets dropped. Also resolved the overflow-priority list's self-contradictory numbering ("1. User message (never drop)" as the first item in a "what gets dropped first" list) by reading it as priority *rank* (1 = most protected), the same convention already used for ADR-023 and Stage 2's default retrieval priority. |
| Output shape | `{"context": str, "messages": list[dict]}`, matching `BaseLLMProvider.chat(messages, context)`'s existing two-parameter split (`OllamaProvider` already prepends `context` as a system message) rather than inventing a new prompt format — Stage 7 was built to fit the interface that already existed, not the other way around. |
| Per-source truncation + rolling window | Each source is capped to its own budgeted max before the overflow pass runs; conversation history keeps the most recent messages and drops whole messages from the oldest end (not mid-message truncation — a single message larger than the entire history budget is dropped as a unit, which is why the overflow test needed several smaller messages rather than one huge one to actually exercise cross-section trimming) |
| Test coverage | 8 tests: full-inclusion under budget, per-source truncation, rolling-window ordering, overflow trimming in the correct priority order, the worst-case floor, and the fail-open fallback |
| `stage_09_llm_streaming.py` | DONE — transport-agnostic by design: yields Part 14.3's WS event shapes (`stage_hint`/`token`/`done`/`error`) as plain dicts, with no knowledge of WebSockets at all. The eventual `/ws/chat` endpoint just forwards each event as JSON. Ordered provider fallback ("try next local provider" — Stage 8 already vetted every provider in the list as consented before this stage runs, so Stage 9 only handles ordering/fallback, not consent). Falls through to the next provider only if a provider fails *before* yielding any tokens; a mid-stream failure after partial output surfaces an error instead of silently starting a second provider from scratch, which would produce a duplicated/garbled response. A provider returning zero tokens without raising (a `BaseLLMProvider.chat()` contract violation) is treated as a failure, not a silent empty "done." `collect()` is a separate synchronous helper that drains a stream for callers (tests, Stage 10, a future CLI) that don't need live token-by-token forwarding. |
| `stage_10_response_delivery.py` | DONE — thin by design, matching its thin spec: finalizes the `trace_log.json` entry for the message and returns a summary. Does **not** trigger Stage 11 Observer — "all learning happens after this stage" refers to session-end Observer, and calling it per-message here would violate Rule 3 (Observer runs at session end only) outright, not just bend it. |
| Doc fix found in passing | Part 11.1's Storage Technology table claimed the trace log uses SQLite via SQLCipher. It doesn't and never has — `core/trace.py` writes to `logs/trace_log.json`, exactly as Part 17's folder structure already (correctly) documented, shipped and tested since Phase 1. A `trace_log` SQLite table exists in `schema.sql` (table 15) but was always dead weight, not the real write path. Fixed the doc row to match the already-shipped code rather than change working Phase 1 code as a side effect of building Stage 9/10 — a storage migration is a separate, bigger decision. |
| Live validation | Ran the full Stage 9 → `collect()` → Stage 10 chain against real `llama3.1:8b`, not just a fake provider — streamed tokens, aggregated correctly, trace entry written. |
| Test coverage | 11 new tests (8 Stage 9, 3 Stage 10), including mid-stream-failure-vs-before-any-tokens fallback behavior and the zero-token contract-violation case, all against a fake provider for speed |
| `core/pipeline.py` | DONE — wires Stages 0–10 for one user message (Stages 11–13 stay session-end only, triggered separately, never from here). A generator: yields every Stage 9 event live for a future WS handler to forward as-is, then a final `{"type": "pipeline_complete", "data": <Stage 10 result>}` sentinel, so callers don't have to drive the awkward `StopIteration.value` dance to get the aggregated result. `run_sync()` drains it for non-streaming callers (tests, a CLI). |
| Deliberate simplification, flagged not hidden | Part 7 specifies Stages 3/4/5 running in parallel via `asyncio.gather` and Stage 6 firing in a background thread. This orchestrator is synchronous — there's no event loop to gather into, because the FastAPI server layer that would own one is the next remaining piece (same boundary Part 13.1 already noted for `BaseLLMProvider.chat()`). All four run sequentially; parallelizing them is a mechanical follow-up once the async server wrapper exists, not a redesign, since the four stage functions are already independent. |
| Deliberate gap, flagged not hidden | Stage 0's `context_depth_modifier` (0–3, meant to scale session-history injection) is computed but not consumed anywhere yet — Stage 7 doesn't currently vary its snapshot budget based on it. |
| Defense in depth | Every stage call is wrapped even though each stage already fails open internally per its own spec — if a stage raises something it wasn't supposed to, the orchestrator logs it and falls back to that stage's documented empty output rather than letting one unexpected exception take down the whole pipeline. |
| Real bug found and fixed while testing | The first test run took 82s for 7 tests (should be seconds) — Stage 5 (RAG) was hitting the *real* embedding model against the *real* production `data/chroma` directory, because these pipeline tests hadn't isolated `vector_store.CHROMA_DB_PATH` the way `test_vector_store.py`/`test_stage_05` already do. Confirmed by checking disk: a real `data/chroma/` had been created. Fixed the test isolation (same pattern as the other RAG tests) and deleted the stray directory — down to 19s and no more real-state pollution. A reminder that "tests pass" isn't the same question as "tests are actually isolated." |
| Test coverage | 7 tests: happy path, `run_sync()`, no-consented-providers short-circuit (verified it exits *before* Stage 9 ever runs, not just that the end status is wrong), web-search trigger gating, a stage-level exception not crashing the pipeline, trace_log entries recorded for every stage under one shared `trace_id`, and mid-stream provider failure still reaching Stage 10 with the partial output preserved |
| `/ws/chat` WebSocket endpoint | DONE — `backend/api/server.py`. One connection = one conversation: `conversation_history` accumulates in memory for the connection's lifetime (Part 15.2: chat is WebSocket-only, no REST `/chat`, ADR-028). Forwards Stage 9's `stage_hint`/`token`/`done`/`error` events verbatim (Part 14.3); the `pipeline_complete` sentinel is consumed server-side, never sent to the client - it's an internal Python convenience, not part of the wire protocol. |
| Sync/async bridge, resolved not just flagged | Part 13.1 already noted the tension (`BaseLLMProvider.chat()` streams synchronously; the async server layer needs `asyncio.to_thread`/`run_in_executor`). Implemented as `loop.run_in_executor(executor, next, gen)` in a loop — calls one `next()` at a time off the event loop, so other WebSocket connections aren't starved for an entire response's duration, while still yielding every event live for progressive streaming. |
| **Real bug found and fixed by the first live end-to-end run, not caught by any mocked test** | `run_in_executor(None, ...)` (the default *shared* thread pool) crashed Stage 8 with `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread` — SQLite/SQLCipher connections aren't thread-safe, and the shared pool can dispatch different `next()` calls to different worker threads while `conn` stays bound to whichever thread created it. Stages 3/4 had been silently absorbing the *same* underlying issue via their own fail-open paths the whole time; Stage 8 correctly did **not** fail open around it (it's a hard security gate, not meant to degrade quietly), which is exactly why it surfaced instead of staying hidden. Fixed with a dedicated single-worker `ThreadPoolExecutor` per WebSocket connection — `conn` is opened on it and every subsequent `next()` call for that connection's whole lifetime runs on that same one thread, never the shared pool. No mocked test (including the 4 in `test_ws_chat.py`) could have caught this — it only exists under real threading behavior, which is exactly why the live end-to-end pass was run before calling this done, not skipped as "probably fine." |
| Live validation | Two full turns over one real WebSocket connection against real `llama3.1:8b`: first a cold-load run correctly hit the fail-open error path (default 30s timeout vs. ADR-033's measured ~130s cold load — expected, not a bug), then a warmed-model run streamed a real answer and a **second** turn on the same connection correctly referenced the first turn's content ("You just asked me to define a hash table..."), confirming `conversation_history` accumulation works for real, not just against a fake in a test. |
| Test coverage | 4 tests against a monkeypatched `pipeline.run` (fast): event streaming hides the `pipeline_complete` sentinel, a missing `message` key sends a clean error, conversation history accumulates correctly across two turns (and does **not** duplicate the current message — a real bug caught and fixed before any test ran, once realizing Stage 7 already appends `user_message` itself), and the DB connection closes on disconnect. That last test needed a small fix too: it originally asserted immediately after the client-side socket closed, racing the server's async cleanup - flaked under the full suite's load even though it passed reliably in isolation. Fixed with a short bounded poll instead of an immediate assert. |
| Process-lifecycle wiring (`core/session_lifecycle.py`) | DONE — closes Rule 3's three real triggers (10-min idle, disconnect, whole-server shutdown), which the original single-session-CLI-era spec didn't map 1:1 onto a multi-connection server, so this module treats them deliberately differently: idle-timeout and normal disconnect run Observer synchronously now (there's time, nothing else waits on either); whole-server shutdown persists every open connection's transcript to `pending_observer` instead (ADR-033 condition 2 - a ~130s-class pass can't run per open connection during shutdown), drained for real by `drain_pending_on_startup()` on the next launch, wired into the FastAPI `lifespan` handler. `SessionRegistry` tracks currently-open sessions (single-process, single-user - an `asyncio.Lock` is sufficient, no distributed coordination needed). |
| **Real bug: Python default-argument gotcha, not a test-only issue** | `run_session_end()`'s `snapshot_path` default is bound at *function-definition* time (a well-known Python trap), so monkeypatching `stage_11_observer.SESSION_SNAPSHOT_PATH` in a test silently did nothing - the call still wrote to the real path baked in at import. Two of `session_lifecycle`'s own tests passed anyway, for the wrong reason: the real `data/` directory happened to exist, so the misdirected write silently succeeded at the wrong location instead of failing - this was quietly polluting the actual production `data/session_snapshot.json` on every test run. Only surfaced once `data/` was cleaned up mid-session and the same write started raising `FileNotFoundError` instead of silently succeeding somewhere wrong. Fixed properly: `run_observer_now()` and `drain_pending_on_startup()` now take an explicit `snapshot_path` parameter and forward it, rather than relying on a module attribute a caller can override. |
| Trace-log visibility, added after a real debugging gap | Observer session-end runs (idle-timeout/disconnect/startup-drain) had zero `trace_log.json` visibility at first - discovered live, mid-verification, when a real disconnect-triggered run produced an empty result and there was no way to tell whether it had even fired, let alone why. `run_observer_now()` now generates its own `trace_id` (session-end runs aren't tied to any single message's trace_id) and logs start/candidate-counts/failure. |
| Second real test-pollution bug, same class as the ChromaDB one | Adding that trace logging meant `session_lifecycle`'s and the WS route's tests started writing into the real `backend/logs/trace_log.json` too, since neither test file had isolated `trace.TRACE_LOG_PATH`. Fixed with the same `monkeypatch.setattr(trace, "TRACE_LOG_PATH", tmp_path / ...)` pattern already used elsewhere in this suite. Also added `data/session_snapshot.json` to `.gitignore` - the same category of runtime artifact as `data/chroma/`, hadn't bitten yet but would have. |
| Live-validated, not just mocked | Full round trip against the real server and real `llama3.1:8b`: sent a content-rich message ("I've switched to using Neovim as my main editor, I prefer it now."), disconnected cleanly, and the trace log confirmed the disconnect-triggered Observer run actually fired and extracted 1 memory candidate + 1 decision candidate from it - not just that the wiring *executes*, but that it produces the same real, useful output already validated for Stage 11 in isolation earlier this session. |
| Found in passing, real but out of scope for this task | Stage 3's FTS5 query broke on ordinary punctuation in a live retrieval_hint (`fts5: syntax error near ","` / `near "?"`) - e.g. "What did I just ask you about?" as a query. Correctly failed open (logged, returned empty, never crashed the pipeline) exactly as designed, but this means Stage 3 decision-log lookup effectively never succeeds for a natural-language `retrieval_hint` containing common punctuation. Needs its own fix (sanitizing/escaping the FTS5 MATCH query) - flagged here rather than silently left for someone to rediscover, but not fixed as part of process-lifecycle wiring. |
| Correctly not built | An OS-level SIGINT/SIGTERM-to-lifespan-shutdown re-verification - this app relies on uvicorn's own well-established signal handling to invoke the FastAPI `lifespan` shutdown phase, which is what was actually implemented and tested here (via `TestClient`, which runs the real Starlette lifespan protocol, not a stand-in). Independently re-testing uvicorn's own OS-signal wiring would be redundant, not missing coverage. |
| Test coverage | 11 new tests: 8 for `session_lifecycle.py` in isolation (registry, `run_observer_now` including the local-provider rejection, `enqueue_for_shutdown`, `drain_pending_on_startup`), 3 more added to `test_ws_chat.py` (idle-timeout triggering + history clearing, registry registration/unregistration wiring, startup drain) |
| `core/response_cache.py` | DONE — this is Phase 8's last remaining piece; the pipeline is now feature-complete end to end. Positioned exactly where Part 7.1 specifies (between Stage 2 Router and Stage 7 Context Assembly): a hit skips Stages 3-9 entirely, not just the LLM call, wired directly into `core/pipeline.py`. |
| Resolved another real spec inconsistency, same class as Stage 7's | Part 7.1's TTL table only lists 6 names (`general_knowledge`, `technical_explanation`, `web_search`, `project_question`, `personal_question`, `decision_lookup`), but Stage 1 has 8 real categories - neither `web_search` nor `decision_lookup` is an actual Stage 1 category name. Resolved as: `web_search` maps to Stage 1's `external_information` (the category that actually triggers Stage 6); `decision_lookup` isn't a category at all, it's the `decision_log_hit` override the same section's "Authority" line already describes, implemented as a hard bypass, not a table entry. The three categories genuinely absent from the table (`coding_question`, `research_request`, `project_continuation`) default to never-cache — the conservative choice, since over-caching a personalized/project-specific answer is a worse failure than under-caching a cacheable one. |
| Cache authority enforced, not just documented | Part 7.1: "Decision Log always overrides." `response_cache.set()` is a no-op whenever `decision_log_hit=True`, regardless of category — a decision-log-influenced answer can never be masked by a stale cached response after the decision is later superseded or abandoned. |
| Real test-pollution bug found while testing the integration | `response_cache._cache` is a module-level dict shared across the whole pytest process. Several `test_pipeline.py` tests reuse plain messages like `"hello"` — without isolating the cache between tests, a cached response from one test silently served a *later* test: it masked a mid-stream provider failure test's provider never actually being called (served a stale cached "success" instead of the real induced "error"), and broke a trace-log test because Stage 3 never ran on the cache-hit path. Same root cause and same fix pattern as the ChromaDB and `trace_log.json` isolation bugs found earlier this session — module-level shared mutable state needs explicit per-test clearing, every time, not just where it was needed last. |
| Test coverage | 19 new tests: 16 for `response_cache.py` in isolation (key normalization, TTL-per-category including the three conservative defaults, decision-log-hit bypass, expiry, fail-open on error), 3 pipeline-level integration tests (a cache hit skips Stage 3 and serves the cached text instead of a differently-configured provider's fresh output; `project_question`'s TTL-0 is honored end to end) |

### Web client (`frontend/web/`) — DONE, live-browser-validated

Part 14.1: plain HTML/JS, built and proven before Flutter is touched. Part
14.4's "frontend has zero intelligence" is enforced structurally — `app.js` is
a thin renderer: every value it shows came directly from a REST/WS response,
nothing is computed or inferred client-side beyond which tab is active and the
in-memory chat transcript.

| Item | Status |
|---|---|
| `index.html` / `style.css` | DONE — onboarding form matching `api_complete_onboarding`'s exact payload shape, tabbed app shell (Chat/Profile/Decisions/Projects/Providers), dark theme via CSS custom properties. |
| `app.js` | DONE — fetch helpers against `/api/v1`; onboarding submit; WS chat (`connectChat()`/`handleChatEvent()`); CRUD load/render for all four REST views; tab switching; auto-reconnect on WS close. |
| Static file serving | `backend/api/server.py` mounts `StaticFiles(directory="frontend/web", html=True)` at `/`, registered **last** — after every `/api/v1/*` route and `/ws/chat` — so Starlette's registration-order route matching gives the explicit API/WS routes precedence over the catch-all static mount. Verified live: `/api/v1/status` still resolved correctly after the mount was added, not shadowed by it. |
| Stage-hints rendering | Matches Part 14.3 exactly: `stage_hint` events are buffered (`pendingStageHints`), only rendered into the sidebar on `done`/`error` — a static post-response snapshot, not live per-event animation, per spec ("live animated per-stage updates are optional polish, not budgeted"). |
| Live validation | Real `uvicorn` server + real `llama3.1:8b` + a real browser (Claude Code's Browser pane), not just unit tests against a fake. Walked through: fresh onboarding (`POST /onboarding/complete`, confirmed field-for-field against the real payload), a clean single-turn WS chat exchange (streamed tokens rendered correctly, stage-hints sidebar populated correctly on `done`), Decision Log create + list refresh, Profile view (rendered real `GET /memory/profile` rows, including the skill/interaction-style rows' `value`/`confidence` split — confirmed that's the backend's real data shape, not a client rendering bug), Projects create + list refresh, and Providers consent grant/revoke (button state and table both updated correctly after each call). |
| Testing artifact, not a product bug | The first live chat test (driven via simulated clicks/typing) produced a stuck empty assistant bubble alongside a second, garbled reply. Isolated by re-driving the exact same flow through direct DOM/event dispatch (bypassing simulated click/type timing) — a clean single-message exchange rendered correctly with no mixing. Root cause was the browser-automation layer's click/focus timing in this environment, not `app.js`: a `computer` `type` action landed on the wrong tab mid-session (confirmed by unexpected `GET /api/v1/projects` / `/memory/profile` calls in the server log with no corresponding intentional tab switch). Flagging as an automation-environment quirk observed during testing, not a defect in the shipped code. |
| Known simplification, flagged not hidden | The Providers view's "Grant consent" button always sends `consent_scope: "full_inference"` regardless of provider type — so granting consent to `web_search` (a `web_search_only`-scoped provider) currently requests the broader `full_inference` scope rather than a narrower one. `VALID_CONSENT_SCOPES` on the backend accepts it, so this isn't a broken request, just not the most precise default. A future pass could add a scope selector; not done now since it doesn't affect Stage 8's enforcement correctness. |
| Not built | No automated frontend test suite (no Playwright/Jest) — validation for this piece is the live manual browser pass documented above, consistent with Part 14.4's "thin renderer" philosophy keeping client-side logic minimal enough that the main risk is wiring, not business logic. |

### Backend completeness pass — closing the open items from the punch list above

Requested directly: go through every backend item flagged as missing/deferred
across the whole build and resolve what's actually resolvable, rather than
leave a known-bugs list sitting in the doc indefinitely.

| Item | Status |
|---|---|
| **Stage 3 FTS5 punctuation bug** (the one real, unfixed functional defect on the list) | FIXED — `decision_log._build_fts5_match_query()` tokenizes the raw query to `\w+` words and re-quotes each as a literal FTS5 term, joined with `OR` (not the FTS5-default implicit `AND`, which turned out to be the wrong join even once the syntax error was gone — a natural-language question shares few *exact* words with a terse logged decision, so requiring every query word present made real questions match nothing, just without throwing). Results are ranked by `bm25()` relevance instead of `created_at` alone, so a single shared content word surfaces the right decision while words shared with nearly every entry ("we", "did") get relevance-penalized automatically rather than needing a hand-maintained stopword list. |
| Test coverage | 4 new tests: `decision_log`-level (matches despite punctuation; a punctuation-only query with no word tokens returns `[]` rather than erroring) and `stage_03`-level (same, through the fail-open wrapper). |
| **Stages 3/4/5 parallelization** — re-examined, deliberately NOT done | The old comment claimed this was "a mechanical follow-up once the async server wrapper exists, not a redesign" — that wrapper exists now (Phase 8), so this got checked for real rather than left on the strength of the old note. It's not actually mechanical: Stages 3, 4, **and** 5 all take the same `conn` and use it for real reads (Stage 5 also calls `decision_log` for its own conflict check, not just `vector_store`) - parallelizing them across threads would reintroduce the exact SQLite/SQLCipher thread-affinity bug this session already hit live in the WS endpoint (connections are thread-pinned to whichever thread created them). Doing this safely needs either a dedicated connection per stage or a genuinely async DB layer - a real design decision with real tradeoffs (extra connection overhead, WAL-mode concurrent-read behavior to verify), not a drop-in change. Documented the actual constraint in `pipeline.py`'s module docstring instead of leaving the old "it's easy" claim standing; left the stages sequential rather than force a risky change with only a marginal latency win (Stage 5's embedding query is the only even mildly slow one of the three). |
| **Stage 0's `context_depth_modifier` now consumed** | FIXED — `stage_07_context_assembly.run()` takes it as a parameter and scales `session_snapshot_tokens` by `modifier / 2`: modifier 2 (the 24h-7d "summary" gap) reproduces the original fixed 250-token budget exactly (default value, so no existing caller's behavior changes), modifier 0 (<1h "none") drops the snapshot section entirely (redundant with live `conversation_history` over that short a gap), modifier 3 (>7d "full") gets 1.5x the base budget for a longer-absence recap. `core/pipeline.py` now forwards `gap_result["context_depth_modifier"]` into the Stage 7 call instead of computing and discarding it. |
| Test coverage | 3 new Stage 7 tests (modifier 0 drops the section; modifier 2 matches the pre-existing fixed-budget output byte-for-byte; modifier 3 fits a snapshot that modifier 2 would have truncated) + 1 pipeline-level wiring test confirming Stage 0's real output value is what actually reaches Stage 7, not just that Stage 7 knows what to do with it in isolation. |
| **`pending_observer.enqueue()` triggering / idle-timeout-and-shutdown triggering (Rule 3)** | Turned out to be a **doc staleness bug, not a code gap** — both were correctly flagged NOT DONE back when only `stage_11_observer.py` existed (Phase 7), but Phase 8's `core/session_lifecycle.py` (built later, same session) already resolved both: `enqueue_for_shutdown()` calls `pending_observer.enqueue()` directly, and idle-timeout/disconnect both run Observer synchronously via `run_observer_now()`. The two stale rows in the Phase 7 table above have been corrected in place rather than deleted, so the sequencing stays visible. No code changed for this item — verified against `session_lifecycle.py` directly before touching anything. |
| **`shared/ws_spec.py`** | BUILT — [shared/ws_spec.py](../shared/ws_spec.py), per Part 17's frozen folder structure. TypedDicts for the four Part 14.3 wire-protocol events (`StageHintEvent`/`TokenEvent`/`DoneEvent`/`ErrorEvent`, unioned as `WSChatEvent`), the internal-only `PipelineCompleteEvent` sentinel (typed separately since it's never forwarded to a client), and `ChatRequest` for the client→server message shape. TypedDict, not Pydantic, to match the convention every other typed module in this codebase already uses. Wired into the actual producer/relay/forwarder chain as type hints only — `stage_09_llm_streaming.run()`/`collect()`, `pipeline.run()`'s generator type, and `server.py`'s `stream_pipeline_to_websocket()`/`ws_chat()` — zero runtime behavior change, since TypedDict performs no validation; this documents the shapes those functions already produced, it doesn't change them. `shared/models.py` (Pydantic REST models) is intentionally not part of this — see the row above. |
| **SQLCipher wrong-key test debt** | Turned out to be a **second doc staleness bug** — the "Tracked Technical Debt" table (further below) still claimed the wrong-key test was skipped because `sqlcipher3` wasn't installed, directly contradicting this same document's own "Resolved, removed from this table" note a few hundred lines earlier (Phase 5 commit `c558893` already installed it). Re-ran `test_schema.py::test_wrong_key_behavior` directly to confirm before touching the doc: it runs, not skips, and passes. Corrected in place. |
| Full suite re-verified | 265 → 272 tests (7 new: 3 FTS5 fix, 4 context_depth_modifier including the pipeline wiring test), all green, after every change above — see the module docstrings/table rows this session touched for what changed and why. |
| ConstitutionEnforcer gated-field row (checked, no code change) | See the corrected "Tracked Technical Debt" row below — the doc's own cleanup suggestion there had the two `_matches_gated_field` branches backwards; verified against the real `constitutional.json` patterns and `test_constitution_enforcer.py` before concluding that, not just re-reading the old note. |
| Pre-commit hook (ADR-025 enforcement) | DEPLOYED — its only listed blocker ("needs git init first") no longer applies, since this repo has been a live git repo with real commit history all session. Copied `scripts/pre-commit` to `.git/hooks/pre-commit` (`chmod +x`); dry-ran it against every file this backend-completeness pass touched before committing — exit 0, no ADR-025 violations. Not tracked by git itself (`.git/hooks/` never is), so a fresh clone still needs this one-time copy step; noted here rather than assumed automatic. |

### Throwaway Flutter spike (`frontend/flutter/`) — DONE, real-async-stream-validated

Part 14.1: "Weeks 3-4: Throwaway Flutter spike (2-3 days). Connects to fake
echo WebSocket server. Renders streamed tokens in Dart. Tests async stream
handling. DISCARDED after - de-risks Dart before Phase 8." Built after the web
client (already proven above), per spec ordering. This is explicitly **not**
the real Phase 8+ Flutter client — no REST calls, no local storage, no
connection to the real PIP backend at all.

| Item | Status |
|---|---|
| `scripts/fake_echo_server.py` | DONE — a minimal `websockets`-based server, deliberately not the real backend (no pipeline, no DB, no LLM). Speaks the actual Part 14.3 wire shape (`stage_hint` → `token`* → `done`, or → `error`) rather than an arbitrary echo format, so the spike exercises the real shape the eventual Flutter client needs, not a toy protocol. Splits the echoed message into words and streams them back one at a time with a 150ms delay between each — a single "here's your whole reply" frame wouldn't exercise the thing this spike exists to de-risk. |
| `frontend/flutter/lib/main.dart` | DONE — `flutter create --platforms=web,windows --project-name=pip_flutter_spike`, then a single-screen chat-style UI: connect bar, a scrollable transcript with `token` events appended to the in-progress bubble as they arrive (proving incremental async rendering, not a buffer-then-render-once pattern), a stage-hint chip row, and a send box. `web_socket_channel: ^3.0.1` for the WS client — the standard package for this, not something bespoke. `flutter analyze`: 0 issues. |
| **Real async-stream validation** — the actual point of the spike | `frontend/flutter/test/echo_stream_test.dart` — not just a widget smoke test. `setUpAll` spawns the real `fake_echo_server.py` as a subprocess (`Process.start`, unbuffered stdout, waits for its "listening" line), connects a real `WebSocketChannel` on the Dart VM (via `flutter test`, no browser involved), sends a message, and asserts on the actual event sequence: `stage_hint` first, one `token` event per word in order with the reassembled text matching exactly, `done` last. Then the test that actually matters for "tests async stream handling": it timestamps each token's arrival and asserts the spread between the first and last token exceeds 300ms — proving the frames arrived spread out over real wall-clock time (matching the server's 150ms-per-word delay), not buffered and delivered in one microtask burst the way a naively-implemented or accidentally-buffering stream consumer would. Ran for real, passed on the first run. |
| `frontend/flutter/test/widget_test.dart` | DONE — smoke test confirming the UI builds and shows its initial shell (connect bar, Send button, "disconnected" status). Rewritten from `flutter create`'s default counter-app test, which referenced the template's `MyApp` class that no longer exists. |
| Manual UI validation — a real gap, disclosed not hidden | Started the real app for real (`flutter run -d web-server --web-port=8090`, confirmed serving via a real HTTP 200 and `document.title`/`document.readyState` inspection) and opened it in the Browser pane the same way the HTML/JS web client was validated earlier this session. Screenshots failed in this environment this session ("the Browser pane is not displayed, so the page is not compositing frames") on *every* tab, including the plain-HTML web client tab that had rendered fine earlier in the same session — an environment-level regression, not something caused by Flutter's CanvasKit rendering. Confirmed the app was really running (HTTP 200, correct `document.title`, a real DOM shadow tree under `flt-glass-pane`), and confirmed Flutter's accessibility/semantics activation button existed and responded to a dispatched pointer event, but could not get pixel-level or accessibility-tree confirmation that the chat bubbles/stage-hint chips render exactly as intended. The `echo_stream_test.dart` result above is real proof the underlying mechanism works; the on-screen rendering of that mechanism is unverified by direct observation this session. Flagged rather than claimed as fully checked. |
| Not built, correctly out of scope | REST calls, local storage, real backend connection, Windows-desktop-build validation (only the web target was run) - none of these are Part 14.1's job for this spike; they belong to the real Phase 8+ Flutter client, which starts from scratch rather than growing out of this throwaway code (spec: "DISCARDED after"). |
| Disposition | Built, committed, and left in the repo rather than deleted outright — per spec this is meant to be discarded once it's done its job, but deleting code the moment after writing it, before anyone's looked at it, isn't a call to make unilaterally. Flagged for the user to decide: delete now that Dart's async stream handling is proven, or keep it a while longer as a reference. |

## Decided but Not Yet Written as Files

| Item | What's missing |
|---|---|
| PRD 1.6 (non-goals vs deferred) | Tool Execution Layer distinction not written (external PRD doc, not this file) |
| PRD 1.8 (tiered success statements) | v0.5/v1.0 claims not in PRD (external PRD doc, not this file) |
| `shared/models.py` (Pydantic REST models) | Still not written. Deliberately not bundled into the `ws_spec.py` work in the backend-completeness pass above — this would mean moving every REST endpoint off its current raw-dict-payload style onto Pydantic, and no module in the codebase uses Pydantic today despite FastAPI pulling it in transitively (TypedDict is the established convention — stage_00/01/02/07/11, `core/types.py`). That's a real design decision (adopt Pydantic project-wide vs. keep TypedDict everywhere), not a mechanical fill-in, so it's left open rather than decided as a side effect. |

**Resolved, removed from this table (verified against the current doc text, not re-claimed as still open):**
SQLCipher test environment (Phase 5 environment-fix commit `c558893` — `sqlcipher3` installed,
wrong-key test passes for real); Threat Model T1/T4 and backup export (Part 10 has described
SQLCipher, not Fernet, since before this session — this table just never got updated to say so);
pending-candidate sort order (Part 8.7/9.2/24 have all said `confidence ASC, created_at ASC`
since before this session, same stale-tracking issue); Shared WS message spec (`shared/ws_spec.py`
now built, see the backend-completeness pass above); pre-commit hook (now deployed to
`.git/hooks/pre-commit`, same pass).

## Tracked Technical Debt (not urgent fixes)

| Item | Status |
|---|---|
| ~~ConstitutionEnforcer gated-field helper cleanup~~ | **Checked, not a real cleanup opportunity — this row had it backwards.** `field_name` (e.g. `"goal_text"`) is never table-qualified on its own (confirmed against `MemoryCandidate`'s producers and `test_constitution_enforcer.py`'s own fixtures); every pattern actually in `constitutional.json`'s `gated_fields.fields` IS table-qualified (`"goal_memory.*"`, `"active_projects.*"`, `"interaction_style.*"`, `"skill_memory.*.level"`). So the `target_table.field_name` concatenation branch is the one doing real work — removing it, as this row used to recommend, would have silently broken gated-field detection for all four current patterns (verified: `test_gated_field_requires_confirmation`'s `goal_memory`/`goal_text` case only passes via that branch). The bare `fnmatch(field_name, pattern)` branch is the actually-unreachable one under the current ruleset, kept as a defensive fallback for a future non-table-qualified pattern rather than deleted, since `constitutional.json` authors that list, not this function. Left both branches in place; added a comment explaining why rather than "cleaning up" into a regression. |

**Removed, stale duplicate:** a "SQLCipher-dependent local tests / wrong-key behavior unverified" row lived here too, contradicting this same document's "Resolved, removed from this table" note above (Phase 5 commit `c558893` installed `sqlcipher3` and made the wrong-key test pass for real). Re-confirmed directly: `test_schema.py::test_wrong_key_behavior` runs (not skipped) and passes in the current environment. The row was never deleted when the fix landed — a doc-sync gap, not a code gap.

## Phase 3 DB Migration Note (one-time, RESOLVED for local dev DB)

**Context:** `seed_provider_consent()` was added to `memory/profile_store.py` in Phase 3 (Ticket 4). Any database initialized before this point (Phase 1/2 work) will have the `provider_consent` table but zero rows, which causes Stage 8 to hard-stop on every request (fail-closed policy).

**Confirmed:** The local dev DB at `data/pip.db` was verified to have 0 rows in `provider_consent` before this migration. The migration was run and confirmed 2 rows inserted (ollama, web_search).

**For any future pre-Phase-3 DB** (e.g. a teammate cloning and using an older DB dump): run the migration script once from the repo root:

```
python scripts/migrate_seed_provider_consent.py [--db-path PATH]
```

- Default path: `data/pip.db`
- Idempotent: safe to run multiple times — no-op if rows already exist
- Script location: `scripts/migrate_seed_provider_consent.py`

**New DBs** created after Phase 3 are not affected — `initialize_schema()` now calls `seed_provider_consent()` automatically.

## Genuinely Open (cannot be resolved by architectural reasoning)

| Item | What's needed |
|---|---|
| Submission deadline | Exact calendar date still unset — confirmed as "3+ months, flexible" as of 2026-08-17, so scope decisions aren't currently being made blind, but no hard date exists yet |

**Resolved, removed from this table:** Model-swap benchmark — retired by ADR-033 (no swap exists to benchmark; Observer and generation share llama3.1:8b).

---

# PART 21 — IMPLEMENTATION SEQUENCE FOR PHASE 0

**Exact order. Non-negotiable for items 1–4:**

```
1. backend/core/constitutional.json          (the ground truth for everything)
2. backend/core/constitution_enforcer.py     (class with 6 ValidationResult values)
3. All ConstitutionEnforcer tests            (Tickets 003–006)
4. backend/core/trace.py                     (trace_id generation, stage_log)
5. backend/core/schema.sql                   (ALREADY DONE)
6. backend/config/settings.json             (ALL keys, activation comments)
7. backend/config/settings.py              (canonical loader)
8. backend/tests/test_schema.py            (FTS5 roundtrip + wrong-key tests)
9. scripts/pre-commit                       (ADR-025 enforcement)
10. requirements.txt + venv setup
11. Phase 0 comment skeletons in stage_01, vector_store, decision_log
```

**Exit condition for Phase 0:**
- All ConstitutionEnforcer tests pass
- FTS5 roundtrip test passes against real SQLCipher DB
- Wrong-key test fails loudly (not silently returns empty)
- Pre-commit hook blocks a test commit with a raw sqlite3 import
- Folder skeleton exists on BatMan's machine
- Git initialized, v0.0 tag pushed

---

# PART 22 — ONBOARDING QUESTION SCRIPT

Onboarding bypasses Observer and Validation entirely (onboarding_bootstrap exception).
Writes directly to identity and profile tables. Deactivates permanently after completion.

```
Q1: "What is your name?"
    → identity.name (immutable)
    Skippable: NO

Q2: "What is your primary language for communication?"
    → identity.language_preference (immutable)
    Skippable: NO

Q3: "What timezone are you in?"
    → identity.timezone (immutable)
    Skippable: YES — defaults to system timezone

Q4: "What are you currently working on?"
    → active_projects (name + description)
    Skippable: YES — can add later via /project new

Q5: "What is your primary skill area?"
    → skill_memory[stated_skill] (level 0.5 default, source=explicit)
    Skippable: YES — accepts up to 3 comma-separated skills

Q6: "How do you prefer answers?"
    1. Brief summary first, detail on request
    2. Full detailed answer always
    3. I'll specify each time (adaptive)
    → interaction_style.value (gated, bootstrap exception applies)
    Skippable: YES — defaults to adaptive

Q7: "What tools do you use most?"
    → preferred_tools (evidence_count=1, source=explicit)
    Skippable: YES — accepts up to 5 comma-separated tools

COMPLETION:
  profile_meta.onboarding_complete = 1
  profile_meta.first_session_date = now_utc()
  onboarding_bootstrap permanently deactivated
  "Setup complete. PIP is ready."
```

---

# PART 23 — COMMAND REFERENCE

```
DECISION LOG
/decide                    Start decision log entry workflow
/decisions                 List all active decisions
/decisions search [query]  FTS5 natural language search
/decisions [id] supersede  Mark as superseded
/decisions [id] abandon    Mark as abandoned (reason required)
/pending                   List pending decision candidates
/pending review [id]       Review one candidate
/pending promote [id]      Promote to decision log
/pending dismiss [id]      Dismiss candidate (kept 90 days)

PROFILE
/profile                   View all fields with confidence + source label
/profile edit [field]      Edit a field (user_correction write)
/profile delete [field]    Soft delete (not removed, filtered from retrieval)
/verify                    Manually trigger 30-session memory verification loop
/reset                     Full profile reset (irreversible without prior backup)

PROJECTS
/project new               Create new project (prompts name + description)
/project list              List all projects with status and last_active
/project switch [name]     Set active_project_id for this session

DOCUMENTS / RAG
/ingest [file]             Ingest document into ChromaDB vector store
/documents                 List indexed documents
/remove [document]         Remove document from index

PROVIDERS
/providers                 List all providers with consent status
/consent [provider]        Grant consent (prompts for scope)
/revoke [provider]         Revoke consent

BACKUP
/export                    Export encrypted backup (separate backup password)
/export --readable         Export plain text JSON (warning shown first)
/restore [file]            Restore from backup

SYSTEM
/status                    Ollama status, memory stats, RAG index status
/trace [trace_id]          Full trace for a specific message
/trace recent              Last 20 trace entries
/help                      Command reference
```

---

# PART 24 — GLOSSARY

**behavioral_override:** Reconciliation prompt when behavioral evidence contradicts a
stated preference across 3+ sessions over 14+ days. Never silent overwrite.

**candidate:** Unvalidated observation from Observer. Not written until Validation approves.

**candidate_store.py:** Sole owner of both pending tables (decision_candidates_pending,
memory_candidates_pending). Stages 11, 12, 13 are callers into it.

**confidence:** base_score * min(evidence_count, 5) / 5. Never self-assigned by Observer.
GENERATED ALWAYS AS column for skill/preference/interaction_style. Stored manual for goal.

**constitutional.json:** Immutable rule file. First file created. Everything downstream.

**ConstitutionEnforcer:** Single Python class. One public method: validate(). Tests must
pass before Observer is built (ADR-011).

**context_depth_modifier:** Integer 0–3 from Gap Detector. Scales session_snapshot allocation.

**decay_flag:** True when goal_memory entry inactive > 14 days.

**Decision Log:** Decisions table in SQLCipher. Hard deletion NEVER permitted (ADR-022).

**decision_candidates_pending:** Low-confidence decisions awaiting manual review.
Surfaced ORDER BY confidence ASC, created_at ASC (low-evidence oldest first).

**evidence_count:** Independent sessions in which signal appeared. Primary confidence input.

**explicit:** Observer label. User directly stated something. base_score = 0.9.

**FTS5:** SQLite full-text search extension used for /decisions search. Availability
checked once at startup. Fallback: LIKE inside still-encrypted DB. Shadow index: never.

**gated field:** Observer may detect changes. Requires user confirmation before write.
Pending candidates survive session close in memory_candidates_pending.

**get_connection():** The ONLY function that opens a SQLCipher connection. Lives in
profile_store.py. Executes 4 mandatory PRAGMAs in order.

**inferred:** Observer label. Observed from behavior, not stated. base_score = 0.4.

**model_loading:** WebSocket stage_hint boolean. True whenever llama3.1:8b needs a
cold load (e.g. after Ollama's keep_alive evicts it). No longer a two-model swap
signal (ADR-033 retired the swap entirely) — still needed because a cold load is
still real wall-clock time the user would otherwise perceive as a silent hang.

**onboarding_bootstrap:** Exception mode, first session only. Direct writes, bypasses all
validation. Deactivates permanently after onboarding_complete = 1.

**Provider Gate:** Stage 8. Hard stop if is_cloud AND (NOT user_consented OR revoked).
Per-provider object, not global boolean.

**retrieval_hint:** Short phrase from Intent Classifier. Pre-seeds Stage 3, 4, 5 lookups.

**session_snapshot.json:** Single JSON object written at every session end by Observer.
Loaded by Gap Detector in ~5ms on return. NOT a SQLite table — JSON is correct here.

**skip_rag:** Intent Classifier flag. Two separate mechanisms produce it vs ADR-002.
Mechanism 1 produces the bool via keyword cache. ADR-002 pre-check runs regardless.

**sqlcipher_export():** SQLCipher's native re-keying export via ATTACH DATABASE. Used for
/export. Encrypted-to-encrypted, no plaintext, WAL-safe (empirically verified).

**source_label:** explicit | inferred | user_verified | user_correction

**trace_id:** UUID generated at Stage 0. Propagated through all 14 stages. Written to
trace_log table with status (success|timeout|error) and error_detail per stage.

**warm_start_level:** none | brief | summary | full. Set by Gap Detector based on gap size.

---

# APPENDIX — EMPIRICAL TEST RESULTS

Historical empirical tests ran in sandbox environment against sqlcipher3-binary v0.6.0, SQLCipher 4.12.0.
Current local pytest report after Phase 2 crash-safety test: 28 passed, 1 skipped. The skipped test is SQLCipher-dependent wrong-key behavior; encryption-layer behavior is unverified in the current local test environment until SQLCipher/sqlcipher3 is installed.
Independently re-verified by a second AI sandbox on the same binary version.

| Claim | Test | Result |
|---|---|---|
| KDF: PBKDF2_HMAC_SHA512, 256k iterations | PRAGMA cipher_kdf_algorithm + cipher_default_kdf_iter | VERIFIED ×2 |
| Generated columns survive sqlcipher_export() | ATTACH + export + read back + check confidence | VERIFIED |
| WAL-resident data survives sqlcipher_export() without checkpoint | Write → confirm WAL file >0 bytes → export no checkpoint → restore → read | VERIFIED |
| PRAGMA wal_checkpoint not load-bearing for sqlcipher_export() path | Same test above | CONFIRMED non-load-bearing, kept as defense-in-depth |
| Full schema.sql executes clean | Run against real SQLCipher DB | 19 tables, 6 views, 1 trigger — PASS |
| decision_text_immutable trigger fires correctly | UPDATE decision_text → RAISE(ABORT) | VERIFIED |
| State field remains mutable (only decision_text protected) | UPDATE state → succeeds | VERIFIED |
| Foreign keys enforced (PRAGMA foreign_keys = ON) | Insert contradiction log with nonexistent FK → rejected | CONFIRMED via connection sequence |

---

*End of PIP Master Reference Document v3.0*
*Next action: Write backend/core/constitutional.json*
