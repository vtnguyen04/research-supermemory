// Main State Container & Accessible Multi-Mode Studio Controller
(function () {
  const { hydrateIcons, esc, tr, getLang, setLang, applyStaticLang } = window.SuperMemoryIcons;
  const { ForceGraphCanvas } = window.SuperMemoryGraph;
  const { InspectorController } = window.SuperMemoryInspector;
  const { MergeStudioController } = window.SuperMemoryMergeStudio;
  const { ModalController } = window.SuperMemoryModals;
  const Views = window.SuperMemoryViews;

  let state = { nodes: [], edges: [], gates: [], experiments: [], events: [], meta: {}, analytics: {}, cognitive_tiers: {}, workspaces: [] };
  let currentScope = "local", activeTier = "ALL", activeType = "ALL", toastTimer = null;
  let graphView = null, inspector = null, mergeStudio = null, modals = null;

  function toast(msg, isError = false) {
    const el = document.getElementById("toast-region");
    el.textContent = msg; el.className = `toast-region${isError ? " toast-error" : ""}`;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.add("hidden"), 3400);
  }

  async function postJson(route, payload = {}) {
    const res = await fetch(route, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scope: currentScope, ...payload }) });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  async function mutateAndRefresh(route, payload, msg) {
    try { await postJson(route, payload); toast(msg); await loadGraph(); }
    catch (err) { toast(err.message, true); }
  }

  function buildViewHandlers() {
    return {
      onInspect: (nid) => { graphView.selectedId = nid; inspector.inspect(nid); },
      onToggleGate: (gid, enabled) => mutateAndRefresh("/api/gates", { action: "toggle", gate_id: gid, enabled }, tr(`Updated ${gid}`, `Đã cập nhật ${gid}`)),
      onDeleteGate: (gid) => mutateAndRefresh("/api/gates", { action: "delete", gate_id: gid }, tr(`Deleted ${gid}`, `Đã xóa ${gid}`)),
      onOpenLesson: () => modals.openAddLesson(),
      onOpenExp: () => modals.openAddExperiment(),
      onOpenProposal: () => modals.openAddProposal(),
      onOpenIdea: () => modals.openAddIdea(),
      onAdvanceProposal: (pid, next) => mutateAndRefresh("/api/proposals", { action: "advance", proposal_id: pid, new_stage: next }, tr(`Moved ${pid} to ${next}`, `Đã chuyển ${pid} sang ${next}`)),
      onAuditProposal: (pid) => mutateAndRefresh("/api/proposals", { action: "audit", proposal_id: pid, verdict: "APPROVE" }, tr(`Approved Audit for ${pid}`, `Đã phê duyệt Audit cho ${pid}`)),
    };
  }

  function rerenderAll() {
    renderWorkspaceSwitcher(); renderCommandAndTelemetry(); renderGraphToolbar();
    graphView._applyLayout(false); mergeStudio.render();
    const h = buildViewHandlers();
    Views.renderConstitution(state, h); Views.renderExperiments(state, h);
    Views.renderLifecycle(state, h); Views.renderEvents(state, h);
  }

  async function loadGraph() {
    const errStrip = document.getElementById("error-banner");
    errStrip.classList.add("hidden");
    try {
      const res = await fetch(`/api/graph?scope=${encodeURIComponent(currentScope)}`);
      if (!res.ok) throw new Error(tr(`Failed to load graph (HTTP ${res.status})`, `Không thể tải dữ liệu đồ thị (HTTP ${res.status})`));
      state = await res.json();
      graphView.setData(state.nodes, state.edges);
      rerenderAll();
      const qs = new URLSearchParams(window.location.search);
      const qMode = qs.get("mode");
      if (qMode && ["FORCE", "RADIAL", "LANES"].includes(qMode.toUpperCase())) setGraphMode(qMode.toUpperCase());
      const qInspect = qs.get("inspect");
      if (qInspect && !inspector.currentNodeId) { graphView.selectedId = qInspect; inspector.inspect(qInspect); }
    } catch (err) {
      errStrip.classList.remove("hidden");
      errStrip.innerHTML = `<span>${tr("Server connection error:", "Lỗi kết nối máy chủ:")} ${esc(err.message)}</span>
        <button type="button" id="btn-retry-load" class="btn btn-secondary btn-sm">${tr("Retry", "Thử lại")}</button>`;
      document.getElementById("btn-retry-load").addEventListener("click", loadGraph);
    }
  }

  function renderWorkspaceSwitcher() {
    const sel = document.getElementById("workspace-switcher");
    sel.innerHTML = "";
    let matched = false;
    (state.workspaces || []).forEach((w) => {
      const opt = document.createElement("option");
      opt.value = w.id === "global" ? "global" : w.path;
      opt.textContent = w.id === "global" ? tr("Global: All Workspaces", "Global: Tất cả dự án") : `Local: ${w.name}`;
      if ((currentScope === "global" && w.id === "global") || w.path === state.workspace_path) { opt.selected = true; matched = true; }
      sel.appendChild(opt);
    });
    if (!matched) {
      const opt = document.createElement("option");
      opt.value = "local"; opt.textContent = `Local: ${state.project}`; opt.selected = true; sel.prepend(opt);
    }
  }

  function renderCommandAndTelemetry() {
    document.getElementById("scope-indicator").textContent = state.is_global ? "GLOBAL" : "LOCAL";
    document.getElementById("project-title").textContent = state.project || "SuperMemory";
    document.getElementById("active-goal-line").textContent = (state.meta || {}).active_goal || "4-Tier Cognitive Graph & Constitutional Harness";
    const tiers = state.cognitive_tiers || {}, byTier = tiers.counts_by_tier || {}, activeTok = tiers.active_prompt_tokens || 0;
    document.getElementById("kpi-tokens").textContent = `${activeTok} / 850 tok`;
    document.getElementById("token-meter-bar").setAttribute("aria-valuenow", String(activeTok));
    document.getElementById("token-meter-fill").style.width = `${Math.min(100, Math.round((activeTok / 850) * 100))}%`;
    document.getElementById("kpi-compression").textContent = `${tiers.context_compression_pct || 0}%`;
    document.getElementById("kpi-blocks").textContent = (state.analytics || {}).total_blocked_regressions || 0;
    document.getElementById("nav-count-nodes").textContent = (state.nodes || []).length;
    document.getElementById("nav-count-episodic").textContent = byTier.EPISODIC || 0;
    document.getElementById("nav-count-gates").textContent = (state.gates || []).length;
    document.getElementById("nav-count-exps").textContent = (state.experiments || []).length;
    document.getElementById("nav-count-props").textContent = (state.nodes || []).filter((n) => n.node_type === "PROPOSAL").length;
  }

  function renderGraphToolbar() {
    const tc = ((state.cognitive_tiers || {}).counts_by_tier) || {}, total = (state.nodes || []).length;
    const segs = [["ALL", `${tr("All", "Tất cả")} (${total})`], ["PROCEDURAL", `L1 (${tc.PROCEDURAL || 0})`], ["SEMANTIC", `L2 (${tc.SEMANTIC || 0})`], ["EPISODIC", `L3 (${tc.EPISODIC || 0})`]];
    const tray = document.getElementById("tier-filters");
    tray.innerHTML = segs.map(([k, lbl]) => `<button type="button" class="seg-btn" aria-pressed="${activeTier === k}" data-tier="${k}">${esc(lbl)}</button>`).join("");
    tray.querySelectorAll("[data-tier]").forEach((btn) => btn.addEventListener("click", () => {
      activeTier = btn.getAttribute("data-tier"); renderGraphToolbar(); graphView.setFilter(activeTier, activeType);
    }));
    const sel = document.getElementById("type-filter-select"), nc = (state.analytics || {}).nodes_by_type || {}, keys = Object.keys(nc).sort();
    if (activeType !== "ALL" && !nc[activeType]) activeType = "ALL";
    sel.innerHTML = `<option value="ALL">${tr("All Types", "Tất cả loại")} (${total})</option>` + keys.map((k) => `<option value="${esc(k)}" ${activeType === k ? "selected" : ""}>${esc(k)} (${nc[k]})</option>`).join("");
  }

  function setGraphMode(mode) {
    document.querySelectorAll("[data-gmode]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.gmode === mode)));
    graphView.setMode(mode);
  }

  function bindTabsAndShortcuts() {
    const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
    const activateTab = (tab, moveFocus = false) => {
      tabs.forEach((t) => {
        const sel = t === tab;
        t.classList.toggle("active", sel); t.setAttribute("aria-selected", String(sel)); t.setAttribute("tabindex", sel ? "0" : "-1");
        const p = document.getElementById(t.dataset.tab); p.classList.toggle("active", sel); p.hidden = !sel;
      });
      if (tab.dataset.tab === "tab-graph") requestAnimationFrame(() => graphView.fitView());
      if (moveFocus) tab.focus();
    };
    tabs.forEach((tab, idx) => {
      tab.addEventListener("click", () => activateTab(tab));
      tab.addEventListener("keydown", (ev) => {
        const map = { ArrowDown: (idx + 1) % tabs.length, ArrowRight: (idx + 1) % tabs.length, ArrowUp: (idx - 1 + tabs.length) % tabs.length, ArrowLeft: (idx - 1 + tabs.length) % tabs.length, Home: 0, End: tabs.length - 1 };
        if (ev.key in map) { ev.preventDefault(); activateTab(tabs[map[ev.key]], true); }
      });
    });
    const rawTab = (location.hash.slice(1) || new URLSearchParams(location.search).get("tab") || "").replace(/^tab-/, "").replace(/^proposals$/, "lifecycle");
    const hashTab = tabs.find((t) => t.dataset.tab === `tab-${rawTab}`);
    if (hashTab) activateTab(hashTab);

    const search = document.getElementById("global-search"), clearBtn = document.getElementById("btn-clear-search"), kbd = document.getElementById("search-kbd");
    let timer = null;
    search.addEventListener("input", () => {
      clearBtn.classList.toggle("hidden", !search.value); kbd.classList.toggle("hidden", Boolean(search.value));
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const q = search.value.trim(), banner = document.getElementById("anti-repeat-banner");
        if (!q) { graphView.highlightIds.clear(); banner.classList.add("hidden"); return; }
        const data = await (await fetch(`/api/search?q=${encodeURIComponent(q)}&scope=${encodeURIComponent(currentScope)}`)).json();
        graphView.highlightIds = new Set((data.results || []).map((r) => r.id));
        banner.classList.toggle("hidden", !data.anti_repeat_warnings?.length);
        banner.innerHTML = data.anti_repeat_warnings?.length ? `<span>${tr("Dead-End Anti-Repeat Warning:", "Cảnh báo trùng hướng thất bại:")} ${data.anti_repeat_warnings.map(esc).join(" | ")}</span>` : "";
      }, 200);
    });
    clearBtn.addEventListener("click", () => {
      search.value = ""; clearBtn.classList.add("hidden"); kbd.classList.remove("hidden");
      graphView.highlightIds.clear(); document.getElementById("anti-repeat-banner").classList.add("hidden");
    });
    window.addEventListener("keydown", (ev) => {
      if (ev.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) { ev.preventDefault(); search.focus(); }
      else if (ev.key === "Escape" && !document.getElementById("workbench-dialog").open) inspector.close();
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    applyStaticLang(); hydrateIcons(document); Views.renderSkeletons();
    graphView = new ForceGraphCanvas(document.getElementById("graph-canvas"), document.getElementById("graph-tooltip"), (n) => inspector.inspect(n.id));
    modals = new ModalController(() => state, (sc) => { currentScope = sc; }, postJson, loadGraph, toast);
    inspector = new InspectorController(() => state, () => currentScope, postJson, loadGraph, (n) => modals.openUpsertNode(n), toast, () => { graphView.selectedId = null; });
    mergeStudio = new MergeStudioController(() => state, postJson, loadGraph, (id) => { graphView.selectedId = id; inspector.inspect(id); }, toast);
    bindTabsAndShortcuts();
    document.getElementById("btn-lang-toggle").addEventListener("click", () => {
      setLang(getLang() === "en" ? "vi" : "en"); rerenderAll();
      if (inspector.currentNodeId) inspector.inspect(inspector.currentNodeId);
    });
    document.querySelectorAll("[data-gmode]").forEach((b) => b.addEventListener("click", () => setGraphMode(b.dataset.gmode)));
    const on = (id, ev, fn) => document.getElementById(id).addEventListener(ev, fn);
    on("chk-hide-aux", "change", (ev) => graphView.setHideAux(ev.target.checked));
    on("workspace-switcher", "change", (ev) => { currentScope = ev.target.value; inspector.resetEmpty(); loadGraph(); });
    on("type-filter-select", "change", (ev) => { activeType = ev.target.value; graphView.setFilter(activeTier, activeType); });
    on("btn-refresh", "click", loadGraph); on("btn-zoom-in", "click", () => graphView.zoomBy(1.18));
    on("btn-zoom-out", "click", () => graphView.zoomBy(0.85)); on("btn-reset-zoom", "click", () => graphView.fitView());
    on("btn-relayout", "click", () => graphView.relayout()); on("exp-track-filter", "change", () => Views.renderExperiments(state, buildViewHandlers()));
    loadGraph();
  });
})();
