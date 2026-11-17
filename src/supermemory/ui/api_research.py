"""Thin Web Studio HTTP Adapter for Bottlenecks, SOTA Vault, Fast-DAG & Kanban (`kernel`-backed)."""

from __future__ import annotations

from typing import Any, Dict

from supermemory.cognitive.outcome_ledger import infer_metric_direction
from supermemory.kernel import execute_command
from supermemory.models import NodeType
from supermemory.research.bottleneck_engine import rank_bottlenecks
from supermemory.research.kanban_ops import enrich_execution_state
from supermemory.research.orchestrator import dag_telemetry, list_tasks
from supermemory.storage.sqlite_store import GraphStore

_RESEARCH_ROUTE_TO_CMD = {
    "/api/bottlenecks": "diagnose_bottleneck",
    "/api/scout": "scout_sota",
    "/api/orchestrate": "orchestrate",
}


def enrich_graph_payload_v3(store: GraphStore, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach Bottlenecks, SOTA Method Cards, Fast-DAG tasks, Kanban KPIs, and metric direction."""
    payload["bottlenecks"] = rank_bottlenecks(store, include_resolved=True)
    payload["method_cards"] = [
        n.to_dict() for n in store.list_nodes(node_types=[NodeType.METHOD_CARD.value], limit=200)
    ]
    tracks = {e.track for e in store.list_experiments() if e.track}
    payload["metric_direction"] = infer_metric_direction(store)
    payload["metric_direction_by_track"] = {tr: infer_metric_direction(store, track=tr) for tr in tracks}
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
    """Delegate `/api/bottlenecks`, `/api/scout`, and `/api/orchestrate` to the shared Kernel."""
    cmd_name = _RESEARCH_ROUTE_TO_CMD.get(route)
    if not cmd_name:
        return None
    payload = dict(body)
    if route == "/api/orchestrate" and "action" not in payload:
        payload["action"] = "plan_sprint"
    return execute_command(cmd_name, payload, store=store)
