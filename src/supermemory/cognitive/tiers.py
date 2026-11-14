"""4-Tier Cognitive Memory Hierarchy (Working, Procedural, Semantic, Episodic) & Consolidation."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from supermemory.models import EdgeType, MemoryEdge, MemoryNode, MemoryTier, NodeType, utc_now_iso
from supermemory.storage.sqlite_store import GraphStore

_PROCEDURAL_TYPES = {
    NodeType.LAW.value,
    NodeType.PROCEDURE.value,
    NodeType.GATE.value,
    NodeType.ALGORITHM.value,
}
_SEMANTIC_TYPES = {
    NodeType.KNOWLEDGE_NODE.value,
    NodeType.OBSERVATION.value,
    NodeType.IDEA.value,
    NodeType.DECISION.value,
}


def classify_tier(node: MemoryNode | Dict[str, Any]) -> str:
    """Map any graph node into WORKING, PROCEDURAL, SEMANTIC, or EPISODIC tier."""
    meta = node.metadata if isinstance(node, MemoryNode) else (node.get("metadata") or {})
    ntype = node.node_type if isinstance(node, MemoryNode) else str(node.get("node_type") or "")
    explicit = str(meta.get("memory_tier") or "").upper()
    if explicit in {t.value for t in MemoryTier}:
        return explicit
    if ntype in _PROCEDURAL_TYPES:
        return MemoryTier.PROCEDURAL.value
    if ntype in _SEMANTIC_TYPES:
        return MemoryTier.SEMANTIC.value
    return MemoryTier.EPISODIC.value


def _est_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)


def compute_tier_telemetry(store: GraphStore) -> Dict[str, Any]:
    """Compute per-tier node counts, consolidated counts, and context token savings."""
    nodes = store.list_nodes(limit=10000)
    counts = {t.value: 0 for t in MemoryTier}
    raw_tokens_by_tier = {t.value: 0 for t in MemoryTier}
    consolidated_count = 0

    for n in nodes:
        tier = classify_tier(n)
        counts[tier] = counts.get(tier, 0) + 1
        raw_tokens_by_tier[tier] += _est_tokens(f"{n.title} {n.summary} {n.content}")
        if n.status == "CONSOLIDATED":
            consolidated_count += 1

    capsule = build_tiered_capsule(store)
    active_prompt_tokens = _est_tokens(capsule)
    total_vault_tokens = sum(raw_tokens_by_tier.values())
    saved_pct = (
        round((1.0 - min(1.0, active_prompt_tokens / max(1, total_vault_tokens))) * 100.0, 1)
        if total_vault_tokens > active_prompt_tokens
        else 0.0
    )
    return {
        "counts_by_tier": counts,
        "raw_tokens_by_tier": raw_tokens_by_tier,
        "active_prompt_tokens": active_prompt_tokens,
        "total_vault_tokens": total_vault_tokens,
        "context_compression_pct": saved_pct,
        "consolidated_episodes": consolidated_count,
    }


def build_tiered_capsule(store: GraphStore, query: str = "", global_rules: List[str] | None = None) -> str:
    """Compile strictly token-budgeted L0 Working + L1 Procedural + L2 Semantic capsule (<850 tokens)."""
    meta = store.get_all_meta()
    proj = meta.get("project_name") or store.workspace_root.name
    goal = (meta.get("active_goal") or "Maintain 100% constitutional compliance.")[:180]
    next_act = (meta.get("next_actions") or "Check recall before editing; commit memory before stopping.")[:180]

    laws = sorted(store.list_nodes(node_types=[NodeType.LAW.value], limit=12), key=lambda x: x.id)
    procs = store.list_nodes(node_types=[NodeType.PROCEDURE.value], limit=6)
    gates = store.list_gates(enabled_only=True)
    proposals = [
        p for p in store.list_nodes(node_types=[NodeType.PROPOSAL.value], limit=6)
        if p.status not in ("ARCHIVED", "REJECTED", "CONSOLIDATED")
    ]
    exps = [e for e in store.list_experiments()[-2:]]

    lines: List[str] = [
        f"🧠 SUPERMEMORY CONSTITUTIONAL HARNESS ACTIVE — Project: `{proj}`",
        f"• [L0 WORKING] Goal: {goal}",
        f"• [L0 WORKING] Next: {next_act}",
    ]
    if proposals:
        lines.append("• [L0 WORKING] Active Proposals: " + " | ".join(f"`{p.id}`[{p.status}] {p.title[:45]}" for p in proposals[:3]))

    lines.append(f"• [L1 PROCEDURAL] {len(laws)} Laws | {len(procs)} Procedures | {len(gates)} PreToolUse Gates:")
    for lw in laws[:10]:
        lines.append(f"  - `{lw.id}`: {lw.title[:78]}")
    for pr in procs[:4]:
        lines.append(f"  - `{pr.id}` (Procedure): {pr.title[:78]}")
    for gr in (global_rules or [])[:4]:
        lines.append(f"  - [GLOBAL] {gr[:85]}")

    if query.strip():
        hits = store.search_fts(query, limit=6)
        sem_lines = []
        for nd, _ in hits:
            if nd.status == "CONSOLIDATED":
                continue
            tier = classify_tier(nd)
            if tier == MemoryTier.SEMANTIC.value or nd.status in ("REJECTED", "REVERT", "FAILED", "FAILURE_INSIGHT"):
                sem_lines.append(f"  - [{tier}/{nd.node_type}] `{nd.id}`: {nd.title[:55]} — {nd.summary[:95]}")
        if sem_lines:
            lines.append("• [L2 SEMANTIC RECALL — Progressive Disclosure]:")
            lines.extend(sem_lines[:4])

    if exps:
        lines.append(
            "• [L3 EPISODIC POINTERS — Paged on Disk]: "
            + " | ".join(f"`{x.exp_id}`({x.verdict}: {x.test_summary[:28] or x.cv_summary[:28]})" for x in exps)
        )
    return "\n".join(lines)


def _next_tier_id(store: GraphStore, prefix: str, ntype: str) -> str:
    existing = store.list_nodes(node_types=[ntype], limit=5000)
    nums = [int(m.group(1)) for n in existing for m in [re.match(rf"^{re.escape(prefix)}-(\d+)$", n.id)] if m]
    return f"{prefix}-{(max(nums) + 1) if nums else 1:03d}"


def consolidate_nodes(
    store: GraphStore,
    source_ids: List[str],
    target_tier: str,
    title: str,
    summary: str,
    content: str = "",
) -> Dict[str, Any]:
    """Distill multiple Episodic/Semantic nodes into 1 Semantic Knowledge or Procedural node."""
    clean_ids = [s.strip() for s in source_ids if s and s.strip()]
    if not clean_ids:
        raise ValueError("Provide at least one source node ID to consolidate.")
    sources = [n for nid in clean_ids for n in [store.get_node(nid)] if n is not None]
    if not sources:
        raise ValueError(f"None of the source IDs exist: {clean_ids}")

    tier_up = target_tier.strip().upper()
    if tier_up == MemoryTier.PROCEDURAL.value:
        ntype = NodeType.PROCEDURE.value
        new_id = _next_tier_id(store, "PROC", ntype)
    else:
        tier_up = MemoryTier.SEMANTIC.value
        ntype = NodeType.KNOWLEDGE_NODE.value
        new_id = _next_tier_id(store, "SEM", ntype)

    merged_trace = "\n".join(f"- **`{s.id}`** (`{s.node_type}`): {s.title} — {s.summary[:140]}" for s in sources)
    full_md = (
        f"# {new_id} [{tier_up}]: {title}\n\n"
        f"- **Consolidated At:** `{utc_now_iso()}`\n"
        f"- **Distilled Summary:** {summary}\n\n"
        f"## Synthesized Principle / Knowledge\n\n{content or summary}\n\n"
        f"## Consolidated Source Lineage ({len(sources)} nodes)\n\n{merged_trace}\n"
    )
    kn_dir = store.mem_dir / "06_KNOWLEDGE_NODES"
    kn_dir.mkdir(parents=True, exist_ok=True)
    rel_path = f"memory/06_KNOWLEDGE_NODES/{new_id}.md"
    (store.workspace_root / rel_path).write_text(full_md, encoding="utf-8")

    distilled = store.upsert_node(
        MemoryNode(
            id=new_id,
            node_type=ntype,
            title=title,
            status="ACTIVE",
            summary=summary[:240],
            content=full_md,
            file_path=rel_path,
            tags=["consolidated", tier_up.lower(), ntype.lower()],
            priority=92 if tier_up == MemoryTier.PROCEDURAL.value else 89,
            metadata={"memory_tier": tier_up, "source_ids": [s.id for s in sources]},
        )
    )
    archived_ids: List[str] = []
    for src in sources:
        store.add_edge(MemoryEdge(source_id=src.id, target_id=new_id, relation=EdgeType.CONSOLIDATED_INTO.value))
        if classify_tier(src) == MemoryTier.EPISODIC.value and src.node_type != NodeType.LAW.value:
            src.status = "CONSOLIDATED"
            src.metadata["consolidated_into"] = new_id
            store.upsert_node(src, log_event=False)
            archived_ids.append(src.id)

    store.log_event("MEMORY_CONSOLIDATION", new_id, f"Consolidated {[s.id for s in sources]} -> {new_id} ({tier_up})")
    return {"created_node": distilled.to_dict(), "consolidated_sources": archived_ids}


def auto_consolidate_episodic(store: GraphStore, min_cluster_size: int = 3) -> Dict[str, Any]:
    """Automatically group unconsolidated Episodic experiments by track into Semantic summaries."""
    exps = [
        n for n in store.list_nodes(node_types=[NodeType.EXPERIMENT.value], limit=2000)
        if n.status not in ("CONSOLIDATED", "VICTORY_CONFIRMED")
    ]
    by_track: Dict[str, List[MemoryNode]] = {}
    for n in exps:
        tr = str(n.metadata.get("track") or "main")
        by_track.setdefault(tr, []).append(n)

    created = []
    for tr, items in by_track.items():
        if len(items) >= min_cluster_size:
            batch = items[:-1] if len(items) > min_cluster_size else items
            bullets = "; ".join(f"{b.id}[{b.status}]: {b.title[:45]}" for b in batch[:8])
            res = consolidate_nodes(
                store,
                source_ids=[b.id for b in batch],
                target_tier=MemoryTier.SEMANTIC.value,
                title=f"Distilled Track Insights: {tr.upper()} ({len(batch)} runs)",
                summary=f"Synthesized {len(batch)} episodic runs on `{tr}`: {bullets[:180]}",
            )
            created.append(res["created_node"]["id"])
    return {"created_semantic_nodes": created, "count": len(created)}
