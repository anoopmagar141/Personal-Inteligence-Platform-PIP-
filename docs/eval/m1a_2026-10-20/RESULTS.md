# M-1(a): results

Population (genuine user quotes, one per recording + chat + claim + quote): 58 accepted, 166 rejected for support. Graded: all 58 accepted and 58 rejected drawn by seed 20261020, mixed and shuffled, the verdict hidden; one grader, a fresh Claude session that had not seen the verdicts. Key fingerprint checked.

| | strict (U counts against the claim) | lenient (U counts for it) |
|---|---|---|
| accepted but NOT supported (false accepts) | 8 of 58 (14%; 95% interval 7-25%) | 7 of 58 (12%; 95% interval 6-23%) |
| rejected but supported (false rejects) | 20 of 58 (34%; 95% interval 24-47%) | 20 of 58 (34%; 95% interval 24-47%) |

**Verdict on Promise 4's wording (rule fixed in DESIGN.md): DOES NOT HOLD** (8 accepted item(s) graded DOES NOT or UNCLEAR on the strict reading; 0 = holds, 1-3 = mostly holds, 4 or more = does not hold).

## Accepted items the grader did not find supported
- 31 [D] v2llama fact_python_years: a skill: "Python", at level 1.0 (0 = none, 1 = expert); quote "I've been writing Python professionally for six years now." - grader: six years professional, but expert level not stated (gate: EVIDENCE_SUFFICIENT)
- 37 [D] v2llama mixed_stack: a skill: "Go", at level 1.0 (0 = none, 1 = expert); quote "I'm a backend developer and I've written Go professionally for four years." - grader: four years professional, but expert level not stated (gate: EVIDENCE_SUFFICIENT)
- 53 [U] v2long long_M_r2_d7: a preference: "project_management" is "Lanternfish, a budgeting app for student hostels"; quote "Context for the next bit: my main project this term is Lanternfish, a budgeting app for student hostels." - grader: Lanternfish is their project; filed as a project-management preference (gate: EVIDENCE_SUFFICIENT)
- 56 [D] v2llama mixed_goal_and_maybe: a topic you are interested in: "marathon"; quote "My friend says I should do a full marathon" - grader: friend's suggestion, which the user calls crazy (gate: EVIDENCE_SUFFICIENT)
- 77 [D] v2llama fact_typescript: a skill: "TypeScript", at level 1.0 (0 = none, 1 = expert); quote "I work mostly in TypeScript these days, at work and at home." - grader: works in TypeScript; expert level not stated (gate: EVIDENCE_SUFFICIENT)
- 81 [D] v2llama mixed_goal_and_maybe: a topic you are interested in: "marathon"; quote "My friend says I should do a full marathon but that's crazy." - grader: friend's suggestion, which the user calls crazy (gate: EVIDENCE_SUFFICIENT)
- 94 [D] v2qwen mixed_stack: a skill: "Go", at level 1.0 (0 = none, 1 = expert); quote "I've written Go professionally for four years." - grader: four years professional, but expert level not stated (gate: EVIDENCE_SUFFICIENT)
- 105 [D] v2llama mixed_stack: a skill: "Go", at level 1.0 (0 = none, 1 = expert); quote "I've written Go professionally for four years." - grader: four years professional, but expert level not stated (gate: EVIDENCE_SUFFICIENT)

## Rejected items the grader found supported
- 3 [S] v2llama trap_assistant_suggests_zig: a project of yours: "My build" (slow); quote "My build is slow, any ideas?" (gate: EVIDENCE_NOT_ENTAILING)
- 5 [S] v2qwen fact_typescript: a preference: "preferred_tools" is "plain Node"; quote " Mostly plain Node." (gate: EVIDENCE_NOT_ENTAILING)
- 14 [S] v2long long_S_r0_d21: a project of yours: "Lanternfish" (a budgeting app for student hostels); quote "Context for the next bit: my main project this term is Lanternfish, a budgeting app for student hostels." (gate: EVIDENCE_NOT_ENTAILING)
- 20 [S] v2llama fact_vector_clocks: a project of yours: "sync" (fixing sync issue in our system); quote "our sync is broken" (gate: EVIDENCE_NOT_ENTAILING)
- 22 [S] v2long long_S_r1_d21: a preference: "Excalidraw" is "drawing tool"; quote "I do all my diagrams in Excalidraw these days, it's the only drawing tool I actually open." (gate: EVIDENCE_NOT_ENTAILING)
- 30 [S] v2qwen immutable_language: a preference: "answer_style" is "French"; quote "Please answer me in French from now on." (gate: EVIDENCE_NOT_ENTAILING)
- 39 [S] v2qwen mixed_stack: a project of yours: "Payments service" (a backend service for a payments system); quote "A payments service." (gate: EVIDENCE_NOT_ENTAILING)
- 40 [S] v2long long_S_r1_d21: a project of yours: "Lanternfish" (a budgeting app for student hostels); quote "my main project this term is Lanternfish, a budgeting app for student hostels." (gate: EVIDENCE_NOT_ENTAILING)
- 42 [S] v2qwen fact_python_years: a project of yours: "backend services" (services built for backend purposes); quote "Mostly backend services." (gate: EVIDENCE_NOT_ENTAILING)
- 43 [S] v2llama immutable_language: a preference: "answer_style" is "French"; quote "Please answer me in French from now on." (gate: EVIDENCE_NOT_ENTAILING)
- 60 [S] v2long long_S_r2_d21: a project of yours: "Lanternfish" (a budgeting app for student hostels); quote "Context for the next bit: my main project this term is Lanternfish, a budgeting app for student hostels. How should I name the tables for shared expenses?" (gate: EVIDENCE_NOT_ENTAILING)
- 62 [S] v2long long_M_r0_d21: a preference: "main_projects" is "Lanternfish"; quote "Context for the next bit: my main project this term is Lanternfish, a budgeting app for student hostels. How should I name the tables for shared expenses?" (gate: EVIDENCE_NOT_ENTAILING)
- 73 [S] v2long long_S_r1_d21: a skill: "Kotlin", at level 0.0 (0 = none, 1 = expert); quote "I don't write Kotlin at all, it's someone else's code, but thanks." (gate: EVIDENCE_NOT_ENTAILING)
- 74 [S] v2llama fact_rust_learning: a project of yours: "CLI tools" (); quote "small CLI tools" (gate: EVIDENCE_NOT_ENTAILING)
- 83 [S] v2long long_M_r0_d63: a project of yours: "Lanternfish" (a budgeting app for student hostels); quote "Context for the next bit: my main project this term is Lanternfish, a budgeting app for student hostels." (gate: EVIDENCE_NOT_ENTAILING)
- 84 [S] v2llama fact_vector_clocks: a goal: "fixing sync"; quote "I keep coming back to this because our sync is broken." (gate: EVIDENCE_NOT_ENTAILING)
- 87 [S] v2llama fact_project: a project of yours: "Halyard" (scheduling app for sailing clubs); quote "a scheduling app for sailing clubs" (gate: EVIDENCE_NOT_ENTAILING)
- 93 [S] v2long long_S_r1_d63: a project of yours: "Lanternfish" (a budgeting app for student hostels); quote "my main project this term is Lanternfish, a budgeting app for student hostels." (gate: EVIDENCE_NOT_ENTAILING)
- 111 [S] v2llama mixed_tools_and_question: a preference: "preferred_tools" is "Docker Compose"; quote "I deploy everything with Docker Compose on a small VPS." (gate: EVIDENCE_NOT_ENTAILING)
- 114 [S] v2long long_S_r1_d7: a project of yours: "Lanternfish" (a budgeting app for student hostels); quote "my main project this term is Lanternfish, a budgeting app for student hostels" (gate: EVIDENCE_NOT_ENTAILING)

## Accepted items by table (graded / not supported, strict)
- active_projects: 4 / 0
- goal_memory: 12 / 0
- interaction_style: 2 / 0
- preference_memory: 18 / 1
- skill_memory: 11 / 5
- topic_interests: 11 / 2

## What happened to the 8 after the gate (added by hand; score.py writes the part above)

From the same recordings' replay through the harness (`scripts/eval_observer_end_to_end.py --replay`, at 0c8fc7f, whose
gate, Constitution and Stage 13 are those of b03f928), the Constitution and Stage 13 columns for each claim:
- 31, 37, 105 (skill level 1.0): queued to ask the user (skill levels are a gated field); 94: queued in one run,
  discarded in another.
- 56, 81 (topic "marathon"), 77 (TypeScript 1.0): discarded by the week-1-2 rule.
- 53 (Lanternfish as preference "project_management", graded UNCLEAR): written.

So no item graded DOES NOT was stored without asking the user. The verdict above is about the gate alone, as the
design's rule says.
