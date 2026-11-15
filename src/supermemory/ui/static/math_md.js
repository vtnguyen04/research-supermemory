// Zero-CDN Recursive LaTeX Math ($...$, $$...$$) & Scientific Markdown Compiler
(function () {
  const { esc } = window.SuperMemoryIcons;

  const BB = { A: "𝔸", B: "𝔹", C: "ℂ", D: "𝔻", E: "𝔼", F: "𝔽", G: "𝔾", H: "ℍ", I: "𝕀", J: "𝕁", K: "𝕂", L: "𝕃", M: "𝕄", N: "ℕ", O: "𝕆", P: "ℙ", Q: "ℚ", R: "ℝ", S: "𝕊", T: "𝕋", U: "𝕌", V: "𝕍", W: "𝕎", X: "𝕏", Y: "𝕐", Z: "ℤ", 1: "𝟙" };
  const CAL = { A: "𝒜", B: "ℬ", C: "𝒞", D: "𝒟", E: "ℰ", F: "ℱ", G: "𝒢", H: "ℋ", I: "ℐ", J: "𝒥", K: "𝒦", L: "ℒ", M: "ℳ", N: "𝒩", O: "𝒪", P: "𝒫", Q: "𝒬", R: "ℛ", S: "𝒮", T: "𝒯", U: "𝒰", V: "𝒱", W: "𝒲", X: "𝒳", Y: "𝒴", Z: "𝒵" };
  const SYM = {
    alpha: "α", beta: "β", gamma: "γ", delta: "δ", epsilon: "ε", varepsilon: "ε", zeta: "ζ", eta: "η", theta: "θ", vartheta: "ϑ", iota: "ι", kappa: "κ", lambda: "λ", mu: "μ", nu: "ν", xi: "ξ", pi: "π", rho: "ρ", varrho: "ϱ", sigma: "σ", varsigma: "ς", tau: "τ", upsilon: "υ", phi: "φ", varphi: "ϕ", chi: "χ", psi: "ψ", omega: "ω",
    Gamma: "Γ", Delta: "Δ", Theta: "Θ", Lambda: "Λ", Xi: "Ξ", Pi: "Π", Sigma: "Σ", Upsilon: "Υ", Phi: "Φ", Psi: "Ψ", Omega: "Ω", ell: "ℓ", hbar: "ℏ",
    in: "∈", notin: "∉", ni: "∋", subset: "⊂", subseteq: "⊆", supset: "⊃", supseteq: "⊇", cup: "∪", cap: "∩", setminus: "∖", emptyset: "∅", varnothing: "∅",
    le: "≤", leq: "≤", ge: "≥", geq: "≥", ll: "≪", gg: "≫", ne: "≠", neq: "≠", approx: "≈", sim: "∼", simeq: "≃", cong: "≅", equiv: "≡", propto: "∝", prec: "≺", preceq: "≼", succ: "≻", succeq: "≽",
    pm: "±", mp: "∓", times: "×", div: "÷", cdot: "·", cdots: "⋯", ldots: "…", dots: "…", vdots: "⋮", circ: "∘", bullet: "•", star: "⋆", ast: "∗", oplus: "⊕", ominus: "⊖", otimes: "⊗", odot: "⊙",
    nabla: "∇", partial: "∂", infty: "∞", forall: "∀", exists: "∃", neg: "¬", lnot: "¬", land: "∧", lor: "∨", top: "⊤", bot: "⊥", perp: "⊥", parallel: "∥", mid: "∣", triangle: "△", triangleq: "≜",
    to: "→", rightarrow: "→", leftarrow: "←", leftrightarrow: "↔", Rightarrow: "⇒", Leftarrow: "⇐", Leftrightarrow: "⇔", iff: "⇔", implies: "⟹", mapsto: "↦", uparrow: "↑", downarrow: "↓",
    langle: "⟨", rangle: "⟩", lceil: "⌈", rceil: "⌉", lfloor: "⌊", rfloor: "⌋", S: "§",
  };
  const BIG = { sum: "∑", prod: "∏", coprod: "∐", int: "∫", iint: "∬", oint: "∮", bigcup: "⋃", bigcap: "⋂", bigoplus: "⨁", bigotimes: "⨂" };
  const OPS = new Set(["min", "max", "argmin", "argmax", "sup", "inf", "lim", "log", "ln", "exp", "sin", "cos", "tan", "tanh", "sinh", "cosh", "det", "tr", "diag", "rank", "dim", "ker", "Pr", "Var", "Cov", "KL"]);
  const ACC = { hat: "&#710;", widehat: "&#710;", dot: "&middot;", ddot: "&uml;", tilde: "&#732;", widetilde: "&#732;", vec: "&rarr;" };
  const DROP = new Set(["left", "right", "bigl", "bigr", "Bigl", "Bigr", "biggl", "biggr", "displaystyle", "textstyle", "scriptstyle", "limits", "nolimits"]);

  function renderTex(src, display = false) {
    const s = String(src ?? "").trim();
    let p = 0;
    const skip = () => { while (p < s.length && /\s/.test(s[p])) p++; };
    const readRawBrace = () => {
      skip();
      if (s[p] !== "{") return p < s.length ? s[p++] : "";
      let d = 1, out = ""; p++;
      while (p < s.length && d > 0) { if (s[p] === "{") d++; else if (s[p] === "}") d--; if (d > 0) out += s[p]; p++; }
      return out;
    };
    const readGroup = () => { skip(); if (s[p] === "{") { p++; return parseExpr("}"); } return parseAtom(); };

    function parseAtom() {
      skip();
      if (p >= s.length) return "";
      const ch = s[p];
      if (ch === "{") { p++; return `<span class="m-grp">${parseExpr("}")}</span>`; }
      if (ch === "\\") {
        p++;
        if (p >= s.length) return "";
        if (!/[a-zA-Z]/.test(s[p])) {
          const c = s[p++];
          const sp = { ",": "&#8201;", ";": "&ensp;", ":": "&ensp;", "!": "", " ": "&nbsp;", "{": "{", "}": "}", "|": "‖", "\\": "<br/>", "%": "%", _: "_", $: "$", "&": "&amp;" };
          return sp[c] ?? esc(c);
        }
        let cmd = "";
        while (p < s.length && /[a-zA-Z]/.test(s[p])) cmd += s[p++];
        if (DROP.has(cmd)) { skip(); if ((cmd === "left" || cmd === "right") && s[p] === ".") p++; return ""; }
        if (cmd === "quad") return "&emsp;";
        if (cmd === "qquad") return "&emsp;&emsp;";
        if (cmd === "begin" || cmd === "end") { readRawBrace(); return ""; }
        if (cmd === "frac" || cmd === "dfrac" || cmd === "tfrac") return `<span class="m-frac"><span class="m-num">${readGroup()}</span><span class="m-den">${readGroup()}</span></span>`;
        if (cmd === "sqrt") { skip(); if (s[p] === "[") { while (p < s.length && s[p] !== "]") p++; p++; } return `<span class="m-sqrt">&radic;<span class="m-rad">${readGroup()}</span></span>`; }
        if (["text", "textrm", "textup", "mbox", "operatorname"].includes(cmd)) {
          const tx = esc(readRawBrace().replace(/---/g, "—").replace(/--/g, "–")).replace(/^ | $/g, "&#8201;");
          return `<span class="m-text">${tx}</span>`;
        }
        if (["textbf", "mathbf", "boldsymbol", "bm"].includes(cmd)) return `<strong class="m-bf">${readGroup()}</strong>`;
        if (cmd === "textit" || cmd === "mathit") return `<em>${readGroup()}</em>`;
        if (cmd === "texttt" || cmd === "mathtt") return `<code class="md-code">${esc(readRawBrace())}</code>`;
        if (cmd === "mathbb") { const raw = readRawBrace(); return `<span class="m-bb">${Array.from(raw).map((c) => BB[c] || esc(c)).join("")}</span>`; }
        if (cmd === "mathcal" || cmd === "mathscr") { const raw = readRawBrace(); return `<span class="m-cal">${Array.from(raw).map((c) => CAL[c] || esc(c)).join("")}</span>`; }
        if (cmd === "bar" || cmd === "overline") return `<span class="m-over">${readGroup()}</span>`;
        if (ACC[cmd]) return `<span class="m-acc">${readGroup()}<span class="m-hat">${ACC[cmd]}</span></span>`;
        if (BIG[cmd]) return `<span class="m-big">${BIG[cmd]}</span>`;
        if (OPS.has(cmd)) return `<span class="m-op">${cmd}</span>`;
        if (SYM[cmd]) return `<span class="m-sym">${SYM[cmd]}</span>`;
        return `<span class="m-op">${esc(cmd)}</span>`;
      }
      p++;
      if (/[a-zA-Z]/.test(ch)) return `<var class="m-var">${ch}</var>`;
      if (ch === "-") return `<span class="m-bin">&minus;</span>`;
      if (ch === "+" || ch === "=" || ch === "<" || ch === ">") return `<span class="m-bin">${esc(ch)}</span>`;
      if (ch === "&") return "&ensp;";
      return esc(ch);
    }

    function parseExpr(stopChar = "") {
      let out = "";
      while (p < s.length) {
        skip();
        if (p >= s.length) break;
        if (stopChar && s[p] === stopChar) { p++; break; }
        if (s[p] === "}") { p++; break; }
        const base = parseAtom();
        let sub = "", sup = "";
        while (p < s.length) {
          skip();
          if (s[p] === "_") { p++; sub = readGroup(); }
          else if (s[p] === "^") { p++; sup = readGroup(); }
          else break;
        }
        if (sub && sup) out += `<span class="m-term">${base}<span class="m-scripts"><span class="m-sup">${sup}</span><span class="m-sub">${sub}</span></span></span>`;
        else if (sup) out += `<span class="m-term">${base}<sup class="m-sup-s">${sup}</sup></span>`;
        else if (sub) out += `<span class="m-term">${base}<sub class="m-sub-s">${sub}</sub></span>`;
        else out += base;
      }
      return out;
    }

    return `<span class="math-expr${display ? " math-disp" : ""}">${parseExpr("")}</span>`;
  }

  function cleanText(raw, maxLen = 0, stripTag = true) {
    const rawStr = String(raw ?? ""), hadTag = /^\[[A-Z0-9_ -]+\]\s*/.test(rawStr);
    let s = rawStr.replace(/^#+\s+/gm, "").replace(/\*\*([^*]+)\*\*/g, "$1").replace(/`([^`]+)`/g, "$1").replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
    s = s.replace(/\$\$([\s\S]*?)\$\$|\$([^$\n]+)\$/g, (_, d, il) => (d || il || "")
      .replace(/\\mathbb\{([A-Z1])\}/g, (__, c) => BB[c] || c).replace(/\\mathcal\{([A-Z])\}/g, (__, c) => CAL[c] || c)
      .replace(/\\(?:text|mathrm|mathbf)\{([^}]*)\}/g, "$1").replace(/\\frac\{([^}]*)\}\{([^}]*)\}/g, "($1)/($2)")
      .replace(/\\([a-zA-Z]+)/g, (__, c) => SYM[c] || BIG[c] || c).replace(/[{}]/g, ""));
    if (stripTag) s = s.replace(/^(?:\[[A-Z0-9_ -]+\]\s*)+/, "");
    s = s.replace(/\s+/g, " ").trim();
    const unclosedParen = (s.match(/\(/g) || []).length > (s.match(/\)/g) || []).length;
    if (unclosedParen || (hadTag && s.length >= 68 && !/[.!?)…]$/.test(s))) {
      const sp = s.lastIndexOf(" "); s = (sp > 24 ? s.slice(0, sp) : s).replace(/[,;:\-(]+$/, "") + "…";
    }
    if (maxLen > 0 && s.length > maxLen) {
      const cut = s.slice(0, maxLen - 1), sp = cut.lastIndexOf(" ");
      s = (sp > maxLen * 0.55 ? cut.slice(0, sp) : cut).replace(/[,;:\-(]+$/, "") + "…";
    }
    return s;
  }

  function inlineMd(raw) {
    const toks = [], stash = (html) => `\x00T${toks.push(html) - 1}\x00`;
    let s = String(raw ?? "").replace(/`([^`]+)`/g, (_, c) => stash(`<code class="md-code">${esc(c)}</code>`));
    s = s.replace(/\$\$?\.\.\.\$\$?/g, (m) => stash(`<code class="md-code">${esc(m)}</code>`));
    s = s.replace(/\$(?=\d[\d,.]*(?:[kKmMbB]\b|(?![^$\n]*\$)))(\d[\d,.]*[kKmMbB]?)(?=[),.;:!?]|\s+(?![+\-*/=<>^_\\])|$)/g, (_, amt) => stash(`$${esc(amt)}`));
    s = s.replace(/\\\((.+?)\\\)|\$(?!\s)([^$\n]+?)(?<!\s)\$/g, (_, p1, p2) => stash(`<span class="math-inline">${renderTex(p1 || p2, false)}</span>`));
    s = esc(s);
    s = s.replace(/\[([^\]]+)\]\(((?:https?:\/\/|file:\/\/)[^\s)]+)\)/g, '<a class="file-anchor" href="$2" target="_blank" rel="noreferrer">$1</a>');
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s).,;:!?]|$)/g, "$1<em>$2</em>");
    return s.replace(/\x00T(\d+)\x00/g, (_, idx) => toks[Number(idx)] || "");
  }

  function splitTableRow(row) {
    const cells = []; let cur = "", inCode = false, inMath = false;
    const body = row.trim().replace(/^\||\|$/g, "");
    for (let i = 0; i < body.length; i++) {
      const c = body[i];
      if (c === "`") inCode = !inCode;
      else if (c === "$" && !inCode) inMath = !inMath;
      if (c === "|" && !inCode && !inMath) { cells.push(cur.trim()); cur = ""; } else cur += c;
    }
    cells.push(cur.trim()); return cells;
  }

  function renderMarkdown(raw, stripTopH1 = false) {
    const fences = [], mblocks = [];
    let pre = String(raw ?? "").replace(/\r\n/g, "\n").replace(/```[\s\S]*?```/g, (m) => `\n\x00FC${fences.push(m) - 1}\x00\n`);
    pre = pre.replace(/(?<=^|\n)[ \t]*\$\$(?!\s*\.\.\.\s*\$\$)([\s\S]*?)\$\$[ \t]*(?=\n|$)|\\\[([\s\S]*?)\\\]/g, (_, d1, d2) => `\n\x00MB${mblocks.push(d1 ?? d2) - 1}\x00\n`);
    const lines = pre.split("\n"), out = [];
    let i = 0, skippedH1 = false;
    while (i < lines.length) {
      const t = lines[i].trim();
      if (!t) { i++; continue; }
      if (stripTopH1 && !skippedH1 && /^#\s+/.test(t)) { skippedH1 = true; i++; continue; }
      skippedH1 = true;
      const fc = t.match(/^\x00FC(\d+)\x00$/);
      if (fc) { const body = fences[Number(fc[1])].replace(/^```[^\n]*\n?|\n?```$/g, ""); out.push(`<pre class="code-block"><code>${esc(body)}</code></pre>`); i++; continue; }
      const mb = t.match(/^\x00MB(\d+)\x00$/);
      if (mb) { out.push(`<div class="math-block">${renderTex(mblocks[Number(mb[1])], true)}</div>`); i++; continue; }
      if (/^(?:---|\*\*\*|___)\s*$/.test(t)) { out.push('<hr class="md-hr" />'); i++; continue; }
      const hm = t.match(/^(#{1,4})\s+(.+)$/);
      if (hm) { const tag = hm[1].length <= 2 ? "h4" : "h5"; out.push(`<${tag} class="md-h">${inlineMd(hm[2])}</${tag}>`); i++; continue; }
      if (t.startsWith(">")) {
        const q = []; while (i < lines.length && lines[i].trim().startsWith(">")) q.push(inlineMd(lines[i++].trim().replace(/^>\s?/, "")));
        out.push(`<blockquote class="md-quote">${q.join("<br/>")}</blockquote>`); continue;
      }
      if (t.startsWith("|") && i + 1 < lines.length && /^\|\s*[-:]+/.test(lines[i + 1].trim())) {
        const hdr = splitTableRow(t).map((c) => `<th>${inlineMd(c)}</th>`).join(""); i += 2;
        const rows = []; while (i < lines.length && lines[i].trim().startsWith("|")) rows.push(`<tr>${splitTableRow(lines[i++]).map((c) => `<td>${inlineMd(c)}</td>`).join("")}</tr>`);
        out.push(`<div class="md-table-wrap"><table class="md-table"><thead><tr>${hdr}</tr></thead><tbody>${rows.join("")}</tbody></table></div>`); continue;
      }
      if (/^(?:[-*•]|\d+\.)\s+/.test(t)) {
        const ord = /^\d+\.\s+/.test(t), tag = ord ? "ol" : "ul", items = [], rx = ord ? /^\d+\.\s+(.*)$/ : /^(?:[-*•])\s+(.*)$/;
        while (i < lines.length && rx.test(lines[i].trim())) {
          const body = lines[i++].trim().replace(rx, "$1").replace(/^\[([ xX])\]\s+/, (_, c) => `[${c.trim() ? "x" : " "}] `);
          const subs = []; while (i < lines.length && /^ {2,}(?:[-*•])\s+/.test(lines[i])) subs.push(`<li>${inlineMd(lines[i++].trim().replace(/^(?:[-*•])\s+/, ""))}</li>`);
          items.push(`<li>${inlineMd(body)}${subs.length ? `<ul class="md-list md-sublist">${subs.join("")}</ul>` : ""}</li>`);
        }
        out.push(`<${tag} class="md-list${ord ? " md-ol" : ""}">${items.join("")}</${tag}>`); continue;
      }
      if (/^N\/A$/i.test(t)) { out.push('<p class="md-na">&mdash;</p>'); i++; continue; }
      const p = [];
      while (i < lines.length && lines[i].trim() && !/^(?:\x00(?:FC|MB)\d+\x00|#{1,4}\s|>|\||(?:---|\*\*\*)|(?:[-*•]|\d+\.)\s)/.test(lines[i].trim())) p.push(inlineMd(lines[i++].trim()));
      out.push(`<p class="md-p">${p.join(" ")}</p>`);
    }
    return out.join("") || `<p class="md-na">&mdash;</p>`;
  }

  Object.assign(window.SuperMemoryIcons, { renderTex, cleanText, inlineMd, renderMarkdown });
})();
