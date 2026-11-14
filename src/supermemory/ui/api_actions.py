"""Interactive Management & CRUD Action Handlers for the SuperMemory Web Studio."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from supermemory.bootstrap import init_workspace
from supermemory.cognitive.federation import promote_node_to_global
from supermemory.cognitive.tiers import auto_consolidate_episodic, consolidate_nodes
from supermemory.gates.enforcer import GateEnforcer
from supermemory.lifecycle.manager import LifecycleManager
from supermemory.models import CodeGate, EdgeType, MemoryEdge, MemoryNode, MemoryTier, NodeType
from supermemory.self_learning.consolidator import LessonConsolidator
from supermemory.storage.sqlite_store import GraphStore
from supermemory.sync.agent_adapters import generate_agent_files, generate_handoff_briefing
from supermemory.sync.markdown_compiler import MarkdownCompiler
from supermemory.sync.zaloai_importer import import_zaloai_workspace


def _next_custom_id(store: GraphStore, prefix: str, node_type: str) -> str:
    nodes = store.list_nodes(node_types=[node_type], limit=5000)
    nums: List[int] = []
    pat = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    for n in nodes:
        m = pat.match(n.id)
        if m:
            nums.append(int(m.group(1)))
    return f"{prefix}-{(max(nums) + 1) if nums else 1:03d}"


def handle_workspace_action(body: Dict[str, Any]) -> Dict[str, Any]:
    """Initialize a new/existing project folder or import from a ZALOAI workspace."""
    raw_path = str(body.get("path") or "").strip()
    if not raw_path:
        raise ValueError("Project folder path is required.")
    target = Path(raw_path).expanduser().resolve()
    name = str(body.get("name") or target.name).strip()
    goal = str(body.get("goal") or "").strip()
    max_lines = int(body.get("max_lines") or 300)
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
    """Execute a graph/lifecycle/gate mutation on `store` and recompile Markdown + Agent rules."""
    if route == "/api/consolidate":
        out = consolidate_nodes(
            store,
            source_ids=list(body.get("source_ids") or []),
            target_tier=str(body.get("target_tier") or "SEMANTIC"),
            title=str(body.get("title") or "Consolidated Memory"),
            summary=str(body.get("summary") or ""),
            content=str(body.get("content") or ""),
        )
        MarkdownCompiler(store).compile_all()
        return out

    if route == "/api/auto-consolidate":
        out = auto_consolidate_episodic(store, min_cluster_size=int(body.get("min_cluster_size") or 2))
        MarkdownCompiler(store).compile_all()
        return out

    if route == "/api/promote":
        out = promote_node_to_global(store, str(body["node_id"]))
        MarkdownCompiler(store).compile_all()
        return out

    if route == "/api/state":
        for key in ("project_name", "active_goal", "current_phase", "primary_targets", "next_actions"):
            if key in body and body[key] is not None:
                store.set_meta(key, str(body[key]))
        MarkdownCompiler(store).compile_all()
        return {"updated": True, "meta": store.get_all_meta()}

    if route == "/api/node/upsert":
        nid = str(body.get("id") or "").strip()
        existing = store.get_node(nid) if nid else None
        ntype = str(body.get("node_type") or (existing.node_type if existing else NodeType.KNOWLEDGE_NODE.value)).upper()
        tier = str(body.get("memory_tier") or "").upper()
        if not nid:
            prefix = "PROC" if ntype == NodeType.PROCEDURE.value else ("OBS" if ntype == NodeType.OBSERVATION.value else "KNOW")
            nid = _next_custom_id(store, prefix, ntype)
        meta = dict(existing.metadata) if existing else {}
        if tier in {t.value for t in MemoryTier}:
            meta["memory_tier"] = tier
        raw_tags = body.get("tags")
        tags = (
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

    if route == "/api/edge/add":
        src = str(body.get("source_id") or "").strip()
        dst = str(body.get("target_id") or "").strip()
        rel = str(body.get("relation") or EdgeType.REFERENCES.value).strip().upper()
        if not src or not dst:
            raise ValueError("Both source_id and target_id are required.")
        store.add_edge(MemoryEdge(source_id=src, target_id=dst, relation=rel))
        MarkdownCompiler(store).compile_all()
        return {"linked": True, "source_id": src, "target_id": dst, "relation": rel}

    if route == "/api/lessons":
        res = LessonConsolidator(store).record_lesson(
            title=str(body["title"]).strip(),
            mistake=str(body["mistake"]).strip(),
            root_cause=str(body["root_cause"]).strip(),
            prevention_rule=str(body["prevention_rule"]).strip(),
            user_quote=str(body.get("user_quote") or "").strip(),
            law_id=str(body.get("law_id") or "").strip(),
            new_law_title=str(body.get("new_law_title") or "").strip(),
            forbid_regex=str(body.get("forbid_regex") or "").strip(),
            target_glob=str(body.get("target_glob") or "**/*.py").strip(),
            forbid_cmd_regex=str(body.get("forbid_cmd_regex") or "").strip(),
        )
        MarkdownCompiler(store).compile_all()
        return res

    if route == "/api/gates":
        action = str(body.get("action") or "create").lower()
        enf = GateEnforcer(store)
        if action == "toggle":
            ok = store.set_gate_enabled(str(body["gate_id"]), bool(body.get("enabled", True)))
            MarkdownCompiler(store).compile_all()
            return {"toggled": ok}
        if action == "delete":
            ok = store.delete_gate(str(body["gate_id"]))
            MarkdownCompiler(store).compile_all()
            return {"deleted": ok}
        if action == "freeze" or body.get("freeze_path"):
            gate = enf.freeze_file(str(body["freeze_path"]).strip(), law_id=str(body.get("law_id") or "LAW-05"))
        else:
            gid = LessonConsolidator(store).next_gate_id()
            gtype = str(body.get("gate_type") or "FORBIDDEN_REGEX").upper()
            cfg = {"max_lines": int(body.get("max_lines") or 300)} if gtype == "MAX_LINES" else {"ignore_comments": True}
            gate = store.upsert_gate(
                CodeGate(
                    id=gid,
                    gate_type=gtype,
                    name=str(body["name"]).strip(),
                    law_id=str(body.get("law_id") or "LAW-08").strip(),
                    target_glob=str(body.get("target_glob") or "**/*.py").strip(),
                    pattern=str(body.get("pattern") or "").strip(),
                    config=cfg,
                )
            )
        MarkdownCompiler(store).compile_all()
        return {"gate": gate.to_dict()}

    if route == "/api/audit":
        return GateEnforcer(store).audit_workspace()

    if route == "/api/ideas":
        out = LifecycleManager(store).register_idea(
            title=str(body["title"]).strip(),
            summary=str(body["summary"]).strip(),
            expected_impact=str(body.get("expected_impact") or "").strip(),
            risks=str(body.get("risks") or "").strip(),
            status=str(body.get("status") or "SEED").strip().upper(),
            rejection_reason=str(body.get("rejection_reason") or "").strip(),
            is_algorithm=bool(body.get("is_algorithm", False)),
            invariants=str(body.get("invariants") or "").strip(),
        )
        MarkdownCompiler(store).compile_all()
        return out

    if route == "/api/proposals":
        lm = LifecycleManager(store)
        act = str(body.get("action") or "create").lower()
        if act == "audit":
            aud = lm.record_audit_verdict(
                target_id=str(body["proposal_id"]),
                auditor_role=str(body.get("auditor_role") or "VictoryAuditor"),
                verdict=str(body.get("verdict") or "APPROVE"),
                findings=str(body.get("findings") or "Approved via SuperMemory Web Studio."),
            )
            MarkdownCompiler(store).compile_all()
            return {"audit": aud}
        if act == "advance":
            pnode = lm.advance_proposal(str(body["proposal_id"]), str(body["new_stage"]), str(body.get("note") or ""))
            MarkdownCompiler(store).compile_all()
            return {"node": pnode.to_dict()}
        tasks_raw = body.get("tasks") or []
        tasks = [t.strip() for t in tasks_raw.splitlines() if t.strip()] if isinstance(tasks_raw, str) else list(tasks_raw)
        out = lm.create_proposal(
            title=str(body["title"]).strip(),
            why=str(body["why"]).strip(),
            what_changes=str(body.get("what_changes") or body["why"]).strip(),
            design_notes=str(body.get("design_notes") or "").strip(),
            tasks=tasks or None,
        )
        MarkdownCompiler(store).compile_all()
        return out

    if route == "/api/experiments":
        cv_val = float(body["cv_score"]) if body.get("cv_score") not in (None, "") else None
        ts_val = float(body["test_score"]) if body.get("test_score") not in (None, "") else None
        raw_ins = body.get("insights") or ""
        ins_list = [s.strip() for s in raw_ins.splitlines() if s.strip()] if isinstance(raw_ins, str) else list(raw_ins)
        out = LifecycleManager(store).log_experiment(
            track=str(body.get("track") or "main"),
            title=str(body["title"]).strip(),
            hypothesis=str(body["hypothesis"]).strip(),
            single_var_diff=str(body["single_var_diff"]).strip(),
            baseline_id=str(body.get("baseline_id") or "").strip(),
            proposal_id=str(body.get("proposal_id") or "").strip(),
            cv_score=cv_val,
            cv_summary=str(body.get("cv_summary") or "").strip(),
            test_score=ts_val,
            test_summary=str(body.get("test_summary") or "").strip(),
            verdict=str(body.get("verdict") or "KEEP").strip().upper(),
            post_mortem=str(body.get("post_mortem") or "").strip(),
            insights=ins_list,
        )
        MarkdownCompiler(store).compile_all()
        return out

    if route == "/api/handoff":
        MarkdownCompiler(store).compile_all()
        hpath = generate_handoff_briefing(store)
        return {"handoff_path": str(hpath), "markdown": hpath.read_text(encoding="utf-8")}

    return None
