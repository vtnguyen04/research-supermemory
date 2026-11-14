// Precision Vector Canvas Renderer for SuperMemory Constitutional Topology
(function () {
  const { esc } = window.SuperMemoryIcons;
  const TYPE_COLORS = {
    LAW: "#e2e8f0", PROCEDURE: "#94a3b8", GATE: "#60a5fa", LESSON: "#f87171",
    EXPERIMENT: "#a78bfa", PROPOSAL: "#facc15", IDEA: "#60a5fa", ALGORITHM: "#60a5fa",
    KNOWLEDGE_NODE: "#38bdf8", OBSERVATION: "#38bdf8", AGENT_RUN: "#4ade80",
  };

  class ForceGraphCanvas {
    constructor(canvas, tooltip, onSelectNode) {
      Object.assign(this, { canvas, ctx: canvas.getContext("2d"), tooltip, onSelectNode, nodes: [], edges: [] });
      Object.assign(this, { nodeMap: new Map(), hiddenTypes: new Set(), hiddenTiers: new Set(), highlightIds: new Set() });
      Object.assign(this, { selectedId: null, dragNode: null, panX: 0, panY: 0, scale: 1, isPanning: false, alpha: 1 });
      this._bindEvents();
      this._loop();
    }

    setData(nodes, edges) {
      const prev = new Map(this.nodes.map((n) => [n.id, { x: n.x, y: n.y, pinned: n.pinned }]));
      const types = Array.from(new Set(nodes.map((n) => n.node_type)));
      this.nodes = nodes.map((n, idx) => {
        const old = prev.get(n.id);
        const angle = (Math.max(0, types.indexOf(n.node_type)) / Math.max(1, types.length)) * Math.PI * 2 + (idx % 17) * 0.21;
        const rad = 136 + (idx % 9) * 28;
        return {
          ...n, x: old ? old.x : Math.cos(angle) * rad, y: old ? old.y : Math.sin(angle) * rad,
          vx: 0, vy: 0, pinned: old ? old.pinned : false,
          r: n.node_type === "LAW" ? 9.5 : n.node_type === "PROPOSAL" ? 8 : 6.5,
        };
      });
      this.nodeMap = new Map(this.nodes.map((n) => [n.id, n]));
      this.edges = edges.filter((e) => this.nodeMap.has(e.source_id) && this.nodeMap.has(e.target_id));
      this.alpha = 1;
      if (!prev.size) {
        for (let k = 0; k < 48; k++) this._stepPhysics();
        this.fitView();
      }
    }

    relayout() {
      this.nodes.forEach((n, i) => {
        n.pinned = false;
        const a = i * 2.39996, r = 34 * Math.sqrt(i + 1);
        n.x = Math.cos(a) * r; n.y = Math.sin(a) * r; n.vx = 0; n.vy = 0;
      });
      this.alpha = 1;
    }

    fitView() {
      const rect = this.canvas.parentElement.getBoundingClientRect();
      const vis = this._visibleNodes();
      if (!vis.length || !rect.width || !rect.height) { this.panX = rect.width / 2; this.panY = rect.height / 2; this.scale = 0.85; return; }
      const xs = vis.map((n) => n.x), ys = vis.map((n) => n.y);
      const minX = Math.min(...xs) - 56, maxX = Math.max(...xs) + 96, minY = Math.min(...ys) - 44, maxY = Math.max(...ys) + 44;
      this.scale = Math.min(1.15, Math.max(0.35, Math.min(rect.width / (maxX - minX || 1), rect.height / (maxY - minY || 1))));
      this.panX = rect.width / 2 - ((minX + maxX) / 2) * this.scale;
      this.panY = rect.height / 2 - ((minY + maxY) / 2) * this.scale;
    }

    zoomBy(factor) { const r = this.canvas.getBoundingClientRect(); this._zoomAt(r.width / 2, r.height / 2, factor); }
    _zoomAt(mx, my, factor) {
      const next = Math.min(3.2, Math.max(0.25, this.scale * factor));
      this.panX = mx - ((mx - this.panX) / this.scale) * next;
      this.panY = my - ((my - this.panY) / this.scale) * next;
      this.scale = next;
    }

    screenToWorld(sx, sy) { return { x: (sx - this.panX) / this.scale, y: (sy - this.panY) / this.scale }; }
    _visibleNodes() { return this.nodes.filter((n) => !this.hiddenTypes.has(n.node_type) && !this.hiddenTiers.has(n.memory_tier)); }

    _stepPhysics() {
      if (this.alpha < 0.008) return;
      const vis = this._visibleNodes();
      for (let i = 0; i < vis.length; i++) {
        const a = vis[i];
        for (let j = i + 1; j < vis.length; j++) {
          const b = vis[j], dx = b.x - a.x, dy = b.y - a.y, d2 = dx * dx + dy * dy + 1;
          if (d2 > 145000) continue;
          const f = (920 * this.alpha) / d2;
          if (!a.pinned) { a.vx -= dx * f; a.vy -= dy * f; }
          if (!b.pinned) { b.vx += dx * f; b.vy += dy * f; }
        }
      }
      for (const e of this.edges) {
        const s = this.nodeMap.get(e.source_id), t = this.nodeMap.get(e.target_id);
        if (!s || !t || this.hiddenTypes.has(s.node_type) || this.hiddenTypes.has(t.node_type)) continue;
        const dx = t.x - s.x, dy = t.y - s.y, dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const f = ((dist - 96) * 0.024 * this.alpha) / dist;
        if (!s.pinned) { s.vx += dx * f; s.vy += dy * f; }
        if (!t.pinned) { t.vx -= dx * f; t.vy -= dy * f; }
      }
      for (const n of vis) {
        if (n.pinned) continue;
        n.vx = (n.vx - n.x * 0.004 * this.alpha) * 0.82;
        n.vy = (n.vy - n.y * 0.004 * this.alpha) * 0.82;
        n.x += n.vx; n.y += n.vy;
      }
      this.alpha *= 0.985;
    }

    _draw() {
      const rect = this.canvas.parentElement.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const dpr = window.devicePixelRatio || 1;
      if (this.canvas.width !== Math.floor(rect.width * dpr) || this.canvas.height !== Math.floor(rect.height * dpr)) {
        this.canvas.width = Math.floor(rect.width * dpr); this.canvas.height = Math.floor(rect.height * dpr);
      }
      const ctx = this.ctx;
      ctx.save(); ctx.scale(dpr, dpr); ctx.clearRect(0, 0, rect.width, rect.height);
      const step = 28 * this.scale;
      if (step >= 14) {
        ctx.fillStyle = "#1d212a";
        for (let x = ((this.panX % step) + step) % step; x < rect.width; x += step)
          for (let y = ((this.panY % step) + step) % step; y < rect.height; y += step) ctx.fillRect(x, y, 1.25, 1.25);
      }
      ctx.translate(this.panX, this.panY); ctx.scale(this.scale, this.scale);
      const ego = new Set();
      if (this.selectedId) {
        ego.add(this.selectedId);
        this.edges.forEach((e) => { if (e.source_id === this.selectedId) ego.add(e.target_id); if (e.target_id === this.selectedId) ego.add(e.source_id); });
      }
      for (const e of this.edges) {
        const s = this.nodeMap.get(e.source_id), t = this.nodeMap.get(e.target_id);
        if (!s || !t || this.hiddenTypes.has(s.node_type) || this.hiddenTypes.has(t.node_type) || this.hiddenTiers.has(s.memory_tier) || this.hiddenTiers.has(t.memory_tier)) continue;
        const active = this.selectedId && (e.source_id === this.selectedId || e.target_id === this.selectedId);
        const stroke = active ? "#f3f4f6" : ego.size ? "rgba(61,68,86,0.22)" : "rgba(126,134,150,0.28)";
        const ang = Math.atan2(t.y - s.y, t.x - s.x), tx = t.x - Math.cos(ang) * (t.r + 2), ty = t.y - Math.sin(ang) * (t.r + 2);
        ctx.strokeStyle = stroke; ctx.lineWidth = active ? 1.5 : 1;
        ctx.beginPath(); ctx.moveTo(s.x, s.y); ctx.lineTo(tx, ty); ctx.stroke();
        ctx.fillStyle = stroke; ctx.beginPath(); ctx.moveTo(tx, ty);
        ctx.lineTo(tx - 5.5 * Math.cos(ang - 0.45), ty - 5.5 * Math.sin(ang - 0.45));
        ctx.lineTo(tx - 5.5 * Math.cos(ang + 0.45), ty - 5.5 * Math.sin(ang + 0.45));
        ctx.closePath(); ctx.fill();
      }
      const fs = Math.round(10.5 / Math.max(0.62, Math.min(1.1, this.scale)));
      ctx.font = `500 ${fs}px "Geist Mono", ui-monospace, monospace`;
      for (const n of this._visibleNodes()) {
        ctx.globalAlpha = (ego.size && !ego.has(n.id)) || (this.highlightIds.size && !this.highlightIds.has(n.id)) ? 0.18 : 1;
        ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fillStyle = TYPE_COLORS[n.node_type] || "#94a3b8"; ctx.fill();
        const sel = n.id === this.selectedId || this.highlightIds.has(n.id);
        ctx.lineWidth = sel ? 2.2 : 1; ctx.strokeStyle = sel ? "#ffffff" : "#090a0c"; ctx.stroke();
        if (this.scale > 0.44 || n.node_type === "LAW" || sel) {
          const tw = ctx.measureText(n.id).width, ph = fs + 6, lx = n.x + n.r + 5, ly = n.y - ph / 2;
          ctx.fillStyle = "rgba(15,17,21,0.9)"; ctx.strokeStyle = "#292e3b"; ctx.lineWidth = 1;
          ctx.beginPath(); ctx.roundRect(lx, ly, tw + 10, ph, 3); ctx.fill(); ctx.stroke();
          ctx.fillStyle = "#f3f4f6"; ctx.fillText(n.id, lx + 5, n.y + fs * 0.34);
        }
      }
      ctx.globalAlpha = 1; ctx.restore();
    }

    _bindEvents() {
      this.canvas.addEventListener("mousedown", (ev) => {
        const r = this.canvas.getBoundingClientRect(), pt = this.screenToWorld(ev.clientX - r.left, ev.clientY - r.top), hit = this._findNode(pt.x, pt.y);
        if (hit) { this.dragNode = hit; hit.pinned = true; this.selectedId = hit.id; this.onSelectNode(hit); }
        else { this.isPanning = true; this.lastMouse = { x: ev.clientX, y: ev.clientY }; }
      });
      window.addEventListener("mousemove", (ev) => {
        const r = this.canvas.getBoundingClientRect();
        if (this.dragNode) { const pt = this.screenToWorld(ev.clientX - r.left, ev.clientY - r.top); this.dragNode.x = pt.x; this.dragNode.y = pt.y; this.alpha = Math.max(this.alpha, 0.25); return; }
        if (this.isPanning) { this.panX += ev.clientX - this.lastMouse.x; this.panY += ev.clientY - this.lastMouse.y; this.lastMouse = { x: ev.clientX, y: ev.clientY }; return; }
        if (ev.target !== this.canvas) { this.tooltip.classList.add("hidden"); return; }
        const pt = this.screenToWorld(ev.clientX - r.left, ev.clientY - r.top), hit = this._findNode(pt.x, pt.y);
        if (hit) {
          this.tooltip.classList.remove("hidden");
          this.tooltip.style.left = `${Math.min(r.width - 240, ev.clientX - r.left + 12)}px`;
          this.tooltip.style.top = `${Math.max(8, ev.clientY - r.top + 12)}px`;
          this.tooltip.innerHTML = `<div class="mono-id">${esc(hit.node_type)} &middot; ${esc(hit.id)}</div><div>${esc(hit.title)}</div>`;
        } else this.tooltip.classList.add("hidden");
      });
      window.addEventListener("mouseup", () => { this.dragNode = null; this.isPanning = false; });
      this.canvas.addEventListener("wheel", (ev) => { ev.preventDefault(); const r = this.canvas.getBoundingClientRect(); this._zoomAt(ev.clientX - r.left, ev.clientY - r.top, ev.deltaY < 0 ? 1.12 : 0.89); }, { passive: false });
      this.canvas.addEventListener("keydown", (ev) => {
        if (ev.key === "+" || ev.key === "=") { ev.preventDefault(); this.zoomBy(1.18); }
        else if (ev.key === "-") { ev.preventDefault(); this.zoomBy(0.85); }
        else if (ev.key === "0") { ev.preventDefault(); this.fitView(); }
      });
    }

    _findNode(wx, wy) {
      const vis = this._visibleNodes();
      for (let i = vis.length - 1; i >= 0; i--) if ((wx - vis[i].x) ** 2 + (wy - vis[i].y) ** 2 <= (vis[i].r + 5) ** 2) return vis[i];
      return null;
    }
    _loop() { this._stepPhysics(); this._draw(); requestAnimationFrame(() => this._loop()); }
  }
  window.SuperMemoryGraph = { ForceGraphCanvas, TYPE_COLORS };
})();
