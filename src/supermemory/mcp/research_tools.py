"""MCP Schemas & Handlers for Research Intelligence v3.0 (Bottlenecks, SOTA Scout & Fast-DAG)."""

from __future__ import annotations

from typing import Any, Dict, List

from supermemory.lifecycle.manager import LifecycleManager
from supermemory.research.bottleneck_engine import (
    diagnose_bottleneck,
    evaluate_occam_gate,
    rank_bottlenecks,
    resolve_bottleneck,
)
from supermemory.research.orchestrator import (
    claim_next_task,
    complete_task,
    dag_telemetry,
    enqueue_task,
    list_tasks,
    plan_research_sprint,
)
from supermemory.research.sota_scout import register_method_card, scout_sota_papers
from supermemory.storage.snapshot_io import mark_turn_memory_handled
from supermemory.storage.sqlite_store import GraphStore
from supermemory.sync.markdown_compiler import MarkdownCompiler

RESEARCH_TOOL_NAMES = {
    "supermemory_diagnose_bottleneck",
    "supermemory_scout_sota",
    "supermemory_orchestrate",
}

RESEARCH_MCP_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "supermemory_diagnose_bottleneck",
        "description": "Bottleneck-First Research Engine: profile/register quantified BOTTLENECK (BNK-XXX) + falsifiable RQ-XXX, rank Pareto bottlenecks, or propose/score a single-variable hypothesis via Occam ROI Gate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["diagnose", "rank", "resolve", "score_occam", "propose_hypothesis"],
                    "default": "diagnose",
                },
                "title": {"type": "string"},
                "evidence_slice": {"type": "string"},
                "error_share_pct": {"type": "number"},
                "ceiling_gain": {"type": "number"},
                "falsifiable_rq": {"type": "string"},
                "metric_name": {"type": "string", "default": "primary_metric"},
                "baseline_value": {"type": "number"},
                "kill_criterion": {"type": "string"},
                "smoke_eval_cmd": {"type": "string"},
                "bottleneck_id": {"type": "string"},
                "what_changes": {"type": "string"},
                "est_loc": {"type": "integer", "default": 60},
                "coupled_vars": {"type": "integer", "default": 1},
                "compute_cost": {"type": "number", "default": 1.0},
                "confidence": {"type": "number", "default": 0.75},
                "novelty_diff": {"type": "string"},
                "resolution_exp_id": {"type": "string"},
                "workspace": {"type": "string"},
            },
        },
    },
    {
        "name": "supermemory_scout_sota",
        "description": "SOTA Literature & Method Scout: search arXiv + Semantic Scholar + OpenAlex (SQLite cached) or register a structured METHOD_CARD (METH-XXX) linked to a BOTTLENECK.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["search", "register_card"], "default": "search"},
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 6},
                "min_year": {"type": "integer", "default": 2022},
                "save_top_k": {"type": "integer", "default": 0},
                "bottleneck_id": {"type": "string"},
                "title": {"type": "string"},
                "bottleneck_addressed": {"type": "string"},
                "core_mechanism": {"type": "string"},
                "assumptions_and_limits": {"type": "string"},
                "complexity_cost": {"type": "string", "default": "O(N)"},
                "minimal_integration_hook": {"type": "string"},
                "source_url": {"type": "string"},
                "venue": {"type": "string"},
                "year": {"type": "integer", "default": 2025},
                "workspace": {"type": "string"},
            },
        },
    },
    {
        "name": "supermemory_orchestrate",
        "description": "Multi-Agent Fast-DAG Orchestrator: plan a 3-Wave parallel research sprint, enqueue tasks, atomically claim glob-locked tasks, complete with <180-token receipts, or inspect DAG telemetry.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["plan_sprint", "enqueue", "claim", "complete", "status"],
                    "default": "status",
                },
                "goal": {"type": "string"},
                "bottleneck_id": {"type": "string"},
                "smoke_cmd": {"type": "string", "default": "pytest -q"},
                "target_globs": {"type": "array", "items": {"type": "string"}},
                "task_id": {"type": "string"},
                "wave": {"type": "integer", "default": 1},
                "role": {"type": "string"},
                "title": {"type": "string"},
                "brief": {"type": "string"},
                "depends_on": {"type": "array", "items": {"type": "string"}},
                "locked_globs": {"type": "array", "items": {"type": "string"}},
                "agent_name": {"type": "string", "default": "worker"},
                "status": {"type": "string", "default": "DONE"},
                "receipt": {"type": "object"},
                "workspace": {"type": "string"},
            },
        },
    },
]


def execute_research_mcp_tool(name: str, store: GraphStore, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute one of the v3.0 Research & Multi-Agent MCP tools."""
    if name == "supermemory_diagnose_bottleneck":
        act = str(args.get("action") or "diagnose").lower()
        if act == "rank":
            return {"bottlenecks": rank_bottlenecks(store, include_resolved=bool(args.get("include_resolved", False)))}
        if act == "resolve":
            out = resolve_bottleneck(
                store,
                bottleneck_id=str(args["bottleneck_id"]),
                resolution_exp_id=str(args.get("resolution_exp_id") or ""),
                note=str(args.get("note") or ""),
            )
            mark_turn_memory_handled(store)
            MarkdownCompiler(store).compile_all()
            return {"resolved": out}
        if act == "score_occam":
            return evaluate_occam_gate(
                store,
                title=str(args.get("title") or ""),
                body=str(args.get("what_changes") or args.get("evidence_slice") or ""),
                bottleneck_id=str(args.get("bottleneck_id") or ""),
                est_loc=int(args.get("est_loc") or 60),
                coupled_vars=int(args.get("coupled_vars") or 1),
                compute_cost=float(args.get("compute_cost") or 1.0),
                confidence=float(args.get("confidence") or 0.75),
                kill_criterion=str(args.get("kill_criterion") or ""),
                strict_occam=bool(args.get("strict_occam", False)),
            )
        if act == "propose_hypothesis":
            res = LifecycleManager(store).create_proposal(
                title=str(args["title"]),
                why=str(args.get("falsifiable_rq") or args.get("evidence_slice") or args["title"]),
                what_changes=str(args["what_changes"]),
                bottleneck_id=str(args.get("bottleneck_id") or ""),
                kill_criterion=str(args.get("kill_criterion") or ""),
                est_loc=int(args.get("est_loc") or 60),
                coupled_vars=int(args.get("coupled_vars") or 1),
                novelty_diff=str(args.get("novelty_diff") or ""),
                strict_occam=True,
            )
            mark_turn_memory_handled(store)
            MarkdownCompiler(store).compile_all()
            return res

        res = diagnose_bottleneck(
            store,
            title=str(args["title"]),
            evidence_slice=str(args["evidence_slice"]),
            error_share_pct=float(args["error_share_pct"]),
            ceiling_gain=float(args["ceiling_gain"]),
            falsifiable_rq=str(args["falsifiable_rq"]),
            metric_name=str(args.get("metric_name") or "primary_metric"),
            baseline_value=float(args["baseline_value"]) if args.get("baseline_value") is not None else None,
            kill_criterion=str(args.get("kill_criterion") or ""),
            smoke_eval_cmd=str(args.get("smoke_eval_cmd") or ""),
        )
        mark_turn_memory_handled(store)
        MarkdownCompiler(store).compile_all()
        return res

    if name == "supermemory_scout_sota":
        act = str(args.get("action") or "search").lower()
        if act == "register_card":
            card = register_method_card(
                store,
                title=str(args["title"]),
                bottleneck_addressed=str(args.get("bottleneck_addressed") or args.get("bottleneck_id") or "Target bottleneck"),
                core_mechanism=str(args["core_mechanism"]),
                assumptions_and_limits=str(args.get("assumptions_and_limits") or "Validate empirically on slice."),
                complexity_cost=str(args.get("complexity_cost") or "O(N)"),
                minimal_integration_hook=str(args.get("minimal_integration_hook") or ""),
                source_url=str(args.get("source_url") or ""),
                venue=str(args.get("venue") or "Literature"),
                year=int(args.get("year") or 2025),
                bottleneck_id=str(args.get("bottleneck_id") or ""),
            )
            mark_turn_memory_handled(store)
            MarkdownCompiler(store).compile_all()
            return {"method_card": card}

        res = scout_sota_papers(
            store,
            query=str(args["query"]),
            limit=int(args.get("limit") or 6),
            min_year=int(args.get("min_year") or 2022),
            bottleneck_id=str(args.get("bottleneck_id") or ""),
            save_top_k=int(args.get("save_top_k") or 0),
        )
        if res["saved_method_cards"]:
            mark_turn_memory_handled(store)
            MarkdownCompiler(store).compile_all()
        return res

    if name == "supermemory_orchestrate":
        act = str(args.get("action") or "status").lower()
        if act == "plan_sprint":
            res = plan_research_sprint(
                store,
                goal=str(args["goal"]),
                bottleneck_id=str(args.get("bottleneck_id") or ""),
                smoke_cmd=str(args.get("smoke_cmd") or "pytest -q"),
                target_globs=list(args["target_globs"]) if args.get("target_globs") is not None else None,
            )
            MarkdownCompiler(store).compile_all()
            return res
        if act == "enqueue":
            task = enqueue_task(
                store,
                role=str(args.get("role") or "self"),
                title=str(args["title"]),
                brief=str(args.get("brief") or ""),
                wave=int(args.get("wave") or 1),
                depends_on=list(args.get("depends_on") or []),
                locked_globs=list(args.get("locked_globs") or []),
                target_id=str(args.get("bottleneck_id") or ""),
                smoke_gate=str(args.get("smoke_cmd") or ""),
                task_id=str(args.get("task_id") or ""),
            )
            MarkdownCompiler(store).compile_all()
            return {"task": task.to_dict()}
        if act == "claim":
            claimed = claim_next_task(
                store,
                agent_name=str(args.get("agent_name") or "worker"),
                role=str(args.get("role") or ""),
            )
            return {"claimed": claimed}
        if act == "complete":
            res = complete_task(
                store,
                task_id=str(args["task_id"]),
                status=str(args.get("status") or "DONE"),
                receipt=dict(args.get("receipt") or {}),
            )
            mark_turn_memory_handled(store)
            MarkdownCompiler(store).compile_all()
            return res
        return {
            "telemetry": dag_telemetry(store),
            "tasks": [t.to_dict() for t in list_tasks(store)],
        }

    raise ValueError(f"Unknown research MCP tool: {name}")
