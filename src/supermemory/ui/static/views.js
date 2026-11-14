// High-Legibility Daylight Presentation Views (Constitution, Experiments, Proposals, Events)
(function () {
  const { esc, statusTag } = window.SuperMemoryIcons;

  function renderSkeletons() {
    const skel = `<div class="skeleton-stack" aria-busy="true" aria-label="Đang tải dữ liệu">
      <div class="skeleton-line"></div><div class="skeleton-line"></div><div class="skeleton-line"></div></div>`;
    ["laws-list", "gates-list", "lessons-list", "events-list"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = skel;
    });
  }

  function rowBtnHtml(n, tagLabel = "") {
    return `<div role="listitem" class="ledger-listitem">
      <button type="button" class="ledger-row" data-nid="${esc(n.id)}">
        <span class="row-top"><span class="mono-id">${esc(n.id)}</span>${statusTag(n.status, tagLabel || n.status)}</span>
        <span class="row-title">${esc(n.title)}</span>
        <span class="row-desc">${esc(n.summary).slice(0, 190)}</span>
      </button></div>`;
  }

  function bindInspectTriggers(root, onInspect) {
    root.querySelectorAll("[data-nid]").forEach((btn) => {
      btn.addEventListener("click", () => onInspect(btn.getAttribute("data-nid")));
    });
  }

  function renderConstitution(state, h) {
    const laws = (state.nodes || []).filter((n) => n.node_type === "LAW" || n.node_type === "PROCEDURE");
    const lessons = (state.nodes || []).filter((n) => n.node_type === "LESSON");
    const lawsBox = document.getElementById("laws-list");
    lawsBox.innerHTML = laws.map((l) => rowBtnHtml(l, `${l.node_type} · Gộp ${(l.metadata || {}).recurrence_count || 0}`)).join("");
    bindInspectTriggers(lawsBox, h.onInspect);

    const gatesBox = document.getElementById("gates-list");
    gatesBox.innerHTML = (state.gates || [])
      .map((g) => `<div role="listitem" class="ledger-item-static">
        <div class="row-top">
          <span class="mono-id">${esc(g.id)} &middot; ${esc(g.gate_type)}</span>
          ${statusTag(g.enabled ? "ENABLED" : "DISABLED", `${g.enabled ? "ĐANG BẬT" : "TẠM TẮT"} (${g.blocked_count})`)}
        </div>
        <div class="row-title">${esc(g.name)} (${esc(g.law_id)})</div>
        <div class="row-desc"><code>${esc(g.target_glob)}</code> &middot; <code>${esc(String(g.pattern).slice(0, 68))}</code></div>
        <div class="row-actions">
          <button type="button" class="btn btn-secondary btn-xs" data-toggle-gate="${esc(g.id)}" data-enabled="${!g.enabled}">${g.enabled ? "Tạm tắt" : "Bật lại"}</button>
          <span data-gate-del-zone="${esc(g.id)}">
            <button type="button" class="btn btn-danger btn-xs" data-arm-gate="${esc(g.id)}">Xóa Gate</button>
          </span>
        </div></div>`)
      .join("");

    gatesBox.querySelectorAll("[data-toggle-gate]").forEach((btn) => {
      btn.addEventListener("click", () => h.onToggleGate(btn.getAttribute("data-toggle-gate"), btn.getAttribute("data-enabled") === "true"));
    });
    gatesBox.querySelectorAll("[data-arm-gate]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const gid = btn.getAttribute("data-arm-gate");
        const zone = gatesBox.querySelector(`[data-gate-del-zone="${CSS.escape(gid)}"]`);
        zone.innerHTML = `<button type="button" class="btn btn-danger btn-xs" data-confirm-gate="${esc(gid)}">Xác nhận xóa</button>
          <button type="button" class="btn btn-ghost btn-xs" data-cancel-gate="${esc(gid)}">Hủy</button>`;
        zone.querySelector("[data-confirm-gate]").focus();
        zone.querySelector("[data-confirm-gate]").addEventListener("click", () => h.onDeleteGate(gid));
        zone.querySelector("[data-cancel-gate]").addEventListener("click", () => renderConstitution(state, h));
      });
    });

    const lessonsBox = document.getElementById("lessons-list");
    if (lessons.length) {
      lessonsBox.innerHTML = lessons.map((l) => rowBtnHtml(l, (l.metadata || {}).law_id || "LESSON")).join("");
      bindInspectTriggers(lessonsBox, h.onInspect);
    } else {
      lessonsBox.innerHTML = `<div class="empty-state"><p class="empty-title">Chưa có bài học nào được ghi</p>
        <p class="empty-desc">Ghi lại sai lầm hoặc quy tắc để tự động kết tinh thành Luật và chốt chặn CodeGate.</p>
        <div><button type="button" id="cta-empty-lesson" class="btn btn-secondary btn-sm">Ghi bài học đầu tiên</button></div></div>`;
      document.getElementById("cta-empty-lesson").addEventListener("click", h.onOpenLesson);
    }
  }

  function renderExperiments(state, h) {
    const sel = document.getElementById("exp-track-filter");
    const exps = state.experiments || [];
    const tracks = Array.from(new Set(exps.map((e) => e.track)));
    const cur = sel.value || "ALL";
    sel.innerHTML = `<option value="ALL">Tất cả nhánh (${exps.length})</option>` + tracks.map((t) => `<option value="${esc(t)}">${esc(t)}</option>`).join("");
    sel.value = tracks.includes(cur) ? cur : "ALL";
    const filtered = sel.value === "ALL" ? exps : exps.filter((e) => e.track === sel.value);

    const chart = document.getElementById("exp-chart-box");
    const scored = [...filtered].reverse().filter((e) => typeof e.test_score === "number" || typeof e.cv_score === "number");
    if (scored.length >= 2) {
      const vals = scored.map((e) => (typeof e.test_score === "number" ? e.test_score : e.cv_score));
      const minV = Math.min(...vals), maxV = Math.max(...vals), span = maxV - minV || 1;
      const W = 880, H = 148, px = 54, py = 24;
      const pts = scored.map((e, i) => ({
        x: px + (i / (scored.length - 1)) * (W - px * 2),
        y: H - py - (((typeof e.test_score === "number" ? e.test_score : e.cv_score) - minV) / span) * (H - py * 2),
        id: e.exp_id || e.id, v: vals[i],
      }));
      chart.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="148" role="img" aria-label="Đường cong điểm số thực nghiệm">
        <line x1="${px}" y1="${py}" x2="${W - px}" y2="${py}" stroke="#D5D1C7" stroke-dasharray="4 4"/>
        <line x1="${px}" y1="${H - py}" x2="${W - px}" y2="${H - py}" stroke="#D5D1C7" stroke-dasharray="4 4"/>
        <text x="6" y="${py + 4}" fill="#484C56" font-size="12" font-family="JetBrains Mono, monospace">${maxV.toFixed(1)}</text>
        <text x="6" y="${H - py + 4}" fill="#484C56" font-size="12" font-family="JetBrains Mono, monospace">${minV.toFixed(1)}</text>
        <polyline fill="none" stroke="#141518" stroke-width="2.25" points="${pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ")}" />
        ${pts.map((p) => `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="5" fill="#0284C7" stroke="#FFFFFF" stroke-width="2"><title>${esc(p.id)}: ${p.v}</title></circle>`).join("")}
      </svg>`;
    } else {
      chart.innerHTML = `<div class="empty-state"><p class="empty-title">Chưa đủ điểm số định lượng để vẽ biểu đồ</p>
        <p class="empty-desc">Ghi nhận từ 2 thực nghiệm có điểm CV hoặc Test trở lên để hiển thị đường tiến trình.</p></div>`;
    }

    const tbody = document.getElementById("exp-table-body");
    if (!filtered.length) {
      tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state"><p class="empty-title">Sổ cái thực nghiệm đang trống</p>
        <div><button type="button" id="cta-empty-exp" class="btn btn-secondary btn-sm">Ghi thực nghiệm đầu tiên</button></div></div></td></tr>`;
      document.getElementById("cta-empty-exp").addEventListener("click", h.onOpenExp);
      return;
    }
    tbody.innerHTML = filtered
      .map((e) => {
        const eid = e.exp_id || e.id;
        const delta = e.delta_vs_baseline != null ? (e.delta_vs_baseline >= 0 ? `+${e.delta_vs_baseline.toFixed(4)}` : e.delta_vs_baseline.toFixed(4)) : "—";
        return `<tr>
          <td><button type="button" class="row-trigger" data-nid="${esc(eid)}"><span class="mono-id">${esc(eid)}</span></button></td>
          <td class="mono-id">${esc(e.track)}</td>
          <td><button type="button" class="row-trigger" data-nid="${esc(eid)}"><span class="row-title">${esc(e.title)}</span><span class="row-desc">${esc(e.single_var_diff || e.hypothesis).slice(0, 110)}</span></button></td>
          <td class="metric-cell">${esc(e.cv_summary || (e.cv_score ?? "—"))}</td>
          <td class="metric-cell">${esc(e.test_summary || (e.test_score ?? "—"))}</td>
          <td class="num-col">${delta}</td>
          <td>${statusTag(e.verdict)}</td></tr>`;
      })
      .join("");
    bindInspectTriggers(tbody, h.onInspect);
  }

  function renderLifecycle(state, h) {
    const stages = ["PROPOSED", "DESIGNED", "IMPLEMENTING", "CHALLENGED", "AUDITED", "ARCHIVED"];
    const props = (state.nodes || []).filter((n) => n.node_type === "PROPOSAL");
    const board = document.getElementById("proposal-kanban");
    board.innerHTML = stages
      .map((st, idx) => {
        const items = props.filter((p) => p.status === st);
        const rows = items
          .map((p) => {
            let acts = "";
            if (idx < 3) acts += `<button type="button" class="btn btn-secondary btn-xs" data-prop-adv="${esc(p.id)}" data-next="${stages[idx + 1]}">Sang ${stages[idx + 1]}</button>`;
            if (st !== "AUDITED" && st !== "ARCHIVED") acts += `<button type="button" class="btn btn-primary btn-xs" data-prop-audit="${esc(p.id)}">Duyệt Audit</button>`;
            if (st === "AUDITED") acts += `<button type="button" class="btn btn-primary btn-xs" data-prop-adv="${esc(p.id)}" data-next="ARCHIVED">Lưu trữ</button>`;
            return `<div class="ledger-item-static">
              <button type="button" class="row-trigger" data-nid="${esc(p.id)}">
                <span class="mono-id">${esc(p.id)}</span><span class="row-title">${esc(p.title)}</span>
                <span class="row-desc">${esc(p.summary).slice(0, 96)}</span>
              </button>${acts ? `<div class="row-actions">${acts}</div>` : ""}</div>`;
          })
          .join("");
        return `<div class="ledger-panel"><div class="ledger-header"><h3>${st}</h3><span class="mono-id">${items.length}</span></div>
          <div class="ledger-list">${rows || '<div class="empty-state"><p class="empty-desc">Trống</p></div>'}</div></div>`;
      })
      .join("");
    bindInspectTriggers(board, h.onInspect);
    board.querySelectorAll("[data-prop-adv]").forEach((b) => b.addEventListener("click", () => h.onAdvanceProposal(b.getAttribute("data-prop-adv"), b.getAttribute("data-next"))));
    board.querySelectorAll("[data-prop-audit]").forEach((b) => b.addEventListener("click", () => h.onAuditProposal(b.getAttribute("data-prop-audit"))));

    const ideas = (state.nodes || []).filter((n) => ["IDEA", "ALGORITHM", "OBSERVATION", "KNOWLEDGE_NODE"].includes(n.node_type));
    const grid = document.getElementById("ideas-grid");
    if (ideas.length) {
      grid.innerHTML = ideas.map((n) => `<div role="listitem" class="ledger-panel"><button type="button" class="ledger-row" data-nid="${esc(n.id)}">
        <span class="row-top"><span class="mono-id">${esc(n.id)}</span>${statusTag(n.status, `${n.node_type} / ${n.status}`)}</span>
        <span class="row-title">${esc(n.title)}</span><span class="row-desc">${esc(n.summary).slice(0, 160)}</span></button></div>`).join("");
      bindInspectTriggers(grid, h.onInspect);
    } else {
      grid.innerHTML = `<div role="listitem" class="ledger-panel"><div class="empty-state"><p class="empty-title">Kho Ý tưởng &amp; Insight đang trống</p>
        <div><button type="button" id="cta-empty-idea" class="btn btn-secondary btn-sm">Lưu Idea đầu tiên</button></div></div></div>`;
      document.getElementById("cta-empty-idea").addEventListener("click", h.onOpenIdea);
    }
  }

  function renderEvents(state, h) {
    const nodeSet = new Set((state.nodes || []).map((n) => n.id));
    const box = document.getElementById("events-list");
    const evs = state.events || [];
    box.innerHTML = evs.length
      ? evs.map((ev) => `<div role="listitem" class="ledger-item-static">
          <div class="row-top">
            <span class="mono-id">${esc(ev.event_type)}${ev.entity_id ? ` &middot; ${esc(ev.entity_id)}` : ""}</span>
            <span class="mono-id">${esc((ev.created_at || "").slice(0, 19))}</span>
          </div>
          <div class="row-desc">${esc(ev.summary || "")}</div>
          ${ev.entity_id && nodeSet.has(ev.entity_id) ? `<div><button type="button" class="btn btn-secondary btn-xs" data-nid="${esc(ev.entity_id)}">Mở ${esc(ev.entity_id)}</button></div>` : ""}
        </div>`).join("")
      : `<div role="listitem" class="empty-state"><p class="empty-desc">Chưa có sự kiện hệ thống nào.</p></div>`;
    bindInspectTriggers(box, h.onInspect);
  }

  window.SuperMemoryViews = { renderSkeletons, renderConstitution, renderExperiments, renderLifecycle, renderEvents };
})();
