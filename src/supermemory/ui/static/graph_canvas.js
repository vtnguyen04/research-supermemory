// Interactive Directed Knowledge Graph Canvas Renderer & Pointer Controller
(function () {
  const { esc } = window.SuperMemoryIcons;
  const { CARD_W, CARD_H, stepForce, computeLayout } = window.SuperMemoryGraphLayouts;
  const { drawGraphFrame } = window.SuperMemoryGraphDraw;
  const isAuxOrMerged = (n) => n.node_type === "AGENT_RUN" || n.status === "CONSOLIDATED" || n.status === "SUPERSEDED" || Boolean(n.metadata?.consolidated || n.metadata?.superseded_by);

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
      const base = this.nodes.filter((n) => (this.activeTier === "ALL" || n.memory_tier === this.activeTier) &&
        (this.activeType === "ALL" || n.node_type === this.activeType) && (!this.hideAux || n.id === this.selectedId || this.activeType === n.node_type || (!isAuxOrMerged(n) && n.status !== "ARCHIVED")));
      if (!this.hideAux || this.activeType !== "ALL" || base.length <= 45) return base;
      const bSet = new Set(base.map((n) => n.id)), linked = new Set();
      this.edges.forEach((e) => { if (bSet.has(e.source_id) && bSet.has(e.target_id)) { linked.add(e.source_id); linked.add(e.target_id); } });
      return base.filter((n) => n.node_type !== "OBSERVATION" || linked.has(n.id) || n.id === this.selectedId || this.highlightIds.has(n.id));
    }

    _emitStats(vis) {
      if (!this.onStats) return;
      const vs = new Set(vis.map((n) => n.id)), ec = this.edges.filter((e) => vs.has(e.source_id) && vs.has(e.target_id)).length;
      this.onStats({ visible: vis.length, total: this.nodes.length, edges: ec, pinned: vis.filter((n) => n.pinned).length });
    }

    focusNode(id) {
      const n = this.nodeMap.get(id); if (!n) return false;
      this.selectedId = id;
      if ((isAuxOrMerged(n) || n.status === "ARCHIVED") && this.hideAux) { this.hideAux = false; const chk = document.getElementById("chk-hide-aux"); if (chk) chk.checked = false; }
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
      if (reset && this.mode === "FORCE" && vis.length > 1) { for (let k = 0; k < 44; k++) stepForce(this, vis); }
      this._emitStats(vis);
      if (reset) this.fitView();
    }

    fitView() {
      const rect = this.canvas.parentElement.getBoundingClientRect(), vis = this._visibleNodes();
      if (!vis.length || !rect.width || !rect.height) return;
      const isCard = this.mode === "LANES", padX = isCard ? 28 : 78, padY = isCard ? 28 : 60;
      const minX = Math.min(...vis.map((n) => n.x)) - padX, maxX = Math.max(...vis.map((n) => n.x + (isCard ? n.w : 0))) + padX;
      const minY = Math.min(...vis.map((n) => n.y)) - padY, maxY = Math.max(...vis.map((n) => n.y + (isCard ? n.h : 34))) + padY;
      const topIn = 18, botIn = rect.width <= 768 ? 18 : 66, availH = Math.max(200, rect.height - topIn - botIn);
      this.scale = Math.min(1.12, Math.max(0.28, Math.min((rect.width - 36) / (maxX - minX || 1), availH / (maxY - minY || 1))));
      this.panX = rect.width / 2 - ((minX + maxX) / 2) * this.scale; this.panY = topIn + availH / 2 - ((minY + maxY) / 2) * this.scale;
    }

    zoomBy(f) { const r = this.canvas.getBoundingClientRect(); this._zoomAt(r.width / 2, r.height / 2, f); }
    _zoomAt(mx, my, f) { const nx = Math.min(2.6, Math.max(0.35, this.scale * f)); this.panX = mx - ((mx - this.panX) / this.scale) * nx; this.panY = my - ((my - this.panY) / this.scale) * nx; this.scale = nx; }
    screenToWorld(sx, sy) { return { x: (sx - this.panX) / this.scale, y: (sy - this.panY) / this.scale }; }

    _draw() {
      drawGraphFrame(this);
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
