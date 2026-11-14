// Main UI Application Controller for the SuperMemory Interactive Management Console
(function () {
  const { ForceGraphCanvas, TYPE_COLORS } = window.SuperMemoryGraph;
  const { MergeStudioController } = window.SuperMemoryMergeStudio;
  const { StudioActionsController } = window.SuperMemoryStudioActions;

  let state = { nodes: [], edges: [], gates: [], experiments: [], events: [], meta: {}, analytics: {}, cognitive_tiers: {}, workspaces: [] };
  let currentScope = "local";
  let graphView = null;
  let mergeStudio = null;
  let studioActions = null;

  const esc = (s) =>
    String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");

  async function loadGraph() {
    const res = await fetch(`/api/graph?scope=${encodeURIComponent(currentScope)}`);
    state = await res.json();
    renderWorkspaceSwitcher();
    renderHeaderAndKpis();
    renderTierAndTypePills();
    graphView.setData(state.nodes, state.edges);
    mergeStudio.render();
    renderConstitutionTab();
    renderExperimentsTab();
    renderLifecycleTab();
    renderEventsTab();
  }

  function renderWorkspaceSwitcher() {
    const sel = document.getElementById("workspace-switcher");
    const list = state.workspaces || [];
    sel.innerHTML = "";
    const curPath = state.workspace_path;
    let matched = false;
    list.forEach((w) => {
      const opt = document.createElement("option");
      opt.value = w.id === "global" ? "global" : w.path;
      opt.textContent = w.id === "global" ? w.name : `📁 Local: ${w.name}`;
      if ((currentScope === "global" && w.id === "global") || w.path === curPath) {
        opt.selected = true;
        matched = true;
      }
      sel.appendChild(opt);
    });
    if (!matched) {
      const opt = document.createElement("option");
      opt.value = "local";
      opt.textContent = `📁 Local: ${state.project}`;
      opt.selected = true;
      sel.prepend(opt);
    }
  }

  function renderHeaderAndKpis() {
    const scopeTag = state.is_global ? "🌐 GLOBAL" : "📁 LOCAL";
    document.getElementById("project-title").textContent = `${scopeTag} • ${state.project}`;
    document.getElementById("active-goal-line").textContent =
      state.meta.active_goal || "4-Tier Cognitive Graph & Federated Self-Learning Harness";

    const byTier = (state.cognitive_tiers || {}).counts_by_tier || {};
    const activeTok = (state.cognitive_tiers || {}).active_prompt_tokens || 0;
    document.getElementById("kpi-nodes").textContent = state.analytics.total_nodes || 0;
    document.getElementById("kpi-procedural").textContent = byTier.PROCEDURAL || 0;
    document.getElementById("kpi-semantic").textContent = byTier.SEMANTIC || 0;
    document.getElementById("kpi-episodic").textContent = byTier.EPISODIC || 0;
    document.getElementById("kpi-blocks").textContent = state.analytics.total_blocked_regressions || 0;
    document.getElementById("kpi-tokens").textContent = `~${activeTok} tok`;
  }

  function renderTierAndTypePills() {
    const tierBox = document.getElementById("tier-filters");
    const tierCounts = (state.cognitive_tiers || {}).counts_by_tier || {};
    const tierColors = { PROCEDURAL: "#10b981", SEMANTIC: "#38bdf8", EPISODIC: "#8b5cf6" };
    tierBox.innerHTML = "";
    ["PROCEDURAL", "SEMANTIC", "EPISODIC"].forEach((tr) => {
      const btn = document.createElement("button");
      btn.className = `pill ${graphView.hiddenTiers.has(tr) ? "muted-pill" : ""}`;
      btn.innerHTML = `<span class="pill-dot" style="background:${tierColors[tr]}"></span>${tr} (${tierCounts[tr] || 0})`;
      btn.onclick = () => {
        if (graphView.hiddenTiers.has(tr)) graphView.hiddenTiers.delete(tr);
        else graphView.hiddenTiers.add(tr);
        graphView.alpha = 0.45;
        renderTierAndTypePills();
      };
      tierBox.appendChild(btn);
    });

    const box = document.getElementById("type-filters");
    const counts = state.analytics.nodes_by_type || {};
    box.innerHTML = "";
    Object.keys(counts).sort().forEach((t) => {
      const btn = document.createElement("button");
      btn.className = `pill ${graphView.hiddenTypes.has(t) ? "muted-pill" : ""}`;
      btn.innerHTML = `<span class="pill-dot" style="background:${TYPE_COLORS[t] || "#94a3b8"}"></span>${esc(t)} (${counts[t]})`;
      btn.onclick = () => {
        if (graphView.hiddenTypes.has(t)) graphView.hiddenTypes.delete(t);
        else graphView.hiddenTypes.add(t);
        graphView.alpha = 0.45;
        renderTierAndTypePills();
      };
      box.appendChild(btn);
    });
  }

  async function inspectNodeById(nodeId) {
    const res = await fetch(`/api/node/${encodeURIComponent(nodeId)}?scope=${encodeURIComponent(currentScope)}`);
    if (!res.ok) return;
    const { node, edges } = await res.json();
    graphView.selectedId = node.id;
    document.getElementById("insp-badge").textContent = `${node.memory_tier || ""} • ${node.node_type} • ${node.status}`;
    document.getElementById("insp-id").textContent = `${node.id}: ${node.title}`;
    const rawPath = node.file_path || "";
    const srcLink = rawPath
      ? `<p style="margin:5px 0"><a class="file-link" href="file://${esc(rawPath)}" target="_blank">📄 ${esc(rawPath)}</a></p>`
      : "";
    const promoteBtn = !state.is_global
      ? `<button id="btn-promote-global" class="btn-ghost btn-xs">🌐 Đưa lên Global</button>`
      : "";
    const edgeButtons = edges
      .map((e) => {
        const other = e.source_id === node.id ? `→ ${e.relation} → ${e.target_id}` : `← ${e.relation} ← ${e.source_id}`;
        const jump = e.source_id === node.id ? e.target_id : e.source_id;
        return `<button class="edge-chip" data-jump="${esc(jump)}">${esc(other)}</button>`;
      })
      .join("");
    const otherNodesOpts = (state.nodes || [])
      .filter((x) => x.id !== node.id)
      .slice(0, 80)
      .map((x) => `<option value="${esc(x.id)}">${esc(x.id)} — ${esc(x.title.slice(0, 30))}</option>`)
      .join("");

    document.getElementById("insp-body").innerHTML = `
      <div class="card-actions" style="margin-bottom:8px">
        <button id="btn-edit-node" class="btn-primary btn-xs">✏️ Sửa Node</button>
        ${promoteBtn}
        <button id="btn-del-node" class="btn-danger btn-xs">🗑 Xóa</button>
      </div>
      <p><strong>Tóm tắt:</strong> ${esc(node.summary)}</p>
      ${srcLink}
      <div class="insp-pre">${esc(node.content || node.summary)}</div>

      <h4 style="margin:8px 0 5px">🔗 Nối Cạnh Đồ thị từ ${esc(node.id)}</h4>
      <div class="action-row" style="margin-bottom:10px">
        <select id="link-rel" class="select-input">
          ${["REFERENCES", "GOVERNED_BY", "DERIVED_FROM", "CONSOLIDATED_INTO", "VERIFIED_BY", "INSPIRED"].map((r) => `<option value="${r}">${r}</option>`).join("")}
        </select>
        <select id="link-dst" class="select-input" style="flex:1;max-width:170px">${otherNodesOpts}</select>
        <button id="btn-add-edge" class="btn-ghost btn-xs">+ Nối</button>
      </div>

      <h4 style="margin:8px 0 5px">Cạnh liên kết (${edges.length})</h4>
      <div>${edgeButtons || '<span class="muted">Chưa có cạnh nối</span>'}</div>
      <h4 style="margin:10px 0 5px">Metadata</h4>
      <div class="insp-pre">${esc(JSON.stringify(node.metadata || {}, null, 2))}</div>
    `;

    document.getElementById("btn-edit-node").onclick = () => studioActions.openUpsertNodeModal(node);
    document.getElementById("btn-del-node").onclick = async () => {
      if (!window.confirm(`Xóa vĩnh viễn node ${node.id} khỏi đồ thị?`)) return;
      try {
        await studioActions.postJson("/api/node/delete", { node_id: node.id });
        studioActions.toast(`🗑 Đã xóa ${node.id}`);
        document.getElementById("insp-body").innerHTML = '<p class="muted">Node đã được xóa.</p>';
        graphView.selectedId = null;
        await loadGraph();
      } catch (e) { studioActions.toast(`❌ ${e.message}`, true); }
    };
    const pBtn = document.getElementById("btn-promote-global");
    if (pBtn) {
      pBtn.onclick = async () => {
        try {
          const pData = await studioActions.postJson("/api/promote", { node_id: node.id });
          studioActions.toast(`🌐 Đã đưa lên Global: ${pData.global_id}`);
          await loadGraph();
        } catch (e) { studioActions.toast(`❌ ${e.message}`, true); }
      };
    }
    document.getElementById("btn-add-edge").onclick = async () => {
      const dst = document.getElementById("link-dst").value;
      const rel = document.getElementById("link-rel").value;
      if (!dst) return;
      try {
        await studioActions.postJson("/api/edge/add", { source_id: node.id, target_id: dst, relation: rel });
        studioActions.toast(`🔗 Đã nối ${node.id} -> ${dst}`);
        await loadGraph();
        inspectNodeById(node.id);
      } catch (e) { studioActions.toast(`❌ ${e.message}`, true); }
    };
    document.querySelectorAll("[data-jump]").forEach((el) => {
      el.onclick = () => inspectNodeById(el.getAttribute("data-jump"));
    });
  }

  function cardHtml(n, badgeExtra = "", extraActions = "") {
    return `<div class="entity-card" data-nid="${esc(n.id)}">
      <div class="card-top"><span class="card-id">${esc(n.id)}</span><span class="type-badge">${esc(badgeExtra || n.status)}</span></div>
      <div class="card-title">${esc(n.title)}</div>
      <div class="card-desc">${esc(n.summary).slice(0, 190)}</div>
      ${extraActions}
    </div>`;
  }

  function bindCardClicks(container) {
    container.querySelectorAll("[data-nid]").forEach((el) => {
      el.onclick = (ev) => {
        if (ev.target.closest("button")) return;
        inspectNodeById(el.getAttribute("data-nid"));
      };
    });
  }

  function renderConstitutionTab() {
    const laws = state.nodes.filter((n) => n.node_type === "LAW" || n.node_type === "PROCEDURE");
    const lessons = state.nodes.filter((n) => n.node_type === "LESSON");
    const lawsBox = document.getElementById("laws-list");
    lawsBox.innerHTML = laws.map((l) => cardHtml(l, `${l.node_type} • Đã gộp: ${(l.metadata || {}).recurrence_count || 0}`)).join("");
    bindCardClicks(lawsBox);

    const gatesBox = document.getElementById("gates-list");
    gatesBox.innerHTML = state.gates
      .map((g) => `<div class="entity-card">
        <div class="card-top">
          <span class="card-id">${esc(g.id)} • ${esc(g.gate_type)}</span>
          <span class="type-badge ${g.enabled ? "verdict-keep" : "verdict-revert"}">${g.enabled ? "🟢 ĐANG BẬT" : "⚪ TẠM TẮT"} • Chặn: ${g.blocked_count}</span>
        </div>
        <div class="card-title">${esc(g.name)} (${esc(g.law_id)})</div>
        <div class="card-desc">glob: <code>${esc(g.target_glob)}</code> | pattern: <code>${esc(String(g.pattern).slice(0, 64))}</code></div>
        <div class="card-actions">
          <button class="btn-ghost btn-xs" data-toggle-gate="${esc(g.id)}" data-enabled="${!g.enabled}">${g.enabled ? "⏸ Tạm tắt" : "▶ Bật lại"}</button>
          <button class="btn-danger btn-xs" data-del-gate="${esc(g.id)}">🗑 Xóa Gate</button>
        </div>
      </div>`).join("");

    gatesBox.querySelectorAll("[data-toggle-gate]").forEach((btn) => {
      btn.onclick = async () => {
        const gid = btn.getAttribute("data-toggle-gate");
        const en = btn.getAttribute("data-enabled") === "true";
        await studioActions.postJson("/api/gates", { action: "toggle", gate_id: gid, enabled: en });
        studioActions.toast(`🛡 ${gid} -> ${en ? "ĐANG BẬT" : "TẠM TẮT"}`);
        await loadGraph();
      };
    });
    gatesBox.querySelectorAll("[data-del-gate]").forEach((btn) => {
      btn.onclick = async () => {
        const gid = btn.getAttribute("data-del-gate");
        if (!window.confirm(`Xóa Gate ${gid}?`)) return;
        await studioActions.postJson("/api/gates", { action: "delete", gate_id: gid });
        studioActions.toast(`🗑 Đã xóa ${gid}`);
        await loadGraph();
      };
    });

    const lessonsBox = document.getElementById("lessons-list");
    lessonsBox.innerHTML = lessons.length ? lessons.map((l) => cardHtml(l, (l.metadata || {}).law_id || "LESSON")).join("") : '<p class="muted">Chưa có bài học nào.</p>';
    bindCardClicks(lessonsBox);
  }

  function renderExperimentsTab() {
    const sel = document.getElementById("exp-track-filter");
    const tracks = Array.from(new Set(state.experiments.map((e) => e.track)));
    const cur = sel.value || "ALL";
    sel.innerHTML = `<option value="ALL">Tất cả Track (${state.experiments.length})</option>` + tracks.map((t) => `<option value="${esc(t)}">${esc(t)}</option>`).join("");
    sel.value = tracks.includes(cur) ? cur : "ALL";
    const filtered = sel.value === "ALL" ? state.experiments : state.experiments.filter((e) => e.track === sel.value);

    const box = document.getElementById("exp-chart-box");
    const scored = [...filtered].reverse().filter((e) => typeof e.test_score === "number" || typeof e.cv_score === "number");
    if (scored.length >= 2) {
      const vals = scored.map((e) => (typeof e.test_score === "number" ? e.test_score : e.cv_score));
      const minV = Math.min(...vals), maxV = Math.max(...vals), span = maxV - minV || 1;
      const W = 860, H = 120, pad = 24;
      const pts = scored.map((e, i) => ({
        x: pad + (i / (scored.length - 1)) * (W - pad * 2),
        y: H - pad - (((typeof e.test_score === "number" ? e.test_score : e.cv_score) - minV) / span) * (H - pad * 2),
        id: e.exp_id || e.id,
      }));
      box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="120">
        <polyline fill="none" stroke="#38bdf8" stroke-width="2.2" points="${pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ")}" />
        ${pts.map((p) => `<circle cx="${p.x}" cy="${p.y}" r="4.5" fill="#10b981"><title>${esc(p.id)}</title></circle>`).join("")}
      </svg>`;
    } else {
      box.innerHTML = '<p class="muted">Log từ 2 thí nghiệm có điểm số trở lên để vẽ đường cong tiến trình.</p>';
    }

    const tbody = document.getElementById("exp-table-body");
    tbody.innerHTML = filtered.map((e) => {
      const eid = e.exp_id || e.id;
      const cls = /REVERT|REJECT|FAIL/i.test(e.verdict) ? "verdict-revert" : "verdict-keep";
      const delta = e.delta_vs_baseline != null ? (e.delta_vs_baseline >= 0 ? `+${e.delta_vs_baseline.toFixed(4)}` : e.delta_vs_baseline.toFixed(4)) : "—";
      return `<tr data-nid="${esc(eid)}"><td><strong class="card-id">${esc(eid)}</strong></td><td>${esc(e.track)}</td>
        <td><strong>${esc(e.title)}</strong><div class="muted">${esc(e.single_var_diff || e.hypothesis).slice(0, 100)}</div></td>
        <td>${esc(e.cv_summary || (e.cv_score ?? "—"))}</td><td>${esc(e.test_summary || (e.test_score ?? "—"))}</td>
        <td>${delta}</td><td><span class="type-badge ${cls}">${esc(e.verdict)}</span></td></tr>`;
    }).join("");
    bindCardClicks(tbody);
  }

  function renderLifecycleTab() {
    const stages = ["PROPOSED", "DESIGNED", "IMPLEMENTING", "CHALLENGED", "AUDITED", "ARCHIVED"];
    const props = state.nodes.filter((n) => n.node_type === "PROPOSAL");
    const board = document.getElementById("proposal-kanban");
    board.innerHTML = stages.map((st, idx) => {
      const items = props.filter((p) => p.status === st);
      const cards = items.map((p) => {
        let btns = "";
        if (idx < 3) btns += `<button class="btn-ghost btn-xs" data-prop-adv="${esc(p.id)}" data-next="${stages[idx + 1]}">▶ ${stages[idx + 1]}</button>`;
        if (st !== "AUDITED" && st !== "ARCHIVED") btns += `<button class="btn-primary btn-xs" data-prop-audit="${esc(p.id)}">✅ Duyệt</button>`;
        if (st === "AUDITED") btns += `<button class="btn-primary btn-xs" data-prop-adv="${esc(p.id)}" data-next="ARCHIVED">📦 Archive</button>`;
        return cardHtml(p, st, btns ? `<div class="card-actions">${btns}</div>` : "");
      }).join("");
      return `<div class="kanban-col"><h4>${st} (${items.length})</h4><div class="card-stack">${cards}</div></div>`;
    }).join("");
    bindCardClicks(board);

    board.querySelectorAll("[data-prop-adv]").forEach((btn) => {
      btn.onclick = async () => {
        try {
          await studioActions.postJson("/api/proposals", { action: "advance", proposal_id: btn.getAttribute("data-prop-adv"), new_stage: btn.getAttribute("data-next") });
          studioActions.toast(`📋 Đã chuyển sang ${btn.getAttribute("data-next")}`);
          await loadGraph();
        } catch (e) { studioActions.toast(`❌ ${e.message}`, true); }
      };
    });
    board.querySelectorAll("[data-prop-audit]").forEach((btn) => {
      btn.onclick = async () => {
        try {
          const pid = btn.getAttribute("data-prop-audit");
          await studioActions.postJson("/api/proposals", { action: "audit", proposal_id: pid, verdict: "APPROVE" });
          studioActions.toast(`✅ Đã duyệt VictoryAudit cho ${pid}`);
          await loadGraph();
        } catch (e) { studioActions.toast(`❌ ${e.message}`, true); }
      };
    });

    const ideas = state.nodes.filter((n) => ["IDEA", "ALGORITHM", "OBSERVATION", "KNOWLEDGE_NODE"].includes(n.node_type));
    const grid = document.getElementById("ideas-grid");
    grid.innerHTML = ideas.length ? ideas.map((n) => cardHtml(n, `${n.memory_tier} • ${n.node_type} • ${n.status}`)).join("") : '<p class="muted">Chưa có Idea / Insight nào.</p>';
    bindCardClicks(grid);
  }

  function renderEventsTab() {
    document.getElementById("events-list").innerHTML = state.events
      .map((ev) => `<div class="entity-card"><div class="card-top"><span class="card-id">${esc(ev.event_type)} • ${esc(ev.entity_id || "")}</span><span class="muted">${esc(ev.created_at)}</span></div><div class="card-desc">${esc(ev.summary || "")}</div></div>`)
      .join("");
  }

  document.addEventListener("DOMContentLoaded", () => {
    graphView = new ForceGraphCanvas(document.getElementById("graph-canvas"), document.getElementById("graph-tooltip"), (node) => inspectNodeById(node.id));
    studioActions = new StudioActionsController(() => state, () => currentScope, (sc) => { currentScope = sc; }, loadGraph, inspectNodeById);
    mergeStudio = new MergeStudioController(() => state, () => currentScope, loadGraph, inspectNodeById, (m) => studioActions.toast(m));

    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.onclick = () => {
        document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
        document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
        btn.classList.add("active");
        document.getElementById(btn.dataset.tab).classList.add("active");
      };
    });

    document.getElementById("workspace-switcher").onchange = (ev) => { currentScope = ev.target.value; loadGraph(); };
    document.getElementById("btn-refresh").onclick = loadGraph;
    document.getElementById("btn-relayout").onclick = () => graphView.relayout();
    document.getElementById("btn-reset-zoom").onclick = () => graphView.fitView();
    document.getElementById("btn-close-inspector").onclick = () => { graphView.selectedId = null; };
    document.getElementById("exp-track-filter").onchange = renderExperimentsTab;

    const searchInput = document.getElementById("global-search");
    let timer = null;
    searchInput.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        const q = searchInput.value.trim();
        const banner = document.getElementById("anti-repeat-banner");
        if (!q) {
          graphView.highlightIds.clear();
          banner.classList.add("hidden");
          return;
        }
        const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&scope=${encodeURIComponent(currentScope)}`);
        const data = await res.json();
        graphView.highlightIds = new Set((data.results || []).map((r) => r.id));
        if (data.anti_repeat_warnings?.length) {
          banner.classList.remove("hidden");
          banner.innerHTML = `<strong>⚠️ Cảnh báo Vết xe đổ (Local + Global):</strong> ${data.anti_repeat_warnings.map(esc).join(" | ")}`;
        } else {
          banner.classList.add("hidden");
        }
      }, 220);
    });
    document.getElementById("btn-clear-search").onclick = () => {
      searchInput.value = "";
      graphView.highlightIds.clear();
      document.getElementById("anti-repeat-banner").classList.add("hidden");
    };

    loadGraph();
  });
})();
