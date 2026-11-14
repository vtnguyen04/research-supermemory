// Interactive Modal Forms, Inspector Inline CRUD & 1-Click Lifecycle Actions
(function () {
  const esc = (s) =>
    String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");

  class StudioActionsController {
    constructor(getState, getScope, setScope, onRefresh, onInspect) {
      this.getState = getState;
      this.getScope = getScope;
      this.setScope = setScope;
      this.onRefresh = onRefresh;
      this.onInspect = onInspect;
      this.modal = document.getElementById("studio-modal");
      this.modalTitle = document.getElementById("modal-title");
      this.modalBody = document.getElementById("modal-body");
      document.getElementById("btn-close-modal").onclick = () => this.closeModal();
      this.modal.onclick = (e) => { if (e.target === this.modal) this.closeModal(); };
      this._bindToolbarButtons();
    }

    toast(msg, isError = false) {
      const el = document.getElementById("toast-bar");
      el.textContent = msg;
      el.className = `toast ${isError ? "err" : ""}`;
      clearTimeout(this._toastTimer);
      this._toastTimer = setTimeout(() => el.classList.add("hidden"), 4200);
    }

    openModal(title, html, onMount) {
      this.modalTitle.textContent = title;
      this.modalBody.innerHTML = html;
      this.modal.classList.remove("hidden");
      if (onMount) onMount(this.modalBody);
    }

    closeModal() {
      this.modal.classList.add("hidden");
    }

    async postJson(url, payload) {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scope: this.getScope(), ...payload }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      return data;
    }

    _bindToolbarButtons() {
      document.getElementById("btn-open-init").onclick = () => this.openInitWorkspaceModal();
      document.getElementById("btn-open-state").onclick = () => this.openEditStateModal();
      document.getElementById("btn-open-quick-node").onclick = () => this.openUpsertNodeModal(null);
      document.getElementById("btn-run-audit").onclick = () => this.runAuditAction();
      document.getElementById("btn-handoff").onclick = () => this.openHandoffModal();
      document.getElementById("btn-add-lesson").onclick = () => this.openAddLessonModal();
      document.getElementById("btn-add-gate").onclick = () => this.openAddGateModal();
      document.getElementById("btn-add-exp").onclick = () => this.openAddExperimentModal();
      document.getElementById("btn-add-proposal").onclick = () => this.openAddProposalModal();
      document.getElementById("btn-add-idea").onclick = () => this.openAddIdeaModal();
    }

    openInitWorkspaceModal() {
      this.openModal("📁 Khởi tạo Dự án mới / Import ZALOAI", `
        <div><label class="field-label">Đường dẫn Folder Dự án trên máy (*)</label>
        <input id="f-ws-path" class="text-input" placeholder="/home/quynhthu/Documents/AI-project/ten-du-an" /></div>
        <div class="form-grid">
          <div><label class="field-label">Tên Dự án</label><input id="f-ws-name" class="text-input" placeholder="MyProject" /></div>
          <div><label class="field-label">Giới hạn dòng / file (LAW-02)</label><input id="f-ws-lines" type="number" class="text-input" value="300" /></div>
        </div>
        <div><label class="field-label">Mục tiêu chiến lược ban đầu</label>
        <input id="f-ws-goal" class="text-input" placeholder="Xây dựng hệ thống SOTA chuẩn kiến trúc..." /></div>
        <div><label class="field-label">(Tùy chọn) Import từ Folder ZALOAI / OpenSpec có sẵn</label>
        <input id="f-ws-zalo" class="text-input" placeholder="Để trống nếu tạo mới (hoặc điền /path/to/ZALOAI)" /></div>
        <button id="f-ws-submit" class="btn-primary">🚀 Khởi tạo & Chuyển tới Dự án này</button>
      `, (box) => {
        box.querySelector("#f-ws-submit").onclick = async () => {
          try {
            const out = await this.postJson("/api/workspaces/init", {
              path: box.querySelector("#f-ws-path").value,
              name: box.querySelector("#f-ws-name").value,
              max_lines: Number(box.querySelector("#f-ws-lines").value || 300),
              goal: box.querySelector("#f-ws-goal").value,
              import_zaloai_from: box.querySelector("#f-ws-zalo").value,
            });
            this.closeModal();
            this.setScope(out.workspace_path);
            this.toast(`✅ Đã khởi tạo & mở dự án: ${out.project}`);
            await this.onRefresh();
          } catch (e) { this.toast(`❌ ${e.message}`, true); }
        };
      });
    }

    openEditStateModal() {
      const m = this.getState().meta || {};
      this.openModal("🎯 Cập nhật Trạng thái Làm việc (L0 WORKING — 01_ACTIVE_STATE.md)", `
        <div><label class="field-label">Tên Dự án</label><input id="f-st-name" class="text-input" value="${esc(m.project_name || this.getState().project)}" /></div>
        <div><label class="field-label">Mục tiêu Chiến lược hiện tại (Active Goal)</label><input id="f-st-goal" class="text-input" value="${esc(m.active_goal || "")}" /></div>
        <div><label class="field-label">Phase hiện tại</label><input id="f-st-phase" class="text-input" value="${esc(m.current_phase || "")}" /></div>
        <div><label class="field-label">Chỉ tiêu / SLA Targets</label><input id="f-st-targets" class="text-input" value="${esc(m.primary_targets || "")}" /></div>
        <div><label class="field-label">Hành động tiếp theo (Next Actions)</label><textarea id="f-st-next" class="text-area" rows="3">${esc(m.next_actions || "")}</textarea></div>
        <button id="f-st-save" class="btn-primary">💾 Lưu Trạng thái & Đồng bộ AGENTS.md</button>
      `, (box) => {
        box.querySelector("#f-st-save").onclick = async () => {
          try {
            await this.postJson("/api/state", {
              project_name: box.querySelector("#f-st-name").value,
              active_goal: box.querySelector("#f-st-goal").value,
              current_phase: box.querySelector("#f-st-phase").value,
              primary_targets: box.querySelector("#f-st-targets").value,
              next_actions: box.querySelector("#f-st-next").value,
            });
            this.closeModal();
            this.toast("✅ Đã cập nhật 01_ACTIVE_STATE.md & AGENTS.md!");
            await this.onRefresh();
          } catch (e) { this.toast(`❌ ${e.message}`, true); }
        };
      });
    }

    openUpsertNodeModal(node) {
      const isEdit = Boolean(node);
      this.openModal(isEdit ? `✏️ Chỉnh sửa ${node.id}` : "✨ Tạo nhanh Tri thức / Quy trình / Luật", `
        <div class="form-grid">
          <div><label class="field-label">Loại Node</label>
            <select id="f-nd-type" class="select-input" style="width:100%">
              ${["KNOWLEDGE_NODE", "PROCEDURE", "OBSERVATION", "LAW", "IDEA", "ALGORITHM", "LESSON", "PROPOSAL"].map(
                (t) => `<option value="${t}" ${node?.node_type === t ? "selected" : ""}>${t}</option>`
              ).join("")}
            </select>
          </div>
          <div><label class="field-label">Tầng Nhận thức (Memory Tier)</label>
            <select id="f-nd-tier" class="select-input" style="width:100%">
              ${["SEMANTIC", "PROCEDURAL", "EPISODIC"].map(
                (tr) => `<option value="${tr}" ${node?.memory_tier === tr ? "selected" : ""}>${tr}</option>`
              ).join("")}
            </select>
          </div>
        </div>
        <div class="form-grid">
          <div><label class="field-label">Trạng thái (Status)</label><input id="f-nd-status" class="text-input" value="${esc(node?.status || "ACTIVE")}" /></div>
          <div><label class="field-label">Tags (cách nhau dấu phẩy)</label><input id="f-nd-tags" class="text-input" value="${esc((node?.tags || []).join(", "))}" /></div>
        </div>
        <div><label class="field-label">Tiêu đề (*)</label><input id="f-nd-title" class="text-input" value="${esc(node?.title || "")}" /></div>
        <div><label class="field-label">Tóm tắt ngắn (Summary — nạp vào Recall)</label><textarea id="f-nd-sum" class="text-area" rows="2">${esc(node?.summary || "")}</textarea></div>
        <div><label class="field-label">Nội dung chi tiết (Markdown)</label><textarea id="f-nd-content" class="text-area" rows="5">${esc(node?.content || "")}</textarea></div>
        <button id="f-nd-save" class="btn-primary">💾 ${isEdit ? "Lưu thay đổi Node" : "Tạo Node vào Đồ thị"}</button>
      `, (box) => {
        box.querySelector("#f-nd-save").onclick = async () => {
          try {
            const out = await this.postJson("/api/node/upsert", {
              id: node?.id || "",
              node_type: box.querySelector("#f-nd-type").value,
              memory_tier: box.querySelector("#f-nd-tier").value,
              status: box.querySelector("#f-nd-status").value,
              tags: box.querySelector("#f-nd-tags").value,
              title: box.querySelector("#f-nd-title").value,
              summary: box.querySelector("#f-nd-sum").value,
              content: box.querySelector("#f-nd-content").value,
            });
            this.closeModal();
            this.toast(`✅ Đã lưu ${out.node.id}`);
            await this.onRefresh();
            this.onInspect(out.node.id);
          } catch (e) { this.toast(`❌ ${e.message}`, true); }
        };
      });
    }

    openAddLessonModal() {
      const laws = (this.getState().nodes || []).filter((n) => n.node_type === "LAW");
      this.openModal("🔥 Ghi Bài học Tự học / Thêm Rule & CodeGate", `
        <div class="form-grid">
          <div><label class="field-label">Lưu vào Phạm vi</label>
            <select id="f-ls-scope" class="select-input" style="width:100%">
              <option value="${esc(this.getScope())}">Dự án đang mở hiện tại</option>
              <option value="global">🌐 Global SuperMemory (Mọi dự án)</option>
            </select>
          </div>
          <div><label class="field-label">Gộp vào LAW sẵn có</label>
            <select id="f-ls-law" class="select-input" style="width:100%">
              <option value="">-- Hoặc tạo LAW mới bên dưới --</option>
              ${laws.map((l) => `<option value="${esc(l.id)}">${esc(l.id)}: ${esc(l.title.slice(0, 38))}</option>`).join("")}
            </select>
          </div>
        </div>
        <div><label class="field-label">(Tùy chọn) Tiêu đề LAW mới nếu tách riêng</label><input id="f-ls-newlaw" class="text-input" placeholder="VD: Cấm dùng print() trực tiếp trong pipeline..." /></div>
        <div><label class="field-label">Tiêu đề Bài học / Quy tắc (*)</label><input id="f-ls-title" class="text-input" placeholder="VD: Luôn dùng logger thay vì print()" /></div>
        <div><label class="field-label">Sai lầm / Bối cảnh phát sinh (*)</label><input id="f-ls-mistake" class="text-input" placeholder="Mô tả lỗi hoặc yêu cầu từ người dùng..." /></div>
        <div><label class="field-label">Nguyên nhân gốc rễ (*)</label><input id="f-ls-root" class="text-input" placeholder="Tại sao lỗi xảy ra..." /></div>
        <div><label class="field-label">Quy tắc Bất biến Phòng ngừa (*)</label><textarea id="f-ls-rule" class="text-area" rows="2" placeholder="Quy định bắt buộc Agent phải tuân thủ..."></textarea></div>
        <div class="form-grid">
          <div><label class="field-label">(Tùy chọn) Regex chặn Code (PreToolUse)</label><input id="f-ls-rx" class="text-input" placeholder="VD: \\bprint\\s*\\(" /></div>
          <div><label class="field-label">Target Glob</label><input id="f-ls-glob" class="text-input" value="src/**/*.py" /></div>
        </div>
        <button id="f-ls-save" class="btn-primary">🛡 Lưu Bài học + Đồng bộ AGENTS.md & CodeGate</button>
      `, (box) => {
        box.querySelector("#f-ls-save").onclick = async () => {
          try {
            const out = await this.postJson("/api/lessons", {
              scope: box.querySelector("#f-ls-scope").value,
              law_id: box.querySelector("#f-ls-law").value,
              new_law_title: box.querySelector("#f-ls-newlaw").value,
              title: box.querySelector("#f-ls-title").value,
              mistake: box.querySelector("#f-ls-mistake").value,
              root_cause: box.querySelector("#f-ls-root").value,
              prevention_rule: box.querySelector("#f-ls-rule").value,
              forbid_regex: box.querySelector("#f-ls-rx").value,
              target_glob: box.querySelector("#f-ls-glob").value,
            });
            this.closeModal();
            this.toast(`✅ Đã lưu ${out.lesson_id} -> ${out.law_id}${out.gate_id ? " + " + out.gate_id : ""}`);
            await this.onRefresh();
          } catch (e) { this.toast(`❌ ${e.message}`, true); }
        };
      });
    }

    openAddGateModal() {
      this.openModal("🛡 Tạo Chốt chặn CodeGate / Khóa cứng File SHA-256", `
        <div><label class="field-label">Chế độ tạo Gate</label>
          <select id="f-gt-type" class="select-input" style="width:100%">
            <option value="FORBIDDEN_REGEX">FORBIDDEN_REGEX (Chặn mẫu code cấm)</option>
            <option value="FROZEN_SHA256">FROZEN_SHA256 (Khóa cứng file chấm điểm / test không cho sửa)</option>
            <option value="FORBIDDEN_CMD_PATTERN">FORBIDDEN_CMD_PATTERN (Chặn lệnh terminal nguy hiểm)</option>
            <option value="FORBIDDEN_FILENAME">FORBIDDEN_FILENAME (Chặn tên file rác)</option>
            <option value="MAX_LINES">MAX_LINES (Giới hạn số dòng tối đa)</option>
          </select>
        </div>
        <div><label class="field-label">Tên Gate / Đường dẫn File cần khóa SHA-256 (*)</label>
        <input id="f-gt-name" class="text-input" placeholder="Tên Gate (hoặc đường dẫn tương đối VD: tests/eval.py nếu chọn FROZEN_SHA256)" /></div>
        <div class="form-grid">
          <div><label class="field-label">Pattern Regex / Số dòng tối đa</label><input id="f-gt-pat" class="text-input" placeholder="Regex cấm (hoặc 300 cho MAX_LINES)" /></div>
          <div><label class="field-label">Target Glob</label><input id="f-gt-glob" class="text-input" value="**/*.py" /></div>
        </div>
        <button id="f-gt-save" class="btn-primary">🔒 Kích hoạt CodeGate ngay</button>
      `, (box) => {
        box.querySelector("#f-gt-save").onclick = async () => {
          try {
            const gtype = box.querySelector("#f-gt-type").value;
            const nameOrPath = box.querySelector("#f-gt-name").value.trim();
            const pat = box.querySelector("#f-gt-pat").value.trim();
            const payload = gtype === "FROZEN_SHA256"
              ? { action: "freeze", freeze_path: nameOrPath }
              : { action: "create", gate_type: gtype, name: nameOrPath, pattern: pat, max_lines: Number(pat || 300), target_glob: box.querySelector("#f-gt-glob").value };
            const out = await this.postJson("/api/gates", payload);
            this.closeModal();
            this.toast(`✅ Đã kích hoạt ${out.gate.id} (${out.gate.gate_type})`);
            await this.onRefresh();
          } catch (e) { this.toast(`❌ ${e.message}`, true); }
        };
      });
    }

    openAddExperimentModal() {
      this.openModal("🧪 Log Thí nghiệm Khoa học Đơn biến (Tự kết tinh Insight OBS-XXX)", `
        <div class="form-grid">
          <div><label class="field-label">Track</label><input id="f-ex-track" class="text-input" value="main" /></div>
          <div><label class="field-label">Kết luận (Verdict)</label>
            <select id="f-ex-verdict" class="select-input" style="width:100%">
              <option value="KEEP">KEEP (Giữ lại)</option>
              <option value="VICTORY_CONFIRMED">VICTORY_CONFIRMED (Đạt mốc chuẩn)</option>
              <option value="REVERT">REVERT (Thất bại / Hoàn tác — bắt buộc ghi Insight)</option>
            </select>
          </div>
        </div>
        <div><label class="field-label">Tiêu đề Thí nghiệm (*)</label><input id="f-ex-title" class="text-input" /></div>
        <div><label class="field-label">Giả thuyết (Hypothesis *)</label><input id="f-ex-hyp" class="text-input" /></div>
        <div><label class="field-label">Biến thay đổi duy nhất (Single-Var Diff *)</label><input id="f-ex-diff" class="text-input" /></div>
        <div class="form-grid">
          <div><label class="field-label">Điểm CV (Số)</label><input id="f-ex-cv" type="number" step="any" class="text-input" /></div>
          <div><label class="field-label">Điểm Test/LB (Số)</label><input id="f-ex-ts" type="number" step="any" class="text-input" /></div>
        </div>
        <div><label class="field-label">Post-Mortem & Insights rút ra (Mỗi dòng 1 insight -> tự tạo OBS-XXX)</label>
        <textarea id="f-ex-ins" class="text-area" rows="3" placeholder="Nhận xét nguyên nhân thất bại / bài học kỹ thuật rút ra..."></textarea></div>
        <button id="f-ex-save" class="btn-primary">🧪 Ghi Sổ cái Thí nghiệm</button>
      `, (box) => {
        box.querySelector("#f-ex-save").onclick = async () => {
          try {
            const ins = box.querySelector("#f-ex-ins").value;
            const out = await this.postJson("/api/experiments", {
              track: box.querySelector("#f-ex-track").value,
              verdict: box.querySelector("#f-ex-verdict").value,
              title: box.querySelector("#f-ex-title").value,
              hypothesis: box.querySelector("#f-ex-hyp").value,
              single_var_diff: box.querySelector("#f-ex-diff").value,
              cv_score: box.querySelector("#f-ex-cv").value,
              test_score: box.querySelector("#f-ex-ts").value,
              post_mortem: ins,
              insights: ins,
            });
            this.closeModal();
            this.toast(`✅ Đã ghi ${out.exp_id} (${(out.observation_ids || []).join(", ") || "OK"})`);
            await this.onRefresh();
          } catch (e) { this.toast(`❌ ${e.message}`, true); }
        };
      });
    }

    openAddProposalModal() {
      this.openModal("📋 Tạo OpenSpec Proposal mới", `
        <div><label class="field-label">Tiêu đề Proposal (*)</label><input id="f-pr-title" class="text-input" /></div>
        <div><label class="field-label">Lý do & Bài toán cần giải quyết (Why *)</label><textarea id="f-pr-why" class="text-area" rows="2"></textarea></div>
        <div><label class="field-label">Thiết kế kỹ thuật & Các thay đổi chính</label><textarea id="f-pr-des" class="text-area" rows="3"></textarea></div>
        <div><label class="field-label">Danh sách Tasks (mỗi dòng 1 task)</label><textarea id="f-pr-tasks" class="text-area" rows="3" placeholder="Viết module X (<300 dòng)\nThêm pytest kiểm thử"></textarea></div>
        <button id="f-pr-save" class="btn-primary">📋 Khởi tạo Proposal</button>
      `, (box) => {
        box.querySelector("#f-pr-save").onclick = async () => {
          try {
            const out = await this.postJson("/api/proposals", {
              action: "create",
              title: box.querySelector("#f-pr-title").value,
              why: box.querySelector("#f-pr-why").value,
              what_changes: box.querySelector("#f-pr-des").value,
              design_notes: box.querySelector("#f-pr-des").value,
              tasks: box.querySelector("#f-pr-tasks").value,
            });
            this.closeModal();
            this.toast(`✅ Đã tạo ${out.proposal_id}`);
            await this.onRefresh();
          } catch (e) { this.toast(`❌ ${e.message}`, true); }
        };
      });
    }

    openAddIdeaModal() {
      this.openModal("💡 Thêm Ý tưởng / Thuật toán / Đánh dấu Dead-End (Cấm lặp lại)", `
        <div class="form-grid">
          <div><label class="field-label">Phân loại</label>
            <select id="f-id-algo" class="select-input" style="width:100%">
              <option value="false">IDEA (Ý tưởng)</option>
              <option value="true">ALGORITHM (Thuật toán)</option>
            </select>
          </div>
          <div><label class="field-label">Trạng thái</label>
            <select id="f-id-st" class="select-input" style="width:100%">
              <option value="SEED">SEED (Tiềm năng)</option>
              <option value="VERIFIED">VERIFIED (Đã kiểm chứng)</option>
              <option value="REJECTED">REJECTED (Vết xe đổ — Cấm Agent lặp lại!)</option>
            </select>
          </div>
        </div>
        <div><label class="field-label">Tiêu đề (*)</label><input id="f-id-title" class="text-input" /></div>
        <div><label class="field-label">Mô tả cốt lõi (*)</label><textarea id="f-id-sum" class="text-area" rows="2"></textarea></div>
        <div><label class="field-label">(Nếu REJECTED) Lý do loại bỏ để cảnh báo Anti-Repeat</label><input id="f-id-rej" class="text-input" placeholder="VD: Gây overfit nặng trên tập test..." /></div>
        <button id="f-id-save" class="btn-primary">💾 Lưu vào Kho Tri thức</button>
      `, (box) => {
        box.querySelector("#f-id-save").onclick = async () => {
          try {
            const out = await this.postJson("/api/ideas", {
              is_algorithm: box.querySelector("#f-id-algo").value === "true",
              status: box.querySelector("#f-id-st").value,
              title: box.querySelector("#f-id-title").value,
              summary: box.querySelector("#f-id-sum").value,
              rejection_reason: box.querySelector("#f-id-rej").value,
            });
            this.closeModal();
            this.toast(`✅ Đã lưu ${out.node.id}`);
            await this.onRefresh();
          } catch (e) { this.toast(`❌ ${e.message}`, true); }
        };
      });
    }

    async runAuditAction() {
      try {
        const res = await this.postJson("/api/audit", {});
        if (res.passed) {
          this.toast(`✅ Gate Audit PASSED (${res.checked_files} files • ${res.active_gates} gates • 0 vi phạm)!`);
        } else {
          this.openModal(`⚠️ Phát hiện ${res.violation_count} vi phạm CodeGate`,
            `<div class="insp-pre">${esc(JSON.stringify(res.violations, null, 2))}</div>`);
        }
      } catch (e) { this.toast(`❌ ${e.message}`, true); }
    }

    async openHandoffModal() {
      try {
        const res = await this.postJson("/api/handoff", {});
        this.openModal("🤝 HANDOFF_BRIEFING.md (Chống mất trí nhớ khi Compact / Đổi Agent)", `
          <p class="muted">Đã lưu tại: <code>${esc(res.handoff_path)}</code></p>
          <textarea id="f-ho-txt" class="text-area" rows="12" readonly>${esc(res.markdown)}</textarea>
          <button id="f-ho-copy" class="btn-primary">📋 Copy toàn bộ Briefing vào Clipboard</button>
        `, (box) => {
          box.querySelector("#f-ho-copy").onclick = () => {
            navigator.clipboard?.writeText(res.markdown);
            this.toast("📋 Đã copy Handoff Briefing!");
          };
        });
      } catch (e) { this.toast(`❌ ${e.message}`, true); }
    }
  }

  window.SuperMemoryStudioActions = { StudioActionsController };
})();
