"""Draws the report's design diagrams as SVG from facts read in the code (2026-10-21, HEAD 1902c5e).

Run:  .venv/Scripts/python.exe notes/report/diagrams/make_diagrams.py
Then: notes/report/diagrams/render.ps1 turns every SVG into a PNG for Word.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svglib import Svg, GREY, GREY2  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "svg")
os.makedirs(OUT, exist_ok=True)


def save(s, name):
    s.save(os.path.join(OUT, name + ".svg"))
    print("wrote", name)


# ---------------------------------------------------------------------------
# Figure 3.1  System architecture (ARCHITECTURE.md "Layers", AGENTS.md stack)
# ---------------------------------------------------------------------------
def architecture():
    s = Svg(1120, 1000)
    s.rect(15, 15, 855, 970, rx=10, dash="8 5", sw=1.4)
    s.text(30, 36, "User's Windows PC (everything in this box runs locally)", size=15,
           anchor="start", weight="bold")

    s.actor(78, 78, "User")
    s.line(104, 118, 148, 118)

    # Flutter client
    s.rect(150, 55, 470, 140, rx=8, fill=GREY, sw=1.5)
    s.text(385, 75, "Flutter desktop app (frontend/flutter)", size=15, weight="bold")
    s.text(385, 108, ["Screens: Sign-in · Chat · Profile & Review · Projects · Decisions",
                      "Documents · Models & Providers · Backup · Trace"], size=13)
    s.box(170, 140, 200, 40, "api_client.dart (REST)", size=14)
    s.box(400, 140, 200, 40, "ws_chat_client.dart (chat)", size=14)

    s.line(270, 180, 270, 298)
    s.text(278, 232, ["HTTP REST /api/v1/*", "+ bearer token"], size=13, anchor="start", style="italic")
    s.line(500, 180, 500, 298)
    s.text(508, 232, ["WebSocket /ws/chat", "streamed events"], size=13, anchor="start", style="italic")

    # Backend
    s.rect(35, 255, 590, 490, rx=8, sw=1.6)
    s.text(330, 275, "Python backend: FastAPI + uvicorn on localhost (backend/)", size=15, weight="bold")

    s.rect(50, 300, 560, 95, rx=5, fill=GREY)
    s.text(330, 316, "1  Transport: api/server.py", size=14, weight="bold")
    s.box(62, 332, 170, 52, ["Middleware:", "CORS → Token → Lock gate"], size=13)
    s.box(242, 332, 170, 52, ["68 REST routes →", "api_*(conn, …) functions"], size=13)
    s.box(422, 332, 176, 52, ["/ws/chat handler +", "one worker thread"], size=13)
    s.line(330, 395, 330, 413)

    s.rect(50, 415, 560, 170, rx=5, fill=GREY)
    s.text(330, 431, "2  Orchestration: core/pipeline.py, stages/, core/", size=14, weight="bold")
    s.box(62, 447, 268, 80, ["Per message (Stages 0–10)", "gap · intent · route · answer cache",
                             "decisions · memory · documents · web", "context · provider gate · LLM · reply"],
          size=13)
    s.box(340, 447, 258, 80, ["At session end (Stages 11–13)", "Observer extracts candidates",
                              "evidence gate · Constitution", "profile update · audit row"], size=13)
    s.box(62, 535, 536, 40, "Core: session key (PBKDF2) · constitutional.json · answer cache · trace · instance lock",
          size=13)
    s.line(210, 585, 210, 603)
    s.line(497, 585, 497, 603)

    s.rect(50, 605, 320, 120, rx=5, fill=GREY)
    s.text(210, 621, "3  Persistence: memory/", size=14, weight="bold")
    s.text(210, 675, ["profile_store · conversation_store", "decision_log · candidate_store",
                      "pending_observer · governance_audit", "vector_store (MiniLM embeddings, CPU)",
                      "llm_endpoint_store"], size=13)
    s.rect(385, 605, 225, 120, rx=5, fill=GREY)
    s.text(497, 621, "4  Providers: providers/", size=14, weight="bold")
    s.text(497, 668, ["base_provider (interface)", "ollama_provider", "openai_compatible_provider"], size=13)

    # Data
    s.rect(35, 790, 590, 180, rx=8, sw=1.5)
    s.text(330, 808, "Profile data folder (one folder per profile)", size=15, weight="bold")
    s.cylinder(50, 825, 170, 95, ["pip.db", "SQLCipher (encrypted)", "33 tables"], fill=GREY)
    s.cylinder(235, 825, 170, 95, ["chroma/", "vector index", "(chunk text encrypted)"], fill=GREY)
    s.cylinder(420, 825, 190, 95, ["documents/", "uploaded files", "+ salt.bin"], fill=GREY)
    s.text(330, 948, "Shared by all profiles: profiles.json (names only) · api_token.txt · pip.lock",
           size=13, style="italic")
    s.line(210, 725, 210, 788)
    s.text(218, 757, "raw SQL / encrypted", size=13, anchor="start", style="italic")

    # Local model, inside the PC
    s.box(655, 600, 195, 80, ["Ollama (local LLM server)", "qwen2.5:7b", "16k window, temperature 0"],
          size=14, fill=GREY)
    s.line(610, 640, 653, 640)
    s.label(632, 628, "HTTP", size=12)

    # Outside the PC
    s.text(1002, 300, "Outside the PC", size=15, weight="bold")
    s.box(900, 330, 205, 95, ["Web search: DuckDuckGo", "(ddgs package)", "only after the user clicks"],
          size=14, dash="6 4")
    s.box(900, 470, 205, 95, ["Cloud LLM provider", "(optional, OpenAI-compatible)", "only with recorded consent"],
          size=14, dash="6 4")
    s.poly([(610, 470), (882, 470), (882, 377), (898, 377)])
    s.label(745, 460, "query, after a click", size=12)
    s.poly([(610, 705), (882, 705), (882, 520), (898, 520)])
    s.label(745, 717, "prompt, if consented", size=12)
    save(s, "fig3-1_system_architecture")


# ---------------------------------------------------------------------------
# Figure 4.1  Use case diagram (routes in server.py, screens in lib/screens/)
# ---------------------------------------------------------------------------
def use_case():
    s = Svg(1110, 880)
    s.rect(185, 20, 725, 845, rx=10, sw=1.5)
    s.text(547, 42, "PIP: Personal Intelligence Platform", size=16, weight="bold")

    a_cx, rx, ry = 382, 152, 25
    a_cases = [
        "Create profile and set password", "Sign in / sign out", "Chat with PIP",
        "Review what PIP learned", "View and correct memory", "Manage projects",
        "Manage decisions", "Upload and search documents", "Read or correct a chat record",
        "Choose model and grant consent", "Back up, restore or import", "View pipeline trace",
    ]
    a_y = [92 + i * 64 for i in range(len(a_cases))]
    s.actor(80, 400, "User")
    for y in a_y:
        s.line(103, 438, a_cx - rx, y, end=None)
    for name, y in zip(a_cases, a_y):
        s.ellipse(a_cx, y, rx, ry)
        s.text(a_cx, y, name, size=14)

    b_cx = 740
    b = {
        "web": (238, "Search the web (after a click)"),
        "stream": (380, "Stream the answer"),
        "pull": (540, "Pull a model"),
        "learn": (680, "Learn from a finished chat"),
        "check": (800, "Check evidence and Constitution"),
    }
    for y, name in b.values():
        s.ellipse(b_cx, y, rx, ry, fill=GREY)
        s.text(b_cx, y, name, size=14)

    chat_y, choose_y = a_y[2], a_y[9]
    # extend / include (dashed, open arrow)
    s.line(b_cx - rx, b["web"][0], a_cx + rx, chat_y, end="open", dash="6 4")
    s.label(561, 196, "«extend»", size=13)
    s.line(a_cx + rx, chat_y + 8, b_cx - rx + 10, b["stream"][0] - 14, end="open", dash="6 4")
    s.label(560, 295, "«include»", size=13)
    s.line(b_cx - rx + 10, b["pull"][0] + 14, a_cx + rx, choose_y - 6, end="open", dash="6 4")
    s.label(616, 604, "«extend»", size=13)
    s.line(b_cx, b["learn"][0] + ry, b_cx, b["check"][0] - ry, end="open", dash="6 4")
    s.label(b_cx + 8, 740, "«include»", size=13, anchor="start")

    # secondary actors
    acts = {"web": (1030, 110, "Web search"), "cloud": (1030, 285, "Cloud model"),
            "ollama": (1030, 470, "Local model"), "timer": (1030, 690, "Session end")}
    for cx, top, name in acts.values():
        s.actor(cx, top, name, size=14)
    s.text(1030, 110 + 108, "(DuckDuckGo)", size=13)
    s.text(1030, 285 + 108, "(optional)", size=13)
    s.text(1030, 470 + 108, "(Ollama)", size=13)
    s.text(1030, 690 + 108, "(timer)", size=13)
    s.line(b_cx + rx, b["web"][0], 1006, 110 + 38, end=None)
    s.line(b_cx + rx, b["stream"][0], 1006, 285 + 38, end=None)
    s.line(b_cx + rx, b["stream"][0], 1006, 470 + 38, end=None)
    s.line(b_cx + rx, b["pull"][0], 1006, 470 + 40, end=None)
    s.line(b_cx + rx, b["learn"][0], 1006, 470 + 42, end=None)
    s.line(b_cx + rx, b["learn"][0], 1006, 690 + 38, end=None)
    save(s, "fig4-1_use_case")


# ---------------------------------------------------------------------------
# Figure 4.2  DFD level 0 (context diagram)
# ---------------------------------------------------------------------------
def dfd0():
    s = Svg(1100, 620)
    s.external(30, 265, 170, 100, "User", size=16)
    s.process(430, 225, 260, 180, "0", ["PIP", "Personal Intelligence", "Platform"], size=16)
    s.external(880, 40, 195, 90, ["Web search", "(DuckDuckGo)"])
    s.external(880, 270, 195, 100, ["Local language", "model (Ollama)"])
    s.external(880, 480, 195, 100, ["Cloud language", "model (optional)"])

    s.line(200, 290, 428, 290)
    s.label(315, 250, ["password, messages, search clicks,", "answers to questions, corrections,",
                       "documents, consent, backup file"], size=13)
    s.line(430, 345, 202, 345)
    s.label(315, 386, ["streamed answers, questions", "to confirm, memory, records,",
                       "trace, backup file"], size=13)

    s.line(690, 290, 878, 290)
    s.label(784, 262, ["prompt with context,", "chat transcript"], size=13)
    s.line(880, 345, 692, 345)
    s.label(784, 374, ["streamed tokens,", "learned candidates"], size=13)

    s.poly([(600, 225), (600, 70), (878, 70)])
    s.label(740, 54, "search query (only after a click)", size=13)
    s.poly([(880, 105), (640, 105), (640, 223)])
    s.label(760, 121, "search results", size=13)

    s.poly([(600, 405), (600, 555), (878, 555)])
    s.label(740, 572, "prompt (only with recorded consent)", size=13)
    s.poly([(880, 505), (640, 505), (640, 407)])
    s.label(760, 489, "streamed tokens", size=13)
    save(s, "fig4-2_dfd_level0")


# ---------------------------------------------------------------------------
# Figure 4.3  DFD level 1
# Three processes (2.0, 3.0, 4.0) share five stores, so 3.0 is drawn below with
# duplicate stores (marked *), the usual DFD way to avoid crossing lines.
# ---------------------------------------------------------------------------
def dfd1():
    s = Svg(1400, 1240)
    UX, UW = 20, 92
    LX, LW = 260, 190
    SX, SW = 545, 265
    RX, RW = 965, 180
    EX, EW = 1240, 150

    names = {
        "D1": ["Profile registry", "and password salt"],
        "D6": ["Documents and", "vector index"],
        "D7": ["Model providers", "and consent"],
        "D2": ["Chats, chat records,", "session-end queue"],
        "D8": ["Logs: trace, audit,", "observations"],
        "D3": ["User model: identity, skills,", "preferences, goals, topics"],
        "D4": ["Projects and", "decisions"],
        "D5": ["Review queue", "(questions to the user)"],
    }
    order = ["D1", "D6", "D7", "D2", "D8", "D3", "D4", "D5"]
    SH = 44
    sy = {sid: 90 + 95 * i for i, sid in enumerate(order)}
    sc = {sid: y + SH / 2 for sid, y in sy.items()}
    for sid in order:
        s.store(SX, sy[sid], SW, SH, sid, names[sid])
    s.store(SX, 865, SW, SH, "D*", ["All of D1–D8, exported as", "one encrypted .pipbak file"])

    P = {
        "1.0": (LX, sc["D1"] - 35, LW, 70, ["Sign in and", "unlock profile"]),
        "5.0": (LX, sc["D6"] - 35, LW, 70, ["Manage", "documents"]),
        "6.0": (LX, sc["D7"] - 35, LW, 70, ["Manage models", "and consent"]),
        "4.0": (LX, 372, LW, 428, ["Review and", "manage records", "(memory, projects,", "decisions, chat",
                                   "records, trace)"]),
        "7.0": (LX, 852, LW, 70, ["Back up and", "restore"]),
        "2.0": (RX, 185, RW, 520, ["Answer a", "chat message", "(Stages 0–10)"]),
    }
    for num, (x, y, w, h, lab) in P.items():
        s.process(x, y, w, h, num, lab, size=14)

    s.external(UX, 77, UW, 845, "User", size=16)

    # user <-> left processes (two-way)
    user_flows = {
        "1.0": ["profile, password →", "← signed in or refused"],
        "5.0": ["documents →", "← document list"],
        "6.0": ["model, consent →", "← models, providers"],
        "4.0": ["answers, edits →", "← questions, records"],
        "7.0": ["password, backup file →", "← backup file"],
    }
    for num, lab in user_flows.items():
        x, y, w, h, _ = P[num]
        c = y + h / 2
        s.line(UX + UW, c, LX - 2, c, start="arr")
        s.label((UX + UW + LX) / 2, c - 20, lab, size=12)

    # top lanes: user <-> 2.0
    s.poly([(55, 77), (55, 20), (1095, 20), (1095, 183)])
    s.label(580, 20, "chat message, web search click", size=13)
    s.poly([(1045, 185), (1045, 50), (95, 50), (95, 75)])
    s.label(580, 50, "streamed answer, web search offer", size=13)

    # left processes <-> stores (two-way unless stated)
    def left(num, sid, lab, t=0.5):
        x, y, w, h, _ = P[num]
        y1 = max(y + 12, min(y + h - 12, sc[sid]))
        x1, x2, y2 = x + w, SX - 2, sc[sid]
        s.line(x1, y1, x2, y2, start="arr")
        s.label(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t - 10, lab, size=12)

    left("1.0", "D1", "salt, last used")
    left("5.0", "D6", "chunks, files")
    left("6.0", "D7", "endpoints, consent")
    left("4.0", "D2", "chat record")
    left("4.0", "D8", "trace, audit row")
    left("4.0", "D3", "memory")
    left("4.0", "D4", "projects, decisions")
    left("4.0", "D5", "answers")
    x, y, w, h, _ = P["7.0"]
    s.line(x + w, y + h / 2, SX - 2, 887, start="arr")
    s.label((x + w + SX) / 2, y + h / 2 - 10, "copy, restore", size=12)

    # stores <-> 2.0, all straight
    mid = (SX + SW + RX) / 2
    for sid, lab, way in [("D6", "passages", "in"), ("D7", "consent", "in"),
                          ("D2", "history, messages", "both"), ("D8", "trace", "out"),
                          ("D3", "user model", "in"), ("D4", "decisions, projects", "in")]:
        y = sc[sid]
        if way == "out":
            s.line(RX, y, SX + SW + 2, y)
        else:
            s.line(SX + SW, y, RX - 2, y, start="arr" if way == "both" else None)
        s.label(mid, y - 11, lab, size=12)

    s.external(EX, 225, EW, 70, ["Web search", "(DuckDuckGo)"])
    s.external(EX, 560, EW, 120, ["Language", "model (local,", "or cloud with", "consent)"])
    s.line(RX + RW, 260, EX - 2, 260, start="arr")
    s.label((RX + RW + EX) / 2, 245, "query, results", size=12)
    s.line(RX + RW, 620, EX - 2, 620, start="arr")
    s.label((RX + RW + EX) / 2, 605, "prompt, tokens", size=12)

    # 3.0 with duplicate stores
    s.line(20, 950, 1380, 950, end=None, dash="3 5", sw=0.9)
    s.text(20, 968, "At session end (after 10 idle minutes, a disconnect, sign-out, shutdown, or at the next start):",
           size=13, anchor="start", style="italic")
    dup = [("D7*", ["Model providers", "and consent"], "in", "locality"),
           ("D2*", ["Chats, records,", "session-end queue"], "both", "transcript, chat record"),
           ("D8*", ["Logs: audit,", "observations"], "out", "audit, observations"),
           ("D3*", ["User model"], "both", "memory"),
           ("D4*", ["Projects and", "decisions"], "out", "decisions"),
           ("D5*", ["Review queue"], "out", "questions")]
    DW, DG, DX0, DY = 150, 20, 140, 995
    p3y = 1105
    for i, (sid, lab, way, flow) in enumerate(dup):
        x = DX0 + i * (DW + DG)
        s.store(x, DY, DW, SH, sid, lab, size=12)
        cx = x + DW / 2
        if way == "out":
            s.line(cx, p3y, cx, DY + SH + 2)
        else:
            s.line(cx, DY + SH, cx, p3y - 2, start="arr" if way == "both" else None)
        s.label(cx + 6, (DY + SH + p3y) / 2, flow, size=12, anchor="start")
    s.process(DX0, p3y, 970, 80, "3.0", "Learn at session end (Stages 11–13): Observer, evidence gate, Constitution, "
              "profile update", size=14)
    s.external(1210, p3y, 170, 80, ["Language", "model*"])
    s.line(DX0 + 970, p3y + 40, 1208, p3y + 40, start="arr")
    s.label(1160, p3y + 22, "transcript,", size=12)
    s.label(1160, p3y + 58, "candidates", size=12)
    s.text(20, 1215, "* Drawn twice to avoid crossing lines: D7*, D2*, D8*, D3*, D4*, D5* are the same stores as "
           "D7, D2, D8, D3, D4, D5 above, and Language model* is the same external entity.",
           size=12, anchor="start", style="italic")
    save(s, "fig4-3_dfd_level1")


# ---------------------------------------------------------------------------
# Figure 4.4  DFD level 2 for process 2.0 (pipeline.py run(): stages 0-10)
# ---------------------------------------------------------------------------
def dfd2_message():
    s = Svg(1150, 1200)
    MX, MW, H = 460, 250, 58
    LX, LW = 40, 290
    EX, EW = 900, 220
    c = [60 + 84 * i + H / 2 for i in range(12)]
    procs = [
        ("2.1", ["Measure the gap since the", "last session (Stage 0)"]),
        ("2.2", ["Classify the intent", "(Stage 1)"]),
        ("2.3", ["Route: choose what to", "look up (Stage 2)"]),
        ("2.4", ["Pick the chat record,", "check the answer cache"]),
        ("2.5", ["Look up decisions", "(Stage 3)"]),
        ("2.6", ["Look up memory", "(Stage 4)"]),
        ("2.7", ["Retrieve document", "passages (Stage 5)"]),
        ("2.8", ["Web search, only after", "the user's click (Stage 6)"]),
        ("2.9", ["Assemble the context", "(Stage 7)"]),
        ("2.10", ["Provider gate: check", "consent (Stage 8)"]),
        ("2.11", ["Stream the answer from", "the model (Stage 9)"]),
        ("2.12", ["Cache, trace and deliver;", "save the turn (Stage 10)"]),
    ]
    for (num, lab), cy in zip(procs, c):
        s.process(MX, cy - H / 2, MW, H, num, lab, size=13)
    chain = ["warm-start level", "intent, retrieval hint", "route plan", "cache miss", "+ decisions",
             "+ memory", "+ passages", "+ web results", "prompt", "prompt, allowed provider", "full answer"]
    cx = MX + MW / 2
    for i, lab in enumerate(chain):
        s.line(cx, c[i] + H / 2, cx, c[i + 1] - H / 2 - 1)
        s.text(cx + 8, (c[i] + c[i + 1]) / 2, lab, size=12, anchor="start", style="italic")

    # stores on the left, all read by the process beside them
    left = [(0, "D3", ["User model (profile_meta:", "last session date)"], "last session date"),
            (2, "M1", ["Answer cache", "(in memory, per session)"], None),
            (3, "D2", ["Chats: this chat's record"], "chat record"),
            (4, "D4", ["Projects and decisions"], "decisions"),
            (5, "D3*", ["User model: identity, skills,", "preferences, goals, projects"], "profile fields"),
            (6, "D6", ["Documents: vector index"], "passages"),
            (8, "D2*", ["Chats: history and record"], "history, record"),
            (9, "D7", ["Providers and consent"], "consent, locality")]
    for row, sid, lab, flow in left:
        s.store(LX, c[row] - 22, LW, 44, sid, lab, size=12)
        if flow:
            s.line(LX + LW, c[row], MX - 2, c[row])
            s.label((LX + LW + MX) / 2, c[row] - 11, flow, size=12)
    s.line(LX + LW, c[2] + 6, MX - 2, c[3] - 14)
    s.label(395, 278, "cached answer", size=12)
    s.store(LX, c[11] - 22, LW, 44, "D8", ["Logs: trace (stage, ms)"], size=12)
    s.line(MX, c[11], LX + LW + 2, c[11])
    s.label((LX + LW + MX) / 2, c[11] - 11, "trace", size=12)

    # below 2.12
    s.store(280, 1100, 240, 44, "M1*", ["Answer cache"], size=12)
    s.store(545, 1100, 240, 44, "D2*", ["Chats: messages"], size=12)
    s.line(480, c[11] + H / 2, 480, 1098)
    s.text(486, 1072, "answer (first message only)", size=12, anchor="start", style="italic")
    s.line(650, c[11] + H / 2, 650, 1098)

    # externals on the right
    s.external(EX, c[1] - 30, EW, 60, "User")
    s.line(EX, c[1], MX + MW + 2, c[1])
    s.label(806, c[1] - 12, "message", size=12)
    s.external(EX, c[7] - 30, EW, 60, ["Web search", "(DuckDuckGo)"])
    s.line(MX + MW, c[7], EX - 2, c[7], start="arr")
    s.label(842, c[7] - 12, "query, results", size=12)
    s.external(EX, c[10] - 30, EW, 60, ["Language model", "(local or cloud)"])
    s.line(MX + MW, c[10], EX - 2, c[10], start="arr")
    s.label(842, c[10] - 12, "prompt, tokens", size=12)
    s.external(EX, 1060, EW, 60, "User*")
    s.poly([(MX + MW, c[10] + 18), (860, c[10] + 18), (860, 1075), (EX - 2, 1075)])
    s.text(866, 1010, "streamed tokens", size=12, anchor="start", style="italic")
    s.poly([(MX + MW, c[11] + 20), (840, c[11] + 20), (840, 1105), (EX - 2, 1105)])
    s.text(834, 1066, "done, search offer", size=12, anchor="end", style="italic")
    s.text(651 + 6, 1072, "messages", size=12, anchor="start", style="italic")

    # cache hit skips 2.5 to 2.11
    s.poly([(MX + MW, c[3] + 10), (780, c[3] + 10), (780, c[11] - 12), (MX + MW + 2, c[11] - 12)], dash="7 4")
    s.text(788, c[3] + 40, ["cache hit:", "stored answer", "(skips 2.5–2.11)"], size=12, anchor="start",
           style="italic")
    s.text(40, 1175, "* Drawn twice to avoid crossing lines (same store or entity). Dashed: a cache hit goes "
           "straight to 2.12.", size=12, anchor="start", style="italic")
    save(s, "fig4-4_dfd_level2_message")


# ---------------------------------------------------------------------------
# Figure 4.5  DFD level 2 for process 3.0 (stage_11/12/13, evidence_gate.py)
# ---------------------------------------------------------------------------
def dfd2_learning():
    s = Svg(1400, 860)
    MX, MW, H = 420, 260, 58
    LX, LW = 30, 270
    RX, RW = 820, 240
    FX, FW = 1110, 270
    c = [80 + 84 * i + H / 2 - 29 for i in range(9)]
    c = [80 + 84 * i for i in range(9)]
    s.text(30, 28, "Runs once per chat at session end: after 10 idle minutes, a disconnect, sign-out, "
           "shutdown, or at the next start for a chat a crash left unfinished.", size=13, anchor="start",
           style="italic")
    main = [("3.1", ["Take the transcript", "from the queue"]),
            ("3.2", ["Check the model is local", "(both records agree)"]),
            ("3.3", ["Extract candidates", "(Observer, Stage 11)"]),
            ("3.4", ["Grounding: is the quote", "in the transcript?"]),
            ("3.5", ["Evidence gate: do the user's", "own words support it?"]),
            ("3.6", ["Reinforce evidence", "(count across chats)"]),
            ("3.7", ["Constitution check", "(Stage 12)"]),
            ("3.8", ["Write, ask or reject", "(Stage 13)"])]
    for (num, lab), cy in zip(main, c):
        s.process(MX, cy - H / 2, MW, H, num, lab, size=13)
    chain = ["transcript", "transcript, allowed provider", "candidates: claim + quote", "grounded candidates",
             "supported memory candidates", "candidate + evidence count", "verdict"]
    cx = MX + MW / 2
    for i, lab in enumerate(chain):
        s.line(cx, c[i] + H / 2, cx, c[i + 1] - H / 2 - 1)
        s.text(cx + 8, (c[i] + c[i + 1]) / 2, lab, size=12, anchor="start", style="italic")

    def lstore(row, sid, lab):
        s.store(LX, c[row] - 22, LW, 44, sid, lab, size=12)

    lstore(0, "D2", ["Chats: session-end queue", "(transcripts)"])
    s.line(LX + LW, c[0], MX - 2, c[0])
    s.label(360, c[0] - 11, "transcript", size=12)
    lstore(1, "D7", ["Providers and consent"])
    s.line(LX + LW, c[1], MX - 2, c[1])
    s.label(360, c[1] - 11, "both records", size=12)
    s.external(LX + 40, c[2] - 30, LW - 40, 60, ["Language model", "(local only)"])
    s.line(LX + LW, c[2], MX - 2, c[2], start="arr")
    s.label(360, c[2] - 13, ["transcript,", "candidates"], size=12)
    lstore(5, "D8*", ["Logs: observation log"])
    s.line(MX, c[5], LX + LW + 2, c[5])
    s.label(360, c[5] - 11, "observation", size=12)
    lstore(6, "D9", ["Constitution rules", "(constitutional.json)"])
    s.line(LX + LW, c[6], MX - 2, c[6])
    s.label(360, c[6] - 11, "rules, thresholds", size=12)
    lstore(7, "D3", ["User model"])
    s.line(LX + LW, c[7], MX - 2, c[7], start="arr")
    s.label(360, c[7] + 13, "memory", size=12)
    s.line(LX + LW, c[7] - 14, MX - 2, c[6] + 18)
    s.label(330, c[6] + 70, "current value", size=12, anchor="start")

    # right column
    s.process(RX, c[2] - H / 2, RW, H, "3.10", ["Write the chat record", "(\"where we left off\")"], size=13)
    s.line(MX + MW, c[2], RX - 2, c[2])
    s.label(750, c[2] - 11, "record fields", size=12)
    s.store(FX, c[2] - 22, FW, 44, "D2*", ["Chats: chat records"], size=12)
    s.line(RX + RW, c[2], FX - 2, c[2])
    s.label((RX + RW + FX) / 2, c[2] - 22, ["record,", "observed"], size=12)

    s.store(RX, c[3] - 22, RW, 44, "D8", ["Logs: audit (dropped)"], size=12)
    s.line(MX + MW, c[3], RX - 2, c[3])
    s.label(750, c[3] - 11, "audit row", size=12)

    s.process(RX, c[4] - H / 2, RW, H, "3.9", ["Route decisions", "(log or ask)"], size=13)
    s.line(MX + MW, c[4] - 10, RX - 2, c[4] - 10)
    s.label(750, c[4] - 21, "decisions", size=12)
    s.store(FX, c[4] - 22, FW, 44, "D4", ["Projects and decisions"], size=12)
    s.line(RX + RW, c[4], FX - 2, c[4])
    s.label((RX + RW + FX) / 2, c[4] - 11, "decision", size=12)

    s.store(RX, c[7] - 22, RW, 44, "D5", ["Review queue (questions)"], size=12)
    s.line(940, c[4] + H / 2, 940, c[7] - 24)
    s.text(946, c[5] + 20, "decision question", size=12, anchor="start", style="italic")
    s.line(MX + MW, c[7] + 6, RX - 2, c[7] + 6)
    s.label(750, c[7] + 32, ["question", "(confirm, shortfall)"], size=12)
    s.store(RX, c[8] - 22, RW, 44, "D8**", ["Logs: audit (outcome)"], size=12)
    s.poly([(600, c[7] + H / 2), (600, c[8]), (RX - 2, c[8])])
    s.label(700, c[8] - 11, "audit row", size=12)

    # a gate rejection goes straight to Stage 13, which records it
    s.poly([(MX + MW, c[4] + 12), (750, c[4] + 12), (750, c[7] - 15), (MX + MW + 2, c[7] - 15)], dash="7 4")
    s.text(758, c[5] + 22, ["rejected", "(skips 3.6–3.7)"], size=12, anchor="start", style="italic")
    s.text(RX, c[1], "If not local: nothing is sent, the chat stays queued.", size=12, anchor="start",
           style="italic")
    s.text(30, 835, "* Drawn more than once to avoid crossing lines (same store). Dashed: a candidate the "
           "evidence gate refuses goes straight to 3.8, which records the refusal.",
           size=12, anchor="start", style="italic")
    save(s, "fig4-5_dfd_level2_learning")


# ---------------------------------------------------------------------------
# ER legend shared by both ER figures
# ---------------------------------------------------------------------------
def er_legend(s, x, y):
    for i, (kind, text) in enumerate([("one", "exactly one"), ("zero_one", "zero or one"),
                                      ("zero_many", "zero or many")]):
        xx = x + i * 200
        s.line(xx, y, xx + 60, y, end=None, sw=1.3)
        s.cf_end(xx + 60, y, -1, 0, kind)
        s.text(xx + 70, y, text, size=12, anchor="start")
    s.text(x, y + 28, "PK primary key · FK foreign key (enforced) · * holds another table's id, "
           "with no foreign key", size=12, anchor="start")


# ---------------------------------------------------------------------------
# Figure 4.6  ER diagram A: chats, projects, decisions, documents (schema.sql)
# ---------------------------------------------------------------------------
def er_work():
    s = Svg(1300, 790)
    W = 250
    X = [30, 360, 690, 1020]
    msg = s.entity(X[0], 50, W, "messages", [
        ("PK", "id", "INTEGER"), ("FK", "conversation_id", "TEXT"), ("", "role", "user | assistant"),
        ("", "content", "TEXT"), ("", "created_at", "TEXT")])
    conv = s.entity(X[1], 50, W, "conversations", [
        ("PK", "id", "TEXT"), ("", "title", "TEXT"), ("FK", "project_id", "TEXT"), ("", "created_at", "TEXT"),
        ("", "updated_at", "TEXT"), ("", "observed_at", "TEXT")])
    proj = s.entity(X[2], 50, W, "active_projects", [
        ("PK", "project_id", "TEXT"), ("", "name", "TEXT, unique"), ("", "description", "TEXT"),
        ("", "status", "active | archived …"), ("", "last_active", "TEXT")])
    docs = s.entity(X[3], 50, W, "documents", [
        ("PK", "id", "INTEGER"), ("FK", "project_id", "TEXT"), ("", "file_path", "TEXT"),
        ("", "content_hash", "TEXT"), ("", "chunk_count", "INTEGER"), ("", "status", "active | removed"),
        ("", "ingested_at", "TEXT")])
    s.entity(X[0], 330, W, "pending_observer", [
        ("PK", "id", "INTEGER"), ("", "session_transcript", "TEXT"), ("", "status", "pending | … | failed"),
        ("*", "conversation_id", "TEXT"), ("", "session_ended_at", "TEXT"), ("", "processed_at", "TEXT")])
    rec = s.entity(X[1], 330, W, "chat_records", [
        ("PK", "id", "INTEGER"), ("FK", "conversation_id", "TEXT, unique"), ("FK", "project_id", "TEXT"),
        ("", "topic", "TEXT"), ("", "open_problems", "TEXT (list)"), ("", "last_decisions", "TEXT (list)"),
        ("", "suggested_next_step", "TEXT"), ("", "record_date", "TEXT"), ("", "source", "observer | user | …")])
    dec = s.entity(X[2], 330, W, "decision_log", [
        ("PK", "id", "INTEGER"), ("", "decision_text", "TEXT"), ("", "reasoning", "TEXT"),
        ("", "alternatives_considered", "TEXT"), ("FK", "project_id", "TEXT"), ("", "confidence", "REAL 0–1"),
        ("", "state", "active | superseded …"), ("FK", "superseded_by", "INTEGER"), ("", "state_reason", "TEXT"),
        ("*", "conversation_id", "TEXT"), ("", "created_at", "TEXT")])
    blob = s.entity(X[3], 330, W, "document_blobs", [
        ("PK FK", "document_id", "INTEGER"), ("", "content", "BLOB"), ("", "byte_size", "INTEGER"),
        ("", "stored_at", "TEXT")])
    s.entity(X[0], 520, W, "decision_candidates_pending", [
        ("PK", "id", "INTEGER"), ("", "decision_text", "TEXT"), ("", "signals_found", "TEXT"),
        ("", "raw_quote", "TEXT"), ("", "confidence", "REAL 0–1"), ("", "state", "pending | promoted …"),
        ("*", "project_id", "TEXT"), ("*", "conversation_id", "TEXT"), ("*", "candidate_id", "TEXT"),
        ("", "created_at", "TEXT")])
    s.entity(X[3], 500, W, "document_decision_conflicts", [
        ("PK", "id", "INTEGER"), ("", "document_path", "TEXT"), ("*", "decision_id", "INTEGER"),
        ("", "detected_at", "TEXT")])

    s.rel([(X[1], 100), (X[0] + W, 100)], "one", "zero_many", "has", (320, 86))
    s.rel([(X[2], 100), (X[1] + W, 100)], "zero_one", "zero_many", "groups", (650, 86))
    s.rel([(X[2] + W, 100), (X[3], 100)], "zero_one", "zero_many", "holds", (980, 86))
    s.rel([(X[3] + W / 2, docs[1] + docs[3]), (X[3] + W / 2, 330)], "one", "zero_one", "stores bytes of",
          (X[3] + W / 2 + 52, 268))
    s.rel([(X[1] + W / 2, conv[1] + conv[3]), (X[1] + W / 2, 330)], "one", "zero_one",
          "summarised by", (X[1] + W / 2 + 50, 260))
    s.rel([(X[1] + W, 400), (650, 400), (650, 150), (X[2], 150)], "zero_many", "zero_one")
    s.label(650, 290, "belongs to", size=12)
    s.rel([(X[2] + W / 2, proj[1] + proj[3]), (X[2] + W / 2, 330)], "zero_one", "zero_many", "records",
          (X[2] + W / 2 + 35, 250))
    s.rel([(X[2] + W, 420), (985, 420), (985, 480), (X[2] + W, 480)], "zero_many", "zero_one")
    s.text(990, 450, "superseded by", size=12, anchor="start", style="italic")
    er_legend(s, 360, 650)
    s.text(360, 706, "Every table is in the profile's encrypted database file (pip.db, SQLCipher).",
           size=12, anchor="start", style="italic")
    save(s, "fig4-6_er_chats_projects")


# ---------------------------------------------------------------------------
# Figure 4.7  ER diagram B: user model, governance, providers, logs (schema.sql)
# ---------------------------------------------------------------------------
def er_user_model():
    s = Svg(1310, 1010)
    W = 230
    s.rect(15, 40, 1000, 560, rx=10, dash="7 5", sw=1.1)
    s.text(30, 58, "User model: what PIP believes about the user", size=14, anchor="start", weight="bold")
    s.rect(1035, 40, 260, 650, rx=10, dash="7 5", sw=1.1)
    s.text(1050, 58, "Providers and logs", size=14, anchor="start", weight="bold")
    s.rect(15, 625, 880, 370, rx=10, dash="7 5", sw=1.1)
    s.text(30, 643, "Governance: how a belief got there", size=14, anchor="start", weight="bold")

    X = [35, 285, 535, 785]
    lab = ("", "source_label", "explicit | inferred …")
    s.entity(X[0], 75, W, "identity (one row)", [
        ("PK", "id", "= 1"), ("", "name", "TEXT"), ("", "preferred_name", "TEXT"),
        ("", "language_preference", "TEXT"), ("", "timezone", "TEXT")])
    s.entity(X[0], 220, W, "profile_meta (one row)", [
        ("PK", "id", "= 1"), ("", "session_count", "INTEGER"), ("", "schema_version", "TEXT"),
        ("", "constitution_version", "TEXT"), ("", "first_session_date", "TEXT"),
        ("", "last_session_date", "TEXT"), ("", "onboarding_complete", "0 | 1")])
    s.entity(X[0], 400, W, "interaction_style (one row)", [
        ("PK", "id", "= 1"), ("", "value", "TEXT"), ("", "evidence_count", "INTEGER"), lab,
        ("", "confidence", "generated")])
    sk = s.entity(X[1], 75, W, "skill_memory", [
        ("PK", "id", "INTEGER"), ("", "name", "TEXT, unique"), ("", "level", "REAL 0–1"),
        ("", "evidence_count", "INTEGER"), lab, ("", "confidence", "generated"),
        ("", "status", "active | archived …")])
    s.entity(X[1], 300, W, "skill_contradiction_log", [
        ("PK", "id", "INTEGER"), ("FK", "skill_id", "INTEGER"), ("", "contradiction_text", "TEXT"),
        ("", "session_no", "INTEGER"), ("", "created_at", "TEXT")])
    s.entity(X[1], 450, W, "topic_interests", [
        ("PK", "id", "INTEGER"), ("", "topic", "TEXT, unique"), ("", "evidence_count", "INTEGER"),
        ("", "last_observed", "TEXT"), ("", "status", "active | deleted")])
    pf = s.entity(X[2], 75, W, "preference_memory", [
        ("PK", "id", "INTEGER"), ("", "name", "TEXT, unique"), ("", "value", "TEXT"),
        ("", "evidence_count", "INTEGER"), lab, ("", "behavioral_signal_count", "INTEGER"),
        ("", "confidence", "generated"), ("", "status", "active | archived …")])
    s.entity(X[2], 300, W, "preference_contradiction_log", [
        ("PK", "id", "INTEGER"), ("FK", "preference_id", "INTEGER"), ("", "contradiction_text", "TEXT"),
        ("", "session_no", "INTEGER"), ("", "created_at", "TEXT")])
    s.entity(X[2], 450, W, "preferred_tools", [
        ("PK", "id", "INTEGER"), ("", "tool_name", "TEXT, unique"), ("", "evidence_count", "INTEGER"),
        ("", "last_observed", "TEXT"), ("", "status", "active | deleted")])
    s.entity(X[3], 75, W, "goal_memory", [
        ("PK", "id", "INTEGER"), ("", "goal_text", "TEXT"), ("", "evidence_count", "INTEGER"),
        ("", "confidence", "REAL 0–1"), ("", "decay_flag", "0 | 1"), ("", "status", "active | completed …"),
        ("", "created_at", "TEXT"), ("", "updated_at", "TEXT")])
    s.text(X[3], 305, ["For skills, preferences and style:", "confidence = 0.9 (explicit, verified",
                       "or corrected) or 0.4 (inferred),", "times min(evidence_count, 5) / 5,",
                       "computed by SQLite."],
           size=12, anchor="start", style="italic")
    s.text(X[3], 420, ["name, language and timezone", "change only by the user", "(Promise 2)."],
           size=12, anchor="start", style="italic")

    s.rel([(X[1] + W / 2, sk[1] + sk[3]), (X[1] + W / 2, 300)], "one", "zero_many", "contradicted by",
          (X[1] + W / 2 + 55, 274))
    s.rel([(X[2] + W / 2, pf[1] + pf[3]), (X[2] + W / 2, 300)], "one", "zero_many", "contradicted by",
          (X[2] + W / 2 + 55, 274))

    GX = [35, 330, 625]
    s.entity(GX[0], 660, W, "memory_candidates_pending", [
        ("PK", "id", "INTEGER"), ("", "target_table", "TEXT"), ("", "field_name", "TEXT"),
        ("", "proposed_value", "TEXT"), ("", "label", "explicit | inferred …"), ("", "evidence_count", "INTEGER"),
        ("", "evidence_text", "TEXT"), ("", "validation_status", "Stage 12 status"),
        ("", "origin", "observer | shortfall …"), ("", "state", "pending | resolved …"),
        ("*", "candidate_id", "TEXT")])
    s.entity(GX[1], 660, W, "governance_audit_log", [
        ("PK", "id", "INTEGER"), ("*", "candidate_id", "TEXT"), ("", "candidate_hmac", "HMAC, no text"),
        ("", "session_no", "INTEGER"), ("", "stage", "11 | 12 | 13"), ("", "actor", "system | user"),
        ("", "outcome", "accepted | rejected …"), ("", "reason_code", "TEXT"), ("", "target_table", "TEXT"),
        ("", "field_name", "TEXT"), ("", "evidence_count", "INTEGER"), ("", "confidence", "REAL"),
        ("*", "conversation_id", "TEXT"), ("", "decided_at", "TEXT")])
    s.entity(GX[2], 660, W, "memory_observation_log", [
        ("PK", "id", "INTEGER"), ("", "target_table", "TEXT"), ("", "field_name", "TEXT"),
        ("", "proposed_value", "TEXT"), ("", "label", "explicit | inferred …"), ("", "session_no", "INTEGER"),
        ("", "created_at", "TEXT")])
    y_pend = 660 + 34 + 17 * 10 + 8.5
    y_aud = 660 + 34 + 17 * 1 + 8.5
    s.poly([(GX[0] + W, y_pend), (297, y_pend), (297, y_aud), (GX[1] - 2, y_aud)], end=None, dash="5 4", sw=1.3)
    s.vtext(312, (y_pend + y_aud) / 2, "same candidate_id", size=11, weight="normal")
    s.text(GX[2], 850, ["The audit log is append-only:", "triggers refuse UPDATE and", "DELETE on it."],
           size=12, anchor="start", style="italic")

    pc = s.entity(1050, 75, W, "provider_consent", [
        ("PK", "provider_id", "TEXT"), ("", "is_cloud", "0 | 1"), ("", "user_consented", "0 | 1"),
        ("", "consent_date", "TEXT"), ("", "revoked", "0 | 1"), ("", "revoked_date", "TEXT"),
        ("", "consent_scope", "full_inference | …")])
    s.entity(1050, 275, W, "llm_endpoints", [
        ("PK", "provider_id", "TEXT"), ("", "label", "TEXT"), ("", "base_url", "TEXT"), ("", "model_name", "TEXT"),
        ("", "api_key", "TEXT"), ("", "is_local", "0 | 1"), ("", "enabled", "0 | 1"), ("", "priority", "INTEGER")])
    s.line(1165, pc[1] + pc[3], 1165, 275, end=None, dash="5 4", sw=1.3)
    s.label(1222, 253, "same provider_id", size=11)
    s.entity(1050, 490, W, "trace_log", [
        ("PK", "id", "INTEGER"), ("", "trace_id", "TEXT"), ("", "timestamp", "TEXT"), ("", "stage", "TEXT"),
        ("", "status", "TEXT"), ("", "message", "TEXT"), ("", "error_detail", "TEXT"),
        ("", "duration_ms", "INTEGER")])

    s.text(915, 730, "Notation", size=13, anchor="start", weight="bold")
    for i, (kind, text) in enumerate([("one", "exactly one"), ("zero_many", "zero or many")]):
        yy = 760 + i * 28
        s.line(915, yy, 975, yy, end=None, sw=1.3)
        s.cf_end(975, yy, -1, 0, kind)
        s.text(985, yy, text, size=12, anchor="start")
    s.line(915, 816, 975, 816, end=None, dash="5 4", sw=1.3)
    s.text(985, 816, "same id, no foreign key", size=12, anchor="start")
    s.text(915, 905, ["PK primary key · FK foreign key", "* holds another table's id,", "  with no foreign key",
                      "Not shown: identity_avatar,", "interaction_style_history,", "session_snapshot, llm_settings,",
                      "record_version, governance_audit_salt,", "document_access_patterns."],
           size=12, anchor="start")
    save(s, "fig4-7_er_user_model_governance")


# ---------------------------------------------------------------------------
# UML sequence diagram helper
# ---------------------------------------------------------------------------
class Seq:
    def __init__(self, s, lanes, top=20, bottom=None):
        """lanes: list of (key, x, label lines, is_actor)."""
        self.s, self.top, self.bottom = s, top, bottom or s.h - 20
        self.x = {k: x for k, x, _, _ in lanes}
        self.bars = []
        for k, x, lab, actor in lanes:
            if actor:
                s.actor(x, top, lab[0], size=14)
                y0 = top + 100
            else:
                s.box(x - 78, top + 20, 156, 50, lab, size=13, rx=3, fill=GREY)
                y0 = top + 70
            s.line(x, y0, x, self.bottom, end=None, dash="6 5", sw=1)

    def bar(self, k, y1, y2):
        self.bars.append((k, y1, y2))
        self.s.rect(self.x[k] - 6, y1, 12, y2 - y1, fill="#fff", sw=1.1)

    def _edge(self, k, y, toward):
        for kk, y1, y2 in self.bars:
            if kk == k and y1 <= y <= y2:
                return self.x[k] + (6 if toward > self.x[k] else -6)
        return self.x[k]

    def msg(self, y, a, b, text, ret=False, size=12):
        s = self.s
        if a == b:
            x = self._edge(a, y, 10 ** 6)
            s.poly([(x, y), (x + 34, y), (x + 34, y + 16), (x + 2, y + 16)])
            s.label(x + 40, y + 8, text, size=size, anchor="start", style="normal")
            return
        xa, xb = self._edge(a, y, self.x[b]), self._edge(b, y, self.x[a])
        if ret:
            s.line(xa, y, xb + (2 if xb < xa else -2), y, end="open", dash="6 4", sw=1.1)
        else:
            s.line(xa, y, xb + (2 if xb < xa else -2), y, sw=1.2)
        s.label((xa + xb) / 2, y - 10, text, size=size, style="normal")

    def frame(self, x1, y1, x2, y2, kind, guard):
        s = self.s
        s.rect(x1, y1, x2 - x1, y2 - y1, fill="none", sw=1.1)
        w = len(kind) * 8 + 16
        s.path(f"M{x1},{y1} L{x1 + w},{y1} L{x1 + w},{y1 + 12} L{x1 + w - 8},{y1 + 20} L{x1},{y1 + 20} Z", fill=GREY2,
               sw=1.1)
        s.text(x1 + w / 2 - 3, y1 + 10, kind, size=12, weight="bold")
        s.text(x1 + w + 8, y1 + 11, guard, size=12, anchor="start", style="italic")

    def divider(self, x1, x2, y, guard):
        self.s.line(x1, y, x2, y, end=None, dash="6 4", sw=1.1)
        self.s.text(x1 + 8, y + 13, guard, size=12, anchor="start", style="italic")


# ---------------------------------------------------------------------------
# Figure 4.10  Sequence: one chat message (server.py ws_chat, pipeline.run)
# ---------------------------------------------------------------------------
def seq_chat():
    s = Svg(1110, 1230)
    q = Seq(s, [("user", 60, ["User"], True),
                ("app", 215, ["Flutter app", "(chat screen)"], False),
                ("srv", 410, ["server.py", "/ws/chat"], False),
                ("pipe", 615, ["pipeline.py", "(Stages 0–10)"], False),
                ("db", 820, ["pip.db", "(SQLCipher)"], False),
                ("llm", 1010, ["Ollama", "(qwen2.5:7b)"], False)], bottom=1205)
    q.bar("srv", 200, 290)
    q.bar("srv", 318, 1150)
    q.bar("pipe", 384, 1024)
    q.msg(140, "user", "app", "types a message, presses Send")
    q.frame(130, 160, 600, 300, "opt", "[first message since the chat opened]")
    q.msg(212, "app", "srv", "connect /ws/chat?token=…&conversation_id=…")
    q.msg(234, "srv", "srv", "check token, unlocked, origin")
    q.msg(280, "srv", "app", "session_info (chat id, messages)", ret=True)
    q.msg(330, "app", "srv", "{message, project_id}")
    q.msg(362, "srv", "db", "save earlier unsaved turns; create chat if new")
    q.msg(396, "srv", "pipe", "run(message, history, chat id)")
    q.msg(418, "pipe", "pipe", "Stage 0 gap · Stage 1 intent · Stage 2 route")
    q.msg(470, "pipe", "db", "read this chat's record")
    q.msg(492, "pipe", "pipe", "check the answer cache (in memory)")
    q.frame(130, 525, 1100, 960, "alt", "[cache hit]")
    q.msg(565, "pipe", "srv", "cached answer (Stages 3–9 skipped)", ret=True)
    q.divider(130, 1100, 585, "[cache miss]")
    q.msg(625, "pipe", "db", "Stages 3–5: decisions, memory, passages")
    q.msg(660, "pipe", "srv", "stage events", ret=True)
    q.msg(690, "srv", "app", "stage events", ret=True)
    q.msg(710, "pipe", "pipe", "Stage 7 build the prompt · Stage 8 check consent")
    q.msg(765, "pipe", "llm", "POST /api/chat (stream, num_ctx 16384)")
    q.frame(145, 785, 1088, 905, "loop", "[each token]")
    q.msg(825, "llm", "pipe", "token", ret=True)
    q.msg(855, "pipe", "srv", "token", ret=True)
    q.msg(885, "srv", "app", "token (the answer grows on screen)", ret=True)
    q.msg(930, "pipe", "pipe", "cache the answer (first message only)")
    q.msg(990, "pipe", "db", "Stage 10: trace rows (stage, ms)")
    q.msg(1020, "pipe", "srv", "result (status, answer text)", ret=True)
    q.msg(1050, "srv", "app", "done", ret=True)
    q.msg(1080, "srv", "db", "save the message and the answer")
    q.frame(130, 1095, 560, 1160, "opt", "[the message would need the web]")
    q.msg(1140, "srv", "app", "web_search_offer (query)", ret=True)
    q.msg(1185, "app", "user", "shows the answer", ret=True)
    save(s, "fig4-10_sequence_chat_message")


# ---------------------------------------------------------------------------
# Figure 4.11  Sequence: sign in (server.py /auth/*, session_key.unlock)
# ---------------------------------------------------------------------------
def seq_sign_in():
    s = Svg(1110, 1130)
    q = Seq(s, [("user", 60, ["User"], True),
                ("app", 220, ["Flutter app", "(sign-in screen)"], False),
                ("srv", 420, ["server.py", "/auth routes"], False),
                ("key", 620, ["session_key", "+ db_key"], False),
                ("files", 820, ["profile files", "(profiles.json, salt, db)"], False),
                ("bg", 1010, ["catch-up task", "(background)"], False)], bottom=1080)
    q.bar("srv", 140, 175)
    q.bar("srv", 206, 240)
    q.bar("srv", 306, 412)
    q.bar("srv", 480, 966)
    q.bar("key", 514, 864)
    q.msg(150, "app", "srv", "GET /auth/state")
    q.msg(175, "srv", "app", "state: locked", ret=True)
    q.msg(215, "app", "srv", "GET /auth/profiles")
    q.msg(240, "srv", "app", "names, last used (no paths)", ret=True)
    q.msg(275, "user", "app", "chooses a profile")
    q.msg(315, "app", "srv", "POST /auth/profile {slug}")
    q.msg(335, "srv", "srv", "check nobody is signed in (else 409)")
    q.msg(382, "srv", "files", "point every path at this profile")
    q.msg(412, "srv", "app", "that profile's state", ret=True)
    q.msg(448, "user", "app", "types the password")
    q.msg(490, "app", "srv", "POST /auth/unlock {profile, password}")
    q.msg(524, "srv", "key", "unlock(password)")
    q.msg(556, "key", "files", "read salt.bin")
    q.msg(576, "key", "key", "PBKDF2-HMAC-SHA512, 256,000 iterations → key")
    q.msg(630, "key", "files", "open pip.db with the key (verify)")
    q.frame(25, 650, 1095, 1020, "alt", "[wrong password]")
    q.msg(676, "key", "key", "wait 0.25 s × failed attempts")
    q.msg(730, "key", "srv", "False", ret=True)
    q.msg(762, "srv", "app", "401 \"That password did not open your data.\"", ret=True)
    q.msg(790, "app", "user", "shows the error", ret=True)
    q.divider(25, 1095, 808, "[the key opens the database]")
    q.msg(834, "key", "key", "keep the key in memory (and in PIP_DB_KEY)")
    q.msg(886, "key", "srv", "True", ret=True)
    q.msg(916, "srv", "files", "record the last used profile")
    q.msg(944, "srv", "bg", "start catch-up")
    q.msg(966, "srv", "app", "200 {state: unlocked}", ret=True)
    q.msg(990, "app", "user", "opens the home screen", ret=True)
    q.msg(1000, "bg", "files", "drain the session-end queue")
    s.text(130, 1110, "Every request also carries the bearer token from data/api_token.txt.", size=12,
           anchor="start", style="italic")
    save(s, "fig4-11_sequence_sign_in")


# ---------------------------------------------------------------------------
# Figure 4.12  Activity: what happens to one learned candidate (stages 11-13)
# ---------------------------------------------------------------------------
def activity_learning():
    s = Svg(1130, 1660)
    cx, rx = 430, 950
    RW = 250

    def act(x, y, w, h, lab):
        s.box(x - w / 2, y - h / 2, w, h, lab, size=13, rx=14)

    def dia(x, y, w, h, lab):
        s.diamond(x, y, w, h)
        s.text(x, y, lab, size=13)

    def bracket(y1, y2, lab):
        s.line(70, y1, 70, y2, end=None, sw=1.6)
        s.line(70, y1, 82, y1, end=None, sw=1.6)
        s.line(70, y2, 82, y2, end=None, sw=1.6)
        s.vtext(52, (y1 + y2) / 2, lab, size=14)

    s.start_node(cx, 40)
    s.line(cx, 51, cx, 82)
    act(cx, 112, 360, 56, ["Chat ends: 10 idle minutes, a disconnect,", "sign-out, shutdown, or the next start"])
    s.line(cx, 140, cx, 172)
    act(cx, 198, 280, 50, ["Queue the transcript", "(pending_observer)"])
    s.line(cx, 223, cx, 260)
    dia(cx, 308, 250, 96, ["Model local in", "both records?"])
    s.line(cx + 125, 308, rx - RW / 2 - 2, 308)
    s.text(cx + 140, 296, "[no]", size=12, anchor="start", style="italic")
    act(rx, 308, RW, 56, ["Send nothing; keep it queued", "for the next start or sign-in"])
    s.line(rx, 336, rx, 368)
    s.end_node(rx, 382)
    s.line(cx, 356, cx, 390)
    s.text(cx + 8, 372, "[yes]", size=12, anchor="start", style="italic")
    act(cx, 420, 380, 56, ["Extract candidates with the local model:", "memories, decisions, chat record"])
    s.line(cx, 448, cx, 486)
    act(cx, 510, 240, 44, "Take the next candidate")
    s.line(cx, 532, cx, 560)

    dia(cx, 608, 250, 96, ["Quote found in", "the transcript?"])
    s.line(cx + 125, 608, rx - RW / 2 - 2, 608)
    s.text(cx + 140, 596, "[no]", size=12, anchor="start", style="italic")
    act(rx, 608, RW, 56, ["Drop it; audit row", "(stage 11)"])
    s.line(cx, 656, cx, 693)
    s.text(cx + 8, 674, "[yes]", size=12, anchor="start", style="italic")

    dia(cx, 748, 300, 110, ["Evidence gate: do the", "user's own words", "support the claim?"])
    s.line(cx + 150, 748, rx - RW / 2 - 2, 748)
    s.text(cx + 162, 736, "[no]", size=12, anchor="start", style="italic")
    act(rx, 748, RW, 56, ["Reject it; audit row", "(stage 11)"])
    s.line(cx, 803, cx, 838)
    s.text(cx + 8, 820, "[yes]", size=12, anchor="start", style="italic")

    dia(cx, 880, 220, 84, "A decision?")
    s.line(cx + 110, 880, rx - RW / 2 - 2, 880)
    s.text(cx + 124, 868, "[yes]", size=12, anchor="start", style="italic")
    act(rx, 880, RW, 56, ["Log it, or ask the user", "(decision rules)"])
    s.line(cx, 922, cx, 958)
    s.text(cx + 8, 940, "[no, a memory]", size=12, anchor="start", style="italic")

    act(cx, 985, 280, 50, ["Reinforce the evidence", "(observation log)"])
    s.line(cx, 1010, cx, 1048)
    act(cx, 1075, 280, 50, ["Check the Constitution's", "rules and thresholds"])
    s.line(cx, 1100, cx, 1143)
    dia(cx, 1188, 200, 88, "Verdict?")

    # three outcomes of Stage 12, written by Stage 13
    bx = 640
    s.line(cx + 100, 1188, bx, 1188, end=None)
    for y, guard, lab in [
        (1110, "[approved]", ["Write to the user model;", "audit row (stage 13)"]),
        (1210, ["[needs the user's confirmation,", "or short of the count, max 2]"],
         ["Queue a question for the", "user; audit row (deferred)"]),
        (1310, "[refused]", ["Reject it; audit row", "(stage 12)"]),
    ]:
        s.poly([(bx, 1188), (bx, y), (rx - RW / 2 - 2, y)])
        act(rx, y, RW, 56, lab)
        s.text(bx + 8, y - 20 if isinstance(guard, str) else y - 30, guard, size=12, anchor="start",
               style="italic")

    # every outcome but the first rejoins the loop
    bus = rx + RW / 2 + 22
    for y in (608, 748, 880, 1110, 1210, 1310):
        s.line(rx + RW / 2, y, bus, y, end=None)
    s.poly([(bus, 608), (bus, 1420), (cx + 110 + 2, 1420)])
    dia(cx, 1420, 220, 84, ["More", "candidates?"])
    s.poly([(cx - 110, 1420), (200, 1420), (200, 510), (cx - 120 - 2, 510)])
    s.text(206, 1404, "[yes]", size=12, anchor="start", style="italic")
    s.line(cx, 1462, cx, 1500)
    s.text(cx + 8, 1480, "[no]", size=12, anchor="start", style="italic")
    act(cx, 1528, 300, 56, ["Write the chat record and", "mark the chat observed"])
    s.line(cx, 1556, cx, 1590)
    s.end_node(cx, 1604)

    s.text(700, 1505, ["Later, on the Review screen, the user confirms", "or dismisses each queued question.",
                       "Confirm writes it as the user's own; dismiss writes", "nothing. Either way a second audit row",
                       "is added (actor: user)."], size=12, anchor="start", style="italic")

    bracket(84, 226, "Session end")
    bracket(258, 930, "Stage 11: Observer")
    bracket(958, 1235, "Stage 12: Constitution")
    save(s, "fig4-12_activity_learning")


# ---------------------------------------------------------------------------
# Figure 4.8  Package diagram: the backend's packages and their real imports
# (counted from every import statement outside backend/tests, 2026-10-22)
# ---------------------------------------------------------------------------
def package_diagram():
    s = Svg(1240, 1000)
    s.package(440, 20, 360, 86, "frontend/flutter (the app)",
              ["Dart: screens, api_client.dart,", "ws_chat_client.dart"])
    s.package(440, 170, 360, 96, "backend/api",
              ["server.py: 68 REST routes, /ws/chat,", "middleware, api_*(conn, ...) functions",
               "uses FastAPI, Starlette"])
    s.package(40, 350, 420, 210, "backend/core (18 modules)",
              ["pipeline · evidence_gate · constitution_enforcer",
               "constitution_version · types · trace · auth",
               "session_key · db_key · profiles · response_cache",
               "session_lifecycle · pinned_executor · restore",
               "backup_mark · instance_lock · proactive",
               "startup_progress",
               "uses sqlcipher3 (restore.py)"])
    s.package(520, 350, 300, 210, "backend/stages (14 modules)",
              ["one run() each:", "00 gap · 01 intent · 02 route",
               "03 decisions · 04 memory · 05 documents", "06 web search · 07 context",
               "08 provider gate · 09 LLM · 10 delivery", "11 Observer · 12 validation · 13 write",
               "uses ddgs (stage 06)"])
    s.package(900, 350, 300, 160, "backend/providers (3)",
              ["base_provider (BaseLLMProvider)", "ollama_provider", "openai_compatible_provider",
               "uses urllib (standard library)"])
    s.package(40, 660, 780, 130, "backend/memory (11 modules)",
              ["profile_store · conversation_store · decision_log · candidate_store",
               "governance_audit · pending_observer · session_snapshot · verification",
               "vector_store · llm_endpoint_store · avatar_store",
               "uses sqlcipher3, chromadb, sentence-transformers, cryptography, pypdf"])
    s.package(900, 660, 140, 90, "backend/config", ["settings.json", "and its loader"])
    s.package(1060, 660, 140, 90, "shared", ["ws_spec.py", "(chat events)"])

    def dep(pts):
        s.poly(pts, end="open", dash="7 4", sw=1.3)

    s.poly([(620, 106), (620, 168)], end="open", dash="2 3", sw=1.3)
    s.text(628, 137, "HTTP and WebSocket (a network call, not an import)", size=12, anchor="start",
           style="italic")
    dep([(520, 266), (300, 348)])
    dep([(640, 266), (665, 348)])
    dep([(760, 266), (1000, 348)])
    dep([(440, 230), (20, 230), (20, 725), (38, 725)])
    dep([(460, 415), (518, 415)])
    dep([(520, 475), (462, 475)])
    dep([(820, 440), (898, 440)])
    dep([(420, 560), (420, 610), (1150, 610), (1150, 512)])
    dep([(200, 560), (200, 658)])
    dep([(320, 660), (320, 562)])
    dep([(670, 560), (670, 658)])

    s.line(40, 850, 90, 850, end="open", dash="7 4", sw=1.3)
    s.text(100, 850, "imports from (the arrow points at the package imported)", size=12, anchor="start")
    s.text(40, 905, ["Counted from the import statements of every module outside backend/tests (2026-10-22). Both ways "
                     "between core and stages: pipeline.py",
                     "runs the stages, and the stages use core's types, evidence gate, trace and Constitution. Both ways "
                     "between core and memory: core's",
                     "pipeline and sign-in use the stores, and the stores use core's types, keys and trace. Not drawn: "
                     "config is imported by api, core,",
                     "stages, memory and providers; shared by api, core and stages. No module under stages or api "
                     "imports sqlite3 or chromadb (a git hook checks this)."],
           size=12, anchor="start", style="italic")
    save(s, "fig4-8_package_diagram")


# ---------------------------------------------------------------------------
# Figure 4.9  Class diagram: the classes PIP has (backend/, 2026-10-22)
# ---------------------------------------------------------------------------
def class_diagram():
    s = Svg(1400, 1110)

    def frame(x, y, w, h, title):
        s.rect(x, y, w, h, rx=8, dash="6 4", sw=1.0)
        s.text(x + 10, y + 14, title, size=13, anchor="start", weight="bold")

    frame(15, 30, 510, 470, "providers (backend/providers)")
    frame(545, 30, 840, 680, "evidence gate and Constitution (backend/core)")
    frame(15, 520, 510, 330, "chat sessions (backend/core)")
    frame(545, 730, 840, 235, "frozen records")

    base = s.uml_class(110, 60, 300, "BaseLLMProvider", "«abstract»", [],
                       ["+ chat(messages, context, max_tokens,", "      timeout_seconds, response_format)",
                        "      : Iterator[str]", "+ is_available(): bool", "+ get_model_info(): dict"])
    oll = s.uml_class(30, 280, 235, "OllamaProvider", None,
                      ["model_name: str", "host: str = OLLAMA_HOST", "last_counts: dict"],
                      ["+ request_options(max_tokens): dict", "+ chat(...): Iterator[str]", "+ is_available(): bool",
                       "+ get_model_info(): dict"])
    oai = s.uml_class(280, 280, 235, "OpenAICompatibleProvider", None,
                      ["model_name, base_url: str", "provider_id, api_key: str", "is_local: bool",
                       "supports_response_format: bool"],
                      ["+ chat(...): Iterator[str]", "+ is_available(): bool", "+ get_model_info(): dict"])
    bx = base[0] + base[2] / 2
    bb = base[1] + base[3]
    s.poly([(oll[0] + oll[2] / 2, 280), (oll[0] + oll[2] / 2, 250), (oai[0] + oai[2] / 2, 250),
            (oai[0] + oai[2] / 2, 280)], end=None, sw=1.3)
    s.line(bx, 250, bx, bb + 13, end=None, sw=1.3)
    s.tri_end(bx, bb, 0, 1)

    mc = s.uml_class(560, 60, 250, "MemoryCandidate", "«TypedDict»",
                     ["target_table, field_name: str", "proposed_value: str",
                      "label: explicit | inferred | ...", "evidence_count: int", "evidence_text: str",
                      "candidate_id?: str", "conversation_id?: str"], [])
    ce = s.uml_class(860, 60, 250, "ConstitutionEnforcer", None, ["rules: dict (constitutional.json)"],
                     ["+ validate(candidate, existing_field,", "      profile_age_weeks): ValidationResult"])
    vr = s.uml_class(1150, 60, 222, "ValidationResult", None, ["status: str", "reason: str"],
                     ["+ APPROVED()", "+ DISCARD(reason)", "+ REQUIRES_CONFIRMATION(reason)",
                      "+ PROMPT_RECONCILIATION(reason)", "+ TIER_2_REQUIRED(reason)", "+ HARD_REJECT(reason)",
                      "(all class methods)"])
    led = s.uml_class(560, 330, 250, "EvidenceLedger", None, ["turns: list[EvidenceTurn]"],
                      ["+ from_transcript(transcript)  (class method)", "+ locate(quote): list[EvidenceTurn]",
                       "+ user_turns(): list[EvidenceTurn]"])
    turn = s.uml_class(560, 545, 250, "EvidenceTurn", "«TypedDict»",
                       ["index: int", "role: user | assistant | unknown", "text: str", "normalized: str"], [])
    ver = s.uml_class(860, 330, 250, "EvidenceVerdict", None, ["state: str (one of EvidenceState)", "detail: str"],
                      ["+ sufficient: bool  (property)", "+ to_validation_result()", "      : ValidationResult"])
    st = s.uml_class(860, 500, 250, "EvidenceState", "«constants»",
                     ["NO_EVIDENCE", "EVIDENCE_INVALID", "EVIDENCE_NOT_FOUND", "EVIDENCE_NOT_USER_SOURCE",
                      "EVIDENCE_CONTRADICTORY", "EVIDENCE_NOT_ENTAILING", "EVIDENCE_SUFFICIENT"], [])

    def depend(pts, label, lpos):
        s.poly(pts, end="open", dash="7 4", sw=1.3)
        s.label(lpos[0], lpos[1], label, size=12)

    depend([(860, 120), (812, 120)], "reads", (836, 108))
    depend([(1110, 120), (1148, 120)], "creates", (1129, 108))
    depend([(1060, 330), (1060, 300), (1200, 300), (1200, vr[1] + vr[3] + 2)], "creates", (1130, 288))
    # composition: a ledger holds its turns
    lx = led[0] + led[2] / 2
    s.line(lx, led[1] + led[3] + 22, lx, 545, end=None, sw=1.3)
    s.diamond_end(lx, led[1] + led[3], 0, 1, filled=True)
    s.text(lx + 8, 535, "0..*", size=12, anchor="start")
    s.text(lx + 8, led[1] + led[3] + 12, "1", size=12, anchor="start")
    # verdict has a state
    vx = ver[0] + ver[2] / 2
    s.line(vx, ver[1] + ver[3], vx, 498, sw=1.3)
    s.text(vx + 8, (ver[1] + ver[3] + 498) / 2, "state", size=12, anchor="start", style="italic")

    s.note(1150, 330, 222, 150, ["evidence_gate.adjudicate(", "  candidate, ledger)", "  -> EvidenceVerdict",
                                 "is a module function, not", "a method. stage_11_observer",
                                 "makes the ledger and the", "enforcer at session end."], size=12)
    s.line(1150, 405, 1112, 405, end=None, dash="3 3", sw=1.0)

    reg = s.uml_class(30, 560, 250, "SessionRegistry", None,
                      ["_sessions: dict", "_lock: Lock", "shutting_down: bool"],
                      ["+ register(session_id, conn, executor,", "      conversation_history, session_state)",
                       "+ unregister(session_id)", "+ snapshot(): list[dict]"])
    pe = s.uml_class(335, 560, 180, "PinnedExecutor", None, ["_queue: Queue", "_thread: Thread (daemon)"],
                     ["+ submit(fn): Future", "+ shutdown(wait, cancel_futures)", "+ thread: Thread  (property)"])
    ry = reg[1] + 60
    s.line(reg[0] + reg[2] + 22, ry, pe[0], ry, end=None, sw=1.3)
    s.diamond_end(reg[0] + reg[2], ry, 1, 0, filled=False)
    s.text(pe[0] - 30, ry + 14, "0..*", size=12, anchor="start")
    s.note(30, 760, 485, 72, ["server.py keeps one SessionRegistry for the process and opens one PinnedExecutor",
                              "(one daemon thread) per chat socket: a SQLCipher connection must stay on the",
                              "thread that opened it."], size=12)

    s.uml_class(560, 770, 250, "Profile", "«dataclass, frozen» core/profiles.py",
                ["slug, name: str", "data_dir, created_at: str", "last_used: str | None"],
                ["+ paths(data_root): dict[str, Path]", "+ exists(data_root): bool"])
    s.uml_class(860, 770, 250, "ConsentRecord", "«dataclass, frozen» stages/stage_08",
                ["provider_id: str", "is_cloud: bool", "user_consented: bool", "consent_scope: str",
                 "revoked: bool"], [])
    s.note(1150, 760, 222, 205, ["Exceptions, each a subclass", "of Exception / RuntimeError", "(\"Error\" left off the names):",
                                 "providers: ProviderUnavailable,", "  ProviderExecution, PullCancelled",
                                 "stages: ProviderConsent,", "  ObserverLocalProvider,", "  ObserverUnavailable",
                                 "core: Restore, WrongPassword,", "  NoSalt, AlreadyRunning,",
                                 "  IncompleteBackup", "memory: IndexLocked, DocumentFile"], size=12)

    s.line(30, 1000, 75, 1000, end=None, sw=1.3)
    s.tri_end(75, 1000, -1, 0)
    s.text(90, 1000, "is a kind of", size=12, anchor="start")
    s.line(200, 1000, 245, 1000, end="open", dash="7 4", sw=1.3)
    s.text(255, 1000, "uses or creates", size=12, anchor="start")
    s.line(390, 1000, 435, 1000, end=None, sw=1.3)
    s.diamond_end(390, 1000, 1, 0, filled=True)
    s.text(445, 1000, "holds (composition)", size=12, anchor="start")
    s.line(600, 1000, 645, 1000, end=None, sw=1.3)
    s.diamond_end(600, 1000, 1, 0, filled=False)
    s.text(655, 1000, "keeps (aggregation)", size=12, anchor="start")
    s.text(30, 1050, ["PIP is written mostly as module-level functions (one run() per stage; store functions that take the "
                      "database connection first), so this", "shows every class it has outside the tests, except the "
                      "event TypedDicts of shared/ws_spec.py and a few private helpers."],
           size=12, anchor="start", style="italic")
    save(s, "fig4-9_class_diagram")


if __name__ == "__main__":
    architecture()
    use_case()
    dfd0()
    dfd1()
    dfd2_message()
    dfd2_learning()
    er_work()
    er_user_model()
    package_diagram()
    class_diagram()
    seq_chat()
    seq_sign_in()
    activity_learning()
