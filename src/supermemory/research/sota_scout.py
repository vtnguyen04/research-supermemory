"""Zero-Dependency SOTA Literature & Method Scout (arXiv + Semantic Scholar + OpenAlex)."""

from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Sequence

from supermemory.cognitive.novelty_guard import extract_mechanism_signature
from supermemory.graph.hybrid_ranker import build_sparse_features
from supermemory.models import EdgeType, MemoryEdge, MemoryNode, NodeType, utc_now_iso
from supermemory.storage.sqlite_store import GraphStore

_ARXIV_NS = {"atom": "http://www.w3.org/2005/Atom"}
_USER_AGENT = "ResearchSuperMemory/3.0 (mailto:research@supermemory.local)"


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:44] or "method"


def _next_method_id(store: GraphStore) -> str:
    nodes = store.list_nodes(node_types=[NodeType.METHOD_CARD.value], limit=5000)
    nums = [int(m.group(1)) for nd in nodes for m in [re.match(r"^METH-(\d+)$", nd.id)] if m]
    return f"METH-{(max(nums) + 1) if nums else 1:03d}"


def _cache_get(store: GraphStore, cache_key: str) -> Optional[List[Dict[str, Any]]]:
    row = store.conn.execute("SELECT response_json FROM http_cache WHERE cache_key = ?", (cache_key,)).fetchone()
    if not row:
        return None
    try:
        data = json.loads(str(row["response_json"]))
        return data if isinstance(data, list) else None
    except ValueError:
        return None


def _cache_put(store: GraphStore, cache_key: str, source: str, query: str, items: List[Dict[str, Any]]) -> None:
    store.conn.execute(
        "INSERT INTO http_cache(cache_key, source, query, response_json, created_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(cache_key) DO UPDATE SET response_json=excluded.response_json, created_at=excluded.created_at",
        (cache_key, source, query, json.dumps(items, ensure_ascii=False), utc_now_iso()),
    )
    store.conn.commit()


def _http_get(url: str, timeout_sec: float) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:  # noqa: S310
        raw: bytes = resp.read()
        return raw.decode("utf-8", errors="replace")


def _fetch_arxiv(query: str, limit: int, timeout_sec: float) -> List[Dict[str, Any]]:
    enc = urllib.parse.quote_plus(query)
    url = f"http://export.arxiv.org/api/query?search_query=all:{enc}&start=0&max_results={limit}&sortBy=relevance"
    root = ET.fromstring(_http_get(url, timeout_sec))  # noqa: S314
    out: List[Dict[str, Any]] = []
    for entry in root.findall("atom:entry", _ARXIV_NS):
        title = " ".join((entry.findtext("atom:title", default="", namespaces=_ARXIV_NS) or "").split())
        summary = " ".join((entry.findtext("atom:summary", default="", namespaces=_ARXIV_NS) or "").split())
        pub = entry.findtext("atom:published", default="", namespaces=_ARXIV_NS) or ""
        year = int(pub[:4]) if len(pub) >= 4 and pub[:4].isdigit() else 2024
        link = entry.findtext("atom:id", default="", namespaces=_ARXIV_NS) or ""
        authors = [(a.findtext("atom:name", default="", namespaces=_ARXIV_NS) or "").strip() for a in entry.findall("atom:author", _ARXIV_NS)]
        if title:
            out.append({"title": title, "abstract": summary[:900], "year": year, "venue": "arXiv", "citations": 0, "url": link, "authors": [x for x in authors if x][:4], "source": "arxiv"})
    return out


def _fetch_semantic_scholar(query: str, limit: int, timeout_sec: float) -> List[Dict[str, Any]]:
    enc = urllib.parse.quote_plus(query)
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={enc}&limit={limit}&fields=title,abstract,year,venue,citationCount,url,authors"
    payload = json.loads(_http_get(url, timeout_sec))
    out: List[Dict[str, Any]] = []
    for item in payload.get("data") or []:
        title = str(item.get("title") or "").strip()
        if title:
            authors = [str(a.get("name") or "") for a in (item.get("authors") or [])[:4] if a.get("name")]
            out.append({"title": title, "abstract": str(item.get("abstract") or "")[:900], "year": int(item.get("year") or 2024), "venue": str(item.get("venue") or "SemanticScholar"), "citations": int(item.get("citationCount") or 0), "url": str(item.get("url") or ""), "authors": authors, "source": "semantic_scholar"})
    return out


def _fetch_openalex(query: str, limit: int, timeout_sec: float) -> List[Dict[str, Any]]:
    enc = urllib.parse.quote_plus(query)
    payload = json.loads(_http_get(f"https://api.openalex.org/works?search={enc}&per-page={limit}", timeout_sec))
    out: List[Dict[str, Any]] = []
    for item in payload.get("results") or []:
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        inv = item.get("abstract_inverted_index") or {}
        pos_words = sorted((int(pos), str(word)) for word, positions in inv.items() for pos in (positions or []))
        loc = (item.get("primary_location") or {}).get("source") or {}
        out.append({"title": title, "abstract": " ".join(w for _, w in pos_words)[:900], "year": int(item.get("publication_year") or 2024), "venue": str(loc.get("display_name") or "OpenAlex"), "citations": int(item.get("cited_by_count") or 0), "url": str(item.get("doi") or item.get("id") or ""), "authors": [], "source": "openalex"})
    return out


def _rank_papers(query: str, papers: List[Dict[str, Any]], min_year: int) -> List[Dict[str, Any]]:
    q_feats = build_sparse_features(query)
    seen_titles: set[str] = set()
    ranked: List[Dict[str, Any]] = []
    for p in papers:
        yr = int(p.get("year") or 0)
        norm_t = re.sub(r"[^a-z0-9]+", "", str(p.get("title") or "").lower())
        if (yr and yr < min_year) or not norm_t or norm_t in seen_titles:
            continue
        seen_titles.add(norm_t)
        p_feats = build_sparse_features(f"{p.get('title', '')} {p.get('abstract', '')}")
        overlap = sum(min(q_feats[k], p_feats.get(k, 0.0)) for k in q_feats) / max(1.0, sum(q_feats.values()))
        score = round(overlap + 0.10 * math.log1p(max(0, int(p.get("citations") or 0))) + max(0.0, (yr - min_year) * 0.03), 4)
        ranked.append({**p, "relevance_score": score})
    ranked.sort(key=lambda x: float(x.get("relevance_score") or 0.0), reverse=True)
    return ranked


def register_method_card(
    store: GraphStore,
    title: str,
    bottleneck_addressed: str,
    core_mechanism: str,
    assumptions_and_limits: str = "Requires empirical validation on target benchmark slice.",
    complexity_cost: str = "O(N)",
    minimal_integration_hook: str = "",
    source_url: str = "",
    venue: str = "",
    year: int = 2025,
    bottleneck_id: str = "",
) -> Dict[str, Any]:
    """Save a structured SOTA METHOD_CARD into memory/07_METHOD_VAULT and link to Bottleneck."""
    mid = _next_method_id(store)
    vault_dir = store.mem_dir / "07_METHOD_VAULT"
    vault_dir.mkdir(parents=True, exist_ok=True)
    rel_path = f"memory/07_METHOD_VAULT/{mid}_{_slugify(title)}.md"
    sig = extract_mechanism_signature(f"{title} {core_mechanism} {minimal_integration_hook}", bottleneck_id)
    hook_txt = minimal_integration_hook or "Isolate as single-variable plug-in module."
    md = (
        f"# {mid}: {title}\n\n"
        f"- **Source / Venue:** `{venue or 'Literature'}` (`{year}`) {source_url}\n"
        f"- **Target Bottleneck:** `{bottleneck_id or 'GENERAL'}` — {bottleneck_addressed}\n"
        f"- **Complexity Cost:** `{complexity_cost}`\n\n"
        f"## 1. Core Mathematical / Algorithmic Mechanism\n\n{core_mechanism}\n\n"
        f"## 2. Assumptions & Failure Limits\n\n{assumptions_and_limits}\n\n"
        f"## 3. Minimal Integration Hook (< 100 LOC)\n\n{hook_txt}\n"
    )
    (store.workspace_root / rel_path).write_text(md, encoding="utf-8")
    node = store.upsert_node(
        MemoryNode(
            id=mid,
            node_type=NodeType.METHOD_CARD.value,
            title=title,
            status="ACTIVE",
            summary=f"[{venue or 'SOTA'} {year}] {core_mechanism[:195]}",
            content=md,
            file_path=rel_path,
            tags=["method_card", *(sig.get("families") or [])],
            priority=84,
            metadata={
                "bottleneck_id": bottleneck_id,
                "bottleneck_addressed": bottleneck_addressed,
                "core_mechanism": core_mechanism,
                "assumptions_and_limits": assumptions_and_limits,
                "complexity_cost": complexity_cost,
                "minimal_integration_hook": hook_txt,
                "source_url": source_url,
                "venue": venue,
                "year": year,
                "mechanism_fingerprint": sig,
            },
        )
    )
    if bottleneck_id and store.get_node(bottleneck_id):
        store.add_edge(MemoryEdge(source_id=mid, target_id=bottleneck_id, relation=EdgeType.CANDIDATE_FOR.value))
    return node.to_dict()


def scout_sota_papers(
    store: GraphStore,
    query: str,
    limit: int = 6,
    min_year: int = 2022,
    sources: Sequence[str] = ("arxiv", "semantic_scholar", "openalex"),
    bottleneck_id: str = "",
    save_top_k: int = 0,
    timeout_sec: float = 6.0,
    offline_fixtures: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Search arXiv/S2/OpenAlex with SQLite HTTP caching and optionally mint METHOD_CARDs."""
    clean_q = query.strip()
    if not clean_q:
        raise ValueError("SOTA scout query cannot be empty.")

    raw_papers: List[Dict[str, Any]] = []
    errors: List[str] = []
    cache_hits = 0
    if offline_fixtures is not None:
        raw_papers.extend(offline_fixtures)
    else:
        fetchers = {"arxiv": _fetch_arxiv, "semantic_scholar": _fetch_semantic_scholar, "openalex": _fetch_openalex}
        for src in sources:
            fn = fetchers.get(src)
            if not fn:
                continue
            ckey = hashlib.sha256(f"{src}:{clean_q.lower()}:{limit}".encode("utf-8")).hexdigest()[:24]
            cached = _cache_get(store, ckey)
            if cached is not None:
                cache_hits += 1
                raw_papers.extend(cached)
                continue
            try:
                fetched = fn(clean_q, limit, timeout_sec)
                _cache_put(store, ckey, src, clean_q, fetched)
                raw_papers.extend(fetched)
            except (urllib.error.URLError, TimeoutError, ET.ParseError, ValueError, OSError) as exc:
                errors.append(f"{src}: {type(exc).__name__}")

    ranked = _rank_papers(clean_q, raw_papers, min_year=min_year)[:limit]
    saved_cards: List[Dict[str, Any]] = []
    if save_top_k > 0:
        bnk_node = store.get_node(bottleneck_id) if bottleneck_id else None
        bnk_desc = bnk_node.title if bnk_node else clean_q
        for paper in ranked[:save_top_k]:
            saved_cards.append(
                register_method_card(
                    store,
                    title=str(paper["title"]),
                    bottleneck_addressed=bnk_desc,
                    core_mechanism=str(paper.get("abstract") or paper["title"])[:420],
                    source_url=str(paper.get("url") or ""),
                    venue=str(paper.get("venue") or paper.get("source") or "SOTA"),
                    year=int(paper.get("year") or 2025),
                    bottleneck_id=bottleneck_id,
                )
            )
    store.log_event("SOTA_SCOUT", bottleneck_id or "VAULT", f"Scouted '{clean_q}': {len(ranked)} papers, {len(saved_cards)} saved")
    return {"query": clean_q, "cache_hits": cache_hits, "papers": ranked, "saved_method_cards": saved_cards, "network_warnings": errors}
