"""MCP tool execution handlers for SuperMemory v2.0 (Tiered, Federated & Semantic Attested)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

from supermemory.bootstrap import init_workspace
from supermemory.cognitive.federation import (
    ensure_global_memory,
    federated_recall,
    list_registered_workspaces,
    promote_node_to_global,
)
from supermemory.cognitive.tiers import (
    auto_consolidate_episodic,
    build_tiered_capsule,
    compute_tier_telemetry,
    consolidate_nodes,
)
from supermemory.gates.enforcer import GateEnforcer
from supermemory.graph.query_engine import QueryEngine
from supermemory.lifecycle.manager import LifecycleManager
from supermemory.mcp.tool_schemas import MCP_TOOLS
from supermemory.models import CodeGate, MemoryEdge, MemoryNode, MemoryTier, NodeType
from supermemory.self_learning.consolidator import LessonConsolidator
from supermemory.storage.snapshot_io import mark_turn_memory_handled
from supermemory.storage.sqlite_store import GraphStore
from supermemory.sync.agent_adapters import generate_handoff_briefing
from supermemory.sync.markdown_compiler import MarkdownCompiler

__all__ = ["MCP_TOOLS", "execute_mcp_tool"]


def _resolve_target_root(args: Dict[str, Any]) -> Path:
    if str(args.get("scope") or "local").lower() == "global":
        return ensure_global_memory()
    ws = Path(str(args.get("workspace") or Path.cwd())).resolve()
    if (ws / ".supermemory").is_dir() or (ws / "memory" / "graph_snapshot.json").is_file():
        return ws
    return ws


def execute_mcp_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch an MCP tool call against Local or Global SuperMemory."""
    raw_ws = Path(str(args.get("workspace") or Path.cwd())).resolve()
    if name == "supermemory_init":
        return init_workspace(
            raw_ws,
            project_name=str(args.get("project_name") or raw_ws.name),
            max_lines=int(args.get("max_lines") or 300),
        )

    if name == "supermemory_recall":
        local_ok = (raw_ws / ".supermemory").is_dir() or (raw_ws / "memory" / "graph_snapshot.json").is_file()
        return federated_recall(
            str(args["query"]),
            local_ws=raw_ws if local_ok else None,
            include_global=bool(args.get("include_global", True)),
            hops=int(args.get("hops") or 1),
        )

    target_root = _resolve_target_root(args)
    # If folder has no local .supermemory yet and user didn't init, fall back to Global for status/checkpoint/lessons
    if (
        str(args.get("scope") or "local").lower() == "local"
        and not (target_root / ".supermemory").is_dir()
        and not (target_root / "memory" / "graph_snapshot.json").is_file()
        and name in ("supermemory_status", "supermemory_checkpoint")
    ):
        target_root = ensure_global_memory()

    with GraphStore(target_root) as store:
        if name == "supermemory_status":
            qe = QueryEngine(store)
            return {
                "scope": "global" if target_root == ensure_global_memory() else "local",
                "capsule": build_tiered_capsule(store),
                "analytics": qe.graph_analytics(),
                "cognitive_tiers": compute_tier_telemetry(store),
                "workspaces": list_registered_workspaces(),
            }

        if name == "supermemory_record_lesson":
            res = LessonConsolidator(store).record_lesson(
                title=str(args["title"]),
                mistake=str(args["mistake"]),
                root_cause=str(args["root_cause"]),
                prevention_rule=str(args["prevention_rule"]),
                user_quote=str(args.get("user_quote") or ""),
                law_id=str(args.get("law_id") or ""),
                new_law_title=str(args.get("new_law_title") or ""),
                forbid_regex=str(args.get("forbid_regex") or ""),
                target_glob=str(args.get("target_glob") or "**/*.py"),
                forbid_cmd_regex=str(args.get("forbid_cmd_regex") or ""),
            )
            mark_turn_memory_handled(store, clear_lesson_lock=True)
            MarkdownCompiler(store).compile_all()
            return res

        if name == "supermemory_add_gate":
            enf = GateEnforcer(store)
            if args.get("freeze_path"):
                gate = enf.freeze_file(str(args["freeze_path"]), law_id=str(args.get("law_id") or "LAW-05"))
            else:
                gid = LessonConsolidator(store).next_gate_id()
                gate = store.upsert_gate(
                    CodeGate(
                        id=gid,
                        gate_type=str(args.get("gate_type") or "FORBIDDEN_REGEX"),
                        name=str(args["name"]),
                        law_id=str(args.get("law_id") or "LAW-08"),
                        target_glob=str(args.get("target_glob") or "**/*.py"),
                        pattern=str(args.get("pattern") or ""),
                    )
                )
            mark_turn_memory_handled(store, clear_lesson_lock=True)
            MarkdownCompiler(store).compile_all()
            return gate.to_dict()

        if name == "supermemory_propose_idea":
            res = LifecycleManager(store).register_idea(
                title=str(args["title"]),
                summary=str(args["summary"]),
                expected_impact=str(args.get("expected_impact") or ""),
                risks=str(args.get("risks") or ""),
                status=str(args.get("status") or "SEED"),
                rejection_reason=str(args.get("rejection_reason") or ""),
                is_algorithm=bool(args.get("is_algorithm", False)),
                invariants=str(args.get("invariants") or ""),
                novelty_diff=str(args.get("novelty_diff") or ""),
            )
            mark_turn_memory_handled(store)
            MarkdownCompiler(store).compile_all()
            return res

        if name == "supermemory_manage_proposal":
            lm = LifecycleManager(store)
            if args.get("action") == "advance":
                nd = lm.advance_proposal(str(args["proposal_id"]), str(args["new_stage"]), str(args.get("note") or ""))
                out: Dict[str, Any] = nd.to_dict()
            else:
                out = lm.create_proposal(
                    title=str(args.get("title") or "Untitled Proposal"),
                    why=str(args.get("why") or ""),
                    what_changes=str(args.get("what_changes") or ""),
                    design_notes=str(args.get("design_notes") or ""),
                    tasks=list(args.get("tasks") or []),
                    proposal_id=str(args.get("proposal_id") or ""),
                    novelty_diff=str(args.get("novelty_diff") or ""),
                )
            mark_turn_memory_handled(store)
            MarkdownCompiler(store).compile_all()
            return out

        if name == "supermemory_log_experiment":
            res = LifecycleManager(store).log_experiment(
                track=str(args.get("track") or "main"),
                exp_id=str(args.get("exp_id") or ""),
                title=str(args["title"]),
                hypothesis=str(args["hypothesis"]),
                single_var_diff=str(args["single_var_diff"]),
                model_stack=str(args.get("model_stack") or ""),
                baseline_id=str(args.get("baseline_id") or ""),
                proposal_id=str(args.get("proposal_id") or ""),
                cv_score=args.get("cv_score"),
                cv_summary=str(args.get("cv_summary") or ""),
                test_score=args.get("test_score"),
                test_summary=str(args.get("test_summary") or ""),
                runtime_summary=str(args.get("runtime_summary") or ""),
                verdict=str(args.get("verdict") or "KEEP"),
                post_mortem=str(args.get("post_mortem") or ""),
                insights=list(args.get("insights") or []),
            )
            mark_turn_memory_handled(store)
            MarkdownCompiler(store).compile_all()
            return res

        if name == "supermemory_update_state":
            for k in ("active_goal", "current_phase", "primary_targets", "next_actions", "state_notes"):
                if args.get(k) is not None:
                    store.set_meta(k, str(args[k]))
            mark_turn_memory_handled(store)
            return MarkdownCompiler(store).compile_all()

        if name == "supermemory_link_knowledge":
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
                created["edge"] = ed.to_dict()
            mark_turn_memory_handled(store)
            MarkdownCompiler(store).compile_all()
            return created

        if name == "supermemory_consolidate":
            mode = str(args.get("mode") or "merge").lower()
            if mode == "promote":
                res = promote_node_to_global(store, str(args["promote_node_id"]))
            elif mode == "auto":
                res = auto_consolidate_episodic(store)
            else:
                res = consolidate_nodes(
                    store,
                    source_ids=list(args.get("source_ids") or []),
                    target_tier=str(args.get("target_tier") or MemoryTier.SEMANTIC.value),
                    title=str(args.get("title") or "Consolidated Memory"),
                    summary=str(args.get("summary") or ""),
                    content=str(args.get("content") or ""),
                )
            mark_turn_memory_handled(store)
            MarkdownCompiler(store).compile_all()
            return res

        if name == "supermemory_checkpoint":
            captured = None
            if args.get("insight_title") and args.get("insight_summary"):
                tier = str(args.get("memory_tier") or MemoryTier.SEMANTIC.value).upper()
                ntype = NodeType.PROCEDURE.value if tier == "PROCEDURAL" else NodeType.OBSERVATION.value
                pref = "PROC" if tier == "PROCEDURAL" else "OBS"
                existing = store.list_nodes(node_types=[ntype], limit=5000)
                nums = [int(m.group(1)) for x in existing for m in [re.match(rf"^{pref}-(\d+)$", x.id)] if m]
                nid = f"{pref}-{(max(nums) + 1) if nums else 1:03d}"
                nd = store.upsert_node(
                    MemoryNode(
                        id=nid,
                        node_type=ntype,
                        title=str(args["insight_title"]),
                        summary=str(args["insight_summary"])[:240],
                        content=str(args["insight_summary"]),
                        metadata={"memory_tier": tier, "note": str(args.get("note") or "")},
                    )
                )
                captured = nd.to_dict()
                MarkdownCompiler(store).compile_all()
            mark_turn_memory_handled(store)
            return {"status": str(args.get("status") or "CLEAN"), "turn_memory_handled": True, "captured": captured}

        if name == "supermemory_audit_gates":
            return GateEnforcer(store).audit_workspace()

        if name == "supermemory_record_audit":
            out_res: Dict[str, Any] = {}
            if args.get("target_id") and args.get("verdict"):
                out_res["audit"] = LifecycleManager(store).record_audit_verdict(
                    target_id=str(args["target_id"]),
                    auditor_role=str(args.get("auditor_role") or "VictoryAuditor"),
                    verdict=str(args["verdict"]),
                    findings=str(args.get("findings") or ""),
                )
            if args.get("generate_handoff"):
                out_res["handoff_path"] = str(generate_handoff_briefing(store))
            mark_turn_memory_handled(store)
            MarkdownCompiler(store).compile_all()
            return out_res

    raise ValueError(f"Unknown MCP tool: {name}")
