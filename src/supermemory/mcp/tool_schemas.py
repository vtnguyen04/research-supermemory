"""MCP JSON Schema definitions for SuperMemory tools."""

from __future__ import annotations

from typing import Any, Dict, List

MCP_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "supermemory_init",
        "description": "Initialize SuperMemory Knowledge Graph, Universal Laws, Gates, and Agent Rules in a workspace.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workspace": {"type": "string", "description": "Workspace path (defaults to current working directory)."},
                "project_name": {"type": "string"},
                "max_lines": {"type": "integer", "default": 300},
            },
        },
    },
    {
        "name": "supermemory_status",
        "description": "Return live Active State capsule, Constitutional Laws, Gate block stats, and recent Experiments.",
        "inputSchema": {
            "type": "object",
            "properties": {"workspace": {"type": "string"}},
        },
    },
    {
        "name": "supermemory_recall",
        "description": "Hybrid BM25 + 2-hop Knowledge Graph search & Anti-Repeat Dead-End check before proposing or coding.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Topic, module, error, or hypothesis to search."},
                "hops": {"type": "integer", "default": 1},
                "workspace": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "supermemory_record_lesson",
        "description": "Self-learning commit: record a mistake/user correction, consolidate into a LAW, and optionally bind a PreToolUse CodeGate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "mistake": {"type": "string"},
                "root_cause": {"type": "string"},
                "prevention_rule": {"type": "string"},
                "user_quote": {"type": "string"},
                "law_id": {"type": "string", "description": "Target LAW ID (e.g. LAW-01) or omit to auto-match."},
                "forbid_regex": {"type": "string", "description": "Optional source code regex to hard-block in PreToolUse."},
                "target_glob": {"type": "string", "default": "**/*.py"},
                "forbid_cmd_regex": {"type": "string", "description": "Optional shell command regex to hard-block."},
                "workspace": {"type": "string"},
            },
            "required": ["title", "mistake", "root_cause", "prevention_rule"],
        },
    },
    {
        "name": "supermemory_add_gate",
        "description": "Register an executable CodeGate (MAX_LINES, FORBIDDEN_REGEX, FORBIDDEN_FILENAME, FROZEN_SHA256, FORBIDDEN_CMD_PATTERN).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "gate_type": {"type": "string"},
                "name": {"type": "string"},
                "law_id": {"type": "string", "default": "LAW-08"},
                "target_glob": {"type": "string", "default": "**/*.py"},
                "pattern": {"type": "string"},
                "freeze_path": {"type": "string", "description": "If set, freezes SHA-256 of this file path."},
                "workspace": {"type": "string"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "supermemory_propose_idea",
        "description": "Log an IDEA or ALGORITHM into the vault (with automatic check against prior rejected dead-ends).",
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
                "workspace": {"type": "string"},
            },
            "required": ["title", "summary"],
        },
    },
    {
        "name": "supermemory_manage_proposal",
        "description": "Create or advance an OpenSpec-grade lifecycle PROPOSAL (PROPOSED -> DESIGNED -> IMPLEMENTING -> CHALLENGED -> AUDITED -> ARCHIVED).",
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
                "new_stage": {"type": "string"},
                "note": {"type": "string"},
                "workspace": {"type": "string"},
            },
        },
    },
    {
        "name": "supermemory_log_experiment",
        "description": "Record a scientific EXPERIMENT (hypothesis, single-variable diff, CV/Test metrics, baseline delta, post-mortem) and sync registry.",
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
                "workspace": {"type": "string"},
            },
            "required": ["title", "hypothesis", "single_var_diff"],
        },
    },
    {
        "name": "supermemory_update_state",
        "description": "Atomically update 01_ACTIVE_STATE.md goals, phase, targets, next actions, and sync Markdown + JSON snapshot.",
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
        "name": "supermemory_link_knowledge",
        "description": "Upsert a KNOWLEDGE_NODE / OBSERVATION and/or link two graph entities with a typed directed edge.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "node_type": {"type": "string", "default": "KNOWLEDGE_NODE"},
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "content": {"type": "string"},
                "source_id": {"type": "string"},
                "target_id": {"type": "string"},
                "relation": {"type": "string", "default": "REFERENCES"},
                "workspace": {"type": "string"},
            },
        },
    },
    {
        "name": "supermemory_audit_gates",
        "description": "Run all active Constitutional CodeGates across the workspace and return violations.",
        "inputSchema": {
            "type": "object",
            "properties": {"workspace": {"type": "string"}},
        },
    },
    {
        "name": "supermemory_record_audit",
        "description": "Record Challenger / Victory Auditor verdict on a Proposal or Experiment, or generate HANDOFF_BRIEFING.md.",
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
]
