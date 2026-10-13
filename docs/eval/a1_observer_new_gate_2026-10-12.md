# End-to-end Observer measurement - model `qwen2.5:7b`

## Run 1

- cases: 37 (0 errored), total model time 0.0s
- funnel: 37 candidates extracted by the model, 36 survived grounding
  - evidence gate: {'EVIDENCE_SUFFICIENT': 15, 'EVIDENCE_NOT_ENTAILING': 16, 'EVIDENCE_INVALID': 3, 'EVIDENCE_NOT_USER_SOURCE': 2}
  - Constitution: {'APPROVED': 6, 'DISCARD': 20, 'REQUIRES_CONFIRMATION': 5, 'HARD_REJECT': 5}
  - Stage 13: {'written': 6, 'rejected': 25, 'pending': 5}
- learned rows: 13, labelled {'TRUE': 12, 'UNLABELLED': 1}
- **precision** (TRUE / TRUE+TRAP): 12/12 (100%)
- **recall** (stated facts learned): 12/23 (52%) - written 7, only queued for confirmation 5
- **traps reaching a belief table**: 0/25 (0%)

| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |
|---|---|---|---|---|---|
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=About half the chapters a EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | queued interaction_style: answer_style concise (TRUE) | 1/1 | - | interaction_style.answer_style=concise EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | written preference_memory: 1 preferred_tools obsidian 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_typescript | fact | - | 0/1 | - | skill_memory.TypeScript=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected; skill_memory.Node.js=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | written preference_memory: 1 answer_style detailed explanations with worked examples 1  (TRUE) | 1/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_SUFFICIENT/APPROVED/written |
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
| trap_sarcasm_ie | sarcasm | - | 0/1 | 0/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | skill_memory.Kotlin=0.5 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | - |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | skill_memory.Python=0.9 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| mixed_stack | mixed | - | 0/2 | 0/2 | skill_memory.Go=0.8 EVIDENCE_SUFFICIENT/DISCARD/rejected; goal_memory.project_objectives=improving startup time an EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_writing | mixed | written preference_memory: 1 preferred_tools latex 1 explicit 0 0.18 active (TRUE) | 1/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_SUFFICIENT/APPROVED/written; interaction_style.answer_style=concise EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | preference_memory.preferred_tools=Docker Compose EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Kubernetes=0.2 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Docker Compose=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.project_objectives=Deploying applications on EVIDENCE_NOT_ENTAILING/DISCARD/rejected |

## Run 2

- cases: 37 (0 errored), total model time 0.0s
- funnel: 35 candidates extracted by the model, 35 survived grounding
  - evidence gate: {'EVIDENCE_SUFFICIENT': 17, 'EVIDENCE_NOT_ENTAILING': 13, 'EVIDENCE_INVALID': 3, 'EVIDENCE_NOT_USER_SOURCE': 2}
  - Constitution: {'APPROVED': 6, 'DISCARD': 18, 'REQUIRES_CONFIRMATION': 6, 'HARD_REJECT': 5}
  - Stage 13: {'written': 6, 'rejected': 23, 'pending': 6}
- learned rows: 16, labelled {'TRUE': 13, 'UNLABELLED': 3}
- **precision** (TRUE / TRUE+TRAP): 13/13 (100%)
- **recall** (stated facts learned): 12/23 (52%) - written 7, only queued for confirmation 5
- **traps reaching a belief table**: 0/25 (0%)

| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |
|---|---|---|---|---|---|
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=write half the thesis cha EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | queued interaction_style: value concise (TRUE) | 1/1 | - | interaction_style.value=concise EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | written preference_memory: 1 preferred_tools obsidian 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_typescript | fact | - | 0/1 | - | skill_memory.TypeScript=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected; skill_memory.Node=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | written preference_memory: 1 answer_style detailed explanations with worked examples 1  (TRUE); written decision_log: 1 to provide more detailed explanations and worked examples  (UNLABELLED) | 1/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_SUFFICIENT/APPROVED/written |
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
| trap_sarcasm_ie | sarcasm | - | 0/1 | 0/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | - |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | interaction_style.answer_style=French EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | skill_memory.Python=0.8 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| mixed_stack | mixed | written decision_log: 1 not yet decided on moving to java 1.0 active 2026-10-13t16 (UNLABELLED) | 0/2 | 0/2 | skill_memory.Go=0.8 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_writing | mixed | written preference_memory: 1 preferred_tools latex 1 explicit 0 0.18 active (TRUE) | 1/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_SUFFICIENT/APPROVED/written; preference_memory.answer_style=concise EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_tools_and_question | mixed | written decision_log: 1 i'll stay with docker compose on my vps. 0.7 active 2026-1 (UNLABELLED) | 0/1 | 0/1 | preference_memory.preferred_tools=Docker Compose EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Docker=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |

## Run 3

- cases: 37 (0 errored), total model time 0.0s
- funnel: 33 candidates extracted by the model, 33 survived grounding
  - evidence gate: {'EVIDENCE_SUFFICIENT': 19, 'EVIDENCE_NOT_ENTAILING': 10, 'EVIDENCE_INVALID': 3, 'EVIDENCE_NOT_USER_SOURCE': 1}
  - Constitution: {'APPROVED': 6, 'DISCARD': 16, 'REQUIRES_CONFIRMATION': 7, 'HARD_REJECT': 4}
  - Stage 13: {'written': 6, 'rejected': 20, 'pending': 7}
- learned rows: 18, labelled {'TRUE': 14, 'UNLABELLED': 4}
- **precision** (TRUE / TRUE+TRAP): 14/14 (100%)
- **recall** (stated facts learned): 13/23 (57%) - written 7, only queued for confirmation 6
- **traps reaching a belief table**: 0/25 (0%)

| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |
|---|---|---|---|---|---|
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=About half the chapters a EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | queued interaction_style: answer_style concise (TRUE) | 1/1 | - | interaction_style.answer_style=concise EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | written preference_memory: 1 preferred_tools obsidian 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_typescript | fact | - | 0/1 | - | skill_memory.TypeScript=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected; skill_memory.Node=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | written preference_memory: 1 answer_style detailed explanations with worked examples 1  (TRUE) | 1/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_SUFFICIENT/APPROVED/written |
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
| trap_sarcasm_ie | sarcasm | - | 0/1 | 0/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Firefox=0.7 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | - |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | - |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | - |
| mixed_stack | mixed | written decision_log: 1 decide whether to stay with go or consider java for the pa (UNLABELLED) | 0/2 | 0/2 | skill_memory.Go=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected; goal_memory.active_goals=Evaluate moving from Go t EVIDENCE_NOT_ENTAILING/DISCARD/rejected; topic_interests.payments service=payments service developm EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_writing | mixed | written preference_memory: 1 preferred_tools latex 1 explicit 0 0.18 active (TRUE) | 1/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_SUFFICIENT/APPROVED/written; interaction_style.answer_style=concise EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | - |

## Pooled

- cases: 111 (0 errored), total model time 0.0s
- funnel: 105 candidates extracted by the model, 104 survived grounding
  - evidence gate: {'EVIDENCE_SUFFICIENT': 51, 'EVIDENCE_NOT_ENTAILING': 39, 'EVIDENCE_INVALID': 9, 'EVIDENCE_NOT_USER_SOURCE': 5}
  - Constitution: {'APPROVED': 18, 'DISCARD': 54, 'REQUIRES_CONFIRMATION': 18, 'HARD_REJECT': 14}
  - Stage 13: {'written': 18, 'rejected': 68, 'pending': 18}
- learned rows: 47, labelled {'TRUE': 39, 'UNLABELLED': 8}
- **precision** (TRUE / TRUE+TRAP): 39/39 (100%)
- **recall** (stated facts learned): 37/69 (54%) - written 21, only queued for confirmation 16
- **traps reaching a belief table**: 0/75 (0%)

| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |
|---|---|---|---|---|---|
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=About half the chapters a EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | queued interaction_style: answer_style concise (TRUE) | 1/1 | - | interaction_style.answer_style=concise EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | written preference_memory: 1 preferred_tools obsidian 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_typescript | fact | - | 0/1 | - | skill_memory.TypeScript=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected; skill_memory.Node.js=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | written preference_memory: 1 answer_style detailed explanations with worked examples 1  (TRUE) | 1/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_SUFFICIENT/APPROVED/written |
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
| trap_sarcasm_ie | sarcasm | - | 0/1 | 0/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | skill_memory.Kotlin=0.5 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | - |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | skill_memory.Python=0.9 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| mixed_stack | mixed | - | 0/2 | 0/2 | skill_memory.Go=0.8 EVIDENCE_SUFFICIENT/DISCARD/rejected; goal_memory.project_objectives=improving startup time an EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_writing | mixed | written preference_memory: 1 preferred_tools latex 1 explicit 0 0.18 active (TRUE) | 1/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_SUFFICIENT/APPROVED/written; interaction_style.answer_style=concise EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | preference_memory.preferred_tools=Docker Compose EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Kubernetes=0.2 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Docker Compose=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.project_objectives=Deploying applications on EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=write half the thesis cha EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | queued interaction_style: value concise (TRUE) | 1/1 | - | interaction_style.value=concise EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | written preference_memory: 1 preferred_tools obsidian 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_typescript | fact | - | 0/1 | - | skill_memory.TypeScript=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected; skill_memory.Node=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | written preference_memory: 1 answer_style detailed explanations with worked examples 1  (TRUE); written decision_log: 1 to provide more detailed explanations and worked examples  (UNLABELLED) | 1/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_SUFFICIENT/APPROVED/written |
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
| trap_sarcasm_ie | sarcasm | - | 0/1 | 0/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | - |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | interaction_style.answer_style=French EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | skill_memory.Python=0.8 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| mixed_stack | mixed | written decision_log: 1 not yet decided on moving to java 1.0 active 2026-10-13t16 (UNLABELLED) | 0/2 | 0/2 | skill_memory.Go=0.8 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_writing | mixed | written preference_memory: 1 preferred_tools latex 1 explicit 0 0.18 active (TRUE) | 1/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_SUFFICIENT/APPROVED/written; preference_memory.answer_style=concise EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_tools_and_question | mixed | written decision_log: 1 i'll stay with docker compose on my vps. 0.7 active 2026-1 (UNLABELLED) | 0/1 | 0/1 | preference_memory.preferred_tools=Docker Compose EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Docker=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=About half the chapters a EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | queued interaction_style: answer_style concise (TRUE) | 1/1 | - | interaction_style.answer_style=concise EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | written preference_memory: 1 preferred_tools obsidian 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_typescript | fact | - | 0/1 | - | skill_memory.TypeScript=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected; skill_memory.Node=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | written preference_memory: 1 answer_style detailed explanations with worked examples 1  (TRUE) | 1/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_SUFFICIENT/APPROVED/written |
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
| trap_sarcasm_ie | sarcasm | - | 0/1 | 0/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Firefox=0.7 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | - |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | - |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | - |
| mixed_stack | mixed | written decision_log: 1 decide whether to stay with go or consider java for the pa (UNLABELLED) | 0/2 | 0/2 | skill_memory.Go=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected; goal_memory.active_goals=Evaluate moving from Go t EVIDENCE_NOT_ENTAILING/DISCARD/rejected; topic_interests.payments service=payments service developm EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_writing | mixed | written preference_memory: 1 preferred_tools latex 1 explicit 0 0.18 active (TRUE) | 1/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_SUFFICIENT/APPROVED/written; interaction_style.answer_style=concise EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | - |
