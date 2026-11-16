"""End-to-end tests for SuperMemory v3.2.1 Notification Bus, Domain-Agnostic Tracking & Schema/Task Gates."""

from __future__ import annotations

from pathlib import Path

import pytest

from supermemory.bootstrap import init_workspace
from supermemory.cognitive.tiers import build_tiered_capsule
from supermemory.hooks.runner import dispatch_hook
from supermemory.mcp.tool_defs import execute_mcp_tool
from supermemory.self_learning.detector import SelfLearningDetector
from supermemory.storage.sqlite_store import GraphStore


def test_diagnostic_question_never_triggers_false_positive_lesson() -> None:
    sig = SelfLearningDetector.analyze(
        "có hardcode ngu ngu gì khong đó?? quan trọng là như 1 notification cho AI nó biết lúc nào cần save đồ không?"
    )
    assert sig.requires_lesson is False
    assert sig.category == "NONE"


def test_inflight_notifications_and_domain_agnostic_tracking(tmp_path: Path) -> None:
    ws = tmp_path / "proj"
    init_workspace(ws, project_name="NotifyProj")

    # 1. Pure Q&A + read-only shell commands (`git status`, `ls`) -> 0 notifications, 0 Stop blocks
    dispatch_hook("PreInvocation", {"conversationId": "c1", "cwd": str(ws), "lastUserInput": "check repo status"})
    ro_out = dispatch_hook(
        "PostToolUse",
        {"conversationId": "c1", "cwd": str(ws), "toolCall": {"name": "run_command", "args": {"CommandLine": "git status && ls -la"}}, "output": "On branch main"},
    )
    assert ro_out == {}
    assert dispatch_hook("Stop", {"conversationId": "c1", "cwd": str(ws), "terminationReason": "NO_TOOL_CALL"})["decision"] == "allow"

    # 2. Create a structured Proposal with 2 concrete Task List steps
    prop = execute_mcp_tool(
        "manage_proposal",
        {
            "workspace": str(ws),
            "action": "create",
            "title": "Adaptive Coil Ramp Damping",
            "why": "Step-0 coil jump accounts for 62% of morning comfort regret.",
            "what_changes": "Add rate-limited coil valve ramp in src/policy.py.",
            "tasks": ["Implement rate-limited ramp in src/policy.py", "Verify on 16-scenario validation suite"],
        },
    )
    pid = prop["proposal_id"]

    # 3. Editing src/policy.py emits an immediate In-Flight Notification naming PROP-001 & Next step #[0]!
    dispatch_hook("PreInvocation", {"conversationId": "c1", "cwd": str(ws), "lastUserInput": "start working"})
    (ws / "src").mkdir()
    target_py = ws / "src" / "policy.py"
    target_py.write_text("x = 1\n", encoding="utf-8")

    edit_notif = dispatch_hook(
        "PostToolUse",
        {
            "hook_event_name": "PostToolUse",
            "session_id": "c1",
            "cwd": str(ws),
            "tool_name": "Write",
            "tool_input": {"file_path": str(target_py), "content": "x = 2\n"},
        },
    )
    ctx_msg = edit_notif["hookSpecificOutput"]["additionalContext"]
    assert "Task-List Notification" in ctx_msg
    assert pid in ctx_msg
    assert "#[0]" in ctx_msg

    # 4. Domain-agnostic custom command (`./bin/run_custom_rust_sim --seed 7`, zero 'train/mse' keywords!) emits Save Notification
    exec_notif = dispatch_hook(
        "PostToolUse",
        {
            "conversationId": "c2",
            "cwd": str(ws),
            "toolCall": {"name": "run_command", "args": {"CommandLine": "./bin/run_custom_rust_sim --seed 7"}},
            "output": "SharpeRatio = 2.41, MaxDrawdown = -4.2%",
        },
    )
    assert "Save Notification" in exec_notif["injectSteps"][0]["systemMessage"]["systemMessage"]
    stop_exec = dispatch_hook("Stop", {"conversationId": "c2", "cwd": str(ws), "terminationReason": "NO_TOOL_CALL"})
    assert stop_exec["decision"] == "continue"
    assert "RESULT & INSIGHT SYNC REQUIRED" in stop_exec["reason"]


def test_strict_proposal_insight_experiment_and_task_list_gates(tmp_path: Path) -> None:
    ws = tmp_path / "proj_strict"
    init_workspace(ws, project_name="StrictProj")

    # 1. Sloppy Proposal rejected
    with pytest.raises(ValueError, match="Proposal Schema Gate"):
        execute_mcp_tool("manage_proposal", {"workspace": str(ws), "action": "create", "title": "Untitled Proposal", "why": "short", "what_changes": "x"})

    # 2. Lazy 2-word insight rejected
    with pytest.raises(ValueError, match="Insight Schema Gate"):
        execute_mcp_tool("checkpoint", {"workspace": str(ws), "insights": ["fixed bug"]})

    # 3. Hollow experiment without any metric rejected
    with pytest.raises(ValueError, match="Experiment Schema Gate"):
        execute_mcp_tool("log_experiment", {"workspace": str(ws), "title": "Valid Title", "hypothesis": "Valid falsifiable hypothesis", "single_var_diff": "Changed alpha 0.1->0.2"})

    # 4. Sequential Task-List Gate: cannot mark Proposal or Kanban Task DONE while steps remain unchecked!
    res1 = execute_mcp_tool(
        "checkpoint",
        {
            "workspace": str(ws),
            "insights": ["Wakeup Spike Root Cause: 62% of morning regret comes from unmasked step-0 coil jump."],
            "new_task": {
                "title": "Dampen step-0 coil wakeup jump",
                "steps": ["Add ramp limiter in policy.py", "Verify on val16 suite"],
                "stage": "IN_PROGRESS",
            },
        },
    )
    tid = res1["created_task"]["task_id"]
    with GraphStore(ws) as store:
        assert f"`{tid}`[RUNNING]" in build_tiered_capsule(store)

    # Ticking only step 0 while requesting stage='DONE' MUST fail because step #[1] is unchecked!
    with pytest.raises(ValueError, match="Task-List Discipline Gate"):
        execute_mcp_tool("checkpoint", {"workspace": str(ws), "task_updates": [{"id": tid, "done_steps": [0], "stage": "DONE"}]})

    # Ticking remaining step #[1] -> now stage='DONE' succeeds!
    res2 = execute_mcp_tool("checkpoint", {"workspace": str(ws), "task_updates": [{"id": tid, "done_steps": [1], "stage": "DONE"}]})
    assert res2["updated_tasks"] == [{"id": tid, "kind": "TASK"}]
