Run stamp: 2026-10-18T03:49:08+00:00
- commit 1ca8dd4055494b01ffcf59bbbb7f9ac44b7d0b2b, uncommitted changes to tracked files: no
- Constitution version 1.0, sha256 3908bd8df7125990198086b6b0d9c09dc47d38c7ddcb383b28b31184a8328733
- model qwen2.5:7b, digest 845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e; Ollama 0.40.3
- options sent: temperature=not sent, num_ctx=not sent
- transcript_token_cap: 8000
- prompt_hash: "9e3a633b21bb4e2ac71e4d59059f9c6be5e0c54dd73b393eedb71fedbfd55139"
- wall_clock_seconds: [210.5, 190.6, 204.9]
- validity_condition: "Valid for gate-only comparisons; any change to the Observer prompt, the extraction schema, the model or grounding voids it."

# End-to-end Observer measurement - model `qwen2.5:7b`

## Run 1

- cases: 37 (0 errored), total model time 210.5s
- funnel: 40 candidates extracted by the model, 39 survived grounding
  - evidence gate: {'EVIDENCE_SUFFICIENT': 13, 'EVIDENCE_NOT_ENTAILING': 16, 'EVIDENCE_NOT_USER_SOURCE': 3, 'EVIDENCE_INVALID': 4, 'EVIDENCE_NOT_FOUND': 3}
  - Constitution: {'APPROVED': 5, 'DISCARD': 19, 'REQUIRES_CONFIRMATION': 5, 'HARD_REJECT': 10}
  - Stage 13: {'written': 5, 'rejected': 29, 'pending': 5}
- learned rows: 15, labelled {'TRUE': 11, 'UNLABELLED': 4}
- **precision** (TRUE / TRUE+TRAP): 11/11 (100%)
- **recall** (stated facts learned): 10/23 (43%) - written 6, only queued for confirmation 4
- **traps reaching a belief table**: 0/25 (0%)

| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |
|---|---|---|---|---|---|
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected; active_projects.backend services=services built for backen EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=write about half the chap EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | written preference_memory: 1 answer_style concise 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.answer_style=concise EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | written preference_memory: 1 preferred_tools obsidian 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_typescript | fact | - | 0/1 | - | preference_memory.preferred_tools=plain Node EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | written decision_log: 1 increase the detail level of explanations. 0.7 active 2026 (UNLABELLED) | 0/1 | - | interaction_style.answer_style=detailed EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| fact_final_year | fact | queued active_projects: pip a personal assistant (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_postgres_decision | fact | written decision_log: 1 move database to postgres before the next release 0.7 acti (TRUE); queued goal_memory: active_goals move database to postgres before the next relea (TRUE) | 1/1 | - | goal_memory.active_goals=Move database to Postgres EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_vector_clocks | topic | - | 0/1 | - | topic_interests.sync=sync EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_rust_learning | fact | - | 0/1 | - | skill_memory.Rust=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.preferred_tools=clap EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_sister | third_party | - | - | 0/1 | preference_memory.preferred_tools=Java EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Java=0.6 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_manager | third_party | - | - | 0/1 | preference_memory.preferred_tools=Jira EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_professor | third_party | - | - | 0/1 | preference_memory.preferred_tools=Fortran EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_what_if | hypothetical | - | - | 0/1 | skill_memory.Elixir=0.6 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | - |
| trap_might_swift | hypothetical | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_kafka_question | question | - | - | 0/1 | topic_interests.distributed_message_brokers=What's the difference bet EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_never_emacs | negation | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_used_to_java | past | - | - | 0/1 | skill_memory.Java=0.2 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| retract_vim_helix | retraction | - | 0/1 | 0/1 | - |
| retract_deadline | retraction | written decision_log: 1 decide to target may for the beta ship date. 0.7 active 20 (UNLABELLED); queued goal_memory: active_goals ship the beta in may (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=ship the beta in May EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| trap_sarcasm_css | sarcasm | - | - | 0/1 | skill_memory.CSS=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sarcasm_ie | sarcasm | - | 0/1 | 0/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Firefox=0.5 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | - |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | preference_memory.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| immutable_language | immutable | - | - | 0/1 | preference_memory.answer_style=French EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | skill_memory.Python=0.9 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| mixed_stack | mixed | written decision_log: 1 not convinced to move to java 0.7 active 2026-10-18t03:52: (UNLABELLED) | 0/2 | 0/2 | skill_memory.Go=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected; active_projects.Payments service=a backend service for a p EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_writing | mixed | written preference_memory: 1 preferred_tools latex 1 explicit 0 0.18 active (TRUE) | 1/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_SUFFICIENT/APPROVED/written; preference_memory.preferred_tools=Word EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | written decision_log: 1 the user has decided to run a half marathon in april. 0.7  (UNLABELLED) | 0/1 | 0/1 | - |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | preference_memory.answer_style=concise EVIDENCE_NOT_FOUND/HARD_REJECT/rejected; preference_memory.preferred_tools=Docker Compose EVIDENCE_NOT_FOUND/HARD_REJECT/rejected; goal_memory.active_goals=Stay with Docker Compose  EVIDENCE_NOT_FOUND/HARD_REJECT/rejected |

## Run 2

- cases: 37 (0 errored), total model time 190.6s
- funnel: 31 candidates extracted by the model, 29 survived grounding
  - evidence gate: {'EVIDENCE_SUFFICIENT': 14, 'EVIDENCE_NOT_ENTAILING': 10, 'EVIDENCE_INVALID': 3, 'EVIDENCE_NOT_USER_SOURCE': 2}
  - Constitution: {'APPROVED': 6, 'DISCARD': 12, 'REQUIRES_CONFIRMATION': 6, 'HARD_REJECT': 5}
  - Stage 13: {'written': 6, 'rejected': 17, 'pending': 6}
- learned rows: 17, labelled {'TRUE': 13, 'UNLABELLED': 4}
- **precision** (TRUE / TRUE+TRAP): 13/13 (100%)
- **recall** (stated facts learned): 13/23 (57%) - written 7, only queued for confirmation 6
- **traps reaching a belief table**: 0/25 (0%)

| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |
|---|---|---|---|---|---|
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | - | 0/1 | - | - |
| fact_short_answers | fact | queued interaction_style: interaction_style concise (TRUE) | 1/1 | - | interaction_style.interaction_style=concise EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE); written decision_log: 1 user prefers using pytest for testing. 0.7 active 2026-10- (UNLABELLED) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | written preference_memory: 1 preferred_tools obsidian 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_typescript | fact | - | 0/1 | - | - |
| fact_detail | fact | written preference_memory: 1 answer_style detailed explanations with worked examples 1  (TRUE) | 1/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_final_year | fact | queued active_projects: pip a personal assistant (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_postgres_decision | fact | written decision_log: 1 move our database to postgres before the next release 0.7  (TRUE) | 1/1 | - | - |
| fact_vector_clocks | topic | - | 0/1 | - | topic_interests.sync=our sync is broken EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_rust_learning | fact | - | 0/1 | - | skill_memory.Rust=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.preferred_tools=clap EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_sister | third_party | - | - | 0/1 | skill_memory.Java=0.3 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_manager | third_party | - | - | 0/1 | preference_memory.preferred_tools=Jira EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_professor | third_party | - | - | 0/1 | preference_memory.preferred_tools=Fortran EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_what_if | hypothetical | written decision_log: 1 decided not to rewrite the backend in elixir. 0.7 active 2 (UNLABELLED) | - | 0/1 | skill_memory.Elixir=0.6 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | - |
| trap_might_swift | hypothetical | - | - | 0/1 | - |
| trap_kafka_question | question | - | - | 0/1 | - |
| trap_never_emacs | negation | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_used_to_java | past | - | - | 0/1 | skill_memory.Java=0.5 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| retract_vim_helix | retraction | written preference_memory: 1 preferred_tools helix 1 explicit 0 0.18 active (TRUE) | 1/1 | 0/1 | preference_memory.preferred_tools=Helix EVIDENCE_SUFFICIENT/APPROVED/written |
| retract_deadline | retraction | written decision_log: 1 commit to shipping the beta in may 0.7 active 2026-10-18t0 (UNLABELLED); queued goal_memory: active_goals ship the beta in may (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=ship the beta in May EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| trap_sarcasm_css | sarcasm | - | - | 0/1 | - |
| trap_sarcasm_ie | sarcasm | - | 0/1 | 0/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Firefox=0.7 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | - |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | preference_memory.answer_style=French EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | skill_memory.Python=0.9 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| mixed_stack | mixed | queued skill_memory: go 1.0 (TRUE) | 1/2 | 0/2 | skill_memory.Go=1.0 EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; active_projects.Payments service=a backend service for a p EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_writing | mixed | written preference_memory: 1 preferred_tools latex 1 explicit 0 0.18 active (TRUE) | 1/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_SUFFICIENT/APPROVED/written; skill_memory.LaTeX=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | written decision_log: 1 to run a half marathon in april 0.7 active 2026-10-18t03:5 (UNLABELLED); queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | preference_memory.preferred_tools=Docker Compose EVIDENCE_NOT_ENTAILING/DISCARD/rejected |

## Run 3

- cases: 37 (0 errored), total model time 204.9s
- funnel: 39 candidates extracted by the model, 39 survived grounding
  - evidence gate: {'EVIDENCE_SUFFICIENT': 15, 'EVIDENCE_NOT_ENTAILING': 14, 'EVIDENCE_INVALID': 4, 'EVIDENCE_NOT_USER_SOURCE': 4, 'EVIDENCE_NOT_FOUND': 2}
  - Constitution: {'APPROVED': 6, 'DISCARD': 18, 'REQUIRES_CONFIRMATION': 5, 'HARD_REJECT': 10}
  - Stage 13: {'written': 6, 'rejected': 28, 'pending': 5}
- learned rows: 17, labelled {'TRUE': 12, 'UNLABELLED': 5}
- **precision** (TRUE / TRUE+TRAP): 12/12 (100%)
- **recall** (stated facts learned): 12/23 (52%) - written 7, only queued for confirmation 5
- **traps reaching a belief table**: 0/25 (0%)

| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |
|---|---|---|---|---|---|
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=about half the chapters a EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | written preference_memory: 1 answer_style concise 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.answer_style=concise EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | written preference_memory: 1 preferred_tools obsidian 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_SUFFICIENT/APPROVED/written; skill_memory.Obsidian=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_typescript | fact | - | 0/1 | - | preference_memory.preferred_tools=Node EVIDENCE_INVALID/HARD_REJECT/rejected |
| fact_detail | fact | written preference_memory: 1 answer_style detailed explanations with worked examples 1  (TRUE); written decision_log: 1 to provide more detailed explanations and include worked e (UNLABELLED) | 1/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_final_year | fact | queued active_projects: pip a personal assistant (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_postgres_decision | fact | written decision_log: 1 move the database to postgres before the next release 1.0  (TRUE) | 1/1 | - | - |
| fact_vector_clocks | topic | written decision_log: 1 user wants to understand vector clocks for sync issues. 0. (UNLABELLED) | 0/1 | - | topic_interests.sync=sync is broken EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_rust_learning | fact | - | 0/1 | - | skill_memory.Rust=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.preferred_tools=clap EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_sister | third_party | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Java=0.3 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_manager | third_party | - | - | 0/1 | preference_memory.preferred_tools=Jira EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_professor | third_party | - | - | 0/1 | preference_memory.preferred_tools=Fortran EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_what_if | hypothetical | written decision_log: 1 not pursuing rewriting the backend in elixir. 0.7 active 2 (UNLABELLED) | - | 0/1 | skill_memory.Elixir=0.6 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | - |
| trap_might_swift | hypothetical | - | - | 0/1 | - |
| trap_kafka_question | question | - | - | 0/1 | skill_memory.RabbitMQ=0.8 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected; skill_memory.Kafka=0.8 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_never_emacs | negation | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_used_to_java | past | - | - | 0/1 | skill_memory.Java=0.2 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| retract_vim_helix | retraction | - | 0/1 | 0/1 | preference_memory.preferred_tools=Helix EVIDENCE_SUFFICIENT/DISCARD/rejected |
| retract_deadline | retraction | - | 0/1 | 0/1 | - |
| trap_sarcasm_css | sarcasm | - | - | 0/1 | topic_interests.debugging CSS=layout issues EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sarcasm_ie | sarcasm | - | 0/1 | 0/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | - |
| trap_forged_role | assistant_said | - | - | 0/1 | preference_memory.preferred_tools=Perl EVIDENCE_INVALID/HARD_REJECT/rejected |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | preference_memory.answer_style=French EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | skill_memory.Python=0.8 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| mixed_stack | mixed | written decision_log: 1 the user is deciding whether to move to java or stay with  (UNLABELLED) | 0/2 | 0/2 | skill_memory.Go=1.0 EVIDENCE_SUFFICIENT/DISCARD/rejected; active_projects.Payments service=a backend system for a pa EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_writing | mixed | written preference_memory: 1 preferred_tools latex 1 explicit 0 0.18 active (TRUE); queued interaction_style: answer_style concise (TRUE) | 2/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_SUFFICIENT/APPROVED/written; preference_memory.preferred_tools=Word EVIDENCE_NOT_ENTAILING/DISCARD/rejected; interaction_style.answer_style=concise EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_goal_and_maybe | mixed | written decision_log: 1 the user will run a half marathon in april. 0.7 active 202 (UNLABELLED); queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | preference_memory.answer_style=concise EVIDENCE_NOT_FOUND/HARD_REJECT/rejected; interaction_style.concise=concise EVIDENCE_NOT_FOUND/HARD_REJECT/rejected |

## Pooled

- cases: 111 (0 errored), total model time 606.0s
- funnel: 110 candidates extracted by the model, 107 survived grounding
  - evidence gate: {'EVIDENCE_SUFFICIENT': 42, 'EVIDENCE_NOT_ENTAILING': 40, 'EVIDENCE_NOT_USER_SOURCE': 9, 'EVIDENCE_INVALID': 11, 'EVIDENCE_NOT_FOUND': 5}
  - Constitution: {'APPROVED': 17, 'DISCARD': 49, 'REQUIRES_CONFIRMATION': 16, 'HARD_REJECT': 25}
  - Stage 13: {'written': 17, 'rejected': 74, 'pending': 16}
- learned rows: 49, labelled {'TRUE': 36, 'UNLABELLED': 13}
- **precision** (TRUE / TRUE+TRAP): 36/36 (100%)
- **recall** (stated facts learned): 35/69 (51%) - written 20, only queued for confirmation 15
- **traps reaching a belief table**: 0/75 (0%)

| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |
|---|---|---|---|---|---|
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected; active_projects.backend services=services built for backen EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=write about half the chap EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | written preference_memory: 1 answer_style concise 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.answer_style=concise EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | written preference_memory: 1 preferred_tools obsidian 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_typescript | fact | - | 0/1 | - | preference_memory.preferred_tools=plain Node EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | written decision_log: 1 increase the detail level of explanations. 0.7 active 2026 (UNLABELLED) | 0/1 | - | interaction_style.answer_style=detailed EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| fact_final_year | fact | queued active_projects: pip a personal assistant (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_postgres_decision | fact | written decision_log: 1 move database to postgres before the next release 0.7 acti (TRUE); queued goal_memory: active_goals move database to postgres before the next relea (TRUE) | 1/1 | - | goal_memory.active_goals=Move database to Postgres EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_vector_clocks | topic | - | 0/1 | - | topic_interests.sync=sync EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_rust_learning | fact | - | 0/1 | - | skill_memory.Rust=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.preferred_tools=clap EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_sister | third_party | - | - | 0/1 | preference_memory.preferred_tools=Java EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Java=0.6 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_manager | third_party | - | - | 0/1 | preference_memory.preferred_tools=Jira EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_professor | third_party | - | - | 0/1 | preference_memory.preferred_tools=Fortran EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_what_if | hypothetical | - | - | 0/1 | skill_memory.Elixir=0.6 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | - |
| trap_might_swift | hypothetical | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_kafka_question | question | - | - | 0/1 | topic_interests.distributed_message_brokers=What's the difference bet EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_never_emacs | negation | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_used_to_java | past | - | - | 0/1 | skill_memory.Java=0.2 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| retract_vim_helix | retraction | - | 0/1 | 0/1 | - |
| retract_deadline | retraction | written decision_log: 1 decide to target may for the beta ship date. 0.7 active 20 (UNLABELLED); queued goal_memory: active_goals ship the beta in may (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=ship the beta in May EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| trap_sarcasm_css | sarcasm | - | - | 0/1 | skill_memory.CSS=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sarcasm_ie | sarcasm | - | 0/1 | 0/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Firefox=0.5 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | - |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | preference_memory.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| immutable_language | immutable | - | - | 0/1 | preference_memory.answer_style=French EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | skill_memory.Python=0.9 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| mixed_stack | mixed | written decision_log: 1 not convinced to move to java 0.7 active 2026-10-18t03:52: (UNLABELLED) | 0/2 | 0/2 | skill_memory.Go=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected; active_projects.Payments service=a backend service for a p EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_writing | mixed | written preference_memory: 1 preferred_tools latex 1 explicit 0 0.18 active (TRUE) | 1/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_SUFFICIENT/APPROVED/written; preference_memory.preferred_tools=Word EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | written decision_log: 1 the user has decided to run a half marathon in april. 0.7  (UNLABELLED) | 0/1 | 0/1 | - |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | preference_memory.answer_style=concise EVIDENCE_NOT_FOUND/HARD_REJECT/rejected; preference_memory.preferred_tools=Docker Compose EVIDENCE_NOT_FOUND/HARD_REJECT/rejected; goal_memory.active_goals=Stay with Docker Compose  EVIDENCE_NOT_FOUND/HARD_REJECT/rejected |
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | - | 0/1 | - | - |
| fact_short_answers | fact | queued interaction_style: interaction_style concise (TRUE) | 1/1 | - | interaction_style.interaction_style=concise EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE); written decision_log: 1 user prefers using pytest for testing. 0.7 active 2026-10- (UNLABELLED) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | written preference_memory: 1 preferred_tools obsidian 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_typescript | fact | - | 0/1 | - | - |
| fact_detail | fact | written preference_memory: 1 answer_style detailed explanations with worked examples 1  (TRUE) | 1/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_final_year | fact | queued active_projects: pip a personal assistant (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_postgres_decision | fact | written decision_log: 1 move our database to postgres before the next release 0.7  (TRUE) | 1/1 | - | - |
| fact_vector_clocks | topic | - | 0/1 | - | topic_interests.sync=our sync is broken EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_rust_learning | fact | - | 0/1 | - | skill_memory.Rust=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.preferred_tools=clap EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_sister | third_party | - | - | 0/1 | skill_memory.Java=0.3 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_manager | third_party | - | - | 0/1 | preference_memory.preferred_tools=Jira EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_professor | third_party | - | - | 0/1 | preference_memory.preferred_tools=Fortran EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_what_if | hypothetical | written decision_log: 1 decided not to rewrite the backend in elixir. 0.7 active 2 (UNLABELLED) | - | 0/1 | skill_memory.Elixir=0.6 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | - |
| trap_might_swift | hypothetical | - | - | 0/1 | - |
| trap_kafka_question | question | - | - | 0/1 | - |
| trap_never_emacs | negation | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_used_to_java | past | - | - | 0/1 | skill_memory.Java=0.5 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| retract_vim_helix | retraction | written preference_memory: 1 preferred_tools helix 1 explicit 0 0.18 active (TRUE) | 1/1 | 0/1 | preference_memory.preferred_tools=Helix EVIDENCE_SUFFICIENT/APPROVED/written |
| retract_deadline | retraction | written decision_log: 1 commit to shipping the beta in may 0.7 active 2026-10-18t0 (UNLABELLED); queued goal_memory: active_goals ship the beta in may (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=ship the beta in May EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| trap_sarcasm_css | sarcasm | - | - | 0/1 | - |
| trap_sarcasm_ie | sarcasm | - | 0/1 | 0/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Firefox=0.7 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | - |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | preference_memory.answer_style=French EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | skill_memory.Python=0.9 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| mixed_stack | mixed | queued skill_memory: go 1.0 (TRUE) | 1/2 | 0/2 | skill_memory.Go=1.0 EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; active_projects.Payments service=a backend service for a p EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_writing | mixed | written preference_memory: 1 preferred_tools latex 1 explicit 0 0.18 active (TRUE) | 1/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_SUFFICIENT/APPROVED/written; skill_memory.LaTeX=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | written decision_log: 1 to run a half marathon in april 0.7 active 2026-10-18t03:5 (UNLABELLED); queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | preference_memory.preferred_tools=Docker Compose EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.9 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=about half the chapters a EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | written preference_memory: 1 answer_style concise 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.answer_style=concise EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_pytest | fact | written preference_memory: 1 preferred_tools pytest 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=pytest EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_obsidian | fact | written preference_memory: 1 preferred_tools obsidian 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_SUFFICIENT/APPROVED/written; skill_memory.Obsidian=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_typescript | fact | - | 0/1 | - | preference_memory.preferred_tools=Node EVIDENCE_INVALID/HARD_REJECT/rejected |
| fact_detail | fact | written preference_memory: 1 answer_style detailed explanations with worked examples 1  (TRUE); written decision_log: 1 to provide more detailed explanations and include worked e (UNLABELLED) | 1/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_final_year | fact | queued active_projects: pip a personal assistant (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_postgres_decision | fact | written decision_log: 1 move the database to postgres before the next release 1.0  (TRUE) | 1/1 | - | - |
| fact_vector_clocks | topic | written decision_log: 1 user wants to understand vector clocks for sync issues. 0. (UNLABELLED) | 0/1 | - | topic_interests.sync=sync is broken EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_rust_learning | fact | - | 0/1 | - | skill_memory.Rust=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.preferred_tools=clap EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_sister | third_party | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Java=0.3 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_manager | third_party | - | - | 0/1 | preference_memory.preferred_tools=Jira EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_professor | third_party | - | - | 0/1 | preference_memory.preferred_tools=Fortran EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_what_if | hypothetical | written decision_log: 1 not pursuing rewriting the backend in elixir. 0.7 active 2 (UNLABELLED) | - | 0/1 | skill_memory.Elixir=0.6 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | - |
| trap_might_swift | hypothetical | - | - | 0/1 | - |
| trap_kafka_question | question | - | - | 0/1 | skill_memory.RabbitMQ=0.8 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected; skill_memory.Kafka=0.8 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_never_emacs | negation | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_used_to_java | past | - | - | 0/1 | skill_memory.Java=0.2 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| retract_vim_helix | retraction | - | 0/1 | 0/1 | preference_memory.preferred_tools=Helix EVIDENCE_SUFFICIENT/DISCARD/rejected |
| retract_deadline | retraction | - | 0/1 | 0/1 | - |
| trap_sarcasm_css | sarcasm | - | - | 0/1 | topic_interests.debugging CSS=layout issues EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sarcasm_ie | sarcasm | - | 0/1 | 0/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | - |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | - |
| trap_forged_role | assistant_said | - | - | 0/1 | preference_memory.preferred_tools=Perl EVIDENCE_INVALID/HARD_REJECT/rejected |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | preference_memory.answer_style=French EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | skill_memory.Python=0.8 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| mixed_stack | mixed | written decision_log: 1 the user is deciding whether to move to java or stay with  (UNLABELLED) | 0/2 | 0/2 | skill_memory.Go=1.0 EVIDENCE_SUFFICIENT/DISCARD/rejected; active_projects.Payments service=a backend system for a pa EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_writing | mixed | written preference_memory: 1 preferred_tools latex 1 explicit 0 0.18 active (TRUE); queued interaction_style: answer_style concise (TRUE) | 2/2 | 0/2 | preference_memory.preferred_tools=LaTeX EVIDENCE_SUFFICIENT/APPROVED/written; preference_memory.preferred_tools=Word EVIDENCE_NOT_ENTAILING/DISCARD/rejected; interaction_style.answer_style=concise EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_goal_and_maybe | mixed | written decision_log: 1 the user will run a half marathon in april. 0.7 active 202 (UNLABELLED); queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | preference_memory.answer_style=concise EVIDENCE_NOT_FOUND/HARD_REJECT/rejected; interaction_style.concise=concise EVIDENCE_NOT_FOUND/HARD_REJECT/rejected |
