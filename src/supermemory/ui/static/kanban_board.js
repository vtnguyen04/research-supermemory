// Interactive 4-Column Drag-and-Drop Kanban Board & Compact Linear-Style Task Execution List
(function () {
  const { esc, statusTag, cleanText, tr, paginate, bindPagers } = window.SuperMemoryIcons;
  const { buildKanbanItems, openTaskModal, inspectTaskInDrawer } = window.SuperMemoryKanbanModals;
  const COL_RANK = { IN_PROGRESS: 0, READY: 1, BACKLOG: 2, DONE: 3 };

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
      const workers = (ov.active_workers || []).length ? ov.active_workers.join(", ") : tr("No active workers", "Chưa có worker chạy");
      box.innerHTML = `
        <div class="kanban-kpi-card">
          <div class="pareto-row"><span>${tr("Overall Progress", "Tổng tiến độ")}</span><strong class="kpi-big">${esc(ov.overall_pct ?? 0)}%</strong></div>
          <progress class="pareto-meter kanban-meter" max="100" value="${esc(ov.overall_pct ?? 0)}"></progress>
          <span class="kpi-sub" title="${esc(ov.subtasks_done ?? 0)}/${esc(ov.subtasks_total ?? 0)}">${esc(ov.subtasks_done ?? 0)}/${esc(ov.subtasks_total ?? 0)} ${tr("subtasks done", "bước hoàn thành")}</span>
        </div>
        <div class="kanban-kpi-card">
          <div class="pareto-row"><span>${tr("In Progress", "Đang chạy")}</span><strong class="kpi-big">${esc(ov.in_progress_count ?? 0)}</strong></div>
          <span class="kpi-sub" title="${esc(workers)}">${esc(workers)}</span>
        </div>
        <div class="kanban-kpi-card">
          <div class="pareto-row"><span>${tr("Ready Queue", "Sẵn sàng")}</span><strong class="kpi-big">${esc(ov.ready_count ?? 0)}</strong></div>
          <span class="kpi-sub">${esc(leases)} ${tr("glob leases", "khóa file")}</span>
        </div>
        <div class="kanban-kpi-card">
          <div class="pareto-row"><span>${tr("Done / Waiting", "Xong / Chờ")}</span><strong class="kpi-big">${esc(ov.done_count ?? 0)} / ${esc(ov.backlog_count ?? 0)}</strong></div>
          <span class="kpi-sub">${ov.halted_count ? `${esc(ov.halted_count)} ${tr("halted", "dừng sớm")}` : tr("Completed vs blocked", "Đã xong vs chờ phụ thuộc")}</span>
        </div>`;
    }

    _actionBtn(it) {
      if (it.col === "IN_PROGRESS") return `<button type="button" class="btn btn-primary btn-xs" data-kmove="DONE" data-kid="${esc(it.id)}" data-kkind="${it.kind}">${tr("Done", "Xong")}</button>`;
      if (it.col === "DONE") return `<button type="button" class="btn btn-ghost btn-xs" data-kmove="READY" data-kid="${esc(it.id)}" data-kkind="${it.kind}">${tr("Requeue", "Chạy lại")}</button>`;
      return `<button type="button" class="btn btn-secondary btn-xs" data-kmove="IN_PROGRESS" data-kid="${esc(it.id)}" data-kkind="${it.kind}">${tr("Start", "Bắt đầu")}</button>`;
    }

    render(state) {
      const mount = document.getElementById("kanban-stage-mount");
      if (!mount) return;
      document.querySelectorAll("[data-kview]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.kview === this.viewMode)));
      this._renderKpis(state);

      const all = buildKanbanItems(state).sort((a, b) => (COL_RANK[a.col] ?? 9) - (COL_RANK[b.col] ?? 9) || String(b.updatedAt).localeCompare(String(a.updatedAt)) || String(b.id).localeCompare(String(a.id)));
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
            const nxtIdx = it.steps.findIndex((s) => !s.done), pIdx = nxtIdx >= 0 ? nxtIdx : 0, pStep = it.steps[pIdx];
            const stepHtml = pStep ? `<label class="subtask-row subtask-single ${pStep.done ? "is-done" : ""}" title="${esc(pStep.text)}">
              <input type="checkbox" data-step-chk="${pIdx}" data-step-id="${esc(it.id)}" data-step-kind="${it.kind}" ${pStep.done ? "checked" : ""} /><span>${esc(pStep.text)}</span></label>` : "";
            const chipTxt = it.wave ? `W${it.wave} · ${it.badge}` : it.badge, dispTitle = cleanText(it.title, 72);
            return `<article class="kanban-card" draggable="true" data-drag-id="${esc(it.id)}" data-drag-kind="${it.kind}" data-task-id="${esc(it.id)}">
              <div class="row-top"><span class="badge-cluster"><span class="mono-id">${esc(it.id)}</span>${statusTag(it.status)}</span>${chipTxt ? `<span class="role-chip" title="${esc(chipTxt)}">${esc(chipTxt)}</span>` : ""}</div>
              <h4 class="kanban-card-title" title="${esc(it.title)}" data-open-id="${esc(it.id)}" data-open-kind="${it.kind}">${esc(dispTitle)}</h4>
              <div class="pareto-row"><span>${it.stepsDone}/${it.stepsTotal} ${tr("steps", "bước")}</span><strong>${it.pct}%</strong></div>
              <progress class="pareto-meter kanban-meter" max="100" value="${it.pct}"></progress>
              ${stepHtml ? `<div class="subtask-list subtask-compact">${stepHtml}</div>` : ""}
              <div class="row-actions"><button type="button" class="btn btn-secondary btn-xs" data-open-id="${esc(it.id)}" data-open-kind="${it.kind}">${tr("Details", "Chi tiết")}</button>${this._actionBtn(it)}</div>
            </article>`;
          }).join("") : `<div class="kanban-empty">${tr("Drop task here or create new", "Kéo thả tác vụ vào cột này")}</div>`;
          return `<section class="kanban-col" data-kcol="${cKey}" aria-label="${esc(cTitle)}"><header class="kanban-col-head"><h3>${esc(cTitle)}</h3><span class="nav-count">${cItems.length}</span></header><div class="kanban-col-body">${cards}</div></section>`;
        }).join("")}</div>`;
      } else {
        const pg = paginate(items, `klist-${this.sourceFilter}`, 10);
        mount.innerHTML = items.length ? `<div class="surface-card task-list-panel">${pg.slice.map((it) => {
          const chipLbl = it.wave ? `W${it.wave} · ${it.badge}` : (it.badge || it.kind), dispTitle = cleanText(it.title, 78);
          const nxt = it.steps.find((s) => !s.done);
          const subLine = (nxt ? `${tr("Next", "Tiếp")}: ${cleanText(nxt.text, 88)}` : cleanText(it.summary, 92)) || "—";
          return `<div class="task-list-row" data-task-id="${esc(it.id)}">
            <div class="tlist-id"><span class="mono-id">${esc(it.id)}</span>${statusTag(it.status)}</div>
            <button type="button" class="tlist-main" data-open-id="${esc(it.id)}" data-open-kind="${it.kind}" title="${esc(it.title)}">
              <span class="tlist-title">${esc(dispTitle)}</span>
              <span class="tlist-sub">${esc(subLine)}</span>
            </button>
            <span class="role-chip tlist-chip" title="${esc(chipLbl)}">${esc(chipLbl)}</span>
            <div class="tlist-prog"><progress class="pareto-meter kanban-meter" max="100" value="${it.pct}"></progress><span class="mono-id">${it.stepsDone}/${it.stepsTotal}</span></div>
            <div class="tlist-acts">${this._actionBtn(it)}<button type="button" class="btn btn-secondary btn-xs" data-open-id="${esc(it.id)}" data-open-kind="${it.kind}">${tr("Details", "Chi tiết")}</button></div>
          </div>`;
        }).join("")}${pg.html}</div>` : `<div class="surface-card empty-state"><p class="empty-desc">${tr("No matching tasks or proposals.", "Không tìm thấy tác vụ phù hợp.")}</p></div>`;
      }
      bindPagers(mount, () => this.render(this.ctx.getState()));
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
      mount.querySelectorAll("[draggable='true']").forEach((card) => {
        card.addEventListener("dragstart", (ev) => {
          this.dragItem = { id: card.dataset.dragId, kind: card.dataset.dragKind };
          card.classList.add("is-dragging");
          ev.dataTransfer?.setData("text/plain", card.dataset.dragId);
        });
        card.addEventListener("dragend", () => { this.dragItem = null; card.classList.remove("is-dragging"); });
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
