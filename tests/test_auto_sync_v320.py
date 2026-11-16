"""End-to-end tests for SuperMemory v3.2 Autonomous Zero-Reminder Sync (Tasks, Insights & Results)."""

from __future__ import annotations

from pathlib import Path

from supermemory.bootstrap import init_workspace
from supermemory.cognitive.tiers import build_tiered_capsule
from supermemory.hooks.runner import dispatch_hook
from supermemory.mcp.tool_defs import execute_mcp_tool
from supermemory.storage.sqlite_store import GraphStore


def test_qna_turn_zero_overhead_vs_code_edit_auto_sync_gate(tmp_path: Path) -> None:
    ws = tmp_path / "proj"
    init_workspace(ws, project_name="AutoSyncProj")

    # 1. Pure Q&A turn -> Stop allows immediately with 0 overhead
    dispatch_hook(
        "PreInvocation",
        {"conversationId": "c1", "cwd": str(ws), "lastUserInput": "claude code sài được không?"},
    )
    stop_qna = dispatch_hook(
        "Stop",
        {"conversationId": "c1", "cwd": str(ws), "terminationReason": "NO_TOOL_CALL"},
    )
    assert stop_qna["decision"] == "allow"

    # 2. Task execution turn where agent claims task first, THEN edits src/policy.py without syncing end-of-turn progress
    pre_task = dispatch_hook(
        "PreInvocation",
        {"conversationId": "c1", "cwd": str(ws), "lastUserInput": "implement night setback damping in src/policy.py"},
    )
    assert "AUTO-SYNC PROTOCOL" in pre_task["injectSteps"][0]["systemMessage"]["systemMessage"]

    (ws / "src").mkdir()
    target_py = ws / "src" / "policy.py"
    target_py.write_text("x = 1\n", encoding="utf-8")

    dispatch_hook(
        "PostToolUse",
        {
            "conversationId": "c1",
            "cwd": str(ws),
            "toolCall": {"name": "write_file", "args": {"Path": str(target_py), "Content": "x = 2\n"}},
        },
    )
    stop_dirty = dispatch_hook(
        "Stop",
        {"conversationId": "c1", "cwd": str(ws), "terminationReason": "NO_TOOL_CALL"},
    )
    assert stop_dirty["decision"] == "continue"
    assert "AUTO-SYNC REQUIRED" in stop_dirty["reason"]
    assert "src/policy.py" in stop_dirty["reason"]


def test_metric_stdout_detection_without_file_edits(tmp_path: Path) -> None:
    ws = tmp_path / "proj_metric"
    init_workspace(ws, project_name="MetricProj")

    dispatch_hook(
        "PreInvocation",
        {"conversationId": "c2", "cwd": str(ws), "lastUserInput": "check current validation regret"},
    )
    dispatch_hook(
        "PostToolUse",
        {
            "conversationId": "c2",
            "cwd": str(ws),
            "toolCall": {"name": "run_command", "args": {"CommandLine": "python3 scripts/check_slice.py"}},
            "output": "Slice 05:00 wakeup -> regret=0.00184, val_score: 0.00462",
        },
    )
    stop_res = dispatch_hook(
        "Stop",
        {"conversationId": "c2", "cwd": str(ws), "terminationReason": "NO_TOOL_CALL"},
    )
    assert stop_res["decision"] == "continue"
    assert "RESULT & INSIGHT SYNC REQUIRED" in stop_res["reason"]


def test_atomic_checkpoint_syncs_insights_kanban_subtasks_and_capsule(tmp_path: Path) -> None:
    ws = tmp_path / "proj_atomic"
    init_workspace(ws, project_name="AtomicProj")

    res1 = execute_mcp_tool(
        "checkpoint",
        {
            "workspace": str(ws),
            "insights": ["Wakeup Spike Root Cause: 62% of morning regret comes from unmasked step-0 coil jump."],
            "new_task": {
                "title": "Dampen step-0 coil wakeup jump",
                "steps": ["Add ramp limiter", "Verify on val16"],
                "stage": "IN_PROGRESS",
            },
            "next_actions": "Run full val16 verification on ramp limiter.",
        },
    )
    assert res1["status"] == "CAPTURED"
    assert res1["captured"]["id"] == "OBS-001"
    task_id = res1["created_task"]["task_id"]
    assert res1["created_task"]["status"] == "RUNNING"

    with GraphStore(ws) as store:
        cap = build_tiered_capsule(store)
        assert f"`{task_id}`[RUNNING]" in cap

    # Complete subtasks + move to DONE via 1-call checkpoint task_updates + orchestrate add_step
    execute_mcp_tool(
        "orchestrate",
        {"workspace": str(ws), "action": "add_step", "task_id": task_id, "text": "Log final benchmark"},
    )
    res2 = execute_mcp_tool(
        "checkpoint",
        {
            "workspace": str(ws),
            "task_updates": [{"id": task_id, "done_steps": [0, 1, 2], "stage": "DONE"}],
        },
    )
    assert res2["updated_tasks"] == [{"id": task_id, "kind": "TASK"}]
    st_orch = execute_mcp_tool("orchestrate", {"workspace": str(ws), "action": "status"})
    done_task = [t for t in st_orch["tasks"] if t["task_id"] == task_id][0]
    assert done_task["status"] == "DONE"
