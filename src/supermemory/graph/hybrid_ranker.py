"""Hybrid Subword N-Gram TF-IDF + Empirical Utility Priors + Personalized PageRank."""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Set, Tuple

from supermemory.graph.supersession import apply_supersession_decay, resolve_supersession_maps
from supermemory.models import ExperimentVerdict, MemoryEdge, MemoryNode, NodeType
from supermemory.storage.sqlite_store import GraphStore

_EDGE_WEIGHT_BOOST: Dict[str, float] = {
    "SUPERSEDES": 1.45,
    "CANDIDATE_FOR": 1.45,
    "DIAGNOSES": 1.40,
    "IMPROVES_OVER": 1.35,
    "DERIVED_FROM": 1.30,
    "TESTS_HYPOTHESIS": 1.25,
    "IMPLEMENTS": 1.25,
    "ENFORCED_BY": 1.25,
    "BLOCKS_RECURRENCE_OF": 1.30,
    "PRODUCED_LESSON": 1.30,
    "REFERENCES": 0.85,
}


def build_sparse_features(text: str) -> Dict[str, float]:
    """Extract normalized word tokens + character 3/4-grams for typo/stem-resilient similarity."""
    clean = re.sub(r"[^0-9a-zA-Z_\u00C0-\u1EF9]+", " ", (text or "").lower()).strip()
    if not clean:
        return {}
    words = [w for w in clean.split() if len(w) >= 2]
    feats: Dict[str, float] = {}
    for w in words[:180]:
        key = f"w:{w}"
        feats[key] = feats.get(key, 0.0) + 1.6
        padded = f"#{w}#"
        if len(padded) >= 4:
            for idx in range(len(padded) - 2):
                g3 = f"c3:{padded[idx:idx + 3]}"
                feats[g3] = feats.get(g3, 0.0) + 0.55
        if len(padded) >= 5:
            for idx in range(len(padded) - 3):
                g4 = f"c4:{padded[idx:idx + 4]}"
                feats[g4] = feats.get(g4, 0.0) + 0.70
    return feats


def compute_hybrid_similarity(
    query: str,
    nodes: List[MemoryNode],
) -> Dict[str, float]:
    """Compute IDF-weighted sparse word + char n-gram cosine similarity across nodes."""
    q_feats = build_sparse_features(query)
    if not q_feats or not nodes:
        return {}

    doc_feats: Dict[str, Dict[str, float]] = {}
    df: Dict[str, int] = {}
    for nd in nodes:
        tags_str = " ".join(nd.tags or [])
        doc_txt = f"{nd.id} {nd.title} {nd.title} {nd.summary} {tags_str} {(nd.content or '')[:600]}"
        fmap = build_sparse_features(doc_txt)
        doc_feats[nd.id] = fmap
        for k in fmap:
            if k in q_feats:
                df[k] = df.get(k, 0) + 1

    n_docs = len(nodes)
    q_vec: Dict[str, float] = {}
    q_norm_sq = 0.0
    for k, tf in q_feats.items():
        idf = math.log(1.0 + (n_docs + 1.0) / (df.get(k, 0) + 1.0))
        val = (1.0 + math.log(tf)) * idf
        q_vec[k] = val
        q_norm_sq += val * val
    q_norm = math.sqrt(q_norm_sq) or 1.0

    scores: Dict[str, float] = {}
    for nd in nodes:
        fmap = doc_feats.get(nd.id) or {}
        if not fmap:
            continue
        dot = 0.0
        d_norm_sq = 0.0
        for k, tf in fmap.items():
            idf = math.log(1.0 + (n_docs + 1.0) / (df.get(k, 0) + 1.0))
            d_val = (1.0 + math.log(tf)) * idf
            d_norm_sq += d_val * d_val
            if k in q_vec:
                dot += q_vec[k] * d_val
        if dot > 0.0 and d_norm_sq > 0.0:
            scores[nd.id] = dot / (q_norm * math.sqrt(d_norm_sq))
    return scores


def compute_utility_priors(store: GraphStore, nodes: List[MemoryNode], edges: List[MemoryEdge]) -> Dict[str, float]:
    """Compute ACT-R empirical utility boost from verified metric deltas and Pareto bottlenecks."""
    priors: Dict[str, float] = {}
    exp_boost: Dict[str, float] = {}
    for exp in store.list_experiments():
        if exp.verdict in (ExperimentVerdict.VICTORY_CONFIRMED.value, ExperimentVerdict.KEEP.value):
            delta = abs(float(exp.delta_vs_baseline or 0.0))
            boost = min(0.45, 0.16 + delta * 1.8)
            exp_boost[exp.exp_id] = boost
            priors[exp.exp_id] = max(priors.get(exp.exp_id, 0.0), boost)

    for ed in edges:
        if ed.source_id in exp_boost:
            priors[ed.target_id] = max(priors.get(ed.target_id, 0.0), exp_boost[ed.source_id] * 0.75)
        if ed.target_id in exp_boost:
            priors[ed.source_id] = max(priors.get(ed.source_id, 0.0), exp_boost[ed.target_id] * 0.75)

    for nd in nodes:
        base = priors.get(nd.id, 0.0)
        if nd.node_type == NodeType.BOTTLENECK.value and nd.status not in ("RESOLVED", "ARCHIVED"):
            share = float(nd.metadata.get("error_share_pct") or 0.0) / 100.0
            ceil_gain = float(nd.metadata.get("ceiling_gain") or 0.1)
            base += min(0.40, 0.14 + share * max(0.05, ceil_gain) * 2.5)
        elif nd.node_type == NodeType.METHOD_CARD.value:
            base += 0.12
        elif nd.node_type in (NodeType.LAW.value, NodeType.GATE.value):
            base += 0.10
        if nd.status == "CONSOLIDATED":
            base -= 0.25
        priors[nd.id] = base
    return priors


def personalized_pagerank(
    seed_scores: Dict[str, float],
    edges: List[MemoryEdge],
    alpha: float = 0.28,
    iterations: int = 8,
) -> Dict[str, float]:
    """Run weighted Personalized PageRank spreading activation from lexical+BM25 seeds."""
    pos_seeds = {k: v for k, v in seed_scores.items() if v > 0.0}
    total_seed = sum(pos_seeds.values())
    if total_seed <= 0.0:
        return {}
    teleport = {k: v / total_seed for k, v in pos_seeds.items()}

    adj: Dict[str, List[Tuple[str, float]]] = {}
    for ed in edges:
        rel_w = _EDGE_WEIGHT_BOOST.get(ed.relation, 1.0) * max(0.2, float(ed.weight or 1.0))
        if ed.relation == "SUPERSEDES":
            # Flow activation strongly from superseded old node -> superseding new node
            adj.setdefault(ed.target_id, []).append((ed.source_id, rel_w * 1.60))
            adj.setdefault(ed.source_id, []).append((ed.target_id, rel_w * 0.25))
        else:
            adj.setdefault(ed.source_id, []).append((ed.target_id, rel_w))
            adj.setdefault(ed.target_id, []).append((ed.source_id, rel_w * 0.85))

    ranks = dict(teleport)
    for _ in range(iterations):
        nxt: Dict[str, float] = {k: alpha * t_val for k, t_val in teleport.items()}
        for nid, r_val in ranks.items():
            nbrs = adj.get(nid)
            if not nbrs:
                nxt[nid] = nxt.get(nid, 0.0) + (1.0 - alpha) * r_val
                continue
            w_sum = sum(w for _, w in nbrs) or 1.0
            for target_id, w in nbrs:
                nxt[target_id] = nxt.get(target_id, 0.0) + (1.0 - alpha) * r_val * (w / w_sum)
        ranks = nxt
    return ranks


def rank_hybrid_graph(
    store: GraphStore,
    query: str,
    fts_hits: List[Tuple[MemoryNode, float]],
    limit: int = 10,
    hops: int = 1,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Fuse FTS5 BM25, char/word TF-IDF cosine, empirical utility, and Personalized PageRank."""
    nodes = store.list_nodes(limit=3000)
    if not nodes:
        return [], []
    by_id = {n.id: n for n in nodes}
    edges = store.list_edges()

    fts_map: Dict[str, float] = {}
    max_fts = max((sc for _, sc in fts_hits), default=1.0) or 1.0
    for nd, sc in fts_hits:
        fts_map[nd.id] = max(0.05, sc / max_fts)

    sim_map = compute_hybrid_similarity(query, nodes)
    priors = compute_utility_priors(store, nodes, edges)
    superseded_by, beaten_by = resolve_supersession_maps(store, nodes, edges)

    seed_scores: Dict[str, float] = {}
    direct_ids: Set[str] = set()
    for nid, nd in by_id.items():
        bm25_norm = fts_map.get(nid, 0.0)
        dense_sim = sim_map.get(nid, 0.0)
        if bm25_norm > 0.0 or dense_sim >= 0.11:
            direct_ids.add(nid)
            raw = 0.52 * bm25_norm + 0.48 * dense_sim
            seed_scores[nid] = max(0.01, raw * (1.0 + priors.get(nid, 0.0)))

    if not seed_scores:
        return [], []

    ppr = personalized_pagerank(seed_scores, edges) if hops >= 1 else {}
    max_ppr = max(ppr.values(), default=1.0) or 1.0

    # Restrict multi-hop expansion to nodes reachable within `hops` of top direct hits
    top_direct = sorted(direct_ids, key=lambda x: seed_scores.get(x, 0.0), reverse=True)[: max(6, limit)]
    hop_dist: Dict[str, int] = {nid: 0 for nid in top_direct}
    via_rel: Dict[str, str] = {}
    frontier: Set[str] = set(top_direct)
    traversed_edges: List[Dict[str, Any]] = []

    for h in range(1, max(0, hops) + 1):
        nxt_f: Set[str] = set()
        for ed in edges:
            if ed.source_id in frontier or ed.target_id in frontier:
                traversed_edges.append(ed.to_dict())
                other = ed.target_id if ed.source_id in frontier else ed.source_id
                if other not in hop_dist and other in by_id:
                    hop_dist[other] = h
                    via_rel[other] = ed.relation
                    nxt_f.add(other)
        frontier = nxt_f

    candidate_ids = direct_ids | set(hop_dist.keys())
    scored_items: List[Dict[str, Any]] = []
    for nid in candidate_ids:
        nd = by_id[nid]
        direct_sc = seed_scores.get(nid, 0.0)
        ppr_sc = (ppr.get(nid, 0.0) / max_ppr) if ppr else 0.0
        util_sc = priors.get(nid, 0.0)
        hop = 0 if nid in direct_ids else hop_dist.get(nid, 1)
        final_sc = (0.62 * direct_sc + 0.28 * ppr_sc + 0.10 * max(0.0, util_sc)) / (1.0 + 0.22 * hop)
        final_sc, sup_target = apply_supersession_decay(nd, final_sc, superseded_by, beaten_by)
        item: Dict[str, Any] = {
            "id": nd.id,
            "type": nd.node_type,
            "title": nd.title,
            "status": nd.status,
            "score": round(final_sc, 4),
            "utility_prior": round(util_sc, 3),
            "summary": nd.summary or nd.content[:200],
            "file_path": nd.file_path,
            "hop": hop,
        }
        if sup_target:
            item["superseded_by"] = sup_target
        if hop > 0 and nid in via_rel:
            item["via_relation"] = via_rel[nid]
        scored_items.append(item)

    scored_items.sort(key=lambda x: (x["hop"] == 0, float(x["score"])), reverse=True)
    return scored_items[: limit + 8], traversed_edges[:30]
