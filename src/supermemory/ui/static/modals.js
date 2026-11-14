// Accessible Native <dialog> Form & Workflow Controller (WCAG 2.1 AA Focus Management)
(function () {
  const { esc, statusTag } = window.SuperMemoryIcons;
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

    open(title, html, onSubmit) {
      this.lastTrigger = document.activeElement;
      document.getElementById("dialog-title").textContent = title;
      this.errBox.classList.add("hidden");
      if (onSubmit) {
        this.bodyBox.innerHTML = `<form id="dlg-form" class="inspector-section" novalidate>${html}
          <div class="dialog-footer"><button type="button" id="btn-dlg-cancel" class="btn btn-ghost">Hủy</button>
          <button type="submit" class="btn btn-primary">Lưu thực thi</button></div></form>`;
        document.getElementById("btn-dlg-cancel").addEventListener("click", () => this.close());
        document.getElementById("dlg-form").addEventListener("submit", async (ev) => {
          ev.preventDefault();
          this.errBox.classList.add("hidden");
          try { await onSubmit(Object.fromEntries(new FormData(ev.target).entries())); this.close(); }
          catch (err) { this.errBox.textContent = err.message; this.errBox.classList.remove("hidden"); }
        });
      } else {
        this.bodyBox.innerHTML = `${html}<div class="dialog-footer"><button type="button" id="btn-dlg-ok" class="btn btn-secondary">Đóng</button></div>`;
        document.getElementById("btn-dlg-ok").addEventListener("click", () => this.close());
      }
      if (!this.dialog.open) this.dialog.showModal();
      this.bodyBox.querySelector("input, textarea, select, button")?.focus();
    }

    openInitWorkspace() {
      this.open("Khởi tạo hoặc Import Dự án SuperMemory",
        fld("path", "Đường dẫn tuyệt đối thư mục dự án *", inp("path", "", "/path/to/project")) +
        row2(fld("name", "Tên dự án", inp("name", "", "MyResearchRepo")), fld("max_lines", "Giới hạn dòng / file", inp("max_lines", "300"))) +
        fld("goal", "Mục tiêu chiến lược ban đầu", inp("goal", "", "Achieve reproducible SOTA")) +
        fld("import_zaloai_from", "Tùy chọn: Import dữ liệu từ workspace cũ", inp("import_zaloai_from")),
        async (v) => {
          if (!v.path.trim()) throw new Error("Vui lòng nhập đường dẫn thư mục dự án.");
          const out = await this.postJson("/api/workspaces/init", { ...v, max_lines: Number(v.max_lines || 300) });
          this.setScope(out.workspace_path); this.notify(`Đã khởi tạo dự án ${out.project}`); await this.onRefresh();
        });
    }

    openEditState() {
      const m = this.getState().meta || {};
      this.open("Cập nhật Trạng thái Làm việc (L0 Working Memory)",
        fld("project_name", "Tên dự án", inp("project_name", m.project_name || this.getState().project || "")) +
        fld("active_goal", "Mục tiêu chiến lược hiện tại", inp("active_goal", m.active_goal || "")) +
        fld("current_phase", "Giai đoạn thực thi", inp("current_phase", m.current_phase || "")) +
        fld("next_actions", "Hành động ưu tiên tiếp theo", area("next_actions", m.next_actions || "", 3)),
        async (v) => { await this.postJson("/api/state", v); this.notify("Đã đồng bộ 01_ACTIVE_STATE.md"); await this.onRefresh(); });
    }

    openUpsertNode(ex = null) {
      this.open(ex ? `Chỉnh sửa thực thể ${ex.id}` : "Tạo Node Tri thức / Quy trình mới",
        row2(fld("node_type", "Loại thực thể", sel("node_type", ["KNOWLEDGE_NODE", "PROCEDURE", "OBSERVATION", "LAW", "IDEA", "ALGORITHM"], ex?.node_type || "KNOWLEDGE_NODE")),
             fld("memory_tier", "Tầng nhận thức", sel("memory_tier", ["SEMANTIC", "PROCEDURAL", "EPISODIC"], ex?.memory_tier || "SEMANTIC"))) +
        row2(fld("id", "Mã định danh (tự sinh nếu trống)", inp("id", ex?.id || "")), fld("status", "Trạng thái", inp("status", ex?.status || "ACTIVE"))) +
        fld("title", "Tiêu đề *", inp("title", ex?.title || "")) +
        fld("summary", "Tóm tắt ngắn (nạp vào Capsule)", area("summary", ex?.summary || "", 2)) +
        fld("content", "Nội dung chi tiết (Markdown)", area("content", ex?.content || "", 4)),
        async (v) => {
          if (!v.title.trim()) throw new Error("Tiêu đề không được để trống.");
          const res = await this.postJson("/api/node/upsert", { ...v, id: ex ? ex.id : v.id.trim() });
          this.notify(`Đã lưu ${res.node.id}`); await this.onRefresh();
        });
    }

    openAddLesson() {
      const laws = [["", "-- Tạo LAW mới --"], ...(this.getState().nodes || []).filter((n) => n.node_type === "LAW").map((l) => [l.id, `${l.id}: ${l.title.slice(0, 42)}`])];
      this.open("Ghi Bài học & Ràng buộc CodeGate Tự động",
        fld("title", "Tiêu đề bài học / Rule *", inp("title", "", "Cấm hardcode ID mẫu kiểm thử")) +
        row2(fld("law_id", "Gộp vào Luật hiện có", sel("law_id", laws)), fld("new_law_title", "Hoặc tên LAW mới", inp("new_law_title"))) +
        fld("mistake", "Sai lầm / Bối cảnh phát hiện *", area("mistake", "", 2)) +
        fld("root_cause", "Nguyên nhân gốc rễ (5-Whys) *", inp("root_cause")) +
        fld("prevention_rule", "Quy tắc phòng ngừa bắt buộc *", area("prevention_rule", "", 2)) +
        row2(fld("forbid_regex", "Regex chặn PreToolUse", inp("forbid_regex")), fld("target_glob", "Phạm vi tệp", inp("target_glob", "**/*.py"))),
        async (v) => {
          if (!v.title.trim() || !v.prevention_rule.trim()) throw new Error("Cần nhập Tiêu đề và Quy tắc phòng ngừa.");
          const mistake = v.mistake.trim() || v.title.trim();
          const out = await this.postJson("/api/lessons", { ...v, mistake, root_cause: v.root_cause.trim() || mistake });
          this.notify(`Đã kết tinh ${out.lesson_id} vào ${out.law_id}`); await this.onRefresh();
        });
    }

    openAddGate() {
      this.open("Thêm Chốt chặn PreToolUse CodeGate / Khóa SHA-256",
        fld("freeze_path", "Khóa toàn vẹn tệp bằng SHA-256 (tùy chọn)", inp("freeze_path", "", "eval/evaluate.py")) +
        row2(fld("name", "Tên Gate", inp("name", "", "Block Print Debug")), fld("law_id", "Thuộc LAW", inp("law_id", "LAW-08"))) +
        row2(fld("gate_type", "Loại Gate", sel("gate_type", ["FORBIDDEN_REGEX", "FORBIDDEN_CMD_PATTERN", "MAX_LINES", "FROZEN_SHA256"])), fld("target_glob", "Target Glob", inp("target_glob", "**/*.py"))) +
        fld("pattern", "Biểu thức Regex chặn", inp("pattern")),
        async (v) => {
          const out = await this.postJson("/api/gates", { ...v, action: v.freeze_path.trim() ? "freeze" : "create", name: v.name.trim() || "Custom Gate" });
          this.notify(`Đã kích hoạt ${out.gate.id}`); await this.onRefresh();
        });
    }

    openAddExperiment() {
      this.open("Ghi nhận Thực nghiệm Khoa học Đơn biến",
        row2(fld("track", "Nhánh (Track)", inp("track", "main")), fld("verdict", "Kết luận", sel("verdict", ["KEEP", "VICTORY_CONFIRMED", "REVERT", "FAILED"]))) +
        fld("title", "Tiêu đề thực nghiệm *", inp("title")) +
        row2(fld("cv_score", "Điểm CV", inp("cv_score")), fld("test_score", "Điểm Test / LB", inp("test_score"))) +
        fld("hypothesis", "Giả thuyết khoa học *", inp("hypothesis")) +
        fld("single_var_diff", "Biến thay đổi duy nhất *", inp("single_var_diff")) +
        fld("post_mortem", "Hậu kiểm (Bắt buộc nếu REVERT / FAILED)", area("post_mortem", "", 2)) +
        fld("insights", "Các Insight rút ra (mỗi dòng 1 ý -> tự tạo OBS-XXX tầng L2)", area("insights", "", 2)),
        async (v) => {
          if (!v.title.trim() || !v.hypothesis.trim() || !v.single_var_diff.trim()) throw new Error("Cần nhập đủ Tiêu đề, Giả thuyết và Biến thay đổi.");
          const out = await this.postJson("/api/experiments", v);
          this.notify(`Đã ghi nhận ${out.exp_id}`); await this.onRefresh();
        });
    }

    openAddProposal() {
      this.open("Tạo OpenSpec Proposal (Có kiểm tra trùng lặp Dead-End)",
        fld("title", "Tiêu đề Proposal *", inp("title")) + fld("why", "Lý do & Vấn đề cốt lõi *", area("why", "", 2)) +
        fld("design_notes", "Thiết kế kiến trúc & Giải pháp", area("design_notes", "", 3)) + fld("tasks", "Danh sách hạng mục (mỗi dòng 1 task)", area("tasks", "", 3)),
        async (v) => {
          if (!v.title.trim() || !v.why.trim()) throw new Error("Cần nhập đủ Tiêu đề và Lý do.");
          const out = await this.postJson("/api/proposals", { ...v, action: "create" });
          this.notify(`Đã khởi tạo ${out.proposal_id}`); await this.onRefresh();
        });
    }

    openAddIdea() {
      this.open("Lưu Ý tưởng mới hoặc Ghi sổ Hướng đã bác bỏ (Dead-End)",
        row2(fld("title", "Tên Ý tưởng / Thuật toán *", inp("title")), fld("status", "Trạng thái", sel("status", ["SEED", "VALIDATED", "REJECTED"]))) +
        fld("summary", "Mô tả cơ chế *", area("summary", "", 2)) + fld("rejection_reason", "Lý do bác bỏ (nếu REJECTED)", inp("rejection_reason")),
        async (v) => {
          if (!v.title.trim() || !v.summary.trim()) throw new Error("Cần nhập Tên và Mô tả ý tưởng.");
          const out = await this.postJson("/api/ideas", v);
          this.notify(`Đã lưu ${out.node.id}`); await this.onRefresh();
        });
    }

    _bindButtons() {
      const map = {
        "btn-open-init": () => this.openInitWorkspace(), "btn-open-state": () => this.openEditState(),
        "btn-open-quick-node": () => this.openUpsertNode(), "btn-add-lesson": () => this.openAddLesson(),
        "btn-add-gate": () => this.openAddGate(), "btn-add-exp": () => this.openAddExperiment(),
        "btn-add-proposal": () => this.openAddProposal(), "btn-add-idea": () => this.openAddIdea(),
      };
      Object.entries(map).forEach(([id, fn]) => document.getElementById(id).addEventListener("click", fn));
      document.getElementById("btn-run-audit").addEventListener("click", async () => {
        const res = await this.postJson("/api/audit", {});
        const vList = (res.violations || []).map((v) => `<li><code>${esc(v.gate_id)}</code>: ${esc(v.message)}</li>`).join("");
        this.open("Kết quả Kiểm định Toàn bộ Workspace",
          `<div>${statusTag(res.passed ? "ACTIVE" : "FAILED", res.passed ? "ĐẠT CHUẨN 100%" : "PHÁT HIỆN VI PHẠM")}</div>` +
          `<p class="row-desc">Đã quét ${res.checked_files || 0} tệp qua ${res.gates_evaluated || 0} chốt chặn CodeGate.</p>` +
          (vList ? `<ul class="code-block">${vList}</ul>` : `<p class="row-desc">Không có vi phạm nào trong mã nguồn và SHA-256.</p>`), null);
      });
      document.getElementById("btn-handoff").addEventListener("click", async () => {
        const res = await this.postJson("/api/handoff", {});
        this.open("Bản bàn giao Không mất Ngữ cảnh (HANDOFF_BRIEFING.md)", `<p class="mono-id">${esc(res.handoff_path)}</p><pre class="code-block">${esc(res.markdown)}</pre>`, null);
      });
    }
  }
  window.SuperMemoryModals = { ModalController };
})();
