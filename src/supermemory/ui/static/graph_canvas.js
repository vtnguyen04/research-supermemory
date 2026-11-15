// Interactive Directed Knowledge Graph Canvas Renderer & Pointer Controller
(function () {
  const { esc } = window.SuperMemoryIcons;
  const { ACCENTS, LANES, CARD_W, CARD_H, cleanTitle, stepForce, computeLayout } = window.SuperMemoryGraphLayouts;

  class ForceGraphCanvas {
    constructor(canvas, tooltip, onSelectNode, onStats) {
      Object.assign(this, { canvas, ctx: canvas.getContext("2d"), tooltip, onSelectNode, onStats, nodes: [], edges: [], nodeMap: new Map(), laneBoxes: [], bandLines: [], mode: "FORCE", hideAux: true, activeTier: "ALL", activeType: "ALL", highlightIds: new Set(), selectedId: null, hoveredId: null, dragNode: null, downPos: null, didDrag: false, panX: 0, panY: 0, scale: 1, alpha: 0, isPanning: false });
      this._bindEvents(); this._loop();
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

    setMode(mode) { this.mode = mode || "FORCE"; this.hoveredId = null; this.nodes.forEach((n) => { n.pinned = false; }); this._applyLayout(true); }
    setHideAux(flag) { this.hideAux = Boolean(flag); this._applyLayout(true); }
    setFilter(tier, ntype) { this.activeTier = tier || "ALL"; this.activeType = ntype || "ALL"; this._applyLayout(true); }
    relayout() { this.nodes.forEach((n) => { n.pinned = false; }); this._applyLayout(true); }

    _visibleNodes() {
      return this.nodes.filter((n) => (this.activeTier === "ALL" || n.memory_tier === this.activeTier) &&
        (this.activeType === "ALL" || n.node_type === this.activeType) && (!this.hideAux || this.activeType === "AGENT_RUN" || n.node_type !== "AGENT_RUN"));
    }

    _emitStats(vis) {
      if (!this.onStats) return;
      const vs = new Set(vis.map((n) => n.id)), ec = this.edges.filter((e) => vs.has(e.source_id) && vs.has(e.target_id)).length;
      this.onStats({ visible: vis.length, total: this.nodes.length, edges: ec, pinned: vis.filter((n) => n.pinned).length });
    }

    focusNode(id) {
      const n = this.nodeMap.get(id); if (!n) return false;
      if (n.node_type === "AGENT_RUN" && this.hideAux) this.hideAux = false;
      if (this.activeTier !== "ALL" && n.memory_tier !== this.activeTier) this.activeTier = "ALL";
      if (this.activeType !== "ALL" && n.node_type !== this.activeType) this.activeType = "ALL";
      this._applyLayout(false); this.hoveredId = null; this.selectedId = id;
      const r = this.canvas.parentElement.getBoundingClientRect(), isCard = this.mode === "LANES";
      this.scale = 1.06; this.panX = r.width / 2 - (n.x + (isCard ? n.w / 2 : 0)) * this.scale; this.panY = r.height / 2 - (n.y + (isCard ? n.h / 2 : 0)) * this.scale;
      return true;
    }

    exportPng(name = "supermemory") {
      const out = document.createElement("canvas"); out.width = this.canvas.width; out.height = this.canvas.height;
      const octx = out.getContext("2d"); octx.fillStyle = "#F5F4F0"; octx.fillRect(0, 0, out.width, out.height); octx.drawImage(this.canvas, 0, 0);
      const a = document.createElement("a"); a.download = `${name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-graph.png`; a.href = out.toDataURL("image/png"); a.click();
    }

    _applyLayout(reset) {
      const vis = this._visibleNodes();
      computeLayout(this, vis, reset);
      this._emitStats(vis);
      if (reset) this.fitView();
    }

    fitView() {
      const rect = this.canvas.parentElement.getBoundingClientRect(), vis = this._visibleNodes();
      if (!vis.length || !rect.width || !rect.height) return;
      const isCard = this.mode === "LANES", padX = isCard ? 28 : 74, padY = isCard ? 24 : 52;
      const minX = Math.min(...vis.map((n) => n.x)) - padX, maxX = Math.max(...vis.map((n) => n.x + (isCard ? n.w : 0))) + padX;
      const minY = Math.min(...vis.map((n) => n.y)) - padY, maxY = Math.max(...vis.map((n) => n.y + (isCard ? n.h : 28))) + padY;
      const topIn = 18, botIn = rect.width <= 768 ? 16 : 52, availH = Math.max(200, rect.height - topIn - botIn);
      this.scale = Math.min(1.12, Math.max(0.48, Math.min((rect.width - 36) / (maxX - minX || 1), availH / (maxY - minY || 1))));
      this.panX = rect.width / 2 - ((minX + maxX) / 2) * this.scale; this.panY = topIn + availH / 2 - ((minY + maxY) / 2) * this.scale;
    }

    zoomBy(f) { const r = this.canvas.getBoundingClientRect(); this._zoomAt(r.width / 2, r.height / 2, f); }
    _zoomAt(mx, my, f) { const nx = Math.min(2.6, Math.max(0.35, this.scale * f)); this.panX = mx - ((mx - this.panX) / this.scale) * nx; this.panY = my - ((my - this.panY) / this.scale) * nx; this.scale = nx; }
    screenToWorld(sx, sy) { return { x: (sx - this.panX) / this.scale, y: (sy - this.panY) / this.scale }; }

    _draw() {
      const rect = this.canvas.parentElement.getBoundingClientRect(); if (!rect.width || !rect.height) return;
      const vis = this._visibleNodes(), dpr = window.devicePixelRatio || 1;
      if (this.mode === "FORCE" && this.alpha >= 0.008) stepForce(this, vis);
      if (this.canvas.width !== Math.floor(rect.width * dpr) || this.canvas.height !== Math.floor(rect.height * dpr)) { this.canvas.width = Math.floor(rect.width * dpr); this.canvas.height = Math.floor(rect.height * dpr); }
      const ctx = this.ctx, visSet = new Set(vis.map((n) => n.id)), isCard = this.mode === "LANES", step = 24 * this.scale;
      ctx.save(); ctx.scale(dpr, dpr); ctx.clearRect(0, 0, rect.width, rect.height);
      if (step >= 12) { ctx.fillStyle = "#DCD8CE"; for (let x = ((this.panX % step) + step) % step; x < rect.width; x += step) for (let y = ((this.panY % step) + step) % step; y < rect.height; y += step) ctx.fillRect(x, y, 1.5, 1.5); }
      ctx.translate(this.panX, this.panY); ctx.scale(this.scale, this.scale);
      if (this.mode === "RADIAL") { ctx.strokeStyle = "#D5D1C7"; ctx.setLineDash([6, 6]); ctx.lineWidth = 1.1; LANES.forEach((ln) => { ctx.beginPath(); ctx.ellipse(0, 0, ln.rx, ln.ry, 0, 0, Math.PI * 2); ctx.stroke(); }); ctx.setLineDash([]); }
      else if (this.mode === "HIERARCHY") for (const bl of this.bandLines) { ctx.strokeStyle = "#DEDAD0"; ctx.setLineDash([5, 5]); ctx.beginPath(); ctx.moveTo(-560, bl.y); ctx.lineTo(560, bl.y); ctx.stroke(); ctx.setLineDash([]); ctx.fillStyle = "#6E7381"; ctx.font = '700 13px "Bear Sans UI", "Noto Sans", sans-serif'; ctx.fillText(bl.title, -552, bl.y - 8); }
      else if (isCard) for (const lb of this.laneBoxes) { ctx.fillStyle = "rgba(255,255,255,0.58)"; ctx.strokeStyle = "#DEDAD0"; ctx.lineWidth = 1; ctx.beginPath(); ctx.roundRect(lb.x, lb.y, lb.w, lb.h, 14); ctx.fill(); ctx.stroke(); ctx.fillStyle = "#484C56"; ctx.font = '700 13px "Bear Sans UI", "Noto Sans", sans-serif'; ctx.fillText(lb.title, lb.x + 16, lb.y + 26); }

      const focusId = this.hoveredId || this.selectedId, ego = new Set(), edgeBadges = [];
      if (focusId) { ego.add(focusId); this.edges.forEach((e) => { if (e.source_id === focusId) ego.add(e.target_id); if (e.target_id === focusId) ego.add(e.source_id); }); }
      for (const e of this.edges) {
        if (!visSet.has(e.source_id) || !visSet.has(e.target_id)) continue;
        const s = this.nodeMap.get(e.source_id), t = this.nodeMap.get(e.target_id), active = focusId && (e.source_id === focusId || e.target_id === focusId);
        const col = active ? "#141518" : ego.size ? "rgba(180,175,162,0.14)" : isCard ? "rgba(140,136,126,0.14)" : "rgba(116,112,102,0.34)";
        ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = active ? 2.1 : 1.15; ctx.beginPath();
        if (isCard) {
          const lr = s.x <= t.x, sx = lr ? s.x + s.w : s.x, sy = s.y + s.h / 2, tx = lr ? t.x : t.x + t.w, ty = t.y + t.h / 2, dx = Math.max(40, Math.abs(tx - sx) * 0.45) * (lr ? 1 : -1);
          ctx.moveTo(sx, sy); ctx.bezierCurveTo(sx + dx, sy, tx - dx, ty, tx, ty); ctx.stroke();
          if (active) edgeBadges.push({ x: (sx + tx) / 2, y: (sy + ty) / 2, txt: e.relation });
        } else {
          const dx = t.x - s.x, dy = t.y - s.y, d = Math.hypot(dx, dy) || 1, ux = dx / d, uy = dy / d, ax = t.x - ux * (t.r + 3), ay = t.y - uy * (t.r + 3);
          ctx.moveTo(s.x, s.y); ctx.lineTo(ax, ay); ctx.stroke();
          if (d > 28 && (!ego.size || active)) { ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(ax - ux * 7 + uy * 3.6, ay - uy * 7 - ux * 3.6); ctx.lineTo(ax - ux * 7 - uy * 3.6, ay - uy * 7 + ux * 3.6); ctx.closePath(); ctx.fill(); }
          if (active) edgeBadges.push({ x: (s.x + t.x) / 2, y: (s.y + t.y) / 2, txt: e.relation });
        }
      }
      const fs = Math.round(12 / Math.min(1, Math.max(0.68, this.scale))), pillH = fs + 8;
      for (const eb of edgeBadges) {
        ctx.font = `600 ${Math.max(11, fs - 1)}px "JetBrains Mono", monospace`; const w = ctx.measureText(eb.txt).width + 10;
        ctx.fillStyle = "rgba(255,255,255,0.95)"; ctx.strokeStyle = "#141518"; ctx.lineWidth = 1; ctx.beginPath(); ctx.roundRect(eb.x - w / 2, eb.y - 9, w, 18, 5); ctx.fill(); ctx.stroke();
        ctx.fillStyle = "#141518"; ctx.textAlign = "center"; ctx.fillText(eb.txt, eb.x, eb.y + 3.5); ctx.textAlign = "start";
      }
      for (const n of [...vis].sort((a, b) => (a.id === focusId ? 1 : 0) - (b.id === focusId ? 1 : 0))) {
        const dimmed = (ego.size && !ego.has(n.id)) || (this.highlightIds.size && !this.highlightIds.has(n.id)), active = n.id === this.selectedId || n.id === this.hoveredId || this.highlightIds.has(n.id), acc = ACCENTS[n.node_type] || "#475569", lbl = cleanTitle(n.title);
        ctx.globalAlpha = dimmed ? 0.22 : 1;
        if (isCard) {
          ctx.fillStyle = "#FFFFFF"; ctx.strokeStyle = active ? "#141518" : "#D5D1C7"; ctx.lineWidth = active ? 2 : 1;
          ctx.beginPath(); ctx.roundRect(n.x, n.y, n.w, n.h, 10); ctx.fill(); ctx.stroke();
          ctx.fillStyle = acc; ctx.beginPath(); ctx.roundRect(n.x + 1, n.y + 8, 4, n.h - 16, 2); ctx.fill();
          ctx.font = '700 12.5px "JetBrains Mono", monospace'; ctx.fillText(n.id.slice(0, 19), n.x + 13, n.y + 20);
          ctx.fillStyle = "#141518"; ctx.font = '600 13.5px "Bear Sans UI", "Noto Sans", sans-serif'; ctx.fillText(lbl.length > 24 ? `${lbl.slice(0, 23)}…` : lbl, n.x + 13, n.y + 38);
        } else {
          ctx.fillStyle = acc; ctx.strokeStyle = active ? "#141518" : n.pinned ? "#D97706" : "#FFFFFF"; ctx.lineWidth = active ? 3 : 2.2;
          ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
          const txt = active ? `${n.id} · ${lbl.slice(0, 22)}` : n.id;
          ctx.font = active ? `700 ${fs + 1}px "Bear Sans UI", "Noto Sans", sans-serif` : `600 ${fs}px "JetBrains Mono", monospace`;
          const tw = ctx.measureText(txt).width + 12; n.pillW = tw; n.pillH = pillH;
          ctx.fillStyle = "rgba(255,255,255,0.94)"; ctx.strokeStyle = active ? "#141518" : "#DEDAD0"; ctx.lineWidth = 1;
          ctx.beginPath(); ctx.roundRect(n.x - tw / 2, n.y + n.r + 4, tw, pillH, 6); ctx.fill(); ctx.stroke();
          ctx.fillStyle = "#141518"; ctx.textAlign = "center"; ctx.fillText(txt, n.x, n.y + n.r + 4 + Math.round(pillH * 0.72)); ctx.textAlign = "start";
        }
      }
      ctx.globalAlpha = 1; ctx.restore();
    }

    _bindEvents() {
      const crossedSlop = (ev) => Math.hypot(ev.clientX - this.downPos.x, ev.clientY - this.downPos.y) > 5;
      this.canvas.addEventListener("mousedown", (ev) => {
        if (ev.button !== 0) return;
        const r = this.canvas.getBoundingClientRect(), pt = this.screenToWorld(ev.clientX - r.left, ev.clientY - r.top), hit = this._findNode(pt.x, pt.y);
        this.downPos = { x: ev.clientX, y: ev.clientY }; this.didDrag = false;
        if (hit) { this.dragNode = hit; this.dragOff = { x: pt.x - hit.x, y: pt.y - hit.y }; }
        else { this.isPanning = true; this.lastMouse = { x: ev.clientX, y: ev.clientY }; }
      });
      window.addEventListener("mousemove", (ev) => {
        const r = this.canvas.getBoundingClientRect();
        if (this.dragNode || this.isPanning) {
          if (!this.didDrag && crossedSlop(ev)) { this.didDrag = true; if (this.dragNode) { this.dragNode.pinned = true; this._emitStats(this._visibleNodes()); } this.tooltip.classList.add("hidden"); this.canvas.style.cursor = "grabbing"; }
          if (this.didDrag && this.dragNode) { const pt = this.screenToWorld(ev.clientX - r.left, ev.clientY - r.top); this.dragNode.x = pt.x - this.dragOff.x; this.dragNode.y = pt.y - this.dragOff.y; if (this.mode === "FORCE") this.alpha = 0.25; }
          else if (this.didDrag) { this.panX += ev.clientX - this.lastMouse.x; this.panY += ev.clientY - this.lastMouse.y; this.lastMouse = { x: ev.clientX, y: ev.clientY }; }
          return;
        }
        if (ev.target !== this.canvas) { this.hoveredId = null; this.tooltip.classList.add("hidden"); return; }
        const pt = this.screenToWorld(ev.clientX - r.left, ev.clientY - r.top), hit = this._findNode(pt.x, pt.y);
        this.hoveredId = hit ? hit.id : null; this.canvas.style.cursor = hit ? "pointer" : "grab";
        if (hit) { this.tooltip.classList.remove("hidden"); this.tooltip.style.left = `${Math.min(r.width - 280, ev.clientX - r.left + 14)}px`; this.tooltip.style.top = `${Math.max(12, ev.clientY - r.top + 14)}px`; this.tooltip.innerHTML = `<div class="mono-id">${esc(hit.node_type)} &middot; ${esc(hit.id)}</div><div class="row-title">${esc(hit.title)}</div>`; }
        else this.tooltip.classList.add("hidden");
      });
      window.addEventListener("mouseup", () => {
        const clickedNode = this.dragNode && !this.didDrag ? this.dragNode : null, clickedBlank = this.isPanning && !this.didDrag;
        this.dragNode = null; this.isPanning = false; this.canvas.style.cursor = this.hoveredId ? "pointer" : "grab";
        if (clickedNode) { this.selectedId = clickedNode.id; this.tooltip.classList.add("hidden"); this.onSelectNode(clickedNode); }
        else if (clickedBlank) { this.selectedId = null; this.onSelectNode(null); }
      });
      this.canvas.addEventListener("dblclick", (ev) => { const r = this.canvas.getBoundingClientRect(), pt = this.screenToWorld(ev.clientX - r.left, ev.clientY - r.top), hit = this._findNode(pt.x, pt.y); if (hit && hit.pinned) { hit.pinned = false; if (this.mode === "FORCE") this.alpha = 0.35; this._emitStats(this._visibleNodes()); } });
      this.canvas.addEventListener("wheel", (ev) => { ev.preventDefault(); const r = this.canvas.getBoundingClientRect(); this._zoomAt(ev.clientX - r.left, ev.clientY - r.top, ev.deltaY < 0 ? 1.1 : 0.9); }, { passive: false });
      this.canvas.addEventListener("keydown", (ev) => { if (ev.key === "+" || ev.key === "=") { ev.preventDefault(); this.zoomBy(1.15); } else if (ev.key === "-") { ev.preventDefault(); this.zoomBy(0.86); } else if (ev.key === "0") { ev.preventDefault(); this.fitView(); } });
    }

    _findNode(wx, wy) {
      const vis = this._visibleNodes(), isCard = this.mode === "LANES";
      for (let i = vis.length - 1; i >= 0; i--) { const n = vis[i], pill = !isCard && Math.abs(wx - n.x) <= (n.pillW || 56) / 2 && wy >= n.y + n.r + 2 && wy <= n.y + n.r + 6 + (n.pillH || 20); if ((isCard && wx >= n.x && wx <= n.x + n.w && wy >= n.y && wy <= n.y + n.h) || (!isCard && (Math.hypot(wx - n.x, wy - n.y) <= n.r + 8 || pill))) return n; }
      return null;
    }
    _loop() { this._draw(); requestAnimationFrame(() => this._loop()); }
  }
  window.SuperMemoryGraph = { ForceGraphCanvas };
})();
