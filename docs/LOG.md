# Log

<!-- Newest first. Prepend new entries directly under the format line. -->

Format:

- [YYYY-MM-DD] <agent> · <what changed> · why: <one clause> · files: <paths>

- [2026-09-08] claude · Added the evidence gate between Observer extraction and Stage 12, so a genuine quote can no longer carry an inference the user never made · why: grounding proved the words existed and the constitution checked policy, but nothing compared the evidence to the claim, so "I've been comparing FastAPI and Flask" wrote preferred_tools=Flask · files: backend/core/evidence_gate.py, backend/stages/stage_11_observer.py, backend/stages/stage_13_profile_update.py, backend/core/session_lifecycle.py, backend/tests/evidence_cases.py, backend/tests/test_evidence_gate.py, backend/tests/test_evidence_inference.py, backend/tests/test_venv_guard.py, scripts/eval_evidence_gate.py, docs/ARCHITECTURE.md

- [2026-09-08] claude · Added an AGENTS.md 80-line cap check to the pre-commit hook and documented it, plus the trailing-newline rule, in CONVENTIONS.md · why: the cap only existed in conversation, and an agent verifying against remembered counts reported all six docs as broken · files: scripts/pre-commit, docs/CONVENTIONS.md

- [2026-09-08] claude · Added Copilot and Cursor pointer files and listed them in the AGENTS.md folder map · why: both tools read only their own filename and would never reach AGENTS.md on their own · files: .github/copilot-instructions.md, .cursor/rules/project-context.mdc, AGENTS.md

- [2026-09-08] claude · Added the agent-context layer: AGENTS.md, CLAUDE.md, GEMINI.md, docs/ARCHITECTURE.md, docs/CONVENTIONS.md, docs/LOG.md · why: the repo's only written context was a single 766-line status doc with no rules for agents and no conventions reference · files: AGENTS.md, CLAUDE.md, GEMINI.md, docs/ARCHITECTURE.md, docs/CONVENTIONS.md, docs/LOG.md

## Archive
