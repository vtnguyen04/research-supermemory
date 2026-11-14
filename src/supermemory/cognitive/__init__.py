"""Cognitive Memory Architecture (Working/Procedural/Semantic/Episodic) & Global-Local Federation."""

from __future__ import annotations

from supermemory.cognitive.federation import (
    ensure_global_memory,
    federated_recall,
    get_global_root,
    list_registered_workspaces,
    promote_node_to_global,
    register_local_workspace,
)
from supermemory.cognitive.tiers import (
    auto_consolidate_episodic,
    build_tiered_capsule,
    classify_tier,
    compute_tier_telemetry,
    consolidate_nodes,
)

__all__ = [
    "auto_consolidate_episodic",
    "build_tiered_capsule",
    "classify_tier",
    "compute_tier_telemetry",
    "consolidate_nodes",
    "ensure_global_memory",
    "federated_recall",
    "get_global_root",
    "list_registered_workspaces",
    "promote_node_to_global",
    "register_local_workspace",
]
