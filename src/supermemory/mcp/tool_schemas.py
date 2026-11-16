"""MCP JSON Schema definitions for SuperMemory v2.0 (Tiered & Federated)."""

from __future__ import annotations

from typing import Any, Dict, List

from supermemory.mcp.research_tools import RESEARCH_MCP_TOOLS

_SCOPE_PROP = {
    "type": "string",
    "enum": ["local", "global"],
    "default": "local",
    "description": "Target 'local' project SuperMemory or 'global' (~/.supermemory/global).",
}

MCP_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "init",
        "description": "Initialize isolated Local SuperMemory in a project folder and register it in Global workspaces.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string"},
                "project_name": {"type": "string"},
                "max_lines": {"type": "integer", "default": 300},
            },
        },
    },
    {
        "name": "status",
        "description": "Return 4-Tier Cognitive Capsule (Working/Procedural/Semantic/Episodic), token budget stats, and workspaces.",
        "inputSchema": {
            "type": "object",
            "properties": {"workspace": {"type": "string"}, "scope": _SCOPE_PROP},
        },
    },
    {
        "name": "recall",
        "description": "2-Stage Progressive Recall: Stage-1 compact index search (`query`) or Stage-2 full node expansion (`node_id`).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "default": ""},
                "node_id": {"type": "string", "description": "Optional Stage-2 ID (e.g. METH-001, OBS-001) to fetch full content."},
                "limit": {"type": "integer", "default": 6},
                "hops": {"type": "integer", "default": 1},
                "compact": {"type": "boolean", "default": True},
                "include_global": {"type": "boolean", "default": True},
                "include_siblings": {"type": "boolean", "default": False},
                "workspace": {"type": "string"},
            },
        },
    },
    {
        "name": "record_lesson",
        "description": "Autonomous self-learning commit: record any critique, mistake, or new user rule into Local or Global LAW + CodeGate.",
        "inputSchema": {
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
                "scope": _SCOPE_PROP,
                "workspace": {"type": "string"},
            },
            "required": ["title", "mistake", "root_cause", "prevention_rule"],
        },
    },
    {
        "name": "add_gate",
        "description": "Register an executable PreToolUse CodeGate (MAX_LINES, FORBIDDEN_REGEX, FROZEN_SHA256, FORBIDDEN_CMD_PATTERN).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "gate_type": {"type": "string"},
                "name": {"type": "string"},
                "law_id": {"type": "string", "default": "LAW-08"},
                "target_glob": {"type": "string", "default": "**/*.py"},
                "pattern": {"type": "string"},
                "freeze_path": {"type": "string"},
                "scope": _SCOPE_PROP,
                "workspace": {"type": "string"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "propose_idea",
        "description": "Log an IDEA or ALGORITHM into Semantic/Procedural memory with Dead-End Anti-Repeat check.",
        "inputSchema": {
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
                "workspace": {"type": "string"},
            },
            "required": ["title", "summary"],
        },
    },
    {
        "name": "manage_proposal",
        "description": "Create or advance an OpenSpec lifecycle PROPOSAL (PROPOSED -> DESIGNED -> IMPLEMENTING -> CHALLENGED -> AUDITED -> ARCHIVED).",
        "inputSchema": {
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
    },
    {
        "name": "log_experiment",
        "description": "Record a scientific EXPERIMENT (enforces post_mortem on failures and crystallizes insights into OBS-XXX Semantic nodes).",
        "inputSchema": {
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
    },
    {
        "name": "update_state",
        "description": "Atomically update L0 Working State (01_ACTIVE_STATE.md), Agent Rules, and Snapshot.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "active_goal": {"type": "string"},
                "current_phase": {"type": "string"},
                "primary_targets": {"type": "string"},
                "next_actions": {"type": "string"},
                "state_notes": {"type": "string"},
                "workspace": {"type": "string"},
            },
        },
    },
    {
        "name": "link_knowledge",
        "description": "Upsert a PROCEDURAL (PROCEDURE) or SEMANTIC (KNOWLEDGE_NODE / OBSERVATION) entity and/or typed edge.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "node_type": {"type": "string", "default": "KNOWLEDGE_NODE"},
                "memory_tier": {"type": "string", "enum": ["PROCEDURAL", "SEMANTIC", "EPISODIC"]},
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "content": {"type": "string"},
                "source_id": {"type": "string"},
                "target_id": {"type": "string"},
                "relation": {"type": "string", "default": "REFERENCES"},
                "scope": _SCOPE_PROP,
                "workspace": {"type": "string"},
            },
        },
    },
    {
        "name": "consolidate",
        "description": "Consolidate/merge Episodic nodes into compact Semantic/Procedural memory, auto-compact tracks, or promote Local -> Global.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["merge", "auto", "promote"], "default": "merge"},
                "source_ids": {"type": "array", "items": {"type": "string"}},
                "target_tier": {"type": "string", "enum": ["SEMANTIC", "PROCEDURAL"], "default": "SEMANTIC"},
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "content": {"type": "string"},
                "promote_node_id": {"type": "string"},
                "workspace": {"type": "string"},
            },
        },
    },
    {
        "name": "checkpoint",
        "description": "1-Call Atomic Turn Sync: persist insights (OBS/PROC), create/update Kanban tasks & subtask checkboxes, update L0 next_actions/phase, or attest CLEAN turn.",
        "inputSchema": {
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
                "new_task": {
                    "type": "object",
                    "description": "Optional Kanban task to create: {title, steps: [...], stage: 'IN_PROGRESS'|'READY'|'DONE', role}.",
                },
                "task_updates": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of Kanban/Proposal updates: [{id: 'DAG-001'|'PROP-001', done_steps: [0,1], add_steps: ['...'], stage: 'IN_PROGRESS'|'DONE'}].",
                },
                "current_phase": {"type": "string"},
                "next_actions": {"type": "string"},
                "active_goal": {"type": "string"},
                "scope": _SCOPE_PROP,
                "workspace": {"type": "string"},
            },
        },
    },
    {
        "name": "audit_gates",
        "description": "Run all active Constitutional CodeGates across the workspace and return violations.",
        "inputSchema": {"type": "object", "properties": {"workspace": {"type": "string"}}},
    },
    {
        "name": "record_audit",
        "description": "Record Challenger / VictoryAuditor verdict on a Proposal/Experiment, or generate HANDOFF_BRIEFING.md.",
        "inputSchema": {
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
    },
    *RESEARCH_MCP_TOOLS,
]
