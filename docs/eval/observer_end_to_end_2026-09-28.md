<!-- Raw output of scripts/eval_observer_end_to_end.py --repeat 3, 2026-09-28.
Labels: backend/tests/observer_cases.py as committed in 1256b51, before this run.
Model: qwen2.5:7b through Ollama 0.32.14 - the only model pulled on the machine
(the code's default, llama3.1:8b, was not available). Every case on a fresh
profile in its first two weeks. Interpretation, including the hand review of
the UNLABELLED rows: docs/FREEZE_LIST.md §7.14. -->

# End-to-end Observer measurement - model `qwen2.5:7b`

## Run 1

- cases: 37 (0 errored), total model time 197.9s
- funnel: 31 candidates extracted by the model, 30 survived grounding
  - evidence gate: {'EVIDENCE_SUFFICIENT': 12, 'EVIDENCE_NOT_ENTAILING': 13, 'EVIDENCE_INVALID': 3, 'EVIDENCE_NOT_USER_SOURCE': 2}
  - Constitution: {'APPROVED': 3, 'DISCARD': 17, 'REQUIRES_CONFIRMATION': 5, 'HARD_REJECT': 5}
  - Stage 13: {'written': 3, 'rejected': 22, 'pending': 5}
- learned rows: 12, labelled {'TRUE': 8, 'UNLABELLED': 3, 'TRAP': 1}
- **precision** (TRUE / TRUE+TRAP): 8/9 (89%)
- **recall** (stated facts learned): 8/23 (35%) - written 3, only queued for confirmation 5
- **traps reaching a belief table**: 1/25 (4%)

| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |
|---|---|---|---|---|---|
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=Finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=Write about half the chap EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | - | 0/1 | - | interaction_style.value=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | - | 0/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_typescript | fact | - | 0/1 | - | skill_memory.TypeScript=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Node.js=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | - | 0/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_final_year | fact | queued active_projects: pip a personal assistant (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_postgres_decision | fact | written decision_log: 1 move our database to postgres before the next release 0.7  (TRUE) | 1/1 | - | - |
| fact_vector_clocks | topic | - | 0/1 | - | - |
| fact_rust_learning | fact | - | 0/1 | - | skill_memory.Rust=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.preferred_tools=clap EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_sister | third_party | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_manager | third_party | - | - | 0/1 | - |
| trap_professor | third_party | - | - | 0/1 | preference_memory.preferred_tools=Fortran EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_what_if | hypothetical | - | - | 0/1 | skill_memory.Elixir=0.6 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | - |
| trap_might_swift | hypothetical | - | - | 0/1 | - |
| trap_kafka_question | question | - | - | 0/1 | - |
| trap_never_emacs | negation | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_used_to_java | past | - | - | 0/1 | skill_memory.Java=0.5 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| retract_vim_helix | retraction | - | 0/1 | 0/1 | preference_memory.preferred_tools=Helix EVIDENCE_SUFFICIENT/DISCARD/rejected |
| retract_deadline | retraction | written decision_log: 1 to ship the beta in may. 0.7 active 2026-09-28t05:57:08z (UNLABELLED); queued goal_memory: active_goals ship the beta in may (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=ship the beta in May EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| trap_sarcasm_css | sarcasm | - | - | 0/1 | - |
| trap_sarcasm_ie | sarcasm | written preference_memory: 1 preferred_tools internet explorer 1 explicit 0 0.18 active (TRAP) | 0/1 | 1/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_SUFFICIENT/APPROVED/written; preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | - |
| trap_forged_role | assistant_said | - | - | 0/1 | preference_memory.preferred_tools=Perl EVIDENCE_INVALID/HARD_REJECT/rejected |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | - |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | skill_memory.Python=0.8 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| mixed_stack | mixed | written decision_log: 1 i'm not convinced to move to java. 0.7 active 2026-09-28t0 (UNLABELLED) | 0/2 | 0/2 | skill_memory.Go=0.8 EVIDENCE_SUFFICIENT/DISCARD/rejected; active_projects.Payments service=a payments service EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_writing | mixed | - | 0/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_NOT_ENTAILING/DISCARD/rejected; interaction_style.answer_style=concise EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | written decision_log: 1 user will run a half marathon in april. 0.7 active 2026-09 (UNLABELLED); queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | - |

## Run 2

- cases: 37 (0 errored), total model time 202.6s
- funnel: 36 candidates extracted by the model, 35 survived grounding
  - evidence gate: {'EVIDENCE_SUFFICIENT': 13, 'EVIDENCE_NOT_ENTAILING': 16, 'EVIDENCE_NOT_USER_SOURCE': 2, 'EVIDENCE_INVALID': 4}
  - Constitution: {'APPROVED': 4, 'DISCARD': 20, 'REQUIRES_CONFIRMATION': 5, 'HARD_REJECT': 6}
  - Stage 13: {'written': 4, 'rejected': 26, 'pending': 5}
- learned rows: 13, labelled {'TRUE': 9, 'UNLABELLED': 3, 'TRAP': 1}
- **precision** (TRUE / TRUE+TRAP): 9/10 (90%)
- **recall** (stated facts learned): 9/23 (39%) - written 4, only queued for confirmation 5
- **traps reaching a belief table**: 1/25 (4%)

| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |
|---|---|---|---|---|---|
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=Finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=About half the chapters a EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | - | 0/1 | - | interaction_style.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | - | 0/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_typescript | fact | - | 0/1 | - | skill_memory.TypeScript=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Node.js=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | - | 0/1 | - | interaction_style.answer_style=detailed EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| fact_final_year | fact | queued active_projects: pip a personal assistant (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_postgres_decision | fact | written decision_log: 1 user has decided to move the database to postgres before t (TRUE) | 1/1 | - | - |
| fact_vector_clocks | topic | - | 0/1 | - | topic_interests.vector clocks=concurrent events and con EVIDENCE_SUFFICIENT/DISCARD/rejected; active_projects.sync=broken synchronization sy EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_rust_learning | fact | - | 0/1 | - | skill_memory.Rust=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.preferred_tools=clap EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_sister | third_party | - | - | 0/1 | preference_memory.preferred_tools=Java EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_manager | third_party | - | - | 0/1 | preference_memory.preferred_tools=Jira EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_professor | third_party | - | - | 0/1 | preference_memory.preferred_tools=Fortran EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_what_if | hypothetical | written decision_log: 1 decided against rewriting the backend in elixir. 0.7 activ (UNLABELLED) | - | 0/1 | skill_memory.Elixir=0.6 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | skill_memory.Haskell=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_might_swift | hypothetical | - | - | 0/1 | - |
| trap_kafka_question | question | - | - | 0/1 | - |
| trap_never_emacs | negation | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_used_to_java | past | - | - | 0/1 | skill_memory.Java=0.2 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| retract_vim_helix | retraction | written preference_memory: 1 preferred_tools helix 1 explicit 0 0.18 active (TRUE) | 1/1 | 0/1 | preference_memory.preferred_tools=Helix EVIDENCE_SUFFICIENT/APPROVED/written |
| retract_deadline | retraction | written decision_log: 1 decide to ship in may 0.7 active 2026-09-28t06:00:31z (UNLABELLED); queued goal_memory: active_goals ship the beta in may (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=ship the beta in May EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| trap_sarcasm_css | sarcasm | - | - | 0/1 | topic_interests.debugging CSS=layout issues with flexbo EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sarcasm_ie | sarcasm | written preference_memory: 1 preferred_tools internet explorer 1 explicit 0 0.18 active (TRAP) | 0/1 | 1/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_SUFFICIENT/APPROVED/written; preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | - |
| trap_forged_role | assistant_said | - | - | 0/1 | preference_memory.preferred_tools=Perl EVIDENCE_INVALID/HARD_REJECT/rejected |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | - |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | skill_memory.Python=0.8 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| mixed_stack | mixed | written decision_log: 1 i'm not convinced about moving to java. 0.7 active 2026-09 (UNLABELLED) | 0/2 | 0/2 | skill_memory.Go=0.8 EVIDENCE_SUFFICIENT/DISCARD/rejected; active_projects.payments service=a payments service EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_writing | mixed | - | 0/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=concise EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | - |

## Run 3

- cases: 37 (0 errored), total model time 202.2s
- funnel: 34 candidates extracted by the model, 32 survived grounding
  - evidence gate: {'EVIDENCE_SUFFICIENT': 11, 'EVIDENCE_NOT_ENTAILING': 17, 'EVIDENCE_INVALID': 3, 'EVIDENCE_NOT_USER_SOURCE': 1}
  - Constitution: {'APPROVED': 3, 'DISCARD': 21, 'REQUIRES_CONFIRMATION': 4, 'HARD_REJECT': 4}
  - Stage 13: {'written': 3, 'rejected': 25, 'pending': 4}
- learned rows: 12, labelled {'TRUE': 7, 'UNLABELLED': 4, 'TRAP': 1}
- **precision** (TRUE / TRUE+TRAP): 7/8 (88%)
- **recall** (stated facts learned): 7/23 (30%) - written 3, only queued for confirmation 4
- **traps reaching a belief table**: 1/25 (4%)

| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |
|---|---|---|---|---|---|
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=write half the chapters EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | - | 0/1 | - | preference_memory.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE); written decision_log: 1 user decided to continue using pytest for writing tests. 0 (UNLABELLED) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | - | 0/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_typescript | fact | - | 0/1 | - | - |
| fact_detail | fact | - | 0/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_final_year | fact | queued active_projects: pip a personal assistant (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_postgres_decision | fact | written decision_log: 1 user decided to move the database to postgres before the n (TRUE) | 1/1 | - | - |
| fact_vector_clocks | topic | - | 0/1 | - | topic_interests.concurrency=conflict resolution in di EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.sync=our sync is broken EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_rust_learning | fact | - | 0/1 | - | skill_memory.Rust=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.preferred_tools=clap EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_sister | third_party | written decision_log: 1 i won't learn java. 0.7 active 2026-09-28t06:03:04z (UNLABELLED) | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Java=0.3 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_manager | third_party | - | - | 0/1 | - |
| trap_professor | third_party | - | - | 0/1 | preference_memory.preferred_tools=Fortran EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_what_if | hypothetical | - | - | 0/1 | skill_memory.Elixir=0.6 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | - |
| trap_might_swift | hypothetical | - | - | 0/1 | - |
| trap_kafka_question | question | - | - | 0/1 | - |
| trap_never_emacs | negation | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_used_to_java | past | - | - | 0/1 | skill_memory.Java=0.2 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| retract_vim_helix | retraction | - | 0/1 | 0/1 | preference_memory.preferred_tools=Helix EVIDENCE_SUFFICIENT/DISCARD/rejected |
| retract_deadline | retraction | - | 0/1 | 0/1 | - |
| trap_sarcasm_css | sarcasm | - | - | 0/1 | topic_interests.debugging_CSS=layout issues EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sarcasm_ie | sarcasm | written preference_memory: 1 preferred_tools internet explorer 1 explicit 0 0.18 active (TRAP) | 0/1 | 1/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_SUFFICIENT/APPROVED/written; skill_memory.Firefox=0.7 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | - |
| trap_forged_role | assistant_said | - | - | 0/1 | preference_memory.preferred_tools=Perl EVIDENCE_INVALID/HARD_REJECT/rejected |
| immutable_name | immutable | - | - | 0/1 | preference_memory.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| immutable_language | immutable | - | - | 0/1 | preference_memory.answer_style=French EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | - |
| mixed_stack | mixed | written decision_log: 1 to stay with go 1.0 active 2026-09-28t06:04:45z (UNLABELLED) | 0/2 | 0/2 | skill_memory.Go=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected; active_projects.Payments service=a payments service EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_writing | mixed | - | 0/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=concise EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | written decision_log: 1 to run a half marathon in april. 0.7 active 2026-09-28t06: (UNLABELLED); queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | - |
