// Main State Container & Accessible Workbench Shell Controller
(function () {
  const { hydrateIcons, esc } = window.SuperMemoryIcons;
  const { ForceGraphCanvas } = window.SuperMemoryGraph;
  const { InspectorController } = window.SuperMemoryInspector;
  const { MergeStudioController } = window.SuperMemoryMergeStudio;
  const { ModalController } = window.SuperMemoryModals;
  const Views = window.SuperMemoryViews;

  let state = { nodes: [], edges: [], gates: [], experiments: [], events: [], meta: {}, analytics: {}, cognitive_tiers: {}, workspaces: [] };
  let currentScope = "local";
  let graphView = null, inspector = null, mergeStudio = null, modals = null, toastTimer = null;

  function toast(msg, isError = false) {
    const el = document.getElementById("toast-region");
    el.textContent = msg;
    el.className = `toast-region${isError ? " toast-error" : ""}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add("hidden"), 3400);
  }

  async function postJson(route, payload = {}) {
    const res = await fetch(route, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scope: currentScope, ...payload }),
    });
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
      onToggleGate: (gid, enabled) => mutateAndRefresh("/api/gates", { action: "toggle", gate_id: gid, enabled }, `Đã cập nhật ${gid}`),
      onDeleteGate: (gid) => mutateAndRefresh("/api/gates", { action: "delete", gate_id: gid }, `Đã xóa ${gid}`),
      onOpenLesson: () => modals.openAddLesson(),
      onOpenExp: () => modals.openAddExperiment(),
      onOpenProposal: () => modals.openAddProposal(),
      onOpenIdea: () => modals.openAddIdea(),
      onAdvanceProposal: (pid, next) => mutateAndRefresh("/api/proposals", { action: "advance", proposal_id: pid, new_stage: next }, `Đã chuyển ${pid} sang ${next}`),
      onAuditProposal: (pid) => mutateAndRefresh("/api/proposals", { action: "audit", proposal_id: pid, verdict: "APPROVE" }, `Đã phê duyệt Audit cho ${pid}`),
    };
  }

  async function loadGraph() {
    const errStrip = document.getElementById("error-banner");
    errStrip.classList.add("hidden");
    try {
      const res = await fetch(`/api/graph?scope=${encodeURIComponent(currentScope)}`);
      if (!res.ok) throw new Error(`Không thể tải dữ liệu đồ thị (HTTP ${res.status})`);
      state = await res.json();
      renderWorkspaceSwitcher();
      renderCommandAndTelemetry();
      renderFilterChips();
      graphView.setData(state.nodes, state.edges);
      mergeStudio.render();
      const handlers = buildViewHandlers();
      Views.renderConstitution(state, handlers);
      Views.renderExperiments(state, handlers);
      Views.renderLifecycle(state, handlers);
      Views.renderEvents(state, handlers);
    } catch (err) {
      errStrip.classList.remove("hidden");
      errStrip.innerHTML = `<span>Lỗi kết nối máy chủ: ${esc(err.message)}</span>
        <button type="button" id="btn-retry-load" class="btn btn-secondary btn-xs">Thử lại</button>`;
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
      opt.textContent = w.id === "global" ? "Global: Tất cả dự án" : `Local: ${w.name}`;
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

  function renderChipGroup(boxId, entries, hiddenSet) {
    const box = document.getElementById(boxId);
    box.innerHTML = entries.map(([k, cnt]) => `<button type="button" class="filter-chip" aria-pressed="${!hiddenSet.has(k)}" data-chip="${esc(k)}">
      <span class="chip-dot" data-tone="${esc(k)}"></span><span>${esc(k)} (${cnt})</span></button>`).join("");
    box.querySelectorAll("[data-chip]").forEach((btn) => btn.addEventListener("click", () => {
      const k = btn.getAttribute("data-chip");
      if (hiddenSet.has(k)) hiddenSet.delete(k); else hiddenSet.add(k);
      graphView.alpha = 0.45; renderFilterChips();
    }));
  }

  function renderFilterChips() {
    const tc = ((state.cognitive_tiers || {}).counts_by_tier) || {};
    renderChipGroup("tier-filters", ["PROCEDURAL", "SEMANTIC", "EPISODIC"].map((k) => [k, tc[k] || 0]), graphView.hiddenTiers);
    const nc = (state.analytics || {}).nodes_by_type || {};
    renderChipGroup("type-filters", Object.keys(nc).sort().map((k) => [k, nc[k]]), graphView.hiddenTypes);
  }

  function bindTabsAndShortcuts() {
    const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
    const activateTab = (tab, moveFocus = false) => {
      tabs.forEach((t) => {
        const sel = t === tab;
        t.classList.toggle("active", sel); t.setAttribute("aria-selected", String(sel)); t.setAttribute("tabindex", sel ? "0" : "-1");
        const p = document.getElementById(t.dataset.tab); p.classList.toggle("active", sel); p.hidden = !sel;
      });
      if (moveFocus) tab.focus();
    };
    tabs.forEach((tab, idx) => {
      tab.addEventListener("click", () => activateTab(tab));
      tab.addEventListener("keydown", (ev) => {
        const map = { ArrowDown: (idx + 1) % tabs.length, ArrowRight: (idx + 1) % tabs.length, ArrowUp: (idx - 1 + tabs.length) % tabs.length, ArrowLeft: (idx - 1 + tabs.length) % tabs.length, Home: 0, End: tabs.length - 1 };
        if (ev.key in map) { ev.preventDefault(); activateTab(tabs[map[ev.key]], true); }
      });
    });

    const search = document.getElementById("global-search"), clearBtn = document.getElementById("btn-clear-search");
    let timer = null;
    search.addEventListener("input", () => {
      clearBtn.classList.toggle("hidden", !search.value);
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const q = search.value.trim(), banner = document.getElementById("anti-repeat-banner");
        if (!q) { graphView.highlightIds.clear(); banner.classList.add("hidden"); return; }
        const data = await (await fetch(`/api/search?q=${encodeURIComponent(q)}&scope=${encodeURIComponent(currentScope)}`)).json();
        graphView.highlightIds = new Set((data.results || []).map((r) => r.id));
        banner.classList.toggle("hidden", !data.anti_repeat_warnings?.length);
        banner.innerHTML = data.anti_repeat_warnings?.length ? `<span>Cảnh báo trùng hướng thất bại: ${data.anti_repeat_warnings.map(esc).join(" | ")}</span>` : "";
      }, 200);
    });
    clearBtn.addEventListener("click", () => { search.value = ""; clearBtn.classList.add("hidden"); graphView.highlightIds.clear(); document.getElementById("anti-repeat-banner").classList.add("hidden"); });
    window.addEventListener("keydown", (ev) => {
      if (ev.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) { ev.preventDefault(); search.focus(); }
      else if (ev.key === "Escape" && !document.getElementById("workbench-dialog").open) inspector.close();
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    hydrateIcons(document); Views.renderSkeletons();
    graphView = new ForceGraphCanvas(document.getElementById("graph-canvas"), document.getElementById("graph-tooltip"), (n) => inspector.inspect(n.id));
    modals = new ModalController(() => state, (sc) => { currentScope = sc; }, postJson, loadGraph, toast);
    inspector = new InspectorController(() => state, () => currentScope, postJson, loadGraph, (n) => modals.openUpsertNode(n), toast, () => { graphView.selectedId = null; });
    mergeStudio = new MergeStudioController(() => state, postJson, loadGraph, (id) => { graphView.selectedId = id; inspector.inspect(id); }, toast);
    bindTabsAndShortcuts();
    document.getElementById("workspace-switcher").addEventListener("change", (ev) => { currentScope = ev.target.value; inspector.resetEmpty(); loadGraph(); });
    document.getElementById("btn-refresh").addEventListener("click", loadGraph);
    document.getElementById("btn-zoom-in").addEventListener("click", () => graphView.zoomBy(1.2));
    document.getElementById("btn-zoom-out").addEventListener("click", () => graphView.zoomBy(0.84));
    document.getElementById("btn-reset-zoom").addEventListener("click", () => graphView.fitView());
    document.getElementById("btn-relayout").addEventListener("click", () => graphView.relayout());
    document.getElementById("exp-track-filter").addEventListener("change", () => Views.renderExperiments(state, buildViewHandlers()));
    loadGraph();
  });
})();
