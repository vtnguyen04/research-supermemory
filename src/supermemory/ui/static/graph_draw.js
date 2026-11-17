// High-Contrast >=13px Canvas Frame Renderer for ForceGraphCanvas (WCAG AA Daylight Theme)
(function () {
  const { ACCENTS, LANES, cleanTitle, stepForce } = window.SuperMemoryGraphLayouts;

  function drawGraphFrame(graph) {
    const rect = graph.canvas.parentElement.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const vis = graph._visibleNodes(), dpr = window.devicePixelRatio || 1;
    if (graph.mode === "FORCE" && graph.alpha >= 0.008) stepForce(graph, vis);
    const cw = Math.floor(rect.width * dpr), ch = Math.floor(rect.height * dpr);
    if (graph.canvas.width !== cw || graph.canvas.height !== ch) { graph.canvas.width = cw; graph.canvas.height = ch; }
    const ctx = graph.ctx, visSet = new Set(vis.map((n) => n.id)), isCard = graph.mode === "LANES", step = 24 * graph.scale;
    ctx.save(); ctx.scale(dpr, dpr); ctx.clearRect(0, 0, rect.width, rect.height);
    if (step >= 12) {
      ctx.fillStyle = "#DCD8CE";
      for (let x = ((graph.panX % step) + step) % step; x < rect.width; x += step) {
        for (let y = ((graph.panY % step) + step) % step; y < rect.height; y += step) ctx.fillRect(x, y, 1.5, 1.5);
      }
    }
    ctx.translate(graph.panX, graph.panY); ctx.scale(graph.scale, graph.scale);
    if (graph.mode === "RADIAL") {
      ctx.strokeStyle = "#D5D1C7"; ctx.setLineDash([6, 6]); ctx.lineWidth = 1.1;
      LANES.forEach((ln) => { ctx.beginPath(); ctx.ellipse(0, 0, ln.rx, ln.ry, 0, 0, Math.PI * 2); ctx.stroke(); });
      ctx.setLineDash([]);
    } else if (graph.mode === "HIERARCHY") {
      for (const bl of graph.bandLines) {
        ctx.strokeStyle = "#DEDAD0"; ctx.setLineDash([5, 5]); ctx.beginPath(); ctx.moveTo(-560, bl.y); ctx.lineTo(560, bl.y); ctx.stroke(); ctx.setLineDash([]);
        ctx.fillStyle = "#525763"; ctx.font = '700 13px "Bear Sans UI", "Noto Sans", sans-serif'; ctx.fillText(bl.title, -552, bl.y - 8);
      }
    } else if (isCard) {
      for (const lb of graph.laneBoxes) {
        ctx.fillStyle = "rgba(255,255,255,0.58)"; ctx.strokeStyle = "#DEDAD0"; ctx.lineWidth = 1; ctx.beginPath(); ctx.roundRect(lb.x, lb.y, lb.w, lb.h, 14); ctx.fill(); ctx.stroke();
        ctx.fillStyle = "#484C56"; ctx.font = '700 13px "Bear Sans UI", "Noto Sans", sans-serif'; ctx.fillText(lb.title, lb.x + 16, lb.y + 26);
      }
    }

    const focusId = graph.hoveredId || graph.selectedId, ego = new Set(), edgeBadges = [];
    if (focusId) {
      ego.add(focusId);
      graph.edges.forEach((e) => { if (e.source_id === focusId) ego.add(e.target_id); if (e.target_id === focusId) ego.add(e.source_id); });
    }
    for (const e of graph.edges) {
      if (!visSet.has(e.source_id) || !visSet.has(e.target_id)) continue;
      const s = graph.nodeMap.get(e.source_id), t = graph.nodeMap.get(e.target_id), active = focusId && (e.source_id === focusId || e.target_id === focusId);
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

    const fs = Math.max(13, Math.round(13 / Math.min(1, Math.max(0.72, graph.scale)))), pillH = fs + 8;
    for (const eb of edgeBadges) {
      ctx.font = `600 ${fs}px "JetBrains Mono", monospace`; const w = ctx.measureText(eb.txt).width + 12;
      ctx.fillStyle = "rgba(255,255,255,0.95)"; ctx.strokeStyle = "#141518"; ctx.lineWidth = 1; ctx.beginPath(); ctx.roundRect(eb.x - w / 2, eb.y - 10, w, 20, 5); ctx.fill(); ctx.stroke();
      ctx.fillStyle = "#141518"; ctx.textAlign = "center"; ctx.fillText(eb.txt, eb.x, eb.y + 4); ctx.textAlign = "start";
    }
    const cullPills = !isCard && vis.length > 48 && graph.scale < 0.88, placed = [];
    const prio = (n) => (n.id === focusId ? 9 : ego.has(n.id) || graph.highlightIds.has(n.id) ? 7 : /LAW|PROPOSAL|BOTTLENECK|METHOD_CARD/.test(n.node_type) ? 4 : n.r);
    for (const n of [...vis].sort((a, b) => (a.id === focusId ? 1 : 0) - (b.id === focusId ? 1 : 0))) {
      const dimmed = (ego.size && !ego.has(n.id)) || (graph.highlightIds.size && !graph.highlightIds.has(n.id)), active = n.id === graph.selectedId || n.id === graph.hoveredId || graph.highlightIds.has(n.id), acc = ACCENTS[n.node_type] || "#475569";
      ctx.globalAlpha = dimmed ? 0.22 : 1; n.pillW = 0; n.pillH = 0;
      if (isCard) {
        const lbl = cleanTitle(n.title);
        ctx.fillStyle = "#FFFFFF"; ctx.strokeStyle = active ? "#141518" : "#D5D1C7"; ctx.lineWidth = active ? 2 : 1;
        ctx.beginPath(); ctx.roundRect(n.x, n.y, n.w, n.h, 10); ctx.fill(); ctx.stroke();
        ctx.fillStyle = acc; ctx.beginPath(); ctx.roundRect(n.x + 1, n.y + 8, 4, n.h - 16, 2); ctx.fill();
        ctx.font = '700 13px "JetBrains Mono", monospace'; ctx.fillText(n.id.slice(0, 19), n.x + 13, n.y + 20);
        ctx.fillStyle = "#141518"; ctx.font = '600 13.5px "Bear Sans UI", "Noto Sans", sans-serif'; ctx.fillText(lbl.length > 24 ? `${lbl.slice(0, 23)}…` : lbl, n.x + 13, n.y + 38);
      } else {
        ctx.fillStyle = acc; ctx.strokeStyle = active ? "#141518" : n.pinned ? "#D97706" : "#FFFFFF"; ctx.lineWidth = active ? 3 : 2.2;
        ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      }
    }
    if (!isCard) {
      for (const n of [...vis].sort((a, b) => prio(b) - prio(a))) {
        const dimmed = (ego.size && !ego.has(n.id)) || (graph.highlightIds.size && !graph.highlightIds.has(n.id)), active = n.id === graph.selectedId || n.id === graph.hoveredId || graph.highlightIds.has(n.id), lbl = cleanTitle(n.title);
        if (dimmed && cullPills) continue;
        const txt = active ? `${n.id} · ${lbl.slice(0, 22)}` : n.id;
        ctx.font = active ? `700 ${fs + 1}px "Bear Sans UI", "Noto Sans", sans-serif` : `600 ${fs}px "JetBrains Mono", monospace`;
        const tw = ctx.measureText(txt).width + 12, bx = n.x - tw / 2, by = n.y + n.r + 4;
        if (cullPills && !active && placed.some((p) => bx < p.x2 + 4 && bx + tw > p.x1 - 4 && by < p.y2 + 3 && by + pillH > p.y1 - 3)) continue;
        placed.push({ x1: bx, x2: bx + tw, y1: by, y2: by + pillH }); n.pillW = tw; n.pillH = pillH; ctx.globalAlpha = dimmed ? 0.22 : 1;
        ctx.fillStyle = "rgba(255,255,255,0.94)"; ctx.strokeStyle = active ? "#141518" : "#DEDAD0"; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.roundRect(bx, by, tw, pillH, 6); ctx.fill(); ctx.stroke();
        ctx.fillStyle = "#141518"; ctx.textAlign = "center"; ctx.fillText(txt, n.x, by + Math.round(pillH * 0.72)); ctx.textAlign = "start";
      }
    }
    ctx.globalAlpha = 1; ctx.restore();
  }

  window.SuperMemoryGraphDraw = { drawGraphFrame };
})();
