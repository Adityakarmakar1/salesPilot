"use strict";
/* SalesPilot AI — static SPA. Talks to the backend at relative /api/v1.
   JWT in localStorage. No build step, no framework, no fake data:
   every number and row below comes from the API or is an honest empty state. */

const API = "/api/v1";
const $ = (s, r) => (r || document).querySelector(s);
const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const token = () => localStorage.getItem("sp_token");
const setToken = (t) => (t ? localStorage.setItem("sp_token", t) : localStorage.removeItem("sp_token"));

/* ---------- inline SVG icons (Lucide-style, stroke) ---------- */
const ICONS = {
  pilot: '<path d="M12 2v4"/><path d="M12 6c4 0 7 2.5 7 6l-2 7h-3l-1-4h-2l-1 4H7l-2-7c0-3.5 3-6 7-6z"/><circle cx="12" cy="10" r="1.4"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.2 3.4-5 6.5-5s5.7 1.8 6.5 5"/><path d="M16 5.2a3.5 3.5 0 0 1 0 5.9M17.8 15.4c2 .6 3.3 2.1 3.8 4.6"/>',
  phone: '<path d="M5 4h4l2 5-2.5 1.5a12 12 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z"/>',
  bot: '<rect x="4" y="8" width="16" height="11" rx="2.5"/><path d="M12 8V4M8 4h8"/><circle cx="9" cy="13.5" r="1" fill="currentColor"/><circle cx="15" cy="13.5" r="1" fill="currentColor"/><path d="M9.5 16.8h5"/>',
  mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  plug: '<path d="M9 3v5M15 3v5M7 8h10v3a5 5 0 0 1-10 0V8zM12 16v5"/>',
  building: '<rect x="5" y="3" width="14" height="18" rx="1.5"/><path d="M9 7h2M13 7h2M9 11h2M13 11h2M9 15h2M13 15h2M10 21v-3h4v3"/>',
  user: '<circle cx="12" cy="8" r="3.6"/><path d="M5 20c.9-3.4 3.7-5.2 7-5.2s6.1 1.8 7 5.2"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  sparkles: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z"/><path d="M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15z"/>',
  trash: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13M10 11v6M14 11v6"/>',
  edit: '<path d="M16.5 4.5l3 3L8 19H5v-3L16.5 4.5z"/><path d="M14.5 6.5l3 3"/>',
  eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
};
function icon(name) {
  return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (ICONS[name] || "") + "</svg>";
}
$$("[data-icon]").forEach((el) => { el.innerHTML = icon(el.getAttribute("data-icon")); });

function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.remove("hidden");
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.add("hidden"), 3200);
}

/* ---------- API ---------- */
async function api(path, opts) {
  opts = opts || {};
  const headers = Object.assign({}, opts.headers || {});
  if (token()) headers["Authorization"] = "Bearer " + token();
  let body = opts.body;
  if (body && !(body instanceof FormData) && typeof body !== "string") {
    headers["Content-Type"] = "application/json"; body = JSON.stringify(body);
  }
  let res;
  try { res = await fetch(API + path, { method: opts.method || "GET", headers, body }); }
  catch (e) { throw new Error("Network error — could not reach the API at " + API + "."); }
  if (res.status === 401) { logout(); throw new Error("Session expired — please sign in again."); }
  const text = await res.text();
  let data = null; try { data = text ? JSON.parse(text) : null; } catch (e) { /* non-JSON */ }
  if (!res.ok) {
    const msg = (data && (data.detail || data.message || data.error)) || ("Request failed (HTTP " + res.status + ")");
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}
const listOf = (d) => (Array.isArray(d) ? d : (d && (d.items || d.results || d.data)) || []);
const objOf = (d) => (d && typeof d === "object" && !Array.isArray(d) ? d : {});
const arrOf = (v) => (Array.isArray(v) ? v : []);
const pct = (v) => { if (v === null || v === undefined || v === "") return "—"; const n = Number(v); if (isNaN(n)) return String(v); return (n <= 1 && n !== 0 ? (n * 100).toFixed(1) : n.toFixed ? (Number.isInteger(n) ? String(n) : n.toFixed(1)) : String(n)) + (n <= 1 ? "%" : "%"); };
function categoryBadge(cat) { const c = String(cat || ""); const cls = /hot/i.test(c) ? "hot" : /warm/i.test(c) ? "warm" : /cold/i.test(c) ? "cold" : "ok"; return c ? '<span class="badge ' + cls + '">' + esc(c) + "</span>" : ""; }
function distList(dist) { const e = Object.entries(objOf(dist)); return e.length ? '<div>' + e.map(([k, v]) => '<div class="member-row"><span>' + esc(k) + '</span><span style="margin-left:auto"><b>' + esc(typeof v === "object" ? JSON.stringify(v) : v) + "</b></span></div>").join("") + "</div>" : '<p class="muted">No data yet.</p>'; }
function countedList(items) { const a = arrOf(items); if (!a.length) return '<p class="muted">None recorded yet.</p>'; return "<div>" + a.map((it) => { if (typeof it === "string") return '<div class="member-row"><span>' + esc(it) + "</span></div>"; const name = it.name || it.text || it.value || it.label || JSON.stringify(it); const cnt = it.count != null ? it.count : (it.occurrences != null ? it.occurrences : ""); return '<div class="member-row"><span>' + esc(name) + '</span>' + (cnt !== "" ? '<span style="margin-left:auto"><b>' + esc(cnt) + "</b></span>" : "") + "</div>"; }).join("") + "</div>"; }
function bantTable(bant) { const b = objOf(bant); const keys = ["budget", "authority", "need", "timeline"]; if (!keys.some((k) => b[k])) return '<p class="muted">No BANT data.</p>'; return '<table class="table"><thead><tr><th>Factor</th><th>Value</th><th>Level</th><th>Confidence</th><th>Quote</th></tr></thead><tbody>' + keys.map((k) => { const x = objOf(b[k]); return "<tr><td><b>" + k + "</b></td><td>" + esc(x.value != null ? x.value : "—") + "</td><td>" + esc(x.level != null ? x.level : "—") + "</td><td>" + esc(x.confidence != null ? x.confidence : "—") + "</td><td><i>" + esc(x.quote || "—") + "</i></td></tr>"; }).join("") + "</tbody></table>"; }
function contextHTML(ctx, title) { if (!ctx) return ""; const c = objOf(ctx); const fb = arrOf(c.open_followups); const bant = c.known_bant ? bantTable(typeof c.known_bant === "object" ? (c.known_bant.bant || c.known_bant) : {}) : ""; return '<div class="card" style="margin:12px 0;background:var(--surface2)"><div class="card-head"><h3>' + esc(title || "Context loaded for this session") + '</h3></div>' + (c.last_summary ? '<p><b>Last summary:</b> ' + esc(c.last_summary) + "</p>" : "") + bant + (fb.length ? "<h4>Open follow-ups</h4>" + countedList(fb) : "") + "</div>"; }
async function downloadAuthed(path, filename) { const res = await fetch(API + path, { headers: token() ? { Authorization: "Bearer " + token() } : {} }); if (!res.ok) { let msg = "Download failed (HTTP " + res.status + ")"; try { const d = await res.json(); msg = d.detail || d.message || msg; } catch (e) {} throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg)); } const blob = await res.blob(); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 4000); }


/* ---------- auth ---------- */
let me = null, myOrg = null;
function showAuth() { $("#authView").classList.remove("hidden"); $("#appView").classList.add("hidden"); }
function showApp() { $("#authView").classList.add("hidden"); $("#appView").classList.remove("hidden"); }
function logout() { setToken(null); me = null; myOrg = null; showAuth(); }

$("#tabLogin").addEventListener("click", () => switchAuthTab(true));
$("#tabRegister").addEventListener("click", () => switchAuthTab(false));
function switchAuthTab(login) {
  $("#tabLogin").classList.toggle("active", login);
  $("#tabRegister").classList.toggle("active", !login);
  $("#loginForm").classList.toggle("hidden", !login);
  $("#registerForm").classList.toggle("hidden", login);
}
$("#loginForm").addEventListener("submit", async (e) => {
  e.preventDefault(); $("#loginError").textContent = "";
  try {
    const d = await api("/auth/login", { method: "POST", body: { email: $("#loginEmail").value.trim(), password: $("#loginPassword").value } });
    setToken(d.access_token); await boot();
  } catch (err) { $("#loginError").textContent = err.message; }
});
$("#registerForm").addEventListener("submit", async (e) => {
  e.preventDefault(); $("#registerError").textContent = "";
  try {
    const d = await api("/auth/register", { method: "POST", body: { email: $("#regEmail").value.trim(), password: $("#regPassword").value, organization_name: $("#regOrg").value.trim() } });
    setToken(d.access_token); await boot();
  } catch (err) { $("#registerError").textContent = err.message; }
});
$("#logoutBtn").addEventListener("click", logout);

async function boot() {
  if (!token()) { showAuth(); return; }
  try {
    me = await api("/auth/me");
    try { myOrg = await api("/organizations/current"); } catch (e) { myOrg = null; }
  } catch (e) { showAuth(); return; }
  $("#userEmail").textContent = (me && (me.email || me.name)) || "Signed in";
  $("#orgChip").textContent = (myOrg && myOrg.name) || "Organization";
  showApp();
  const start = (location.hash || "#dashboard").slice(1);
  navigate(VIEWS[start] ? start : "dashboard");
}

/* ---------- routing ---------- */
const VIEWS = { dashboard: "Dashboard", leads: "Leads", agents: "AI Agents", voice: "Live Voice Testing", calls: "Call History", kb: "Knowledge Base", appointments: "Appointments", tasks: "Tasks", analytics: "Analytics", integrations: "Integrations", organization: "Organization", compliance: "Compliance & Launch Readiness" };
let currentView = "dashboard";
function navigate(view) {
  currentView = view;
  Object.keys(VIEWS).forEach((v) => $("#view-" + v).classList.toggle("hidden", v !== view));
  $$(".nav-item").forEach((a) => a.classList.toggle("active", a.getAttribute("data-nav") === view));
  $("#pageTitle").textContent = VIEWS[view];
  if (location.hash !== "#" + view) history.replaceState(null, "", "#" + view);
  $("#sidebar").classList.remove("open"); $("#sidebarScrim").classList.remove("on");
  if (view === "dashboard") loadDashboard();
  if (view === "leads") loadLeads();
  if (view === "agents") loadAgents();
  if (view === "voice") loadVoiceSetup();
  if (view === "calls") loadCalls();
  if (view === "integrations") loadIntegrations();
  if (view === "organization") loadOrganization();
  if (view === "kb") loadKB();
  if (view === "appointments") loadAppointments();
  if (view === "tasks") loadTasks();
  if (view === "analytics") loadAnalytics();
  if (view === "compliance") loadCompliance();
}
$$(".nav-item").forEach((a) => a.addEventListener("click", () => navigate(a.getAttribute("data-nav"))));
$$("[data-goto]").forEach((b) => b.addEventListener("click", () => navigate(b.getAttribute("data-goto"))));
$("#menuBtn").addEventListener("click", () => { $("#sidebar").classList.add("open"); $("#sidebarScrim").classList.add("on"); });
$("#sidebarScrim").addEventListener("click", () => navigate(currentView));
window.addEventListener("hashchange", () => { const v = location.hash.slice(1); if (VIEWS[v] && v !== currentView && token()) navigate(v); });

/* ---------- modals ---------- */
$$("[data-close]").forEach((b) => b.addEventListener("click", () => $("#" + b.getAttribute("data-close")).classList.add("hidden")));
$$(".modal-wrap").forEach((w) => w.addEventListener("click", (e) => { if (e.target === w) w.classList.add("hidden"); }));
const openModal = (id) => $("#" + id).classList.remove("hidden");
const closeModal = (id) => $("#" + id).classList.add("hidden");

/* ---------- dashboard ---------- */
const KPI_DEFS = [
  ["total_leads", "Total leads"], ["total_calls", "Total calls"], ["completed_calls", "Completed calls"],
  ["qualified_leads", "Qualified leads"], ["hot_leads", "Hot leads"], ["warm_leads", "Warm leads"],
  ["cold_leads", "Cold leads"], ["appointments_booked", "Appointments booked"],
  ["followups_due", "Follow-ups due"], ["followups_scheduled", "Follow-ups scheduled"], ["conversion_rate", "Conversion rate"],
];
const PALETTE = ["#5b8cff", "#3fb97f", "#e0a83e", "#9a7bff", "#e05c5c", "#4fc3d9", "#b8c04f", "#e07fb0", "#7d8aa5", "#5cd0b3", "#d98c4f", "#8a94e0", "#67b76a", "#c46fd9"];
function findDist(data, keys) {
  for (const k of keys) if (data && data[k] && typeof data[k] === "object" && !Array.isArray(data[k])) return data[k];
  return null;
}
function donutSVG(dist) {
  const entries = Object.entries(dist).filter(([, v]) => Number(v) > 0);
  const total = entries.reduce((s, [, v]) => s + Number(v), 0);
  if (!total) return '<p class="muted">No data yet.</p>';
  let acc = 0; const R = 52, C = 2 * Math.PI * R;
  const segs = entries.map(([k, v], i) => {
    const frac = Number(v) / total, off = acc; acc += frac;
    return '<circle cx="70" cy="70" r="' + R + '" fill="none" stroke="' + PALETTE[i % PALETTE.length] + '" stroke-width="17" stroke-dasharray="' + (frac * C).toFixed(1) + " " + C.toFixed(1) + '" stroke-dashoffset="' + (-off * C).toFixed(1) + '" transform="rotate(-90 70 70)"><title>' + esc(k) + ": " + v + "</title></circle>";
  }).join("");
  const legend = entries.map(([k, v], i) => '<div class="li"><span class="sw" style="background:' + PALETTE[i % PALETTE.length] + '"></span>' + esc(k) + "<b>" + v + "</b></div>").join("");
  return '<div style="display:flex;align-items:center"><svg width="140" height="140" viewBox="0 0 140 140">' + segs +
    '<text x="70" y="67" text-anchor="middle" fill="#e8eaf0" font-size="21" font-weight="700">' + total + '</text>' +
    '<text x="70" y="84" text-anchor="middle" fill="#9aa1b1" font-size="10.5">total</text></svg>' +
    '<div class="chart-legend">' + legend + "</div></div>";
}
function barsSVG(dist) {
  const entries = Object.entries(dist).filter(([, v]) => Number(v) > 0).sort((a, b) => Number(b[1]) - Number(a[1]));
  if (!entries.length) return '<p class="muted">No data yet.</p>';
  const max = Math.max.apply(null, entries.map(([, v]) => Number(v)));
  const rows = entries.slice(0, 8).map(([k, v], i) =>
    '<div style="display:flex;align-items:center;gap:9px;width:100%;margin:3px 0"><span style="width:118px;color:var(--muted);font-size:12.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="' + esc(k) + '">' + esc(k) +
    '</span><div style="flex:1;background:var(--bg2);border-radius:5px;height:15px"><div style="width:' + Math.max(3, (Number(v) / max) * 100) + "%;background:" + PALETTE[i % PALETTE.length] + ';height:15px;border-radius:5px"></div></div><b style="font-size:12.5px">' + v + "</b></div>").join("");
  return '<div style="width:100%">' + rows + "</div>";
}
async function loadDashboard() {
  let d = {};
  try { d = (await api("/analytics/overview")) || {}; }
  catch (e) { $("#kpiGrid").innerHTML = '<div class="card"><p class="muted">Could not load analytics: ' + esc(e.message) + "</p></div>"; return; }
  const flat = Object.assign({}, d, d.totals || {}, d.kpis || {}, d.summary || {});
  const shown = KPI_DEFS.filter(([k]) => flat[k] !== undefined && flat[k] !== null);
  const picks = (shown.length ? shown : KPI_DEFS.slice(0, 4)).slice(0, 8);
  $("#kpiGrid").innerHTML = picks.map(([k, label]) => {
    let v = flat[k]; if (v === undefined || v === null) v = 0;
    if (k === "conversion_rate" && Number(v) <= 1 && Number(v) > 0) v = (Number(v) * 100).toFixed(1) + "%";
    return '<div class="kpi"><div class="kpi-label">' + label + '</div><div class="kpi-value">' + esc(v) + "</div></div>";
  }).join("");
  const status = findDist(d, ["leads_by_status", "lead_statuses", "status_distribution", "by_status"]);
  const source = findDist(d, ["leads_by_source", "lead_sources", "source_distribution", "by_source"]);
  const outcome = findDist(d, ["calls_by_outcome", "call_outcomes", "outcome_distribution", "by_outcome"]);
  const language = findDist(d, ["leads_by_language", "languages", "language_distribution", "by_language", "calls_by_language"]);
  $("#chartStatus").innerHTML = status ? donutSVG(status) : '<p class="muted">No data yet.</p>';
  $("#chartSource").innerHTML = source ? barsSVG(source) : '<p class="muted">No data yet.</p>';
  $("#chartOutcome").innerHTML = outcome ? barsSVG(outcome) : '<p class="muted">No calls yet.</p>';
  $("#chartLanguage").innerHTML = language ? donutSVG(language) : '<p class="muted">No data yet.</p>';
  const totalLeads = Number(flat.total_leads || 0), totalCalls = Number(flat.total_calls || 0);
  $("#dashEmpty").classList.toggle("hidden", !(totalLeads === 0 && totalCalls === 0));
  try {
    const full = objOf(await api("/analytics/full?range_days=0"));
    const L = objOf(full.leads), C = objOf(full.calls), Tk = objOf(full.tasks), I = objOf(full.insights);
    const tiles = [];
    if (L.conversion_rate !== undefined) tiles.push(["Conversion rate", pct(L.conversion_rate) + (L.converted != null ? " (" + L.converted + "/" + (L.total || 0) + ")" : "")]);
    if (C.analyzed_rate !== undefined) tiles.push(["Calls analyzed", pct(C.analyzed_rate) + (C.analyzed != null ? " (" + C.analyzed + "/" + (C.total || 0) + ")" : "")]);
    if (Tk.open !== undefined) tiles.push(["Open tasks", Tk.open]);
    if (Tk.overdue !== undefined) tiles.push(["Overdue tasks", Tk.overdue]);
    $("#dashFullTiles").innerHTML = tiles.map(([l, v]) => '<div class="kpi"><div class="kpi-label">' + l + '</div><div class="kpi-value" style="font-size:22px">' + esc(v) + "</div></div>").join("");
    $("#chartQual").innerHTML = L.by_category && Object.keys(objOf(L.by_category)).length ? donutSVG(objOf(L.by_category)) : '<p class="muted">No qualification data yet.</p>';
    $("#chartSentiment").innerHTML = I.sentiment_distribution && Object.keys(objOf(I.sentiment_distribution)).length ? barsSVG(objOf(I.sentiment_distribution)) : '<p class="muted">No sentiment data yet — analyze a call first.</p>';
  } catch (e) { const q = $("#chartQual"); if (q) q.innerHTML = '<p class="muted">Analytics unavailable: ' + esc(e.message) + "</p>"; }
}

/* ---------- leads ---------- */
const LEAD_STATUSES = ["New", "Pending", "Scheduled", "Calling", "Contacted", "Qualified", "Hot", "Warm", "Cold", "Appointment Booked", "Follow-up Required", "Converted", "Not Interested", "Do Not Contact"];
let leadsCache = [], editingLeadId = null;
function statusBadge(s) {
  const cls = s === "Hot" ? "hot" : s === "Warm" ? "warm" : s === "Cold" ? "cold" : (s === "Qualified" || s === "Converted") ? "ok" : "";
  return '<span class="badge ' + cls + '">' + esc(s || "New") + "</span>";
}
function scoreClass(v) { v = Number(v); return v >= 80 ? "hot" : v >= 50 ? "warm" : "cold"; }

async function loadLeads() {
  const q = new URLSearchParams();
  const search = $("#leadSearch").value.trim(), st = $("#leadFilterStatus").value, src = $("#leadFilterSource").value, lang = $("#leadFilterLanguage").value;
  if (search) q.set("q", search);
  if (st) q.set("status", st);
  if (src) q.set("source", src);
  if (lang) q.set("language", lang);
  const fs = $("#leadFilterStatus");
  if (fs.options.length <= 1) LEAD_STATUSES.forEach((s) => { const o = document.createElement("option"); o.textContent = s; fs.appendChild(o); });
  try { leadsCache = listOf(await api("/leads" + (q.toString() ? "?" + q : ""))); }
  catch (e) { toast(e.message); leadsCache = []; }
  const srcSel = $("#leadFilterSource"), cur = srcSel.value;
  const sources = Array.from(new Set(leadsCache.map((l) => l.lead_source).filter(Boolean)));
  srcSel.innerHTML = '<option value="">All sources</option>' + sources.map((s) => '<option' + (s === cur ? " selected" : "") + ">" + esc(s) + "</option>").join("");
  renderLeads();
}
function renderLeads() {
  const tb = $("#leadsTbody");
  $("#leadsEmpty").classList.toggle("hidden", leadsCache.length > 0);
  tb.innerHTML = leadsCache.map((l) => "<tr>" +
    "<td><b>" + esc(l.full_name || "—") + "</b>" + (l.do_not_contact ? ' <span class="dnc">DNC</span>' : "") + "</td>" +
    "<td>" + esc(l.company || "—") + "</td><td>" + esc(l.phone || "—") + "</td>" +
    "<td>" + statusBadge(l.lead_status) + "</td>" +
    '<td>' + (l.lead_score === null || l.lead_score === undefined || l.lead_score === "" ? "—" : '<span class="score-pill badge ' + scoreClass(l.lead_score) + '">' + esc(l.lead_score) + "</span>") + "</td>" +
    "<td>" + esc(l.preferred_language || "—") + "</td><td>" + esc(l.lead_source || "—") + "</td>" +
    '<td><div class="row-actions">' +
    '<button class="icon-btn" title="View" data-lead-view="' + l.id + '">' + icon("eye") + "</button>" +
    '<button class="icon-btn" title="Edit" data-lead-edit="' + l.id + '">' + icon("edit") + "</button>" +
    '<button class="icon-btn" title="Delete" data-lead-del="' + l.id + '">' + icon("trash") + "</button>" +
    "</div></td></tr>").join("");
  $$("[data-lead-view]", tb).forEach((b) => b.addEventListener("click", () => openLeadDetail(b.getAttribute("data-lead-view"))));
  $$("[data-lead-edit]", tb).forEach((b) => b.addEventListener("click", () => openLeadForm(b.getAttribute("data-lead-edit"))));
  $$("[data-lead-del]", tb).forEach((b) => b.addEventListener("click", () => deleteLead(b.getAttribute("data-lead-del"))));
}
["leadSearch", "leadFilterStatus", "leadFilterSource", "leadFilterLanguage"].forEach((id) => {
  $("#" + id).addEventListener("input", () => { clearTimeout(window._lq); window._lq = setTimeout(loadLeads, 250); });
  $("#" + id).addEventListener("change", loadLeads);
});
async function deleteLead(id) {
  const l = leadsCache.find((x) => String(x.id) === String(id));
  if (!confirm("Delete lead " + (l ? l.full_name : id) + "? This cannot be undone.")) return;
  try { await api("/leads/" + id, { method: "DELETE" }); toast("Lead deleted."); loadLeads(); }
  catch (e) { toast(e.message); }
}
function fillLeadForm(l) {
  ["full_name", "company", "phone", "email", "location", "industry", "lead_source", "budget", "decision_authority", "purchase_timeline", "requirements", "pain_points"].forEach((f) => { $("#lf_" + f).value = l ? (l[f] || "") : ""; });
  $("#lf_preferred_language").value = (l && l.preferred_language) || "English";
  $("#lf_lead_score").value = l && l.lead_score !== null && l.lead_score !== undefined ? l.lead_score : "";
  $("#lf_lead_status").value = (l && l.lead_status) || "New";
  $("#lf_next_followup").value = l && l.next_followup ? String(l.next_followup).slice(0, 10) : "";
  $("#lf_consent").checked = !!(l && l.consent);
  $("#lf_do_not_contact").checked = !!(l && l.do_not_contact);
}
function openLeadForm(id) {
  editingLeadId = id || null;
  const st = $("#lf_lead_status");
  if (!st.options.length) LEAD_STATUSES.forEach((s) => { const o = document.createElement("option"); o.textContent = s; st.appendChild(o); });
  fillLeadForm(id ? leadsCache.find((x) => String(x.id) === String(id)) : null);
  $("#leadModalTitle").textContent = id ? "Edit lead" : "Add lead";
  $("#leadError").textContent = "";
  openModal("leadModal");
}
$("#addLeadBtn").addEventListener("click", () => openLeadForm(null));
$("#leadForm").addEventListener("submit", async (e) => {
  e.preventDefault(); $("#leadError").textContent = "";
  const body = {};
  ["full_name", "company", "phone", "email", "location", "preferred_language", "industry", "lead_source", "budget", "requirements", "decision_authority", "purchase_timeline", "pain_points", "lead_status"].forEach((f) => { body[f] = $("#lf_" + f).value.trim(); });
  const sc = $("#lf_lead_score").value; body.lead_score = sc === "" ? null : Number(sc);
  body.next_followup = $("#lf_next_followup").value || null;
  body.consent = $("#lf_consent").checked; body.do_not_contact = $("#lf_do_not_contact").checked;
  try {
    if (editingLeadId) await api("/leads/" + editingLeadId, { method: "PATCH", body });
    else await api("/leads", { method: "POST", body });
    closeModal("leadModal"); toast("Lead saved."); loadLeads();
  } catch (err) { $("#leadError").textContent = err.message; }
});
async function openLeadDetail(id) {
  let l = leadsCache.find((x) => String(x.id) === String(id));
  try { l = (await api("/leads/" + id)) || l; } catch (e) { /* fall back to cached row */ }
  if (!l) return;
  $("#leadDetailTitle").textContent = l.full_name || "Lead";
  const fields = [["Company", l.company], ["Phone", l.phone], ["Email", l.email], ["Location", l.location], ["Language", l.preferred_language], ["Industry", l.industry], ["Source", l.lead_source], ["Status", l.lead_status], ["Score", l.lead_score], ["Budget", l.budget], ["Decision authority", l.decision_authority], ["Timeline", l.purchase_timeline], ["Requirements", l.requirements], ["Pain points", l.pain_points], ["Last interaction", fmtDT(l.last_interaction)], ["Next follow-up", l.next_followup], ["Consent", l.consent ? "Yes" : "No"], ["Do not contact", l.do_not_contact ? "Yes" : "No"]];
  let html = '<div class="kv-grid">' + fields.map(([k, v]) => '<div class="kv"><b>' + k + "</b><span>" + esc(v === null || v === undefined || v === "" ? "—" : v) + "</span></div>").join("") + "</div>";
  try {
    const calls = listOf(await api("/calls")).filter((c) => String(c.lead_id) === String(id));
    html += "<h3 style='margin:18px 0 8px'>Calls with this lead</h3>" + (calls.length
      ? calls.map((c) => '<div class="member-row"><span>' + esc(fmtDT(c.started_at || c.created_at)) + '</span><span class="badge">' + esc(c.outcome || c.status || "—") + "</span></div>").join("")
      : '<p class="muted">No calls recorded for this lead yet.</p>');
  } catch (e) { /* calls list unavailable */ }
  if (l.hubspot_id) html += '<p style="margin-top:10px"><b>HubSpot ID:</b> ' + esc(l.hubspot_id) + "</p>";
  html += '<div id="leadIntel"><p class="muted">Loading qualification &amp; memory…</p></div>';
  html += '<div style="display:flex;gap:9px;margin-top:12px;flex-wrap:wrap"><button class="btn btn-primary btn-sm" id="syncHubspotBtn" type="button">Sync to HubSpot</button><span id="syncHubspotResult" class="muted"></span></div>';
  html += '<h3 style="margin:18px 0 8px">Appointments for this lead</h3><div id="leadAppts"><p class="muted">Loading…</p></div>';
  $("#leadDetailBody").innerHTML = html;
  openModal("leadDetailModal");
  const sb = $("#syncHubspotBtn"); if (sb) sb.addEventListener("click", async () => { const rEl = $("#syncHubspotResult"); rEl.textContent = "Syncing…"; try { const r = objOf(await api("/leads/" + id + "/sync-hubspot", { method: "POST" })); rEl.textContent = r.ok ? ("Synced" + (r.hubspot_id ? " — HubSpot ID " + r.hubspot_id : "")) : ("Failed: " + (r.error || "unknown error")); if (r.ok) toast("HubSpot sync complete."); } catch (e) { rEl.textContent = e.message; } });
  try {
    const intel = objOf(await api("/leads/" + id + "/intelligence"));
    const scores = arrOf(intel.scores), mem = arrOf(intel.memory), sent = arrOf(intel.sentiment_history);
    const latest = scores.length ? scores[scores.length - 1] : (scores[0] || null);
    let ih = '<h3 style="margin:18px 0 8px">Qualification</h3>';
    if (latest) { ih += '<p><b>Latest score:</b> ' + esc(latest.score != null ? latest.score : (latest.total != null ? latest.total : "—")) + " " + categoryBadge(latest.category) + "</p>" + bantTable(latest.bant || latest); }
    else ih += '<p class="muted">No qualification scores yet — analyze a call with this lead.</p>';
    if (scores.length) ih += "<h4>Score history</h4>" + scores.map((s) => '<div class="member-row"><span>' + esc(fmtDT(s.created_at)) + '</span><span style="margin-left:auto"><b>' + esc(s.score != null ? s.score : (s.total != null ? s.total : "—")) + "</b> " + categoryBadge(s.category) + "</span></div>").join("");
    ih += '<h3 style="margin:18px 0 8px">Memory timeline</h3>' + (mem.length ? mem.map((m) => '<div class="member-row"><span><span class="badge">' + esc(m.category || "note") + "</span> " + esc(m.content || m.text || "") + '</span><span class="muted">' + esc(fmtDT(m.created_at)) + "</span></div>").join("") : '<p class="muted">No memory entries yet.</p>');
    ih += '<h3 style="margin:18px 0 8px">Sentiment history</h3>' + (sent.length ? sent.map((s) => '<div class="member-row"><span>' + esc(fmtDT(s.created_at)) + '</span><span style="margin-left:auto">' + esc(typeof s === "object" ? (s.sentiment || s.value || JSON.stringify(s)) : s) + "</span></div>").join("") : '<p class="muted">No sentiment history yet.</p>');
    const intelEl = $("#leadIntel"); if (intelEl) intelEl.innerHTML = ih;
  } catch (e) { const el = $("#leadIntel"); if (el) el.innerHTML = '<p class="muted">Intelligence unavailable: ' + esc(e.message) + "</p>"; }
  try {
    const appts = listOf(await api("/appointments")).filter((a) => String(a.lead_id) === String(id));
    const el = $("#leadAppts"); if (el) el.innerHTML = appts.length ? appts.map((a) => '<div class="member-row"><span>' + esc(a.title || "Appointment") + '</span><span class="badge">' + esc(a.status || "scheduled") + '</span><span class="muted">' + esc(fmtDT(a.starts_at)) + "</span></div>").join("") : '<p class="muted">No appointments for this lead.</p>';
  } catch (e) { const el = $("#leadAppts"); if (el) el.innerHTML = '<p class="muted">Appointments unavailable.</p>'; }
  openModal("leadDetailModal");
}
function fmtDT(v) {
  if (!v) return "—";
  const d = new Date(v); return isNaN(d) ? String(v) : d.toLocaleString();
}

/* ---------- CSV import ---------- */
function parseCSV(text) {
  const rows = []; let row = [], field = "", inQ = false;
  text = String(text).replace(/^\uFEFF/, "");
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQ) {
      if (c === '"') { if (text[i + 1] === '"') { field += '"'; i++; } else inQ = false; }
      else field += c;
    } else if (c === '"') inQ = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field); field = "";
      if (row.some((x) => String(x).trim() !== "")) rows.push(row);
      row = [];
    } else field += c;
  }
  row.push(field);
  if (row.some((x) => String(x).trim() !== "")) rows.push(row);
  if (!rows.length) return [];
  const headers = rows[0].map((h) => String(h).trim().toLowerCase().replace(/[\s\-]+/g, "_"));
  const ALIAS = { name: "full_name", full_name: "full_name", company_name: "company", language: "preferred_language", preferred_language: "preferred_language", source: "lead_source", lead_source: "lead_source", status: "lead_status", lead_status: "lead_status", score: "lead_score", lead_score: "lead_score", decision_making_authority: "decision_authority", decision_authority: "decision_authority", timeline: "purchase_timeline", purchase_timeline: "purchase_timeline", pain_points: "pain_points", requirements: "requirements", budget: "budget", industry: "industry", location: "location", phone: "phone", mobile: "phone", email: "email", company: "company" };
  return rows.slice(1).map((r) => {
    const o = {};
    headers.forEach((h, i) => { const k = ALIAS[h]; if (k) o[k] = (r[i] || "").trim(); });
    return o;
  }).filter((o) => Object.values(o).some((v) => v));
}
$("#csvFile").addEventListener("change", async (e) => {
  const file = e.target.files[0]; e.target.value = "";
  if (!file) return;
  const bar = $("#importBar"); bar.classList.remove("hidden", "err");
  let rows;
  try { rows = parseCSV(await file.text()); }
  catch (err) { bar.classList.add("err"); bar.textContent = "Could not read that file: " + err.message; return; }
  if (!rows.length) { bar.classList.add("err"); bar.textContent = "No data rows found in " + file.name + ". The first row must be headers (name, phone, email…)."; return; }
  bar.textContent = "Parsed " + rows.length + " row(s) from " + file.name + " — importing…";
  try {
    const r = await api("/leads/import", { method: "POST", body: { rows } });
    bar.innerHTML = "<b>Import finished:</b> " + (r.imported || 0) + " imported · " + (r.skippedDuplicates ?? r.skipped_duplicates ?? 0) + " duplicates skipped · " + (r.invalidRows ?? r.invalid_rows ?? 0) + " invalid row(s).";
    loadLeads();
  } catch (err) { bar.classList.add("err"); bar.textContent = "Import failed: " + err.message; }
});

/* ---------- agents ---------- */
let agentsCache = [], editingAgentId = null;
async function loadAgents() {
  try { agentsCache = listOf(await api("/agents")); } catch (e) { toast(e.message); agentsCache = []; }
  const g = $("#agentsGrid");
  $("#agentsEmpty").classList.toggle("hidden", agentsCache.length > 0);
  g.innerHTML = agentsCache.map((a) => {
    const langs = Array.isArray(a.languages) ? a.languages : (a.languages ? String(a.languages).split(",") : []);
    return '<div class="card entity-card"><div class="ec-head">' +
      '<div class="avatar-dot">' + esc((a.name || "A").slice(0, 1).toUpperCase()) + "</div>" +
      '<div style="flex:1;min-width:0"><div class="ec-title">' + esc(a.name || "Unnamed agent") + "</div>" +
      '<div class="ec-sub">' + esc(a.company_name || "") + "</div></div>" +
      '<span class="badge ' + (a.is_active ? "ok" : "off") + '">' + (a.is_active ? "Active" : "Inactive") + "</span></div>" +
      (a.description ? '<div class="ec-sub">' + esc(a.description) + "</div>" : "") +
      '<div class="ec-meta">' +
      (a.personality ? '<span class="badge">' + esc(a.personality) + "</span>" : "") +
      langs.map((l) => '<span class="badge">' + esc(String(l).trim()) + "</span>").join("") +
      (a.voice_name ? '<span class="badge">' + esc(a.voice_name) + "</span>" : "") +
      "</div>" +
      '<div class="ec-actions"><button class="btn btn-ghost btn-sm" data-agent-edit="' + a.id + '">Edit</button>' +
      '<button class="btn btn-ghost btn-sm" data-agent-del="' + a.id + '">Delete</button>' +
      '<button class="btn btn-primary btn-sm" data-agent-test="' + a.id + '">Test voice</button></div></div>';
  }).join("");
  $$("[data-agent-edit]", g).forEach((b) => b.addEventListener("click", () => openAgentForm(b.getAttribute("data-agent-edit"))));
  $$("[data-agent-del]", g).forEach((b) => b.addEventListener("click", () => deleteAgent(b.getAttribute("data-agent-del"))));
  $$("[data-agent-test]", g).forEach((b) => b.addEventListener("click", () => { navigate("voice"); setTimeout(() => { $("#voiceAgent").value = b.getAttribute("data-agent-test"); }, 60); }));
}
async function deleteAgent(id) {
  const a = agentsCache.find((x) => String(x.id) === String(id));
  if (!confirm("Delete agent " + (a ? a.name : id) + "?")) return;
  try { await api("/agents/" + id, { method: "DELETE" }); toast("Agent deleted."); loadAgents(); }
  catch (e) { toast(e.message); }
}
const AGENT_FIELDS = ["name", "description", "company_name", "personality", "voice_provider", "voice_name", "calling_hours", "sales_objectives", "target_audience", "qualification_questions", "escalation_conditions", "followup_behaviour"];
function openAgentForm(id) {
  editingAgentId = id || null;
  const a = id ? agentsCache.find((x) => String(x.id) === String(id)) : null;
  AGENT_FIELDS.forEach((f) => { $("#af_" + f).value = a ? (a[f] || "") : ""; });
  $("#af_speaking_speed").value = a && a.speaking_speed != null ? a.speaking_speed : "";
  $("#af_max_call_duration").value = a && a.max_call_duration != null ? a.max_call_duration : "";
  $("#af_is_active").checked = a ? !!a.is_active : true;
  const langs = a ? (Array.isArray(a.languages) ? a.languages : String(a.languages || "").split(",")) : ["English"];
  $$(".af_lang").forEach((c) => { c.checked = langs.map((x) => String(x).trim()).includes(c.value); });
  $("#agentModalTitle").textContent = id ? "Edit agent" : "New agent";
  $("#agentError").textContent = "";
  openModal("agentModal");
}
$("#addAgentBtn").addEventListener("click", () => openAgentForm(null));
$("#agentForm").addEventListener("submit", async (e) => {
  e.preventDefault(); $("#agentError").textContent = "";
  const body = {};
  AGENT_FIELDS.forEach((f) => { body[f] = $("#af_" + f).value.trim(); });
  body.languages = $$(".af_lang").filter((c) => c.checked).map((c) => c.value);
  const sp = $("#af_speaking_speed").value; body.speaking_speed = sp === "" ? null : Number(sp);
  const md = $("#af_max_call_duration").value; body.max_call_duration = md === "" ? null : Number(md);
  body.is_active = $("#af_is_active").checked;
  try {
    if (editingAgentId) await api("/agents/" + editingAgentId, { method: "PATCH", body });
    else await api("/agents", { method: "POST", body });
    closeModal("agentModal"); toast("Agent saved."); loadAgents();
  } catch (err) { $("#agentError").textContent = err.message; }
});

/* ---------- voice testing ---------- */
let voiceMode = "turn";           // "turn" | "livekit"
let session = null;               // {callId, mode}
let mediaRecorder = null, mediaStream = null, audioChunks = [];
let lkRoom = null;

async function loadVoiceSetup() {
  try {
    const agents = listOf(await api("/agents"));
    const sel = $("#voiceAgent"), cur = sel.value;
    sel.innerHTML = agents.length ? agents.map((a) => '<option value="' + a.id + '">' + esc(a.name || "Agent") + "</option>").join("") : '<option value="">No agents — create one first</option>';
    if (cur) sel.value = cur;
    const leads = listOf(await api("/leads"));
    const lsel = $("#voiceLead"), lcur = lsel.value;
    lsel.innerHTML = '<option value="">— No lead —</option>' + leads.map((l) => '<option value="' + l.id + '">' + esc(l.full_name || "Lead") + (l.company ? " · " + esc(l.company) : "") + "</option>").join("");
    if (lcur) lsel.value = lcur;
  } catch (e) { /* selects stay as-is; start will surface the error */ }
}
function setMode(m) {
  voiceMode = m;
  $("#modeTurnBtn").classList.toggle("active", m === "turn");
  $("#modeLivekitBtn").classList.toggle("active", m === "livekit");
  $("#modeHint").textContent = m === "turn"
    ? "Turn-based: hold the mic button, speak, release — the agent transcribes, thinks and speaks back. Works anywhere this page can reach the API."
    : "LiveKit live: your browser joins a LiveKit room directly and publishes your mic in real time. Needs this page to reach LiveKit (HTTPS/WSS) — errors are shown exactly as they happen.";
  syncVoiceZones();
}
$("#modeTurnBtn").addEventListener("click", () => setMode("turn"));
$("#modeLivekitBtn").addEventListener("click", () => setMode("livekit"));
function syncVoiceZones() {
  const active = !!session;
  $("#micZone").classList.toggle("hidden", !(active && session.mode === "turn"));
  $("#livekitZone").classList.toggle("hidden", !(active && session.mode === "livekit"));
  $("#startSessionBtn").classList.toggle("hidden", active);
  $("#endSessionBtn").classList.toggle("hidden", !active);
}
function addMsg(who, text) {
  const box = $("#transcriptBox");
  const empty = $(".empty", box); if (empty) empty.remove();
  const div = document.createElement("div");
  div.className = "msg " + (who === "You" ? "user" : who === "Agent" ? "agent" : "system");
  div.innerHTML = (who === "system" ? "" : '<div class="msg-who">' + esc(who) + "</div>") + esc(text);
  box.appendChild(div); box.scrollTop = box.scrollHeight;
}
function setVoiceError(msg) { $("#voiceError").textContent = msg || ""; }

$("#startSessionBtn").addEventListener("click", async () => {
  setVoiceError("");
  const agentId = $("#voiceAgent").value;
  if (!agentId) { setVoiceError("Create an AI agent first (AI Agents page), then start a session."); return; }
  const body = { agent_id: isNaN(Number(agentId)) ? agentId : Number(agentId), language: $("#voiceLang").value, mode: voiceMode };
  const leadId = $("#voiceLead").value;
  if (leadId) body.lead_id = isNaN(Number(leadId)) ? leadId : Number(leadId);
  let d;
  try { d = await api("/calls/start", { method: "POST", body }); }
  catch (e) { setVoiceError(e.message); return; }
  const call = d.call || d;
  session = { callId: call.id, mode: voiceMode };
  const vctx = d.context_snapshot || call.context_snapshot || null;
  const vcEl = $("#voiceContext");
  if (vctx) { vcEl.innerHTML = contextHTML(vctx, "Context loaded"); vcEl.classList.remove("hidden"); } else { vcEl.innerHTML = ""; vcEl.classList.add("hidden"); }
  $("#transcriptBox").innerHTML = "";
  $("#sessionMeta").innerHTML = "Session live · Call <b>#" + esc(call.id) + "</b> · " + esc(body.language) + " · " + (voiceMode === "turn" ? "Turn-based" : "LiveKit");
  $("#transcriptBadge").textContent = "Live"; $("#transcriptBadge").className = "badge ok";
  addMsg("system", "Session started. " + (voiceMode === "turn" ? "Hold the mic button and speak." : "Connecting to the LiveKit room…"));
  syncVoiceZones();
  if (voiceMode === "livekit") await connectLiveKit(d);
});
$("#endSessionBtn").addEventListener("click", async () => {
  if (!session) return;
  if (lkRoom) { try { await lkRoom.disconnect(); } catch (e) { /* already gone */ } lkRoom = null; }
  stopMicTracks();
  try { await api("/calls/" + session.callId + "/end", { method: "POST", body: { outcome: "Completed" } }); } catch (e) { setVoiceError(e.message); }
  addMsg("system", "Session ended and saved to Call History.");
  $("#transcriptBadge").textContent = "Ended"; $("#transcriptBadge").className = "badge";
  $("#sessionMeta").textContent = "No active session.";
  session = null; syncVoiceZones();
});

/* --- turn-based recording --- */
function stopMicTracks() { if (mediaStream) { mediaStream.getTracks().forEach((t) => t.stop()); mediaStream = null; } }
async function startRecording() {
  if (!session || session.mode !== "turn") return;
  setVoiceError("");
  if (!window.isSecureContext || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    setVoiceError("Microphone capture is unavailable in this browser context — getUserMedia needs a secure context. Open this page over HTTPS (your deployed URL) or at http://localhost, then try again.");
    return;
  }
  try { mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
  catch (e) { setVoiceError("The microphone could not be opened: " + (e.message || e.name) + ". Check the browser's microphone permission for this page, then try again."); return; }
  audioChunks = [];
  try { mediaRecorder = new MediaRecorder(mediaStream); }
  catch (e) { stopMicTracks(); setVoiceError("MediaRecorder is not supported in this browser."); return; }
  mediaRecorder.ondataavailable = (ev) => { if (ev.data && ev.data.size) audioChunks.push(ev.data); };
  mediaRecorder.onstop = sendTurn;
  mediaRecorder.start();
  $("#micBtn").classList.add("recording");
  $("#micLabel").textContent = "Recording… release to send";
  $("#micState").textContent = "Listening — speak now.";
}
function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === "recording") mediaRecorder.stop();
  stopMicTracks();
  $("#micBtn").classList.remove("recording");
  $("#micLabel").textContent = "Hold to talk";
}
async function sendTurn() {
  if (!session) return;
  const blob = new Blob(audioChunks, { type: (mediaRecorder && mediaRecorder.mimeType) || "audio/webm" });
  if (!blob.size) { $("#micState").textContent = "Nothing was recorded — hold the button while speaking."; return; }
  $("#micState").textContent = "Transcribing and thinking…";
  $("#micBtn").disabled = true;
  const fd = new FormData();
  fd.append("audio", blob, "turn.webm");
  let d;
  try { d = await api("/calls/" + session.callId + "/turn", { method: "POST", body: fd }); }
  catch (e) { setVoiceError(e.message); $("#micState").textContent = ""; $("#micBtn").disabled = false; return; }
  if (d.user_text) addMsg("You", d.user_text);
  else addMsg("system", "(No speech was detected in that recording — try again, a little closer to the mic.)");
  if (d.reply_text) addMsg("Agent", d.reply_text);
  if (d.audio_base64) {
    const audio = $("#replyAudio");
    audio.src = "data:" + (d.audio_content_type || "audio/mpeg") + ";base64," + d.audio_base64;
    audio.classList.remove("hidden");
    audio.play().catch(() => { /* user can press play on the visible controls */ });
  } else if (d.audio_error) {
    addMsg("system", "Reply audio unavailable: " + d.audio_error);
  }
  $("#micState").textContent = "";
  $("#micBtn").disabled = false;
}
const micBtn = $("#micBtn");
micBtn.addEventListener("mousedown", startRecording);
micBtn.addEventListener("mouseup", stopRecording);
micBtn.addEventListener("mouseleave", () => { if (mediaRecorder && mediaRecorder.state === "recording") stopRecording(); });
micBtn.addEventListener("touchstart", (e) => { e.preventDefault(); startRecording(); }, { passive: false });
micBtn.addEventListener("touchend", (e) => { e.preventDefault(); stopRecording(); }, { passive: false });

/* --- LiveKit direct mode --- */
async function connectLiveKit(d) {
  const LK = window.LivekitClient;
  if (!LK) { setVoiceError("The LiveKit SDK could not be loaded from its CDN — check your connection and reload. No connection was faked."); $("#lkState").textContent = "SDK unavailable."; return; }
  if (!d.livekit_url || !d.token) { setVoiceError("The server did not return a LiveKit URL/token for this session (is LiveKit configured on the host?)."); $("#lkState").textContent = "No LiveKit credentials for this session."; return; }
  try {
    lkRoom = new LK.Room({ adaptiveStream: true, dynacast: true });
    lkRoom.on(LK.RoomEvent.Connected, () => { $("#lkState").textContent = "Connected to room " + (d.room || "") + " — you are live."; addMsg("system", "LiveKit connected."); });
    lkRoom.on(LK.RoomEvent.Disconnected, () => { $("#lkState").textContent = "Disconnected."; });
    lkRoom.on(LK.RoomEvent.TranscriptionReceived, (segments, participant) => {
      (segments || []).forEach((s) => { if (s.final && s.text) addMsg(participant && participant.isLocal ? "You" : "Agent", s.text); });
    });
    await lkRoom.connect(d.livekit_url, d.token);
    await lkRoom.localParticipant.setMicrophoneEnabled(true);
    $("#lkState").textContent = "Connected to room " + (d.room || "") + " — microphone live.";
  } catch (e) {
    $("#lkState").textContent = "Connection failed.";
    setVoiceError("LiveKit connection failed: " + (e.message || e) + " — the AI agent worker must also be running (voice-agent/agent.py) for the agent to speak in the room.");
  }
}

/* ---------- call history ---------- */
async function loadCalls() {
  let calls = [];
  try { calls = listOf(await api("/calls")); } catch (e) { toast(e.message); }
  let agents = [], leads = [];
  try { agents = listOf(await api("/agents")); leads = listOf(await api("/leads")); } catch (e) { /* names are a nicety */ }
  const aName = (id) => { const a = agents.find((x) => String(x.id) === String(id)); return a ? a.name : (id ? "#" + id : "—"); };
  const lName = (id) => { const l = leads.find((x) => String(x.id) === String(id)); return l ? l.full_name : (id ? "#" + id : "—"); };
  $("#callsEmpty").classList.toggle("hidden", calls.length > 0);
  $("#callsTbody").innerHTML = calls.map((c) => {
    let dur = "—";
    if (c.duration_seconds != null) dur = Math.floor(c.duration_seconds / 60) + "m " + Math.round(c.duration_seconds % 60) + "s";
    else if (c.started_at && c.ended_at) dur = Math.max(0, Math.round((new Date(c.ended_at) - new Date(c.started_at)) / 1000)) + "s";
    else if (c.duration != null) dur = esc(c.duration);
    return "<tr><td>" + esc(fmtDT(c.started_at || c.created_at)) + "</td><td>" + esc(aName(c.agent_id)) + "</td><td>" + esc(lName(c.lead_id)) + "</td><td>" +
      esc(c.language || "—") + "</td><td>" + esc(c.mode || "—") + "</td><td>" + statusBadge(c.outcome || c.status || "—") + (c.has_insight ? ' <span class="badge ok">Analyzed</span>' : "") + "</td><td>" + dur + "</td>" +
      '<td><div class="row-actions"><button class="icon-btn" title="View transcript" data-call-view="' + c.id + '">' + icon("eye") + "</button></div></td></tr>";
  }).join("");
  $$("[data-call-view]").forEach((b) => b.addEventListener("click", () => openCallDetail(b.getAttribute("data-call-view"), aName, lName)));
}
let currentCall = null, currentInsight = null;
function renderInsightPanel() {
  const panel = $("#callAnalysisPanel"); if (!panel || !currentCall) return;
  const c = currentCall; const ins = currentInsight;
  const hasTranscript = arrOf(c._msgs).length > 0 || !!(c.transcript_text || c.has_transcript);
  let html = '<div class="card" style="background:var(--surface2)"><div class="card-head"><h3>Call analysis</h3>';
  if (ins) html += '<button class="btn btn-ghost btn-sm" id="analyzeBtn" type="button">Re-analyze</button>';
  else if (hasTranscript) html += '<button class="btn btn-primary btn-sm" id="analyzeBtn" type="button">Analyze call</button>';
  else html += '<span class="muted small">No transcript — analysis is unavailable for this call.</span>';
  html += '</div><div class="auth-error" id="analyzeError"></div>';
  if (!ins) html += hasTranscript ? '<p class="muted">Not analyzed yet. Run analysis to extract BANT, sentiment and next actions from the transcript.</p>' : '<p class="muted">Analyze is disabled because no transcript was captured for this call.</p>';
  else {
    html += (ins.score != null ? '<p><b>Score:</b> ' + esc(ins.score) + " " + categoryBadge(ins.category) + "</p>" : "");
    if (ins.summary) html += "<p><b>Summary:</b> " + esc(ins.summary) + "</p>";
    if (ins.requirements) html += "<p><b>Requirements:</b> " + esc(ins.requirements) + "</p>";
    html += "<h4>BANT</h4>" + bantTable(ins.bant);
    if (arrOf(ins.pain_points).length) html += "<h4>Pain points</h4>" + countedList(ins.pain_points);
    if (arrOf(ins.product_interests).length) html += "<h4>Product interests</h4>" + countedList(ins.product_interests);
    if (arrOf(ins.objections).length) html += "<h4>Objections</h4>" + countedList(ins.objections);
    html += '<div class="kv-grid">' +
      "<div class='kv'><b>Sentiment</b><span>" + esc(ins.sentiment_overall || "—") + "</span></div>" +
      "<div class='kv'><b>Purchase intent</b><span>" + esc(ins.purchase_intent != null ? ins.purchase_intent : "—") + "</span></div>" +
      "<div class='kv'><b>Engagement</b><span>" + esc(ins.engagement != null ? ins.engagement : "—") + "</span></div>" +
      "<div class='kv'><b>Appointment status</b><span>" + esc(ins.appointment_status || "—") + "</span></div>" +
      "<div class='kv'><b>Next action</b><span>" + esc(ins.next_action || "—") + "</span></div></div>";
    if (arrOf(ins.sentiment_progression).length) html += "<h4>Sentiment progression</h4><p class='muted'>" + arrOf(ins.sentiment_progression).map((s) => esc(typeof s === "object" ? JSON.stringify(s) : s)).join(" → ") + "</p>";
    if (c.lead_id) html += '<button class="btn btn-primary btn-sm" id="bookFromCallBtn" type="button">Book appointment from this call</button>';
  }
  html += "</div>";
  panel.innerHTML = html;
  const ab = $("#analyzeBtn"); if (ab) ab.addEventListener("click", analyzeCurrentCall);
  const bb = $("#bookFromCallBtn"); if (bb) bb.addEventListener("click", () => { navigate("appointments"); setTimeout(() => { if (c.lead_id) $("#apptLead").value = c.lead_id; $("#apptTitle").value = (ins && ins.next_action) || "Follow-up appointment"; const nx = $("#apptNotes"); if (nx && ins) nx.value = ins.summary || ""; }, 80); });
}
async function analyzeCurrentCall() {
  const errEl = $("#analyzeError"); if (errEl) errEl.textContent = "";
  try { currentInsight = objOf(await api("/calls/" + currentCall.id + "/analyze", { method: "POST" })); if (currentInsight.insight) currentInsight = currentInsight.insight; renderInsightPanel(); toast("Analysis complete."); }
  catch (e) { if (errEl) errEl.textContent = e.message; else toast(e.message); }
}
async function openCallDetail(id, aName, lName) {
  let d;
  try { d = await api("/calls/" + id); } catch (e) { toast(e.message); return; }
  const c = d.call || d;
  const msgs = d.transcript || d.messages || d.transcript_messages || c.transcript || c.messages || [];
  c._msgs = arrOf(msgs);
  currentCall = c; currentInsight = null;
  $("#callDetailMeta").innerHTML =
    '<span class="badge">Call #' + esc(c.id) + "</span>" +
    '<span class="badge">' + esc(fmtDT(c.started_at || c.created_at)) + "</span>" +
    '<span class="badge">' + esc(c.language || "—") + "</span>" +
    '<span class="badge">' + esc(c.mode || "—") + "</span>" +
    statusBadge(c.outcome || c.status || "—") +
    (c.agent_id ? '<span class="badge">Agent: ' + esc(aName ? aName(c.agent_id) : c.agent_id) + "</span>" : "") +
    (c.lead_id ? '<span class="badge">Lead: ' + esc(lName ? lName(c.lead_id) : c.lead_id) + "</span>" : "");
  const ctx = d.context_snapshot || c.context_snapshot || null;
  $("#callContextBlock").innerHTML = ctx ? contextHTML(ctx, "Context loaded for this session") : "";
  const box = $("#callTranscript");
  box.innerHTML = msgs.length ? "" : '<div class="empty small-empty"><p>No transcript was captured for this call.</p></div>';
  arrOf(msgs).forEach((m) => {
    const who = /user|lead|customer|you/i.test(m.role || m.speaker || "") ? "You" : /agent|assistant|ai/i.test(m.role || m.speaker || "") ? "Agent" : "system";
    const div = document.createElement("div");
    div.className = "msg " + (who === "You" ? "user" : who === "Agent" ? "agent" : "system");
    div.innerHTML = (who === "system" ? "" : '<div class="msg-who">' + who + "</div>") + esc(m.text || m.content || "");
    box.appendChild(div);
  });
  try { const ins = await api("/calls/" + id + "/insight"); currentInsight = ins && (ins.insight || ins); if (currentInsight && !Object.keys(objOf(currentInsight)).length) currentInsight = null; } catch (e) { currentInsight = null; }
  renderInsightPanel();
  openModal("callModal");
}

/* ---------- integrations ---------- */
const INTEGRATION_META = {
  livekit: ["LiveKit", "Real-time voice rooms (WebRTC)"],
  llm: ["Groq LLM", "Conversation, analysis and knowledge answers"],
  deepgram: ["Deepgram", "Speech-to-text (Nova)"],
  deepgram_tts: ["Deepgram Aura", "Text-to-speech voices"],
  tts: ["Deepgram Aura", "Text-to-speech voices"],
  google_calendar: ["Google Calendar", "Appointment booking — Phase 5"],
  hubspot: ["HubSpot", "CRM synchronization — Phase 5"],
  telephony: ["SIP Telephony", "Real phone calls — Phase 5"],
  sip: ["SIP Telephony", "Real phone calls — Phase 5"],
};
async function loadIntegrations() {
  let d = {};
  try { d = (await api("/integrations/status")) || {}; } catch (e) { toast(e.message); }
  const entries = [];
  const walk = (obj, prefix) => {
    Object.entries(obj || {}).forEach(([k, v]) => {
      if (v && typeof v === "object" && ("connected" in v || "configured" in v || "status" in v)) entries.push([prefix ? prefix + "_" + k : k, v]);
      else if (v && typeof v === "object" && !Array.isArray(v)) walk(v, prefix ? prefix + "_" + k : k);
    });
  };
  walk(d, "");
  const seen = new Set();
  $("#integrationsGrid").innerHTML = entries.map(([key, v]) => {
    const meta = INTEGRATION_META[key.toLowerCase()] || INTEGRATION_META[key.toLowerCase().replace(/.*_/, "")] || [key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()), ""];
    if (seen.has(meta[0])) return ""; seen.add(meta[0]);
    const on = v.connected === true || v.configured === true || v.status === "connected";
    const detail = v.detail || v.message || v.url || v.provider || (on ? "Connected" : "Not connected — credentials required");
    const err = v.lastError || v.last_error || "";
    return '<div class="card entity-card"><div class="ec-head"><span class="status-dot ' + (on ? "on" : "off") + '"></span>' +
      '<div style="flex:1"><div class="ec-title">' + esc(meta[0]) + '</div><div class="ec-sub">' + esc(meta[1]) + "</div></div>" +
      '<span class="badge ' + (on ? "ok" : "off") + '">' + (on ? "Connected" : "Not connected") + "</span></div>" +
      '<div class="ec-sub">' + esc(detail) + "</div>" +
      (err ? '<div class="voice-error">Last attempt: ' + esc(err) + "</div>" : "") + "</div>";
  }).join("") || '<div class="card"><p class="muted">No integration status returned by the server.</p></div>';
  // Extended cards: HubSpot auto-sync + sync logs, Google Calendar .ics note
  try {
    const extra = $("#integrationsExtra"); if (!extra) return;
    const hs = objOf(d.hubspot || d.HubSpot || {});
    const gc = objOf(d.googleCalendar || d.google_calendar || {});
    const hsOn = hs.connected === true;
    let org = myOrg; try { org = await api("/organizations/current"); myOrg = org; } catch (e) {}
    let logs = []; try { logs = listOf(await api("/sync-logs")); } catch (e) {}
    extra.innerHTML =
      '<div class="grid-2">' +
      '<div class="card"><div class="card-head"><h3>HubSpot</h3><span class="badge ' + (hsOn ? "ok" : "off") + '">' + (hsOn ? "Connected" : "Not connected — credentials required") + '</span></div>' +
      '<label class="check"><input type="checkbox" id="hubspotAutoSync" ' + (org && org.hubspot_auto_sync ? "checked" : "") + '> Auto-sync leads to HubSpot</label>' +
      '<p class="muted small">Toggle is saved to your organization settings.</p><div class="auth-error" id="hsToggleError"></div></div>' +
      '<div class="card"><div class="card-head"><h3>Google Calendar</h3><span class="badge">' + esc(gc.mode || "ics") + '</span></div>' +
      '<p class="muted">' + esc(gc.note || "Appointments are managed in SalesPilot and exported as .ics files") + '</p><p class="muted small">Connected: ' + (gc.connected ? "Yes" : "No") + ' — use the .ics download on each appointment to add it to Google Calendar.</p></div></div>' +
      '<div class="card" style="margin-top:16px"><div class="card-head"><h3>HubSpot sync log</h3></div>' +
      (logs.length ? '<table class="table"><thead><tr><th>When</th><th>Lead</th><th>Direction</th><th>Result</th><th>HubSpot ID</th><th>Error</th></tr></thead><tbody>' + logs.slice(0, 50).map((l) => "<tr><td>" + esc(fmtDT(l.created_at)) + "</td><td>" + esc(l.lead_id || "—") + "</td><td>" + esc(l.direction || "—") + "</td><td>" + esc(l.result || "—") + "</td><td>" + esc(l.hubspot_id || "—") + "</td><td>" + esc(l.error || "—") + "</td></tr>").join("") + "</tbody></table>" : '<p class="muted">No sync attempts recorded yet.</p>') + "</div>";
    const tog = $("#hubspotAutoSync"); if (tog) tog.addEventListener("change", async () => { try { await api("/organizations/current", { method: "PATCH", body: { hubspot_auto_sync: tog.checked } }); toast("HubSpot auto-sync " + (tog.checked ? "enabled." : "disabled.")); } catch (e) { $("#hsToggleError").textContent = e.message; tog.checked = !tog.checked; } });
  } catch (e) { /* base grid already rendered */ }
}

/* ---------- organization ---------- */
async function loadOrganization() {
  try { myOrg = await api("/organizations/current"); } catch (e) { myOrg = null; }
  if (myOrg) {
    $("#orgName").value = myOrg.name || "";
    $("#orgIndustry").value = myOrg.industry || "";
    $("#orgWebsite").value = myOrg.website || "";
    $("#orgTimezone").value = myOrg.timezone || "";
    $("#orgCallingHours").value = myOrg.calling_hours || "";
    $("#orgChip").textContent = myOrg.name || "Organization";
  }
  renderMembers();
}
async function renderMembers() {
  let members = [];
  try { members = listOf(await api("/organizations/members")); } catch (e) { toast(e.message); }
  $("#membersList").innerHTML = members.length ? members.map((m) =>
    '<div class="member-row"><span data-icon="user" class="icon-btn" style="pointer-events:none">' + icon("user") + '</span>' +
    '<span class="mr-email">' + esc(m.email || m.name || ("User #" + m.user_id)) + "</span>" +
    '<select data-member-role="' + m.id + '">' +
    ["Owner", "Administrator", "Sales Manager", "Sales Representative"].map((r) => "<option" + (r === (m.role || "") ? " selected" : "") + ">" + r + "</option>").join("") +
    '</select><button class="icon-btn" title="Remove" data-member-del="' + m.id + '">' + icon("trash") + "</button></div>").join("")
    : '<p class="muted">No members listed yet.</p>';
  $$("[data-member-role]").forEach((s) => s.addEventListener("change", async () => {
    try { await api("/organizations/members/" + s.getAttribute("data-member-role"), { method: "PATCH", body: { role: s.value } }); toast("Role updated."); }
    catch (e) { toast(e.message); renderMembers(); }
  }));
  $$("[data-member-del]").forEach((b) => b.addEventListener("click", async () => {
    if (!confirm("Remove this member from the organization?")) return;
    try { await api("/organizations/members/" + b.getAttribute("data-member-del"), { method: "DELETE" }); renderMembers(); }
    catch (e) { toast(e.message); }
  }));
}
$("#orgForm").addEventListener("submit", async (e) => {
  e.preventDefault(); $("#orgError").textContent = ""; $("#orgSaved").textContent = "";
  const body = { name: $("#orgName").value.trim(), industry: $("#orgIndustry").value.trim(), website: $("#orgWebsite").value.trim(), timezone: $("#orgTimezone").value.trim(), calling_hours: $("#orgCallingHours").value.trim() };
  try { myOrg = await api("/organizations/current", { method: "PATCH", body }); $("#orgSaved").textContent = "Saved."; $("#orgChip").textContent = body.name; }
  catch (err) { $("#orgError").textContent = err.message; }
});
$("#memberForm").addEventListener("submit", async (e) => {
  e.preventDefault(); $("#memberError").textContent = "";
  try {
    await api("/organizations/members", { method: "POST", body: { email: $("#memberEmail").value.trim(), role: $("#memberRole").value } });
    $("#memberEmail").value = ""; toast("Member added."); renderMembers();
  } catch (err) { $("#memberError").textContent = err.message; }
});


/* ---------- knowledge base ---------- */
async function loadKB() {
  let docs = [];
  try { docs = listOf(await api("/kb/documents")); } catch (e) { toast(e.message); }
  $("#kbEmpty").classList.toggle("hidden", docs.length > 0);
  $("#kbTbody").innerHTML = docs.map((d) => "<tr><td><b>" + esc(d.name || "—") + "</b></td><td>" + esc(d.type || d.file_type || d.content_type || "—") + "</td><td>" + esc(d.status || "—") + "</td><td>" + esc(d.chunk_count != null ? d.chunk_count : (d.chunks != null ? (Array.isArray(d.chunks) ? d.chunks.length : d.chunks) : "—")) + "</td><td>" + esc(d.embedding_model || "—") + '</td><td><div class="row-actions"><button class="btn btn-ghost btn-sm" data-kb-view="' + d.id + '">View chunks</button><button class="btn btn-ghost btn-sm" data-kb-reindex="' + d.id + '">Re-index</button><button class="btn btn-ghost btn-sm" data-kb-del="' + d.id + '">Delete</button></div></td></tr>').join("");
  $$("[data-kb-view]").forEach((b) => b.addEventListener("click", async () => { try { const d = objOf(await api("/kb/documents/" + b.getAttribute("data-kb-view"))); const chunks = arrOf(d.chunks); $("#kbChunksCard").classList.remove("hidden"); $("#kbChunksTitle").textContent = "Chunks — " + (d.name || ""); $("#kbChunks").innerHTML = chunks.length ? chunks.map((c, i) => '<div class="member-row"><span class="badge">#' + esc(c.chunk_index != null ? c.chunk_index : i) + "</span><span>" + esc(typeof c === "string" ? c : (c.text || "")) + "</span></div>").join("") : '<p class="muted">No chunks stored for this document.</p>'; } catch (e) { toast(e.message); } }));
  $$("[data-kb-reindex]").forEach((b) => b.addEventListener("click", async () => { try { await api("/kb/documents/" + b.getAttribute("data-kb-reindex") + "/reindex", { method: "POST" }); toast("Re-index requested."); loadKB(); } catch (e) { toast(e.message); } }));
  $$("[data-kb-del]").forEach((b) => b.addEventListener("click", async () => { if (!confirm("Delete this document and its chunks?")) return; try { await api("/kb/documents/" + b.getAttribute("data-kb-del"), { method: "DELETE" }); toast("Document deleted."); loadKB(); } catch (e) { toast(e.message); } }));
}
$("#kbUploadBtn").addEventListener("click", async () => { const f = $("#kbFile").files[0]; $("#kbUploadError").textContent = ""; if (!f) { $("#kbUploadError").textContent = "Choose a file first."; return; } const fd = new FormData(); fd.append("file", f); try { await api("/kb/documents", { method: "POST", body: fd }); toast("Document uploaded."); loadKB(); } catch (e) { $("#kbUploadError").textContent = e.message; } });
$("#kbTextForm").addEventListener("submit", async (e) => { e.preventDefault(); try { await api("/kb/documents", { method: "POST", body: { name: $("#kbTextName").value.trim(), text: $("#kbTextBody").value } }); $("#kbTextName").value = ""; $("#kbTextBody").value = ""; toast("Document added."); loadKB(); } catch (err) { toast(err.message); } });
$("#kbRetrieveBtn").addEventListener("click", async () => { const q = $("#kbRetrieveQ").value.trim(); const el = $("#kbRetrieveResults"); el.innerHTML = '<p class="muted">Searching…</p>'; try { const r = objOf(await api("/kb/retrieve", { method: "POST", body: { question: q } })); const res = arrOf(r.results); if (!r.found || !res.length) { el.innerHTML = '<p class="muted">No relevant content found.</p>'; return; } el.innerHTML = res.map((x) => '<div class="member-row"><span><b>' + esc(x.document_name || "Document") + "</b> · chunk " + esc(x.chunk_index) + ' · score ' + esc(x.score) + "<br>" + esc(x.text || "") + "</span></div>").join(""); } catch (e) { el.innerHTML = '<p class="voice-error">' + esc(e.message) + "</p>"; } });
$("#kbAskBtn").addEventListener("click", async () => { const q = $("#kbAskQ").value.trim(); const el = $("#kbAskResults"); el.innerHTML = '<p class="muted">Asking…</p>'; try { const r = objOf(await api("/kb/ask", { method: "POST", body: { question: q } })); const used = arrOf(r.chunks_used); el.innerHTML = "<p>" + esc(r.answer || "") + "</p>" + (used.length ? "<h4>Citations</h4>" + used.map((c) => '<div class="member-row"><span>' + esc(typeof c === "string" ? c : ((c.document_name || "Document") + " · chunk " + (c.chunk_index != null ? c.chunk_index : "") + " — " + (c.text || ""))) + "</span></div>").join("") : '<p class="muted">No chunks used.</p>'); } catch (e) { el.innerHTML = '<p class="voice-error">' + esc(e.message) + "</p>"; } });

/* ---------- appointments ---------- */
let apptsCache = [];
async function fillLeadSelects() { try { const leads = listOf(await api("/leads")); const opts = leads.map((l) => '<option value="' + l.id + '">' + esc(l.full_name || "Lead") + "</option>").join(""); const a = $("#apptLead"); if (a) { const cur = a.value; a.innerHTML = opts || '<option value="">No leads</option>'; if (cur) a.value = cur; } const tk = $("#taskLead"); if (tk) { const cur2 = tk.value; tk.innerHTML = opts || '<option value="">No leads</option>'; if (cur2) tk.value = cur2; } return leads; } catch (e) { return []; } }
async function loadAppointments() {
  await fillLeadSelects();
  try { apptsCache = listOf(await api("/appointments")); } catch (e) { toast(e.message); apptsCache = []; }
  apptsCache.sort((a, b) => new Date(a.starts_at || 0) - new Date(b.starts_at || 0));
  $("#appointmentsEmpty").classList.toggle("hidden", apptsCache.length > 0);
  $("#appointmentsList").innerHTML = apptsCache.map((a) => '<div class="member-row" style="flex-wrap:wrap"><span><b>' + esc(a.title || "Appointment") + "</b><br><span class='muted'>" + esc(fmtDT(a.starts_at)) + " · " + esc(a.duration_minutes || "—") + " min · Lead " + esc(a.lead_id || "—") + "</span></span>" +
    '<select data-appt-status="' + a.id + '">' + ["scheduled", "confirmed", "completed", "cancelled", "no_show"].map((s) => "<option" + (s === (a.status || "scheduled") ? " selected" : "") + ">" + s + "</option>").join("") + "</select>" +
    '<button class="btn btn-ghost btn-sm" data-appt-ics="' + a.id + '">.ics</button><button class="btn btn-ghost btn-sm" data-appt-del="' + a.id + '">Delete</button></div>').join("");
  $$("[data-appt-status]").forEach((s) => s.addEventListener("change", async () => { try { await api("/appointments/" + s.getAttribute("data-appt-status"), { method: "PATCH", body: { status: s.value } }); toast("Appointment updated."); } catch (e) { toast(e.message); loadAppointments(); } }));
  $$("[data-appt-ics]").forEach((b) => b.addEventListener("click", async () => { try { await downloadAuthed("/appointments/" + b.getAttribute("data-appt-ics") + "/ics", "appointment-" + b.getAttribute("data-appt-ics") + ".ics"); } catch (e) { toast(e.message); } }));
  $$("[data-appt-del]").forEach((b) => b.addEventListener("click", async () => { if (!confirm("Delete this appointment?")) return; try { await api("/appointments/" + b.getAttribute("data-appt-del"), { method: "DELETE" }); loadAppointments(); } catch (e) { toast(e.message); } }));
}
$("#apptForm").addEventListener("submit", async (e) => { e.preventDefault(); $("#apptError").textContent = ""; $("#apptConflict").classList.add("hidden"); const starts = $("#apptStarts").value; const body = { lead_id: isNaN(Number($("#apptLead").value)) ? $("#apptLead").value : Number($("#apptLead").value), title: $("#apptTitle").value.trim(), starts_at: starts ? new Date(starts).toISOString() : null, duration_minutes: Number($("#apptDuration").value || 30), timezone: $("#apptTimezone").value.trim() || "Asia/Kolkata", notes: $("#apptNotes").value.trim() }; try { const r = objOf(await api("/appointments", { method: "POST", body })); if (r.conflict) { const el = $("#apptConflict"); el.classList.remove("hidden"); el.innerHTML = '<div class="import-bar err"><b>Conflict warning:</b> this overlaps ' + arrOf(r.conflicts).length + " existing appointment(s)." + arrOf(r.conflicts).map((c) => "<br>" + esc(c.title || "Appointment") + " — " + esc(fmtDT(c.starts_at))).join("") + "</div>"; } toast("Appointment created."); loadAppointments(); } catch (err) { $("#apptError").textContent = err.message; } });

/* ---------- tasks ---------- */
async function loadTasks() {
  await fillLeadSelects();
  let tasks = []; try { tasks = listOf(await api("/tasks")); } catch (e) { toast(e.message); }
  tasks.sort((a, b) => new Date(a.due_at || a.created_at || 0) - new Date(b.due_at || b.created_at || 0));
  $("#tasksEmpty").classList.toggle("hidden", tasks.length > 0);
  const now = Date.now();
  $("#tasksList").innerHTML = tasks.map((tk) => { const overdue = tk.due_at && new Date(tk.due_at).getTime() < now && tk.status !== "done" && !tk.completed_at; const kind = tk.kind || tk.type || (tk.is_escalation ? "escalation" : "followup"); return '<div class="member-row" style="flex-wrap:wrap;' + (overdue ? "background:rgba(224,92,92,.10);border-radius:8px;padding:9px" : "") + '"><span><span class="badge ' + (kind === "escalation" ? "hot" : "warm") + '">' + esc(kind) + "</span> <b>" + esc(tk.reason || tk.title || "Task") + '</b><br><span class="muted">Lead ' + esc(tk.lead_id || "—") + " · Due " + esc(fmtDT(tk.due_at)) + (overdue ? " · OVERDUE" : "") + " · " + esc(tk.status || (tk.completed_at ? "done" : "open")) + "</span></span>" + ((tk.status !== "done" && !tk.completed_at) ? '<button class="btn btn-primary btn-sm" data-task-done="' + tk.id + '" style="margin-left:auto">Complete</button>' : "") + "</div>"; }).join("");
  $$("[data-task-done]").forEach((b) => b.addEventListener("click", async () => { try { await api("/tasks/" + b.getAttribute("data-task-done") + "/complete", { method: "POST" }); toast("Task completed."); loadTasks(); } catch (e) { toast(e.message); } }));
}
$("#taskForm").addEventListener("submit", async (e) => { e.preventDefault(); $("#taskError").textContent = ""; const due = $("#taskDue").value; try { await api("/tasks", { method: "POST", body: { lead_id: isNaN(Number($("#taskLead").value)) ? $("#taskLead").value : Number($("#taskLead").value), reason: $("#taskReason").value.trim(), due_at: due ? new Date(due).toISOString() : null } }); toast("Follow-up created."); loadTasks(); } catch (err) { $("#taskError").textContent = err.message; } });

/* ---------- analytics ---------- */
async function loadAnalytics() {
  const range = $("#analyticsRange").value;
  const el = $("#analyticsBody"); el.innerHTML = '<p class="muted">Loading…</p>';
  let f; try { f = objOf(await api("/analytics/full?range_days=" + encodeURIComponent(range))); } catch (e) { el.innerHTML = '<p class="voice-error">' + esc(e.message) + "</p>"; return; }
  const L = objOf(f.leads), C = objOf(f.calls), I = objOf(f.insights), A = objOf(f.appointments), Tk = objOf(f.tasks), KB = objOf(f.kb), agents = arrOf(f.agents);
  const sec = (title, inner) => '<div class="card" style="margin-bottom:16px"><div class="card-head"><h3>' + title + "</h3></div>" + inner + "</div>";
  const kv = (pairs) => '<div class="kv-grid">' + pairs.map(([k, v]) => '<div class="kv"><b>' + k + "</b><span>" + esc(v == null || v === "" ? "—" : v) + "</span></div>").join("") + "</div>";
  let html = "";
  html += sec("Leads", kv([["Total", L.total], ["Converted", L.converted], ["Conversion rate", pct(L.conversion_rate)], ["Average score", L.avg_score]]) + "<h4>By status</h4>" + distList(L.by_status) + "<h4>By source</h4>" + distList(L.by_source) + "<h4>By language</h4>" + distList(L.by_language) + "<h4>By category</h4>" + distList(L.by_category));
  html += sec("Calls", kv([["Total", C.total], ["Total duration (s)", C.total_duration], ["Avg duration (s)", C.avg_duration], ["With transcripts", C.with_transcripts], ["Analyzed", C.analyzed], ["Analyzed rate", pct(C.analyzed_rate)], ["Avg qualification score", C.avg_qualification_score]]) + "<h4>By outcome</h4>" + distList(C.by_outcome) + "<h4>By language</h4>" + distList(C.by_language) + "<h4>By agent</h4>" + distList(C.by_agent));
  const trend = arrOf(I.weekly_trend); const trendDist = {}; trend.forEach((w, i) => { trendDist[w.week || w.label || ("Week " + (i + 1))] = w.count != null ? w.count : (w.calls != null ? w.calls : (w.value != null ? w.value : 0)); });
  html += sec("Insights", "<h4>Sentiment distribution</h4>" + (Object.keys(objOf(I.sentiment_distribution)).length ? barsSVG(objOf(I.sentiment_distribution)) : '<p class="muted">No sentiment data yet.</p>') + "<h4>Weekly trend</h4>" + (trend.length ? barsSVG(trendDist) : '<p class="muted">No weekly trend yet.</p>') + "<h4>Intent distribution</h4>" + distList(I.intent_distribution) + "<h4>Top objections</h4>" + countedList(I.top_objections) + "<h4>Top pain points</h4>" + countedList(I.top_pain_points) + "<h4>Top interests</h4>" + countedList(I.top_interests) + "<h4>BANT completeness (avg)</h4>" + (typeof I.bant_completeness_avg === "object" ? distList(I.bant_completeness_avg) : kv([["Average", I.bant_completeness_avg]])));
  html += sec("Appointments", distList(A.by_status) + kv([["Completion rate", pct(A.completion_rate)]]));
  html += sec("Tasks", kv([["Open", Tk.open], ["Done", Tk.done], ["Overdue", Tk.overdue], ["Escalations", Tk.escalations], ["Follow-ups", Tk.followups]]));
  html += sec("Knowledge base", kv([["Documents", KB.documents], ["Ready", KB.ready], ["Chunks", KB.chunks], ["Queries", KB.queries], ["Hits", KB.hits], ["Hit rate", pct(KB.hit_rate)]]));
  html += sec("Agent performance", agents.length ? '<table class="table"><thead><tr><th>Agent</th><th>Calls</th><th>Analyzed</th><th>Avg score</th><th>Hot leads</th><th>Appointments</th></tr></thead><tbody>' + agents.map((a) => "<tr><td>" + esc(a.name || ("#" + a.agent_id)) + "</td><td>" + esc(a.calls || 0) + "</td><td>" + esc(a.analyzed || 0) + "</td><td>" + esc(a.avg_score != null ? a.avg_score : "—") + "</td><td>" + esc(a.hot_leads || 0) + "</td><td>" + esc(a.appointments_booked || 0) + "</td></tr>").join("") + "</tbody></table>" : '<p class="muted">No agent activity yet.</p>');
  el.innerHTML = html || '<p class="muted">No analytics data yet.</p>';
}
$("#analyticsRange").addEventListener("change", loadAnalytics);
$("#exportLeadsCsvBtn").addEventListener("click", async () => { try { await downloadAuthed("/analytics/leads.csv", "leads.csv"); } catch (e) { toast(e.message); } });
$("#exportSummaryCsvBtn").addEventListener("click", async () => { try { await downloadAuthed("/analytics/summary.csv", "summary.csv"); } catch (e) { toast(e.message); } });

/* ---------- compliance ---------- */
async function loadCompliance() {
  let status = {}, full = null;
  try { status = objOf(await api("/integrations/status")); } catch (e) {}
  try { full = objOf(await api("/analytics/full?range_days=0")); } catch (e) {}
  const hs = objOf(status.hubspot || {}); const oa = objOf(status.llm || {});
  const item = (ok, label, note) => '<div class="member-row"><span class="badge ' + (ok ? "ok" : "off") + '">' + (ok ? "✓ Done" : "○ Not yet") + "</span><span><b>" + esc(label) + "</b>" + (note ? '<br><span class="muted">' + esc(note) + "</span>" : "") + "</span></div>";
  $("#launchChecklist").innerHTML = "<h4>Launch checklist</h4>" +
    item(hs.connected === true, "HubSpot connected", hs.connected ? "" : "Not connected — credentials required") +
    item(!!(oa.connected || oa.configured), "LLM provider configured", (oa.connected || oa.configured) ? ((oa.provider || "Groq") + " \u00b7 " + (oa.model || "")) : "Add a GROQ_API_KEY (free tier available) — the LLM powers voice replies, call analysis and knowledge answers.") +
    item(false, "Deployed at a public URL", "Manual check — confirm your production deployment URL is live and HTTPS.") +
    item(!!(full && objOf(full.calls).total > 0), "At least one real call recorded", full ? ("Calls: " + (objOf(full.calls).total || 0)) : "Analytics unavailable") +
    item(true, "Do Not Contact enforcement enabled", "Server blocks DNC leads from call start (403 shown verbatim)") +
    item(false, "TRAI / DLT registration complete", "Manual — complete registration with your operator/provider") +
    item(false, "Consent & disclosure script reviewed", "Manual — review AI/recording disclosure with legal advisor");
}

/* ---------- org data controls ---------- */
$("#exportOrgBtn").addEventListener("click", async () => { const el = $("#dataControlsResult"); try { await downloadAuthed("/organizations/current/export", "workspace-export.json"); el.textContent = "Export downloaded."; } catch (e) { el.textContent = e.message; } });
$("#wipeBtn").addEventListener("click", () => $("#wipeZone").classList.remove("hidden"));
$("#wipeCancelBtn").addEventListener("click", () => { $("#wipeZone").classList.add("hidden"); $("#wipeConfirm").value = ""; });
$("#wipeConfirmBtn").addEventListener("click", async () => { const el = $("#dataControlsResult"); if ($("#wipeConfirm").value !== "DELETE") { el.textContent = "Type DELETE exactly to confirm."; return; } try { const r = objOf(await api("/organizations/current/wipe", { method: "POST", body: { confirm_text: "DELETE" } })); el.textContent = "Wipe complete. Deleted counts: " + JSON.stringify(r.counts || r.deleted || r, null, 2); $("#wipeZone").classList.add("hidden"); $("#wipeConfirm").value = ""; } catch (e) { el.textContent = e.message; } });


/* ---------- init ---------- */
boot();
