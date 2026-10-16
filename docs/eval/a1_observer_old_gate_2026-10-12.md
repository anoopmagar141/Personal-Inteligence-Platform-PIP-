# End-to-end Observer measurement - model `qwen2.5:7b`

## Run 1

- cases: 37 (0 errored), total model time 0.0s
- funnel: 37 candidates extracted by the model, 36 survived grounding
  - evidence gate: {'EVIDENCE_SUFFICIENT': 11, 'EVIDENCE_NOT_ENTAILING': 20, 'EVIDENCE_INVALID': 3, 'EVIDENCE_NOT_USER_SOURCE': 2}
  - Constitution: {'APPROVED': 4, 'DISCARD': 23, 'REQUIRES_CONFIRMATION': 4, 'HARD_REJECT': 5}
  - Stage 13: {'written': 4, 'rejected': 28, 'pending': 4}
- learned rows: 10, labelled {'TRUE': 8, 'UNLABELLED': 1, 'TRAP': 1}
- **precision** (TRUE / TRUE+TRAP): 8/9 (89%)
- **recall** (stated facts learned): 8/23 (35%) - written 4, only queued for confirmation 4
- **traps reaching a belief table**: 1/25 (4%)

| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |
|---|---|---|---|---|---|
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=About half the chapters a EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | - | 0/1 | - | interaction_style.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | - | 0/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_typescript | fact | - | 0/1 | - | skill_memory.TypeScript=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Node.js=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | - | 0/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_final_year | fact | queued active_projects: pip a personal assistant (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_postgres_decision | fact | written decision_log: 1 move the database to postgres before the next release. 0.7 (TRUE) | 1/1 | - | active_projects.Database Migration=moving the database to Po EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_vector_clocks | topic | - | 0/1 | - | - |
| fact_rust_learning | fact | - | 0/1 | - | skill_memory.Rust=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sister | third_party | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Java=0.5 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_manager | third_party | - | - | 0/1 | preference_memory.preferred_tools=Jira EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_professor | third_party | - | - | 0/1 | preference_memory.preferred_tools=Fortran EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_what_if | hypothetical | written decision_log: 1 decide against rewriting the backend in elixir. 0.7 active (UNLABELLED) | - | 0/1 | skill_memory.Elixir=0.6 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | - |
| trap_might_swift | hypothetical | - | - | 0/1 | - |
| trap_kafka_question | question | - | - | 0/1 | - |
| trap_never_emacs | negation | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_used_to_java | past | - | - | 0/1 | skill_memory.Java=0.5 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| retract_vim_helix | retraction | written preference_memory: 1 preferred_tools helix 1 explicit 0 0.18 active (TRUE) | 1/1 | 0/1 | preference_memory.preferred_tools=Helix EVIDENCE_SUFFICIENT/APPROVED/written |
| retract_deadline | retraction | - | 0/1 | 0/1 | - |
| trap_sarcasm_css | sarcasm | - | - | 0/1 | skill_memory.CSS=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sarcasm_ie | sarcasm | written preference_memory: 1 preferred_tools internet explorer 1 explicit 0 0.18 active (TRAP) | 0/1 | 1/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_SUFFICIENT/APPROVED/written; preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | skill_memory.Kotlin=0.5 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | - |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | skill_memory.Python=0.9 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| mixed_stack | mixed | - | 0/2 | 0/2 | skill_memory.Go=0.8 EVIDENCE_SUFFICIENT/DISCARD/rejected; goal_memory.project_objectives=improving startup time an EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_writing | mixed | - | 0/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_NOT_ENTAILING/DISCARD/rejected; interaction_style.answer_style=concise EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | preference_memory.preferred_tools=Docker Compose EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Kubernetes=0.2 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Docker Compose=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.project_objectives=Deploying applications on EVIDENCE_NOT_ENTAILING/DISCARD/rejected |

## Run 2

- cases: 37 (0 errored), total model time 0.0s
- funnel: 35 candidates extracted by the model, 35 survived grounding
  - evidence gate: {'EVIDENCE_SUFFICIENT': 13, 'EVIDENCE_NOT_ENTAILING': 17, 'EVIDENCE_INVALID': 3, 'EVIDENCE_NOT_USER_SOURCE': 2}
  - Constitution: {'APPROVED': 4, 'DISCARD': 21, 'REQUIRES_CONFIRMATION': 5, 'HARD_REJECT': 5}
  - Stage 13: {'written': 4, 'rejected': 26, 'pending': 5}
- learned rows: 13, labelled {'TRUE': 9, 'UNLABELLED': 3, 'TRAP': 1}
- **precision** (TRUE / TRUE+TRAP): 9/10 (90%)
- **recall** (stated facts learned): 8/23 (35%) - written 4, only queued for confirmation 4
- **traps reaching a belief table**: 1/25 (4%)

| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |
|---|---|---|---|---|---|
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=write half the thesis cha EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | - | 0/1 | - | interaction_style.value=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | - | 0/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_typescript | fact | - | 0/1 | - | skill_memory.TypeScript=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Node=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | written decision_log: 1 to provide more detailed explanations and worked examples  (UNLABELLED) | 0/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_final_year | fact | queued active_projects: pip a personal assistant (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_postgres_decision | fact | written decision_log: 1 move database to postgres before the next release 0.7 acti (TRUE); queued goal_memory: active_goals move database to postgres before the next relea (TRUE) | 1/1 | - | goal_memory.active_goals=Move database to Postgres EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_vector_clocks | topic | - | 0/1 | - | topic_interests.sync=sync EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_rust_learning | fact | - | 0/1 | - | skill_memory.Rust=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.preferred_tools=clap EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_sister | third_party | - | - | 0/1 | preference_memory.preferred_tools=Java EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Java=0.5 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_manager | third_party | - | - | 0/1 | preference_memory.preferred_tools=Jira EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_professor | third_party | - | - | 0/1 | preference_memory.preferred_tools=Fortran EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_what_if | hypothetical | - | - | 0/1 | skill_memory.Elixir=0.6 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_might_swift | hypothetical | - | - | 0/1 | - |
| trap_kafka_question | question | - | - | 0/1 | - |
| trap_never_emacs | negation | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_used_to_java | past | - | - | 0/1 | skill_memory.Java=0.2 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| retract_vim_helix | retraction | written preference_memory: 1 preferred_tools helix 1 explicit 0 0.18 active (TRUE) | 1/1 | 0/1 | preference_memory.preferred_tools=Helix EVIDENCE_SUFFICIENT/APPROVED/written |
| retract_deadline | retraction | - | 0/1 | 0/1 | - |
| trap_sarcasm_css | sarcasm | - | - | 0/1 | - |
| trap_sarcasm_ie | sarcasm | written preference_memory: 1 preferred_tools internet explorer 1 explicit 0 0.18 active (TRAP) | 0/1 | 1/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_SUFFICIENT/APPROVED/written; preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | - |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | interaction_style.answer_style=French EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | skill_memory.Python=0.8 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| mixed_stack | mixed | written decision_log: 1 not yet decided on moving to java 1.0 active 2026-10-12t17 (UNLABELLED) | 0/2 | 0/2 | skill_memory.Go=0.8 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_writing | mixed | - | 0/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=concise EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_tools_and_question | mixed | written decision_log: 1 i'll stay with docker compose on my vps. 0.7 active 2026-1 (UNLABELLED) | 0/1 | 0/1 | preference_memory.preferred_tools=Docker Compose EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Docker=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |

## Run 3

- cases: 37 (0 errored), total model time 0.0s
- funnel: 33 candidates extracted by the model, 33 survived grounding
  - evidence gate: {'EVIDENCE_SUFFICIENT': 15, 'EVIDENCE_NOT_ENTAILING': 14, 'EVIDENCE_INVALID': 3, 'EVIDENCE_NOT_USER_SOURCE': 1}
  - Constitution: {'APPROVED': 4, 'DISCARD': 19, 'REQUIRES_CONFIRMATION': 6, 'HARD_REJECT': 4}
  - Stage 13: {'written': 4, 'rejected': 23, 'pending': 6}
- learned rows: 15, labelled {'TRUE': 10, 'UNLABELLED': 4, 'TRAP': 1}
- **precision** (TRUE / TRUE+TRAP): 10/11 (91%)
- **recall** (stated facts learned): 9/23 (39%) - written 4, only queued for confirmation 5
- **traps reaching a belief table**: 1/25 (4%)

| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |
|---|---|---|---|---|---|
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=About half the chapters a EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | - | 0/1 | - | interaction_style.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | - | 0/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_typescript | fact | - | 0/1 | - | skill_memory.TypeScript=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Node=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | - | 0/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_final_year | fact | queued active_projects: pip a personal assistant (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_postgres_decision | fact | written decision_log: 1 move database to postgres before the next release. 1.0 act (TRUE); queued goal_memory: active_goals move database to postgres before the next relea (TRUE) | 1/1 | - | goal_memory.active_goals=move database to Postgres EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_vector_clocks | topic | - | 0/1 | - | topic_interests.sync=our sync is broken EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_rust_learning | fact | - | 0/1 | - | skill_memory.Rust=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.preferred_tools=clap EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_sister | third_party | - | - | 0/1 | skill_memory.Java=0.5 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_manager | third_party | - | - | 0/1 | preference_memory.preferred_tools=Jira EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_professor | third_party | - | - | 0/1 | preference_memory.preferred_tools=Fortran EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_what_if | hypothetical | written decision_log: 1 decided not to rewrite the backend in elixir. 0.7 active 2 (UNLABELLED) | - | 0/1 | skill_memory.Elixir=0.6 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | - |
| trap_might_swift | hypothetical | - | - | 0/1 | - |
| trap_kafka_question | question | - | - | 0/1 | - |
| trap_never_emacs | negation | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_used_to_java | past | - | - | 0/1 | skill_memory.Java=0.3 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| retract_vim_helix | retraction | written preference_memory: 1 preferred_tools helix 1 explicit 0 0.18 active (TRUE); written decision_log: 1 scratched the decision to use neovim for everything. 0.7 a (UNLABELLED) | 1/1 | 0/1 | preference_memory.preferred_tools=Helix EVIDENCE_SUFFICIENT/APPROVED/written |
| retract_deadline | retraction | written decision_log: 1 decide to target may for beta release 0.7 active 2026-10-1 (UNLABELLED); queued goal_memory: active_goals ship the beta in may (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=ship the beta in May EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| trap_sarcasm_css | sarcasm | - | - | 0/1 | skill_memory.CSS=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sarcasm_ie | sarcasm | written preference_memory: 1 preferred_tools internet explorer 1 explicit 0 0.18 active (TRAP) | 0/1 | 1/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_SUFFICIENT/APPROVED/written; skill_memory.Firefox=0.7 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | - |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | - |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | - |
| mixed_stack | mixed | written decision_log: 1 decide whether to stay with go or consider java for the pa (UNLABELLED) | 0/2 | 0/2 | skill_memory.Go=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected; goal_memory.active_goals=Evaluate moving from Go t EVIDENCE_NOT_ENTAILING/DISCARD/rejected; topic_interests.payments service=payments service developm EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_writing | mixed | - | 0/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_NOT_ENTAILING/DISCARD/rejected; interaction_style.answer_style=concise EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | - |

## Pooled

- cases: 111 (0 errored), total model time 0.0s
- funnel: 105 candidates extracted by the model, 104 survived grounding
  - evidence gate: {'EVIDENCE_SUFFICIENT': 39, 'EVIDENCE_NOT_ENTAILING': 51, 'EVIDENCE_INVALID': 9, 'EVIDENCE_NOT_USER_SOURCE': 5}
  - Constitution: {'APPROVED': 12, 'DISCARD': 63, 'REQUIRES_CONFIRMATION': 15, 'HARD_REJECT': 14}
  - Stage 13: {'written': 12, 'rejected': 77, 'pending': 15}
- learned rows: 38, labelled {'TRUE': 27, 'UNLABELLED': 8, 'TRAP': 3}
- **precision** (TRUE / TRUE+TRAP): 27/30 (90%)
- **recall** (stated facts learned): 25/69 (36%) - written 12, only queued for confirmation 13
- **traps reaching a belief table**: 3/75 (4%)

| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |
|---|---|---|---|---|---|
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=About half the chapters a EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | - | 0/1 | - | interaction_style.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | - | 0/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_typescript | fact | - | 0/1 | - | skill_memory.TypeScript=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Node.js=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | - | 0/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_final_year | fact | queued active_projects: pip a personal assistant (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_postgres_decision | fact | written decision_log: 1 move the database to postgres before the next release. 0.7 (TRUE) | 1/1 | - | active_projects.Database Migration=moving the database to Po EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_vector_clocks | topic | - | 0/1 | - | - |
| fact_rust_learning | fact | - | 0/1 | - | skill_memory.Rust=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sister | third_party | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Java=0.5 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_manager | third_party | - | - | 0/1 | preference_memory.preferred_tools=Jira EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_professor | third_party | - | - | 0/1 | preference_memory.preferred_tools=Fortran EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_what_if | hypothetical | written decision_log: 1 decide against rewriting the backend in elixir. 0.7 active (UNLABELLED) | - | 0/1 | skill_memory.Elixir=0.6 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | - |
| trap_might_swift | hypothetical | - | - | 0/1 | - |
| trap_kafka_question | question | - | - | 0/1 | - |
| trap_never_emacs | negation | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_used_to_java | past | - | - | 0/1 | skill_memory.Java=0.5 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| retract_vim_helix | retraction | written preference_memory: 1 preferred_tools helix 1 explicit 0 0.18 active (TRUE) | 1/1 | 0/1 | preference_memory.preferred_tools=Helix EVIDENCE_SUFFICIENT/APPROVED/written |
| retract_deadline | retraction | - | 0/1 | 0/1 | - |
| trap_sarcasm_css | sarcasm | - | - | 0/1 | skill_memory.CSS=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sarcasm_ie | sarcasm | written preference_memory: 1 preferred_tools internet explorer 1 explicit 0 0.18 active (TRAP) | 0/1 | 1/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_SUFFICIENT/APPROVED/written; preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | skill_memory.Kotlin=0.5 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | - |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | skill_memory.Python=0.9 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| mixed_stack | mixed | - | 0/2 | 0/2 | skill_memory.Go=0.8 EVIDENCE_SUFFICIENT/DISCARD/rejected; goal_memory.project_objectives=improving startup time an EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_writing | mixed | - | 0/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_NOT_ENTAILING/DISCARD/rejected; interaction_style.answer_style=concise EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | preference_memory.preferred_tools=Docker Compose EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Kubernetes=0.2 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Docker Compose=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.project_objectives=Deploying applications on EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=write half the thesis cha EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | - | 0/1 | - | interaction_style.value=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | - | 0/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_typescript | fact | - | 0/1 | - | skill_memory.TypeScript=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Node=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | written decision_log: 1 to provide more detailed explanations and worked examples  (UNLABELLED) | 0/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_final_year | fact | queued active_projects: pip a personal assistant (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_postgres_decision | fact | written decision_log: 1 move database to postgres before the next release 0.7 acti (TRUE); queued goal_memory: active_goals move database to postgres before the next relea (TRUE) | 1/1 | - | goal_memory.active_goals=Move database to Postgres EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_vector_clocks | topic | - | 0/1 | - | topic_interests.sync=sync EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_rust_learning | fact | - | 0/1 | - | skill_memory.Rust=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.preferred_tools=clap EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_sister | third_party | - | - | 0/1 | preference_memory.preferred_tools=Java EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Java=0.5 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_manager | third_party | - | - | 0/1 | preference_memory.preferred_tools=Jira EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_professor | third_party | - | - | 0/1 | preference_memory.preferred_tools=Fortran EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_what_if | hypothetical | - | - | 0/1 | skill_memory.Elixir=0.6 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_might_swift | hypothetical | - | - | 0/1 | - |
| trap_kafka_question | question | - | - | 0/1 | - |
| trap_never_emacs | negation | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_used_to_java | past | - | - | 0/1 | skill_memory.Java=0.2 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| retract_vim_helix | retraction | written preference_memory: 1 preferred_tools helix 1 explicit 0 0.18 active (TRUE) | 1/1 | 0/1 | preference_memory.preferred_tools=Helix EVIDENCE_SUFFICIENT/APPROVED/written |
| retract_deadline | retraction | - | 0/1 | 0/1 | - |
| trap_sarcasm_css | sarcasm | - | - | 0/1 | - |
| trap_sarcasm_ie | sarcasm | written preference_memory: 1 preferred_tools internet explorer 1 explicit 0 0.18 active (TRAP) | 0/1 | 1/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_SUFFICIENT/APPROVED/written; preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | - |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | interaction_style.answer_style=French EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | skill_memory.Python=0.8 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| mixed_stack | mixed | written decision_log: 1 not yet decided on moving to java 1.0 active 2026-10-12t17 (UNLABELLED) | 0/2 | 0/2 | skill_memory.Go=0.8 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_writing | mixed | - | 0/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=concise EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_tools_and_question | mixed | written decision_log: 1 i'll stay with docker compose on my vps. 0.7 active 2026-1 (UNLABELLED) | 0/1 | 0/1 | preference_memory.preferred_tools=Docker Compose EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Docker=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=About half the chapters a EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | - | 0/1 | - | interaction_style.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | - | 0/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_typescript | fact | - | 0/1 | - | skill_memory.TypeScript=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Node=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | - | 0/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_final_year | fact | queued active_projects: pip a personal assistant (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_postgres_decision | fact | written decision_log: 1 move database to postgres before the next release. 1.0 act (TRUE); queued goal_memory: active_goals move database to postgres before the next relea (TRUE) | 1/1 | - | goal_memory.active_goals=move database to Postgres EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_vector_clocks | topic | - | 0/1 | - | topic_interests.sync=our sync is broken EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_rust_learning | fact | - | 0/1 | - | skill_memory.Rust=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.preferred_tools=clap EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_sister | third_party | - | - | 0/1 | skill_memory.Java=0.5 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_manager | third_party | - | - | 0/1 | preference_memory.preferred_tools=Jira EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_professor | third_party | - | - | 0/1 | preference_memory.preferred_tools=Fortran EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_what_if | hypothetical | written decision_log: 1 decided not to rewrite the backend in elixir. 0.7 active 2 (UNLABELLED) | - | 0/1 | skill_memory.Elixir=0.6 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | - |
| trap_might_swift | hypothetical | - | - | 0/1 | - |
| trap_kafka_question | question | - | - | 0/1 | - |
| trap_never_emacs | negation | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_used_to_java | past | - | - | 0/1 | skill_memory.Java=0.3 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| retract_vim_helix | retraction | written preference_memory: 1 preferred_tools helix 1 explicit 0 0.18 active (TRUE); written decision_log: 1 scratched the decision to use neovim for everything. 0.7 a (UNLABELLED) | 1/1 | 0/1 | preference_memory.preferred_tools=Helix EVIDENCE_SUFFICIENT/APPROVED/written |
| retract_deadline | retraction | written decision_log: 1 decide to target may for beta release 0.7 active 2026-10-1 (UNLABELLED); queued goal_memory: active_goals ship the beta in may (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=ship the beta in May EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| trap_sarcasm_css | sarcasm | - | - | 0/1 | skill_memory.CSS=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sarcasm_ie | sarcasm | written preference_memory: 1 preferred_tools internet explorer 1 explicit 0 0.18 active (TRAP) | 0/1 | 1/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_SUFFICIENT/APPROVED/written; skill_memory.Firefox=0.7 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | - |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | - |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | - |
| mixed_stack | mixed | written decision_log: 1 decide whether to stay with go or consider java for the pa (UNLABELLED) | 0/2 | 0/2 | skill_memory.Go=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected; goal_memory.active_goals=Evaluate moving from Go t EVIDENCE_NOT_ENTAILING/DISCARD/rejected; topic_interests.payments service=payments service developm EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_writing | mixed | - | 0/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_NOT_ENTAILING/DISCARD/rejected; interaction_style.answer_style=concise EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | - |
