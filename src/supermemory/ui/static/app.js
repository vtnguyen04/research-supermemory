// Main UI Application Controller for SuperMemory Observatory
(function () {
  const { ForceGraphCanvas, TYPE_COLORS } = window.SuperMemoryGraph;
  let state = { nodes: [], edges: [], gates: [], experiments: [], events: [], meta: {}, analytics: {} };
  let graphView = null;

  const esc = (s) =>
    String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

  async function loadGraph() {
    const res = await fetch("/api/graph");
    state = await res.json();
    renderHeaderAndKpis();
    renderTypePills();
    graphView.setData(state.nodes, state.edges);
    renderConstitutionTab();
    renderExperimentsTab();
    renderLifecycleTab();
    renderEventsTab();
  }

  function renderHeaderAndKpis() {
    document.getElementById("project-title").textContent = `${state.project} — SuperMemory Harness`;
    document.getElementById("active-goal-line").textContent =
      state.meta.active_goal || "Zero-Amnesia Knowledge Graph & Self-Learning Anti-Regression Harness";
    const byType = state.analytics.nodes_by_type || {};
    document.getElementById("kpi-nodes").textContent = state.analytics.total_nodes || 0;
    document.getElementById("kpi-edges").textContent = state.analytics.total_edges || 0;
    document.getElementById("kpi-laws").textContent = byType.LAW || 0;
    document.getElementById("kpi-lessons").textContent = byType.LESSON || 0;
    document.getElementById("kpi-blocks").textContent = state.analytics.total_blocked_regressions || 0;
    document.getElementById("kpi-exps").textContent = state.experiments.length || byType.EXPERIMENT || 0;
  }

  function renderTypePills() {
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
          renderTypePills();
        };
        box.appendChild(btn);
      });
  }

  async function inspectNodeById(nodeId) {
    const res = await fetch(`/api/node/${encodeURIComponent(nodeId)}`);
    if (!res.ok) return;
    const { node, edges } = await res.json();
    graphView.selectedId = node.id;
    document.getElementById("insp-badge").textContent = `${node.node_type} • ${node.status}`;
    document.getElementById("insp-id").textContent = `${node.id}: ${node.title}`;
    const rawPath = node.file_path || node.source_path || "";
    const srcLink = rawPath
      ? `<p style="margin:6px 0"><a class="file-link" href="file://${esc(rawPath)}" target="_blank">📄 ${esc(rawPath)}</a></p>`
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
      <div class="insp-pre">${esc(node.content || node.summary)}</div>
      <h4 style="margin:10px 0 6px">Connected Graph Edges (${edges.length})</h4>
      <div>${edgeButtons || '<span class="muted">No edges</span>'}</div>
      <h4 style="margin:12px 0 6px">Metadata</h4>
      <div class="insp-pre">${esc(JSON.stringify(node.metadata || {}, null, 2))}</div>
    `;
    document.querySelectorAll("[data-jump]").forEach((el) => {
      el.onclick = () => inspectNodeById(el.getAttribute("data-jump"));
    });
  }

  function cardHtml(n, badgeExtra = "") {
    return `<div class="entity-card" data-nid="${esc(n.id)}">
      <div class="card-top"><span class="card-id">${esc(n.id)}</span><span class="type-badge">${esc(badgeExtra || n.status)}</span></div>
      <div class="card-title">${esc(n.title)}</div>
      <div class="card-desc">${esc(n.summary).slice(0, 220)}</div>
    </div>`;
  }

  function bindCardClicks(container) {
    container.querySelectorAll("[data-nid]").forEach((el) => {
      el.onclick = () => inspectNodeById(el.getAttribute("data-nid"));
    });
  }

  function renderConstitutionTab() {
    const laws = state.nodes.filter((n) => n.node_type === "LAW");
    const lessons = state.nodes.filter((n) => n.node_type === "LESSON");
    const lawsBox = document.getElementById("laws-list");
    lawsBox.innerHTML = laws.map((l) => cardHtml(l, `Consolidated: ${(l.metadata || {}).recurrence_count || 0}`)).join("");
    bindCardClicks(lawsBox);

    const gatesBox = document.getElementById("gates-list");
    gatesBox.innerHTML = state.gates
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
    lessonsBox.innerHTML = lessons.length
      ? lessons.map((l) => cardHtml(l, (l.metadata || {}).law_id || "LESSON")).join("")
      : '<p class="muted">No user corrections / mistakes recorded yet.</p>';
    bindCardClicks(lessonsBox);
  }

  function renderExperimentsTab() {
    const sel = document.getElementById("exp-track-filter");
    const tracks = Array.from(new Set(state.experiments.map((e) => e.track)));
    const cur = sel.value || "ALL";
    sel.innerHTML = `<option value="ALL">All Tracks (${state.experiments.length})</option>` +
      tracks.map((t) => `<option value="${esc(t)}">${esc(t)}</option>`).join("");
    sel.value = tracks.includes(cur) ? cur : "ALL";

    const filtered = sel.value === "ALL" ? state.experiments : state.experiments.filter((e) => e.track === sel.value);
    renderExpChart(filtered);

    const tbody = document.getElementById("exp-table-body");
    tbody.innerHTML = filtered
      .map((e) => {
        const eid = e.exp_id || e.id;
        const cls = /REVERT|REJECT|FAIL/i.test(e.verdict) ? "verdict-revert" : "verdict-keep";
        const delta = e.delta_vs_baseline != null ? (e.delta_vs_baseline >= 0 ? `+${e.delta_vs_baseline.toFixed(4)}` : e.delta_vs_baseline.toFixed(4)) : "—";
        return `<tr data-nid="${esc(eid)}">
          <td><strong class="card-id">${esc(eid)}</strong></td>
          <td>${esc(e.track)}</td>
          <td><strong>${esc(e.title)}</strong><div class="muted">${esc(e.single_var_diff || e.hypothesis).slice(0, 110)}</div></td>
          <td>${esc(e.cv_summary || (e.cv_score ?? "—"))}</td>
          <td>${esc(e.test_summary || (e.test_score ?? "—"))}</td>
          <td>${delta}</td>
          <td><span class="type-badge ${cls}">${esc(e.verdict)}</span></td>
        </tr>`;
      })
      .join("");
    bindCardClicks(tbody);
  }

  function renderExpChart(exps) {
    const box = document.getElementById("exp-chart-box");
    const scored = [...exps].reverse().filter((e) => typeof e.test_score === "number" || typeof e.cv_score === "number");
    if (scored.length < 2) {
      box.innerHTML = '<p class="muted">Log 2+ numeric CV/Test experiments on a track to plot monotonic metric lineage.</p>';
      return;
    }
    const vals = scored.map((e) => (typeof e.test_score === "number" ? e.test_score : e.cv_score));
    const minV = Math.min(...vals);
    const maxV = Math.max(...vals);
    const span = maxV - minV || 1;
    const W = 860, H = 125, pad = 26;
    const pts = scored.map((e, i) => {
      const x = pad + (i / (scored.length - 1)) * (W - pad * 2);
      const v = typeof e.test_score === "number" ? e.test_score : e.cv_score;
      const y = H - pad - ((v - minV) / span) * (H - pad * 2);
      return { x, y, v, id: e.exp_id || e.id };
    });
    const poly = pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
    const dots = pts.map((p) => `<circle cx="${p.x}" cy="${p.y}" r="4.5" fill="#10b981"><title>${esc(p.id)}: ${p.v}</title></circle>`).join("");
    box.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="125">
      <polyline fill="none" stroke="#38bdf8" stroke-width="2.2" points="${poly}" />
      ${dots}
      <text x="${pad}" y="14" fill="#94a3b8" font-size="11">Metric Progression (min=${minV.toFixed(4)} → max=${maxV.toFixed(4)})</text>
    </svg>`;
  }

  function renderLifecycleTab() {
    const stages = ["PROPOSED", "DESIGNED", "IMPLEMENTING", "CHALLENGED", "AUDITED", "ARCHIVED"];
    const props = state.nodes.filter((n) => n.node_type === "PROPOSAL");
    const board = document.getElementById("proposal-kanban");
    board.innerHTML = stages
      .map((st) => {
        const items = props.filter((p) => p.status === st);
        return `<div class="kanban-col"><h4>${st} (${items.length})</h4>
          <div class="card-stack">${items.map((i) => cardHtml(i, st)).join("")}</div></div>`;
      })
      .join("");
    bindCardClicks(board);

    const ideas = state.nodes.filter((n) => n.node_type === "IDEA" || n.node_type === "ALGORITHM");
    const grid = document.getElementById("ideas-grid");
    grid.innerHTML = ideas.length
      ? ideas.map((n) => cardHtml(n, `${n.node_type} • ${n.status}`)).join("")
      : '<p class="muted">No Ideas or Algorithms logged yet. Use `supermemory idea` or MCP `supermemory_propose_idea`.</p>';
    bindCardClicks(grid);
  }

  function renderEventsTab() {
    const box = document.getElementById("events-list");
    box.innerHTML = state.events
      .map(
        (ev) => `<div class="entity-card">
          <div class="card-top"><span class="card-id">${esc(ev.event_type)}</span><span class="muted">${esc(ev.created_at)}</span></div>
          <div class="card-desc"><code>${esc(JSON.stringify(ev.payload))}</code></div>
        </div>`
      )
      .join("");
  }

  document.addEventListener("DOMContentLoaded", () => {
    graphView = new ForceGraphCanvas(
      document.getElementById("graph-canvas"),
      document.getElementById("graph-tooltip"),
      (node) => inspectNodeById(node.id)
    );

    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.onclick = () => {
        document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
        document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
        btn.classList.add("active");
        document.getElementById(btn.dataset.tab).classList.add("active");
      };
    });

    document.getElementById("btn-refresh").onclick = loadGraph;
    document.getElementById("btn-relayout").onclick = () => graphView.relayout();
    document.getElementById("btn-reset-zoom").onclick = () => graphView.fitView();
    document.getElementById("btn-close-inspector").onclick = () => {
      graphView.selectedId = null;
    };
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
        const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
        const data = await res.json();
        graphView.highlightIds = new Set((data.results || []).map((r) => r.id));
        if (data.anti_repeat_warnings && data.anti_repeat_warnings.length) {
          banner.classList.remove("hidden");
          banner.innerHTML = `<strong>⚠️ Anti-Repeat Dead-End Warnings:</strong> ${data.anti_repeat_warnings.map(esc).join(" | ")}`;
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
