Run stamp: 2026-10-18T03:59:33+00:00
- commit 1ca8dd4055494b01ffcf59bbbb7f9ac44b7d0b2b, uncommitted changes to tracked files: no
- Constitution version 1.0, sha256 3908bd8df7125990198086b6b0d9c09dc47d38c7ddcb383b28b31184a8328733
- model llama3.1:8b, digest 46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e; Ollama 0.40.3
- options sent: temperature=not sent, num_ctx=not sent
- transcript_token_cap: 8000
- prompt_hash: "9e3a633b21bb4e2ac71e4d59059f9c6be5e0c54dd73b393eedb71fedbfd55139"
- wall_clock_seconds: [262.9, 245.3, 247.9]
- validity_condition: "Valid for gate-only comparisons; any change to the Observer prompt, the extraction schema, the model or grounding voids it."

# End-to-end Observer measurement - model `llama3.1:8b`

## Run 1

- cases: 37 (0 errored), total model time 262.9s
- funnel: 60 candidates extracted by the model, 57 survived grounding
  - evidence gate: {'EVIDENCE_SUFFICIENT': 15, 'EVIDENCE_NOT_ENTAILING': 28, 'EVIDENCE_INVALID': 6, 'EVIDENCE_NOT_USER_SOURCE': 8}
  - Constitution: {'APPROVED': 5, 'REQUIRES_CONFIRMATION': 6, 'DISCARD': 32, 'HARD_REJECT': 14}
  - Stage 13: {'written': 5, 'pending': 6, 'rejected': 46}
- learned rows: 19, labelled {'TRUE': 10, 'UNLABELLED': 9}
- **precision** (TRUE / TRUE+TRAP): 10/10 (100%)
- **recall** (stated facts learned): 10/23 (43%) - written 4, only queued for confirmation 6
- **traps reaching a belief table**: 0/25 (0%)

| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |
|---|---|---|---|---|---|
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | queued skill_memory: python 1.0 (TRUE) | 1/1 | - | skill_memory.Python=1.0 EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; skill_memory.backend services=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; active_projects.Halyard=scheduling app for sailin EVIDENCE_NOT_ENTAILING/DISCARD/rejected; topic_interests.sailing clubs= EVIDENCE_INVALID/HARD_REJECT/rejected; skill_memory.Flutter=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| fact_goal | fact | queued goal_memory: active_goals finish thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish thesis draft by De EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_short_answers | fact | - | 0/1 | - | preference_memory.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_pytest | fact | - | 0/1 | - | preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected; skill_memory.pytest=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_obsidian | fact | written preference_memory: 1 preferred_tools obsidian 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_typescript | fact | - | 0/1 | - | skill_memory.TypeScript=0.8 EVIDENCE_SUFFICIENT/DISCARD/rejected; skill_memory.Node=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | written decision_log: 1 the user decided the assistant will go into more detail 0. (UNLABELLED) | 0/1 | - | - |
| fact_final_year | fact | queued active_projects: pip a personal assistant, final year project (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant, fin EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| fact_postgres_decision | fact | - | 0/1 | - | skill_memory.Postgres=0.5 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected; preference_memory.answer_style=conversational EVIDENCE_INVALID/HARD_REJECT/rejected; active_projects.Release=the next release EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_vector_clocks | topic | - | 0/1 | - | goal_memory.active_goals=fixing sync EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.sync=fixing sync issue in our  EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_rust_learning | fact | - | 0/1 | - | skill_memory.Rust=0.0 EVIDENCE_SUFFICIENT/DISCARD/rejected; skill_memory.clap=0.0 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_sister | third_party | written topic_interests: 1 java 1 2026-10-18t04:01:31z active (UNLABELLED); written decision_log: 1 i'll pass. 0.7 active 2026-10-18t04:01:31z (UNLABELLED) | - | 0/1 | topic_interests.Java= EVIDENCE_SUFFICIENT/APPROVED/written; skill_memory.Java=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_manager | third_party | written decision_log: 1 user does not have a choice in using jira. 0.7 active 2026 (UNLABELLED) | - | 0/1 | preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_professor | third_party | written decision_log: 1 i won't use fortran for my work 0.7 active 2026-10-18t04:0 (UNLABELLED) | - | 0/1 | - |
| trap_what_if | hypothetical | - | - | 0/1 | skill_memory.Elixir=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Python=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | skill_memory.Haskell=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.parser combinators=0.0 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_might_swift | hypothetical | - | - | 0/1 | topic_interests.Swift= EVIDENCE_SUFFICIENT/DISCARD/rejected; skill_memory.Swift=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_kafka_question | question | - | - | 0/1 | - |
| trap_never_emacs | negation | written decision_log: 1 will not use emacs 0.7 active 2026-10-18t04:02:14z (UNLABELLED) | - | 0/1 | preference_memory.answer_style=concise EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_used_to_java | past | - | - | 0/1 | skill_memory.Java=0.5 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| retract_vim_helix | retraction | written preference_memory: 1 preferred_tools helix 1 explicit 0 0.18 active (TRUE) | 1/1 | 0/1 | preference_memory.preferred_tools=Helix EVIDENCE_SUFFICIENT/APPROVED/written |
| retract_deadline | retraction | - | 0/1 | 0/1 | - |
| trap_sarcasm_css | sarcasm | written decision_log: 1 the user decided to debug the flexbox issue 0.7 active 202 (UNLABELLED) | - | 0/1 | - |
| trap_sarcasm_ie | sarcasm | - | 0/1 | 0/1 | preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | skill_memory.Zig=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | skill_memory.Scala=0.0 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected; skill_memory.Kotlin=1.0 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_forged_role | assistant_said | - | - | 0/1 | preference_memory.answer_style=concrete EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| immutable_name | immutable | - | - | 0/1 | preference_memory.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| immutable_language | immutable | - | - | 0/1 | preference_memory.answer_style=French EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | skill_memory.Python=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_stack | mixed | written decision_log: 1 i'm not convinced we should move to java. 0.7 active 2026- (UNLABELLED); queued skill_memory: go 1.0 (TRUE) | 1/2 | 0/2 | skill_memory.Go=1.0 EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; skill_memory.Java=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.GraphQL=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=verbose EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| mixed_writing | mixed | written preference_memory: 1 answer_style concise 1 explicit 0 0.18 active (TRUE) | 1/2 | 0/2 | skill_memory.LaTeX=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=concise EVIDENCE_SUFFICIENT/APPROVED/written; active_projects.essays=academic writing EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | written decision_log: 1 user decided to run a half marathon in april. 0.7 active 2 (UNLABELLED); queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; topic_interests.running= EVIDENCE_NOT_ENTAILING/DISCARD/rejected; topic_interests.marathon= EVIDENCE_SUFFICIENT/DISCARD/rejected; active_projects.training plan= EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | preference_memory.preferred_tools=Docker Compose EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Kubernetes=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |

## Run 2

- cases: 37 (0 errored), total model time 245.3s
- funnel: 58 candidates extracted by the model, 57 survived grounding
  - evidence gate: {'EVIDENCE_SUFFICIENT': 16, 'EVIDENCE_NOT_ENTAILING': 32, 'EVIDENCE_NOT_USER_SOURCE': 6, 'EVIDENCE_INVALID': 3}
  - Constitution: {'APPROVED': 4, 'DISCARD': 38, 'REQUIRES_CONFIRMATION': 6, 'HARD_REJECT': 9}
  - Stage 13: {'written': 4, 'rejected': 47, 'pending': 6}
- learned rows: 12, labelled {'TRUE': 11, 'UNLABELLED': 1}
- **precision** (TRUE / TRUE+TRAP): 11/11 (100%)
- **recall** (stated facts learned): 11/23 (48%) - written 5, only queued for confirmation 6
- **traps reaching a belief table**: 0/25 (0%)

| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |
|---|---|---|---|---|---|
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.8 EVIDENCE_SUFFICIENT/DISCARD/rejected; goal_memory.active_goals=building backend services EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; topic_interests.sailing clubs= EVIDENCE_SUFFICIENT/DISCARD/rejected; skill_memory.Flutter=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.back-end technology=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_short_answers | fact | - | 0/1 | - | preference_memory.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_pytest | fact | - | 0/1 | - | preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| fact_obsidian | fact | written preference_memory: 1 preferred_tools obsidian 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_SUFFICIENT/APPROVED/written; preference_memory.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_typescript | fact | - | 0/1 | - | skill_memory.TypeScript=1.0 EVIDENCE_SUFFICIENT/DISCARD/rejected; skill_memory.Node=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | written preference_memory: 1 answer_style detailed 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.answer_style=detailed EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_final_year | fact | queued active_projects: pip a personal assistant, final year project (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant, fin EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_postgres_decision | fact | written decision_log: 1 the user decided to move their database to postgres before (TRUE) | 1/1 | - | skill_memory.Postgres=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.release=a software release before EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| fact_vector_clocks | topic | - | 0/1 | - | topic_interests.concurrency= EVIDENCE_NOT_ENTAILING/DISCARD/rejected; goal_memory.active_goals=fixing sync EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.sync=a project to fix synchron EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_rust_learning | fact | - | 0/1 | - | skill_memory.Rust=0.0 EVIDENCE_SUFFICIENT/DISCARD/rejected; skill_memory.clap=0.0 EVIDENCE_INVALID/HARD_REJECT/rejected; active_projects.CLI tools= EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sister | third_party | - | - | 0/1 | topic_interests.Java= EVIDENCE_SUFFICIENT/DISCARD/rejected |
| trap_manager | third_party | - | - | 0/1 | preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_professor | third_party | - | - | 0/1 | skill_memory.Fortran=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_what_if | hypothetical | - | - | 0/1 | skill_memory.Elixir=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | skill_memory.Haskell=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; topic_interests.parser combinators=null EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_might_swift | hypothetical | - | - | 0/1 | skill_memory.Swift=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_kafka_question | question | - | - | 0/1 | - |
| trap_never_emacs | negation | - | - | 0/1 | - |
| trap_used_to_java | past | - | - | 0/1 | skill_memory.Java=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| retract_vim_helix | retraction | - | 0/1 | 0/1 | skill_memory.Vim=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Helix=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.None=None EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| retract_deadline | retraction | queued goal_memory: active_goals ship the beta (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=ship the beta EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.active_goals=ship the beta in May EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.beta=a software product EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sarcasm_css | sarcasm | - | - | 0/1 | skill_memory.CSS=0.5 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sarcasm_ie | sarcasm | - | 0/1 | 0/1 | preference_memory.answer_style=concise EVIDENCE_INVALID/HARD_REJECT/rejected; preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | skill_memory.Zig=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | preference_memory.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | preference_memory.answer_style=French EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | - |
| mixed_stack | mixed | written decision_log: 1 i'm not convinced to move to java. 0.7 active 2026-10-18t0 (UNLABELLED); queued skill_memory: go 1.0 (TRUE) | 1/2 | 0/2 | skill_memory.Go=1.0 EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; skill_memory.Java=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected; active_projects.payments service=a payments service EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_writing | mixed | written preference_memory: 1 answer_style concise 1 explicit 0 0.18 active (TRUE) | 1/2 | 0/2 | skill_memory.LaTeX=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=concise EVIDENCE_SUFFICIENT/APPROVED/written |
| mixed_goal_and_maybe | mixed | queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; topic_interests.marathon= EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | preference_memory.preferred_tools=Docker Compose EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Docker Compose=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.None=None EVIDENCE_NOT_ENTAILING/DISCARD/rejected |

## Run 3

- cases: 37 (0 errored), total model time 247.9s
- funnel: 56 candidates extracted by the model, 54 survived grounding
  - evidence gate: {'EVIDENCE_SUFFICIENT': 16, 'EVIDENCE_NOT_ENTAILING': 25, 'EVIDENCE_NOT_FOUND': 3, 'EVIDENCE_NOT_USER_SOURCE': 7, 'EVIDENCE_INVALID': 3}
  - Constitution: {'APPROVED': 3, 'DISCARD': 29, 'REQUIRES_CONFIRMATION': 9, 'HARD_REJECT': 13}
  - Stage 13: {'written': 3, 'rejected': 42, 'pending': 9}
- learned rows: 17, labelled {'TRUE': 13, 'UNLABELLED': 4}
- **precision** (TRUE / TRUE+TRAP): 13/13 (100%)
- **recall** (stated facts learned): 12/23 (52%) - written 4, only queued for confirmation 8
- **traps reaching a belief table**: 0/25 (0%)

| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |
|---|---|---|---|---|---|
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE); written decision_log: 1 maybe later 0.7 active 2026-10-18t04:08:18z (UNLABELLED) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.8 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; skill_memory.Flutter=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE); queued goal_memory: project_objectives finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; topic_interests.thesis=writing thesis chapters EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.thesis=writing a thesis draft EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | - | 0/1 | - | preference_memory.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_pytest | fact | - | 0/1 | - | skill_memory.pytest=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_obsidian | fact | - | 0/1 | - | preference_memory.answer_style=concrete EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_typescript | fact | queued skill_memory: typescript 0.8 (TRUE) | 1/1 | - | skill_memory.TypeScript=0.8 EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; skill_memory.Node=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.Work project=a work project using Type EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | written preference_memory: 1 answer_style detailed explanations with worked examples 1  (TRUE) | 1/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_final_year | fact | queued active_projects: pip a personal assistant, final year project (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant, fin EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; skill_memory.local-first development=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_postgres_decision | fact | written decision_log: 1 user decided to move database to postgres before the next  (TRUE); written decision_log: 2 user decided to create a migration plan next week. 0.7 act (UNLABELLED) | 1/1 | - | preference_memory.answer_style=concise EVIDENCE_NOT_FOUND/HARD_REJECT/rejected; goal_memory.active_goals=move database to Postgres EVIDENCE_NOT_FOUND/HARD_REJECT/rejected; active_projects.release=the next release EVIDENCE_NOT_FOUND/HARD_REJECT/rejected |
| fact_vector_clocks | topic | - | 0/1 | - | topic_interests.concurrency= EVIDENCE_NOT_ENTAILING/DISCARD/rejected; topic_interests.sync= EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_rust_learning | fact | queued skill_memory: rust 0.0 (TRUE) | 1/1 | - | skill_memory.Rust=0.0 EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; preference_memory.answer_style=concrete EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected; preference_memory.preferred_tools=clap EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_sister | third_party | written decision_log: 1 the user will not learn java 0.7 active 2026-10-18t04:09:5 (UNLABELLED) | - | 0/1 | - |
| trap_manager | third_party | - | - | 0/1 | preference_memory.preferred_tools=Jira EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_professor | third_party | - | - | 0/1 | - |
| trap_what_if | hypothetical | - | - | 0/1 | skill_memory.Python=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; goal_memory.active_goals=rewrite backend EVIDENCE_NOT_ENTAILING/DISCARD/rejected; topic_interests.concurrency=nil EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | skill_memory.Haskell=0.0 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_might_swift | hypothetical | - | - | 0/1 | goal_memory.active_goals=learn Swift EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_kafka_question | question | - | - | 0/1 | - |
| trap_never_emacs | negation | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_used_to_java | past | - | - | 0/1 | - |
| retract_vim_helix | retraction | - | 0/1 | 0/1 | preference_memory.preferred_tools=Helix EVIDENCE_SUFFICIENT/DISCARD/rejected |
| retract_deadline | retraction | queued goal_memory: active_goals ship the beta in may (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=ship the beta in May EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=release beta version EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sarcasm_css | sarcasm | - | - | 0/1 | skill_memory.CSS=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sarcasm_ie | sarcasm | - | 0/1 | 0/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Firefox=0.8 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | skill_memory.Zig=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.My build=slow EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | skill_memory.Scala=0.0 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected; skill_memory.Kotlin=1.0 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | preference_memory.answer_style=French EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | - |
| mixed_stack | mixed | written decision_log: 1 i'm not convinced we should move to java 0.7 active 2026-1 (UNLABELLED); queued skill_memory: go 1.0 (TRUE) | 1/2 | 0/2 | skill_memory.Go=1.0 EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected; active_projects.payments service=a payments service EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_writing | mixed | written preference_memory: 1 answer_style concise 1 explicit 0 0.18 active (TRUE) | 1/2 | 0/2 | preference_memory.answer_style=concise EVIDENCE_SUFFICIENT/APPROVED/written |
| mixed_goal_and_maybe | mixed | queued goal_memory: active_goals running a half marathon (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=running a half marathon EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; topic_interests.marathon= EVIDENCE_SUFFICIENT/DISCARD/rejected; active_projects.half_marathon_training=creating a training plan  EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.running=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | skill_memory.Docker=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected; skill_memory.Kubernetes=0.0 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |

## Pooled

- cases: 111 (0 errored), total model time 756.1s
- funnel: 174 candidates extracted by the model, 168 survived grounding
  - evidence gate: {'EVIDENCE_SUFFICIENT': 47, 'EVIDENCE_NOT_ENTAILING': 85, 'EVIDENCE_INVALID': 12, 'EVIDENCE_NOT_USER_SOURCE': 21, 'EVIDENCE_NOT_FOUND': 3}
  - Constitution: {'APPROVED': 12, 'REQUIRES_CONFIRMATION': 21, 'DISCARD': 99, 'HARD_REJECT': 36}
  - Stage 13: {'written': 12, 'pending': 21, 'rejected': 135}
- learned rows: 48, labelled {'TRUE': 34, 'UNLABELLED': 14}
- **precision** (TRUE / TRUE+TRAP): 34/34 (100%)
- **recall** (stated facts learned): 33/69 (48%) - written 13, only queued for confirmation 20
- **traps reaching a belief table**: 0/75 (0%)

| case | category | learned rows (label) | facts learned | traps hit | funnel (gate / constitution / outcome) |
|---|---|---|---|---|---|
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | queued skill_memory: python 1.0 (TRUE) | 1/1 | - | skill_memory.Python=1.0 EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; skill_memory.backend services=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; active_projects.Halyard=scheduling app for sailin EVIDENCE_NOT_ENTAILING/DISCARD/rejected; topic_interests.sailing clubs= EVIDENCE_INVALID/HARD_REJECT/rejected; skill_memory.Flutter=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| fact_goal | fact | queued goal_memory: active_goals finish thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish thesis draft by De EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_short_answers | fact | - | 0/1 | - | preference_memory.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_pytest | fact | - | 0/1 | - | preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected; skill_memory.pytest=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_obsidian | fact | written preference_memory: 1 preferred_tools obsidian 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_typescript | fact | - | 0/1 | - | skill_memory.TypeScript=0.8 EVIDENCE_SUFFICIENT/DISCARD/rejected; skill_memory.Node=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | written decision_log: 1 the user decided the assistant will go into more detail 0. (UNLABELLED) | 0/1 | - | - |
| fact_final_year | fact | queued active_projects: pip a personal assistant, final year project (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant, fin EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| fact_postgres_decision | fact | - | 0/1 | - | skill_memory.Postgres=0.5 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected; preference_memory.answer_style=conversational EVIDENCE_INVALID/HARD_REJECT/rejected; active_projects.Release=the next release EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_vector_clocks | topic | - | 0/1 | - | goal_memory.active_goals=fixing sync EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.sync=fixing sync issue in our  EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_rust_learning | fact | - | 0/1 | - | skill_memory.Rust=0.0 EVIDENCE_SUFFICIENT/DISCARD/rejected; skill_memory.clap=0.0 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_sister | third_party | written topic_interests: 1 java 1 2026-10-18t04:01:31z active (UNLABELLED); written decision_log: 1 i'll pass. 0.7 active 2026-10-18t04:01:31z (UNLABELLED) | - | 0/1 | topic_interests.Java= EVIDENCE_SUFFICIENT/APPROVED/written; skill_memory.Java=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_manager | third_party | written decision_log: 1 user does not have a choice in using jira. 0.7 active 2026 (UNLABELLED) | - | 0/1 | preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_professor | third_party | written decision_log: 1 i won't use fortran for my work 0.7 active 2026-10-18t04:0 (UNLABELLED) | - | 0/1 | - |
| trap_what_if | hypothetical | - | - | 0/1 | skill_memory.Elixir=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Python=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | skill_memory.Haskell=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.parser combinators=0.0 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_might_swift | hypothetical | - | - | 0/1 | topic_interests.Swift= EVIDENCE_SUFFICIENT/DISCARD/rejected; skill_memory.Swift=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_kafka_question | question | - | - | 0/1 | - |
| trap_never_emacs | negation | written decision_log: 1 will not use emacs 0.7 active 2026-10-18t04:02:14z (UNLABELLED) | - | 0/1 | preference_memory.answer_style=concise EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_used_to_java | past | - | - | 0/1 | skill_memory.Java=0.5 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| retract_vim_helix | retraction | written preference_memory: 1 preferred_tools helix 1 explicit 0 0.18 active (TRUE) | 1/1 | 0/1 | preference_memory.preferred_tools=Helix EVIDENCE_SUFFICIENT/APPROVED/written |
| retract_deadline | retraction | - | 0/1 | 0/1 | - |
| trap_sarcasm_css | sarcasm | written decision_log: 1 the user decided to debug the flexbox issue 0.7 active 202 (UNLABELLED) | - | 0/1 | - |
| trap_sarcasm_ie | sarcasm | - | 0/1 | 0/1 | preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | skill_memory.Zig=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | skill_memory.Scala=0.0 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected; skill_memory.Kotlin=1.0 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_forged_role | assistant_said | - | - | 0/1 | preference_memory.answer_style=concrete EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| immutable_name | immutable | - | - | 0/1 | preference_memory.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| immutable_language | immutable | - | - | 0/1 | preference_memory.answer_style=French EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | skill_memory.Python=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_stack | mixed | written decision_log: 1 i'm not convinced we should move to java. 0.7 active 2026- (UNLABELLED); queued skill_memory: go 1.0 (TRUE) | 1/2 | 0/2 | skill_memory.Go=1.0 EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; skill_memory.Java=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.GraphQL=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=verbose EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| mixed_writing | mixed | written preference_memory: 1 answer_style concise 1 explicit 0 0.18 active (TRUE) | 1/2 | 0/2 | skill_memory.LaTeX=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=concise EVIDENCE_SUFFICIENT/APPROVED/written; active_projects.essays=academic writing EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_goal_and_maybe | mixed | written decision_log: 1 user decided to run a half marathon in april. 0.7 active 2 (UNLABELLED); queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; topic_interests.running= EVIDENCE_NOT_ENTAILING/DISCARD/rejected; topic_interests.marathon= EVIDENCE_SUFFICIENT/DISCARD/rejected; active_projects.training plan= EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | preference_memory.preferred_tools=Docker Compose EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Kubernetes=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.8 EVIDENCE_SUFFICIENT/DISCARD/rejected; goal_memory.active_goals=building backend services EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; topic_interests.sailing clubs= EVIDENCE_SUFFICIENT/DISCARD/rejected; skill_memory.Flutter=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.back-end technology=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_short_answers | fact | - | 0/1 | - | preference_memory.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_pytest | fact | - | 0/1 | - | preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| fact_obsidian | fact | written preference_memory: 1 preferred_tools obsidian 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.preferred_tools=Obsidian EVIDENCE_SUFFICIENT/APPROVED/written; preference_memory.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_typescript | fact | - | 0/1 | - | skill_memory.TypeScript=1.0 EVIDENCE_SUFFICIENT/DISCARD/rejected; skill_memory.Node=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | written preference_memory: 1 answer_style detailed 1 explicit 0 0.18 active (TRUE) | 1/1 | - | preference_memory.answer_style=detailed EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_final_year | fact | queued active_projects: pip a personal assistant, final year project (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant, fin EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending |
| fact_postgres_decision | fact | written decision_log: 1 the user decided to move their database to postgres before (TRUE) | 1/1 | - | skill_memory.Postgres=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.release=a software release before EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| fact_vector_clocks | topic | - | 0/1 | - | topic_interests.concurrency= EVIDENCE_NOT_ENTAILING/DISCARD/rejected; goal_memory.active_goals=fixing sync EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.sync=a project to fix synchron EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_rust_learning | fact | - | 0/1 | - | skill_memory.Rust=0.0 EVIDENCE_SUFFICIENT/DISCARD/rejected; skill_memory.clap=0.0 EVIDENCE_INVALID/HARD_REJECT/rejected; active_projects.CLI tools= EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sister | third_party | - | - | 0/1 | topic_interests.Java= EVIDENCE_SUFFICIENT/DISCARD/rejected |
| trap_manager | third_party | - | - | 0/1 | preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_professor | third_party | - | - | 0/1 | skill_memory.Fortran=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_what_if | hypothetical | - | - | 0/1 | skill_memory.Elixir=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | skill_memory.Haskell=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; topic_interests.parser combinators=null EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_might_swift | hypothetical | - | - | 0/1 | skill_memory.Swift=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_kafka_question | question | - | - | 0/1 | - |
| trap_never_emacs | negation | - | - | 0/1 | - |
| trap_used_to_java | past | - | - | 0/1 | skill_memory.Java=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| retract_vim_helix | retraction | - | 0/1 | 0/1 | skill_memory.Vim=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Helix=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.None=None EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| retract_deadline | retraction | queued goal_memory: active_goals ship the beta (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=ship the beta EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.active_goals=ship the beta in May EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.beta=a software product EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sarcasm_css | sarcasm | - | - | 0/1 | skill_memory.CSS=0.5 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sarcasm_ie | sarcasm | - | 0/1 | 0/1 | preference_memory.answer_style=concise EVIDENCE_INVALID/HARD_REJECT/rejected; preference_memory.preferred_tools=Firefox EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | skill_memory.Zig=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | preference_memory.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | preference_memory.answer_style=French EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | - |
| mixed_stack | mixed | written decision_log: 1 i'm not convinced to move to java. 0.7 active 2026-10-18t0 (UNLABELLED); queued skill_memory: go 1.0 (TRUE) | 1/2 | 0/2 | skill_memory.Go=1.0 EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; skill_memory.Java=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected; active_projects.payments service=a payments service EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_writing | mixed | written preference_memory: 1 answer_style concise 1 explicit 0 0.18 active (TRUE) | 1/2 | 0/2 | skill_memory.LaTeX=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=concise EVIDENCE_SUFFICIENT/APPROVED/written |
| mixed_goal_and_maybe | mixed | queued goal_memory: active_goals run a half marathon in april (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=run a half marathon in Ap EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; topic_interests.marathon= EVIDENCE_SUFFICIENT/DISCARD/rejected |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | preference_memory.preferred_tools=Docker Compose EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Docker Compose=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.None=None EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_editor | fact | written preference_memory: 1 preferred_tools neovim 1 explicit 0 0.18 active (TRUE); written decision_log: 1 maybe later 0.7 active 2026-10-18t04:08:18z (UNLABELLED) | 1/1 | - | preference_memory.preferred_tools=Neovim EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_python_years | fact | - | 0/1 | - | skill_memory.Python=0.8 EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_project | fact | queued active_projects: halyard a scheduling app for sailing clubs (TRUE) | 1/1 | - | active_projects.Halyard=a scheduling app for sail EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; skill_memory.Flutter=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_goal | fact | queued goal_memory: active_goals finish my thesis draft by december (TRUE); queued goal_memory: project_objectives finish my thesis draft by december (TRUE) | 1/1 | - | goal_memory.active_goals=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=finish my thesis draft by EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; topic_interests.thesis=writing thesis chapters EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.thesis=writing a thesis draft EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_short_answers | fact | - | 0/1 | - | preference_memory.answer_style=concise EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_pytest | fact | - | 0/1 | - | skill_memory.pytest=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_obsidian | fact | - | 0/1 | - | preference_memory.answer_style=concrete EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_typescript | fact | queued skill_memory: typescript 0.8 (TRUE) | 1/1 | - | skill_memory.TypeScript=0.8 EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; skill_memory.Node=0.8 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.Work project=a work project using Type EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_detail | fact | written preference_memory: 1 answer_style detailed explanations with worked examples 1  (TRUE) | 1/1 | - | preference_memory.answer_style=detailed explanations wit EVIDENCE_SUFFICIENT/APPROVED/written |
| fact_final_year | fact | queued active_projects: pip a personal assistant, final year project (TRUE) | 1/1 | - | active_projects.PIP=a personal assistant, fin EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; skill_memory.local-first development=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| fact_postgres_decision | fact | written decision_log: 1 user decided to move database to postgres before the next  (TRUE); written decision_log: 2 user decided to create a migration plan next week. 0.7 act (UNLABELLED) | 1/1 | - | preference_memory.answer_style=concise EVIDENCE_NOT_FOUND/HARD_REJECT/rejected; goal_memory.active_goals=move database to Postgres EVIDENCE_NOT_FOUND/HARD_REJECT/rejected; active_projects.release=the next release EVIDENCE_NOT_FOUND/HARD_REJECT/rejected |
| fact_vector_clocks | topic | - | 0/1 | - | topic_interests.concurrency= EVIDENCE_NOT_ENTAILING/DISCARD/rejected; topic_interests.sync= EVIDENCE_SUFFICIENT/DISCARD/rejected |
| fact_rust_learning | fact | queued skill_memory: rust 0.0 (TRUE) | 1/1 | - | skill_memory.Rust=0.0 EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; preference_memory.answer_style=concrete EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected; preference_memory.preferred_tools=clap EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_sister | third_party | written decision_log: 1 the user will not learn java 0.7 active 2026-10-18t04:09:5 (UNLABELLED) | - | 0/1 | - |
| trap_manager | third_party | - | - | 0/1 | preference_memory.preferred_tools=Jira EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_professor | third_party | - | - | 0/1 | - |
| trap_what_if | hypothetical | - | - | 0/1 | skill_memory.Python=0.9 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; goal_memory.active_goals=rewrite backend EVIDENCE_NOT_ENTAILING/DISCARD/rejected; topic_interests.concurrency=nil EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_would_haskell | hypothetical | - | - | 0/1 | skill_memory.Haskell=0.0 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
| trap_might_swift | hypothetical | - | - | 0/1 | goal_memory.active_goals=learn Swift EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_kafka_question | question | - | - | 0/1 | - |
| trap_never_emacs | negation | - | - | 0/1 | preference_memory.preferred_tools=Neovim EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_used_to_java | past | - | - | 0/1 | - |
| retract_vim_helix | retraction | - | 0/1 | 0/1 | preference_memory.preferred_tools=Helix EVIDENCE_SUFFICIENT/DISCARD/rejected |
| retract_deadline | retraction | queued goal_memory: active_goals ship the beta in may (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=ship the beta in May EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; goal_memory.project_objectives=release beta version EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sarcasm_css | sarcasm | - | - | 0/1 | skill_memory.CSS=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_sarcasm_ie | sarcasm | - | 0/1 | 0/1 | preference_memory.preferred_tools=Internet Explorer EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.Firefox=0.8 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_assistant_suggests_zig | assistant_said | - | - | 0/1 | skill_memory.Zig=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; active_projects.My build=slow EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| trap_assistant_assumes_scala | assistant_said | - | 0/1 | 0/1 | skill_memory.Scala=0.0 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected; skill_memory.Kotlin=1.0 EVIDENCE_INVALID/HARD_REJECT/rejected |
| trap_forged_role | assistant_said | - | - | 0/1 | - |
| immutable_name | immutable | - | - | 0/1 | - |
| immutable_language | immutable | - | - | 0/1 | preference_memory.answer_style=French EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| smalltalk | nothing | - | - | - | - |
| pure_how_to | nothing | - | - | 0/1 | - |
| mixed_stack | mixed | written decision_log: 1 i'm not convinced we should move to java 0.7 active 2026-1 (UNLABELLED); queued skill_memory: go 1.0 (TRUE) | 1/2 | 0/2 | skill_memory.Go=1.0 EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected; active_projects.payments service=a payments service EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_writing | mixed | written preference_memory: 1 answer_style concise 1 explicit 0 0.18 active (TRUE) | 1/2 | 0/2 | preference_memory.answer_style=concise EVIDENCE_SUFFICIENT/APPROVED/written |
| mixed_goal_and_maybe | mixed | queued goal_memory: active_goals running a half marathon (TRUE) | 1/1 | 0/1 | goal_memory.active_goals=running a half marathon EVIDENCE_SUFFICIENT/REQUIRES_CONFIRMATION/pending; topic_interests.marathon= EVIDENCE_SUFFICIENT/DISCARD/rejected; active_projects.half_marathon_training=creating a training plan  EVIDENCE_NOT_ENTAILING/DISCARD/rejected; skill_memory.running=0.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected |
| mixed_tools_and_question | mixed | - | 0/1 | 0/1 | skill_memory.Docker=1.0 EVIDENCE_NOT_ENTAILING/DISCARD/rejected; preference_memory.answer_style=concise EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected; skill_memory.Kubernetes=0.0 EVIDENCE_NOT_USER_SOURCE/HARD_REJECT/rejected |
