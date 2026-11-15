"""Web Studio v3.0 HTTP API Extensions for Bottlenecks, SOTA Method Vault & Multi-Agent DAG."""

from __future__ import annotations

from typing import Any, Dict

from supermemory.models import NodeType
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
from supermemory.storage.sqlite_store import GraphStore
from supermemory.sync.markdown_compiler import MarkdownCompiler


def enrich_graph_payload_v3(store: GraphStore, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach Pareto Bottlenecks, SOTA Method Cards, and Multi-Agent Fast-DAG state to `/api/graph`."""
    payload["bottlenecks"] = rank_bottlenecks(store, include_resolved=True)
    payload["method_cards"] = [
        n.to_dict() for n in store.list_nodes(node_types=[NodeType.METHOD_CARD.value], limit=200)
    ]
    payload["agent_tasks"] = [t.to_dict() for t in list_tasks(store)]
    payload["dag_telemetry"] = dag_telemetry(store)
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
            raw_globs = body.get("target_globs") or "src/**"
            globs = [g.strip() for g in raw_globs.split(",") if g.strip()] if isinstance(raw_globs, str) else list(raw_globs)
            res = plan_research_sprint(
                store,
                goal=str(body["goal"]).strip(),
                bottleneck_id=str(body.get("bottleneck_id") or "").strip(),
                smoke_cmd=str(body.get("smoke_cmd") or "pytest -q").strip(),
                target_globs=globs,
            )
            MarkdownCompiler(store).compile_all()
            return res
        if act == "enqueue":
            raw_deps = body.get("depends_on") or ""
            deps = [d.strip() for d in raw_deps.split(",") if d.strip()] if isinstance(raw_deps, str) else list(raw_deps)
            raw_lk = body.get("locked_globs") or ""
            lk = [g.strip() for g in raw_lk.split(",") if g.strip()] if isinstance(raw_lk, str) else list(raw_lk)
            task = enqueue_task(
                store,
                role=str(body.get("role") or "self").strip(),
                title=str(body["title"]).strip(),
                brief=str(body.get("brief") or "").strip(),
                wave=int(body.get("wave") or 1),
                depends_on=deps,
                locked_globs=lk,
                target_id=str(body.get("bottleneck_id") or "").strip(),
                smoke_gate=str(body.get("smoke_cmd") or "").strip(),
            )
            MarkdownCompiler(store).compile_all()
            return {"task": task.to_dict()}
        if act == "claim":
            return {"claimed": claim_next_task(store, agent_name=str(body.get("agent_name") or "ui-worker"), role=str(body.get("role") or ""))}
        if act == "complete":
            receipt = body.get("receipt") if isinstance(body.get("receipt"), dict) else {"note": str(body.get("note") or "")}
            res = complete_task(store, task_id=str(body["task_id"]).strip(), status=str(body.get("status") or "DONE"), receipt=receipt)
            MarkdownCompiler(store).compile_all()
            return res
        return {"telemetry": dag_telemetry(store), "tasks": [t.to_dict() for t in list_tasks(store)]}

    return None
