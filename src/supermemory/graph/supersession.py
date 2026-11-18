"""Relational Temporal Fact Supersession & Baseline Decay (METH-002)."""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from supermemory.models import (
    DEAD_END_STATUSES,
    EdgeType,
    ExperimentVerdict,
    MemoryEdge,
    MemoryNode,
    NodeType,
)
from supermemory.storage.sqlite_store import GraphStore


def is_negative_warning_node(nd: MemoryNode) -> bool:
    """Never decay mistakes, failed/discarded runs, or rejected dead-ends so anti-repeat stays 100% intact."""
    if nd.node_type == NodeType.LESSON.value:
        return True
    return nd.status.upper() in DEAD_END_STATUSES or bool((nd.metadata or {}).get("is_dead_end_digest"))


def resolve_supersession_maps(
    store: GraphStore,
    nodes: List[MemoryNode],
    edges: List[MemoryEdge],
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Map outdated nodes to newer superseding nodes (`SUPERSEDES`) or SOTA champions (`IMPROVES_OVER`)."""
    superseded_by: Dict[str, str] = {}
    for ed in edges:
        if ed.relation == EdgeType.SUPERSEDES.value and ed.source_id != ed.target_id:
            superseded_by[ed.target_id] = ed.source_id
    for nd in nodes:
        sup = nd.metadata.get("superseded_by")
        if sup and str(sup) != nd.id:
            superseded_by.setdefault(nd.id, str(sup))

    confirmed = {
        e.exp_id
        for e in store.list_experiments()
        if e.verdict in (ExperimentVerdict.VICTORY_CONFIRMED.value, ExperimentVerdict.KEEP.value)
    }
    beaten_by: Dict[str, str] = {}
    for ed in edges:
        if ed.relation == EdgeType.IMPROVES_OVER.value and ed.source_id in confirmed and ed.source_id != ed.target_id:
            beaten_by[ed.target_id] = ed.source_id
    return superseded_by, beaten_by


def apply_supersession_decay(
    nd: MemoryNode,
    score: float,
    superseded_by: Dict[str, str],
    beaten_by: Dict[str, str],
) -> Tuple[float, str]:
    """Damp consolidated/superseded episodes (`0.35x`–`0.42x` floor — never 0.0) while keeping 100% of active dead-end warnings."""
    if nd.node_type == NodeType.LESSON.value:
        return score, ""
    if nd.status == "CONSOLIDATED" or (nd.metadata or {}).get("consolidated"):
        return score * 0.35, str((nd.metadata or {}).get("consolidated_into") or "SEM")
    if is_negative_warning_node(nd):
        return score, ""
    if nd.id in superseded_by or nd.status == "SUPERSEDED":
        return score * 0.42, superseded_by.get(nd.id, "NEWER")
    if nd.status == "ARCHIVED":
        return score * 0.45, ""
    if nd.id in beaten_by:
        return score * 0.72, beaten_by[nd.id]
    return score, ""


def apply_supersedes_links(
    store: GraphStore,
    new_ids: Iterable[str],
    supersedes: Iterable[str],
) -> List[str]:
    """Wire `SUPERSEDES` edges from `new_ids` to `supersedes` and tag superseded positive insights."""
    clean_new = [s.strip() for s in new_ids if s and s.strip()]
    clean_old = [s.strip() for s in supersedes if s and s.strip()]
    if not clean_new or not clean_old:
        return []

    linked: List[str] = []
    lead_new = clean_new[-1]
    for old_id in clean_old:
        if old_id == lead_new:
            continue
        old_nd = store.get_node(old_id)
        if old_nd is None or is_negative_warning_node(old_nd) or old_nd.node_type == NodeType.LAW.value:
            continue
        for new_id in clean_new:
            if new_id != old_id:
                store.add_edge(MemoryEdge(source_id=new_id, target_id=old_id, relation=EdgeType.SUPERSEDES.value))
        old_nd.metadata["superseded_by"] = lead_new
        if old_nd.node_type == NodeType.OBSERVATION.value:
            old_nd.status = "SUPERSEDED"
        store.upsert_node(old_nd, log_event=False)
        store.log_event("NODE_SUPERSEDED", old_id, f"{old_id} superseded by {lead_new}")
        linked.append(old_id)
    return linked
