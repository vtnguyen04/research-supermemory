"""Declarative Kernel Commands: Ideas, OpenSpec Proposals, Scientific Experiments, Audits & Checkpoints."""

from __future__ import annotations

from typing import Any, Dict

from supermemory.kernel.checkpoint_sync import execute_atomic_checkpoint
from supermemory.kernel.registry import REGISTRY, SCOPE_SCHEMA_PROP
from supermemory.lifecycle.manager import LifecycleManager
from supermemory.storage.sqlite_store import GraphStore
from supermemory.sync.agent_adapters import generate_handoff_briefing


@REGISTRY.register(
    name="propose_idea",
    description="Log an IDEA or ALGORITHM into Semantic/Procedural memory with Dead-End Anti-Repeat check.",
    input_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "expected_impact": {"type": "string"},
            "risks": {"type": "string"},
            "status": {"type": "string", "default": "SEED"},
            "rejection_reason": {"type": "string"},
            "is_algorithm": {"type": "boolean", "default": False},
            "invariants": {"type": "string"},
            "novelty_diff": {"type": "string"},
            "bottleneck_id": {"type": "string"},
            "workspace": {"type": "string"},
        },
        "required": ["title", "summary"],
    },
    mutates_memory=True,
)
def _cmd_propose_idea(store: GraphStore, args: Dict[str, Any]) -> Dict[str, Any]:
    return LifecycleManager(store).register_idea(
        title=str(args["title"]).strip(),
        summary=str(args["summary"]).strip(),
        expected_impact=str(args.get("expected_impact") or "").strip(),
        risks=str(args.get("risks") or "").strip(),
        status=str(args.get("status") or "SEED").strip().upper(),
        rejection_reason=str(args.get("rejection_reason") or "").strip(),
        is_algorithm=bool(args.get("is_algorithm", False)),
        invariants=str(args.get("invariants") or "").strip(),
        novelty_diff=str(args.get("novelty_diff") or "").strip(),
        bottleneck_id=str(args.get("bottleneck_id") or "").strip(),
    )


@REGISTRY.register(
    name="manage_proposal",
    description="Create or advance an OpenSpec lifecycle PROPOSAL (PROPOSED -> DESIGNED -> IMPLEMENTING -> CHALLENGED -> AUDITED -> ARCHIVED).",
    input_schema={
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["create", "advance"], "default": "create"},
            "proposal_id": {"type": "string"},
            "title": {"type": "string"},
            "why": {"type": "string"},
            "what_changes": {"type": "string"},
            "design_notes": {"type": "string"},
            "tasks": {"type": "array", "items": {"type": "string"}},
            "novelty_diff": {"type": "string"},
            "bottleneck_id": {"type": "string"},
            "kill_criterion": {"type": "string"},
            "est_loc": {"type": "integer", "default": 80},
            "coupled_vars": {"type": "integer", "default": 1},
            "strict_occam": {"type": "boolean", "default": False},
            "new_stage": {"type": "string"},
            "note": {"type": "string"},
            "workspace": {"type": "string"},
        },
    },
    mutates_memory=True,
)
def _cmd_manage_proposal(store: GraphStore, args: Dict[str, Any]) -> Dict[str, Any]:
    lm = LifecycleManager(store)
    if str(args.get("action") or "create").lower() == "advance":
        return lm.advance_proposal(
            str(args["proposal_id"]),
            str(args["new_stage"]),
            str(args.get("note") or ""),
        ).to_dict()
    raw_tasks = args.get("tasks")
    tasks = [t.strip() for t in raw_tasks.splitlines() if t.strip()] if isinstance(raw_tasks, str) else list(raw_tasks or [])
    return lm.create_proposal(
        title=str(args.get("title") or ""),
        why=str(args.get("why") or ""),
        what_changes=str(args.get("what_changes") or ""),
        design_notes=str(args.get("design_notes") or ""),
        tasks=tasks or None,
        proposal_id=str(args.get("proposal_id") or ""),
        novelty_diff=str(args.get("novelty_diff") or ""),
        bottleneck_id=str(args.get("bottleneck_id") or ""),
        kill_criterion=str(args.get("kill_criterion") or ""),
        est_loc=int(args.get("est_loc") or 80),
        coupled_vars=int(args.get("coupled_vars") or 1),
        strict_occam=bool(args.get("strict_occam", False)),
    )


@REGISTRY.register(
    name="log_experiment",
    description="Record a scientific EXPERIMENT (enforces post_mortem on failures and crystallizes insights into OBS-XXX Semantic nodes).",
    input_schema={
        "type": "object",
        "properties": {
            "track": {"type": "string", "default": "main"},
            "exp_id": {"type": "string"},
            "title": {"type": "string"},
            "hypothesis": {"type": "string"},
            "single_var_diff": {"type": "string"},
            "model_stack": {"type": "string"},
            "baseline_id": {"type": "string"},
            "proposal_id": {"type": "string"},
            "cv_score": {"type": "number"},
            "cv_summary": {"type": "string"},
            "test_score": {"type": "number"},
            "test_summary": {"type": "string"},
            "runtime_summary": {"type": "string"},
            "verdict": {"type": "string", "default": "KEEP"},
            "post_mortem": {"type": "string"},
            "insights": {"type": "array", "items": {"type": "string"}},
            "workspace": {"type": "string"},
        },
        "required": ["title", "hypothesis", "single_var_diff"],
    },
    mutates_memory=True,
)
def _cmd_log_experiment(store: GraphStore, args: Dict[str, Any]) -> Dict[str, Any]:
    cv_val = float(args["cv_score"]) if args.get("cv_score") not in (None, "") else None
    ts_val = float(args["test_score"]) if args.get("test_score") not in (None, "") else None
    raw_ins = args.get("insights") or []
    ins_list = [s.strip() for s in raw_ins.splitlines() if s.strip()] if isinstance(raw_ins, str) else list(raw_ins)
    return LifecycleManager(store).log_experiment(
        track=str(args.get("track") or "main"),
        exp_id=str(args.get("exp_id") or ""),
        title=str(args["title"]),
        hypothesis=str(args["hypothesis"]),
        single_var_diff=str(args["single_var_diff"]),
        model_stack=str(args.get("model_stack") or ""),
        baseline_id=str(args.get("baseline_id") or ""),
        proposal_id=str(args.get("proposal_id") or ""),
        cv_score=cv_val,
        cv_summary=str(args.get("cv_summary") or ""),
        test_score=ts_val,
        test_summary=str(args.get("test_summary") or ""),
        runtime_summary=str(args.get("runtime_summary") or ""),
        verdict=str(args.get("verdict") or "KEEP"),
        post_mortem=str(args.get("post_mortem") or ""),
        insights=ins_list,
    )


@REGISTRY.register(
    name="checkpoint",
    description="1-Call Atomic Turn Sync: persist insights (OBS/PROC), create/update Kanban tasks & subtask checkboxes, update L0 next_actions/phase, or attest CLEAN turn.",
    input_schema={
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["CLEAN", "CAPTURED"], "default": "CAPTURED"},
            "note": {"type": "string"},
            "insights": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of technical/empirical insights discovered this turn ('Title: detailed finding').",
            },
            "insight_title": {"type": "string"},
            "insight_summary": {"type": "string"},
            "memory_tier": {"type": "string", "enum": ["SEMANTIC", "PROCEDURAL"], "default": "SEMANTIC"},
            "new_task": {"type": "object"},
            "task_updates": {"type": "array", "items": {"type": "object"}},
            "current_phase": {"type": "string"},
            "next_actions": {"type": "string"},
            "active_goal": {"type": "string"},
            "scope": SCOPE_SCHEMA_PROP,
            "workspace": {"type": "string"},
        },
    },
    # execute_atomic_checkpoint handles selective Markdown compile (skipping disk recompile on pure CLEAN attestation)
    mutates_memory=lambda _args, res: True if res is None else False,
    fallback_to_global_if_uninit=True,
)
def _cmd_checkpoint(store: GraphStore, args: Dict[str, Any]) -> Dict[str, Any]:
    return execute_atomic_checkpoint(store, args)


@REGISTRY.register(
    name="record_audit",
    description="Record Challenger / VictoryAuditor verdict on a Proposal/Experiment, or generate HANDOFF_BRIEFING.md.",
    input_schema={
        "type": "object",
        "properties": {
            "target_id": {"type": "string"},
            "auditor_role": {"type": "string", "default": "VictoryAuditor"},
            "verdict": {"type": "string", "enum": ["APPROVE", "REQUEST_CHANGES"]},
            "findings": {"type": "string"},
            "generate_handoff": {"type": "boolean", "default": False},
            "workspace": {"type": "string"},
        },
    },
    mutates_memory=True,
)
def _cmd_record_audit(store: GraphStore, args: Dict[str, Any]) -> Dict[str, Any]:
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
    return out_res
