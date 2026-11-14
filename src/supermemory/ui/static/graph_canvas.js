// Force-Directed Interactive Canvas Renderer for SuperMemory Knowledge Graph
(function () {
  const TYPE_COLORS = {
    LAW: "#10b981",
    PROCEDURE: "#34d399",
    GATE: "#06b6d4",
    LESSON: "#f43f5e",
    EXPERIMENT: "#8b5cf6",
    PROPOSAL: "#f59e0b",
    IDEA: "#38bdf8",
    ALGORITHM: "#0ea5e9",
    KNOWLEDGE_NODE: "#818cf8",
    OBSERVATION: "#a78bfa",
    AGENT_RUN: "#14b8a6",
  };

  class ForceGraphCanvas {
    constructor(canvas, tooltip, onSelectNode) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d");
      this.tooltip = tooltip;
      this.onSelectNode = onSelectNode;
      this.nodes = [];
      this.edges = [];
      this.nodeMap = new Map();
      this.hiddenTypes = new Set();
      this.hiddenTiers = new Set();
      this.highlightIds = new Set();
      this.selectedId = null;
      this.hoveredNode = null;
      this.dragNode = null;
      this.panX = 0;
      this.panY = 0;
      this.scale = 1;
      this.isPanning = false;
      this.alpha = 1;
      this._bindEvents();
      this._loop();
    }

    setData(nodes, edges) {
      const prevPos = new Map(this.nodes.map((n) => [n.id, { x: n.x, y: n.y, pinned: n.pinned }]));
      const types = Array.from(new Set(nodes.map((n) => n.node_type)));
      this.nodes = nodes.map((n, idx) => {
        const old = prevPos.get(n.id);
        const tIdx = Math.max(0, types.indexOf(n.node_type));
        const angle = (tIdx / Math.max(1, types.length)) * Math.PI * 2 + (idx % 17) * 0.19;
        const radius = 140 + (idx % 9) * 28;
        return {
          ...n,
          x: old ? old.x : Math.cos(angle) * radius,
          y: old ? old.y : Math.sin(angle) * radius,
          vx: 0,
          vy: 0,
          pinned: old ? old.pinned : false,
          r: n.node_type === "LAW" ? 11 : n.node_type === "PROPOSAL" ? 9.5 : 7.5,
        };
      });
      this.nodeMap = new Map(this.nodes.map((n) => [n.id, n]));
      this.edges = edges.filter((e) => this.nodeMap.has(e.source_id) && this.nodeMap.has(e.target_id));
      this.alpha = 1;
      this.fitView();
    }

    relayout() {
      this.nodes.forEach((n, i) => {
        n.pinned = false;
        const a = i * 2.39996;
        const r = 35 * Math.sqrt(i + 1);
        n.x = Math.cos(a) * r;
        n.y = Math.sin(a) * r;
        n.vx = 0;
        n.vy = 0;
      });
      this.alpha = 1;
    }

    fitView() {
      const rect = this.canvas.parentElement.getBoundingClientRect();
      this.panX = rect.width / 2;
      this.panY = rect.height / 2;
      this.scale = this.nodes.length > 60 ? 0.75 : 0.95;
    }

    screenToWorld(sx, sy) {
      return { x: (sx - this.panX) / this.scale, y: (sy - this.panY) / this.scale };
    }

    _visibleNodes() {
      return this.nodes.filter(
        (n) => !this.hiddenTypes.has(n.node_type) && !this.hiddenTiers.has(n.memory_tier)
      );
    }

    _stepPhysics() {
      if (this.alpha < 0.008) return;
      const vis = this._visibleNodes();
      const nLen = vis.length;
      for (let i = 0; i < nLen; i++) {
        const a = vis[i];
        for (let j = i + 1; j < nLen; j++) {
          const b = vis[j];
          let dx = b.x - a.x;
          let dy = b.y - a.y;
          let d2 = dx * dx + dy * dy + 1;
          if (d2 > 140000) continue;
          const f = (950 * this.alpha) / d2;
          const fx = dx * f;
          const fy = dy * f;
          if (!a.pinned) { a.vx -= fx; a.vy -= fy; }
          if (!b.pinned) { b.vx += fx; b.vy += fy; }
        }
      }
      for (const e of this.edges) {
        const s = this.nodeMap.get(e.source_id);
        const t = this.nodeMap.get(e.target_id);
        if (!s || !t || this.hiddenTypes.has(s.node_type) || this.hiddenTypes.has(t.node_type)) continue;
        const dx = t.x - s.x;
        const dy = t.y - s.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (dist - 95) * 0.025 * this.alpha;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        if (!s.pinned) { s.vx += fx; s.vy += fy; }
        if (!t.pinned) { t.vx -= fx; t.vy -= fy; }
      }
      for (const n of vis) {
        if (n.pinned) continue;
        n.vx = (n.vx - n.x * 0.004 * this.alpha) * 0.82;
        n.vy = (n.vy - n.y * 0.004 * this.alpha) * 0.82;
        n.x += n.vx;
        n.y += n.vy;
      }
      this.alpha *= 0.985;
    }

    _draw() {
      const rect = this.canvas.parentElement.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) return;
      const dpr = window.devicePixelRatio || 1;
      if (this.canvas.width !== Math.floor(rect.width * dpr) || this.canvas.height !== Math.floor(rect.height * dpr)) {
        this.canvas.width = Math.floor(rect.width * dpr);
        this.canvas.height = Math.floor(rect.height * dpr);
      }
      const ctx = this.ctx;
      ctx.save();
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, rect.width, rect.height);
      ctx.translate(this.panX, this.panY);
      ctx.scale(this.scale, this.scale);

      const egoSet = new Set();
      if (this.selectedId) {
        egoSet.add(this.selectedId);
        this.edges.forEach((e) => {
          if (e.source_id === this.selectedId) egoSet.add(e.target_id);
          if (e.target_id === this.selectedId) egoSet.add(e.source_id);
        });
      }

      // Draw directed edges
      for (const e of this.edges) {
        const s = this.nodeMap.get(e.source_id);
        const t = this.nodeMap.get(e.target_id);
        if (!s || !t || this.hiddenTypes.has(s.node_type) || this.hiddenTypes.has(t.node_type)) continue;
        const activeEdge = this.selectedId && (e.source_id === this.selectedId || e.target_id === this.selectedId);
        ctx.strokeStyle = activeEdge ? "#38bdf8" : egoSet.size ? "rgba(71,85,105,0.16)" : "rgba(100,116,139,0.34)";
        ctx.lineWidth = activeEdge ? 1.8 : 1;
        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(t.x, t.y);
        ctx.stroke();
        if (activeEdge && this.scale > 0.55) {
          ctx.fillStyle = "#94a3b8";
          ctx.font = "9px Inter, sans-serif";
          ctx.fillText(e.relation, (s.x + t.x) / 2 + 4, (s.y + t.y) / 2 - 3);
        }
      }

      // Draw nodes
      for (const n of this._visibleNodes()) {
        const dimmed = (egoSet.size && !egoSet.has(n.id)) || (this.highlightIds.size && !this.highlightIds.has(n.id));
        const color = TYPE_COLORS[n.node_type] || "#94a3b8";
        ctx.globalAlpha = dimmed ? 0.2 : 1;
        ctx.beginPath();
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        if (n.id === this.selectedId || this.highlightIds.has(n.id)) {
          ctx.lineWidth = 2.6;
          ctx.strokeStyle = "#ffffff";
          ctx.stroke();
        }
        if (this.scale > 0.62 || n.node_type === "LAW" || n.id === this.selectedId) {
          ctx.fillStyle = "#e2e8f0";
          ctx.font = `${n.node_type === "LAW" ? "600 10.5px" : "10px"} Inter, sans-serif`;
          ctx.fillText(n.id, n.x + n.r + 4, n.y + 3.5);
        }
      }
      ctx.globalAlpha = 1;
      ctx.restore();
    }

    _bindEvents() {
      this.canvas.addEventListener("mousedown", (ev) => {
        const rect = this.canvas.getBoundingClientRect();
        const pt = this.screenToWorld(ev.clientX - rect.left, ev.clientY - rect.top);
        const hit = this._findNode(pt.x, pt.y);
        if (hit) {
          this.dragNode = hit;
          hit.pinned = true;
          this.selectedId = hit.id;
          this.onSelectNode(hit);
        } else {
          this.isPanning = true;
          this.lastMouse = { x: ev.clientX, y: ev.clientY };
        }
      });

      window.addEventListener("mousemove", (ev) => {
        const rect = this.canvas.getBoundingClientRect();
        if (this.dragNode) {
          const pt = this.screenToWorld(ev.clientX - rect.left, ev.clientY - rect.top);
          this.dragNode.x = pt.x;
          this.dragNode.y = pt.y;
          this.alpha = Math.max(this.alpha, 0.25);
          return;
        }
        if (this.isPanning) {
          this.panX += ev.clientX - this.lastMouse.x;
          this.panY += ev.clientY - this.lastMouse.y;
          this.lastMouse = { x: ev.clientX, y: ev.clientY };
          return;
        }
        if (ev.target !== this.canvas) {
          this.tooltip.classList.add("hidden");
          return;
        }
        const pt = this.screenToWorld(ev.clientX - rect.left, ev.clientY - rect.top);
        const hit = this._findNode(pt.x, pt.y);
        if (hit) {
          this.tooltip.classList.remove("hidden");
          this.tooltip.style.left = `${ev.clientX - rect.left + 14}px`;
          this.tooltip.style.top = `${ev.clientY - rect.top + 14}px`;
          this.tooltip.innerHTML = `<strong>[${hit.node_type}] ${hit.id}</strong><br/>${hit.title}`;
        } else {
          this.tooltip.classList.add("hidden");
        }
      });

      window.addEventListener("mouseup", () => {
        this.dragNode = null;
        this.isPanning = false;
      });

      this.canvas.addEventListener("wheel", (ev) => {
        ev.preventDefault();
        const rect = this.canvas.getBoundingClientRect();
        const mx = ev.clientX - rect.left;
        const my = ev.clientY - rect.top;
        const zoom = ev.deltaY < 0 ? 1.12 : 0.89;
        const nextScale = Math.min(3.5, Math.max(0.22, this.scale * zoom));
        this.panX = mx - ((mx - this.panX) / this.scale) * nextScale;
        this.panY = my - ((my - this.panY) / this.scale) * nextScale;
        this.scale = nextScale;
      }, { passive: false });
    }

    _findNode(wx, wy) {
      const vis = this._visibleNodes();
      for (let i = vis.length - 1; i >= 0; i--) {
        const n = vis[i];
        const dx = wx - n.x;
        const dy = wy - n.y;
        if (dx * dx + dy * dy <= (n.r + 5) * (n.r + 5)) return n;
      }
      return null;
    }

    _loop() {
      this._stepPhysics();
      this._draw();
      requestAnimationFrame(() => this._loop());
    }
  }

  window.SuperMemoryGraph = { ForceGraphCanvas, TYPE_COLORS };
})();
