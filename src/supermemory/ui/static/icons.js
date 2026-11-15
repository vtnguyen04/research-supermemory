// Crisp 1.5px Icons, EN/VI i18n, Safe Markdown Renderer, Text Excerpts & Pagination
(function () {
  const esc = (val) =>
    String(val ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");

  const qLang = new URLSearchParams(window.location.search).get("lang");
  let curLang = (qLang || localStorage.getItem("sm_lang") || "en").toLowerCase() === "vi" ? "vi" : "en";
  const getLang = () => curLang;
  const tr = (en, vi) => (curLang === "vi" ? vi : en);

  function setLang(next) {
    curLang = next === "vi" ? "vi" : "en";
    localStorage.setItem("sm_lang", curLang);
    applyStaticLang();
  }

  function applyStaticLang() {
    document.documentElement.lang = curLang;
    document.querySelectorAll("[data-vi]").forEach((el) => {
      if (el.dataset.en === undefined) el.dataset.en = el.textContent;
      el.textContent = curLang === "vi" ? el.dataset.vi : el.dataset.en;
    });
    document.querySelectorAll("[data-vi-ph]").forEach((el) => {
      if (el.dataset.enPh === undefined) el.dataset.enPh = el.getAttribute("placeholder") || "";
      el.setAttribute("placeholder", curLang === "vi" ? el.dataset.viPh : el.dataset.enPh);
    });
    const btn = document.getElementById("btn-lang-toggle");
    if (btn) btn.textContent = curLang === "vi" ? "EN" : "VI";
  }

  function cleanText(raw, maxLen = 0, stripTag = true) {
    const rawStr = String(raw ?? ""), hadTag = /^\[[A-Z0-9_ -]+\]\s*/.test(rawStr);
    let s = rawStr.replace(/^#+\s+/gm, "").replace(/\*\*([^*]+)\*\*/g, "$1").replace(/`([^`]+)`/g, "$1").replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
    if (stripTag) s = s.replace(/^(?:\[[A-Z0-9_ -]+\]\s*)+/, "");
    s = s.replace(/\s+/g, " ").trim();
    const unclosedParen = (s.match(/\(/g) || []).length > (s.match(/\)/g) || []).length;
    if (unclosedParen || (hadTag && s.length >= 68 && !/[.!?)…]$/.test(s))) {
      const sp = s.lastIndexOf(" ");
      s = (sp > 24 ? s.slice(0, sp) : s).replace(/[,;:\-(]+$/, "") + "…";
    }
    if (maxLen > 0 && s.length > maxLen) {
      const cut = s.slice(0, maxLen - 1), sp = cut.lastIndexOf(" ");
      s = (sp > maxLen * 0.55 ? cut.slice(0, sp) : cut).replace(/[,;:\-(]+$/, "") + "…";
    }
    return s;
  }

  function inlineMd(raw) {
    const codes = [];
    let s = esc(raw).replace(/`([^`]+)`/g, (_, c) => { codes.push(`<code class="md-code">${c}</code>`); return `\x00C${codes.length - 1}\x00`; });
    s = s.replace(/\[([^\]]+)\]\(((?:https?:\/\/|file:\/\/)[^\s)]+)\)/g, '<a class="file-anchor" href="$2" target="_blank" rel="noreferrer">$1</a>');
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s).,;:!?]|$)/g, "$1<em>$2</em>");
    return s.replace(/\x00C(\d+)\x00/g, (_, idx) => codes[Number(idx)] || "");
  }

  function renderMarkdown(raw, stripTopH1 = false) {
    const lines = String(raw ?? "").replace(/\r\n/g, "\n").split("\n"), out = [];
    let i = 0, skippedH1 = false;
    while (i < lines.length) {
      const ln = lines[i], t = ln.trim();
      if (!t) { i++; continue; }
      if (stripTopH1 && !skippedH1 && /^#\s+/.test(t)) { skippedH1 = true; i++; continue; }
      skippedH1 = true;
      if (t.startsWith("```")) {
        const buf = []; i++;
        while (i < lines.length && !lines[i].trim().startsWith("```")) buf.push(esc(lines[i++]));
        i++; out.push(`<pre class="code-block"><code>${buf.join("\n")}</code></pre>`); continue;
      }
      if (/^(?:---|\*\*\*|___)\s*$/.test(t)) { out.push('<hr class="md-hr" />'); i++; continue; }
      const hm = t.match(/^(#{1,4})\s+(.+)$/);
      if (hm) { const tag = hm[1].length <= 2 ? "h4" : "h5"; out.push(`<${tag} class="md-h">${inlineMd(hm[2])}</${tag}>`); i++; continue; }
      if (t.startsWith(">")) {
        const q = [];
        while (i < lines.length && lines[i].trim().startsWith(">")) q.push(inlineMd(lines[i++].trim().replace(/^>\s?/, "")));
        out.push(`<blockquote class="md-quote">${q.join("<br/>")}</blockquote>`); continue;
      }
      if (t.startsWith("|") && i + 1 < lines.length && /^\|\s*[-:]+/.test(lines[i + 1].trim())) {
        const cells = (r) => r.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        const hdr = cells(t).map((c) => `<th>${inlineMd(c)}</th>`).join(""); i += 2;
        const rows = [];
        while (i < lines.length && lines[i].trim().startsWith("|")) rows.push(`<tr>${cells(lines[i++]).map((c) => `<td>${inlineMd(c)}</td>`).join("")}</tr>`);
        out.push(`<div class="md-table-wrap"><table class="md-table"><thead><tr>${hdr}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`); continue;
      }
      if (/^(?:[-*•]|\d+\.)\s+/.test(t)) {
        const ord = /^\d+\.\s+/.test(t), tag = ord ? "ol" : "ul", items = [];
        const rx = ord ? /^\d+\.\s+(.*)$/ : /^(?:[-*•])\s+(.*)$/;
        while (i < lines.length && rx.test(lines[i].trim())) {
          let body = lines[i++].trim().replace(rx, "$1");
          body = body.replace(/^\[([ xX])\]\s+/, (_, c) => `[${c.trim() ? "x" : " "}] `);
          items.push(`<li>${inlineMd(body)}</li>`);
        }
        out.push(`<${tag} class="md-list${ord ? " md-ol" : ""}">${items.join("")}</${tag}>`); continue;
      }
      if (/^N\/A$/i.test(t)) { out.push('<p class="md-na">&mdash;</p>'); i++; continue; }
      const p = [];
      while (i < lines.length && lines[i].trim() && !/^(?:#{1,4}\s|```|>|\||(?:---|\*\*\*)|(?:[-*•]|\d+\.)\s)/.test(lines[i].trim())) p.push(inlineMd(lines[i++].trim()));
      out.push(`<p class="md-p">${p.join(" ")}</p>`);
    }
    return out.join("") || `<p class="md-na">&mdash;</p>`;
  }

  const PATHS = {
    topology: '<circle cx="4.5" cy="4.5" r="1.75"/><circle cx="11.5" cy="4.5" r="1.75"/><circle cx="8" cy="11.5" r="1.75"/><path d="M6.25 4.5h3.5M5.4 6l1.75 3.8M10.6 6l-1.75 3.8"/>',
    layers: '<path d="M8 2.25L14 5.5 8 8.75 2 5.5 8 2.25z"/><path d="M2 8.5L8 11.75 14 8.5"/><path d="M2 11.25L8 14.5 14 11.25"/>',
    shield: '<path d="M8 1.75l5.25 2v4.1c0 3.35-2.25 5.45-5.25 6.4-3-0.95-5.25-3.05-5.25-6.4v-4.1L8 1.75z"/><path d="M5.75 8.1l1.55 1.55 3.1-3.1"/>',
    activity: '<path d="M1.75 8h2.75l1.75-4.25 3.25 8.5 1.85-4.25h2.9"/>',
    gitBranch: '<circle cx="5" cy="4" r="1.6"/><circle cx="5" cy="12" r="1.6"/><circle cx="11.5" cy="6.5" r="1.6"/><path d="M5 5.6v4.8M9.9 6.5H7.5c-1.4 0-2.5 1.1-2.5 2.5"/>',
    terminal: '<rect x="2" y="2.5" width="12" height="11" rx="2"/><path d="M4.75 6.25L7.25 8l-2.5 1.75M8.5 10h2.75"/>',
    search: '<circle cx="7.25" cy="7.25" r="4.5"/><path d="M10.6 10.6l3.15 3.15"/>',
    check: '<path d="M3.25 8.25l3.1 3.1 6.4-6.4"/>',
    warn: '<path d="M8 2.5l5.75 10.5H2.25L8 2.5z"/><path d="M8 6.5v3M8 11.25h.01"/>',
    x: '<path d="M4.25 4.25l7.5 7.5M11.75 4.25l-7.5 7.5"/>',
    dot: '<circle cx="8" cy="8" r="3"/>',
    arrowRight: '<path d="M3 8h10M9.5 4.5L13 8l-3.5 3.5"/>',
    plus: '<path d="M8 3.25v9.5M3.25 8h9.5"/>',
    lock: '<rect x="3.25" y="7.25" width="9.5" height="6.5" rx="1.5"/><path d="M5.25 7.25V5.2a2.75 2.75 0 015.5 0v2.05"/>',
  };

  function svg(name, size = 16) {
    return `<svg viewBox="0 0 16 16" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${PATHS[name] || PATHS.dot}</svg>`;
  }

  function hydrateIcons(root = document) {
    root.querySelectorAll("[data-icon]").forEach((el) => { const n = el.getAttribute("data-icon"); if (n) el.innerHTML = svg(n, 15); });
  }

  const OK_SET = new Set(["ACTIVE", "KEEP", "VICTORY_CONFIRMED", "APPROVE", "AUDITED", "VERIFIED", "ENABLED"]);
  const WARN_SET = new Set(["PROPOSED", "DESIGNED", "IMPLEMENTING", "CHALLENGED", "SEED", "PENDING"]);
  const ERR_SET = new Set(["REVERT", "FAILED", "REJECTED", "REQUEST_CHANGES", "DISABLED", "BLOCKED", "FAILURE_INSIGHT"]);

  function statusTag(rawStatus, labelOverride = "") {
    const code = String(rawStatus || "ACTIVE").toUpperCase(), label = labelOverride || code;
    let cls = "status-tag", icon = "dot";
    if (OK_SET.has(code)) { cls += " status-ok"; icon = "check"; }
    else if (WARN_SET.has(code)) { cls += " status-warn"; icon = "warn"; }
    else if (ERR_SET.has(code)) { cls += " status-err"; icon = "x"; }
    return `<span class="${cls}"><span class="status-icon" aria-hidden="true">${svg(icon, 12)}</span><span>${esc(label)}</span></span>`;
  }

  const pageMap = {};
  function paginate(items, key, perPage = 5) {
    const total = items.length, pages = Math.max(1, Math.ceil(total / perPage));
    const cur = Math.min(pages, Math.max(1, pageMap[key] || 1));
    pageMap[key] = cur;
    const start = (cur - 1) * perPage, slice = items.slice(start, start + perPage);
    if (total <= perPage) return { slice, html: "" };
    const html = `<nav class="pager-bar" aria-label="Pagination ${esc(key)}">
      <span class="pager-info">${start + 1}&ndash;${Math.min(total, start + perPage)} / ${total}</span>
      <div class="pager-btns">
        <button type="button" class="btn btn-secondary btn-xs" data-page-key="${esc(key)}" data-page-to="${cur - 1}" ${cur <= 1 ? "disabled" : ""}>${tr("Prev", "Trước")}</button>
        <span class="pager-num">${tr("Page", "Trang")} ${cur}/${pages}</span>
        <button type="button" class="btn btn-secondary btn-xs" data-page-key="${esc(key)}" data-page-to="${cur + 1}" ${cur >= pages ? "disabled" : ""}>${tr("Next", "Sau")}</button>
      </div></nav>`;
    return { slice, html };
  }

  function bindPagers(root, onRerender) {
    root.querySelectorAll("[data-page-key]").forEach((btn) => {
      btn.addEventListener("click", () => { pageMap[btn.getAttribute("data-page-key")] = Number(btn.getAttribute("data-page-to")) || 1; onRerender(); });
    });
  }

  window.SuperMemoryIcons = { svg, hydrateIcons, statusTag, esc, cleanText, inlineMd, renderMarkdown, paginate, bindPagers, tr, getLang, setLang, applyStaticLang };
})();
