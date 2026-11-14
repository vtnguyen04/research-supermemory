// Interactive 4-Tier Cognitive Hierarchy & Memory Merge / Consolidation Studio
(function () {
  const esc = (s) =>
    String(s ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

  class MergeStudioController {
    constructor(getState, getScope, onRefresh, onInspect, notify) {
      this.getState = getState;
      this.getScope = getScope;
      this.onRefresh = onRefresh;
      this.onInspect = onInspect;
      this.notify = notify || (() => {});
      this.selectedIds = new Set();
      this._bindButtonsImmediate();
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
        `Capsule đang nạp cho Agent: ~${activeTok} tokens / Tổng Vault: ~${totalTok} tokens ` +
        `(Tiết kiệm ${savedPct}% context • Đã gộp ${consCount} mảnh Episodic).`;

      const cols = [
        { key: "PROCEDURAL", title: "🛡 L1 PROCEDURAL (Luật, Quy trình, Gates)" },
        { key: "SEMANTIC", title: "💡 L2 SEMANTIC (Tri thức & Insight đúc kết)" },
        { key: "EPISODIC", title: "🧪 L3 EPISODIC (Thí nghiệm, Bài học, Proposals)" },
      ];
      const box = document.getElementById("tier-columns");
      box.innerHTML = cols
        .map((c) => {
          const items = (state.nodes || []).filter(
            (n) => n.memory_tier === c.key && (!hideCons || n.status !== "CONSOLIDATED")
          );
          const cards = items
            .map((n) => {
              const checked = this.selectedIds.has(n.id) ? "checked" : "";
              return `<div class="entity-card">
                <div class="check-row">
                  <input type="checkbox" class="merge-chk" data-id="${esc(n.id)}" ${checked} />
                  <div style="flex:1" data-inspect="${esc(n.id)}">
                    <div class="card-top">
                      <span class="card-id">${esc(n.id)}</span>
                      <span class="type-badge">${esc(n.node_type)} • ${esc(n.status)}</span>
                    </div>
                    <div class="card-title">${esc(n.title)}</div>
                    <div class="card-desc">${esc(n.summary).slice(0, 140)}</div>
                  </div>
                </div>
              </div>`;
            })
            .join("");
          return `<div class="tier-col"><h3>${c.title} (${items.length})</h3>
            <div class="card-stack">${cards || '<p class="muted">Trống</p>'}</div></div>`;
        })
        .join("");

      box.querySelectorAll(".merge-chk").forEach((chk) => {
        chk.onchange = (ev) => {
          const id = ev.target.getAttribute("data-id");
          if (ev.target.checked) this.selectedIds.add(id);
          else this.selectedIds.delete(id);
          this._updateButtonCount();
        };
      });
      box.querySelectorAll("[data-inspect]").forEach((el) => {
        el.onclick = () => this.onInspect(el.getAttribute("data-inspect"));
      });
      this._updateButtonCount();
    }

    _updateButtonCount() {
      const btn = document.getElementById("btn-merge-selected");
      if (btn) btn.textContent = `🧬 Gộp các mục đã chọn (${this.selectedIds.size})`;
    }

    _bindButtonsImmediate() {
      const mergeBtn = document.getElementById("btn-merge-selected");
      const autoBtn = document.getElementById("btn-auto-consolidate");
      const selEpBtn = document.getElementById("btn-select-episodic");
      const clearBtn = document.getElementById("btn-clear-merge-sel");
      const hideChk = document.getElementById("chk-hide-consolidated");
      const fb = document.getElementById("merge-feedback");

      if (hideChk) hideChk.onchange = () => this.render();
      if (selEpBtn) {
        selEpBtn.onclick = () => {
          (this.getState().nodes || [])
            .filter((n) => n.memory_tier === "EPISODIC" && n.status !== "CONSOLIDATED")
            .forEach((n) => this.selectedIds.add(n.id));
          this.render();
        };
      }
      if (clearBtn) {
        clearBtn.onclick = () => {
          this.selectedIds.clear();
          this.render();
        };
      }

      mergeBtn.onclick = async () => {
        const ids = Array.from(this.selectedIds);
        const title = document.getElementById("merge-title").value.trim();
        const summary = document.getElementById("merge-summary").value.trim();
        const tier = document.getElementById("merge-tier").value;
        if (!ids.length || !title || !summary) {
          fb.textContent = "⚠️ Hãy tích chọn ít nhất 1 node và nhập đủ Tiêu đề + Nội dung đúc kết.";
          return;
        }
        const res = await fetch("/api/consolidate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ scope: this.getScope(), source_ids: ids, target_tier: tier, title, summary }),
        });
        const data = await res.json();
        if (!res.ok) {
          fb.textContent = `❌ ${data.error || "Consolidation failed"}`;
          return;
        }
        this.selectedIds.clear();
        document.getElementById("merge-title").value = "";
        document.getElementById("merge-summary").value = "";
        fb.textContent = `✅ Đã gộp thành [${tier}] ${data.created_node.id}: ${data.created_node.title}`;
        this.notify(`✅ Đã tạo ${data.created_node.id} (${tier})`);
        await this.onRefresh();
      };

      autoBtn.onclick = async () => {
        const res = await fetch("/api/auto-consolidate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ scope: this.getScope(), min_cluster_size: 2 }),
        });
        const data = await res.json();
        const msg = data.count
          ? `⚡ Đã tự động gộp ${data.count} cụm: ${data.created_semantic_nodes.join(", ")}`
          : "ℹ️ Mọi cụm hiện tại đã gọn (< 2 mảnh Episodic chưa gộp / track).";
        fb.textContent = msg;
        this.notify(msg);
        await this.onRefresh();
      };
    }
  }

  window.SuperMemoryMergeStudio = { MergeStudioController };
})();
