// 4-Tier Cognitive Hierarchy & Paginated Memory Consolidation Workbench Controller
(function () {
  const { esc, statusTag, paginate, bindPagers } = window.SuperMemoryIcons;

  class MergeStudioController {
    constructor(getState, postJson, onRefresh, onInspect, notify) {
      this.getState = getState;
      this.postJson = postJson;
      this.onRefresh = onRefresh;
      this.onInspect = onInspect;
      this.notify = notify;
      this.selectedIds = new Set();
      this._bindControls();
    }

    render() {
      const state = this.getState();
      const tiers = state.cognitive_tiers || {};
      const activeTok = tiers.active_prompt_tokens || 0;
      const totalTok = tiers.total_vault_tokens || 0;
      const savedPct = tiers.context_compression_pct || 0;
      const consCount = tiers.consolidated_episodes || 0;
      const hideCons = document.getElementById("chk-hide-consolidated")?.checked;

      document.getElementById("tier-budget-summary").textContent =
        `Capsule nạp cho Agent: ~${activeTok} tok / Tổng kho lưu trữ: ~${totalTok} tok ` +
        `(Giảm ${savedPct}% ngữ cảnh, đã nén ${consCount} mảnh L3).`;

      const cols = [
        { key: "PROCEDURAL", title: "L1 Procedural — Luật & Gates" },
        { key: "SEMANTIC", title: "L2 Semantic — Tri thức miền" },
        { key: "EPISODIC", title: "L3 Episodic — Thực nghiệm & Bài học" },
      ];
      const box = document.getElementById("tier-columns");
      box.innerHTML = cols
        .map((c) => {
          const items = (state.nodes || []).filter(
            (n) => n.memory_tier === c.key && (!hideCons || n.status !== "CONSOLIDATED")
          );
          const pg = paginate(items, `tier-${c.key}`, 5);
          const rows = pg.slice
            .map((n) => {
              const checked = this.selectedIds.has(n.id) ? "checked" : "";
              return `<div class="selectable-row">
                <input type="checkbox" class="merge-chk" data-id="${esc(n.id)}" aria-label="Chọn ${esc(n.id)}" ${checked} />
                <button type="button" class="row-trigger" data-inspect="${esc(n.id)}">
                  <span class="row-top"><span class="mono-id">${esc(n.id)}</span>${statusTag(n.status, `${n.node_type} / ${n.status}`)}</span>
                  <span class="row-title">${esc(n.title)}</span>
                  <span class="row-desc">${esc(n.summary).slice(0, 125)}</span>
                </button></div>`;
            })
            .join("");
          const empty = `<div class="empty-state"><p class="empty-title">Tầng này đang trống</p><p class="empty-desc">Không có thực thể nào khớp bộ lọc hiện tại.</p></div>`;
          return `<div class="ledger-panel">
            <div class="ledger-header"><h3>${esc(c.title)}</h3><span class="mono-id">${items.length}</span></div>
            <div class="ledger-list">${rows || empty}</div>${pg.html}</div>`;
        })
        .join("");

      box.querySelectorAll(".merge-chk").forEach((chk) => {
        chk.addEventListener("change", (ev) => {
          const id = ev.target.getAttribute("data-id");
          if (ev.target.checked) this.selectedIds.add(id);
          else this.selectedIds.delete(id);
          this._syncSubmitLabel();
        });
      });
      box.querySelectorAll("[data-inspect]").forEach((btn) => {
        btn.addEventListener("click", () => this.onInspect(btn.getAttribute("data-inspect")));
      });
      bindPagers(box, () => this.render());
      this._syncSubmitLabel();
    }

    _syncSubmitLabel() {
      const btn = document.getElementById("btn-merge-selected");
      if (btn) btn.textContent = `Gộp mục đã chọn (${this.selectedIds.size})`;
    }

    _bindControls() {
      const fb = document.getElementById("merge-feedback");
      document.getElementById("chk-hide-consolidated").addEventListener("change", () => this.render());
      document.getElementById("btn-select-episodic").addEventListener("click", () => {
        (this.getState().nodes || [])
          .filter((n) => n.memory_tier === "EPISODIC" && n.status !== "CONSOLIDATED")
          .forEach((n) => this.selectedIds.add(n.id));
        this.render();
      });
      document.getElementById("btn-clear-merge-sel").addEventListener("click", () => {
        this.selectedIds.clear();
        this.render();
      });
      document.getElementById("merge-form").addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const ids = Array.from(this.selectedIds);
        const title = document.getElementById("merge-title").value.trim();
        const summary = document.getElementById("merge-summary").value.trim();
        const tier = document.getElementById("merge-tier").value;
        if (!ids.length || !title || !summary) {
          fb.textContent = "Vui lòng chọn ít nhất 1 mục nguồn và điền đủ Tiêu đề cùng Nguyên lý tổng hợp.";
          return;
        }
        try {
          const data = await this.postJson("/api/consolidate", { source_ids: ids, target_tier: tier, title, summary });
          this.selectedIds.clear();
          document.getElementById("merge-title").value = "";
          document.getElementById("merge-summary").value = "";
          fb.textContent = `Đã chưng cất thành [${tier}] ${data.created_node.id}: ${data.created_node.title}`;
          this.notify(`Đã tạo ${data.created_node.id} (${tier})`);
          await this.onRefresh();
        } catch (err) { fb.textContent = err.message; }
      });
      document.getElementById("btn-auto-consolidate").addEventListener("click", async () => {
        try {
          const data = await this.postJson("/api/auto-consolidate", { min_cluster_size: 2 });
          const msg = data.count ? `Đã tự động gộp ${data.count} cụm: ${data.created_semantic_nodes.join(", ")}` : "Chưa có cụm L3 nào từ 2 mục trở lên cần gộp.";
          fb.textContent = msg; this.notify(msg); await this.onRefresh();
        } catch (err) { fb.textContent = err.message; }
      });
    }
  }

  window.SuperMemoryMergeStudio = { MergeStudioController };
})();
