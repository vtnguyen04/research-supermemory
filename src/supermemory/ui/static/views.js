// Paginated, Filterable & Sortable Studio Views (Constitution, Experiments, Proposals, Events)
(function () {
  const { esc, statusTag, paginate, bindPagers, tr, cleanText } = window.SuperMemoryIcons;
  let activePropStage = "ALL", activeVaultType = "ALL", activeEvtCat = "ALL";
  const matchQ = (q, ...parts) => !q || parts.join(" ").toLowerCase().includes(q);

  function renderSkeletons() {
    const skel = `<div class="skeleton-stack" aria-busy="true" aria-label="${tr("Loading data", "Đang tải dữ liệu")}"><div class="skeleton-line"></div><div class="skeleton-line"></div><div class="skeleton-line"></div></div>`;
    ["laws-list", "gates-list", "lessons-list", "events-list"].forEach((id) => { const el = document.getElementById(id); if (el) el.innerHTML = skel; });
  }

  function rowBtnHtml(n, tagLabel = "") {
    return `<div role="listitem" class="ledger-listitem"><button type="button" class="ledger-row" data-nid="${esc(n.id)}">
      <span class="row-top"><span class="mono-id">${esc(n.id)}</span>${statusTag(n.status, tagLabel || n.status)}</span>
      <span class="row-title">${esc(cleanText(n.title, 110))}</span><span class="row-desc">${esc(cleanText(n.summary, 175))}</span></button></div>`;
  }

  function bindInspectTriggers(root, onInspect) {
    root.querySelectorAll("[data-nid]").forEach((btn) => btn.addEventListener("click", () => onInspect(btn.getAttribute("data-nid"))));
  }

  function renderConstitution(state, h) {
    const root = document.getElementById("tab-constitution"), q = (document.getElementById("const-filter-input")?.value || "").trim().toLowerCase();
    const laws = (state.nodes || []).filter((n) => (n.node_type === "LAW" || n.node_type === "PROCEDURE") && matchQ(q, n.id, n.title, n.summary));
    const gates = (state.gates || []).filter((g) => matchQ(q, g.id, g.name, g.law_id, g.gate_type, g.target_glob, g.pattern));
    const lessons = (state.nodes || []).filter((n) => n.node_type === "LESSON" && matchQ(q, n.id, n.title, n.summary));

    const pgLaws = paginate(laws, "const-laws", 5), lawsBox = document.getElementById("laws-list");
    lawsBox.innerHTML = (pgLaws.slice.length ? pgLaws.slice.map((l) => rowBtnHtml(l, `${l.node_type} · ${tr("Merged", "Gộp")} ${(l.metadata || {}).recurrence_count || 0}`)).join("") : `<div class="empty-state"><p class="empty-desc">${tr("No matching laws.", "Không có luật khớp bộ lọc.")}</p></div>`) + pgLaws.html;
    bindInspectTriggers(lawsBox, h.onInspect);

    const pgGates = paginate(gates, "const-gates", 4), gatesBox = document.getElementById("gates-list");
    gatesBox.innerHTML = (pgGates.slice.length ? pgGates.slice.map((g) => `<div role="listitem" class="ledger-item-static">
      <button type="button" class="row-trigger" data-gate-inspect="${esc(g.id)}">
        <span class="row-top"><span class="mono-id">${esc(g.id)} &middot; ${esc(g.gate_type)}</span>
          ${statusTag(g.enabled ? "ENABLED" : "DISABLED", `${g.enabled ? tr("ENABLED", "ĐANG BẬT") : tr("PAUSED", "TẠM TẮT")} (${g.blocked_count})`)}</span>
        <span class="row-title">${esc(g.name)} (${esc(g.law_id)})</span>
        <span class="row-desc"><code>${esc(g.target_glob)}</code> &middot; <code>${esc(String(g.pattern).slice(0, 72))}</code></span>
      </button>
      <div class="row-actions">
        <button type="button" class="btn btn-secondary btn-xs" data-gate-inspect="${esc(g.id)}">${tr("Inspect Full Regex", "Xem đầy đủ")}</button>
        <button type="button" class="btn btn-secondary btn-xs" data-edit-gate="${esc(g.id)}">${tr("Edit", "Sửa")}</button>
        <button type="button" class="btn btn-secondary btn-xs" data-toggle-gate="${esc(g.id)}" data-enabled="${!g.enabled}">${g.enabled ? tr("Pause", "Tạm tắt") : tr("Enable", "Bật lại")}</button>
        <span data-gate-del-zone="${esc(g.id)}"><button type="button" class="btn btn-danger btn-xs" data-arm-gate="${esc(g.id)}">${tr("Delete", "Xóa")}</button></span>
      </div></div>`).join("") : `<div class="empty-state"><p class="empty-desc">${tr("No matching CodeGates.", "Không có CodeGate khớp bộ lọc.")}</p></div>`) + pgGates.html;

    const gateMap = new Map((state.gates || []).map((g) => [g.id, g]));
    gatesBox.querySelectorAll("[data-gate-inspect]").forEach((b) => b.addEventListener("click", () => h.onInspectGate(gateMap.get(b.dataset.gateInspect))));
    gatesBox.querySelectorAll("[data-edit-gate]").forEach((b) => b.addEventListener("click", () => h.onEditGate(gateMap.get(b.dataset.editGate))));
    gatesBox.querySelectorAll("[data-toggle-gate]").forEach((b) => b.addEventListener("click", () => h.onToggleGate(b.dataset.toggleGate, b.dataset.enabled === "true")));
    gatesBox.querySelectorAll("[data-arm-gate]").forEach((btn) => btn.addEventListener("click", () => {
      const gid = btn.dataset.armGate, zone = gatesBox.querySelector(`[data-gate-del-zone="${CSS.escape(gid)}"]`);
      zone.innerHTML = `<button type="button" class="btn btn-danger btn-xs" data-confirm-gate="${esc(gid)}">${tr("Confirm", "Xác nhận")}</button><button type="button" class="btn btn-ghost btn-xs" data-cancel-gate="${esc(gid)}">${tr("Cancel", "Hủy")}</button>`;
      zone.querySelector("[data-confirm-gate]").addEventListener("click", () => h.onDeleteGate(gid));
      zone.querySelector("[data-cancel-gate]").addEventListener("click", () => renderConstitution(state, h));
    }));

    const lessonsBox = document.getElementById("lessons-list");
    if (lessons.length) {
      const pgLes = paginate(lessons, "const-lessons", 4);
      lessonsBox.innerHTML = pgLes.slice.map((l) => rowBtnHtml(l, (l.metadata || {}).law_id || "LESSON")).join("") + pgLes.html;
      bindInspectTriggers(lessonsBox, h.onInspect);
    } else {
      lessonsBox.innerHTML = `<div class="empty-state"><p class="empty-title">${tr("No lessons matched", "Chưa có bài học khớp")}</p><div><button type="button" id="cta-empty-lesson" class="btn btn-secondary btn-sm">${tr("+ Record Lesson", "+ Ghi bài học")}</button></div></div>`;
      document.getElementById("cta-empty-lesson").addEventListener("click", h.onOpenLesson);
    }
    bindPagers(root, () => renderConstitution(state, h));
  }

  function renderExperiments(state, h) {
    const sel = document.getElementById("exp-track-filter"), vSel = document.getElementById("exp-verdict-filter"), sSel = document.getElementById("exp-sort-select");
    const exps = state.experiments || [], tracks = Array.from(new Set(exps.map((e) => e.track))), cur = sel.value || "ALL";
    sel.innerHTML = `<option value="ALL">${tr("All Tracks", "Tất cả nhánh")} (${exps.length})</option>` + tracks.map((t) => `<option value="${esc(t)}">${esc(t)}</option>`).join("");
    sel.value = tracks.includes(cur) ? cur : "ALL";
    const vMode = vSel?.value || "ALL", sMode = sSel?.value || "NEWEST";
    const numScore = (e) => (typeof e.test_score === "number" ? e.test_score : typeof e.cv_score === "number" ? e.cv_score : -Infinity);
    let filtered = exps.filter((e) => (sel.value === "ALL" || e.track === sel.value) &&
      (vMode === "ALL" || (vMode === "WINNERS" ? ["VICTORY_CONFIRMED", "KEEP"].includes(e.verdict) : ["REVERT", "FAILED"].includes(e.verdict))));
    if (sMode === "SCORE") filtered = [...filtered].sort((a, b) => numScore(b) - numScore(a));
    else if (sMode === "DELTA") filtered = [...filtered].sort((a, b) => (b.delta_vs_baseline ?? -Infinity) - (a.delta_vs_baseline ?? -Infinity));

    const chart = document.getElementById("exp-chart-box"), scored = [...filtered].reverse().filter((e) => Number.isFinite(numScore(e)));
    if (scored.length >= 2) {
      const vals = scored.map(numScore), minV = Math.min(...vals), maxV = Math.max(...vals), span = maxV - minV || 1, W = 880, H = 144, px = 76, py = 26;
      const pts = scored.map((e, i) => ({ x: px + (i / (scored.length - 1)) * (W - px * 2), y: H - py - ((vals[i] - minV) / span) * (H - py * 2), id: e.exp_id || e.id, v: vals[i] }));
      chart.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="144" role="img" aria-label="${tr("Experiment score progression", "Đường cong điểm số thực nghiệm")}">
        <line x1="${px}" y1="${py}" x2="${W - px}" y2="${py}" stroke="#D5D1C7" stroke-dasharray="4 4"/><line x1="${px}" y1="${H - py}" x2="${W - px}" y2="${H - py}" stroke="#D5D1C7" stroke-dasharray="4 4"/>
        <text x="6" y="${py + 4}" fill="#484C56" font-size="13" font-family="JetBrains Mono, monospace">${maxV.toFixed(1)}</text>
        <text x="6" y="${H - py + 4}" fill="#484C56" font-size="13" font-family="JetBrains Mono, monospace">${minV.toFixed(1)}</text>
        <polyline fill="none" stroke="#141518" stroke-width="2.25" points="${pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ")}" />
        ${pts.map((p) => `<g class="chart-pt" data-nid="${esc(p.id)}"><circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="6" fill="#0284C7" stroke="#FFFFFF" stroke-width="2"/><text x="${p.x.toFixed(1)}" y="${Math.max(13, p.y - 10).toFixed(1)}" text-anchor="middle" fill="#141518" font-size="13" font-family="JetBrains Mono, monospace">${esc(p.id.replace(/^EXP-/, ""))}</text><title>${esc(p.id)}: ${p.v}</title></g>`).join("")}</svg>`;
      bindInspectTriggers(chart, h.onInspect);
    } else chart.innerHTML = `<div class="empty-state"><p class="empty-title">${tr("Need at least 2 numeric scores in filter to plot progression", "Cần ít nhất 2 điểm số định lượng để vẽ biểu đồ")}</p></div>`;

    const tbody = document.getElementById("exp-table-body"), pagerBox = document.getElementById("exp-pager");
    if (!filtered.length) {
      tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state"><p class="empty-title">${tr("No experiments match current filter", "Không có thực nghiệm khớp bộ lọc")}</p><div><button type="button" id="cta-empty-exp" class="btn btn-secondary btn-sm">${tr("+ Log Experiment", "+ Ghi thực nghiệm")}</button></div></div></td></tr>`;
      pagerBox.innerHTML = ""; document.getElementById("cta-empty-exp").addEventListener("click", h.onOpenExp); return;
    }
    const pg = paginate(filtered, "exp-table", 5);
    tbody.innerHTML = pg.slice.map((e) => {
      const eid = e.exp_id || e.id, delta = e.delta_vs_baseline != null ? (e.delta_vs_baseline >= 0 ? `+${e.delta_vs_baseline.toFixed(4)}` : e.delta_vs_baseline.toFixed(4)) : "—";
      return `<tr><td><button type="button" class="row-trigger" data-nid="${esc(eid)}"><span class="mono-id">${esc(eid)}</span></button></td><td class="mono-id">${esc(e.track)}</td>
        <td><button type="button" class="row-trigger" data-nid="${esc(eid)}"><span class="row-title">${esc(cleanText(e.title, 96))}</span><span class="row-desc">${esc(cleanText(e.single_var_diff || e.hypothesis, 115))}</span></button></td>
        <td class="metric-cell">${esc(e.cv_summary || (e.cv_score ?? "—"))}</td><td class="metric-cell">${esc(e.test_summary || (e.test_score ?? "—"))}</td><td class="num-col">${delta}</td><td>${statusTag(e.verdict)}</td></tr>`;
    }).join("");
    pagerBox.innerHTML = pg.html; bindInspectTriggers(tbody, h.onInspect); bindPagers(pagerBox, () => renderExperiments(state, h));
  }

  function renderLifecycle(state, h) {
    const root = document.getElementById("tab-lifecycle"), q = (document.getElementById("lifecycle-filter-input")?.value || "").trim().toLowerCase();
    const stages = ["PROPOSED", "DESIGNED", "IMPLEMENTING", "CHALLENGED", "AUDITED", "ARCHIVED"];
    const props = (state.nodes || []).filter((n) => n.node_type === "PROPOSAL" && matchQ(q, n.id, n.title, n.summary));
    const openCnt = props.filter((p) => p.status !== "ARCHIVED").length;
    const bar = document.getElementById("proposal-stage-bar");
    bar.innerHTML = [["ALL", `${tr("All", "Tất cả")} (${props.length})`], ["OPEN", `${tr("Open", "Đang mở")} (${openCnt})`], ...stages.map((s) => [s, `${s} (${props.filter((p) => p.status === s).length})`])]
      .map(([k, lbl]) => `<button type="button" class="seg-btn" aria-pressed="${activePropStage === k}" data-pstage="${k}">${esc(lbl)}</button>`).join("");
    bar.querySelectorAll("[data-pstage]").forEach((b) => b.addEventListener("click", () => { activePropStage = b.dataset.pstage; renderLifecycle(state, h); }));

    const filteredProps = activePropStage === "ALL" ? props : activePropStage === "OPEN" ? props.filter((p) => p.status !== "ARCHIVED") : props.filter((p) => p.status === activePropStage);
    const pgProps = paginate(filteredProps, `prop-${activePropStage}`, 6), grid = document.getElementById("proposal-grid");
    grid.innerHTML = pgProps.slice.length ? pgProps.slice.map((p) => {
      const idx = stages.indexOf(p.status); let acts = "";
      if (idx >= 0 && idx < 3) acts += `<button type="button" class="btn btn-secondary btn-xs" data-prop-adv="${esc(p.id)}" data-next="${stages[idx + 1]}">${tr("To", "Sang")} ${stages[idx + 1]}</button>`;
      if (p.status !== "AUDITED" && p.status !== "ARCHIVED") acts += `<button type="button" class="btn btn-primary btn-xs" data-prop-audit="${esc(p.id)}">${tr("Approve Audit", "Duyệt Audit")}</button>`;
      if (p.status === "AUDITED") acts += `<button type="button" class="btn btn-primary btn-xs" data-prop-adv="${esc(p.id)}" data-next="ARCHIVED">${tr("Archive", "Lưu trữ")}</button>`;
      return `<div class="ledger-panel"><div class="ledger-item-static"><button type="button" class="row-trigger" data-nid="${esc(p.id)}"><span class="row-top"><span class="mono-id">${esc(p.id)}</span>${statusTag(p.status)}</span><span class="row-title">${esc(cleanText(p.title, 96))}</span><span class="row-desc">${esc(cleanText(p.summary, 145))}</span></button>${acts ? `<div class="row-actions">${acts}</div>` : ""}</div></div>`;
    }).join("") : `<div class="ledger-panel"><div class="empty-state"><p class="empty-title">${tr("No proposals in this stage", "Không có Proposal ở giai đoạn này")}</p></div></div>`;
    document.getElementById("proposal-pager").innerHTML = pgProps.html; bindInspectTriggers(grid, h.onInspect);
    grid.querySelectorAll("[data-prop-adv]").forEach((b) => b.addEventListener("click", () => h.onAdvanceProposal(b.dataset.propAdv, b.dataset.next)));
    grid.querySelectorAll("[data-prop-audit]").forEach((b) => b.addEventListener("click", () => h.onAuditProposal(b.dataset.propAudit)));

    const allIdeas = (state.nodes || []).filter((n) => ["IDEA", "ALGORITHM", "OBSERVATION", "KNOWLEDGE_NODE"].includes(n.node_type) && matchQ(q, n.id, n.title, n.summary));
    const vBar = document.getElementById("vault-type-bar");
    const vOpts = [["ALL", `${tr("All", "Tất cả")} (${allIdeas.length})`], ["OBSERVATION", `${tr("Insights", "Insights")} (${allIdeas.filter((x) => x.node_type === "OBSERVATION").length})`], ["ALGORITHM", `${tr("Algorithms", "Thuật toán")} (${allIdeas.filter((x) => x.node_type === "ALGORITHM").length})`], ["IDEA", `Ideas (${allIdeas.filter((x) => x.node_type === "IDEA").length})`], ["DEAD_END", `Dead-Ends (${allIdeas.filter((x) => x.status === "REJECTED").length})`]];
    vBar.innerHTML = vOpts.map(([k, lbl]) => `<button type="button" class="seg-btn" aria-pressed="${activeVaultType === k}" data-vtype="${k}">${esc(lbl)}</button>`).join("");
    vBar.querySelectorAll("[data-vtype]").forEach((b) => b.addEventListener("click", () => { activeVaultType = b.dataset.vtype; renderLifecycle(state, h); }));
    const ideas = activeVaultType === "ALL" ? allIdeas : activeVaultType === "DEAD_END" ? allIdeas.filter((x) => x.status === "REJECTED") : allIdeas.filter((x) => x.node_type === activeVaultType);
    const pgIdeas = paginate(ideas, `ideas-${activeVaultType}`, 6), ideasGrid = document.getElementById("ideas-grid");
    ideasGrid.innerHTML = ideas.length ? pgIdeas.slice.map((n) => `<div role="listitem" class="ledger-panel"><button type="button" class="ledger-row" data-nid="${esc(n.id)}"><span class="row-top"><span class="mono-id">${esc(n.id)}</span>${statusTag(n.status, `${n.node_type} / ${n.status}`)}</span><span class="row-title">${esc(cleanText(n.title, 96))}</span><span class="row-desc">${esc(cleanText(n.summary, 145))}</span></button></div>`).join("") : `<div role="listitem" class="ledger-panel"><div class="empty-state"><p class="empty-title">${tr("No vault items match filter", "Không có mục nào khớp bộ lọc")}</p></div></div>`;
    document.getElementById("ideas-pager").innerHTML = pgIdeas.html; bindInspectTriggers(ideasGrid, h.onInspect); bindPagers(root, () => renderLifecycle(state, h));
  }

  function renderEvents(state, h) {
    const nodeSet = new Set((state.nodes || []).map((n) => n.id)), box = document.getElementById("events-list"), q = (document.getElementById("events-filter-input")?.value || "").trim().toLowerCase();
    const catMatch = (t) => activeEvtCat === "ALL" || (activeEvtCat === "LEARNING" && /LEARN|LESSON|CONSOLIDAT/.test(t)) || (activeEvtCat === "GATE" && /GATE|AUDIT/.test(t)) || (activeEvtCat === "ERROR" && /ERROR|BLOCK|FAIL/.test(t)) || (activeEvtCat === "GRAPH" && /NODE|EDGE|EXP|PROP/.test(t));
    const evBar = document.getElementById("events-cat-bar");
    evBar.innerHTML = [["ALL", tr("All Events", "Tất cả")], ["LEARNING", tr("Self-Learning", "Tự học")], ["GATE", "CodeGates"], ["GRAPH", tr("Graph & Exps", "Đồ thị & Exp")], ["ERROR", tr("Blocks & Errors", "Chặn & Lỗi")]]
      .map(([k, lbl]) => `<button type="button" class="seg-btn" aria-pressed="${activeEvtCat === k}" data-ecat="${k}">${esc(lbl)}</button>`).join("");
    evBar.querySelectorAll("[data-ecat]").forEach((b) => b.addEventListener("click", () => { activeEvtCat = b.dataset.ecat; renderEvents(state, h); }));

    const evs = (state.events || []).filter((ev) => catMatch(String(ev.event_type || "")) && matchQ(q, ev.event_type, ev.entity_id, ev.summary));
    const pg = paginate(evs, `ev-${activeEvtCat}`, 7);
    box.innerHTML = pg.slice.length ? pg.slice.map((ev) => `<div role="listitem" class="ledger-item-static">
      <div class="row-top"><span class="mono-id">${esc(ev.event_type)}${ev.entity_id ? ` &middot; ${esc(ev.entity_id)}` : ""}</span><span class="mono-id">${esc((ev.created_at || "").slice(0, 19))}</span></div>
      <div class="row-desc">${esc(cleanText(ev.summary || "", 200))}</div>
      ${ev.entity_id && nodeSet.has(ev.entity_id) ? `<div><button type="button" class="btn btn-secondary btn-xs" data-nid="${esc(ev.entity_id)}">${tr("Open", "Mở")} ${esc(ev.entity_id)}</button></div>` : ""}</div>`).join("") + pg.html
      : `<div role="listitem" class="empty-state"><p class="empty-desc">${tr("No telemetry events match current filter.", "Không có sự kiện nào khớp bộ lọc.")}</p></div>`;
    bindInspectTriggers(box, h.onInspect); bindPagers(box, () => renderEvents(state, h));
  }

  window.SuperMemoryViews = { renderSkeletons, renderConstitution, renderExperiments, renderLifecycle, renderEvents };
})();
