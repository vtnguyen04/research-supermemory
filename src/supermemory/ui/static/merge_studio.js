// 4-Tier Cognitive Hierarchy & Paginated Memory Consolidation Workbench Controller
(function () {
  const { esc, statusTag, paginate, bindPagers, tr, cleanText } = window.SuperMemoryIcons;

  class MergeStudioController {
    constructor(getState, postJson, onRefresh, onInspect, notify) {
      Object.assign(this, { getState, postJson, onRefresh, onInspect, notify, selectedIds: new Set(), filterQuery: "" });
      this._bindControls();
    }

    render() {
      const state = this.getState();
      const tiers = state.cognitive_tiers || {};
      const activeTok = tiers.active_prompt_tokens || 0, totalTok = tiers.total_vault_tokens || 0;
      const savedPct = tiers.context_compression_pct || 0, consCount = tiers.consolidated_episodes || 0;
      const hideCons = document.getElementById("chk-hide-consolidated")?.checked;
      const q = this.filterQuery.toLowerCase();

      document.getElementById("tier-budget-summary").textContent = tr(
        `Active Agent Capsule: ~${activeTok} tok / Total Vault: ~${totalTok} tok (${savedPct}% context saved, ${consCount} L3 episodes consolidated).`,
        `Capsule nạp cho Agent: ~${activeTok} tok / Tổng kho lưu trữ: ~${totalTok} tok (Giảm ${savedPct}% ngữ cảnh, đã nén ${consCount} mảnh L3).`
      );

      const cols = [
        { key: "PROCEDURAL", title: tr("L1 Procedural — Laws & Gates", "L1 Procedural — Luật & Gates") },
        { key: "SEMANTIC", title: tr("L2 Semantic — Domain Knowledge", "L2 Semantic — Tri thức miền") },
        { key: "EPISODIC", title: tr("L3 Episodic — Experiments & Lessons", "L3 Episodic — Thực nghiệm & Bài học") },
      ];
      const box = document.getElementById("tier-columns");
      box.innerHTML = cols
        .map((c) => {
          const items = (state.nodes || []).filter((n) => {
            if (n.memory_tier !== c.key || (hideCons && n.status === "CONSOLIDATED")) return false;
            return !q || `${n.id} ${n.title} ${n.summary} ${n.node_type}`.toLowerCase().includes(q);
          });
          const pg = paginate(items, `tier-${c.key}`, 5);
          const rows = pg.slice
            .map((n) => {
              const checked = this.selectedIds.has(n.id) ? "checked" : "";
              return `<div class="selectable-row">
                <input type="checkbox" class="merge-chk" data-id="${esc(n.id)}" aria-label="${tr("Select", "Chọn")} ${esc(n.id)}" ${checked} />
                <button type="button" class="row-trigger" data-inspect="${esc(n.id)}">
                  <span class="row-top"><span class="mono-id">${esc(n.id)}</span>${statusTag(n.status, `${n.node_type} / ${n.status}`)}</span>
                  <span class="row-title">${esc(cleanText(n.title, 92))}</span>
                  <span class="row-desc">${esc(cleanText(n.summary, 135))}</span>
                </button></div>`;
            })
            .join("");
          const empty = `<div class="empty-state"><p class="empty-title">${tr("Tier is empty", "Tầng này đang trống")}</p><p class="empty-desc">${tr("No entities match the current filter.", "Không có thực thể nào khớp bộ lọc hiện tại.")}</p></div>`;
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
      if (btn) btn.textContent = tr(`Consolidate Selected (${this.selectedIds.size})`, `Gộp mục đã chọn (${this.selectedIds.size})`);
    }

    _bindControls() {
      const fb = document.getElementById("merge-feedback");
      document.getElementById("chk-hide-consolidated").addEventListener("change", () => this.render());
      document.getElementById("tier-filter-input")?.addEventListener("input", (ev) => {
        this.filterQuery = ev.target.value.trim();
        this.render();
      });
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
          fb.textContent = tr("Select at least 1 source item and provide Title + Synthesized Principle.", "Chọn ít nhất 1 mục nguồn và điền đủ Tiêu đề + Nguyên lý tổng hợp.");
          return;
        }
        try {
          const data = await this.postJson("/api/consolidate", { source_ids: ids, target_tier: tier, title, summary });
          this.selectedIds.clear();
          document.getElementById("merge-title").value = "";
          document.getElementById("merge-summary").value = "";
          fb.textContent = tr(`Consolidated into [${tier}] ${data.created_node.id}: ${data.created_node.title}`, `Đã chưng cất thành [${tier}] ${data.created_node.id}: ${data.created_node.title}`);
          this.notify(tr(`Created ${data.created_node.id} (${tier})`, `Đã tạo ${data.created_node.id} (${tier})`));
          await this.onRefresh();
        } catch (err) { fb.textContent = err.message; }
      });
      document.getElementById("btn-auto-consolidate").addEventListener("click", async () => {
        try {
          const data = await this.postJson("/api/auto-consolidate", { min_cluster_size: 2 });
          const msg = data.count
            ? tr(`Auto-consolidated ${data.count} clusters: ${data.created_semantic_nodes.join(", ")}`, `Đã tự động gộp ${data.count} cụm: ${data.created_semantic_nodes.join(", ")}`)
            : tr("No L3 clusters with 2+ items need consolidation yet.", "Chưa có cụm L3 nào từ 2 mục trở lên cần gộp.");
          fb.textContent = msg; this.notify(msg); await this.onRefresh();
        } catch (err) { fb.textContent = err.message; }
      });
    }
  }

  window.SuperMemoryMergeStudio = { MergeStudioController };
})();
