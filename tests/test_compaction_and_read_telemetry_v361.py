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
