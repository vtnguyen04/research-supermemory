"""Thin Web Studio HTTP Adapter for Graph CRUD & Kernel-Backed Domain Mutations."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from supermemory.bootstrap import init_workspace
from supermemory.kernel import execute_command
from supermemory.models import EdgeType, MemoryEdge, MemoryNode, MemoryTier, NodeType
from supermemory.storage.sqlite_store import GraphStore
from supermemory.sync.agent_adapters import generate_agent_files, generate_handoff_briefing
from supermemory.sync.markdown_compiler import MarkdownCompiler
from supermemory.sync.zaloai_importer import import_zaloai_workspace
from supermemory.ui.api_research import dispatch_research_mutation


def _next_custom_id(store: GraphStore, prefix: str, node_type: str) -> str:
    nodes = store.list_nodes(node_types=[node_type], limit=5000)
    pat = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    nums = [int(m.group(1)) for n in nodes for m in [pat.match(n.id)] if m]
    return f"{prefix}-{(max(nums) + 1) if nums else 1:03d}"


def handle_workspace_action(body: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize a new/existing project folder or import from a ZALOAI workspace."""
    raw_path = str(body.get("path") or "").strip()
    if not raw_path:
        raise ValueError("Project folder path is required.")
    target = Path(raw_path).expanduser().resolve()
    name = str(body.get("name") or target.name).strip()
    goal = str(body.get("goal") or "").strip()
    max_lines = int(body.get("max_lines") or 500)
    zalo_src = str(body.get("import_zaloai_from") or "").strip()

    paths = init_workspace(target, project_name=name, max_lines=max_lines, active_goal=goal, register_in_global=True)
    imported: Dict[str, int] = {}
    if zalo_src:
        src_dir = Path(zalo_src).expanduser().resolve()
        with GraphStore(target) as store:
            imported = import_zaloai_workspace(src_dir, store)
            MarkdownCompiler(store).compile_all()
            generate_agent_files(store, install_workspace_hooks=False)
    return {"workspace_path": str(target), "project": name, "paths": paths, "imported": imported}


def dispatch_store_mutation(route: str, store: GraphStore, body: Dict[str, Any]) -> Dict[str, Any] | None:
    """Route Web Studio mutations through the unified `CommandRegistry` Kernel."""
    if route == "/api/consolidate":
        return execute_command("consolidate", {**body, "mode": "merge"}, store=store)
    if route == "/api/auto-consolidate":
        return execute_command(
            "consolidate",
            {"mode": "auto", "min_cluster_size": int(body.get("min_cluster_size") or 2)},
            store=store,
        )
    if route == "/api/promote":
        return execute_command("consolidate", {"mode": "promote", "promote_node_id": body["node_id"]}, store=store)
    if route == "/api/state":
        execute_command("update_state", body, store=store)
        return {"updated": True, "meta": store.get_all_meta()}
    if route == "/api/lessons":
        return execute_command("record_lesson", body, store=store)
    if route == "/api/audit":
        return execute_command("audit_gates", body, store=store)
    if route == "/api/ideas":
        return execute_command("propose_idea", body, store=store)
    if route == "/api/experiments":
        return execute_command("log_experiment", body, store=store)

    if route == "/api/proposals":
        act = str(body.get("action") or "create").lower()
        if act == "audit":
            return execute_command(
                "record_audit",
                {
                    "target_id": body["proposal_id"],
                    "auditor_role": body.get("auditor_role") or "VictoryAuditor",
                    "verdict": body.get("verdict") or "APPROVE",
                    "findings": body.get("findings") or "Approved via SuperMemory Web Studio.",
                },
                store=store,
            )
        if act == "advance":
            return {"node": execute_command("manage_proposal", body, store=store)}
        payload = dict(body)
        payload.setdefault("what_changes", body.get("why") or "")
        return execute_command("manage_proposal", payload, store=store)

    if route == "/api/gates":
        act = str(body.get("action") or "create").lower()
        if act == "toggle":
            ok = store.set_gate_enabled(str(body["gate_id"]), bool(body.get("enabled", True)))
            MarkdownCompiler(store).compile_all()
            return {"toggled": ok}
        if act == "delete":
            ok = store.delete_gate(str(body["gate_id"]))
            MarkdownCompiler(store).compile_all()
            return {"deleted": ok}
        return {"gate": execute_command("add_gate", body, store=store)}

    if route == "/api/handoff":
        MarkdownCompiler(store).compile_all()
        hpath = generate_handoff_briefing(store)
        return {"handoff_path": str(hpath), "markdown": hpath.read_text(encoding="utf-8")}

    if route == "/api/node/upsert":
        nid = str(body.get("id") or "").strip()
        existing = store.get_node(nid) if nid else None
        ntype = str(body.get("node_type") or (existing.node_type if existing else NodeType.KNOWLEDGE_NODE.value)).upper()
        tier = str(body.get("memory_tier") or "").upper()
        if not nid:
            pref = "PROC" if ntype == NodeType.PROCEDURE.value else ("OBS" if ntype == NodeType.OBSERVATION.value else "KNOW")
            nid = _next_custom_id(store, pref, ntype)
        meta = dict(existing.metadata) if existing else {}
        if tier in {t.value for t in MemoryTier}:
            meta["memory_tier"] = tier
        raw_tags = body.get("tags")
        tags: List[str] = (
            [t.strip() for t in raw_tags.split(",") if t.strip()]
            if isinstance(raw_tags, str)
            else list(raw_tags or (existing.tags if existing else [ntype.lower()]))
        )
        node = MemoryNode(
            id=nid,
            node_type=ntype,
            title=str(body.get("title") or (existing.title if existing else nid)).strip(),
            status=str(body.get("status") or (existing.status if existing else "ACTIVE")).strip().upper(),
            summary=str(body.get("summary") if body.get("summary") is not None else (existing.summary if existing else "")).strip(),
            content=str(body.get("content") if body.get("content") is not None else (existing.content if existing else "")).strip(),
            metadata=meta,
            file_path=existing.file_path if existing else "",
            tags=tags,
            priority=int(body.get("priority") or (existing.priority if existing else 80)),
        )
        store.upsert_node(node)
        MarkdownCompiler(store).compile_all()
        return {"node": node.to_dict()}

    if route == "/api/node/delete":
        nid = str(body.get("node_id") or "").strip()
        if not nid:
            raise ValueError("node_id is required.")
        deleted = store.delete_node(nid)
        MarkdownCompiler(store).compile_all()
        return {"deleted": deleted, "node_id": nid}

    if route in ("/api/edge/add", "/api/edge/delete"):
        src, dst = str(body.get("source_id") or "").strip(), str(body.get("target_id") or "").strip()
        if not src or not dst:
            raise ValueError("Both source_id and target_id are required.")
        rel = str(body.get("relation") or (EdgeType.REFERENCES.value if route.endswith("add") else "")).strip().upper()
        if route.endswith("add"):
            store.add_edge(MemoryEdge(source_id=src, target_id=dst, relation=rel))
            MarkdownCompiler(store).compile_all()
            return {"linked": True, "source_id": src, "target_id": dst, "relation": rel}
        ok = store.delete_edge(src, dst, rel)
        MarkdownCompiler(store).compile_all()
        return {"deleted": ok, "source_id": src, "target_id": dst, "relation": rel}

    return dispatch_research_mutation(route, store, body)
