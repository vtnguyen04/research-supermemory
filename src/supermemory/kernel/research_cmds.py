"""Declarative Kernel Commands: Pareto Bottlenecks, SOTA Method Scout & Multi-Agent Kanban/DAG."""

from __future__ import annotations

from typing import Any, Dict, List

from supermemory.kernel.checkpoint_sync import execute_kanban_orchestrate_ext
from supermemory.kernel.registry import REGISTRY
from supermemory.lifecycle.manager import LifecycleManager
from supermemory.research.bottleneck_engine import (
    diagnose_bottleneck,
    evaluate_occam_gate,
    rank_bottlenecks,
    resolve_bottleneck,
)
from supermemory.research.orchestrator import (
    claim_next_task,
    clear_completed_tasks,
    complete_task,
    dag_telemetry,
    enqueue_task,
    list_tasks,
    plan_research_sprint,
)
from supermemory.research.sota_scout import register_method_card, scout_sota_papers
from supermemory.storage.sqlite_store import GraphStore


def _split_items(raw: Any, sep: str = ",") -> List[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return [x.strip() for x in str(raw or "").split(sep) if x.strip()]


@REGISTRY.register(
    name="diagnose_bottleneck",
    description="Bottleneck-First Research Engine: profile/register quantified BOTTLENECK (BNK-XXX) + falsifiable RQ-XXX, rank Pareto bottlenecks, or propose/score a single-variable hypothesis via Occam ROI Gate.",
    input_schema={
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
            "note": {"type": "string"},
            "workspace": {"type": "string"},
        },
    },
    mutates_memory=lambda args, _res: str(args.get("action") or "diagnose").lower() not in ("rank", "score_occam"),
)
def _cmd_diagnose_bottleneck(store: GraphStore, args: Dict[str, Any]) -> Dict[str, Any]:
    act = str(args.get("action") or "diagnose").lower()
    if act == "rank":
        return {"bottlenecks": rank_bottlenecks(store, include_resolved=bool(args.get("include_resolved", False)))}
    if act == "resolve":
        return {
            "resolved": resolve_bottleneck(
                store,
                bottleneck_id=str(args["bottleneck_id"]).strip(),
                resolution_exp_id=str(args.get("resolution_exp_id") or "").strip(),
                note=str(args.get("note") or "").strip(),
            )
        }
    if act == "score_occam":
        return evaluate_occam_gate(
            store,
            title=str(args.get("title") or ""),
            body=str(args.get("what_changes") or args.get("body") or args.get("evidence_slice") or ""),
            bottleneck_id=str(args.get("bottleneck_id") or ""),
            est_loc=int(args.get("est_loc") or 60),
            coupled_vars=int(args.get("coupled_vars") or 1),
            compute_cost=float(args.get("compute_cost") or 1.0),
            confidence=float(args.get("confidence") or 0.75),
            kill_criterion=str(args.get("kill_criterion") or ""),
            strict_occam=bool(args.get("strict_occam", False)),
        )
    if act == "propose_hypothesis":
        return LifecycleManager(store).create_proposal(
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
    return diagnose_bottleneck(
        store,
        title=str(args["title"]).strip(),
        evidence_slice=str(args["evidence_slice"]).strip(),
        error_share_pct=float(args["error_share_pct"]),
        ceiling_gain=float(args["ceiling_gain"]),
        falsifiable_rq=str(args["falsifiable_rq"]).strip(),
        metric_name=str(args.get("metric_name") or "primary_metric").strip(),
        baseline_value=float(args["baseline_value"]) if args.get("baseline_value") not in (None, "") else None,
        kill_criterion=str(args.get("kill_criterion") or "").strip(),
        smoke_eval_cmd=str(args.get("smoke_eval_cmd") or "").strip(),
    )


def _scout_mutated(args: Dict[str, Any], res: Dict[str, Any] | None) -> bool:
    if str(args.get("action") or "search").lower() == "register_card":
        return True
    if res is not None:
        return bool(res.get("saved_method_cards"))
    return int(args.get("save_top_k") or 0) > 0


@REGISTRY.register(
    name="scout_sota",
    description="SOTA Literature & Method Scout: search arXiv + Semantic Scholar + OpenAlex (SQLite cached) or register a structured METHOD_CARD (METH-XXX) linked to a BOTTLENECK.",
    input_schema={
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
    mutates_memory=_scout_mutated,
    is_readonly_research=lambda args, res: not _scout_mutated(args, res),
)
def _cmd_scout_sota(store: GraphStore, args: Dict[str, Any]) -> Dict[str, Any]:
    if str(args.get("action") or "search").lower() == "register_card":
        card = register_method_card(
            store,
            title=str(args["title"]).strip(),
            bottleneck_addressed=str(args.get("bottleneck_addressed") or args.get("bottleneck_id") or "Target bottleneck").strip(),
            core_mechanism=str(args["core_mechanism"]).strip(),
            assumptions_and_limits=str(args.get("assumptions_and_limits") or "Validate empirically on slice.").strip(),
            complexity_cost=str(args.get("complexity_cost") or "O(N)").strip(),
            minimal_integration_hook=str(args.get("minimal_integration_hook") or "").strip(),
            source_url=str(args.get("source_url") or "").strip(),
            venue=str(args.get("venue") or "Literature").strip(),
            year=int(args.get("year") or 2025),
            bottleneck_id=str(args.get("bottleneck_id") or "").strip(),
        )
        return {"method_card": card}
    return scout_sota_papers(
        store,
        query=str(args["query"]).strip(),
        limit=int(args.get("limit") or 6),
        min_year=int(args.get("min_year") or 2022),
        bottleneck_id=str(args.get("bottleneck_id") or "").strip(),
        save_top_k=int(args.get("save_top_k") or 0),
    )


@REGISTRY.register(
    name="orchestrate",
    description="Multi-Agent Fast-DAG & Kanban Orchestrator: plan sprints, enqueue/move tasks, toggle/add subtask steps, claim glob-locked slices, or complete tasks.",
    input_schema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["plan_sprint", "enqueue", "claim", "move", "toggle_step", "add_step", "delete", "complete", "clear_done", "status"],
                "default": "status",
            },
            "goal": {"type": "string"},
            "bottleneck_id": {"type": "string"},
            "smoke_cmd": {"type": "string", "default": "pytest -q"},
            "target_globs": {"type": "array", "items": {"type": "string"}},
            "task_id": {"type": "string"},
            "item_id": {"type": "string"},
            "kind": {"type": "string", "enum": ["TASK", "PROPOSAL"], "default": "TASK"},
            "step_idx": {"type": "integer"},
            "done": {"type": "boolean"},
            "text": {"type": "string"},
            "target_stage": {"type": "string"},
            "steps": {"type": "array", "items": {"type": "string"}},
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
    mutates_memory=lambda args, _res: str(args.get("action") or "status").lower()
    in ("plan_sprint", "enqueue", "update", "move", "toggle_step", "add_step", "complete"),
)
def _cmd_orchestrate(store: GraphStore, args: Dict[str, Any]) -> Dict[str, Any]:
    act = str(args.get("action") or "status").lower()
    kb_res = execute_kanban_orchestrate_ext(act, store, args)
    if kb_res is not None:
        return kb_res
    if act == "plan_sprint":
        globs = _split_items(args["target_globs"]) if args.get("target_globs") is not None else None
        return plan_research_sprint(
            store,
            goal=str(args["goal"]).strip(),
            bottleneck_id=str(args.get("bottleneck_id") or "").strip(),
            smoke_cmd=str(args.get("smoke_cmd") or "pytest -q").strip(),
            target_globs=globs,
        )
    if act in ("enqueue", "update"):
        raw_steps = args.get("steps")
        steps = _split_items(raw_steps, "\n") if raw_steps is not None else None
        task = enqueue_task(
            store,
            role=str(args.get("role") or "self").strip(),
            title=str(args["title"]).strip(),
            brief=str(args.get("brief") or "").strip(),
            wave=int(args.get("wave") or 1),
            depends_on=_split_items(args.get("depends_on")),
            locked_globs=_split_items(args.get("locked_globs")),
            target_id=str(args.get("bottleneck_id") or "").strip(),
            smoke_gate=str(args.get("smoke_cmd") or "").strip(),
            task_id=str(args.get("task_id") or "").strip(),
            steps=steps,
        )
        return {"task": task.to_dict()}
    if act == "claim":
        return {
            "claimed": claim_next_task(
                store,
                agent_name=str(args.get("agent_name") or "worker"),
                role=str(args.get("role") or ""),
                task_id=str(args.get("task_id") or "").strip(),
            )
        }
    if act == "clear_done":
        return {"cleared": clear_completed_tasks(store)}
    if act == "complete":
        rec = args.get("receipt") if isinstance(args.get("receipt"), dict) else {"note": str(args.get("note") or "")}
        return complete_task(store, task_id=str(args["task_id"]).strip(), status=str(args.get("status") or "DONE"), receipt=rec)
    return {"telemetry": dag_telemetry(store), "tasks": [t.to_dict() for t in list_tasks(store)]}
