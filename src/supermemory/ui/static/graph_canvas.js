// Structured 3-Lane Architectural Card Topology Canvas (Bezier Connectors & Crisp Card Nodes)
(function () {
  const { esc } = window.SuperMemoryIcons;
  const ACCENTS = {
    LAW: "#141518", PROCEDURE: "#334155", GATE: "#2563EB",
    KNOWLEDGE_NODE: "#0284C7", OBSERVATION: "#0284C7", ALGORITHM: "#0D9488", IDEA: "#0284C7",
    PROPOSAL: "#D97706", EXPERIMENT: "#6D28D9", LESSON: "#DC2626", AGENT_RUN: "#15803D",
  };
  const LANES = [
    { key: "PROCEDURAL", title: "TẦNG L1 · HIẾN PHÁP & GATES" },
    { key: "SEMANTIC", title: "TẦNG L2 · TRI THỨC & INSIGHT" },
    { key: "EPISODIC", title: "TẦNG L3 · THỰC NGHIỆM & PROPOSALS" },
  ];
  const CARD_W = 206, CARD_H = 52, GAP_X = 14, GAP_Y = 9, LANE_GAP = 48;
  const cleanTitle = (s) => String(s || "").replace(/^(?:\[[^\]]+\]\s*|Guard for LESSON-\d+:\s*|SuperMemory v[\d.]+[:\s]*|VictoryAuditor Audit on\s*)/i, "");

  class ForceGraphCanvas {
    constructor(canvas, tooltip, onSelectNode) {
      Object.assign(this, { canvas, ctx: canvas.getContext("2d"), tooltip, onSelectNode, nodes: [], edges: [] });
      Object.assign(this, { nodeMap: new Map(), laneBoxes: [], activeTier: "ALL", activeType: "ALL", highlightIds: new Set() });
      Object.assign(this, { selectedId: null, hoveredId: null, dragNode: null, panX: 0, panY: 0, scale: 1, isPanning: false });
      this._bindEvents();
      this._loop();
    }

    setData(nodes, edges) {
      const prev = new Map(this.nodes.map((n) => [n.id, { x: n.x, y: n.y, pinned: n.pinned }]));
      this.nodes = nodes.map((n) => {
        const old = prev.get(n.id);
        return { ...n, x: old ? old.x : 0, y: old ? old.y : 0, pinned: old ? old.pinned : false, w: CARD_W, h: CARD_H };
      });
      this.nodeMap = new Map(this.nodes.map((n) => [n.id, n]));
      this.edges = edges.filter((e) => this.nodeMap.has(e.source_id) && this.nodeMap.has(e.target_id));
      this._computeLaneLayout(!prev.size);
      if (!prev.size) this.fitView();
    }

    setFilter(tier, ntype) {
      this.activeTier = tier || "ALL";
      this.activeType = ntype || "ALL";
      this._computeLaneLayout(true);
      this.fitView();
    }

    relayout() {
      this.nodes.forEach((n) => { n.pinned = false; });
      this._computeLaneLayout(true);
      this.fitView();
    }

    _visibleNodes() {
      return this.nodes.filter(
        (n) => (this.activeTier === "ALL" || n.memory_tier === this.activeTier) &&
               (this.activeType === "ALL" || n.node_type === this.activeType)
      );
    }

    _computeLaneLayout(resetPositions) {
      const vis = this._visibleNodes();
      this.laneBoxes = [];
      let curX = 0;
      LANES.forEach((ln) => {
        const items = vis.filter((n) => n.memory_tier === ln.key);
        if (!items.length) return;
        const cols = items.length > 6 ? 2 : 1, rows = Math.ceil(items.length / cols);
        const boxW = cols * CARD_W + (cols - 1) * GAP_X + 32;
        const boxH = rows * CARD_H + (rows - 1) * GAP_Y + 56;
        items.forEach((n, idx) => {
          if (resetPositions || !n.pinned) {
            n.x = curX + 16 + (idx % cols) * (CARD_W + GAP_X);
            n.y = 42 + Math.floor(idx / cols) * (CARD_H + GAP_Y);
          }
        });
        this.laneBoxes.push({ title: `${ln.title} (${items.length})`, x: curX, y: 0, w: boxW, h: boxH });
        curX += boxW + LANE_GAP;
      });
    }

    fitView() {
      const rect = this.canvas.parentElement.getBoundingClientRect(), vis = this._visibleNodes();
      if (!vis.length || !rect.width || !rect.height) return;
      const minX = Math.min(...vis.map((n) => n.x)) - 22, maxX = Math.max(...vis.map((n) => n.x + n.w)) + 22;
      const minY = -8, maxY = Math.max(...vis.map((n) => n.y + n.h)) + 24;
      const topInset = rect.width <= 768 ? 16 : 66, botInset = rect.width <= 768 ? 16 : 54;
      const availH = Math.max(240, rect.height - topInset - botInset);
      this.scale = Math.min(1.04, Math.max(0.55, Math.min((rect.width - 36) / (maxX - minX || 1), availH / (maxY - minY || 1))));
      this.panX = rect.width / 2 - ((minX + maxX) / 2) * this.scale;
      this.panY = topInset + availH / 2 - ((minY + maxY) / 2) * this.scale;
    }

    zoomBy(f) { const r = this.canvas.getBoundingClientRect(); this._zoomAt(r.width / 2, r.height / 2, f); }
    _zoomAt(mx, my, f) {
      const next = Math.min(2.4, Math.max(0.4, this.scale * f));
      this.panX = mx - ((mx - this.panX) / this.scale) * next;
      this.panY = my - ((my - this.panY) / this.scale) * next;
      this.scale = next;
    }
    screenToWorld(sx, sy) { return { x: (sx - this.panX) / this.scale, y: (sy - this.panY) / this.scale }; }

    _draw() {
      const rect = this.canvas.parentElement.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const dpr = window.devicePixelRatio || 1;
      if (this.canvas.width !== Math.floor(rect.width * dpr) || this.canvas.height !== Math.floor(rect.height * dpr)) {
        this.canvas.width = Math.floor(rect.width * dpr); this.canvas.height = Math.floor(rect.height * dpr);
      }
      const ctx = this.ctx, vis = this._visibleNodes(), visSet = new Set(vis.map((n) => n.id));
      ctx.save(); ctx.scale(dpr, dpr); ctx.clearRect(0, 0, rect.width, rect.height);

      const step = 24 * this.scale;
      if (step >= 12) {
        ctx.fillStyle = "#DCD8CE";
        for (let x = ((this.panX % step) + step) % step; x < rect.width; x += step)
          for (let y = ((this.panY % step) + step) % step; y < rect.height; y += step) ctx.fillRect(x, y, 1.5, 1.5);
      }
      ctx.translate(this.panX, this.panY); ctx.scale(this.scale, this.scale);

      for (const lb of this.laneBoxes) {
        ctx.fillStyle = "rgba(255, 255, 255, 0.58)"; ctx.strokeStyle = "#DEDAD0"; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.roundRect(lb.x, lb.y, lb.w, lb.h, 14); ctx.fill(); ctx.stroke();
        ctx.fillStyle = "#484C56"; ctx.font = '700 13px "Bear Sans UI", "Noto Sans", sans-serif';
        ctx.fillText(lb.title, lb.x + 16, lb.y + 26);
      }

      const focusId = this.hoveredId || this.selectedId, ego = new Set();
      if (focusId) {
        ego.add(focusId);
        this.edges.forEach((e) => { if (e.source_id === focusId) ego.add(e.target_id); if (e.target_id === focusId) ego.add(e.source_id); });
      }

      for (const e of this.edges) {
        if (!visSet.has(e.source_id) || !visSet.has(e.target_id)) continue;
        const s = this.nodeMap.get(e.source_id), t = this.nodeMap.get(e.target_id);
        const active = focusId && (e.source_id === focusId || e.target_id === focusId), lr = s.x <= t.x;
        const sx = lr ? s.x + s.w : s.x, sy = s.y + s.h / 2, tx = lr ? t.x : t.x + t.w, ty = t.y + t.h / 2;
        const dx = Math.max(40, Math.abs(tx - sx) * 0.45) * (lr ? 1 : -1);
        ctx.strokeStyle = active ? "#141518" : ego.size ? "rgba(180,175,162,0.18)" : "rgba(130,126,116,0.32)";
        ctx.lineWidth = active ? 2 : 1.25;
        ctx.beginPath(); ctx.moveTo(sx, sy); ctx.bezierCurveTo(sx + dx, sy, tx - dx, ty, tx, ty); ctx.stroke();
      }

      for (const n of vis) {
        const dimmed = (ego.size && !ego.has(n.id)) || (this.highlightIds.size && !this.highlightIds.has(n.id));
        const active = n.id === this.selectedId || n.id === this.hoveredId || this.highlightIds.has(n.id);
        const acc = ACCENTS[n.node_type] || "#475569", lbl = cleanTitle(n.title);
        ctx.globalAlpha = dimmed ? 0.28 : 1;
        ctx.fillStyle = "#FFFFFF"; ctx.strokeStyle = active ? "#141518" : "#D5D1C7"; ctx.lineWidth = active ? 2 : 1;
        ctx.beginPath(); ctx.roundRect(n.x, n.y, n.w, n.h, 10); ctx.fill(); ctx.stroke();
        ctx.fillStyle = acc; ctx.beginPath(); ctx.roundRect(n.x + 1, n.y + 8, 4, n.h - 16, 2); ctx.fill();
        ctx.fillStyle = acc; ctx.font = '700 12.5px "JetBrains Mono", monospace';
        ctx.fillText(n.id.slice(0, 19), n.x + 13, n.y + 20);
        ctx.fillStyle = "#141518"; ctx.font = '600 13.5px "Bear Sans UI", "Noto Sans", sans-serif';
        ctx.fillText(lbl.length > 24 ? `${lbl.slice(0, 23)}…` : lbl, n.x + 13, n.y + 39);
      }
      ctx.globalAlpha = 1; ctx.restore();
    }

    _bindEvents() {
      this.canvas.addEventListener("mousedown", (ev) => {
        const r = this.canvas.getBoundingClientRect(), pt = this.screenToWorld(ev.clientX - r.left, ev.clientY - r.top), hit = this._findNode(pt.x, pt.y);
        if (hit) { this.dragNode = hit; this.dragOff = { x: pt.x - hit.x, y: pt.y - hit.y }; hit.pinned = true; this.selectedId = hit.id; this.onSelectNode(hit); }
        else { this.isPanning = true; this.lastMouse = { x: ev.clientX, y: ev.clientY }; }
      });
      window.addEventListener("mousemove", (ev) => {
        const r = this.canvas.getBoundingClientRect();
        if (this.dragNode) { const pt = this.screenToWorld(ev.clientX - r.left, ev.clientY - r.top); this.dragNode.x = pt.x - this.dragOff.x; this.dragNode.y = pt.y - this.dragOff.y; return; }
        if (this.isPanning) { this.panX += ev.clientX - this.lastMouse.x; this.panY += ev.clientY - this.lastMouse.y; this.lastMouse = { x: ev.clientX, y: ev.clientY }; return; }
        if (ev.target !== this.canvas) { this.hoveredId = null; this.tooltip.classList.add("hidden"); return; }
        const pt = this.screenToWorld(ev.clientX - r.left, ev.clientY - r.top), hit = this._findNode(pt.x, pt.y);
        this.hoveredId = hit ? hit.id : null;
        if (hit) {
          this.tooltip.classList.remove("hidden");
          this.tooltip.style.left = `${Math.min(r.width - 280, ev.clientX - r.left + 14)}px`;
          this.tooltip.style.top = `${Math.max(64, ev.clientY - r.top + 14)}px`;
          this.tooltip.innerHTML = `<div class="mono-id">${esc(hit.node_type)} &middot; ${esc(hit.id)}</div><div class="row-title">${esc(hit.title)}</div>`;
        } else this.tooltip.classList.add("hidden");
      });
      window.addEventListener("mouseup", () => { this.dragNode = null; this.isPanning = false; });
      this.canvas.addEventListener("wheel", (ev) => { ev.preventDefault(); const r = this.canvas.getBoundingClientRect(); this._zoomAt(ev.clientX - r.left, ev.clientY - r.top, ev.deltaY < 0 ? 1.1 : 0.9); }, { passive: false });
      this.canvas.addEventListener("keydown", (ev) => {
        if (ev.key === "+" || ev.key === "=") { ev.preventDefault(); this.zoomBy(1.15); }
        else if (ev.key === "-") { ev.preventDefault(); this.zoomBy(0.86); }
        else if (ev.key === "0") { ev.preventDefault(); this.fitView(); }
      });
    }

    _findNode(wx, wy) {
      const vis = this._visibleNodes();
      for (let i = vis.length - 1; i >= 0; i--) { const n = vis[i]; if (wx >= n.x && wx <= n.x + n.w && wy >= n.y && wy <= n.y + n.h) return n; }
      return null;
    }
    _loop() { this._draw(); requestAnimationFrame(() => this._loop()); }
  }
  window.SuperMemoryGraph = { ForceGraphCanvas };
})();
