"""Zero-Orphan Contextual Auto-Linker & Near-Duplicate Observation Supersession."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Set

from supermemory.graph.hybrid_ranker import compute_hybrid_similarity
from supermemory.models import EdgeType, MemoryEdge, MemoryNode, NodeType
from supermemory.storage.sqlite_store import GraphStore

_NODE_ID_TOKEN_RE = re.compile(
    r"\b(?:BNK|RQ|METH|EXP|PROP|IDEA|ALGO|LESSON|LAW|SEM|PROC)-[A-Z0-9-]*\d+[A-Z0-9-]*\b",
    re.IGNORECASE,
)
_CONTENT_WORD_RE = re.compile(r"[0-9a-zA-Z_\u00C0-\u1EF9]{4,}")
_ANCHOR_TYPES = [
    NodeType.BOTTLENECK.value,
    NodeType.PROPOSAL.value,
    NodeType.METHOD_CARD.value,
    NodeType.ALGORITHM.value,
    NodeType.LAW.value,
]


def _content_words(text: str) -> Set[str]:
    return {w.lower() for w in _CONTENT_WORD_RE.findall(text or "")}


def extract_explicit_node_ids(store: GraphStore, text: str, exclude_id: str = "") -> List[str]:
    """Extract existing graph node IDs referenced inside free-form insight/proposal text."""
    seen: Set[str] = set()
    found: List[str] = []
    for raw in _NODE_ID_TOKEN_RE.findall(text or ""):
        cand = raw.upper().rstrip("-")
        if cand == exclude_id or cand in seen:
            continue
        if store.get_node(cand) is not None:
            seen.add(cand)
            found.append(cand)
    return found


def find_near_duplicate_insights(
    store: GraphStore,
    title: str,
    summary: str,
    exclude_id: str = "",
    threshold: float = 0.58,
) -> List[str]:
    """Return read-only candidate `OBS-*` IDs with high lexical overlap for agent/`memory-curator` review (never auto-merged)."""
    query_txt = f"{title} {summary}".strip()
    q_words = _content_words(query_txt)
    if len(q_words) < 2:
        return []
    candidates = [
        n
        for n in store.list_nodes(node_types=[NodeType.OBSERVATION.value], limit=600)
        if n.id != exclude_id
        and n.status == "SCIENTIFIC_INSIGHT"
        and not (n.metadata or {}).get("consolidated")
        and not (n.metadata or {}).get("superseded_by")
    ]
    if not candidates:
        return []
    sim_map = compute_hybrid_similarity(query_txt, candidates)
    by_id = {c.id: c for c in candidates}
    dups: List[str] = []
    for cid, sc in sorted(sim_map.items(), key=lambda kv: kv[1], reverse=True):
        cand = by_id[cid]
        shared = q_words & _content_words(f"{cand.title} {cand.summary}")
        if sc >= threshold and len(shared) >= 3:
            dups.append(cid)
        if len(dups) >= 3:
            break
    return dups


def _wire_typed_pair(store: GraphStore, src: MemoryNode, dst: MemoryNode) -> None:
    s_type = src.node_type
    d_type = dst.node_type
    if s_type in (NodeType.IDEA.value, NodeType.ALGORITHM.value, NodeType.PROPOSAL.value) and d_type == NodeType.BOTTLENECK.value:
        store.add_edge(MemoryEdge(source_id=src.id, target_id=dst.id, relation=EdgeType.CANDIDATE_FOR.value))
    elif s_type == NodeType.PROPOSAL.value and d_type in (NodeType.IDEA.value, NodeType.ALGORITHM.value):
        store.add_edge(MemoryEdge(source_id=dst.id, target_id=src.id, relation=EdgeType.PROMOTED_TO.value))
    elif s_type in (NodeType.IDEA.value, NodeType.ALGORITHM.value) and d_type == NodeType.METHOD_CARD.value:
        store.add_edge(MemoryEdge(source_id=dst.id, target_id=src.id, relation=EdgeType.INSPIRED.value))
    elif s_type == NodeType.OBSERVATION.value and d_type in (
        NodeType.EXPERIMENT.value,
        NodeType.PROPOSAL.value,
        NodeType.BOTTLENECK.value,
        NodeType.ALGORITHM.value,
        NodeType.METHOD_CARD.value,
    ):
        store.add_edge(MemoryEdge(source_id=src.id, target_id=dst.id, relation=EdgeType.DERIVED_FROM.value))
    else:
        store.add_edge(MemoryEdge(source_id=src.id, target_id=dst.id, relation=EdgeType.REFERENCES.value))


def _has_any_edge(store: GraphStore, node_id: str) -> bool:
    row = store.conn.execute(
        "SELECT 1 FROM edges WHERE source_id = ? OR target_id = ? LIMIT 1",
        (node_id, node_id),
    ).fetchone()
    return row is not None


def _pick_fallback_anchor(store: GraphStore, node: MemoryNode, text: str) -> Optional[MemoryNode]:
    anchors = [
        a
        for a in store.list_nodes(node_types=_ANCHOR_TYPES, limit=400)
        if a.id != node.id and a.status not in ("CONSOLIDATED", "SUPERSEDED")
    ]
    if not anchors:
        return None
    sim = compute_hybrid_similarity(text or f"{node.title} {node.summary}", anchors)
    if sim:
        best_id, best_sc = max(sim.items(), key=lambda kv: kv[1])
        if best_sc >= 0.22:
            return store.get_node(best_id)

    active_props = [
        a for a in anchors if a.node_type == NodeType.PROPOSAL.value and a.status in ("IMPLEMENTING", "DESIGNED", "PROPOSED")
    ]
    if active_props:
        active_props.sort(key=lambda p: p.id, reverse=True)
        return active_props[0]
    open_bnks = [a for a in anchors if a.node_type == NodeType.BOTTLENECK.value and a.status == "OPEN"]
    if open_bnks:
        open_bnks.sort(
            key=lambda b: float((b.metadata or {}).get("error_share_pct") or 0.0)
            * float((b.metadata or {}).get("ceiling_gain") or 0.1),
            reverse=True,
        )
        return open_bnks[0]
    return anchors[0]


def wire_contextual_edges(
    store: GraphStore,
    node_id: str,
    text: str = "",
    context_ids: Optional[Iterable[str]] = None,
    allow_fallback: bool = True,
) -> List[str]:
    """Ensure `node_id` is connected to explicit ID mentions or the active campaign anchor (`0` orphans)."""
    node = store.get_node(node_id)
    if node is None:
        return []
    full_txt = text or f"{node.title} {node.summary} {node.content}"
    targets: List[str] = []
    for cid in context_ids or []:
        clean_c = str(cid or "").strip().upper()
        if clean_c and clean_c != node_id and clean_c not in targets and store.get_node(clean_c) is not None:
            targets.append(clean_c)
    for eid in extract_explicit_node_ids(store, full_txt, exclude_id=node_id):
        if eid not in targets:
            targets.append(eid)

    linked: List[str] = []
    for tid in targets[:5]:
        dst = store.get_node(tid)
        if dst is not None:
            _wire_typed_pair(store, node, dst)
            linked.append(tid)

    if not linked and allow_fallback and not _has_any_edge(store, node_id):
        fb = _pick_fallback_anchor(store, node, full_txt)
        if fb is not None:
            store.add_edge(MemoryEdge(source_id=node.id, target_id=fb.id, relation=EdgeType.REFERENCES.value))
            linked.append(fb.id)
    return linked


def repair_orphan_nodes(store: GraphStore, allow_fallback: bool = True) -> Dict[str, Any]:
    """Backfill contextual edges for existing degree-0 `OBS`, `ALGO`, `IDEA`, `PROP`, and `PROC` nodes."""
    target_types = {
        NodeType.OBSERVATION.value,
        NodeType.ALGORITHM.value,
        NodeType.IDEA.value,
        NodeType.PROPOSAL.value,
        NodeType.PROCEDURE.value,
        NodeType.KNOWLEDGE_NODE.value,
    }
    repaired: List[str] = []
    for nd in store.list_nodes(limit=5000):
        if nd.node_type in target_types and not _has_any_edge(store, nd.id):
            wired = wire_contextual_edges(store, nd.id, allow_fallback=allow_fallback)
            if wired:
                repaired.append(nd.id)
    return {"repaired_count": len(repaired), "repaired_ids": repaired}
