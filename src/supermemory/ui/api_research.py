"""Web Studio v3.1 HTTP API Extensions for Bottlenecks, SOTA Vault, Fast-DAG & Kanban."""

from __future__ import annotations

from typing import Any, Dict, List

from supermemory.models import NodeType
from supermemory.research.bottleneck_engine import (
    diagnose_bottleneck,
    evaluate_occam_gate,
    rank_bottlenecks,
    resolve_bottleneck,
)
from supermemory.research.kanban_ops import (
    add_subtask,
    delete_task,
    enrich_execution_state,
    move_task_stage,
    toggle_subtask,
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
from supermemory.sync.markdown_compiler import MarkdownCompiler


def _split_list(raw: Any, sep: str = ",") -> List[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return [x.strip() for x in str(raw or "").split(sep) if x.strip()]


def enrich_graph_payload_v3(store: GraphStore, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach Bottlenecks, SOTA Method Cards, Fast-DAG tasks, and Kanban execution KPIs."""
    payload["bottlenecks"] = rank_bottlenecks(store, include_resolved=True)
    payload["method_cards"] = [
        n.to_dict() for n in store.list_nodes(node_types=[NodeType.METHOD_CARD.value], limit=200)
    ]
    tasks = [t.to_dict() for t in list_tasks(store)]
    telemetry = dag_telemetry(store)
    payload["execution_overview"] = enrich_execution_state(
        tasks,
        telemetry.get("ready_parallel_task_ids", []),
        payload.get("nodes", []),
    )
    payload["agent_tasks"] = tasks
    payload["dag_telemetry"] = telemetry
    return payload


def dispatch_research_mutation(route: str, store: GraphStore, body: Dict[str, Any]) -> Dict[str, Any] | None:
    """Handle POST `/api/bottlenecks`, `/api/scout`, and `/api/orchestrate`."""
    if route == "/api/bottlenecks":
        act = str(body.get("action") or "diagnose").lower()
        if act == "resolve":
            out = resolve_bottleneck(
                store,
                bottleneck_id=str(body["bottleneck_id"]).strip(),
                resolution_exp_id=str(body.get("resolution_exp_id") or "").strip(),
                note=str(body.get("note") or "").strip(),
            )
            MarkdownCompiler(store).compile_all()
            return {"resolved": out}
        if act == "score_occam":
            return evaluate_occam_gate(
                store,
                title=str(body.get("title") or ""),
                body=str(body.get("body") or ""),
                bottleneck_id=str(body.get("bottleneck_id") or ""),
                est_loc=int(body.get("est_loc") or 60),
                coupled_vars=int(body.get("coupled_vars") or 1),
                kill_criterion=str(body.get("kill_criterion") or ""),
                strict_occam=bool(body.get("strict_occam", False)),
            )
        res = diagnose_bottleneck(
            store,
            title=str(body["title"]).strip(),
            evidence_slice=str(body["evidence_slice"]).strip(),
            error_share_pct=float(body["error_share_pct"]),
            ceiling_gain=float(body["ceiling_gain"]),
            falsifiable_rq=str(body["falsifiable_rq"]).strip(),
            metric_name=str(body.get("metric_name") or "primary_metric").strip(),
            baseline_value=float(body["baseline_value"]) if body.get("baseline_value") not in (None, "") else None,
            kill_criterion=str(body.get("kill_criterion") or "").strip(),
            smoke_eval_cmd=str(body.get("smoke_eval_cmd") or "").strip(),
        )
        MarkdownCompiler(store).compile_all()
        return res

    if route == "/api/scout":
        act = str(body.get("action") or "search").lower()
        if act == "register_card":
            card = register_method_card(
                store,
                title=str(body["title"]).strip(),
                bottleneck_addressed=str(body.get("bottleneck_addressed") or body.get("bottleneck_id") or "Target bottleneck").strip(),
                core_mechanism=str(body["core_mechanism"]).strip(),
                assumptions_and_limits=str(body.get("assumptions_and_limits") or "Validate empirically on slice.").strip(),
                complexity_cost=str(body.get("complexity_cost") or "O(N)").strip(),
                minimal_integration_hook=str(body.get("minimal_integration_hook") or "").strip(),
                source_url=str(body.get("source_url") or "").strip(),
                venue=str(body.get("venue") or "SOTA").strip(),
                year=int(body.get("year") or 2025),
                bottleneck_id=str(body.get("bottleneck_id") or "").strip(),
            )
            MarkdownCompiler(store).compile_all()
            return {"method_card": card}
        res = scout_sota_papers(
            store,
            query=str(body["query"]).strip(),
            limit=int(body.get("limit") or 6),
            min_year=int(body.get("min_year") or 2022),
            bottleneck_id=str(body.get("bottleneck_id") or "").strip(),
            save_top_k=int(body.get("save_top_k") or 0),
        )
        if res["saved_method_cards"]:
            MarkdownCompiler(store).compile_all()
        return res

    if route == "/api/orchestrate":
        act = str(body.get("action") or "plan_sprint").lower()
        if act == "plan_sprint":
            res = plan_research_sprint(
                store,
                goal=str(body["goal"]).strip(),
                bottleneck_id=str(body.get("bottleneck_id") or "").strip(),
                smoke_cmd=str(body.get("smoke_cmd") or "pytest -q").strip(),
                target_globs=_split_list(body.get("target_globs") or "src/**"),
            )
            MarkdownCompiler(store).compile_all()
            return res
        if act in ("enqueue", "update"):
            raw_steps = body.get("steps")
            steps = _split_list(raw_steps, "\n") if raw_steps is not None else None
            task = enqueue_task(
                store,
                role=str(body.get("role") or "self").strip(),
                title=str(body["title"]).strip(),
                brief=str(body.get("brief") or "").strip(),
                wave=int(body.get("wave") or 1),
                depends_on=_split_list(body.get("depends_on")),
                locked_globs=_split_list(body.get("locked_globs")),
                target_id=str(body.get("bottleneck_id") or "").strip(),
                smoke_gate=str(body.get("smoke_cmd") or "").strip(),
                task_id=str(body.get("task_id") or "").strip(),
                steps=steps,
            )
            MarkdownCompiler(store).compile_all()
            return {"task": task.to_dict()}
        if act == "claim":
            return {
                "claimed": claim_next_task(
                    store,
                    agent_name=str(body.get("agent_name") or "ui-worker"),
                    role=str(body.get("role") or ""),
                    task_id=str(body.get("task_id") or "").strip(),
                )
            }
        if act == "move":
            out = move_task_stage(
                store,
                task_id=str(body["task_id"]).strip(),
                target_stage=str(body["target_stage"]).strip(),
                agent_name=str(body.get("agent_name") or "studio"),
            )
            MarkdownCompiler(store).compile_all()
            return out
        if act == "toggle_step":
            done_val = body.get("done")
            out = toggle_subtask(
                store,
                item_kind=str(body.get("kind") or "TASK"),
                item_id=str(body["item_id"]).strip(),
                step_idx=int(body["step_idx"]),
                done=bool(done_val) if done_val is not None else None,
            )
            MarkdownCompiler(store).compile_all()
            return out
        if act == "add_step":
            out = add_subtask(
                store,
                item_kind=str(body.get("kind") or "TASK"),
                item_id=str(body["item_id"]).strip(),
                text=str(body["text"]).strip(),
            )
            MarkdownCompiler(store).compile_all()
            return out
        if act == "delete":
            deleted = delete_task(store, task_id=str(body["task_id"]).strip())
            MarkdownCompiler(store).compile_all()
            return {"deleted": deleted}
        if act == "clear_done":
            return {"cleared": clear_completed_tasks(store)}
        if act == "complete":
            receipt = body.get("receipt") if isinstance(body.get("receipt"), dict) else {"note": str(body.get("note") or "")}
            res = complete_task(store, task_id=str(body["task_id"]).strip(), status=str(body.get("status") or "DONE"), receipt=receipt)
            MarkdownCompiler(store).compile_all()
            return res
        return {"telemetry": dag_telemetry(store), "tasks": [t.to_dict() for t in list_tasks(store)]}

    return None
