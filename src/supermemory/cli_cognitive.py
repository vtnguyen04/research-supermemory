"""Thin CLI Handlers for Cognitive Consolidation, Promotion & Checkpoints (`kernel`-backed)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from supermemory.cognitive.federation import list_registered_workspaces
from supermemory.kernel import execute_command


def handle_workspaces(_args: argparse.Namespace) -> int:
    items = list_registered_workspaces()
    print(f"🗂️ Registered SuperMemory Scopes ({len(items)}):")
    for it in items:
        print(f"  • [{it['scope']}] {it['name']} -> {it['path']}")
    return 0


def handle_consolidate(args: argparse.Namespace) -> int:
    scope = "global" if getattr(args, "use_global", False) else "local"
    ids = [s.strip() for s in (args.ids or "").split(",") if s.strip()]
    mode = "gc" if getattr(args, "gc", False) else ("auto" if args.auto else "merge")
    res = execute_command(
        "consolidate",
        {
            "workspace": str(Path(args.workspace).resolve()),
            "scope": scope,
            "mode": mode,
            "min_cluster_size": args.min_cluster,
            "source_ids": ids,
            "target_tier": args.tier,
            "title": args.title or "Consolidated Memory",
            "summary": args.summary or "",
            "content": args.content or "",
        },
    )
    print("🧬 Memory Consolidation Complete:", json.dumps(res, ensure_ascii=False))
    return 0


def handle_promote(args: argparse.Namespace) -> int:
    res = execute_command(
        "consolidate",
        {"workspace": str(Path(args.workspace).resolve()), "mode": "promote", "promote_node_id": args.node_id},
    )
    print(f"🌐 Promoted `{res['local_id']}` -> Global SuperMemory as `{res['global_id']}`")
    return 0


def handle_checkpoint(args: argparse.Namespace) -> int:
    out = execute_command(
        "checkpoint",
        {
            "workspace": str(Path(args.workspace).resolve()),
            "scope": "global" if getattr(args, "use_global", False) else "local",
            "status": args.status,
            "note": args.note or "",
            "insight_title": args.insight_title or "",
            "insight_summary": args.insight_summary or "",
            "supersedes": getattr(args, "supersedes", "") or "",
            "memory_tier": args.tier,
        },
    )
    print("✓ Turn Checkpoint Attested:", json.dumps(out, ensure_ascii=False))
    return 0
