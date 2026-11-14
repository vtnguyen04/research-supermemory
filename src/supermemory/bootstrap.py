"""Workspace bootstrapper initializing SuperMemory Graph, Laws, Gates, and Agent Rules."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from supermemory.models import MemoryNode, NodeType
from supermemory.presets.universal_laws import build_universal_constitution
from supermemory.storage.sqlite_store import GraphStore
from supermemory.sync.agent_adapters import generate_agent_files
from supermemory.sync.markdown_compiler import MarkdownCompiler


def init_workspace(
    workspace_dir: Path | str,
    project_name: str = "",
    max_lines: int = 300,
    active_goal: str = "",
    install_workspace_hooks: bool = True,
    register_in_global: bool = True,
) -> Dict[str, Any]:
    """Idempotently initialize SuperMemory in any repository."""
    root = Path(workspace_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    name = project_name.strip() or root.name

    with GraphStore(root) as store:
        store.set_meta("project_name", name)
        store.set_meta("max_lines", str(max_lines))
        if active_goal.strip():
            store.set_meta("active_goal", active_goal.strip())
        elif not store.get_meta("active_goal"):
            store.set_meta(
                "active_goal",
                f"Build and evolve {name} with 100% constitutional compliance, scientific rigor, and zero repeated mistakes.",
            )
        if not store.get_meta("current_phase"):
            store.set_meta("current_phase", "INITIALIZED")
        if not store.get_meta("primary_targets"):
            store.set_meta(
                "primary_targets",
                f"Every source file < {max_lines} lines; 100% test/lint/type pass; 100% proposals & experiments tracked.",
            )

        laws, gates, edges = build_universal_constitution(max_lines=max_lines)
        for lw in laws:
            if not store.get_node(lw.id):
                store.upsert_node(lw, log_event=False)
        for gt in gates:
            store.upsert_gate(gt)
            if not store.get_node(gt.id):
                store.upsert_node(
                    MemoryNode(
                        id=gt.id,
                        node_type=NodeType.GATE.value,
                        title=gt.name,
                        summary=f"[{gt.gate_type}] `{gt.target_glob}` -> `{gt.pattern}`",
                        tags=["gate", gt.law_id.lower()],
                        priority=95,
                        metadata=gt.to_dict(),
                    ),
                    log_event=False,
                )
        for ed in edges:
            store.add_edge(ed)

        md_files = MarkdownCompiler(store).compile_all()
        agent_files = generate_agent_files(store, install_workspace_hooks=install_workspace_hooks)
        store.log_event("WORKSPACE_INIT", name, f"Initialized SuperMemory in {root}")

    if register_in_global:
        from supermemory.cognitive.federation import register_local_workspace

        register_local_workspace(root, project_name=name)

    return {
        "workspace": str(root),
        "project_name": name,
        "max_lines": max_lines,
        "memory_files": md_files,
        "agent_files": agent_files,
    }
