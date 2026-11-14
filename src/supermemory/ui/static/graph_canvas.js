// Multi-Mode Interactive Knowledge Graph Canvas: FORCE (Network), RADIAL (Rings) & LANES (Cards)
(function () {
  const { esc } = window.SuperMemoryIcons;
  const ACCENTS = {
    LAW: "#141518", PROCEDURE: "#334155", GATE: "#2563EB", KNOWLEDGE_NODE: "#0284C7", OBSERVATION: "#0284C7",
    ALGORITHM: "#0D9488", IDEA: "#0284C7", PROPOSAL: "#D97706", EXPERIMENT: "#6D28D9", LESSON: "#DC2626", AGENT_RUN: "#15803D",
  };
  const LANES = [
    { key: "PROCEDURAL", title: "TẦNG L1 · HIẾN PHÁP & GATES", rx: 210, ry: 136 },
    { key: "SEMANTIC", title: "TẦNG L2 · TRI THỨC & INSIGHT", rx: 332, ry: 214 },
    { key: "EPISODIC", title: "TẦNG L3 · THỰC NGHIỆM & PROPOSALS", rx: 456, ry: 294 },
  ];
  const CARD_W = 204, CARD_H = 50, GAP_X = 14, GAP_Y = 10, LANE_GAP = 54;
  const cleanTitle = (s) => String(s || "").replace(/^(?:\[[^\]]+\]\s*|Guard for LESSON-\d+:\s*|SuperMemory v[\d.]+[:\s]*|VictoryAuditor Audit on\s*)/i, "");

  class ForceGraphCanvas {
    constructor(canvas, tooltip, onSelectNode) {
      Object.assign(this, { canvas, ctx: canvas.getContext("2d"), tooltip, onSelectNode, nodes: [], edges: [], nodeMap: new Map(), laneBoxes: [] });
      Object.assign(this, { mode: "FORCE", hideAux: true, activeTier: "ALL", activeType: "ALL", highlightIds: new Set() });
      Object.assign(this, { selectedId: null, hoveredId: null, dragNode: null, panX: 0, panY: 0, scale: 1, alpha: 0, isPanning: false });
      this._bindEvents();
      this._loop();
    }

    setData(nodes, edges) {
      const prev = new Map(this.nodes.map((n) => [n.id, n])), deg = {};
      edges.forEach((e) => { deg[e.source_id] = (deg[e.source_id] || 0) + 1; deg[e.target_id] = (deg[e.target_id] || 0) + 1; });
      this.nodes = nodes.map((n, i) => {
        const old = prev.get(n.id), ang = i * 2.39996, rad = 44 * Math.sqrt(i + 1), r = Math.min(15, 8.5 + Math.sqrt(deg[n.id] || 0) * 1.6);
        return { ...n, x: old ? old.x : Math.cos(ang) * rad, y: old ? old.y : Math.sin(ang) * rad, vx: 0, vy: 0, r, w: CARD_W, h: CARD_H, pinned: old ? old.pinned : false };
      });
      this.nodeMap = new Map(this.nodes.map((n) => [n.id, n]));
      this.edges = edges.filter((e) => this.nodeMap.has(e.source_id) && this.nodeMap.has(e.target_id));
      this._applyLayout(!prev.size);
    }

    setMode(mode) { this.mode = mode || "FORCE"; this.nodes.forEach((n) => { n.pinned = false; }); this._applyLayout(true); }
    setHideAux(flag) { this.hideAux = Boolean(flag); this._applyLayout(true); }
    setFilter(tier, ntype) { this.activeTier = tier || "ALL"; this.activeType = ntype || "ALL"; this._applyLayout(true); }
    relayout() { this.nodes.forEach((n) => { n.pinned = false; }); this._applyLayout(true); }

    _visibleNodes() {
      return this.nodes.filter((n) => (this.activeTier === "ALL" || n.memory_tier === this.activeTier) &&
        (this.activeType === "ALL" || n.node_type === this.activeType) && (!this.hideAux || this.activeType === "AGENT_RUN" || n.node_type !== "AGENT_RUN"));
    }

    _applyLayout(reset) {
      const vis = this._visibleNodes(); this.laneBoxes = [];
      if (this.mode === "FORCE") {
        if (reset) vis.forEach((n, i) => { if (!n.pinned) { const a = i * 2.39996, r = 64 * Math.sqrt(i + 1); n.x = Math.cos(a) * r * 1.42; n.y = Math.sin(a) * r * 0.86; n.vx = 0; n.vy = 0; } });
        this.alpha = 1; for (let k = 0; k < 120; k++) this._stepForce(vis);
      } else if (this.mode === "RADIAL") {
        this.alpha = 0;
        LANES.forEach((ln) => {
          const items = vis.filter((n) => n.memory_tier === ln.key);
          items.forEach((n, i) => { if (reset || !n.pinned) { const a = (2 * Math.PI * i) / Math.max(1, items.length) - Math.PI / 2, st = items.length > 12 ? (i % 2 ? 1.09 : 0.91) : 1; n.x = Math.cos(a) * ln.rx * st; n.y = Math.sin(a) * ln.ry * st; } });
        });
      } else {
        this.alpha = 0; let curX = 0;
        LANES.forEach((ln) => {
          const items = vis.filter((n) => n.memory_tier === ln.key); if (!items.length) return;
          const cols = items.length > 6 ? 2 : 1, rows = Math.ceil(items.length / cols), boxW = cols * CARD_W + (cols - 1) * GAP_X + 32, boxH = rows * CARD_H + (rows - 1) * GAP_Y + 56;
          items.forEach((n, i) => { if (reset || !n.pinned) { n.x = curX + 16 + (i % cols) * (CARD_W + GAP_X); n.y = 42 + Math.floor(i / cols) * (CARD_H + GAP_Y); } });
          this.laneBoxes.push({ title: `${ln.title} (${items.length})`, x: curX, y: 0, w: boxW, h: boxH }); curX += boxW + LANE_GAP;
        });
      }
      if (reset) this.fitView();
    }

    _stepForce(vis) {
      if (this.alpha < 0.008) return;
      const visSet = new Set(vis.map((n) => n.id));
      for (let i = 0; i < vis.length; i++) for (let j = i + 1; j < vis.length; j++) {
        const a = vis[i], b = vis[j], dx0 = b.x - a.x || 0.5, dy0 = b.y - a.y || 0.5, d2 = Math.max(640, dx0 * dx0 + dy0 * dy0), d = Math.sqrt(d2), f = (8400 * this.alpha) / d2;
        if (!a.pinned) { a.vx -= (dx0 / d) * f; a.vy -= (dy0 / d) * f; }
        if (!b.pinned) { b.vx += (dx0 / d) * f; b.vy += (dy0 / d) * f; }
        if (Math.abs(dx0) < 108 && Math.abs(dy0) < 48) {
          const px = (108 - Math.abs(dx0)) * 0.09 * Math.sign(dx0), py = (48 - Math.abs(dy0)) * 0.14 * Math.sign(dy0);
          if (!a.pinned) { a.vx -= px; a.vy -= py; }
          if (!b.pinned) { b.vx += px; b.vy += py; }
        }
      }
      for (const e of this.edges) {
        if (!visSet.has(e.source_id) || !visSet.has(e.target_id)) continue;
        const s = this.nodeMap.get(e.source_id), t = this.nodeMap.get(e.target_id), dx = t.x - s.x, dy = t.y - s.y, d = Math.sqrt(dx * dx + dy * dy) || 1, f = (d - 185) * 0.018 * this.alpha;
        if (!s.pinned) { s.vx += (dx / d) * f; s.vy += (dy / d) * f; }
        if (!t.pinned) { t.vx -= (dx / d) * f; t.vy -= (dy / d) * f; }
      }
      for (const n of vis) if (!n.pinned) { n.vx = (n.vx - n.x * 0.004 * this.alpha) * 0.78; n.vy = (n.vy - n.y * 0.009 * this.alpha) * 0.78; n.x += n.vx; n.y += n.vy; }
      this.alpha *= 0.95;
    }

    fitView() {
      const rect = this.canvas.parentElement.getBoundingClientRect(), vis = this._visibleNodes();
      if (!vis.length || !rect.width || !rect.height) return;
      const isCard = this.mode === "LANES", padX = isCard ? 28 : 68, padY = isCard ? 24 : 44;
      const minX = Math.min(...vis.map((n) => n.x)) - padX, maxX = Math.max(...vis.map((n) => n.x + (isCard ? n.w : 0))) + padX;
      const minY = Math.min(...vis.map((n) => n.y)) - padY, maxY = Math.max(...vis.map((n) => n.y + (isCard ? n.h : 28))) + padY;
      const topIn = 18, botIn = rect.width <= 768 ? 16 : 52, availH = Math.max(200, rect.height - topIn - botIn);
      this.scale = Math.min(1.12, Math.max(0.52, Math.min((rect.width - 36) / (maxX - minX || 1), availH / (maxY - minY || 1))));
      this.panX = rect.width / 2 - ((minX + maxX) / 2) * this.scale; this.panY = topIn + availH / 2 - ((minY + maxY) / 2) * this.scale;
    }

    zoomBy(f) { const r = this.canvas.getBoundingClientRect(); this._zoomAt(r.width / 2, r.height / 2, f); }
    _zoomAt(mx, my, f) { const nx = Math.min(2.6, Math.max(0.35, this.scale * f)); this.panX = mx - ((mx - this.panX) / this.scale) * nx; this.panY = my - ((my - this.panY) / this.scale) * nx; this.scale = nx; }
    screenToWorld(sx, sy) { return { x: (sx - this.panX) / this.scale, y: (sy - this.panY) / this.scale }; }

    _draw() {
      const rect = this.canvas.parentElement.getBoundingClientRect(); if (!rect.width || !rect.height) return;
      const vis = this._visibleNodes(), dpr = window.devicePixelRatio || 1;
      if (this.mode === "FORCE" && this.alpha >= 0.008) this._stepForce(vis);
      if (this.canvas.width !== Math.floor(rect.width * dpr) || this.canvas.height !== Math.floor(rect.height * dpr)) { this.canvas.width = Math.floor(rect.width * dpr); this.canvas.height = Math.floor(rect.height * dpr); }
      const ctx = this.ctx, visSet = new Set(vis.map((n) => n.id)), isCard = this.mode === "LANES", step = 24 * this.scale;
      ctx.save(); ctx.scale(dpr, dpr); ctx.clearRect(0, 0, rect.width, rect.height);
      if (step >= 12) { ctx.fillStyle = "#DCD8CE"; for (let x = ((this.panX % step) + step) % step; x < rect.width; x += step) for (let y = ((this.panY % step) + step) % step; y < rect.height; y += step) ctx.fillRect(x, y, 1.5, 1.5); }
      ctx.translate(this.panX, this.panY); ctx.scale(this.scale, this.scale);
      if (this.mode === "RADIAL") { ctx.strokeStyle = "#D5D1C7"; ctx.setLineDash([6, 6]); ctx.lineWidth = 1.1; LANES.forEach((ln) => { ctx.beginPath(); ctx.ellipse(0, 0, ln.rx, ln.ry, 0, 0, Math.PI * 2); ctx.stroke(); }); ctx.setLineDash([]); }
      else if (isCard) for (const lb of this.laneBoxes) { ctx.fillStyle = "rgba(255,255,255,0.58)"; ctx.strokeStyle = "#DEDAD0"; ctx.lineWidth = 1; ctx.beginPath(); ctx.roundRect(lb.x, lb.y, lb.w, lb.h, 14); ctx.fill(); ctx.stroke(); ctx.fillStyle = "#484C56"; ctx.font = '700 13px "Bear Sans UI", "Noto Sans", sans-serif'; ctx.fillText(lb.title, lb.x + 16, lb.y + 26); }
      const focusId = this.hoveredId || this.selectedId, ego = new Set();
      if (focusId) { ego.add(focusId); this.edges.forEach((e) => { if (e.source_id === focusId) ego.add(e.target_id); if (e.target_id === focusId) ego.add(e.source_id); }); }
      for (const e of this.edges) {
        if (!visSet.has(e.source_id) || !visSet.has(e.target_id)) continue;
        const s = this.nodeMap.get(e.source_id), t = this.nodeMap.get(e.target_id), active = focusId && (e.source_id === focusId || e.target_id === focusId);
        ctx.strokeStyle = active ? "#141518" : ego.size ? "rgba(180,175,162,0.12)" : isCard ? "rgba(140,136,126,0.12)" : "rgba(120,116,106,0.32)";
        ctx.lineWidth = active ? 2.1 : 1.15; ctx.beginPath();
        if (isCard) { const lr = s.x <= t.x, sx = lr ? s.x + s.w : s.x, sy = s.y + s.h / 2, tx = lr ? t.x : t.x + t.w, ty = t.y + t.h / 2, dx = Math.max(40, Math.abs(tx - sx) * 0.45) * (lr ? 1 : -1); ctx.moveTo(sx, sy); ctx.bezierCurveTo(sx + dx, sy, tx - dx, ty, tx, ty); }
        else { ctx.moveTo(s.x, s.y); ctx.lineTo(t.x, t.y); }
        ctx.stroke();
      }
      const fs = Math.round(12 / Math.min(1, Math.max(0.68, this.scale))), pillH = fs + 8;
      for (const n of vis) {
        const dimmed = (ego.size && !ego.has(n.id)) || (this.highlightIds.size && !this.highlightIds.has(n.id));
        const active = n.id === this.selectedId || n.id === this.hoveredId || this.highlightIds.has(n.id), acc = ACCENTS[n.node_type] || "#475569", lbl = cleanTitle(n.title);
        ctx.globalAlpha = dimmed ? 0.24 : 1;
        if (isCard) {
          ctx.fillStyle = "#FFFFFF"; ctx.strokeStyle = active ? "#141518" : "#D5D1C7"; ctx.lineWidth = active ? 2 : 1;
          ctx.beginPath(); ctx.roundRect(n.x, n.y, n.w, n.h, 10); ctx.fill(); ctx.stroke();
          ctx.fillStyle = acc; ctx.beginPath(); ctx.roundRect(n.x + 1, n.y + 8, 4, n.h - 16, 2); ctx.fill();
          ctx.font = '700 12.5px "JetBrains Mono", monospace'; ctx.fillText(n.id.slice(0, 19), n.x + 13, n.y + 20);
          ctx.fillStyle = "#141518"; ctx.font = '600 13.5px "Bear Sans UI", "Noto Sans", sans-serif'; ctx.fillText(lbl.length > 24 ? `${lbl.slice(0, 23)}…` : lbl, n.x + 13, n.y + 38);
        } else {
          ctx.fillStyle = acc; ctx.strokeStyle = active ? "#141518" : "#FFFFFF"; ctx.lineWidth = active ? 3 : 2.2;
          ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
          const txt = active ? `${n.id} · ${lbl.slice(0, 22)}` : n.id;
          ctx.font = active ? `700 ${fs + 1}px "Bear Sans UI", "Noto Sans", sans-serif` : `600 ${fs}px "JetBrains Mono", monospace`;
          const tw = ctx.measureText(txt).width + 12;
          ctx.fillStyle = "rgba(255,255,255,0.94)"; ctx.strokeStyle = active ? "#141518" : "#DEDAD0"; ctx.lineWidth = 1;
          ctx.beginPath(); ctx.roundRect(n.x - tw / 2, n.y + n.r + 4, tw, pillH, 6); ctx.fill(); ctx.stroke();
          ctx.fillStyle = "#141518"; ctx.textAlign = "center"; ctx.fillText(txt, n.x, n.y + n.r + 4 + Math.round(pillH * 0.72)); ctx.textAlign = "start";
        }
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
        if (this.dragNode) { const pt = this.screenToWorld(ev.clientX - r.left, ev.clientY - r.top); this.dragNode.x = pt.x - this.dragOff.x; this.dragNode.y = pt.y - this.dragOff.y; if (this.mode === "FORCE") this.alpha = 0.25; return; }
        if (this.isPanning) { this.panX += ev.clientX - this.lastMouse.x; this.panY += ev.clientY - this.lastMouse.y; this.lastMouse = { x: ev.clientX, y: ev.clientY }; return; }
        if (ev.target !== this.canvas) { this.hoveredId = null; this.tooltip.classList.add("hidden"); return; }
        const pt = this.screenToWorld(ev.clientX - r.left, ev.clientY - r.top), hit = this._findNode(pt.x, pt.y);
        this.hoveredId = hit ? hit.id : null;
        if (hit) { this.tooltip.classList.remove("hidden"); this.tooltip.style.left = `${Math.min(r.width - 280, ev.clientX - r.left + 14)}px`; this.tooltip.style.top = `${Math.max(12, ev.clientY - r.top + 14)}px`; this.tooltip.innerHTML = `<div class="mono-id">${esc(hit.node_type)} &middot; ${esc(hit.id)}</div><div class="row-title">${esc(hit.title)}</div>`; }
        else this.tooltip.classList.add("hidden");
      });
      window.addEventListener("mouseup", () => { this.dragNode = null; this.isPanning = false; });
      this.canvas.addEventListener("wheel", (ev) => { ev.preventDefault(); const r = this.canvas.getBoundingClientRect(); this._zoomAt(ev.clientX - r.left, ev.clientY - r.top, ev.deltaY < 0 ? 1.1 : 0.9); }, { passive: false });
      this.canvas.addEventListener("keydown", (ev) => { if (ev.key === "+" || ev.key === "=") { ev.preventDefault(); this.zoomBy(1.15); } else if (ev.key === "-") { ev.preventDefault(); this.zoomBy(0.86); } else if (ev.key === "0") { ev.preventDefault(); this.fitView(); } });
    }

    _findNode(wx, wy) {
      const vis = this._visibleNodes(), isCard = this.mode === "LANES";
      for (let i = vis.length - 1; i >= 0; i--) { const n = vis[i]; if ((isCard && wx >= n.x && wx <= n.x + n.w && wy >= n.y && wy <= n.y + n.h) || (!isCard && Math.hypot(wx - n.x, wy - n.y) <= n.r + 8)) return n; }
      return null;
    }
    _loop() { this._draw(); requestAnimationFrame(() => this._loop()); }
  }
  window.SuperMemoryGraph = { ForceGraphCanvas };
})();
