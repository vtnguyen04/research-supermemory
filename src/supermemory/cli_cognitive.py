"""CLI handlers for Cognitive Consolidation, Global-Local Federation, and Turn Checkpoints."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from supermemory.cognitive.federation import (
    ensure_global_memory,
    list_registered_workspaces,
    promote_node_to_global,
)
from supermemory.cognitive.tiers import auto_consolidate_episodic, consolidate_nodes
from supermemory.mcp.tool_defs import execute_mcp_tool
from supermemory.storage.snapshot_io import mark_turn_memory_handled
from supermemory.storage.sqlite_store import GraphStore
from supermemory.sync.markdown_compiler import MarkdownCompiler


def handle_workspaces(_args: argparse.Namespace) -> int:
    items = list_registered_workspaces()
    print(f"🗂️ Registered SuperMemory Scopes ({len(items)}):")
    for it in items:
        print(f"  • [{it['scope']}] {it['name']} -> {it['path']}")
    return 0


def handle_consolidate(args: argparse.Namespace) -> int:
    ws = ensure_global_memory() if getattr(args, "use_global", False) else Path(args.workspace).resolve()
    with GraphStore(ws) as store:
        if args.auto:
            res = auto_consolidate_episodic(store, min_cluster_size=args.min_cluster)
        else:
            ids = [s.strip() for s in (args.ids or "").split(",") if s.strip()]
            res = consolidate_nodes(
                store,
                source_ids=ids,
                target_tier=args.tier,
                title=args.title or "Consolidated Memory",
                summary=args.summary or "",
                content=args.content or "",
            )
        mark_turn_memory_handled(store)
        MarkdownCompiler(store).compile_all()
    print("🧬 Memory Consolidation Complete:", json.dumps(res, ensure_ascii=False))
    return 0


def handle_promote(args: argparse.Namespace) -> int:
    ws = Path(args.workspace).resolve()
    with GraphStore(ws) as store:
        res = promote_node_to_global(store, args.node_id)
        mark_turn_memory_handled(store)
        MarkdownCompiler(store).compile_all()
    print(f"🌐 Promoted `{res['local_id']}` -> Global SuperMemory as `{res['global_id']}`")
    return 0


def handle_checkpoint(args: argparse.Namespace) -> int:
    out = execute_mcp_tool(
        "supermemory_checkpoint",
        {
            "workspace": str(Path(args.workspace).resolve()),
            "scope": "global" if getattr(args, "use_global", False) else "local",
            "status": args.status,
            "note": args.note or "",
            "insight_title": args.insight_title or "",
            "insight_summary": args.insight_summary or "",
            "memory_tier": args.tier,
        },
    )
    print("✓ Turn Checkpoint Attested:", json.dumps(out, ensure_ascii=False))
    return 0
