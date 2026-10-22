# Report diagrams

Drawn on 2026-10-21 from the real code at commit 1902c5e. If the code changes, re-check the facts in
`make_diagrams.py` and run it again.

## What is here

- `png/`: one picture per figure, at double size so it prints sharp. **Use these in Word.**
- `svg/`: the same figures as vector files. Word 365 can insert them too, and they never blur.
- `make_diagrams.py` and `svglib.py`: draw every SVG (Python standard library only).
- `render.ps1`: turns the SVGs into PNGs with the Microsoft Edge that is already on the PC.

To redraw everything:

```powershell
.\.venv\Scripts\python.exe -I notes\report\diagrams\make_diagrams.py
powershell -ExecutionPolicy Bypass -File notes\report\diagrams\render.ps1
```

In Word: Insert → Pictures → choose the PNG, then set its width to the text width (about 15 cm with the
guide's margins). Write the caption in Word (References → Insert Caption), so the list of figures
builds itself.

## The figures

| File | Caption | Report section | Drawn from |
|---|---|---|---|
| fig3-1_system_architecture | Figure 3.1: System architecture of PIP | 3.5 | AGENTS.md stack; ARCHITECTURE.md "Layers" |
| fig4-1_use_case | Figure 4.1: Use case diagram | 4.1 | routes in backend/api/server.py; screens in frontend/flutter/lib/screens/ |
| fig4-2_dfd_level0 | Figure 4.2: Context diagram (DFD level 0) | 4.2 | the same, plus stage_06 (web search) and providers/ |
| fig4-3_dfd_level1 | Figure 4.3: DFD level 1 | 4.2 | server.py routes; backend/memory/ stores |
| fig4-4_dfd_level2_message | Figure 4.4: DFD level 2, process 2.0 (answer a chat message) | 4.2 | core/pipeline.py run(), Stages 0–10 |
| fig4-5_dfd_level2_learning | Figure 4.5: DFD level 2, process 3.0 (learn at session end) | 4.2 | stage_11/12/13, core/evidence_gate.py |
| fig4-6_er_chats_projects | Figure 4.6: ER diagram: chats, projects, decisions and documents | 4.3 | backend/core/schema.sql |
| fig4-7_er_user_model_governance | Figure 4.7: ER diagram: user model, governance, providers and logs | 4.3 | backend/core/schema.sql |
| fig4-8_package_diagram | Figure 4.8: Package diagram of the backend | 4.4 | every import statement outside backend/tests (counted 2026-10-22) |
| fig4-9_class_diagram | Figure 4.9: Class diagram | 4.4 | every class in backend/ (providers, core, stages), 2026-10-22 |
| fig4-10_sequence_chat_message | Figure 4.10: Sequence diagram: one chat message | 4.5 | server.py ws_chat(); pipeline.py |
| fig4-11_sequence_sign_in | Figure 4.11: Sequence diagram: signing in | 4.5 | server.py /auth routes; core/session_key.py unlock() |
| fig4-12_activity_learning | Figure 4.12: Activity diagram: what happens to a learned fact | 4.5 | stage_13_profile_update.py run() outcomes |

The sequence and activity diagrams were Figures 4.8-4.10 until 2026-10-22; they moved to 4.10-4.12 so the
figures follow the sections (4.4 comes before 4.5).

## Points to explain in the text

- **DFD notation:** Gane–Sarson (rounded boxes are processes, open boxes are data stores, grey boxes are
  external entities). A store or entity marked `*` is drawn twice only to avoid crossing lines.
- **Figure 4.4:** the dashed line is a cache hit. The answer comes from memory and Stages 3–9 are skipped.
- **Figure 4.5 and 4.12:** a fact the evidence gate refuses goes straight to Stage 13, which records the
  refusal in the audit log. It never reaches the Constitution check.
- **Figure 4.8 (packages):** the arrows are real imports. core and stages import each other (pipeline.py runs
  the stages; the stages use core's types, evidence gate and trace), and so do core and memory. So the four
  "layers" of Figure 3.1 describe roles, not strict import rules; the one rule a git hook enforces is that
  nothing under stages/ or api/ imports sqlite3, chromadb or ollama.
- **Figure 4.9 (classes):** say in one sentence that PIP is written mostly as module-level functions (one
  run() per stage, store functions that take the connection first), so the class diagram shows the few
  classes it has: the provider hierarchy, the evidence gate and Constitution types, the chat-session
  helpers, two frozen records and the exceptions.
- **ER diagrams:** crow's foot notation. Columns marked `*` hold another table's id with no foreign key, so
  SQLite does not enforce that link. The user model tables have no links between them: they are
  connected only through the Observer and the governance tables.
- **Not drawn yet:** the UI/UX design (4.6), which needs screenshots of the real app.
