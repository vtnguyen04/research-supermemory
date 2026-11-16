"""Declarative Kernel Commands: Federated Recall, L0 Working State, Knowledge Graph & Tier Consolidation."""

from __future__ import annotations

from typing import Any, Dict

from supermemory.cognitive.federation import (
    federated_recall,
    promote_node_to_global,
    resolve_default_workspace,
)
from supermemory.cognitive.tiers import auto_consolidate_episodic, consolidate_nodes
from supermemory.kernel.registry import REGISTRY, SCOPE_SCHEMA_PROP
from supermemory.models import MemoryEdge, MemoryNode, MemoryTier, NodeType
from supermemory.storage.sqlite_store import GraphStore
from supermemory.sync.markdown_compiler import MarkdownCompiler


@REGISTRY.register(
    name="recall",
    description="2-Stage Progressive Recall: Stage-1 compact index search (`query`) or Stage-2 full node expansion (`node_id`).",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "default": ""},
            "node_id": {"type": "string", "description": "Optional Stage-2 ID (e.g. METH-001, OBS-001) to fetch full content."},
            "limit": {"type": "integer", "default": 6},
            "hops": {"type": "integer", "default": 1},
            "compact": {"type": "boolean", "default": True},
            "include_global": {"type": "boolean", "default": True},
            "include_siblings": {"type": "boolean", "default": False},
            "workspace": {"type": "string"},
        },
    },
    requires_store=False,
    mutates_memory=False,
)
def _cmd_recall(args: Dict[str, Any]) -> Dict[str, Any]:
    raw_ws = resolve_default_workspace(str(args.get("workspace") or ""))
    local_ok = (raw_ws / ".supermemory").is_dir() or (raw_ws / "memory" / "graph_snapshot.json").is_file()
    return federated_recall(
        str(args.get("query") or ""),
        local_ws=raw_ws if local_ok else None,
        include_global=bool(args.get("include_global", True)),
        include_siblings=bool(args.get("include_siblings", False)),
        limit=int(args.get("limit") or 6),
        hops=int(args.get("hops") or 1),
        compact=bool(args.get("compact", True)),
        node_id=str(args.get("node_id") or ""),
    )


@REGISTRY.register(
    name="update_state",
    description="Atomically update L0 Working State (01_ACTIVE_STATE.md), Agent Rules, and Snapshot.",
    input_schema={
        "type": "object",
        "properties": {
            "active_goal": {"type": "string"},
            "current_phase": {"type": "string"},
            "primary_targets": {"type": "string"},
            "next_actions": {"type": "string"},
            "state_notes": {"type": "string"},
            "workspace": {"type": "string"},
        },
    },
    mutates_memory=True,
)
def _cmd_update_state(store: GraphStore, args: Dict[str, Any]) -> Dict[str, Any]:
    changed = []
    for k in ("project_name", "active_goal", "current_phase", "primary_targets", "next_actions", "state_notes"):
        if args.get(k) is not None:
            store.set_meta(k, str(args[k]))
            changed.append(k)
    if changed:
        store.log_event("STATE_UPDATED", "L0_STATE", f"Updated L0 working state ({', '.join(changed)})")
    return MarkdownCompiler(store).compile_all()


@REGISTRY.register(
    name="link_knowledge",
    description="Upsert a PROCEDURAL (PROCEDURE) or SEMANTIC (KNOWLEDGE_NODE / OBSERVATION) entity and/or typed edge.",
    input_schema={
        "type": "object",
        "properties": {
            "node_id": {"type": "string"},
            "node_type": {"type": "string", "default": "KNOWLEDGE_NODE"},
            "memory_tier": {"type": "string", "enum": ["PROCEDURAL", "SEMANTIC", "EPISODIC"]},
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "content": {"type": "string"},
            "source_id": {"type": "string"},
            "target_id": {"type": "string"},
            "relation": {"type": "string", "default": "REFERENCES"},
            "scope": SCOPE_SCHEMA_PROP,
            "workspace": {"type": "string"},
        },
    },
    mutates_memory=True,
)
def _cmd_link_knowledge(store: GraphStore, args: Dict[str, Any]) -> Dict[str, Any]:
    created: Dict[str, Any] = {}
    if args.get("node_id") and args.get("title"):
        meta = {"memory_tier": str(args["memory_tier"])} if args.get("memory_tier") else {}
        nd = store.upsert_node(
            MemoryNode(
                id=str(args["node_id"]),
                node_type=str(args.get("node_type") or NodeType.KNOWLEDGE_NODE.value),
                title=str(args["title"]),
                summary=str(args.get("summary") or ""),
                content=str(args.get("content") or ""),
                metadata=meta,
            )
        )
        created["node"] = nd.to_dict()
    if args.get("source_id") and args.get("target_id"):
        ed = MemoryEdge(
            source_id=str(args["source_id"]),
            target_id=str(args["target_id"]),
            relation=str(args.get("relation") or "REFERENCES"),
        )
        store.add_edge(ed)
        store.log_event("EDGE_LINKED", ed.source_id, f"Linked {ed.source_id} -[{ed.relation}]-> {ed.target_id}")
        created["edge"] = ed.to_dict()
    return created


@REGISTRY.register(
    name="consolidate",
    description="Consolidate/merge Episodic nodes into compact Semantic/Procedural memory, auto-compact tracks, or promote Local -> Global.",
    input_schema={
        "type": "object",
        "properties": {
            "mode": {"type": "string", "enum": ["merge", "auto", "promote"], "default": "merge"},
            "source_ids": {"type": "array", "items": {"type": "string"}},
            "target_tier": {"type": "string", "enum": ["SEMANTIC", "PROCEDURAL"], "default": "SEMANTIC"},
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "content": {"type": "string"},
            "promote_node_id": {"type": "string"},
            "min_cluster_size": {"type": "integer", "default": 3},
            "workspace": {"type": "string"},
        },
    },
    mutates_memory=True,
)
def _cmd_consolidate(store: GraphStore, args: Dict[str, Any]) -> Dict[str, Any]:
    mode = str(args.get("mode") or "merge").lower()
    if mode == "promote":
        return promote_node_to_global(store, str(args["promote_node_id"]))
    if mode == "auto":
        return auto_consolidate_episodic(store, min_cluster_size=int(args.get("min_cluster_size") or 3))
    return consolidate_nodes(
        store,
        source_ids=list(args.get("source_ids") or []),
        target_tier=str(args.get("target_tier") or MemoryTier.SEMANTIC.value),
        title=str(args.get("title") or "Consolidated Memory"),
        summary=str(args.get("summary") or ""),
        content=str(args.get("content") or ""),
    )
