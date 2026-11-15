// Research v3.0.2 Studio: Pareto Bottleneck Ledger, SOTA Method Vault & Multi-Agent Fast-DAG
(function () {
  const { esc, statusTag, paginate, bindPagers, inlineMd, tr } = window.SuperMemoryIcons;
  const fld = (n, lbl, ctrl) => `<div class="field-group"><label for="rh-${n}" class="field-label">${lbl}</label>${ctrl}</div>`;
  const inp = (n, val = "", ph = "") => `<input id="rh-${n}" name="${n}" class="control-input" value="${esc(val)}" placeholder="${esc(ph)}" />`;
  const area = (n, val = "", rows = 2, ph = "") => `<textarea id="rh-${n}" name="${n}" class="control-textarea" rows="${rows}" placeholder="${esc(ph)}">${esc(val)}</textarea>`;
  const row2 = (a, b) => `<div class="form-row-2">${a}${b}</div>`;

  class ResearchHubController {
    constructor(getState, postJson, onRefresh, onInspect, modals, notify, onInspectTask = null) {
      Object.assign(this, { getState, postJson, onRefresh, onInspect, modals, notify, onInspectTask });
      this._bindToolbar();
    }

    _bindToolbar() {
      const on = (id, fn) => document.getElementById(id)?.addEventListener("click", fn);
      on("btn-open-bottleneck", () => this.openDiagnoseModal());
      on("btn-open-scout", () => this.openScoutModal());
      on("btn-open-method-card", () => this.openMethodCardModal());
      on("btn-open-sprint", () => this.openSprintModal());
      on("btn-dag-claim", () => this._claimTask(""));
      on("btn-dag-clear", async () => {
        try {
          const res = await this.postJson("/api/orchestrate", { action: "clear_done" });
          this.notify(tr(`Cleared ${res.cleared || 0} finished tasks`, `Đã dọn ${res.cleared || 0} tác vụ hoàn tất`));
          await this.onRefresh();
        } catch (err) { this.notify(err.message, true); }
      });
    }

    async _claimTask(taskId = "") {
      try {
        const res = await this.postJson("/api/orchestrate", { action: "claim", agent_name: "studio-coordinator", task_id: taskId });
        if (res.claimed) this.notify(tr(`Claimed ${res.claimed.task_id} (${res.claimed.role})`, `Đã nhận ${res.claimed.task_id} (${res.claimed.role})`));
        else this.notify(tr("No dependency-ready QUEUED task available.", "Chưa có tác vụ QUEUED nào đủ điều kiện chạy."));
        await this.onRefresh();
      } catch (err) { this.notify(err.message, true); }
    }

    openDiagnoseModal() {
      const html = fld("title", tr("Bottleneck Title *", "Tên điểm nghẽn (Bottleneck) *"), inp("title", "", "e.g. Night-time thermal overshoot on desert buildings")) +
        row2(fld("error_share_pct", tr("Error Share % (0-100] *", "Tỷ trọng lỗi % (0-100] *"), inp("error_share_pct", "42", "42")),
             fld("ceiling_gain", tr("Oracle Ceiling Gain (+) *", "Biên độ cải thiện tối đa (+) *"), inp("ceiling_gain", "0.08", "0.08"))) +
        row2(fld("metric_name", tr("Target Metric", "Chỉ số đo lường"), inp("metric_name", "primary_metric")),
             fld("smoke_eval_cmd", tr("10% Fast Smoke Command", "Lệnh Smoke Test 10%"), inp("smoke_eval_cmd", "pytest -q"))) +
        fld("evidence_slice", tr("Empirical Failure Slice & Evidence *", "Phân khúc lỗi thực nghiệm & Bằng chứng *"), area("evidence_slice", "", 2, "Quantify which validation slice fails and why...")) +
        fld("falsifiable_rq", tr("Falsifiable Research Question (RQ) *", "Câu hỏi nghiên cứu có thể kiểm chứng (RQ) *"), area("falsifiable_rq", "", 2, "Does mechanism X reduce slice error >= Y% without regressing latency?")) +
        fld("kill_criterion", tr("Early-Stop Kill Criterion (10% Budget)", "Tiêu chí dừng sớm (Kill Criterion ở 10% budget)"), inp("kill_criterion", "", "Abort if 10% smoke slice improves < 2%"));
      this.modals.open(tr("Diagnose Pareto Bottleneck & RQ", "Chẩn đoán Điểm nghẽn Pareto & RQ"), html, async (fd) => {
        if (!fd.title.trim() || !fd.evidence_slice.trim() || !fd.falsifiable_rq.trim()) {
          throw new Error(tr("Title, Failure Slice, and Falsifiable RQ are required.", "Cần nhập đủ Tên điểm nghẽn, Phân khúc lỗi và Câu hỏi RQ."));
        }
        await this.postJson("/api/bottlenecks", { action: "diagnose", ...fd });
        this.notify(tr("Registered Bottleneck + Research Question", "Đã lưu Điểm nghẽn + Câu hỏi nghiên cứu"));
        await this.onRefresh();
      });
    }

    openScoutModal() {
      const bnks = (this.getState().bottlenecks || []).filter((b) => b.status !== "RESOLVED");
      const html = fld("query", tr("Literature Search Query (arXiv + Semantic Scholar + OpenAlex) *", "Truy vấn bài báo SOTA (arXiv + S2 + OpenAlex) *"), inp("query", "", "e.g. model predictive control regret minimization")) +
        row2(fld("bottleneck_id", tr("Link to Bottleneck ID", "Gắn với mã Bottleneck"), inp("bottleneck_id", bnks[0]?.id || "", "BNK-001")),
             fld("save_top_k", tr("Auto-Save Top K Method Cards", "Tự lưu Top K Method Cards"), inp("save_top_k", "2", "2"))) +
        row2(fld("min_year", tr("Min Publication Year", "Năm xuất bản tối thiểu"), inp("min_year", "2023")),
             fld("limit", tr("Max Papers", "Số bài tối đa"), inp("limit", "6")));
      this.modals.open(tr("Scout SOTA Literature & Mint Method Cards", "Săn bài báo SOTA & Lưu Method Cards"), html, async (fd) => {
        if (!fd.query.trim()) throw new Error(tr("Please enter a literature search query.", "Vui lòng nhập từ khóa tìm kiếm bài báo."));
        const res = await this.postJson("/api/scout", { action: "search", ...fd });
        this.notify(tr(`Scouted ${res.papers.length} papers, saved ${res.saved_method_cards.length} cards`, `Tìm thấy ${res.papers.length} bài, đã lưu ${res.saved_method_cards.length} thẻ`));
        await this.onRefresh();
      });
    }

    openMethodCardModal() {
      const bnks = (this.getState().bottlenecks || []).filter((b) => b.status !== "RESOLVED");
      const html = fld("title", tr("Method / Paper Title *", "Tên phương pháp / Bài báo *"), inp("title", "", "e.g. Entropic Optimal Transport Assignment")) +
        row2(fld("bottleneck_id", tr("Target Bottleneck ID", "Mã Bottleneck mục tiêu"), inp("bottleneck_id", bnks[0]?.id || "", "BNK-001")),
             fld("complexity_cost", tr("Complexity Cost", "Độ phức tạp tính toán"), inp("complexity_cost", "O(N log N)"))) +
        row2(fld("venue", tr("Venue", "Hội nghị / Nguồn"), inp("venue", "NeurIPS")),
             fld("year", tr("Year", "Năm"), inp("year", "2025"))) +
        fld("core_mechanism", tr("Core Mathematical / Algorithmic Mechanism *", "Cơ chế toán học / thuật toán cốt lõi *"), area("core_mechanism", "", 2)) +
        fld("assumptions_and_limits", tr("Assumptions & Failure Modes", "Giả định & Giới hạn thất bại"), area("assumptions_and_limits", "", 2)) +
        fld("minimal_integration_hook", tr("Minimal Integration Hook (< 100 LOC)", "Điểm ghép tối giản vào code (< 100 dòng)"), inp("minimal_integration_hook", "", "Plug into ranker.py score_candidates()"));
      this.modals.open(tr("Register SOTA Method Card (METH-XXX)", "Thêm thẻ Phương pháp SOTA (METH-XXX)"), html, async (fd) => {
        if (!fd.title.trim() || !fd.core_mechanism.trim()) throw new Error(tr("Title and Core Mechanism are required.", "Cần nhập Tên phương pháp và Cơ chế cốt lõi."));
        await this.postJson("/api/scout", { action: "register_card", ...fd });
        this.notify(tr("Saved Method Card to 07_METHOD_VAULT", "Đã lưu Method Card vào 07_METHOD_VAULT"));
        await this.onRefresh();
      });
    }

    openSprintModal() {
      const bnks = (this.getState().bottlenecks || []).filter((b) => b.status !== "RESOLVED");
      const html = fld("goal", tr("Research Sprint Objective *", "Mục tiêu Sprint Nghiên cứu *"), inp("goal", "", "Isolate highest-Occam-ROI fix for top Pareto bottleneck")) +
        row2(fld("bottleneck_id", tr("Target Bottleneck ID", "Mã Bottleneck"), inp("bottleneck_id", bnks[0]?.id || "", "BNK-001")),
             fld("target_globs", tr("Wave-3 Glob Lease Lock", "Khóa vùng file Wave-3"), inp("target_globs", "src/**"))) +
        fld("smoke_cmd", tr("10% Smoke Gate Command", "Lệnh kiểm tra nhanh 10% Smoke Gate"), inp("smoke_cmd", "pytest -q"));
      this.modals.open(tr("Plan 3-Wave Multi-Agent Fast-DAG Sprint", "Lập kế hoạch Sprint 3-Wave Đa Agent"), html, async (fd) => {
        if (!fd.goal.trim()) throw new Error(tr("Please enter the Research Sprint Objective.", "Vui lòng nhập Mục tiêu Sprint Nghiên cứu."));
        const res = await this.postJson("/api/orchestrate", { action: "plan_sprint", ...fd });
        this.notify(tr(`Planned ${res.tasks.length} DAG tasks across 3 waves`, `Đã tạo ${res.tasks.length} tác vụ DAG qua 3 đợt`));
        await this.onRefresh();
      });
    }

    render(state) {
      const bnks = state.bottlenecks || [], cards = state.method_cards || [], tasks = state.agent_tasks || [], tel = state.dag_telemetry || {};
      const bnkBox = document.getElementById("bottlenecks-list"), cardBox = document.getElementById("method-vault-list"), dagBox = document.getElementById("dag-waves-board");
      if (!bnkBox || !cardBox || !dagBox) return;
      const readySet = new Set(tel.ready_parallel_task_ids || []);

      const bp = paginate(bnks, "bnk", 4);
      bnkBox.innerHTML = (bp.slice.length ? bp.slice.map((b) => `<article class="ledger-item-static ledger-item-clickable" data-inspect-rh="${esc(b.id)}">
        <div class="row-top"><span class="badge-cluster"><span class="mono-id">${esc(b.id)}</span>${statusTag(b.status)}</span><span class="role-chip">Pareto ${esc(b.pareto_priority)}</span></div>
        <h4 class="row-title">${esc(b.title)}</h4>
        <div class="pareto-row"><span>${esc(b.error_share_pct)}% ${tr("error share", "tỷ trọng lỗi")} &middot; +${esc(b.ceiling_gain)} ${esc(b.metric_name)}</span><span>${esc((b.candidate_ids || []).length)} ${tr("candidates", "ứng viên")}</span></div>
        <progress class="pareto-meter" max="100" value="${esc(Math.min(100, Number(b.error_share_pct) || 0))}"></progress>
        <p class="row-desc">${inlineMd(b.kill_criterion || b.summary)}</p>
        <div class="row-actions"><button type="button" class="btn btn-secondary btn-xs" data-inspect-btn="${esc(b.id)}">${tr("Inspect", "Chi tiết")}</button>
        ${b.rq_id ? `<button type="button" class="btn btn-ghost btn-xs" data-inspect-btn="${esc(b.rq_id)}">${esc(b.rq_id)}</button>` : ""}
        ${b.status !== "RESOLVED" ? `<button type="button" class="btn btn-ghost btn-xs" data-resolve-bnk="${esc(b.id)}">${tr("Mark Resolved", "Đánh dấu Xong")}</button>` : ""}</div>
      </article>`).join("") : `<div class="empty-state"><p class="empty-desc">${tr("No bottlenecks profiled yet. Click '+ Diagnose Bottleneck' to quantify error slices before proposing ideas.", "Chưa có điểm nghẽn nào. Nhấn '+ Chẩn đoán Điểm nghẽn' để định lượng lỗi trước khi đề xuất ý tưởng.")}</p></div>`) + bp.html;

      const mp = paginate(cards, "meth", 4);
      cardBox.innerHTML = (mp.slice.length ? mp.slice.map((m) => {
        const md = m.metadata || {};
        return `<article class="ledger-item-static ledger-item-clickable" data-inspect-rh="${esc(m.id)}">
          <div class="row-top"><span class="badge-cluster"><span class="mono-id">${esc(m.id)}</span><span class="role-chip">${esc(md.venue || "SOTA")} ${esc(md.year || "")}</span></span><span class="mono-tag">${esc(md.complexity_cost || "O(N)")}</span></div>
          <h4 class="row-title">${esc(m.title)}</h4>
          <p class="row-desc">${inlineMd(md.core_mechanism || m.summary)}</p>
          <div class="dag-meta-row">${md.bottleneck_id ? `<span class="mono-tag">${tr("Targets", "Đích")}: ${esc(md.bottleneck_id)}</span>` : "<span></span>"}<button type="button" class="btn btn-secondary btn-xs" data-inspect-btn="${esc(m.id)}">${tr("Read Card", "Đọc thẻ")}</button></div>
        </article>`;
      }).join("") : `<div class="empty-state"><p class="empty-desc">${tr("Method Vault is empty. Harvest papers from arXiv / Semantic Scholar / OpenAlex or add a curated Method Card.", "Kho phương pháp trống. Hãy săn bài báo từ arXiv / Semantic Scholar / OpenAlex hoặc thêm thẻ mới.")}</p></div>`) + mp.html;

      const pill = document.getElementById("dag-summary-pill");
      if (pill) pill.textContent = `${tasks.length} ${tr("tasks", "tác vụ")} · ${readySet.size} ${tr("parallel ready", "sẵn sàng song song")} · ${(tel.active_glob_leases || []).length} ${tr("glob leases", "khóa file")}`;

      const waves = [[1, tr("Wave 1 · Parallel Discovery", "Đợt 1 · Khám phá Song song")], [2, tr("Wave 2 · Occam & Red-Team Gate", "Đợt 2 · Lọc Occam & Phản biện")], [3, tr("Wave 3 · Locked Slice & 10% Smoke", "Đợt 3 · Thực thi Khóa file & Smoke 10%")]];
      dagBox.innerHTML = waves.map(([w, title]) => {
        const wTasks = tasks.filter((t) => Number(t.wave) === w);
        const body = wTasks.length ? wTasks.map((t) => `<div class="dag-card" data-task-id="${esc(t.task_id)}">
          <div class="row-top"><span class="badge-cluster"><span class="mono-id">${esc(t.task_id)}</span>${statusTag(t.status)}</span><span class="role-chip">${esc(t.role)}</span></div>
          <strong class="dag-title">${esc(t.title)}</strong>
          <p class="row-desc">${inlineMd(t.brief)}</p>
          <div class="pareto-row"><span>${esc(t.steps_done ?? 0)}/${esc(t.steps_total ?? 3)} ${tr("steps", "bước")}</span><strong>${esc(t.progress_pct ?? 0)}%</strong></div>
          <progress class="pareto-meter kanban-meter" max="100" value="${esc(t.progress_pct ?? 0)}"></progress>
          ${(t.locked_globs || []).length || t.claimed_by ? `<div class="dag-meta-row">${(t.locked_globs || []).length ? `<span class="mono-tag">Lease: ${esc(t.locked_globs.join(", "))}</span>` : ""}${t.claimed_by ? `<span class="mono-tag">Worker: ${esc(t.claimed_by)}</span>` : ""}</div>` : ""}
          ${t.receipt?.note ? `<p class="mono-id">${esc(t.receipt.note)}</p>` : ""}
          <div class="row-actions"><button type="button" class="btn btn-secondary btn-xs" data-dag-inspect="${esc(t.task_id)}">${tr("Details", "Chi tiết")}</button>
          ${readySet.has(t.task_id) ? `<button type="button" class="btn btn-secondary btn-xs" data-dag-claim="${esc(t.task_id)}">${tr("Claim Task", "Nhận việc")}</button>` : ""}
          ${t.status === "RUNNING" ? `<button type="button" class="btn btn-primary btn-xs" data-dag-done="${esc(t.task_id)}" data-dag-st="DONE">${tr("Complete", "Hoàn tất")}</button><button type="button" class="btn btn-danger btn-xs" data-dag-done="${esc(t.task_id)}" data-dag-st="EARLY_KILLED">${tr("10% Early-Kill", "Dừng sớm 10%")}</button>` : ""}</div>
        </div>`).join("") : `<div class="empty-state"><p class="empty-desc">${tr("No tasks in this wave.", "Chưa có tác vụ ở đợt này.")}</p></div>`;
        return `<div class="ledger-panel"><div class="ledger-header"><h3>${esc(title)}</h3><span class="nav-count">${wTasks.length}</span></div><div class="dag-col-body">${body}</div></div>`;
      }).join("");

      const root = document.getElementById("tab-research");
      bindPagers(root, () => this.render(this.getState()));
      root.querySelectorAll("[data-inspect-btn]").forEach((b) => b.addEventListener("click", (e) => { e.stopPropagation(); this.onInspect(b.dataset.inspectBtn); }));
      root.querySelectorAll("[data-inspect-rh]").forEach((el) => el.addEventListener("click", () => this.onInspect(el.dataset.inspectRh)));
      root.querySelectorAll("[data-dag-claim]").forEach((b) => b.addEventListener("click", () => this._claimTask(b.dataset.dagClaim)));
      root.querySelectorAll("[data-dag-inspect]").forEach((b) => b.addEventListener("click", () => this.onInspectTask?.(b.dataset.dagInspect)));
      root.querySelectorAll("[data-resolve-bnk]").forEach((b) => b.addEventListener("click", async (e) => {
        e.stopPropagation();
        try { await this.postJson("/api/bottlenecks", { action: "resolve", bottleneck_id: b.dataset.resolveBnk }); this.notify(tr("Bottleneck marked RESOLVED", "Đã đóng điểm nghẽn")); await this.onRefresh(); }
        catch (err) { this.notify(err.message, true); }
      }));
      root.querySelectorAll("[data-dag-done]").forEach((b) => b.addEventListener("click", async () => {
        try { await this.postJson("/api/orchestrate", { action: "complete", task_id: b.dataset.dagDone, status: b.dataset.dagSt, note: "Verified in Studio" }); await this.onRefresh(); }
        catch (err) { this.notify(err.message, true); }
      }));
    }
  }

  window.SuperMemoryResearchHub = { ResearchHubController };
})();
