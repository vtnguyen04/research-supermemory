// Flexible Split-Pane / Floating Inspector with History, Graph Focus, Copy MD & Gate View
(function () {
  const { esc, statusTag, tr, cleanText, renderMarkdown, svg } = window.SuperMemoryIcons;

  function formatMetaSection(meta) {
    const entries = Object.entries(meta || {}).filter(([, v]) => v !== null && v !== "" && !(Array.isArray(v) && !v.length));
    if (!entries.length) return "";
    const rows = entries.map(([k, v]) => {
      const label = k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()).replace(/\bId\b/g, "ID").replace(/\bSha\b/g, "SHA");
      const valHtml = Array.isArray(v)
        ? v.map((x) => `<code class="md-code">${esc(typeof x === "object" ? JSON.stringify(x) : x)}</code>`).join(" ")
        : typeof v === "object"
          ? Object.entries(v).map(([sk, sv]) => `<code class="md-code">${esc(sk)}: ${esc(sv)}</code>`).join(" ")
          : `<span class="prop-val">${esc(v)}</span>`;
      return `<span class="prop-key">${esc(label)}</span><span>${valHtml}</span>`;
    }).join("");
    return `<div class="inspector-section"><h3 class="inspector-subhead">${tr("Attributes & Metadata", "Thuộc tính mở rộng")}</h3><div class="prop-grid meta-grid">${rows}</div></div>`;
  }

  class InspectorController {
    constructor(getState, getScope, postJson, onRefresh, modals, notify, callbacks = {}) {
      Object.assign(this, { getState, getScope, postJson, onRefresh, modals, notify, callbacks, currentNodeId: null, history: [] });
      this.isDocked = localStorage.getItem("sm_insp_dock") !== "float";
      this.isWide = localStorage.getItem("sm_insp_wide") === "1";
      this.drawer = document.getElementById("inspector-drawer");
      this.backdrop = document.getElementById("inspector-backdrop");
      this.backBtn = document.getElementById("btn-insp-back");
      this.dockBtn = document.getElementById("btn-dock-inspector");
      this.wideBtn = document.getElementById("btn-wide-inspector");
      this._syncModeClasses(false);
      this._bindChrome();
    }

    _bindChrome() {
      document.getElementById("btn-close-inspector").addEventListener("click", () => this.close());
      this.backdrop.addEventListener("click", () => this.close());
      this.backBtn.addEventListener("click", () => { const prev = this.history.pop(); if (prev) this.inspect(prev, false); });
      this.dockBtn.addEventListener("click", () => this.toggleDock());
      this.wideBtn.addEventListener("click", () => { this.isWide = !this.isWide; localStorage.setItem("sm_insp_wide", this.isWide ? "1" : "0"); this._syncModeClasses(Boolean(this.currentNodeId)); });
      document.addEventListener("click", (ev) => {
        if (this.isDocked || !this.currentNodeId || ev.target.closest("#inspector-drawer, #graph-canvas, .row-trigger, .ledger-row, [data-nid], [data-gate-inspect], [data-jump], dialog, button, a, input, select, textarea, label")) return;
        this.close();
      });
    }
    toggleDock() { this.isDocked = !this.isDocked; localStorage.setItem("sm_insp_dock", this.isDocked ? "dock" : "float"); this._syncModeClasses(Boolean(this.currentNodeId)); }

    _syncModeClasses(isOpen) {
      const sig = `${this.isDocked}:${this.isWide}:${isOpen}`, changed = this._layoutSig !== sig;
      this._layoutSig = sig;
      document.body.classList.toggle("insp-docked", this.isDocked);
      document.body.classList.toggle("insp-wide", this.isWide);
      document.body.classList.toggle("insp-open", isOpen);
      this.dockBtn.setAttribute("aria-pressed", String(this.isDocked));
      this.wideBtn.setAttribute("aria-pressed", String(this.isWide));
      this.backBtn.disabled = !this.history.length;
      if (changed) requestAnimationFrame(() => this.callbacks.onLayoutChange?.());
    }

    _openChrome(badgeTxt, headingTxt) {
      this.drawer.classList.add("is-open");
      this.drawer.setAttribute("aria-hidden", "false");
      this.backdrop.classList.toggle("hidden", this.isDocked);
      document.getElementById("insp-badge").textContent = badgeTxt;
      document.getElementById("insp-id").textContent = headingTxt;
      this._syncModeClasses(true);
    }

    close() {
      this.currentNodeId = null; this.history = [];
      this.drawer.classList.remove("is-open");
      this.drawer.setAttribute("aria-hidden", "true");
      this.backdrop.classList.add("hidden");
      this._syncModeClasses(false);
      this.callbacks.onClearSelection?.();
    }

    resetEmpty() { this.close(); document.getElementById("insp-body").innerHTML = ""; }

    inspectGate(gate) {
      if (!gate) return;
      if (this.currentNodeId && !this.currentNodeId.startsWith("GATE:")) this.history.push(this.currentNodeId);
      this.currentNodeId = `GATE:${gate.id}`;
      this._openChrome(`PROCEDURAL / ${gate.gate_type}`, `${gate.id} — ${gate.name}`);
      document.getElementById("insp-body").innerHTML = `
        <div class="row-actions">
          <button type="button" id="btn-edit-gate-insp" class="btn btn-primary btn-sm">${tr("Edit Gate", "Sửa Gate")}</button>
          <button type="button" id="btn-toggle-gate-insp" class="btn btn-secondary btn-sm">${gate.enabled ? tr("Pause Gate", "Tạm tắt") : tr("Enable Gate", "Bật lại")}</button>
          ${gate.law_id ? `<button type="button" id="btn-jump-gate-law" class="btn btn-secondary btn-sm">${tr("Open", "Mở")} ${esc(gate.law_id)}</button>` : ""}
        </div>
        <div class="prop-grid">
          <span class="prop-key">Gate ID</span><span class="prop-val">${esc(gate.id)}</span>
          <span class="prop-key">${tr("Type", "Loại Gate")}</span><span class="prop-val">${esc(gate.gate_type)}</span>
          <span class="prop-key">${tr("Status", "Trạng thái")}</span><span>${statusTag(gate.enabled ? "ENABLED" : "DISABLED", gate.enabled ? tr("ENABLED", "ĐANG BẬT") : tr("PAUSED", "TẠM TẮT"))}</span>
          <span class="prop-key">Target Glob</span><span class="prop-val"><code class="md-code">${esc(gate.target_glob)}</code></span>
          <span class="prop-key">${tr("Blocks", "Đã chặn")}</span><span class="prop-val">${esc(gate.blocked_count || 0)}${gate.last_blocked_at ? ` (${esc(gate.last_blocked_at.slice(0, 19))})` : ""}</span>
        </div>
        <div class="inspector-section">
          <h3 class="inspector-subhead">${tr("Full Rule Pattern / SHA-256 Signature", "Biểu thức Regex / Chữ ký SHA-256 đầy đủ")}</h3>
          <pre class="code-block"><code>${esc(gate.pattern || "—")}</code></pre>
        </div>
        ${formatMetaSection(gate.config)}`;
      document.getElementById("btn-edit-gate-insp").addEventListener("click", () => this.modals.openAddGate(gate));
      document.getElementById("btn-toggle-gate-insp").addEventListener("click", async () => {
        await this.postJson("/api/gates", { action: "toggle", gate_id: gate.id, enabled: !gate.enabled });
        await this.onRefresh();
        const updated = (this.getState().gates || []).find((x) => x.id === gate.id);
        if (updated) this.inspectGate(updated);
      });
      document.getElementById("btn-jump-gate-law")?.addEventListener("click", () => this.inspect(gate.law_id));
    }

    async inspect(nodeId, pushHistory = true) {
      if (!nodeId) return;
      if (pushHistory && this.currentNodeId && this.currentNodeId !== nodeId && !this.currentNodeId.startsWith("GATE:")) this.history.push(this.currentNodeId);
      const res = await fetch(`/api/node/${encodeURIComponent(nodeId)}?scope=${encodeURIComponent(this.getScope())}`);
      if (!res.ok) { this.notify(tr(`Entity not found: ${nodeId}`, `Không tìm thấy thực thể ${nodeId}`), true); return; }
      const { node, edges } = await res.json(), state = this.getState();
      this.currentNodeId = node.id;
      this._openChrome(`${node.memory_tier || "SEMANTIC"} / ${node.node_type}`, `${node.id} — ${cleanText(node.title, 96)}`);

      const promoteBtn = !state.is_global ? `<button type="button" id="btn-promote-global" class="btn btn-secondary btn-sm">${tr("Promote", "Lên Global")}</button>` : "";
      const fileRow = node.file_path ? `<span class="prop-key">${tr("Source File", "Tệp nguồn")}</span><span class="prop-val"><a class="file-anchor" href="file://${esc(node.file_path)}" target="_blank" rel="noreferrer">${esc(node.file_path)}</a></span>` : "";
      const edgeRows = edges.map((e) => {
        const out = e.source_id === node.id, jump = out ? e.target_id : e.source_id, lbl = out ? `${e.relation} → ${jump}` : `${jump} → ${e.relation}`;
        return `<div class="edge-item"><button type="button" class="edge-btn" data-jump="${esc(jump)}"><span>${esc(lbl)}</span><span class="muted">${tr("Open", "Mở")}</span></button>
          <button type="button" class="icon-btn edge-del-btn" data-del-src="${esc(e.source_id)}" data-del-dst="${esc(e.target_id)}" data-del-rel="${esc(e.relation)}" title="${tr("Unlink edge", "Gỡ cạnh liên kết")}">${svg("x", 13)}</button></div>`;
      }).join("");
      const targetOpts = (state.nodes || []).filter((x) => x.id !== node.id).slice(0, 120).map((x) => `<option value="${esc(x.id)}">${esc(x.id)} — ${esc(cleanText(x.title, 36))}</option>`).join("");
      const relOpts = ["REFERENCES", "GOVERNED_BY", "DERIVED_FROM", "CONSOLIDATED_INTO", "VERIFIED_BY", "INSPIRED"].map((r) => `<option value="${r}">${r}</option>`).join("");
      const mdRaw = String(node.content || node.summary || "").trim();

      document.getElementById("insp-body").innerHTML = `
        <div class="row-actions">
          <button type="button" id="btn-edit-node" class="btn btn-primary btn-sm">${tr("Edit", "Chỉnh sửa")}</button>
          <button type="button" id="btn-focus-graph" class="btn btn-secondary btn-sm">${svg("crosshair", 14)} ${tr("Focus in Graph", "Định vị Graph")}</button>
          <button type="button" id="btn-copy-md" class="btn btn-secondary btn-sm">${svg("copy", 14)} ${tr("Copy", "Sao chép")}</button>
          ${promoteBtn}
          <span id="insp-del-zone"><button type="button" id="btn-arm-del-node" class="btn btn-danger btn-sm">${tr("Delete", "Xóa")}</button></span>
        </div>
        <div class="prop-grid">
          <span class="prop-key">${tr("Entity ID", "Mã thực thể")}</span><span class="prop-val">${esc(node.id)}</span>
          <span class="prop-key">${tr("Cognitive Tier", "Tầng nhận thức")}</span><span class="prop-val">${esc(node.memory_tier || "SEMANTIC")} &middot; ${esc(node.node_type)}</span>
          <span class="prop-key">${tr("Status", "Trạng thái")}</span><span>${statusTag(node.status)}</span>
          <span class="prop-key">${tr("Updated", "Cập nhật")}</span><span class="prop-val">${esc((node.updated_at || "").slice(0, 19))}</span>
          ${fileRow}
        </div>
        <div class="inspector-section"><h3 class="inspector-subhead">${tr("Content & Details", "Nội dung chi tiết")}</h3><article class="md-prose">${renderMarkdown(mdRaw, true)}</article></div>
        <div class="inspector-section"><h3 class="inspector-subhead">${tr("Link Edge from", "Nối cạnh liên kết từ")} ${esc(node.id)}</h3>
          <div class="link-composer"><select id="link-rel" class="control-select" aria-label="Edge relation">${relOpts}</select>
            <select id="link-dst" class="control-select" aria-label="Target entity">${targetOpts}</select>
            <button type="button" id="btn-add-edge" class="btn btn-secondary btn-sm">${tr("Link", "Nối cạnh")}</button></div></div>
        <div class="inspector-section"><h3 class="inspector-subhead">${tr("Graph Edges", "Liên kết đồ thị")} (${edges.length})</h3>
          <div class="edge-list">${edgeRows || `<p class="empty-desc">${tr("No direct graph edges yet.", "Chưa có cạnh liên kết trực tiếp.")}</p>`}</div></div>
        ${formatMetaSection(node.metadata)}`;
      this._bindNodeActions(node, mdRaw);
    }

    _bindNodeActions(node, mdRaw) {
      document.getElementById("btn-edit-node").addEventListener("click", () => this.modals.openUpsertNode(node));
      document.getElementById("btn-focus-graph").addEventListener("click", () => this.callbacks.onFocusGraph?.(node.id));
      document.getElementById("btn-copy-md").addEventListener("click", async () => {
        await navigator.clipboard?.writeText(`# ${node.id}: ${node.title}\n\n${mdRaw}`);
        this.notify(tr(`Copied ${node.id} Markdown`, `Đã sao chép Markdown của ${node.id}`));
      });
      document.getElementById("btn-promote-global")?.addEventListener("click", async () => {
        try { const out = await this.postJson("/api/promote", { node_id: node.id }); this.notify(tr(`Promoted: ${out.global_id}`, `Đã chuyển lên Global: ${out.global_id}`)); await this.onRefresh(); }
        catch (err) { this.notify(err.message, true); }
      });
      const bindArm = () => document.getElementById("btn-arm-del-node")?.addEventListener("click", () => {
        const z = document.getElementById("insp-del-zone");
        z.innerHTML = `<button type="button" id="btn-confirm-del-node" class="btn btn-danger btn-sm">${tr("Confirm", "Xác nhận")}</button><button type="button" id="btn-cancel-del-node" class="btn btn-ghost btn-sm">${tr("Cancel", "Hủy")}</button>`;
        document.getElementById("btn-cancel-del-node").addEventListener("click", () => { z.innerHTML = `<button type="button" id="btn-arm-del-node" class="btn btn-danger btn-sm">${tr("Delete", "Xóa")}</button>`; bindArm(); });
        document.getElementById("btn-confirm-del-node").addEventListener("click", async () => {
          try { await this.postJson("/api/node/delete", { node_id: node.id }); this.notify(tr(`Deleted ${node.id}`, `Đã xóa ${node.id}`)); this.resetEmpty(); await this.onRefresh(); }
          catch (err) { this.notify(err.message, true); }
        });
      });
      bindArm();
      document.getElementById("btn-add-edge").addEventListener("click", async () => {
        const dst = document.getElementById("link-dst").value, rel = document.getElementById("link-rel").value;
        if (!dst) return;
        try { await this.postJson("/api/edge/add", { source_id: node.id, target_id: dst, relation: rel }); await this.onRefresh(); await this.inspect(node.id, false); }
        catch (err) { this.notify(err.message, true); }
      });
      document.getElementById("insp-body").querySelectorAll("[data-jump]").forEach((b) => b.addEventListener("click", () => this.inspect(b.getAttribute("data-jump"), true)));
      document.getElementById("insp-body").querySelectorAll("[data-del-src]").forEach((b) => b.addEventListener("click", async () => {
        await this.postJson("/api/edge/delete", { source_id: b.dataset.delSrc, target_id: b.dataset.delDst, relation: b.dataset.delRel });
        this.notify(tr("Unlinked edge", "Đã gỡ cạnh liên kết")); await this.onRefresh(); await this.inspect(node.id, false);
      }));
    }
  }
  window.SuperMemoryInspector = { InspectorController };
})();
