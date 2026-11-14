// Main UI Application Controller for Multi-Project & Tiered SuperMemory Observatory
(function () {
  const { ForceGraphCanvas, TYPE_COLORS } = window.SuperMemoryGraph;
  const { MergeStudioController } = window.SuperMemoryMergeStudio;

  let state = { nodes: [], edges: [], gates: [], experiments: [], events: [], meta: {}, analytics: {}, cognitive_tiers: {}, workspaces: [] };
  let currentScope = "local";
  let graphView = null;
  let mergeStudio = null;

  const esc = (s) =>
    String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

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
    Object.keys(counts)
      .sort()
      .forEach((t) => {
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
      ? `<p style="margin:6px 0"><a class="file-link" href="file://${esc(rawPath)}" target="_blank">📄 ${esc(rawPath)}</a></p>`
      : "";
    const promoteBtn = !state.is_global
      ? `<button id="btn-promote-global" class="btn-primary" style="width:100%;margin:8px 0">🌐 Promote Node to Global SuperMemory</button><p id="promote-msg" class="muted"></p>`
      : "";
    const edgeButtons = edges
      .map((e) => {
        const other = e.source_id === node.id ? `→ ${e.relation} → ${e.target_id}` : `← ${e.relation} ← ${e.source_id}`;
        const jump = e.source_id === node.id ? e.target_id : e.source_id;
        return `<button class="edge-chip" data-jump="${esc(jump)}">${esc(other)}</button>`;
      })
      .join("");
    document.getElementById("insp-body").innerHTML = `
      <p><strong>Summary:</strong> ${esc(node.summary)}</p>
      ${srcLink}
      ${promoteBtn}
      <div class="insp-pre">${esc(node.content || node.summary)}</div>
      <h4 style="margin:10px 0 6px">Connected Graph Edges (${edges.length})</h4>
      <div>${edgeButtons || '<span class="muted">No edges</span>'}</div>
      <h4 style="margin:12px 0 6px">Metadata</h4>
      <div class="insp-pre">${esc(JSON.stringify(node.metadata || {}, null, 2))}</div>
    `;
    document.querySelectorAll("[data-jump]").forEach((el) => {
      el.onclick = () => inspectNodeById(el.getAttribute("data-jump"));
    });
    const pBtn = document.getElementById("btn-promote-global");
    if (pBtn) {
      pBtn.onclick = async () => {
        const pRes = await fetch("/api/promote", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ scope: currentScope, node_id: node.id }),
        });
        const pData = await pRes.json();
        document.getElementById("promote-msg").textContent = pRes.ok
          ? `✅ Promoted to Global as ${pData.global_id}`
          : `❌ ${pData.error}`;
        await loadGraph();
      };
    }
  }

  function cardHtml(n, badgeExtra = "") {
    return `<div class="entity-card" data-nid="${esc(n.id)}">
      <div class="card-top"><span class="card-id">${esc(n.id)}</span><span class="type-badge">${esc(badgeExtra || n.status)}</span></div>
      <div class="card-title">${esc(n.title)}</div>
      <div class="card-desc">${esc(n.summary).slice(0, 200)}</div>
    </div>`;
  }

  function bindCardClicks(container) {
    container.querySelectorAll("[data-nid]").forEach((el) => {
      el.onclick = () => inspectNodeById(el.getAttribute("data-nid"));
    });
  }

  function renderConstitutionTab() {
    const laws = state.nodes.filter((n) => n.node_type === "LAW" || n.node_type === "PROCEDURE");
    const lessons = state.nodes.filter((n) => n.node_type === "LESSON");
    const lawsBox = document.getElementById("laws-list");
    lawsBox.innerHTML = laws.map((l) => cardHtml(l, `${l.node_type} • Consolidated: ${(l.metadata || {}).recurrence_count || 0}`)).join("");
    bindCardClicks(lawsBox);

    document.getElementById("gates-list").innerHTML = state.gates
      .map(
        (g) => `<div class="entity-card">
          <div class="card-top"><span class="card-id">${esc(g.id)} • ${esc(g.gate_type)}</span>
          <span class="type-badge verdict-keep">Blocked: ${g.blocked_count}</span></div>
          <div class="card-title">${esc(g.name)} (${esc(g.law_id)})</div>
          <div class="card-desc">glob: <code>${esc(g.target_glob)}</code> | pattern: <code>${esc(String(g.pattern).slice(0, 68))}</code></div>
        </div>`
      )
      .join("");

    const lessonsBox = document.getElementById("lessons-list");
    lessonsBox.innerHTML = lessons.length ? lessons.map((l) => cardHtml(l, (l.metadata || {}).law_id || "LESSON")).join("") : '<p class="muted">No lessons recorded yet.</p>';
    bindCardClicks(lessonsBox);
  }

  function renderExperimentsTab() {
    const sel = document.getElementById("exp-track-filter");
    const tracks = Array.from(new Set(state.experiments.map((e) => e.track)));
    const cur = sel.value || "ALL";
    sel.innerHTML = `<option value="ALL">All Tracks (${state.experiments.length})</option>` + tracks.map((t) => `<option value="${esc(t)}">${esc(t)}</option>`).join("");
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
      box.innerHTML = '<p class="muted">Log 2+ numeric CV/Test experiments on a track to plot monotonic progression.</p>';
    }

    const tbody = document.getElementById("exp-table-body");
    tbody.innerHTML = filtered
      .map((e) => {
        const eid = e.exp_id || e.id;
        const cls = /REVERT|REJECT|FAIL/i.test(e.verdict) ? "verdict-revert" : "verdict-keep";
        const delta = e.delta_vs_baseline != null ? (e.delta_vs_baseline >= 0 ? `+${e.delta_vs_baseline.toFixed(4)}` : e.delta_vs_baseline.toFixed(4)) : "—";
        return `<tr data-nid="${esc(eid)}"><td><strong class="card-id">${esc(eid)}</strong></td><td>${esc(e.track)}</td>
          <td><strong>${esc(e.title)}</strong><div class="muted">${esc(e.single_var_diff || e.hypothesis).slice(0, 100)}</div></td>
          <td>${esc(e.cv_summary || (e.cv_score ?? "—"))}</td><td>${esc(e.test_summary || (e.test_score ?? "—"))}</td>
          <td>${delta}</td><td><span class="type-badge ${cls}">${esc(e.verdict)}</span></td></tr>`;
      })
      .join("");
    bindCardClicks(tbody);
  }

  function renderLifecycleTab() {
    const stages = ["PROPOSED", "DESIGNED", "IMPLEMENTING", "CHALLENGED", "AUDITED", "ARCHIVED"];
    const props = state.nodes.filter((n) => n.node_type === "PROPOSAL");
    const board = document.getElementById("proposal-kanban");
    board.innerHTML = stages.map((st) => {
      const items = props.filter((p) => p.status === st);
      return `<div class="kanban-col"><h4>${st} (${items.length})</h4><div class="card-stack">${items.map((i) => cardHtml(i, st)).join("")}</div></div>`;
    }).join("");
    bindCardClicks(board);

    const ideas = state.nodes.filter((n) => ["IDEA", "ALGORITHM", "OBSERVATION", "KNOWLEDGE_NODE"].includes(n.node_type));
    const grid = document.getElementById("ideas-grid");
    grid.innerHTML = ideas.length ? ideas.map((n) => cardHtml(n, `${n.memory_tier} • ${n.node_type} • ${n.status}`)).join("") : '<p class="muted">No Semantic Ideas/Insights yet.</p>';
    bindCardClicks(grid);
  }

  function renderEventsTab() {
    document.getElementById("events-list").innerHTML = state.events
      .map((ev) => `<div class="entity-card"><div class="card-top"><span class="card-id">${esc(ev.event_type)}</span><span class="muted">${esc(ev.created_at)}</span></div><div class="card-desc"><code>${esc(JSON.stringify(ev.payload))}</code></div></div>`)
      .join("");
  }

  document.addEventListener("DOMContentLoaded", () => {
    graphView = new ForceGraphCanvas(document.getElementById("graph-canvas"), document.getElementById("graph-tooltip"), (node) => inspectNodeById(node.id));
    mergeStudio = new MergeStudioController(() => state, () => currentScope, loadGraph, inspectNodeById);

    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.onclick = () => {
        document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
        document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
        btn.classList.add("active");
        document.getElementById(btn.dataset.tab).classList.add("active");
      };
    });

    document.getElementById("workspace-switcher").onchange = (ev) => {
      currentScope = ev.target.value;
      loadGraph();
    };
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
        if (data.anti_repeat_warnings && data.anti_repeat_warnings.length) {
          banner.classList.remove("hidden");
          banner.innerHTML = `<strong>⚠️ Federated Anti-Repeat Warnings:</strong> ${data.anti_repeat_warnings.map(esc).join(" | ")}`;
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
