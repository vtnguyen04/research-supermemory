"""Research Intelligence v3.0: Bottleneck Engine, SOTA Method Scout & Fast-DAG Orchestrator."""

from __future__ import annotations

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
    complete_task,
    dag_telemetry,
    enqueue_task,
    list_tasks,
    plan_research_sprint,
)
from supermemory.research.sota_scout import register_method_card, scout_sota_papers

__all__ = [
    "add_subtask",
    "claim_next_task",
    "complete_task",
    "dag_telemetry",
    "delete_task",
    "diagnose_bottleneck",
    "enrich_execution_state",
    "enqueue_task",
    "evaluate_occam_gate",
    "list_tasks",
    "move_task_stage",
    "plan_research_sprint",
    "rank_bottlenecks",
    "register_method_card",
    "resolve_bottleneck",
    "scout_sota_papers",
    "toggle_subtask",
]
