"""Regression suite for SuperMemory v3.6.1: Mid-Turn Compaction Probe, Notification Relay & Read Telemetry."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from supermemory.bootstrap import init_workspace
from supermemory.hooks.runner import dispatch_hook
from supermemory.kernel import execute_command
from supermemory.storage.snapshot_io import get_session_state
from supermemory.storage.sqlite_store import GraphStore

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_mid_turn_monotonic_step_compaction_recovery(tmp_path: Path) -> None:
    ws = tmp_path / "ws_compact_mid"
    init_workspace(ws, project_name="MidTurnCompact")
    execute_command(
        "checkpoint",
        {
            "workspace": str(ws),
            "insights": ["Schmitt Hysteresis Deadband: 14K deadband cuts overnight boiler pulses by 74%."],
            "new_task": {
                "title": "Verify 30-day Winter Suite",
                "stage": "IN_PROGRESS",
                "steps": ["Run val16 smoke", "Log full 30d suite"],
            },
        },
    )

    t_file = tmp_path / "transcript.jsonl"
    base_lines = [
        json.dumps({"step_index": 8530, "source": "USER_EXPLICIT", "type": "USER_INPUT", "created_at": "2026-11-17T07:00:00Z"}),
        json.dumps({"step_index": 8534, "source": "MODEL", "type": "PLANNER_RESPONSE", "created_at": "2026-11-17T07:08:50Z"}),
    ]
    t_file.write_text("\n".join(base_lines) + "\n", encoding="utf-8")

    # Initial turn start at step 8531
    dispatch_hook(
        "PreInvocation",
        {
            "cwd": str(ws),
            "conversationId": "conv-mid-1",
            "invocationNum": 35,
            "initialNumSteps": 8531,
            "transcriptPath": str(t_file),
            "lastUserInput": "Run 85-zone forensic suite",
        },
    )

    # Antigravity emits mid-turn SYSTEM CHECKPOINT at step 8535 (step_index stays monotonic -> 8536!)
    with t_file.open("a", encoding="utf-8") as fh:
        fh.write(
            json.dumps(
                {
                    "step_index": 8535,
                    "source": "SYSTEM",
                    "type": "CHECKPOINT",
                    "created_at": "2026-11-17T07:08:54Z",
                    "content": "# Resuming from a compaction",
                }
            )
            + "\n"
        )

    t0 = time.perf_counter()
    mid_out = dispatch_hook(
        "PreInvocation",
        {
            "cwd": str(ws),
            "conversationId": "conv-mid-1",
            "invocationNum": 35,
            "initialNumSteps": 8536,
            "transcriptPath": str(t_file),
            "lastUserInput": "Run 85-zone forensic suite",
        },
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert elapsed_ms < (150.0 if sys.gettrace() is not None else 25.0)

    msg = mid_out["injectSteps"][0]["systemMessage"]["systemMessage"]
    assert "COMPACTION RECOVERY DETECTED" in msg
    assert "[L2 LATEST INSIGHTS]" in msg
    assert "LIVE KANBAN BOARD" in msg

    with GraphStore(ws) as store:
        st = get_session_state(store, "conv-mid-1")
        assert st["compaction_count"] == 1
        ev_types = [e["event_type"] for e in store.list_events(limit=15)]
        assert "COMPACTION_RECOVERY" in ev_types

    # Next step 8537 without a new CHECKPOINT must NOT re-trigger compaction recovery
    nxt_out = dispatch_hook(
        "PreInvocation",
        {
            "cwd": str(ws),
            "conversationId": "conv-mid-1",
            "invocationNum": 35,
            "initialNumSteps": 8537,
            "transcriptPath": str(t_file),
            "lastUserInput": "Run 85-zone forensic suite",
        },
    )
    assert nxt_out == {}


def test_antigravity_post_tool_relay_and_12_step_incremental_pulse(tmp_path: Path) -> None:
    ws = tmp_path / "ws_relay"
    init_workspace(ws, project_name="RelayPulse")

    dispatch_hook(
        "PreInvocation",
        {
            "cwd": str(ws),
            "conversationId": "conv-rel",
            "invocationNum": 1,
            "initialNumSteps": 2,
            "lastUserInput": "Run remote benchmarks",
        },
    )

    # Subprocess CLI PostToolUse for Antigravity MUST output strict `{}` while queuing notification for PreInvocation
    hook_script = REPO_ROOT / "plugin" / "scripts" / "hook_entry.py"
    payload = {
        "cwd": str(ws),
        "conversationId": "conv-rel",
        "toolCall": {"name": "run_command", "args": {"CommandLine": "python3 eval_suite.py --split val16"}},
    }
    proc = subprocess.run(
        [sys.executable, str(hook_script), "PostToolUse"],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(proc.stdout.strip()) == {}

    # Immediately following mid-turn PreInvocation delivers the queued Save Notification!
    pre_mid = dispatch_hook(
        "PreInvocation",
        {
            "cwd": str(ws),
            "conversationId": "conv-rel",
            "invocationNum": 1,
            "initialNumSteps": 3,
            "lastUserInput": "Run remote benchmarks",
        },
    )
    relayed_txt = pre_mid["injectSteps"][0]["systemMessage"]["systemMessage"]
    assert "SuperMemory Save Notification" in relayed_txt

    # 11 more unsynced substantive executions (total = 12) trigger Incremental Sync Pulse
    for step_n in range(2, 13):
        dispatch_hook("PostToolUse", payload)
        last_pre = dispatch_hook(
            "PreInvocation",
            {
                "cwd": str(ws),
                "conversationId": "conv-rel",
                "invocationNum": 1,
                "initialNumSteps": 3 + step_n,
                "lastUserInput": "Run remote benchmarks",
            },
        )
    pulse_txt = last_pre["injectSteps"][0]["systemMessage"]["systemMessage"]
    assert "12 Unsynced Steps" in pulse_txt
    with GraphStore(ws) as store:
        ev_types = [e["event_type"] for e in store.list_events(limit=20)]
        assert "INCREMENTAL_SYNC_PULSE" in ev_types


def test_periodic_capsule_refresh_and_visible_memory_read_events(tmp_path: Path) -> None:
    ws = tmp_path / "ws_telemetry"
    init_workspace(ws, project_name="ReadTelemetry")
    execute_command(
        "checkpoint",
        {
            "workspace": str(ws),
            "insights": ["Pontryagin Costate Shield: Eliminating Gaussian wall flip cut OOD8 regret by 5.2%."],
        },
    )

    # 1. Explicit MCP recall logs MEMORY_RECALLED
    execute_command("recall", {"workspace": str(ws), "query": "Pontryagin Costate"})
    # 2. Reading memory/01_ACTIVE_STATE.md via read_file logs MEMORY_READ
    dispatch_hook(
        "PostToolUse",
        {
            "cwd": str(ws),
            "conversationId": "conv-tel",
            "toolCall": {"name": "read_file", "args": {"Path": str(ws / "memory" / "01_ACTIVE_STATE.md")}},
        },
    )

    # 3. Cross-language Vietnamese progress question after >=45 steps gets automatic Capsule Refresh
    out = dispatch_hook(
        "PreInvocation",
        {
            "cwd": str(ws),
            "conversationId": "conv-tel",
            "invocationNum": 7,
            "initialNumSteps": 60,
            "lastUserInput": "chưa có đột phá gì mới hả? nhớ hết những gì mình đã làm chưa?",
        },
    )
    msg = out["injectSteps"][0]["systemMessage"]["systemMessage"]
    assert "PERIODIC MEMORY CAPSULE REFRESH" in msg
    assert "OBS-001" in msg

    with GraphStore(ws) as store:
        ev_types = [e["event_type"] for e in store.list_events(limit=20)]
        assert "MEMORY_RECALLED" in ev_types
        assert "MEMORY_READ" in ev_types
        assert "PERIODIC_CAPSULE_REFRESH" in ev_types


def test_post_compaction_pre_tool_use_grounding_gate_and_contextual_query(tmp_path: Path) -> None:
    """Verify PROP-021: pre-PreInvocation CHECKPOINT grounding gate, recall clearance, 1-strike valve & smart query."""
    empty_ws = tmp_path / "empty_ws"
    init_workspace(empty_ws, project_name="EmptyVault")
    t_empty = tmp_path / "empty_transcript.jsonl"
    t_empty.write_text(json.dumps({"step_index": 5, "type": "CHECKPOINT", "created_at": "2026-11-23T10:00:00Z"}) + "\n", encoding="utf-8")
    assert dispatch_hook("PreToolUse", {"cwd": str(empty_ws), "conversationId": "c-emp", "transcriptPath": str(t_empty), "toolCall": {"name": "write_file", "args": {"Path": str(empty_ws / "a.py"), "Content": "x = 1\n"}}})["decision"] == "allow"

    ws = tmp_path / "ws_ground"
    init_workspace(ws, project_name="GroundedProj", active_goal="Unthrottle polar warmup rate on giant zones")
    w = str(ws)
    execute_command("manage_proposal", {"workspace": w, "action": "create", "title": "Polar Warmup Rate Controller", "why": "Remove hardcoded 0.50h cap", "what_changes": "Edit hybrid_manifold_head.py", "tasks": ["Patch step_hybrid_fm_v8_pre", "Run fairbanks_3 probe"]})
    execute_command("checkpoint", {"workspace": w, "insights": ["Polar Warmup Breakthrough: Unlocking warmup_rate_k_h cut fairbanks_3 regret by 10.09%."]})

    t_file = tmp_path / "main_transcript.jsonl"
    t_file.write_text(json.dumps({"step_index": 1, "type": "USER_INPUT", "created_at": "2026-11-23T10:00:00Z"}) + "\n", encoding="utf-8")
    dispatch_hook("SessionStart", {"cwd": w, "conversationId": "conv-g1", "transcriptPath": str(t_file)})

    # Simulate Antigravity writing CHECKPOINT immediately BEFORE PLANNER_RESPONSE (before PreInvocation re-runs!)
    with t_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"step_index": 42, "type": "CHECKPOINT", "created_at": "2026-11-23T10:05:00Z", "content": "# Resuming from a compaction"}) + "\n")

    # 1. Read-only commands & outside-workspace artifacts pass straight through (0 false blocks)
    assert dispatch_hook("PreToolUse", {"cwd": w, "conversationId": "conv-g1", "transcriptPath": str(t_file), "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest -q && git status"}}})["decision"] == "allow"
    assert dispatch_hook("PreToolUse", {"cwd": w, "conversationId": "conv-g1", "transcriptPath": str(t_file), "toolCall": {"name": "write_file", "args": {"Path": str(tmp_path / "scratch_note.md"), "Content": "ok"}}})["decision"] == "allow"

    # 2. Ungrounded workspace edit right after CHECKPOINT is denied once while preserving PreInvocation's marker!
    deny_1 = dispatch_hook("PreToolUse", {"cwd": w, "conversationId": "conv-g1", "transcriptPath": str(t_file), "toolCall": {"name": "edit_file", "args": {"Path": str(ws / "hybrid_manifold_head.py"), "Target": "a", "Replacement": "b"}}})
    assert deny_1["decision"] == "deny"
    assert "POST-COMPACTION GROUNDING REQUIRED" in deny_1["reason"]
    assert "PROP-001" in deny_1["reason"]

    # 3. Subsequent PreInvocation on short prompt ("tiếp đi") STILL detects CHECKPOINT, sets user_markdown & contextual recall!
    pre_out = dispatch_hook("PreInvocation", {"cwd": w, "conversationId": "conv-g1", "invocationNum": 9, "initialNumSteps": 43, "transcriptPath": str(t_file), "lastUserInput": "tiếp đi"})
    sm_node = pre_out["injectSteps"][0]["systemMessage"]
    assert "COMPACTION RECOVERY DETECTED" in sm_node["systemMessage"]
    assert "Polar Warmup Breakthrough" in sm_node["systemMessage"]
    assert "user_markdown" in sm_node["metadata"]

    # 4. Calling MCP `recall` immediately grounds the session so workspace edits & substantive runs succeed!
    execute_command("recall", {"workspace": w, "query": "Polar Warmup Rate Controller"})
    allow_after_recall = dispatch_hook("PreToolUse", {"cwd": w, "conversationId": "conv-g1", "transcriptPath": str(t_file), "toolCall": {"name": "edit_file", "args": {"Path": str(ws / "hybrid_manifold_head.py"), "Target": "a", "Replacement": "b"}}})
    assert allow_after_recall["decision"] == "allow"

    # 5. Second compaction verifies 1-strike anti-deadlock valve if agent retries twice without recall
    with t_file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"step_index": 90, "type": "CHECKPOINT", "created_at": "2026-11-23T10:20:00Z"}) + "\n")
    d2_a = dispatch_hook("PreToolUse", {"cwd": w, "conversationId": "conv-g1", "transcriptPath": str(t_file), "toolCall": {"name": "run_command", "args": {"CommandLine": "python3 run_probe.py"}}})
    d2_b = dispatch_hook("PreToolUse", {"cwd": w, "conversationId": "conv-g1", "transcriptPath": str(t_file), "toolCall": {"name": "run_command", "args": {"CommandLine": "python3 run_probe.py"}}})
    assert d2_a["decision"] == "deny"
    assert d2_b["decision"] == "allow"

