// Main State Container, Flexible Shell & Accessible Multi-Mode Studio Controller
(function () {
  const { hydrateIcons, esc, tr, getLang, setLang, applyStaticLang, syncPagers, resetPagers } = window.SuperMemoryIcons;
  const { ForceGraphCanvas } = window.SuperMemoryGraph, { InspectorController } = window.SuperMemoryInspector;
  const { MergeStudioController } = window.SuperMemoryMergeStudio, { ModalController } = window.SuperMemoryModals;
  const { SearchPaletteController } = window.SuperMemoryPalette, Views = window.SuperMemoryViews;
  const { ResearchHubController } = window.SuperMemoryResearchHub, { KanbanBoardController } = window.SuperMemoryKanbanBoard;
  const rawVer = document.querySelector('meta[name="sm-version"]')?.content || "", UI_VER = rawVer.includes("{{") ? "" : rawVer;
  let state = { nodes: [], edges: [], gates: [], experiments: [], events: [], meta: {}, analytics: {}, cognitive_tiers: {}, workspaces: [] };
  let currentScope = "local", activeTier = "ALL", activeType = "ALL", toastTimer = null, liveTimer = null, lastFetch = 0;
  let graphView = null, inspector = null, mergeStudio = null, modals = null, researchHub = null, kanbanBoard = null, activateTabFn = null;

  function toast(msg, isError = false) {
    const el = document.getElementById("toast-region"); el.textContent = msg; el.className = `toast-region${isError ? " toast-error" : ""}`;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.add("hidden"), 3400);
  }
  async function postJson(route, payload = {}) {
    const res = await fetch(route, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scope: currentScope, ...payload }) });
    const data = await res.json(); if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`); return data;
  }
  async function mutateAndRefresh(route, payload, msg) { try { await postJson(route, payload); toast(msg); await loadGraph(); } catch (err) { toast(err.message, true); } }

  function buildViewHandlers() {
    return {
      onInspect: (nid) => { graphView.selectedId = nid; inspector.inspect(nid); }, onInspectGate: (g) => inspector.inspectGate(g), onEditGate: (g) => modals.openAddGate(g),
      onToggleGate: (gid, enabled) => mutateAndRefresh("/api/gates", { action: "toggle", gate_id: gid, enabled }, tr(`Updated ${gid}`, `Đã cập nhật ${gid}`)),
      onDeleteGate: (gid) => mutateAndRefresh("/api/gates", { action: "delete", gate_id: gid }, tr(`Deleted ${gid}`, `Đã xóa ${gid}`)),
      onOpenLesson: () => modals.openAddLesson(), onOpenExp: () => modals.openAddExperiment(), onOpenProposal: () => modals.openAddProposal(), onOpenIdea: () => modals.openAddIdea(),
      onAdvanceProposal: (pid, next) => mutateAndRefresh("/api/proposals", { action: "advance", proposal_id: pid, new_stage: next }, tr(`Moved ${pid} to ${next}`, `Đã chuyển ${pid} sang ${next}`)),
      onAuditProposal: (pid) => mutateAndRefresh("/api/proposals", { action: "audit", proposal_id: pid, verdict: "APPROVE" }, tr(`Approved Audit for ${pid}`, `Đã phê duyệt Audit cho ${pid}`)),
    };
  }

  function focusInGraph(nodeId) {
    activateTabFn?.(document.getElementById("tabbtn-graph"));
    requestAnimationFrame(() => {
      if (graphView.focusNode(nodeId)) {
        document.getElementById("chk-hide-aux").checked = graphView.hideAux;
        activeTier = graphView.activeTier; activeType = graphView.activeType; renderGraphToolbar();
      }
    });
  }

  function rerenderAll() {
    renderWorkspaceSwitcher(); renderCommandAndTelemetry(); renderGraphToolbar();
    graphView._applyLayout(false); mergeStudio.render(); kanbanBoard.render(state);
    const h = buildViewHandlers();
    Views.renderConstitution(state, h); Views.renderExperiments(state, h); Views.renderLifecycle(state, h); Views.renderEvents(state, h); researchHub.render(state);
    if (inspector.currentNodeId?.startsWith("TASK:") && !document.activeElement?.closest("#insp-body input")) kanbanBoard.inspectTask(inspector.currentNodeId.slice(5));
  }

  const cmpVer = (a, b) => String(a).localeCompare(String(b), undefined, { numeric: true });
  async function loadGraph() {
    const errStrip = document.getElementById("error-banner"); errStrip.classList.add("hidden");
    try {
      const res = await fetch(`/api/graph?scope=${encodeURIComponent(currentScope)}`);
      if (!res.ok) throw new Error(tr(`Failed to load graph (HTTP ${res.status})`, `Không thể tải dữ liệu đồ thị (HTTP ${res.status})`));
      state = await res.json(); lastFetch = Date.now();
      if (state.ui_version && UI_VER && cmpVer(state.ui_version, UI_VER) > 0 && !sessionStorage.getItem(`sm_rl_${state.ui_version}`)) { sessionStorage.setItem(`sm_rl_${state.ui_version}`, "1"); location.reload(); return; }
      graphView.setData(state.nodes, state.edges); rerenderAll();
      const qs = new URLSearchParams(window.location.search), qMode = qs.get("mode"), qInspect = qs.get("inspect");
      if (qMode && ["FORCE", "RADIAL", "HIERARCHY", "LANES"].includes(qMode.toUpperCase())) setGraphMode(qMode.toUpperCase());
      if (qInspect && !inspector.currentNodeId) { graphView.selectedId = qInspect; inspector.inspect(qInspect); }
    } catch (err) {
      errStrip.classList.remove("hidden");
      errStrip.innerHTML = `<span>${tr("Server connection error:", "Lỗi kết nối máy chủ:")} ${esc(err.message)}</span><button type="button" id="btn-retry-load" class="btn btn-secondary btn-sm">${tr("Retry", "Thử lại")}</button>`;
      document.getElementById("btn-retry-load").addEventListener("click", loadGraph);
    }
  }

  function renderWorkspaceSwitcher() {
    const sel = document.getElementById("workspace-switcher"); sel.innerHTML = ""; let matched = false;
    (state.workspaces || []).forEach((w) => {
      const opt = Object.assign(document.createElement("option"), { value: w.id === "global" ? "global" : w.path, textContent: w.id === "global" ? tr("Global: All Workspaces", "Global: Tất cả dự án") : `Local: ${w.name}` });
      if ((currentScope === "global" && w.id === "global") || w.path === state.workspace_path) { opt.selected = true; matched = true; }
      sel.appendChild(opt);
    });
    if (!matched) sel.prepend(Object.assign(document.createElement("option"), { value: "local", textContent: `Local: ${state.project}`, selected: true }));
  }

  function renderCommandAndTelemetry() {
    const meta = state.meta || {}, nodes = state.nodes || [], gates = state.gates || [], exps = state.experiments || [], ov = state.execution_overview || {};
    const flat = (s) => String(s || "").replace(/^\s*\[['"]?|['"]?\]\s*$/g, "").replace(/['"],\s*['"]/g, " · ").replace(/\\n|\s+/g, " ").trim();
    const setTxt = (id, v, tip = false) => { const el = document.getElementById(id); if (el) { el.textContent = v; if (tip) el.title = String(v); } };
    setTxt("scope-indicator", state.is_global ? "GLOBAL" : "LOCAL"); setTxt("project-title", state.project || "SuperMemory", true);
    const vTag = document.querySelector(".version-tag"); if (vTag && state.ui_version) vTag.textContent = `Studio ${state.ui_version}`;
    setTxt("active-goal-line", flat(meta.active_goal) || "4-Tier Cognitive Graph & Constitutional Harness", true);
    setTxt("l0-phase", flat((meta.current_phase || tr("Active Studio", "Đang hoạt động")).split("|")[0].split("(")[0]), true);
    setTxt("l0-next", flat(meta.next_actions || meta.active_goal) || tr("Ready for research & verification.", "Sẵn sàng thực nghiệm & kiểm định."), true);
    const tiers = state.cognitive_tiers || {}, byTier = tiers.counts_by_tier || {}, activeTok = tiers.active_prompt_tokens || 0;
    setTxt("kpi-tokens", `${activeTok} / 850 tok`); document.getElementById("token-meter-bar").setAttribute("aria-valuenow", String(activeTok));
    document.getElementById("token-meter-fill").style.width = `${Math.min(100, Math.round((activeTok / 850) * 100))}%`;
    setTxt("kpi-compression", `${tiers.context_compression_pct || 0}%`); setTxt("kpi-blocks", (state.analytics || {}).total_blocked_regressions || 0);
    setTxt("nav-count-nodes", nodes.length); setTxt("nav-count-kanban", ov.total_items || 0);
    setTxt("nav-count-research", (state.bottlenecks || []).filter((b) => b.status !== "RESOLVED").length + (state.method_cards || []).length);
    setTxt("nav-count-episodic", byTier.EPISODIC || 0); setTxt("nav-count-gates", gates.length);
    setTxt("nav-count-exps", exps.length); setTxt("nav-count-props", nodes.filter((n) => n.node_type === "PROPOSAL").length); setTxt("nav-count-events", state.events_total ?? (state.events || []).length);
    const lawsCnt = nodes.filter((n) => n.node_type === "LAW").length, insCnt = nodes.filter((n) => ["OBSERVATION", "KNOWLEDGE_NODE", "ALGORITHM"].includes(n.node_type)).length;
    const pills = [
      ["tabbtn-kanban", `${ov.overall_pct ?? 0}% · ${ov.in_progress_count ?? 0}/${ov.total_items ?? 0} ${tr("Tasks", "Tác vụ")}`],
      ["tabbtn-constitution", `${lawsCnt} Laws · ${gates.filter((g) => g.enabled).length} Gates`],
      ["tabbtn-tiers", `${insCnt} ${tr("L2 Insights", "Insights L2")}`],
      ["tabbtn-experiments", `${exps.length} ${tr("Experiments", "Thực nghiệm")}`],
    ];
    const kpiBox = document.getElementById("l0-kpis");
    kpiBox.innerHTML = pills.map(([tid, txt]) => `<button type="button" class="l0-chip" data-jump-tab="${tid}">${esc(txt)}</button>`).join("");
    kpiBox.querySelectorAll("[data-jump-tab]").forEach((b) => b.addEventListener("click", () => activateTabFn?.(document.getElementById(b.dataset.jumpTab))));
  }

  function renderGraphToolbar() {
    const tc = ((state.cognitive_tiers || {}).counts_by_tier) || {}, total = (state.nodes || []).length;
    const segs = [["ALL", `${tr("All", "Tất cả")} (${total})`], ["PROCEDURAL", `L1 (${tc.PROCEDURAL || 0})`], ["SEMANTIC", `L2 (${tc.SEMANTIC || 0})`], ["EPISODIC", `L3 (${tc.EPISODIC || 0})`]];
    const tray = document.getElementById("tier-filters");
    tray.innerHTML = segs.map(([k, lbl]) => `<button type="button" class="seg-btn" aria-pressed="${activeTier === k}" data-tier="${k}">${esc(lbl)}</button>`).join("");
    tray.querySelectorAll("[data-tier]").forEach((btn) => btn.addEventListener("click", () => { activeTier = btn.dataset.tier; renderGraphToolbar(); graphView.setFilter(activeTier, activeType); }));
    const sel = document.getElementById("type-filter-select"), nc = (state.analytics || {}).nodes_by_type || {}, keys = Object.keys(nc).sort();
    if (activeType !== "ALL" && !nc[activeType]) activeType = "ALL";
    sel.innerHTML = `<option value="ALL">${tr("All Types", "Tất cả loại")} (${total})</option>` + keys.map((k) => `<option value="${esc(k)}" ${activeType === k ? "selected" : ""}>${esc(k)} (${nc[k]})</option>`).join("");
  }

  function setGraphMode(mode) { document.querySelectorAll("[data-gmode]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.gmode === mode))); graphView.setMode(mode); }

  function bindTabs() {
    const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
    activateTabFn = (tab, moveFocus = false) => {
      if (!tab) return;
      tabs.forEach((t) => {
        const sel = t === tab, p = document.getElementById(t.dataset.tab);
        t.classList.toggle("active", sel); t.setAttribute("aria-selected", String(sel)); t.setAttribute("tabindex", sel ? "0" : "-1");
        p.classList.toggle("active", sel); p.hidden = !sel;
      });
      if (tab.dataset.tab === "tab-graph") requestAnimationFrame(() => graphView.fitView());
      else syncPagers(document.getElementById(tab.dataset.tab));
      if (moveFocus) tab.focus();
    };
    tabs.forEach((tab, idx) => {
      tab.addEventListener("click", () => { activateTabFn(tab); if (tab.dataset.tab === "tab-events" || tab.dataset.tab === "tab-kanban" || Date.now() - lastFetch > 2500) loadGraph(); });
      tab.addEventListener("keydown", (ev) => {
        const map = { ArrowDown: (idx + 1) % tabs.length, ArrowRight: (idx + 1) % tabs.length, ArrowUp: (idx - 1 + tabs.length) % tabs.length, ArrowLeft: (idx - 1 + tabs.length) % tabs.length, Home: 0, End: tabs.length - 1 };
        if (ev.key in map) { ev.preventDefault(); activateTabFn(tabs[map[ev.key]], true); }
      });
    });
    const rawTab = (location.hash.slice(1) || new URLSearchParams(location.search).get("tab") || "").replace(/^tab-/, "").replace(/^proposals$/, "lifecycle");
    const hashTab = tabs.find((t) => t.dataset.tab === `tab-${rawTab}`); if (hashTab) activateTabFn(hashTab);
    window.addEventListener("focus", () => { if (Date.now() - lastFetch > 5000 && !document.getElementById("workbench-dialog").open) loadGraph(); });
    window.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && !document.getElementById("workbench-dialog").open) inspector.close(); });
  }

  document.addEventListener("DOMContentLoaded", () => {
    if (localStorage.getItem("sm_rail_collapsed") === "1") document.body.classList.add("rail-collapsed");
    if (localStorage.getItem("sm_l0_hidden") === "1") document.getElementById("l0-context-strip")?.classList.add("is-compact");
    applyStaticLang(); hydrateIcons(document); Views.renderSkeletons();
    graphView = new ForceGraphCanvas(document.getElementById("graph-canvas"), document.getElementById("graph-tooltip"), (n) => (n ? inspector.inspect(n.id) : inspector.close()), (st) => {
      document.getElementById("graph-stats-pill").textContent = `${st.visible}/${st.total} ${tr("nodes", "nút")} · ${st.edges} ${tr("edges", "cạnh")}${st.pinned ? ` · ${st.pinned} ${tr("pinned", "ghim")}` : ""}`;
    });
    modals = new ModalController(() => state, async (sc) => { currentScope = sc; await loadGraph(); }, postJson, loadGraph, toast);
    inspector = new InspectorController(() => state, () => currentScope, postJson, loadGraph, modals, toast, {
      onClearSelection: () => { graphView.selectedId = null; }, onFocusGraph: focusInGraph,
      onLayoutChange: () => { if (document.getElementById("tab-graph").classList.contains("active")) graphView.fitView(); },
    });
    const inspectNode = (id) => { graphView.selectedId = id; inspector.inspect(id); };
    mergeStudio = new MergeStudioController(() => state, postJson, loadGraph, inspectNode, toast);
    researchHub = new ResearchHubController(() => state, postJson, loadGraph, inspectNode, modals, toast, (tid) => kanbanBoard.inspectTask(tid));
    kanbanBoard = new KanbanBoardController({ getState: () => state, postJson, onRefresh: loadGraph, notify: toast, modals, inspector, onInspectNode: inspectNode, onOpenSprint: () => researchHub.openSprintModal() });
    new SearchPaletteController(() => currentScope, async (sc) => { currentScope = sc; await loadGraph(); }, inspectNode, focusInGraph, {
      newNode: () => modals.openUpsertNode(), newExp: () => modals.openAddExperiment(), newProp: () => modals.openAddProposal(),
      newLesson: () => modals.openAddLesson(), runAudit: () => modals.runAuditDialog(), handoff: () => modals.openHandoffDialog(), toggleDock: () => inspector.toggleDock(),
    }, (ids) => { graphView.highlightIds = ids; });
    bindTabs();
    const on = (id, ev, fn) => document.getElementById(id)?.addEventListener(ev, fn);
    on("btn-collapse-rail", "click", () => { const c = document.body.classList.toggle("rail-collapsed"); localStorage.setItem("sm_rail_collapsed", c ? "1" : "0"); requestAnimationFrame(() => graphView.fitView()); });
    on("btn-toggle-l0", "click", () => { const c = document.getElementById("l0-context-strip").classList.toggle("is-compact"); localStorage.setItem("sm_l0_hidden", c ? "1" : "0"); requestAnimationFrame(() => graphView.fitView()); });
    const setLive = (next, say = false) => {
      const btn = document.getElementById("btn-live-sync"); if (!btn) return;
      clearInterval(liveTimer); liveTimer = next ? setInterval(() => { if (!document.hidden && !document.getElementById("workbench-dialog").open && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName)) loadGraph(); }, 4000) : null;
      btn.setAttribute("aria-pressed", String(next)); btn.classList.toggle("is-live", next); localStorage.setItem("sm_live_sync", next ? "1" : "0");
      if (say) toast(next ? tr("Live auto-sync enabled (4s)", "Đã bật cập nhật trực tiếp (4s)") : tr("Live auto-sync paused", "Đã tạm dừng cập nhật trực tiếp"));
    };
    on("btn-live-sync", "click", () => setLive(!liveTimer, true)); setLive(localStorage.getItem("sm_live_sync") !== "0", false);
    on("btn-lang-toggle", "click", () => {
      setLang(getLang() === "en" ? "vi" : "en"); rerenderAll();
      if (inspector.currentNodeId?.startsWith("GATE:")) inspector.inspectGate((state.gates || []).find((g) => `GATE:${g.id}` === inspector.currentNodeId));
      else if (inspector.currentNodeId?.startsWith("TASK:")) kanbanBoard.inspectTask(inspector.currentNodeId.slice(5));
      else if (inspector.currentNodeId) inspector.inspect(inspector.currentNodeId, false);
    });
    document.querySelectorAll("[data-gmode]").forEach((b) => b.addEventListener("click", () => setGraphMode(b.dataset.gmode)));
    on("chk-hide-aux", "change", (ev) => graphView.setHideAux(ev.target.checked)); on("workspace-switcher", "change", (ev) => { currentScope = ev.target.value; resetPagers(true); inspector.resetEmpty(); loadGraph(); });
    on("type-filter-select", "change", (ev) => { activeType = ev.target.value; graphView.setFilter(activeTier, activeType); });
    on("btn-refresh", "click", loadGraph); on("btn-zoom-in", "click", () => graphView.zoomBy(1.18)); on("btn-zoom-out", "click", () => graphView.zoomBy(0.85));
    on("btn-reset-zoom", "click", () => graphView.fitView()); on("btn-relayout", "click", () => graphView.relayout()); on("btn-export-png", "click", () => graphView.exportPng(state.project));
    on("const-filter-input", "input", () => Views.renderConstitution(state, buildViewHandlers())); on("lifecycle-filter-input", "input", () => Views.renderLifecycle(state, buildViewHandlers()));
    ["exp-track-filter", "exp-verdict-filter", "exp-sort-select"].forEach((id) => on(id, "change", () => Views.renderExperiments(state, buildViewHandlers())));
    on("events-filter-input", "input", () => Views.renderEvents(state, buildViewHandlers())); loadGraph();
  });
})();
