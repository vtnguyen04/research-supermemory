"""Declarative Kernel Commands: Workspace Init, Status, Constitutional Lessons & CodeGates."""

from __future__ import annotations

import re
from typing import Any, Dict

from supermemory.bootstrap import init_workspace
from supermemory.cognitive.federation import (
    ensure_global_memory,
    list_registered_workspaces,
    resolve_default_workspace,
)
from supermemory.cognitive.tiers import build_tiered_capsule, compute_tier_telemetry
from supermemory.gates.enforcer import GateEnforcer
from supermemory.gates.sim_helpers import validate_regex_pattern
from supermemory.graph.query_engine import QueryEngine
from supermemory.kernel.registry import REGISTRY, SCOPE_SCHEMA_PROP
from supermemory.models import CodeGate, EdgeType, MemoryEdge, MemoryNode, NodeType
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
        if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$", gid):
            raise ValueError(f"Invalid `gate_id`: `{gid}`")
        existing_g = next((x for x in store.list_gates() if x.id == gid), None)
        gtype = str(args.get("gate_type") or (existing_g.gate_type if existing_g else "FORBIDDEN_REGEX")).upper()
        pat = str(args.get("pattern") if args.get("pattern") is not None else (existing_g.pattern if existing_g else "")).strip()
        if gtype in ("FORBIDDEN_REGEX", "FORBIDDEN_CMD_PATTERN", "FORBIDDEN_FILENAME"):
            pat = validate_regex_pattern(pat, "pattern")
        prev_cfg = dict(existing_g.config) if existing_g else {}
        if gtype == "MAX_LINES":
            raw_ml = args.get("max_lines") if args.get("max_lines") is not None else (pat if pat.isdigit() else prev_cfg.get("max_lines", 500))
            ml_val = int(str(raw_ml if raw_ml is not None else 500))
            if ml_val <= 0:
                raise ValueError("`max_lines` must be > 0.")
            cfg = {**prev_cfg, "max_lines": ml_val}
            pat = str(ml_val)
        else:
            cfg = {**{"ignore_comments": True}, **prev_cfg}
        law_id = str(args.get("law_id") or (existing_g.law_id if existing_g else "LAW-08")).strip()
        gate = store.upsert_gate(
            CodeGate(
                id=gid,
                gate_type=gtype,
                name=str(args["name"]).strip(),
                law_id=law_id,
                lesson_id=existing_g.lesson_id if existing_g else "",
                target_glob=str(args.get("target_glob") or (existing_g.target_glob if existing_g else "**/*.py")).strip(),
                pattern=pat,
                config=cfg,
                enabled=existing_g.enabled if existing_g else True,
                blocked_count=existing_g.blocked_count if existing_g else 0,
            )
        )
        store.upsert_node(
            MemoryNode(
                id=gid,
                node_type=NodeType.GATE.value,
                title=gate.name,
                summary=f"[{gtype}] `{gate.target_glob}` -> `{gate.pattern}`",
                tags=["gate", law_id.lower()],
                priority=95,
                metadata=gate.to_dict(),
            ),
            log_event=False,
        )
        if law_id and store.get_node(law_id):
            store.add_edge(MemoryEdge(source_id=law_id, target_id=gid, relation=EdgeType.ENFORCED_BY.value))
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
