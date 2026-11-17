// Accessible Native <dialog> Form & Workflow Controller (WCAG 2.1 AA Focus Management)
(function () {
  const { esc, statusTag, tr, renderMarkdown, svg } = window.SuperMemoryIcons;
  const fld = (name, label, ctrl) => `<div class="field-group"><label for="f-${name}" class="field-label">${label}</label>${ctrl}</div>`;
  const inp = (name, val = "", ph = "") => `<input id="f-${name}" name="${name}" class="control-input" value="${esc(val)}" placeholder="${esc(ph)}" />`;
  const area = (name, val = "", rows = 3) => `<textarea id="f-${name}" name="${name}" class="control-textarea" rows="${rows}">${esc(val)}</textarea>`;
  const row2 = (a, b) => `<div class="form-row-2">${a}${b}</div>`;
  const sel = (name, opts, cur = "") =>
    `<select id="f-${name}" name="${name}" class="control-select">${opts
      .map((o) => (typeof o === "string" ? [o, o] : o))
      .map(([v, l]) => `<option value="${esc(v)}" ${v === cur ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>`;

  class ModalController {
    constructor(getState, setScope, postJson, onRefresh, notify) {
      Object.assign(this, { getState, setScope, postJson, onRefresh, notify, lastTrigger: null });
      this.dialog = document.getElementById("workbench-dialog");
      this.errBox = document.getElementById("dialog-error");
      this.bodyBox = document.getElementById("dialog-body");
      document.getElementById("btn-close-dialog").addEventListener("click", () => this.close());
      this.dialog.addEventListener("click", (ev) => { if (ev.target === this.dialog) this.close(); });
      this.dialog.addEventListener("close", () => { if (this.lastTrigger?.focus) this.lastTrigger.focus(); });
      this._bindButtons();
    }

    close() { if (this.dialog.open) this.dialog.close(); }

    open(title, html, onSubmit, extraFooterHtml = "") {
      this.lastTrigger = document.activeElement;
      document.getElementById("dialog-title").textContent = title;
      this.errBox.classList.add("hidden");
      if (onSubmit) {
        this.bodyBox.innerHTML = `<form id="dlg-form" class="inspector-section" novalidate>${html}
          <div class="dialog-footer"><button type="button" id="btn-dlg-cancel" class="btn btn-ghost">${tr("Cancel", "Hủy")}</button>
          <button type="submit" class="btn btn-primary">${tr("Save", "Lưu thực thi")}</button></div></form>`;
        document.getElementById("btn-dlg-cancel").addEventListener("click", () => this.close());
        document.getElementById("dlg-form").addEventListener("submit", async (ev) => {
          ev.preventDefault(); this.errBox.classList.add("hidden");
          try { await onSubmit(Object.fromEntries(new FormData(ev.target).entries())); this.close(); }
          catch (err) { this.errBox.textContent = err.message; this.errBox.classList.remove("hidden"); }
        });
      } else {
        this.bodyBox.innerHTML = `${html}<div class="dialog-footer">${extraFooterHtml}<button type="button" id="btn-dlg-ok" class="btn btn-secondary">${tr("Close", "Đóng")}</button></div>`;
        document.getElementById("btn-dlg-ok").addEventListener("click", () => this.close());
      }
      if (!this.dialog.open) this.dialog.showModal();
      this.bodyBox.querySelector("input, textarea, select, button")?.focus();
    }

    openInitWorkspace() {
      this.open(tr("Initialize or Import SuperMemory Workspace", "Khởi tạo hoặc Import Dự án SuperMemory"),
        fld("path", tr("Absolute Project Directory Path *", "Đường dẫn tuyệt đối thư mục dự án *"), inp("path", "", "/path/to/project")) +
        row2(fld("name", tr("Project Name", "Tên dự án"), inp("name", "", "MyResearchRepo")), fld("max_lines", tr("Max Lines / File", "Giới hạn dòng / file"), inp("max_lines", "500"))) +
        fld("goal", tr("Initial Strategic Goal", "Mục tiêu chiến lược ban đầu"), inp("goal", "", "Achieve reproducible SOTA")) +
        fld("import_zaloai_from", tr("Optional: Import from legacy workspace", "Tùy chọn: Import dữ liệu từ workspace cũ"), inp("import_zaloai_from")),
        async (v) => {
          if (!v.path.trim()) throw new Error(tr("Please enter the project directory path.", "Vui lòng nhập đường dẫn thư mục dự án."));
          const out = await this.postJson("/api/workspaces/init", { ...v, max_lines: Number(v.max_lines || 500) });
          this.setScope(out.workspace_path); this.notify(tr(`Initialized workspace ${out.project}`, `Đã khởi tạo dự án ${out.project}`)); await this.onRefresh();
        });
    }

    openEditState() {
      const m = this.getState().meta || {};
      this.open(tr("Update Working State (L0 Working Memory)", "Cập nhật Trạng thái Làm việc (L0 Working Memory)"),
        fld("project_name", tr("Project Name", "Tên dự án"), inp("project_name", m.project_name || this.getState().project || "")) +
        fld("active_goal", tr("Active Strategic Goal", "Mục tiêu chiến lược hiện tại"), inp("active_goal", m.active_goal || "")) +
        fld("current_phase", tr("Current Phase", "Giai đoạn thực thi"), inp("current_phase", m.current_phase || "")) +
        fld("next_actions", tr("Immediate Next Actions", "Hành động ưu tiên tiếp theo"), area("next_actions", m.next_actions || "", 3)),
        async (v) => { await this.postJson("/api/state", v); this.notify(tr("Synced 01_ACTIVE_STATE.md", "Đã đồng bộ 01_ACTIVE_STATE.md")); await this.onRefresh(); });
    }

    openUpsertNode(ex = null) {
      this.open(ex ? tr(`Edit Entity ${ex.id}`, `Chỉnh sửa thực thể ${ex.id}`) : tr("Create Knowledge / Procedure Entity", "Tạo Node Tri thức / Quy trình mới"),
        row2(fld("node_type", tr("Entity Type", "Loại thực thể"), sel("node_type", ["KNOWLEDGE_NODE", "PROCEDURE", "OBSERVATION", "LAW", "IDEA", "ALGORITHM"], ex?.node_type || "KNOWLEDGE_NODE")),
             fld("memory_tier", tr("Cognitive Tier", "Tầng nhận thức"), sel("memory_tier", ["SEMANTIC", "PROCEDURAL", "EPISODIC"], ex?.memory_tier || "SEMANTIC"))) +
        row2(fld("id", tr("Entity ID (auto-generated if blank)", "Mã định danh (tự sinh nếu trống)"), inp("id", ex?.id || "")), fld("status", tr("Status", "Trạng thái"), inp("status", ex?.status || "ACTIVE"))) +
        fld("title", tr("Title *", "Tiêu đề *"), inp("title", ex?.title || "")) +
        fld("summary", tr("Short Summary (injected into Capsule)", "Tóm tắt ngắn (nạp vào Capsule)"), area("summary", ex?.summary || "", 2)) +
        fld("content", tr("Detailed Content (Markdown)", "Nội dung chi tiết (Markdown)"), area("content", ex?.content || "", 4)),
        async (v) => {
          if (!v.title.trim()) throw new Error(tr("Title cannot be empty.", "Tiêu đề không được để trống."));
          const res = await this.postJson("/api/node/upsert", { ...v, id: ex ? ex.id : v.id.trim() });
          this.notify(tr(`Saved ${res.node.id}`, `Đã lưu ${res.node.id}`)); await this.onRefresh();
        });
    }

    openAddLesson() {
      const laws = [["", tr("-- Create New LAW --", "-- Tạo LAW mới --")], ...(this.getState().nodes || []).filter((n) => n.node_type === "LAW").map((l) => [l.id, `${l.id}: ${l.title.slice(0, 42)}`])];
      this.open(tr("Record Lesson & Bind Automated CodeGate", "Ghi Bài học & Ràng buộc CodeGate Tự động"),
        fld("title", tr("Lesson / Rule Title *", "Tiêu đề bài học / Rule *"), inp("title", "", tr("Never hardcode eval sample IDs", "Cấm hardcode ID mẫu kiểm thử"))) +
        row2(fld("law_id", tr("Consolidate into Existing Law", "Gộp vào Luật hiện có"), sel("law_id", laws)), fld("new_law_title", tr("Or New LAW Title", "Hoặc tên LAW mới"), inp("new_law_title"))) +
        fld("mistake", tr("Mistake / Incident Context *", "Sai lầm / Bối cảnh phát hiện *"), area("mistake", "", 2)) +
        fld("root_cause", tr("Root Cause (5-Whys) *", "Nguyên nhân gốc rễ (5-Whys) *"), inp("root_cause")) +
        fld("prevention_rule", tr("Mandatory Prevention Rule *", "Quy tắc phòng ngừa bắt buộc *"), area("prevention_rule", "", 2)) +
        row2(fld("forbid_regex", tr("PreToolUse Forbidden Regex", "Regex chặn PreToolUse"), inp("forbid_regex")), fld("target_glob", tr("Target Glob", "Phạm vi tệp"), inp("target_glob", "**/*.py"))),
        async (v) => {
          if (!v.title.trim() || !v.prevention_rule.trim()) throw new Error(tr("Title and Prevention Rule are required.", "Cần nhập Tiêu đề và Quy tắc phòng ngừa."));
          const mistake = v.mistake.trim() || v.title.trim();
          const out = await this.postJson("/api/lessons", { ...v, mistake, root_cause: v.root_cause.trim() || mistake });
          this.notify(tr(`Crystallized ${out.lesson_id} into ${out.law_id}`, `Đã kết tinh ${out.lesson_id} vào ${out.law_id}`)); await this.onRefresh();
        });
    }

    openAddGate(ex = null) {
      this.open(ex ? tr(`Edit CodeGate ${ex.id}`, `Chỉnh sửa CodeGate ${ex.id}`) : tr("Add PreToolUse CodeGate / SHA-256 Freeze", "Thêm Chốt chặn PreToolUse CodeGate / Khóa SHA-256"),
        (ex ? "" : fld("freeze_path", tr("Freeze File Integrity via SHA-256 (optional)", "Khóa toàn vẹn tệp bằng SHA-256 (tùy chọn)"), inp("freeze_path", "", "eval/evaluate.py"))) +
        row2(fld("name", tr("Gate Name", "Tên Gate"), inp("name", ex?.name || "", "Block Print Debug")), fld("law_id", tr("Bound LAW", "Thuộc LAW"), inp("law_id", ex?.law_id || "LAW-08"))) +
        row2(fld("gate_type", tr("Gate Type", "Loại Gate"), sel("gate_type", ["FORBIDDEN_REGEX", "FORBIDDEN_CMD_PATTERN", "FORBIDDEN_FILENAME", "AST_SYNTAX", "MAX_LINES", "FROZEN_SHA256", "CHANGELOG_SYNC"], ex?.gate_type || "FORBIDDEN_REGEX")),
             fld("target_glob", "Target Glob", inp("target_glob", ex?.target_glob || "**/*.py"))) +
        fld("pattern", tr("Rule Pattern / Max Lines / SHA-256", "Biểu thức Regex / Số dòng / SHA-256"), area("pattern", ex?.pattern || "", 2)),
        async (v) => {
          const out = await this.postJson("/api/gates", { ...v, id: ex?.id || "", action: v.freeze_path?.trim() ? "freeze" : "create", name: v.name.trim() || "Custom Gate" });
          this.notify(tr(`Saved ${out.gate.id}`, `Đã lưu ${out.gate.id}`)); await this.onRefresh();
        });
    }

    openAddExperiment() {
      this.open(tr("Log Single-Variable Scientific Experiment", "Ghi nhận Thực nghiệm Khoa học Đơn biến"),
        row2(fld("track", tr("Track", "Nhánh (Track)"), inp("track", "main")), fld("verdict", tr("Verdict", "Kết luận"), sel("verdict", ["KEEP", "VICTORY_CONFIRMED", "REVERT", "FAILED"]))) +
        fld("title", tr("Experiment Title *", "Tiêu đề thực nghiệm *"), inp("title")) +
        row2(fld("cv_score", tr("CV Score", "Điểm CV"), inp("cv_score")), fld("test_score", tr("Test / LB Score", "Điểm Test / LB"), inp("test_score"))) +
        fld("hypothesis", tr("Scientific Hypothesis *", "Giả thuyết khoa học *"), inp("hypothesis")) +
        fld("single_var_diff", tr("Single-Variable Diff *", "Biến thay đổi duy nhất *"), inp("single_var_diff")) +
        fld("post_mortem", tr("Post-Mortem (Mandatory if REVERT / FAILED)", "Hậu kiểm (Bắt buộc nếu REVERT / FAILED)"), area("post_mortem", "", 2)) +
        fld("insights", tr("Extracted Insights (1 per line -> L2 OBS-XXX)", "Các Insight rút ra (mỗi dòng 1 ý -> tự tạo OBS-XXX tầng L2)"), area("insights", "", 2)),
        async (v) => {
          if (!v.title.trim() || !v.hypothesis.trim() || !v.single_var_diff.trim()) throw new Error(tr("Title, Hypothesis, and Single-Variable Diff are required.", "Cần nhập đủ Tiêu đề, Giả thuyết và Biến thay đổi."));
          const out = await this.postJson("/api/experiments", v);
          this.notify(tr(`Logged ${out.exp_id}`, `Đã ghi nhận ${out.exp_id}`)); await this.onRefresh();
        });
    }

    openAddProposal() {
      this.open(tr("Create OpenSpec Proposal (With Dead-End Anti-Repeat Check)", "Tạo OpenSpec Proposal (Có kiểm tra trùng lặp Dead-End)"),
        fld("title", tr("Proposal Title *", "Tiêu đề Proposal *"), inp("title")) + fld("why", tr("Motivation & Core Problem *", "Lý do & Vấn đề cốt lõi *"), area("why", "", 2)) +
        fld("design_notes", tr("Architecture Design & Solution", "Thiết kế kiến trúc & Giải pháp"), area("design_notes", "", 3)) + fld("tasks", tr("Implementation Tasks (1 per line)", "Danh sách hạng mục (mỗi dòng 1 task)"), area("tasks", "", 3)),
        async (v) => {
          if (!v.title.trim() || !v.why.trim()) throw new Error(tr("Title and Motivation are required.", "Cần nhập đủ Tiêu đề và Lý do."));
          const out = await this.postJson("/api/proposals", { ...v, action: "create" });
          this.notify(tr(`Created ${out.proposal_id}`, `Đã khởi tạo ${out.proposal_id}`)); await this.onRefresh();
        });
    }

    openAddIdea() {
      this.open(tr("Save Idea or Record Falsified Dead-End", "Lưu Ý tưởng mới hoặc Ghi sổ Hướng đã bác bỏ (Dead-End)"),
        row2(fld("title", tr("Idea / Algorithm Title *", "Tên Ý tưởng / Thuật toán *"), inp("title")), fld("status", tr("Status", "Trạng thái"), sel("status", ["SEED", "VALIDATED", "REJECTED"]))) +
        fld("summary", tr("Mechanism Summary *", "Mô tả cơ chế *"), area("summary", "", 2)) + fld("rejection_reason", tr("Rejection Reason (if REJECTED)", "Lý do bác bỏ (nếu REJECTED)"), inp("rejection_reason")),
        async (v) => {
          if (!v.title.trim() || !v.summary.trim()) throw new Error(tr("Title and Summary are required.", "Cần nhập Tên và Mô tả ý tưởng."));
          const out = await this.postJson("/api/ideas", v);
          this.notify(tr(`Saved ${out.node.id}`, `Đã lưu ${out.node.id}`)); await this.onRefresh();
        });
    }

    async runAuditDialog() {
      const res = await this.postJson("/api/audit", {});
      const vList = (res.violations || []).map((v) => typeof v === "string" ? `<li><code>${esc(v)}</code></li>` : `<li><code>${esc(v.gate_id)}</code>: ${esc(v.message)}</li>`).join("");
      this.open(tr("Full Workspace CodeGate Audit Results", "Kết quả Kiểm định Toàn bộ Workspace"),
        `<div>${statusTag(res.passed ? "ACTIVE" : "FAILED", res.passed ? tr("100% PASSED", "ĐẠT CHUẨN 100%") : tr("VIOLATIONS FOUND", "PHÁT HIỆN VI PHẠM"))}</div>` +
        `<p class="row-desc">${tr(`Scanned ${res.checked_files || 0} files across ${res.active_gates || res.gates_evaluated || 0} active CodeGates.`, `Đã quét ${res.checked_files || 0} tệp qua ${res.active_gates || res.gates_evaluated || 0} chốt chặn CodeGate.`)}</p>` +
        (vList ? `<ul class="code-block">${vList}</ul>` : `<p class="row-desc">${tr("Zero source or SHA-256 integrity violations detected.", "Không có vi phạm nào trong mã nguồn và SHA-256.")}</p>`), null);
    }

    async openHandoffDialog() {
      const res = await this.postJson("/api/handoff", {});
      this.open(tr("Zero-Loss Handoff Briefing (HANDOFF_BRIEFING.md)", "Bản bàn giao Không mất Ngữ cảnh (HANDOFF_BRIEFING.md)"),
        `<p class="mono-id">${esc(res.handoff_path)}</p><article class="md-prose md-modal-scroll">${renderMarkdown(res.markdown, false)}</article>`, null,
        `<button type="button" id="btn-copy-handoff" class="btn btn-primary">${svg("copy", 14)} ${tr("Copy Markdown", "Sao chép Markdown")}</button>`);
      document.getElementById("btn-copy-handoff")?.addEventListener("click", async () => {
        await navigator.clipboard?.writeText(res.markdown || "");
        this.notify(tr("Copied HANDOFF_BRIEFING.md", "Đã sao chép HANDOFF_BRIEFING.md"));
      });
    }

    _bindButtons() {
      const map = {
        "btn-open-init": () => this.openInitWorkspace(), "btn-open-state": () => this.openEditState(),
        "btn-open-quick-node": () => this.openUpsertNode(), "btn-add-lesson": () => this.openAddLesson(),
        "btn-add-gate": () => this.openAddGate(), "btn-add-exp": () => this.openAddExperiment(),
        "btn-add-proposal": () => this.openAddProposal(), "btn-add-idea": () => this.openAddIdea(),
        "btn-run-audit": () => this.runAuditDialog(), "btn-handoff": () => this.openHandoffDialog(),
      };
      Object.entries(map).forEach(([id, fn]) => document.getElementById(id)?.addEventListener("click", fn));
    }
  }
  window.SuperMemoryModals = { ModalController };
})();
