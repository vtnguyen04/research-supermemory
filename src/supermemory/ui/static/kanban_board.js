// Interactive 4-Column Drag-and-Drop Kanban Board & Granular Task Execution List
(function () {
  const { esc, statusTag, inlineMd, tr } = window.SuperMemoryIcons;
  const { buildKanbanItems, openTaskModal, inspectTaskInDrawer } = window.SuperMemoryKanbanModals;

  class KanbanBoardController {
    constructor(ctx) {
      this.ctx = ctx;
      this.viewMode = localStorage.getItem("sm_kanban_view") === "LIST" ? "LIST" : "BOARD";
      this.sourceFilter = "ALL";
      this.dragItem = null;
      this._bindChrome();
    }

    _bindChrome() {
      const on = (id, ev, fn) => document.getElementById(id)?.addEventListener(ev, fn);
      on("btn-new-kanban-task", "click", () => openTaskModal(this.ctx.modals, this.ctx.postJson, this.ctx.onRefresh, this.ctx.notify, this.ctx.getState()));
      on("btn-kanban-sprint", "click", () => this.ctx.onOpenSprint());
      on("btn-kanban-clear-done", "click", async () => {
        try { const r = await this.ctx.postJson("/api/orchestrate", { action: "clear_done" }); this.ctx.notify(tr(`Cleared ${r.cleared || 0} finished tasks`, `Đã dọn ${r.cleared || 0} tác vụ xong`)); await this.ctx.onRefresh(); }
        catch (err) { this.ctx.notify(err.message, true); }
      });
      on("kanban-filter-input", "input", () => this.render(this.ctx.getState()));
      document.querySelectorAll("[data-kview]").forEach((btn) => btn.addEventListener("click", () => {
        this.viewMode = btn.dataset.kview;
        localStorage.setItem("sm_kanban_view", this.viewMode);
        this.render(this.ctx.getState());
      }));
    }

    inspectTask(taskId) { inspectTaskInDrawer(this.ctx, taskId); }

    async _moveItem(kind, id, targetCol) {
      try {
        if (kind === "PROPOSAL") {
          const prop = (this.ctx.getState().nodes || []).find((n) => n.id === id);
          if (targetCol === "DONE" && !(prop?.metadata?.audits || []).length) {
            await this.ctx.postJson("/api/proposals", { action: "audit", proposal_id: id, verdict: "APPROVE" });
          } else {
            const map = { BACKLOG: "PROPOSED", READY: "DESIGNED", IN_PROGRESS: "IMPLEMENTING", DONE: "ARCHIVED" };
            await this.ctx.postJson("/api/proposals", { action: "advance", proposal_id: id, new_stage: map[targetCol] || "IMPLEMENTING" });
          }
        } else {
          await this.ctx.postJson("/api/orchestrate", { action: "move", task_id: id, target_stage: targetCol });
        }
        await this.ctx.onRefresh();
      } catch (err) { this.ctx.notify(err.message, true); }
    }

    _renderKpis(state) {
      const ov = state.execution_overview || {}, leases = (state.dag_telemetry?.active_glob_leases || []).length;
      const box = document.getElementById("kanban-kpi-grid");
      if (!box) return;
      const workers = (ov.active_workers || []).length ? ov.active_workers.join(", ") : tr("No active workers", "Chưa có worker đang chạy");
      box.innerHTML = `
        <div class="kanban-kpi-card">
          <div class="pareto-row"><span>${tr("Overall Progress", "Tổng tiến độ công việc")}</span><strong class="kpi-big">${esc(ov.overall_pct ?? 0)}%</strong></div>
          <progress class="pareto-meter kanban-meter" max="100" value="${esc(ov.overall_pct ?? 0)}"></progress>
          <span class="kpi-sub">${esc(ov.subtasks_done ?? 0)}/${esc(ov.subtasks_total ?? 0)} ${tr("subtasks completed", "bước con hoàn thành")}</span>
        </div>
        <div class="kanban-kpi-card">
          <div class="pareto-row"><span>${tr("In Progress", "Đang thực hiện")}</span><strong class="kpi-big">${esc(ov.in_progress_count ?? 0)}</strong></div>
          <span class="kpi-sub">${esc(workers)}</span>
        </div>
        <div class="kanban-kpi-card">
          <div class="pareto-row"><span>${tr("Ready Queue", "Sẵn sàng thực thi")}</span><strong class="kpi-big">${esc(ov.ready_count ?? 0)}</strong></div>
          <span class="kpi-sub">${esc(leases)} ${tr("active file-glob leases", "khóa vùng file đang giữ")}</span>
        </div>
        <div class="kanban-kpi-card">
          <div class="pareto-row"><span>${tr("Done / Waiting", "Hoàn tất / Đang chờ")}</span><strong class="kpi-big">${esc(ov.done_count ?? 0)} / ${esc(ov.backlog_count ?? 0)}</strong></div>
          <span class="kpi-sub">${ov.halted_count ? `${esc(ov.halted_count)} ${tr("early-killed / halted", "dừng sớm")}` : tr("Completed vs dependency-blocked", "Đã xong vs chờ phụ thuộc")}</span>
        </div>`;
    }

    render(state) {
      const mount = document.getElementById("kanban-stage-mount");
      if (!mount) return;
      document.querySelectorAll("[data-kview]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.kview === this.viewMode)));
      this._renderKpis(state);

      const all = buildKanbanItems(state);
      const q = (document.getElementById("kanban-filter-input")?.value || "").trim().toLowerCase();
      const sBar = document.getElementById("kanban-source-bar");
      const tabs = [
        ["ALL", `${tr("All", "Tất cả")} (${all.length})`],
        ["ACTIVE", `${tr("Active", "Đang mở")} (${all.filter((x) => x.col !== "DONE").length})`],
        ["TASK", `${tr("Agent Tasks", "Tác vụ")} (${all.filter((x) => x.kind === "TASK").length})`],
        ["PROPOSAL", `Proposals (${all.filter((x) => x.kind === "PROPOSAL").length})`],
      ];
      sBar.innerHTML = tabs.map(([k, lbl]) => `<button type="button" class="seg-btn" aria-pressed="${this.sourceFilter === k}" data-ksrc="${k}">${esc(lbl)}</button>`).join("");
      sBar.querySelectorAll("[data-ksrc]").forEach((b) => b.addEventListener("click", () => { this.sourceFilter = b.dataset.ksrc; this.render(this.ctx.getState()); }));

      const items = all.filter((it) => {
        if (this.sourceFilter === "ACTIVE" && it.col === "DONE") return false;
        if ((this.sourceFilter === "TASK" || this.sourceFilter === "PROPOSAL") && it.kind !== this.sourceFilter) return false;
        return !q || `${it.id} ${it.title} ${it.summary} ${it.badge} ${it.worker} ${it.targetId}`.toLowerCase().includes(q);
      });

      if (this.viewMode === "BOARD") {
        const cols = [
          ["BACKLOG", tr("Backlog / Blocked", "Chờ phụ thuộc")],
          ["READY", tr("Ready", "Sẵn sàng")],
          ["IN_PROGRESS", tr("In Progress", "Đang thực hiện")],
          ["DONE", tr("Done / Halted", "Hoàn tất / Dừng")],
        ];
        mount.innerHTML = `<div class="kanban-board">${cols.map(([cKey, cTitle]) => {
          const cItems = items.filter((x) => x.col === cKey);
          const cards = cItems.length ? cItems.map((it) => {
            const stepsHtml = it.steps.slice(0, 3).map((s, idx) => `<label class="subtask-row ${s.done ? "is-done" : ""}">
              <input type="checkbox" data-step-chk="${idx}" data-step-id="${esc(it.id)}" data-step-kind="${it.kind}" ${s.done ? "checked" : ""} /><span>${esc(s.text)}</span></label>`).join("");
            const more = it.steps.length > 3 ? `<span class="subtask-more">+${it.steps.length - 3} ${tr("more", "bước nữa")}</span>` : "";
            const actBtn = cKey === "IN_PROGRESS"
              ? `<button type="button" class="btn btn-primary btn-xs" data-kmove="DONE" data-kid="${esc(it.id)}" data-kkind="${it.kind}">${tr("Done", "Hoàn tất")}</button>`
              : cKey === "DONE"
                ? `<button type="button" class="btn btn-ghost btn-xs" data-kmove="READY" data-kid="${esc(it.id)}" data-kkind="${it.kind}">${tr("Requeue", "Chạy lại")}</button>`
                : `<button type="button" class="btn btn-secondary btn-xs" data-kmove="IN_PROGRESS" data-kid="${esc(it.id)}" data-kkind="${it.kind}">${tr("Start", "Bắt đầu")}</button>`;
            return `<article class="kanban-card" draggable="true" data-drag-id="${esc(it.id)}" data-drag-kind="${it.kind}" data-task-id="${esc(it.id)}">
              <div class="row-top"><span class="badge-cluster"><span class="mono-id">${esc(it.id)}</span>${statusTag(it.status)}</span><span class="role-chip">${esc(it.wave ? `W${it.wave} · ${it.badge}` : it.badge)}</span></div>
              <h4 class="kanban-card-title" data-open-id="${esc(it.id)}" data-open-kind="${it.kind}">${esc(it.title)}</h4>
              <div class="pareto-row"><span>${it.stepsDone}/${it.stepsTotal} ${tr("steps", "bước")}</span><strong>${it.pct}%</strong></div>
              <progress class="pareto-meter kanban-meter" max="100" value="${it.pct}"></progress>
              ${stepsHtml ? `<div class="subtask-list subtask-compact">${stepsHtml}${more}</div>` : ""}
              ${(it.worker || it.targetId || it.deps.length) ? `<div class="dag-meta-row">${it.worker ? `<span class="mono-tag">${esc(it.worker)}</span>` : ""}${it.targetId ? `<span class="mono-tag">${esc(it.targetId)}</span>` : ""}${it.deps.length ? `<span class="mono-tag">${tr("Deps", "Chờ")}: ${esc(it.deps.join(","))}</span>` : ""}</div>` : ""}
              <div class="row-actions"><button type="button" class="btn btn-secondary btn-xs" data-open-id="${esc(it.id)}" data-open-kind="${it.kind}">${tr("Details", "Chi tiết")}</button>${actBtn}</div>
            </article>`;
          }).join("") : `<div class="kanban-empty">${tr("Drop task here or create new", "Kéo thả tác vụ vào cột này")}</div>`;
          return `<section class="kanban-col" data-kcol="${cKey}" aria-label="${esc(cTitle)}"><header class="kanban-col-head"><h3>${esc(cTitle)}</h3><span class="nav-count">${cItems.length}</span></header><div class="kanban-col-body">${cards}</div></section>`;
        }).join("")}</div>`;
      } else {
        mount.innerHTML = items.length ? `<div class="task-list-stack">${items.map((it) => {
          const allSteps = it.steps.map((s, idx) => `<label class="subtask-row ${s.done ? "is-done" : ""}">
            <input type="checkbox" data-step-chk="${idx}" data-step-id="${esc(it.id)}" data-step-kind="${it.kind}" ${s.done ? "checked" : ""} /><span>${esc(s.text)}</span></label>`).join("");
          return `<article class="surface-card task-list-card" data-task-id="${esc(it.id)}">
            <div class="row-top">
              <span class="badge-cluster"><span class="mono-id">${esc(it.id)}</span>${statusTag(it.status)}<span class="role-chip">${esc(it.wave ? `Wave ${it.wave} · ${it.badge}` : it.badge)}</span>${it.worker ? `<span class="mono-tag">Worker: ${esc(it.worker)}</span>` : ""}${it.globs.length ? `<span class="mono-tag">Lease: ${esc(it.globs.join(", "))}</span>` : ""}</span>
              <div class="row-actions">
                <strong class="mono-tag">${it.stepsDone}/${it.stepsTotal} &middot; ${it.pct}%</strong>
                ${it.col !== "IN_PROGRESS" ? `<button type="button" class="btn btn-secondary btn-xs" data-kmove="IN_PROGRESS" data-kid="${esc(it.id)}" data-kkind="${it.kind}">${tr("Start", "Bắt đầu")}</button>` : ""}
                ${it.col !== "DONE" ? `<button type="button" class="btn btn-primary btn-xs" data-kmove="DONE" data-kid="${esc(it.id)}" data-kkind="${it.kind}">${tr("Mark Done", "Hoàn tất")}</button>` : `<button type="button" class="btn btn-ghost btn-xs" data-kmove="READY" data-kid="${esc(it.id)}" data-kkind="${it.kind}">${tr("Requeue", "Chạy lại")}</button>`}
                <button type="button" class="btn btn-secondary btn-xs" data-open-id="${esc(it.id)}" data-open-kind="${it.kind}">${tr("Inspect", "Chi tiết")}</button>
              </div>
            </div>
            <h3 class="row-title">${esc(it.title)}</h3>
            <p class="row-desc">${inlineMd(it.summary)}</p>
            <progress class="pareto-meter kanban-meter" max="100" value="${it.pct}"></progress>
            <div class="subtask-list task-list-grid">${allSteps}</div>
            <form class="step-add-row" data-list-step-form="${esc(it.id)}" data-list-step-kind="${it.kind}" novalidate>
              <input class="control-input" name="step_txt" placeholder="${tr("Add a checklist subtask...", "Thêm bước thực thi con...")}" />
              <button type="submit" class="btn btn-secondary btn-xs">+ ${tr("Add Step", "Thêm bước")}</button>
            </form>
          </article>`;
        }).join("")}</div>` : `<div class="surface-card empty-state"><p class="empty-desc">${tr("No matching tasks or proposals. Create a new task or plan a 3-Wave Sprint.", "Không tìm thấy tác vụ phù hợp. Hãy tạo Task mới hoặc lập Sprint 3-Wave.")}</p></div>`;
      }
      this._bindStageEvents(mount);
    }

    _bindStageEvents(mount) {
      mount.querySelectorAll("[data-open-id]").forEach((el) => el.addEventListener("click", () => {
        if (el.dataset.openKind === "PROPOSAL") this.ctx.onInspectNode(el.dataset.openId);
        else this.inspectTask(el.dataset.openId);
      }));
      mount.querySelectorAll("[data-kmove]").forEach((b) => b.addEventListener("click", () => this._moveItem(b.dataset.kkind, b.dataset.kid, b.dataset.kmove)));
      mount.querySelectorAll("[data-step-chk]").forEach((chk) => chk.addEventListener("change", async () => {
        try { await this.ctx.postJson("/api/orchestrate", { action: "toggle_step", kind: chk.dataset.stepKind, item_id: chk.dataset.stepId, step_idx: Number(chk.dataset.stepChk), done: chk.checked }); await this.ctx.onRefresh(); }
        catch (err) { this.ctx.notify(err.message, true); }
      }));
      mount.querySelectorAll("[data-list-step-form]").forEach((frm) => frm.addEventListener("submit", async (ev) => {
        ev.preventDefault(); const inp = frm.querySelector("input"), val = inp.value.trim(); if (!val) return;
        try { await this.ctx.postJson("/api/orchestrate", { action: "add_step", kind: frm.dataset.listStepKind, item_id: frm.dataset.listStepForm, text: val }); await this.ctx.onRefresh(); }
        catch (err) { this.ctx.notify(err.message, true); }
      }));
      mount.querySelectorAll("[draggable='true']").forEach((card) => {
        card.addEventListener("dragstart", (ev) => {
          this.dragItem = { id: card.dataset.dragId, kind: card.dataset.dragKind };
          card.classList.add("is-dragging");
          ev.dataTransfer?.setData("text/plain", card.dataset.dragId);
        });
        card.addEventListener("dragend", () => card.classList.remove("is-dragging"));
      });
      mount.querySelectorAll("[data-kcol]").forEach((col) => {
        col.addEventListener("dragover", (ev) => { ev.preventDefault(); col.classList.add("is-drag-over"); });
        col.addEventListener("dragleave", (ev) => { if (!col.contains(ev.relatedTarget)) col.classList.remove("is-drag-over"); });
        col.addEventListener("drop", (ev) => {
          ev.preventDefault(); col.classList.remove("is-drag-over");
          if (this.dragItem) { const { kind, id } = this.dragItem; this.dragItem = null; this._moveItem(kind, id, col.dataset.kcol); }
        });
      });
    }
  }

  window.SuperMemoryKanbanBoard = { KanbanBoardController };
})();
