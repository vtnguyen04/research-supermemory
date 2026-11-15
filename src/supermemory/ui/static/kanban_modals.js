// Kanban Item Adapter, Task Creation/Edit Modal & 3-Mode Task Inspector
(function () {
  const { esc, statusTag, tr, renderMarkdown, inlineMd, svg } = window.SuperMemoryIcons;
  const fld = (n, lbl, ctrl) => `<div class="field-group"><label for="kb-${n}" class="field-label">${lbl}</label>${ctrl}</div>`;
  const inp = (n, val = "", ph = "") => `<input id="kb-${n}" name="${n}" class="control-input" value="${esc(val)}" placeholder="${esc(ph)}" />`;
  const area = (n, val = "", rows = 3, ph = "") => `<textarea id="kb-${n}" name="${n}" class="control-textarea" rows="${rows}" placeholder="${esc(ph)}">${esc(val)}</textarea>`;
  const row2 = (a, b) => `<div class="form-row-2">${a}${b}</div>`;
  const sel = (n, opts, cur = "") => `<select id="kb-${n}" name="${n}" class="control-select">${opts.map(([v, l]) => `<option value="${esc(v)}" ${String(v) === String(cur) ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>`;

  const ROLES = [
    ["bottleneck-profiler", "bottleneck-profiler"], ["sota-scout", "sota-scout"], ["memory-curator", "memory-curator"],
    ["hypothesis-architect", "hypothesis-architect"], ["experiment-challenger", "experiment-challenger"],
    ["slice-builder", "slice-builder"], ["code-reviewer", "code-reviewer"], ["test-engineer", "test-engineer"], ["self", "self / general"],
  ];

  function buildKanbanItems(state) {
    const tasks = (state.agent_tasks || []).map((t) => ({
      kind: "TASK", id: t.task_id, col: t.kanban_col || "BACKLOG", status: t.status || "QUEUED",
      title: t.title, summary: t.brief || "", badge: t.role || "self", wave: Number(t.wave) || 1,
      worker: t.claimed_by || "", deps: t.depends_on || [], globs: t.locked_globs || [],
      targetId: t.target_id || "", smokeGate: t.smoke_gate || "", steps: t.steps || [],
      stepsDone: t.steps_done ?? 0, stepsTotal: t.steps_total ?? (t.steps || []).length,
      pct: t.progress_pct ?? 0, updatedAt: t.updated_at || "", raw: t,
    }));
    const props = (state.nodes || []).filter((n) => n.node_type === "PROPOSAL" && n.status !== "ARCHIVED").map((n) => {
      const md = n.metadata || {}, rawT = md.tasks || [], done = md.tasks_done || [];
      const steps = rawT.map((txt, i) => ({ text: txt, done: Boolean(done[i]) }));
      const roi = Number(md.occam_roi);
      return {
        kind: "PROPOSAL", id: n.id, col: md.kanban_col || "BACKLOG", status: n.status || "PROPOSED",
        title: n.title, summary: n.summary || "", badge: roi > 0 ? `ROI ${roi}` : "", wave: 0,
        worker: (md.audits || []).length ? "audited" : "", deps: [], globs: [],
        targetId: md.bottleneck_id || "", smokeGate: md.kill_criterion || "", steps,
        stepsDone: steps.filter((s) => s.done).length, stepsTotal: steps.length,
        pct: md.progress_pct ?? 0, updatedAt: n.updated_at || "", raw: n,
      };
    });
    return [...tasks, ...props];
  }

  function openTaskModal(modals, postJson, onRefresh, notify, state, ex = null) {
    const bnks = (state.bottlenecks || []).filter((b) => b.status !== "RESOLVED");
    const stepTxt = ex ? (ex.steps || []).map((s) => s.text).join("\n") : "";
    const html = fld("title", tr("Task Title *", "Tên tác vụ *"), inp("title", ex?.title || "", tr("e.g. Implement hybrid ranker ablation", "Ví dụ: Thực thi kiểm chứng nhánh Hybrid Ranker"))) +
      row2(fld("role", tr("Agent / Owner Role", "Vai trò thực thi"), sel("role", ROLES, ex?.role || "slice-builder")),
           fld("wave", tr("Execution Wave", "Đợt thực thi (Wave)"), sel("wave", [["1", "Wave 1 · Discovery"], ["2", "Wave 2 · Gate & Spec"], ["3", "Wave 3 · Execution"]], ex?.wave || 1))) +
      row2(fld("bottleneck_id", tr("Target Bottleneck ID", "Mã Bottleneck đích"), inp("bottleneck_id", ex?.target_id || bnks[0]?.id || "", "BNK-001")),
           fld("depends_on", tr("Depends On (comma-separated)", "Phụ thuộc các mã Task"), inp("depends_on", (ex?.depends_on || []).join(", "), "DAG-001, DAG-002"))) +
      row2(fld("locked_globs", tr("File Glob Leases", "Khóa vùng file (Globs)"), inp("locked_globs", (ex?.locked_globs || []).join(", "), "src/supermemory/**")),
           fld("smoke_cmd", tr("10% Smoke Command", "Lệnh kiểm tra nhanh 10%"), inp("smoke_cmd", ex?.smoke_gate || "pytest -q"))) +
      fld("brief", tr("Task Brief & Acceptance Criteria", "Mô tả chi tiết & Tiêu chí hoàn thành"), area("brief", ex?.brief || "", 2)) +
      fld("steps", tr("Subtask Checklist (1 step per line)", "Danh sách việc con (mỗi dòng 1 bước)"), area("steps", stepTxt, 3, tr("Profile baseline\nImplement single-variable slice\nVerify tests & log metrics", "Đo baseline\nViết code thay đổi đơn biến\nChạy test & lưu kết quả")));
    modals.open(ex ? tr(`Edit Task ${ex.task_id}`, `Chỉnh sửa tác vụ ${ex.task_id}`) : tr("Create Execution Task", "Tạo Tác vụ Mới trên Kanban"), html, async (fd) => {
      if (!fd.title.trim()) throw new Error(tr("Task title is required.", "Vui lòng nhập tên tác vụ."));
      const res = await postJson("/api/orchestrate", { action: ex ? "update" : "enqueue", task_id: ex?.task_id || "", ...fd });
      notify(tr(`Saved ${res.task.task_id}`, `Đã lưu ${res.task.task_id}`));
      await onRefresh();
    });
  }

  function inspectTaskInDrawer(ctx, taskId) {
    const t = (ctx.getState().agent_tasks || []).find((x) => x.task_id === taskId);
    if (!t) { ctx.inspector.close(); return; }
    ctx.inspector.currentNodeId = `TASK:${t.task_id}`;
    ctx.inspector._openChrome(`WAVE ${t.wave} / ${t.role}`, `${t.task_id} — ${t.title}`);
    const steps = t.steps || [], pct = t.progress_pct ?? 0;
    const stepRows = steps.map((s, idx) => `<label class="subtask-row ${s.done ? "is-done" : ""}">
      <input type="checkbox" data-insp-step="${idx}" ${s.done ? "checked" : ""} /><span>${esc(s.text)}</span></label>`).join("");
    const depBtns = (t.depends_on || []).map((d) => `<button type="button" class="btn btn-secondary btn-xs" data-jump-task="${esc(d)}">${esc(d)}</button>`).join(" ") || "—";
    const bnkBtn = t.target_id ? `<button type="button" class="btn btn-secondary btn-xs" data-jump-node="${esc(t.target_id)}">${esc(t.target_id)}</button>` : "—";

    document.getElementById("insp-body").innerHTML = `
      <div class="row-actions">
        <button type="button" id="btn-edit-task" class="btn btn-primary btn-sm">${tr("Edit Task", "Sửa Task")}</button>
        <button type="button" id="btn-expand-center" class="btn btn-secondary btn-sm">${svg("maximize", 13)} ${ctx.inspector.mode === "center" ? tr("Dock to Side (F)", "Thu về cạnh phải (F)") : tr("Expand to Center (F)", "Phóng to giữa màn (F)")}</button>
        ${t.status !== "RUNNING" ? `<button type="button" class="btn btn-secondary btn-sm" data-insp-move="IN_PROGRESS">${tr("Start", "Bắt đầu")}</button>` : ""}
        ${t.status !== "DONE" ? `<button type="button" class="btn btn-secondary btn-sm" data-insp-move="DONE">${tr("Mark Done", "Hoàn tất")}</button>` : ""}
        ${t.status !== "QUEUED" ? `<button type="button" class="btn btn-ghost btn-sm" data-insp-move="READY">${tr("Requeue", "Đưa về chờ")}</button>` : ""}
        ${t.status === "RUNNING" ? `<button type="button" class="btn btn-danger btn-sm" data-insp-move="EARLY_KILLED">${tr("10% Early-Kill", "Dừng sớm 10%")}</button>` : ""}
        <span id="insp-task-del"><button type="button" id="btn-arm-del-task" class="btn btn-danger btn-sm">${tr("Delete", "Xóa")}</button></span>
      </div>
      <div class="prop-grid">
        <span class="prop-key">${tr("Task ID", "Mã tác vụ")}</span><span class="prop-val">${esc(t.task_id)} &middot; Wave ${esc(t.wave)}</span>
        <span class="prop-key">${tr("Agent Role", "Vai trò")}</span><span class="prop-val"><code class="md-code">${esc(t.role)}</code>${t.claimed_by ? ` (${esc(t.claimed_by)})` : ""}</span>
        <span class="prop-key">${tr("Status", "Trạng thái")}</span><span>${statusTag(t.status)}</span>
        <span class="prop-key">${tr("Progress", "Tiến độ")}</span><span class="prop-val">${esc(t.steps_done ?? 0)}/${esc(steps.length)} (${esc(pct)}%)</span>
        <span class="prop-key">${tr("Depends On", "Phụ thuộc")}</span><span>${depBtns}</span>
        <span class="prop-key">${tr("Target BNK", "Điểm nghẽn")}</span><span>${bnkBtn}</span>
        <span class="prop-key">${tr("Glob Lease", "Khóa file")}</span><span class="prop-val">${(t.locked_globs || []).length ? `<code class="md-code">${esc(t.locked_globs.join(", "))}</code>` : "—"}</span>
        ${t.smoke_gate ? `<span class="prop-key">Smoke Gate</span><span class="prop-val"><code class="md-code">${esc(t.smoke_gate)}</code></span>` : ""}
      </div>
      <div class="inspector-section">
        <div class="pareto-row"><h3 class="inspector-subhead">${tr("Subtask Checklist", "Danh sách việc con")}</h3><span>${esc(pct)}%</span></div>
        <progress class="pareto-meter kanban-meter" max="100" value="${esc(pct)}"></progress>
        <div class="subtask-list">${stepRows}</div>
        <form id="insp-add-step-form" class="step-add-row" novalidate>
          <input id="insp-new-step" class="control-input" placeholder="${tr("Add a new subtask step...", "Thêm một bước công việc con...")}" />
          <button type="submit" class="btn btn-secondary btn-sm">+ ${tr("Add", "Thêm")}</button>
        </form>
      </div>
      <div class="inspector-section"><h3 class="inspector-subhead">${tr("Brief & Execution Notes", "Mô tả nhiệm vụ & Ghi chú")}</h3>
        <article class="md-prose">${renderMarkdown(t.brief || tr("No additional brief.", "Chưa có mô tả bổ sung."), true)}</article>
        ${t.receipt?.note ? `<p class="row-desc">${inlineMd(t.receipt.note)}</p>` : ""}
      </div>`;

    const body = document.getElementById("insp-body");
    document.getElementById("btn-edit-task").addEventListener("click", () => openTaskModal(ctx.modals, ctx.postJson, ctx.onRefresh, ctx.notify, ctx.getState(), t));
    document.getElementById("btn-expand-center").addEventListener("click", () => { ctx.inspector.toggleCenter(); inspectTaskInDrawer(ctx, t.task_id); });
    body.querySelectorAll("[data-insp-move]").forEach((b) => b.addEventListener("click", async () => {
      try { await ctx.postJson("/api/orchestrate", { action: "move", task_id: t.task_id, target_stage: b.dataset.inspMove }); await ctx.onRefresh(); } catch (err) { ctx.notify(err.message, true); }
    }));
    body.querySelectorAll("[data-insp-step]").forEach((chk) => chk.addEventListener("change", async () => {
      try { await ctx.postJson("/api/orchestrate", { action: "toggle_step", kind: "TASK", item_id: t.task_id, step_idx: Number(chk.dataset.inspStep), done: chk.checked }); await ctx.onRefresh(); } catch (err) { ctx.notify(err.message, true); }
    }));
    document.getElementById("insp-add-step-form").addEventListener("submit", async (ev) => {
      ev.preventDefault(); const v = document.getElementById("insp-new-step").value.trim(); if (!v) return;
      try { await ctx.postJson("/api/orchestrate", { action: "add_step", kind: "TASK", item_id: t.task_id, text: v }); await ctx.onRefresh(); } catch (err) { ctx.notify(err.message, true); }
    });
    body.querySelectorAll("[data-jump-task]").forEach((b) => b.addEventListener("click", () => inspectTaskInDrawer(ctx, b.dataset.jumpTask)));
    body.querySelectorAll("[data-jump-node]").forEach((b) => b.addEventListener("click", () => ctx.onInspectNode(b.dataset.jumpNode)));
    const bindDel = () => document.getElementById("btn-arm-del-task")?.addEventListener("click", () => {
      const z = document.getElementById("insp-task-del");
      z.innerHTML = `<button type="button" id="btn-ok-del-task" class="btn btn-danger btn-sm">${tr("Confirm", "Xác nhận")}</button><button type="button" id="btn-no-del-task" class="btn btn-ghost btn-sm">${tr("Cancel", "Hủy")}</button>`;
      document.getElementById("btn-no-del-task").addEventListener("click", () => { z.innerHTML = `<button type="button" id="btn-arm-del-task" class="btn btn-danger btn-sm">${tr("Delete", "Xóa")}</button>`; bindDel(); });
      document.getElementById("btn-ok-del-task").addEventListener("click", async () => {
        try { await ctx.postJson("/api/orchestrate", { action: "delete", task_id: t.task_id }); ctx.inspector.resetEmpty(); ctx.notify(tr(`Deleted ${t.task_id}`, `Đã xóa ${t.task_id}`)); await ctx.onRefresh(); } catch (err) { ctx.notify(err.message, true); }
      });
    });
    bindDel();
  }

  function renderProposalChecklist(node) {
    if (node?.node_type !== "PROPOSAL") return "";
    const md = node.metadata || {}, rawT = md.tasks || [], done = md.tasks_done || [];
    const finished = ["AUDITED", "ARCHIVED"].includes(node.status);
    const steps = rawT.map((txt, i) => ({ text: txt, done: finished || Boolean(done[i]) }));
    const sDone = steps.filter((s) => s.done).length, pct = finished ? 100 : (steps.length ? Math.round((sDone / steps.length) * 100) : 0);
    const rows = steps.map((s, idx) => `<label class="subtask-row ${s.done ? "is-done" : ""}"><input type="checkbox" data-prop-step="${idx}" ${s.done ? "checked" : ""} /><span>${esc(s.text)}</span></label>`).join("");
    return `<div class="inspector-section">
      <div class="pareto-row"><h3 class="inspector-subhead">${tr("Implementation Checklist", "Danh sách bước triển khai")}</h3><span>${sDone}/${steps.length} &middot; ${pct}%</span></div>
      <progress class="pareto-meter kanban-meter" max="100" value="${pct}"></progress>
      <div class="subtask-list">${rows || `<p class="empty-desc">${tr("No checklist steps yet.", "Chưa có bước thực thi con.")}</p>`}</div>
      <form id="insp-prop-step-form" class="step-add-row" novalidate>
        <input id="insp-prop-new-step" class="control-input" placeholder="${tr("Add implementation step...", "Thêm bước triển khai...")}" />
        <button type="submit" class="btn btn-secondary btn-sm">+ ${tr("Add", "Thêm")}</button>
      </form>
    </div>`;
  }

  function bindProposalChecklist(root, nodeId, postJson, onRefresh, notify, reInspect) {
    root.querySelectorAll("[data-prop-step]").forEach((chk) => chk.addEventListener("change", async () => {
      try { await postJson("/api/orchestrate", { action: "toggle_step", kind: "PROPOSAL", item_id: nodeId, step_idx: Number(chk.dataset.propStep), done: chk.checked }); await onRefresh(); await reInspect(); }
      catch (err) { notify(err.message, true); }
    }));
    root.querySelector("#insp-prop-step-form")?.addEventListener("submit", async (ev) => {
      ev.preventDefault(); const v = root.querySelector("#insp-prop-new-step")?.value.trim(); if (!v) return;
      try { await postJson("/api/orchestrate", { action: "add_step", kind: "PROPOSAL", item_id: nodeId, text: v }); await onRefresh(); await reInspect(); }
      catch (err) { notify(err.message, true); }
    });
  }

  window.SuperMemoryKanbanModals = { buildKanbanItems, openTaskModal, inspectTaskInDrawer, renderProposalChecklist, bindProposalChecklist };
})();
