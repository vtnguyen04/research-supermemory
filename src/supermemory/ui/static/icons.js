// Crisp 1.5px Icons, EN/VI i18n, Status Badges & Pagination Helpers
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
    document.querySelectorAll("[data-vi-title]").forEach((el) => {
      if (el.dataset.enTitle === undefined) el.dataset.enTitle = el.getAttribute("title") || "";
      const val = curLang === "vi" ? el.dataset.viTitle : el.dataset.enTitle;
      el.setAttribute("title", val);
      el.setAttribute("aria-label", val);
    });
    const btn = document.getElementById("btn-lang-toggle");
    if (btn) btn.textContent = curLang === "vi" ? "EN" : "VI";
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
    arrowLeft: '<path d="M13 8H3M6.5 4.5L3 8l3.5 3.5"/>',
    sidebarLeft: '<rect x="2" y="2.5" width="12" height="11" rx="2"/><path d="M6.25 2.5v11"/>',
    dockRight: '<rect x="2" y="2.5" width="12" height="11" rx="2"/><path d="M10 2.5v11"/>',
    expand: '<path d="M2.5 8h11M5.25 5.25L2.5 8l2.75 2.75M10.75 5.25L13.5 8l-2.75 2.75"/>',
    maximize: '<path d="M2.5 6V2.5H6M10 2.5h3.5V6M13.5 10v3.5H10M6 13.5H2.5V10"/><path d="M2.75 2.75L6.25 6.25M13.25 2.75L9.75 6.25M13.25 13.25L9.75 9.75M2.75 13.25L6.25 9.75"/>',
    crosshair: '<circle cx="8" cy="8" r="4.25"/><path d="M8 1.75v2.25M8 12v2.25M1.75 8H4M12 8h2.25"/>',
    copy: '<rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/><path d="M3 10.5V3.5A1.5 1.5 0 014.5 2h7"/>',
    download: '<path d="M8 2.25v7.5M5.25 7L8 9.75 10.75 7M3 13.25h10"/>',
    kanban: '<rect x="2" y="2.5" width="3.2" height="11" rx="0.9"/><rect x="6.4" y="2.5" width="3.2" height="7.5" rx="0.9"/><rect x="10.8" y="2.5" width="3.2" height="9.5" rx="0.9"/>',
    list: '<path d="M5.5 4h8.25M5.5 8h8.25M5.5 12h8.25"/><circle cx="2.75" cy="4" r="1"/><circle cx="2.75" cy="8" r="1"/><circle cx="2.75" cy="12" r="1"/>',
    plus: '<path d="M8 3.25v9.5M3.25 8h9.5"/>',
    play: '<path d="M5 3.5l7.5 4.5L5 12.5V3.5z"/>',
  };

  function svg(name, size = 16) {
    return `<svg viewBox="0 0 16 16" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${PATHS[name] || PATHS.dot}</svg>`;
  }

  function hydrateIcons(root = document) {
    root.querySelectorAll("[data-icon]").forEach((el) => { const n = el.getAttribute("data-icon"); if (n) el.innerHTML = svg(n, 15); });
  }

  const OK_SET = new Set(["ACTIVE", "KEEP", "VICTORY_CONFIRMED", "APPROVE", "AUDITED", "VERIFIED", "ENABLED", "RESOLVED", "ANSWERED", "DONE"]);
  const WARN_SET = new Set(["PROPOSED", "DESIGNED", "IMPLEMENTING", "CHALLENGED", "SEED", "PENDING", "OPEN", "QUEUED", "RUNNING", "READY"]);
  const ERR_SET = new Set(["REVERT", "FAILED", "REJECTED", "REQUEST_CHANGES", "DISABLED", "BLOCKED", "FAILURE_INSIGHT", "EARLY_KILLED", "CANCELLED_BY_KILL_GATE"]);

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
    const start = (cur - 1) * perPage, slice = items.slice(start, start + perPage), pad = pages > 1 ? Math.max(0, perPage - slice.length) : 0;
    if (total <= perPage) return { slice, pages, pad: 0, html: "" };
    const html = `<nav class="pager-bar" aria-label="Pagination ${esc(key)}">
      <span class="pager-info">${start + 1}&ndash;${Math.min(total, start + perPage)} / ${total}</span>
      <div class="pager-btns">
        <button type="button" class="btn btn-secondary btn-xs" data-page-key="${esc(key)}" data-page-to="${cur - 1}" ${cur <= 1 ? "disabled" : ""}>${tr("Prev", "Trước")}</button>
        <span class="pager-num">${tr("Page", "Trang")} ${cur}/${pages}</span>
        <button type="button" class="btn btn-secondary btn-xs" data-page-key="${esc(key)}" data-page-to="${cur + 1}" ${cur >= pages ? "disabled" : ""}>${tr("Next", "Sau")}</button>
      </div></nav>`;
    return { slice, pages, pad, html };
  }

  function bindPagers(root, onRerender) {
    root.querySelectorAll("[data-page-key]").forEach((btn) => {
      btn.addEventListener("click", () => { pageMap[btn.getAttribute("data-page-key")] = Number(btn.getAttribute("data-page-to")) || 1; onRerender(); });
    });
  }

  window.SuperMemoryIcons = { svg, hydrateIcons, statusTag, esc, paginate, bindPagers, tr, getLang, setLang, applyStaticLang };
})();
