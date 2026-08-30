// PIP Web Client
//
// Part 14.4: "Frontend has zero intelligence. All logic in PIP Core backend.
// Client always goes through POST/WS to PIP Core. Client never talks directly
// to DB, ChromaDB, or Ollama." This file is a thin renderer over the REST/WS
// API - every value shown here came directly from a server response, nothing
// is computed or inferred client-side beyond basic DOM state (which tab is
// active, the current chat transcript).
//
// Part 14.2: WebSocket (/ws/chat) for ALL chat, REST for everything else.
// REST /chat does not exist (ADR-028).

const API_BASE = "/api/v1";
let ws = null;
let currentProjectId = null;
let pendingStageHints = null; // buffered, not rendered until "done"/"error"

// Security fix: every /api/v1/* route and /ws/chat now require a token read
// from data/api_token.txt (see backend/core/auth.py). Not printed by the
// server (never logged) - the operator reads it from that file and passes
// it in via this page's own URL, e.g. http://127.0.0.1:8765/?token=<token>.
// Read once on load, carried in memory for the rest of the session only -
// never written to localStorage/sessionStorage, so it doesn't outlive the tab.
const API_TOKEN = new URLSearchParams(location.search).get("token") || "";

// ---------------------------------------------------------------- API helpers

// FastAPI reports a refusal as {"detail": "..."} - that sentence is the whole
// point of a 422 (see the memory review queue, where a candidate can exist and
// still be unapplicable), so it is unwrapped here rather than shown to the user
// as a JSON envelope.
async function readError(res) {
  const raw = await res.text();
  try {
    const parsed = JSON.parse(raw);
    return typeof parsed.detail === "string" ? parsed.detail : raw;
  } catch {
    return raw;
  }
}

async function apiGet(path) {
  const res = await fetch(API_BASE + path, { headers: { "Authorization": `Bearer ${API_TOKEN}` } });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${API_TOKEN}` },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

async function apiPatch(path, body) {
  const res = await fetch(API_BASE + path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", "Authorization": `Bearer ${API_TOKEN}` },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ------------------------------------------------------------------ Onboarding

async function checkOnboarding() {
  const status = await apiGet("/status");
  if (!status.onboarding_complete) {
    document.getElementById("onboarding").classList.remove("hidden");
  } else {
    startApp();
  }
}

function parseCsv(value, limit) {
  if (!value) return undefined;
  const items = value.split(",").map((s) => s.trim()).filter(Boolean);
  return limit ? items.slice(0, limit) : items;
}

async function submitOnboarding(event) {
  event.preventDefault();
  const form = event.target;
  const errorEl = document.getElementById("onboarding-error");
  errorEl.classList.add("hidden");

  const payload = {
    name: form.name.value,
    language_preference: form.language_preference.value,
    timezone: form.timezone.value || undefined,
    skills: parseCsv(form.skills.value, 3),
    interaction_style: form.interaction_style.value || undefined,
    preferred_tools: parseCsv(form.preferred_tools.value, 5),
  };
  if (form.project_name.value) {
    payload.current_project = {
      name: form.project_name.value,
      description: form.project_description.value || "",
    };
  }

  try {
    await apiPost("/onboarding/complete", payload);
    document.getElementById("onboarding").classList.add("hidden");
    startApp();
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove("hidden");
  }
}

// ----------------------------------------------------------------------- Chat

function connectChat() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${proto}//${location.host}/ws/chat?token=${encodeURIComponent(API_TOKEN)}`);
  const statusEl = document.getElementById("connection-status");

  ws.onopen = () => {
    statusEl.textContent = "connected";
    statusEl.className = "status connected";
  };
  ws.onclose = () => {
    statusEl.textContent = "disconnected - reconnecting…";
    statusEl.className = "status disconnected";
    setTimeout(connectChat, 2000);
  };
  ws.onerror = () => ws.close();
  ws.onmessage = (event) => handleChatEvent(JSON.parse(event.data));
}

function handleChatEvent(msg) {
  switch (msg.type) {
    case "stage_hint":
      pendingStageHints = msg.data;
      break;
    case "token":
      appendToCurrentAssistantMessage(msg.data);
      break;
    case "done":
      renderStageHints(pendingStageHints);
      break;
    case "error":
      appendSystemMessage("Error: " + msg.data);
      renderStageHints(pendingStageHints);
      break;
  }
}

function chatLog() {
  return document.getElementById("chat-log");
}

function appendUserMessage(text) {
  const div = document.createElement("div");
  div.className = "msg msg-user";
  div.innerHTML = `<div class="bubble"></div>`;
  div.querySelector(".bubble").textContent = text;
  chatLog().appendChild(div);
  chatLog().scrollTop = chatLog().scrollHeight;
}

let currentAssistantBubble = null;

function startAssistantMessage() {
  const div = document.createElement("div");
  div.className = "msg msg-assistant";
  div.innerHTML = `<div class="bubble"></div>`;
  chatLog().appendChild(div);
  currentAssistantBubble = div.querySelector(".bubble");
  chatLog().scrollTop = chatLog().scrollHeight;
}

function appendToCurrentAssistantMessage(token) {
  if (!currentAssistantBubble) startAssistantMessage();
  currentAssistantBubble.textContent += token;
  chatLog().scrollTop = chatLog().scrollHeight;
}

function appendSystemMessage(text) {
  const div = document.createElement("div");
  div.className = "msg msg-system";
  div.textContent = text;
  chatLog().appendChild(div);
  chatLog().scrollTop = chatLog().scrollHeight;
}

// Part 14.3: stage_hints render as a static snapshot once the response
// completes, not live per-event - "live animated per-stage updates are
// optional polish, not budgeted."
function renderStageHints(hints) {
  const body = document.getElementById("stage-hints-body");
  if (!hints) {
    body.innerHTML = '<span class="muted">No response yet.</span>';
    return;
  }
  const rows = [
    ["Decision Log hit", hints.decision_log_hit],
    ["Web search used", hints.web_search_used],
    ["Served from cache", hints.cache_hit],
    ["Model cold-loading", hints.model_loading],
  ];
  body.innerHTML = rows
    .map(([label, val]) => `<div class="hint-row"><span>${label}</span><span class="${val ? "hint-yes" : "hint-no"}">${val ? "yes" : "no"}</span></div>`)
    .join("");
  currentAssistantBubble = null;
}

function submitChatMessage(event) {
  event.preventDefault();
  const input = document.getElementById("chat-input");
  const text = input.value.trim();
  if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

  appendUserMessage(text);
  startAssistantMessage();
  pendingStageHints = null;
  ws.send(JSON.stringify({ message: text, project_id: currentProjectId }));
  input.value = "";
}

// -------------------------------------------------------------------- Profile

async function loadProfile() {
  const fields = await apiGet("/memory/profile");
  const tbody = document.querySelector("#profile-table tbody");
  if (fields.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="muted">No profile fields yet.</td></tr>';
    return;
  }
  tbody.innerHTML = fields
    .map(
      (f) => `<tr>
        <td>${escapeHtml(f.table)}</td>
        <td>${escapeHtml(f.field)}</td>
        <td>${escapeHtml(String(f.value))}</td>
        <td>${f.confidence != null ? f.confidence.toFixed(2) : "-"}</td>
        <td>${escapeHtml(f.source_label || "-")}</td>
      </tr>`
    )
    .join("");
}

// ------------------------------------------------------------------ Decisions

async function loadDecisions(query) {
  const q = query ? `?q=${encodeURIComponent(query)}` : "";
  const decisions = await apiGet(`/decision/search${q}`);
  const list = document.getElementById("decision-list");
  if (decisions.length === 0) {
    list.innerHTML = '<li class="muted">No decisions found.</li>';
    return;
  }
  list.innerHTML = decisions
    .map(
      (d) => `<li>
        <div>${escapeHtml(d.decision_text)}</div>
        <div class="item-meta">confidence ${d.confidence.toFixed(2)} · ${escapeHtml(d.state)} · ${escapeHtml(d.created_at)}</div>
      </li>`
    )
    .join("");
}

async function submitDecisionSearch(event) {
  event.preventDefault();
  await loadDecisions(document.getElementById("decision-search-input").value);
}

async function submitDecisionCreate(event) {
  event.preventDefault();
  const form = event.target;
  const resultEl = document.getElementById("decision-create-result");
  try {
    const result = await apiPost("/decision/create", {
      text: form.text.value,
      reasoning: form.reasoning.value || undefined,
      alternatives: form.alternatives.value || undefined,
      project_id: currentProjectId || undefined,
    });
    resultEl.textContent =
      result.status === "logged"
        ? `Logged (confidence ${result.confidence.toFixed(2)}).`
        : `Confidence too low to auto-log (${result.confidence.toFixed(2)}) - saved as a pending candidate.`;
    form.reset();
    await loadDecisions();
  } catch (err) {
    resultEl.textContent = "Error: " + err.message;
  }
}

// ------------------------------------------------------------------- Projects

async function loadProjects() {
  const projects = await apiGet("/projects");
  const list = document.getElementById("project-list");
  if (projects.length === 0) {
    list.innerHTML = '<li class="muted">No projects yet.</li>';
    return;
  }
  list.innerHTML = projects
    .map(
      (p) => `<li>
        <div>${escapeHtml(p.name)} ${p.project_id === currentProjectId ? "· <strong>active</strong>" : ""}</div>
        <div class="item-meta">${escapeHtml(p.description || "")}</div>
        <div class="item-meta">status: ${escapeHtml(p.status)}</div>
        <button class="small" data-activate="${escapeHtml(p.project_id)}">Set active</button>
      </li>`
    )
    .join("");
  list.querySelectorAll("[data-activate]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await apiPost(`/projects/${btn.dataset.activate}/activate`);
      currentProjectId = btn.dataset.activate;
      await loadProjects();
    });
  });
}

async function submitProjectCreate(event) {
  event.preventDefault();
  const form = event.target;
  await apiPost("/projects", { name: form.name.value, description: form.description.value });
  form.reset();
  await loadProjects();
}

// ------------------------------------------------------------------ Providers

async function loadProviders() {
  const providers = await apiGet("/providers");
  const tbody = document.querySelector("#provider-table tbody");
  tbody.innerHTML = providers
    .map((p) => {
      const consented = p.user_consented && !p.revoked;
      const actionBtn = p.is_cloud
        ? consented
          ? `<button class="small danger" data-revoke="${escapeHtml(p.provider_id)}">Revoke</button>`
          : `<button class="small" data-consent="${escapeHtml(p.provider_id)}">Grant consent</button>`
        : '<span class="muted">n/a (local)</span>';
      return `<tr>
        <td>${escapeHtml(p.provider_id)}</td>
        <td>${p.is_cloud ? "cloud" : "local"}</td>
        <td>${p.is_cloud ? (consented ? "granted" : p.revoked ? "revoked" : "not consented") : "n/a"}</td>
        <td>${escapeHtml(p.consent_scope || "-")}</td>
        <td>${actionBtn}</td>
      </tr>`;
    })
    .join("");

  tbody.querySelectorAll("[data-consent]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await apiPost(`/providers/${btn.dataset.consent}/consent`, { consent_scope: "full_inference" });
      await loadProviders();
    });
  });
  tbody.querySelectorAll("[data-revoke]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await apiPost(`/providers/${btn.dataset.revoke}/revoke`);
      await loadProviders();
    });
  });
}

// --------------------------------------------------------------------- Review

// Part 14.4 keeps all intelligence in the backend, and these maps do not break
// that: nothing here decides anything. The server says WHY a candidate is
// waiting (origin, validation_status) and these turn that code into the
// sentence a person can answer. No candidate is filtered, ranked, or judged
// client-side - the list is rendered in the order the server returned it.
const MEMORY_QUESTION = {
  verification: "Do I still have this right?",
  observer: "Should I remember this?",
};

const MEMORY_REASON = {
  REQUIRES_CONFIRMATION: "This is something PIP is not allowed to record without asking.",
  TIER_2_REQUIRED: "This disagrees with something already recorded confidently.",
  PROMPT_RECONCILIATION: "You stated one thing, and PIP has repeatedly observed another.",
};

const TABLE_LABEL = {
  preference_memory: "Preference",
  skill_memory: "Skill",
  goal_memory: "Goal",
  active_projects: "Project",
  interaction_style: "Answer style",
  topic_interests: "Topic",
  identity: "Identity",
};

function reviewItemHtml(c) {
  const label = TABLE_LABEL[c.target_table] || c.target_table;
  const isCheck = c.origin === "verification";
  const question = MEMORY_QUESTION[c.origin] || MEMORY_QUESTION.observer;

  // evidence_text means two different things depending on origin, and rendering
  // both the same way said something false. For an Observer candidate it is the
  // user's own words, quoted back - that is what the quote styling is for. For
  // a periodic check it is a sentence the BACKEND wrote about its own record
  // ("recorded as inferred, never confirmed"), so quoting it would attribute
  // PIP's note to the user. It also already explains itself better than the
  // status map can: MEMORY_REASON keys on validation_status, and a check is
  // REQUIRES_CONFIRMATION for a different reason than a gated field is, so the
  // generic sentence read as a flat contradiction of the question above it -
  // "Do I still have this right?" answered by "PIP is not allowed to record
  // this without asking", about something already recorded.
  const explanation = isCheck ? (c.evidence_text || "") : (MEMORY_REASON[c.validation_status] || "");
  const quote = !isCheck && c.evidence_text
    ? `<div class="review-evidence">${escapeHtml(c.evidence_text)}</div>`
    : "";
  return `<li data-memory-id="${c.id}">
    <div class="review-question">${escapeHtml(question)}</div>
    <div class="review-claim">${escapeHtml(label)} · <strong>${escapeHtml(c.field_name)}</strong>: ${escapeHtml(String(c.proposed_value))}</div>
    ${quote}
    <div class="item-meta">${escapeHtml(explanation)}</div>
    <div class="review-actions">
      <button class="small primary" data-confirm-memory="${c.id}">Yes, keep it</button>
      <button class="small" data-dismiss-memory="${c.id}">No</button>
      <span class="review-error hidden"></span>
    </div>
  </li>`;
}

async function loadReview() {
  const [memory, decisions, proactive] = await Promise.all([
    apiGet("/memory/pending"),
    apiGet("/decision/pending"),
    apiGet("/proactive"),
  ]);

  const memoryList = document.getElementById("memory-pending-list");
  memoryList.innerHTML = memory.length
    ? memory.map(reviewItemHtml).join("")
    : '<li class="muted">Nothing waiting. PIP will ask here when it needs to.</li>';

  const decisionList = document.getElementById("decision-pending-list");
  decisionList.innerHTML = decisions.length
    ? decisions
        .map(
          (d) => `<li data-decision-id="${d.id}">
            <div class="review-question">Was this a decision you made?</div>
            <div class="review-claim">${escapeHtml(d.decision_text)}</div>
            ${d.raw_quote ? `<div class="review-evidence">${escapeHtml(d.raw_quote)}</div>` : ""}
            <div class="item-meta">confidence ${d.confidence.toFixed(2)} · signals: ${escapeHtml((d.signals_found || []).join(", ") || "none")}</div>
            <div class="review-actions">
              <button class="small primary" data-promote-decision="${d.id}">Log it</button>
              <button class="small" data-dismiss-decision="${d.id}">No</button>
              <span class="review-error hidden"></span>
            </div>
          </li>`
        )
        .join("")
    : '<li class="muted">No decision candidates waiting.</li>';

  const proactiveList = document.getElementById("proactive-list");
  proactiveList.innerHTML = proactive.length
    ? proactive.map((t) => `<li>${escapeHtml(describeTrigger(t))}</li>`).join("")
    : '<li class="muted">Nothing to raise.</li>';

  bindReviewActions();
  await refreshReviewBadge();
}

function describeTrigger(t) {
  if (t.trigger === "session_gap_exceeds_48h") {
    return `It has been about ${Math.floor(t.hours_elapsed / 24)} day(s) since your last session.`;
  }
  if (t.trigger === "goal_inactive_14_days") {
    return `Goal not mentioned in over ${t.threshold_days} days: ${t.goal_text}`;
  }
  if (t.trigger === "document_decision_conflict_detected") {
    return `A document may disagree with a recorded decision - "${t.decision_text}" vs ${t.document_path}`;
  }
  return t.trigger;
}

// One handler shape for all four buttons: run the call, and on failure show the
// server's reason on the item itself rather than silently leaving the row
// looking unchanged. A confirm can legitimately fail with 422 - the candidate
// exists but cannot be applied - and that is exactly the case a user must not
// be left guessing about.
function bindAction(attr, handler) {
  document.querySelectorAll(`[${attr}]`).forEach((btn) => {
    btn.addEventListener("click", async () => {
      const item = btn.closest("li");
      const errorEl = item.querySelector(".review-error");
      errorEl.classList.add("hidden");
      item.querySelectorAll("button").forEach((b) => (b.disabled = true));
      try {
        await handler(btn.getAttribute(attr));
        await loadReview();
      } catch (err) {
        errorEl.textContent = err.message;
        errorEl.classList.remove("hidden");
        item.querySelectorAll("button").forEach((b) => (b.disabled = false));
      }
    });
  });
}

function bindReviewActions() {
  bindAction("data-confirm-memory", (id) => apiPost(`/memory/pending/${id}/confirm`));
  bindAction("data-dismiss-memory", (id) => apiPost(`/memory/pending/${id}/dismiss`));
  bindAction("data-promote-decision", (id) => apiPost(`/decision/pending/${id}/promote`));
  bindAction("data-dismiss-decision", (id) => apiPost(`/decision/pending/${id}/dismiss`));
}

// The badge is why /status reports both counts: without it the only way to
// discover PIP is waiting on you is to already know the tab exists and open it.
async function refreshReviewBadge() {
  const badge = document.getElementById("review-badge");
  try {
    const status = await apiGet("/status");
    const waiting = (status.pending_memory || 0) + (status.pending_decisions || 0);
    badge.textContent = String(waiting);
    badge.classList.toggle("hidden", waiting === 0);
  } catch {
    badge.classList.add("hidden");
  }
}

// --------------------------------------------------------------------- Views

const viewLoaders = {
  review: loadReview,
  profile: loadProfile,
  decisions: () => loadDecisions(),
  projects: loadProjects,
  providers: loadProviders,
};

function showView(name) {
  document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
  document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
  document.getElementById(`view-${name}`).classList.add("active");
  document.querySelector(`.tab[data-view="${name}"]`).classList.add("active");
  if (viewLoaders[name]) viewLoaders[name]().catch((err) => console.error(err));
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// --------------------------------------------------------------------- Init

function startApp() {
  document.getElementById("app").classList.remove("hidden");
  connectChat();
  renderStageHints(null);
  // On load rather than only when the tab is opened: the Observer runs at
  // session end, so a queue filled by the last conversation would otherwise go
  // unnoticed until the user happened to look.
  refreshReviewBadge().catch((err) => console.error(err));
}

function setupEventListeners() {
  document.getElementById("onboarding-form").addEventListener("submit", submitOnboarding);
  document.getElementById("chat-form").addEventListener("submit", submitChatMessage);
  document.getElementById("decision-search-form").addEventListener("submit", submitDecisionSearch);
  document.getElementById("decision-create-form").addEventListener("submit", submitDecisionCreate);
  document.getElementById("project-create-form").addEventListener("submit", submitProjectCreate);
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => showView(tab.dataset.view));
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  checkOnboarding().catch((err) => {
    console.error(err);
    document.body.innerHTML = `<div class="card" style="margin:40px auto;max-width:500px;"><h1>Can't reach PIP</h1><p>${escapeHtml(err.message)}</p></div>`;
  });
});
