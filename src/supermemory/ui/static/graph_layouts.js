// 4-Mode Graph Layout Algorithms: FORCE (Spring), RADIAL (Rings), HIERARCHY (DAG) & LANES (Cards)
(function () {
  const { tr } = window.SuperMemoryIcons;
  const ACCENTS = {
    LAW: "#141518", PROCEDURE: "#334155", GATE: "#2563EB", KNOWLEDGE_NODE: "#0284C7", OBSERVATION: "#0284C7",
    ALGORITHM: "#0D9488", IDEA: "#0284C7", PROPOSAL: "#D97706", EXPERIMENT: "#6D28D9", LESSON: "#DC2626", AGENT_RUN: "#15803D",
  };
  const LANES = [
    { key: "PROCEDURAL", en: "TIER L1 · CONSTITUTION & GATES", vi: "TẦNG L1 · HIẾN PHÁP & GATES", rx: 210, ry: 136 },
    { key: "SEMANTIC", en: "TIER L2 · SEMANTIC & INSIGHTS", vi: "TẦNG L2 · TRI THỨC & INSIGHT", rx: 332, ry: 214 },
    { key: "EPISODIC", en: "TIER L3 · EXPERIMENTS & PROPOSALS", vi: "TẦNG L3 · THỰC NGHIỆM & PROPOSALS", rx: 456, ry: 294 },
  ];
  const CARD_W = 204, CARD_H = 50, GAP_X = 14, GAP_Y = 10, LANE_GAP = 54;
  const cleanTitle = (s) => String(s || "").replace(/^(?:\[[^\]]+\]\s*|Guard for LESSON-\d+:\s*|SuperMemory v[\d.]+[:\s]*|VictoryAuditor Audit on\s*)/i, "");

  function stepForce(graph, vis) {
    if (graph.alpha < 0.008) return;
    const visSet = new Set(vis.map((n) => n.id)), free = (n) => !n.pinned && n !== graph.dragNode;
    for (let i = 0; i < vis.length; i++) {
      for (let j = i + 1; j < vis.length; j++) {
        const a = vis[i], b = vis[j], dx0 = b.x - a.x || 0.5, dy0 = b.y - a.y || 0.5;
        const d2 = Math.max(640, dx0 * dx0 + dy0 * dy0), d = Math.sqrt(d2), f = (8400 * graph.alpha) / d2;
        if (free(a)) { a.vx -= (dx0 / d) * f; a.vy -= (dy0 / d) * f; }
        if (free(b)) { b.vx += (dx0 / d) * f; b.vy += (dy0 / d) * f; }
        if (Math.abs(dx0) < 108 && Math.abs(dy0) < 48) {
          const px = (108 - Math.abs(dx0)) * 0.09 * Math.sign(dx0), py = (48 - Math.abs(dy0)) * 0.14 * Math.sign(dy0);
          if (free(a)) { a.vx -= px; a.vy -= py; }
          if (free(b)) { b.vx += px; b.vy += py; }
        }
      }
    }
    for (const e of graph.edges) {
      if (!visSet.has(e.source_id) || !visSet.has(e.target_id)) continue;
      const s = graph.nodeMap.get(e.source_id), t = graph.nodeMap.get(e.target_id);
      const dx = t.x - s.x, dy = t.y - s.y, d = Math.sqrt(dx * dx + dy * dy) || 1, f = (d - 185) * 0.018 * graph.alpha;
      if (free(s)) { s.vx += (dx / d) * f; s.vy += (dy / d) * f; }
      if (free(t)) { t.vx -= (dx / d) * f; t.vy -= (dy / d) * f; }
    }
    for (const n of vis) {
      if (free(n)) {
        n.vx = (n.vx - n.x * 0.004 * graph.alpha) * 0.78;
        n.vy = (n.vy - n.y * 0.009 * graph.alpha) * 0.78;
        n.x += n.vx; n.y += n.vy;
      }
    }
    graph.alpha *= 0.95;
  }

  function computeLayout(graph, vis, reset) {
    graph.laneBoxes = []; graph.bandLines = [];
    if (graph.mode === "FORCE") {
      if (reset) {
        vis.forEach((n, i) => {
          if (!n.pinned) {
            const a = i * 2.39996, r = 64 * Math.sqrt(i + 1);
            n.x = Math.cos(a) * r * 1.42; n.y = Math.sin(a) * r * 0.86; n.vx = 0; n.vy = 0;
          }
        });
      }
      graph.alpha = 1;
      for (let k = 0; k < 120; k++) stepForce(graph, vis);
    } else if (graph.mode === "RADIAL") {
      graph.alpha = 0;
      LANES.forEach((ln) => {
        const items = vis.filter((n) => n.memory_tier === ln.key);
        items.forEach((n, i) => {
          if (reset || !n.pinned) {
            const a = (2 * Math.PI * i) / Math.max(1, items.length) - Math.PI / 2;
            const st = items.length > 12 ? (i % 2 ? 1.09 : 0.91) : 1;
            n.x = Math.cos(a) * ln.rx * st; n.y = Math.sin(a) * ln.ry * st;
          }
        });
      });
    } else if (graph.mode === "HIERARCHY") {
      graph.alpha = 0; let curY = 0;
      LANES.forEach((ln) => {
        const items = vis.filter((n) => n.memory_tier === ln.key);
        if (!items.length) return;
        const perRow = 6, rows = Math.ceil(items.length / perRow);
        graph.bandLines.push({ title: `${tr(ln.en, ln.vi)} (${items.length})`, y: curY - 30 });
        items.forEach((n, i) => {
          if (reset || !n.pinned) {
            const rIdx = Math.floor(i / perRow), cIdx = i % perRow;
            const rowCnt = Math.min(perRow, items.length - rIdx * perRow);
            n.x = (cIdx - (rowCnt - 1) / 2) * 168; n.y = curY + rIdx * 88;
          }
        });
        curY += rows * 88 + 72;
      });
    } else {
      graph.alpha = 0; let curX = 0;
      LANES.forEach((ln) => {
        const items = vis.filter((n) => n.memory_tier === ln.key);
        if (!items.length) return;
        const cols = items.length > 6 ? 2 : 1, rows = Math.ceil(items.length / cols);
        const boxW = cols * CARD_W + (cols - 1) * GAP_X + 32, boxH = rows * CARD_H + (rows - 1) * GAP_Y + 56;
        items.forEach((n, i) => {
          if (reset || !n.pinned) {
            n.x = curX + 16 + (i % cols) * (CARD_W + GAP_X);
            n.y = 42 + Math.floor(i / cols) * (CARD_H + GAP_Y);
          }
        });
        graph.laneBoxes.push({ title: `${tr(ln.en, ln.vi)} (${items.length})`, x: curX, y: 0, w: boxW, h: boxH });
        curX += boxW + LANE_GAP;
      });
    }
  }

  window.SuperMemoryGraphLayouts = { ACCENTS, LANES, CARD_W, CARD_H, cleanTitle, stepForce, computeLayout };
})();
