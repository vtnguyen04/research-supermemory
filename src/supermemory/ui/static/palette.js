// Live Federated Search Popover & Keyboard Command Palette (/ or Ctrl+K)
(function () {
  const { esc, tr, cleanText } = window.SuperMemoryIcons;

  class SearchPaletteController {
    constructor(getScope, setScope, onInspect, onFocusGraph, commands, onHighlightGraph) {
      Object.assign(this, { getScope, setScope, onInspect, onFocusGraph, commands, onHighlightGraph, items: [], activeIdx: 0, lastResults: [] });
      this.input = document.getElementById("global-search");
      this.clearBtn = document.getElementById("btn-clear-search");
      this.kbd = document.getElementById("search-kbd");
      this.popover = document.getElementById("search-popover");
      this.banner = document.getElementById("anti-repeat-banner");
      this._bind();
    }

    close() {
      this.popover.classList.add("hidden");
    }

    _buildCommands() {
      return [
        { kind: "cmd", id: "new-node", label: tr("+ Create Knowledge / Procedure Entity", "+ Tạo thực thể Tri thức / Quy trình"), hint: "Entity", run: this.commands.newNode },
        { kind: "cmd", id: "new-exp", label: tr("+ Log Scientific Experiment", "+ Ghi nhận Thực nghiệm mới"), hint: "L3 Exp", run: this.commands.newExp },
        { kind: "cmd", id: "new-prop", label: tr("+ Create OpenSpec Proposal", "+ Tạo OpenSpec Proposal"), hint: "Spec", run: this.commands.newProp },
        { kind: "cmd", id: "new-lesson", label: tr("+ Record Lesson & PreToolUse CodeGate", "+ Ghi Bài học & Ràng buộc CodeGate"), hint: "Law+Gate", run: this.commands.newLesson },
        { kind: "cmd", id: "audit", label: tr("Run Full Workspace CodeGate Audit", "Chạy kiểm định toàn bộ CodeGate"), hint: "Audit", run: this.commands.runAudit },
        { kind: "cmd", id: "handoff", label: tr("Generate Zero-Loss Handoff Briefing", "Xuất bản bàn giao Handoff Briefing"), hint: "Markdown", run: this.commands.handoff },
        { kind: "cmd", id: "dock", label: tr("Toggle Center Modal / Split-Pane Inspector (F)", "Phóng to Giữa màn hình / Ghim cạnh Inspector (F)"), hint: "F", run: this.commands.toggleDock },
      ];
    }

    _renderPopover(q) {
      if (!q) {
        const cmds = this._buildCommands();
        this.items = cmds;
        this.activeIdx = Math.min(this.activeIdx, Math.max(0, cmds.length - 1));
        this.popover.innerHTML = `<div class="pop-head">${tr("Quick Studio Commands · Type to search Local + Global memory", "Lệnh nhanh Studio · Nhập từ khóa để tìm trên Local + Global")}</div>` +
          cmds.map((c, idx) => `<button type="button" class="pop-item${idx === this.activeIdx ? " is-active" : ""}" data-cidx="${idx}">
            <span class="pop-title">${esc(c.label)}</span><span class="mono-id">${esc(c.hint)}</span></button>`).join("");
        this.popover.classList.remove("hidden");
        this.popover.querySelectorAll("[data-cidx]").forEach((btn) => btn.addEventListener("click", () => this._activate(Number(btn.dataset.cidx))));
        return;
      }

      const res = this.lastResults;
      this.items = res.map((r) => ({ kind: "node", data: r }));
      this.activeIdx = Math.min(this.activeIdx, Math.max(0, this.items.length - 1));
      if (!res.length) {
        this.popover.innerHTML = `<div class="pop-empty">${tr(`No entities matched "${q}" in Local or Global memory.`, `Không tìm thấy kết quả khớp "${q}" trong bộ nhớ Local và Global.`)}</div>`;
        this.popover.classList.remove("hidden");
        return;
      }

      this.popover.innerHTML = `<div class="pop-head">${tr(`Federated Recall (${res.length} matches across Local + Global)`, `Kết quả truy hồi liên kết (${res.length} mục từ Local + Global)`)}</div>` +
        res.map((r, idx) => {
          const scopeBadge = r.scope === "GLOBAL" ? "GLOBAL" : "LOCAL";
          return `<div class="pop-row${idx === this.activeIdx ? " is-active" : ""}">
            <button type="button" class="pop-main" data-ridx="${idx}">
              <span class="row-top"><span class="scope-mini scope-${scopeBadge.toLowerCase()}">${scopeBadge}</span><span class="mono-id">${esc(r.type)} &middot; ${esc(r.id)}</span></span>
              <span class="pop-title">${esc(cleanText(r.title, 88))}</span>
              <span class="pop-sub">${esc(cleanText(r.summary, 115))}</span>
            </button>
            <button type="button" class="btn btn-secondary btn-xs pop-graph-btn" data-gidx="${idx}">${tr("Graph", "Đồ thị")}</button>
          </div>`;
        }).join("");
      this.popover.classList.remove("hidden");
      this.popover.querySelectorAll("[data-ridx]").forEach((b) => b.addEventListener("click", () => this._activate(Number(b.dataset.ridx))));
      this.popover.querySelectorAll("[data-gidx]").forEach((b) => b.addEventListener("click", () => this._jumpGraph(Number(b.dataset.gidx))));
    }

    async _jumpGraph(idx) {
      const entry = this.items[idx];
      if (!entry || entry.kind !== "node") return;
      this.close();
      const r = entry.data;
      if (r.scope === "GLOBAL" && this.getScope() !== "global") await this.setScope("global");
      this.onFocusGraph(r.id);
    }

    async _activate(idx) {
      const entry = this.items[idx];
      if (!entry) return;
      this.close();
      if (entry.kind === "cmd") { entry.run(); return; }
      const r = entry.data;
      if (r.scope === "GLOBAL" && this.getScope() !== "global") await this.setScope("global");
      this.onInspect(r.id);
    }

    _bind() {
      let timer = null;
      this.input.addEventListener("focus", () => { this.activeIdx = 0; this._renderPopover(this.input.value.trim()); });
      this.input.addEventListener("input", () => {
        const q = this.input.value.trim();
        this.clearBtn.classList.toggle("hidden", !this.input.value);
        this.kbd.classList.toggle("hidden", Boolean(this.input.value));
        clearTimeout(timer);
        if (!q) {
          this.lastResults = []; this.onHighlightGraph(new Set()); this.banner.classList.add("hidden");
          this.activeIdx = 0; this._renderPopover(""); return;
        }
        timer = setTimeout(async () => {
          const data = await (await fetch(`/api/search?q=${encodeURIComponent(q)}&scope=${encodeURIComponent(this.getScope())}`)).json();
          this.lastResults = data.results || [];
          this.onHighlightGraph(new Set(this.lastResults.map((r) => r.id)));
          this.banner.classList.toggle("hidden", !data.anti_repeat_warnings?.length);
          this.banner.innerHTML = data.anti_repeat_warnings?.length ? `<span>${tr("Dead-End Anti-Repeat Warning:", "Cảnh báo trùng hướng thất bại:")} ${data.anti_repeat_warnings.map(esc).join(" | ")}</span>` : "";
          this.activeIdx = 0; this._renderPopover(q);
        }, 160);
      });

      this.input.addEventListener("keydown", (ev) => {
        if (this.popover.classList.contains("hidden") || !this.items.length) return;
        if (ev.key === "ArrowDown") { ev.preventDefault(); this.activeIdx = (this.activeIdx + 1) % this.items.length; this._renderPopover(this.input.value.trim()); }
        else if (ev.key === "ArrowUp") { ev.preventDefault(); this.activeIdx = (this.activeIdx - 1 + this.items.length) % this.items.length; this._renderPopover(this.input.value.trim()); }
        else if (ev.key === "Enter") { ev.preventDefault(); this._activate(this.activeIdx); }
        else if (ev.key === "Escape") { ev.preventDefault(); this.close(); this.input.blur(); }
      });

      this.clearBtn.addEventListener("click", () => {
        this.input.value = ""; this.lastResults = []; this.clearBtn.classList.add("hidden"); this.kbd.classList.remove("hidden");
        this.onHighlightGraph(new Set()); this.banner.classList.add("hidden"); this.close();
      });

      document.addEventListener("mousedown", (ev) => {
        if (!ev.target.closest(".search-wrap")) this.close();
      });

      window.addEventListener("keydown", (ev) => {
        if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "k") { ev.preventDefault(); this.input.focus(); this.input.select(); }
        else if (ev.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) { ev.preventDefault(); this.input.focus(); }
      });
    }
  }

  window.SuperMemoryPalette = { SearchPaletteController };
})();
