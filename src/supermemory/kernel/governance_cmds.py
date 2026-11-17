"""Declarative Kernel Commands: Workspace Init, Status, Constitutional Lessons & CodeGates."""

from __future__ import annotations

from typing import Any, Dict

from supermemory.bootstrap import init_workspace
from supermemory.cognitive.federation import (
    ensure_global_memory,
    list_registered_workspaces,
    resolve_default_workspace,
)
from supermemory.cognitive.tiers import build_tiered_capsule, compute_tier_telemetry
from supermemory.gates.enforcer import GateEnforcer
from supermemory.graph.query_engine import QueryEngine
from supermemory.kernel.registry import REGISTRY, SCOPE_SCHEMA_PROP
from supermemory.models import CodeGate
from supermemory.self_learning.consolidator import LessonConsolidator
from supermemory.storage.sqlite_store import GraphStore


@REGISTRY.register(
    name="init",
    description="Initialize isolated Local SuperMemory in a project folder and register it in Global workspaces.",
    input_schema={
        "type": "object",
        "properties": {
            "workspace": {"type": "string"},
            "project_name": {"type": "string"},
            "max_lines": {"type": "integer", "default": 500},
            "active_goal": {"type": "string"},
        },
    },
    requires_store=False,
    mutates_memory=False,
)
def _cmd_init(args: Dict[str, Any]) -> Dict[str, Any]:
    raw_ws = resolve_default_workspace(str(args.get("workspace") or ""))
    return init_workspace(
        raw_ws,
        project_name=str(args.get("project_name") or raw_ws.name),
        max_lines=int(args.get("max_lines") or 500),
        active_goal=str(args.get("active_goal") or ""),
    )


@REGISTRY.register(
    name="status",
    description="Return 4-Tier Cognitive Capsule (Working/Procedural/Semantic/Episodic), token budget stats, and workspaces.",
    input_schema={"type": "object", "properties": {"workspace": {"type": "string"}, "scope": SCOPE_SCHEMA_PROP}},
    mutates_memory=False,
    fallback_to_global_if_uninit=True,
)
def _cmd_status(store: GraphStore, _args: Dict[str, Any]) -> Dict[str, Any]:
    qe = QueryEngine(store)
    return {
        "scope": "global" if store.workspace_root == ensure_global_memory() else "local",
        "capsule": build_tiered_capsule(store),
        "analytics": qe.graph_analytics(),
        "cognitive_tiers": compute_tier_telemetry(store),
        "workspaces": list_registered_workspaces(),
    }


@REGISTRY.register(
    name="record_lesson",
    description="Autonomous self-learning commit: record any critique, mistake, or new user rule into Local or Global LAW + CodeGate.",
    input_schema={
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "mistake": {"type": "string"},
            "root_cause": {"type": "string"},
            "prevention_rule": {"type": "string"},
            "user_quote": {"type": "string"},
            "law_id": {"type": "string"},
            "new_law_title": {"type": "string"},
            "forbid_regex": {"type": "string"},
            "target_glob": {"type": "string", "default": "**/*.py"},
            "forbid_cmd_regex": {"type": "string"},
            "scope": SCOPE_SCHEMA_PROP,
            "workspace": {"type": "string"},
        },
        "required": ["title", "mistake", "root_cause", "prevention_rule"],
    },
    mutates_memory=True,
    clears_lesson_lock=True,
)
def _cmd_record_lesson(store: GraphStore, args: Dict[str, Any]) -> Dict[str, Any]:
    return LessonConsolidator(store).record_lesson(
        title=str(args["title"]).strip(),
        mistake=str(args["mistake"]).strip(),
        root_cause=str(args["root_cause"]).strip(),
        prevention_rule=str(args["prevention_rule"]).strip(),
        user_quote=str(args.get("user_quote") or "").strip(),
        law_id=str(args.get("law_id") or "").strip(),
        new_law_title=str(args.get("new_law_title") or "").strip(),
        forbid_regex=str(args.get("forbid_regex") or "").strip(),
        target_glob=str(args.get("target_glob") or "**/*.py").strip(),
        forbid_cmd_regex=str(args.get("forbid_cmd_regex") or "").strip(),
        source_exp_id=str(args.get("source_exp_id") or "").strip(),
    )


@REGISTRY.register(
    name="add_gate",
    description="Register an executable PreToolUse CodeGate (MAX_LINES, FORBIDDEN_REGEX, FROZEN_SHA256, FORBIDDEN_CMD_PATTERN, CHANGELOG_SYNC).",
    input_schema={
        "type": "object",
        "properties": {
            "gate_type": {"type": "string"},
            "name": {"type": "string"},
            "law_id": {"type": "string", "default": "LAW-08"},
            "target_glob": {"type": "string", "default": "**/*.py"},
            "pattern": {"type": "string"},
            "freeze_path": {"type": "string"},
            "scope": SCOPE_SCHEMA_PROP,
            "workspace": {"type": "string"},
        },
        "required": ["name"],
    },
    mutates_memory=True,
    clears_lesson_lock=True,
)
def _cmd_add_gate(store: GraphStore, args: Dict[str, Any]) -> Dict[str, Any]:
    enf = GateEnforcer(store)
    if args.get("freeze_path"):
        gate = enf.freeze_file(str(args["freeze_path"]).strip(), law_id=str(args.get("law_id") or "LAW-05"))
    else:
        gid = str(args.get("id") or "").strip() or LessonConsolidator(store).next_gate_id()
        gtype = str(args.get("gate_type") or "FORBIDDEN_REGEX").upper()
        cfg = {"max_lines": int(args.get("max_lines") or 500)} if gtype == "MAX_LINES" else {"ignore_comments": True}
        gate = store.upsert_gate(
            CodeGate(
                id=gid,
                gate_type=gtype,
                name=str(args["name"]).strip(),
                law_id=str(args.get("law_id") or "LAW-08").strip(),
                target_glob=str(args.get("target_glob") or "**/*.py").strip(),
                pattern=str(args.get("pattern") or "").strip(),
                config=cfg,
            )
        )
        store.log_event("GATE_UPSERTED", gid, f"[{gtype}] {gate.name} -> {gate.target_glob}")
    return gate.to_dict()


@REGISTRY.register(
    name="audit_gates",
    description="Run all active Constitutional CodeGates across the workspace and return violations.",
    input_schema={"type": "object", "properties": {"workspace": {"type": "string"}}},
    mutates_memory=False,
)
def _cmd_audit_gates(store: GraphStore, _args: Dict[str, Any]) -> Dict[str, Any]:
    return GateEnforcer(store).audit_workspace(log_audit=True)
