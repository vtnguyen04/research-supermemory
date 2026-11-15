// Contextual Floating Slide-Over Inspector Sheet with Inline 2-Step Confirmation
(function () {
  const { esc, statusTag, tr } = window.SuperMemoryIcons;

  class InspectorController {
    constructor(getState, getScope, postJson, onRefresh, onOpenEditModal, notify, onClearSelection) {
      Object.assign(this, { getState, getScope, postJson, onRefresh, onOpenEditModal, notify, onClearSelection, currentNodeId: null });
      this.drawer = document.getElementById("inspector-drawer");
      this.backdrop = document.getElementById("inspector-backdrop");
      document.getElementById("btn-close-inspector").addEventListener("click", () => this.close());
      this.backdrop.addEventListener("click", () => this.close());
    }

    close() {
      this.currentNodeId = null;
      this.drawer.classList.remove("is-open");
      this.drawer.setAttribute("aria-hidden", "true");
      this.backdrop.classList.add("hidden");
      if (this.onClearSelection) this.onClearSelection();
    }

    resetEmpty() {
      this.close();
      document.getElementById("insp-body").innerHTML = "";
    }

    async inspect(nodeId) {
      if (!nodeId) return;
      const scope = encodeURIComponent(this.getScope());
      const res = await fetch(`/api/node/${encodeURIComponent(nodeId)}?scope=${scope}`);
      if (!res.ok) {
        this.notify(tr(`Entity not found: ${nodeId}`, `Không tìm thấy thực thể ${nodeId}`), true);
        return;
      }
      const { node, edges } = await res.json();
      const state = this.getState();
      this.currentNodeId = node.id;
      this.drawer.classList.add("is-open");
      this.drawer.setAttribute("aria-hidden", "false");
      this.backdrop.classList.remove("hidden");
      document.getElementById("insp-badge").textContent = `${node.memory_tier || "SEMANTIC"} / ${node.node_type}`;
      document.getElementById("insp-id").textContent = `${node.id} — ${node.title}`;

      const promoteBtn = !state.is_global
        ? `<button type="button" id="btn-promote-global" class="btn btn-secondary btn-sm">${tr("Promote to Global", "Đưa lên Global")}</button>`
        : "";
      const fileRow = node.file_path
        ? `<span class="prop-key">${tr("Source File", "Tệp nguồn")}</span><span class="prop-val"><a class="file-anchor" href="file://${esc(node.file_path)}" target="_blank" rel="noreferrer">${esc(node.file_path)}</a></span>`
        : "";

      const edgeRows = edges
        .map((e) => {
          const outbound = e.source_id === node.id;
          const jump = outbound ? e.target_id : e.source_id;
          const relLabel = outbound ? `${e.relation} -> ${jump}` : `${jump} -> ${e.relation}`;
          return `<button type="button" class="edge-btn" data-jump="${esc(jump)}"><span>${esc(relLabel)}</span><span class="muted">${tr("Open", "Mở")}</span></button>`;
        })
        .join("");

      const targetOpts = (state.nodes || [])
        .filter((x) => x.id !== node.id)
        .slice(0, 120)
        .map((x) => `<option value="${esc(x.id)}">${esc(x.id)} — ${esc(x.title.slice(0, 34))}</option>`)
        .join("");

      const relOpts = ["REFERENCES", "GOVERNED_BY", "DERIVED_FROM", "CONSOLIDATED_INTO", "VERIFIED_BY", "INSPIRED"]
        .map((r) => `<option value="${r}">${r}</option>`)
        .join("");

      const metaJson = node.metadata && Object.keys(node.metadata).length
        ? `<div class="inspector-section"><h3 class="inspector-subhead">${tr("Extended Metadata", "Thuộc tính mở rộng (Metadata)")}</h3><pre class="code-block">${esc(JSON.stringify(node.metadata, null, 2))}</pre></div>`
        : "";

      document.getElementById("insp-body").innerHTML = `
        <div class="row-actions">
          <button type="button" id="btn-edit-node" class="btn btn-primary btn-sm">${tr("Edit", "Chỉnh sửa")}</button>
          ${promoteBtn}
          <span id="insp-del-zone">
            <button type="button" id="btn-arm-del-node" class="btn btn-danger btn-sm">${tr("Delete", "Xóa")}</button>
          </span>
        </div>

        <div class="prop-grid">
          <span class="prop-key">${tr("Entity ID", "Mã thực thể")}</span><span class="prop-val">${esc(node.id)}</span>
          <span class="prop-key">${tr("Type", "Phân loại")}</span><span class="prop-val">${esc(node.node_type)}</span>
          <span class="prop-key">${tr("Cognitive Tier", "Tầng nhận thức")}</span><span class="prop-val">${esc(node.memory_tier || "SEMANTIC")}</span>
          <span class="prop-key">${tr("Status", "Trạng thái")}</span><span>${statusTag(node.status)}</span>
          <span class="prop-key">${tr("Updated", "Cập nhật")}</span><span class="prop-val">${esc((node.updated_at || "").slice(0, 19))}</span>
          ${fileRow}
        </div>

        <div class="inspector-section">
          <h3 class="inspector-subhead">${tr("Summary & Full Content", "Tóm tắt & Nội dung chi tiết")}</h3>
          <p class="row-desc">${esc(node.summary)}</p>
          <pre class="code-block">${esc(node.content || node.summary)}</pre>
        </div>

        <div class="inspector-section">
          <h3 class="inspector-subhead">${tr("Link Edge from", "Nối cạnh liên kết từ")} ${esc(node.id)}</h3>
          <div class="link-composer">
            <label for="link-rel" class="sr-only">${tr("Edge Relation", "Quan hệ liên kết")}</label>
            <select id="link-rel" class="control-select">${relOpts}</select>
            <label for="link-dst" class="sr-only">${tr("Target Entity", "Thực thể đích")}</label>
            <select id="link-dst" class="control-select">${targetOpts}</select>
            <button type="button" id="btn-add-edge" class="btn btn-secondary btn-sm">${tr("Link", "Nối cạnh")}</button>
          </div>
        </div>

        <div class="inspector-section">
          <h3 class="inspector-subhead">${tr("Graph Edges", "Liên kết đồ thị")} (${edges.length})</h3>
          <div class="edge-list">${edgeRows || `<p class="empty-desc">${tr("No direct graph edges yet.", "Chưa có cạnh liên kết trực tiếp.")}</p>`}</div>
        </div>
        ${metaJson}
      `;

      this._bindInspectorActions(node);
    }

    _bindInspectorActions(node) {
      document.getElementById("btn-edit-node").addEventListener("click", () => this.onOpenEditModal(node));
      const promoteBtn = document.getElementById("btn-promote-global");
      if (promoteBtn) {
        promoteBtn.addEventListener("click", async () => {
          try {
            const out = await this.postJson("/api/promote", { node_id: node.id });
            this.notify(tr(`Promoted to Global: ${out.global_id}`, `Đã chuyển lên Global: ${out.global_id}`));
            await this.onRefresh();
          } catch (err) { this.notify(err.message, true); }
        });
      }

      const bindArmDelete = () => {
        const armBtn = document.getElementById("btn-arm-del-node");
        if (!armBtn) return;
        armBtn.addEventListener("click", () => {
          const zone = document.getElementById("insp-del-zone");
          zone.innerHTML = `<button type="button" id="btn-confirm-del-node" class="btn btn-danger btn-sm">${tr("Confirm Delete", "Xác nhận xóa")}</button>
            <button type="button" id="btn-cancel-del-node" class="btn btn-ghost btn-sm">${tr("Cancel", "Hủy")}</button>`;
          document.getElementById("btn-confirm-del-node").focus();
          document.getElementById("btn-cancel-del-node").addEventListener("click", () => {
            zone.innerHTML = `<button type="button" id="btn-arm-del-node" class="btn btn-danger btn-sm">${tr("Delete", "Xóa")}</button>`;
            bindArmDelete();
          });
          document.getElementById("btn-confirm-del-node").addEventListener("click", async () => {
            try {
              await this.postJson("/api/node/delete", { node_id: node.id });
              this.notify(tr(`Deleted entity ${node.id}`, `Đã xóa thực thể ${node.id}`));
              this.resetEmpty();
              await this.onRefresh();
            } catch (err) { this.notify(err.message, true); }
          });
        });
      };
      bindArmDelete();

      document.getElementById("btn-add-edge").addEventListener("click", async () => {
        const dst = document.getElementById("link-dst").value, rel = document.getElementById("link-rel").value;
        if (!dst) return;
        try {
          await this.postJson("/api/edge/add", { source_id: node.id, target_id: dst, relation: rel });
          this.notify(tr(`Linked ${node.id} -> ${dst}`, `Đã nối cạnh ${node.id} -> ${dst}`));
          await this.onRefresh();
          await this.inspect(node.id);
        } catch (err) { this.notify(err.message, true); }
      });

      document.getElementById("insp-body").querySelectorAll("[data-jump]").forEach((btn) => {
        btn.addEventListener("click", () => this.inspect(btn.getAttribute("data-jump")));
      });
    }
  }

  window.SuperMemoryInspector = { InspectorController };
})();
