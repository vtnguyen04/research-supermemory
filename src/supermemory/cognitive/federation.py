"""Global (~/.supermemory/global) + Per-Folder Local SuperMemory Federation & Workspace Registry."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from supermemory.bootstrap import init_workspace
from supermemory.cognitive.tiers import classify_tier
from supermemory.graph.query_engine import QueryEngine
from supermemory.models import CodeGate, EdgeType, MemoryEdge, MemoryNode, utc_now_iso
from supermemory.storage.sqlite_store import GraphStore
from supermemory.sync.markdown_compiler import MarkdownCompiler


def get_global_root() -> Path:
    """Return Global SuperMemory directory (overrideable via SUPERMEMORY_GLOBAL_DIR for tests)."""
    env_dir = os.environ.get("SUPERMEMORY_GLOBAL_DIR", "").strip()
    if env_dir:
        return Path(env_dir).resolve()
    return (Path.home() / ".supermemory" / "global").resolve()


def ensure_global_memory() -> Path:
    """Lazily initialize Global SuperMemory once without touching any user repository."""
    g_root = get_global_root()
    if not (g_root / ".supermemory" / "supermemory.db").is_file() and not (
        g_root / "memory" / "graph_snapshot.json"
    ).is_file():
        init_workspace(
            g_root,
            project_name="Global-SuperMemory",
            max_lines=300,
            active_goal="Cross-project developer preferences, universal laws, reusable procedures & anti-regression gates.",
            install_workspace_hooks=False,
            register_in_global=False,
        )
    return g_root


def _registry_file() -> Path:
    g_root = ensure_global_memory()
    return g_root / "workspaces.json"


def register_local_workspace(workspace_root: Path, project_name: str = "") -> None:
    """Register a Local project SuperMemory in ~/.supermemory/global/workspaces.json."""
    ws = workspace_root.resolve()
    g_root = get_global_root()
    if ws == g_root or ("pytest-of-" in str(ws) and not os.environ.get("SUPERMEMORY_GLOBAL_DIR", "").strip()):
        return
    reg_path = _registry_file()
    entries: List[Dict[str, Any]] = []
    if reg_path.is_file():
        try:
            entries = json.loads(reg_path.read_text(encoding="utf-8"))
        except ValueError:
            entries = []
    by_path = {str(item.get("path")): item for item in entries if item.get("path")}
    by_path[str(ws)] = {
        "path": str(ws),
        "name": project_name or ws.name,
        "updated_at": utc_now_iso(),
    }
    reg_path.write_text(json.dumps(list(by_path.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_registered_workspaces() -> List[Dict[str, Any]]:
    """Return Global SuperMemory plus all active Local project workspaces."""
    g_root = ensure_global_memory()
    out: List[Dict[str, Any]] = [
        {
            "id": "global",
            "scope": "GLOBAL",
            "name": "🌐 Global SuperMemory (All Projects)",
            "path": str(g_root),
            "exists": True,
        }
    ]
    reg_path = g_root / "workspaces.json"
    if reg_path.is_file():
        try:
            raw = json.loads(reg_path.read_text(encoding="utf-8"))
        except ValueError:
            raw = []
        for item in raw:
            p = Path(str(item.get("path") or ""))
            if "pytest-of-" in str(p) and not os.environ.get("SUPERMEMORY_GLOBAL_DIR", "").strip():
                continue
            if p.is_dir() and ((p / ".supermemory").is_dir() or (p / "memory" / "graph_snapshot.json").is_file()):
                out.append(
                    {
                        "id": str(p),
                        "scope": "LOCAL",
                        "name": str(item.get("name") or p.name),
                        "path": str(p),
                        "exists": True,
                    }
                )
    return out


def promote_node_to_global(local_store: GraphStore, node_id: str) -> Dict[str, Any]:
    """Promote a Local LAW, PROCEDURE, GATE, LESSON, or SEMANTIC insight up to Global SuperMemory."""
    node = local_store.get_node(node_id)
    if not node:
        raise ValueError(f"Node `{node_id}` not found in local workspace {local_store.workspace_root}")
    g_root = ensure_global_memory()
    proj_name = local_store.get_meta("project_name") or local_store.workspace_root.name
    global_id = node.id if node.id.startswith("LAW-") else f"GLB-{proj_name[:8].upper()}-{node.id}"

    with GraphStore(g_root) as g_store:
        meta = dict(node.metadata or {})
        meta["promoted_from_workspace"] = str(local_store.workspace_root)
        meta["promoted_from_project"] = proj_name
        meta["memory_tier"] = classify_tier(node)
        promoted = g_store.upsert_node(
            MemoryNode(
                id=global_id,
                node_type=node.node_type,
                title=node.title,
                status="ACTIVE",
                summary=f"[{proj_name}] {node.summary}"[:240],
                content=node.content,
                tags=list(set([*(node.tags or []), "global", "promoted"])),
                priority=max(node.priority, 90),
                metadata=meta,
            )
        )
        # If local node was a CodeGate (not FROZEN_SHA256 repo-specific file), promote gate too
        local_gates = [g for g in local_store.list_gates() if g.id == node_id or g.lesson_id == node_id]
        for lg in local_gates:
            if lg.gate_type != "FROZEN_SHA256":
                g_store.upsert_gate(
                    CodeGate(
                        id=f"GLB-{lg.id}",
                        gate_type=lg.gate_type,
                        name=f"[Global] {lg.name}",
                        law_id=lg.law_id or "LAW-08",
                        target_glob=lg.target_glob,
                        pattern=lg.pattern,
                        config=lg.config,
                    )
                )
        MarkdownCompiler(g_store).compile_all()

    local_store.add_edge(MemoryEdge(source_id=node.id, target_id=global_id, relation=EdgeType.PROMOTED_TO.value))
    local_store.log_event("PROMOTED_TO_GLOBAL", node.id, f"Promoted {node.id} -> Global `{global_id}`")
    return {"local_id": node.id, "global_id": global_id, "global_node": promoted.to_dict()}


def federated_recall(
    query: str,
    local_ws: Optional[Path] = None,
    include_global: bool = True,
    limit: int = 8,
    hops: int = 1,
) -> Dict[str, Any]:
    """Query Local project SuperMemory + Global SuperMemory with consolidated-episode filtering."""
    merged_results: List[Dict[str, Any]] = []
    warnings: List[str] = []

    if local_ws is not None and (
        (local_ws / ".supermemory").is_dir() or (local_ws / "memory" / "graph_snapshot.json").is_file()
    ):
        with GraphStore(local_ws) as l_store:
            l_rec = QueryEngine(l_store).recall(query, limit=limit, hops=hops)
            warnings.extend(l_rec["anti_repeat_warnings"])
            for r in l_rec["results"]:
                if r.get("status") != "CONSOLIDATED":
                    merged_results.append({**r, "scope": "LOCAL", "tier": classify_tier({"node_type": r["type"], "metadata": {}})})

    if include_global:
        g_root = ensure_global_memory()
        if local_ws is None or local_ws.resolve() != g_root:
            with GraphStore(g_root) as g_store:
                g_rec = QueryEngine(g_store).recall(query, limit=max(4, limit // 2), hops=1)
                for w in g_rec["anti_repeat_warnings"]:
                    warnings.append(f"[GLOBAL] {w}")
                for r in g_rec["results"]:
                    if r.get("status") != "CONSOLIDATED":
                        merged_results.append(
                            {**r, "scope": "GLOBAL", "tier": classify_tier({"node_type": r["type"], "metadata": {}})}
                        )

    return {
        "query": query,
        "local_initialized": local_ws is not None,
        "anti_repeat_warnings": warnings[:8],
        "results": merged_results[: limit + 6],
    }
