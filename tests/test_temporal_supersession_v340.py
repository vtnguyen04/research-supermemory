"""Tests for SuperMemory v3.4.0: Temporal Fact Supersession Decay & Zero-Turn Hook Auto-Recall."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from supermemory.bootstrap import init_workspace
from supermemory.hooks.runner import dispatch_hook
from supermemory.kernel import execute_command


def test_temporal_supersession_and_baseline_decay_preserve_dead_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify newer observations/SOTA baselines outrank superseded ones while dead-end warnings never decay."""
    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(tmp_path / "global_sm"))
    ws = tmp_path / "kaggle_proj"
    init_workspace(ws, project_name="KaggleThermograph")
    w = str(ws)

    # 1. Early observation (Day 1): lr=1e-3
    c1 = execute_command(
        "checkpoint",
        {
            "workspace": w,
            "insights": ["Transformer Schedule Learning Rate: AdamW lr=1e-3 with linear warmup achieves best validation regret"],
        },
    )
    obs1_id = c1["captured"]["id"]

    # 2. Failed dead-end experiment (Day 2): lr=5e-3 diverges -> MUST NEVER DECAY
    fail_exp = execute_command(
        "log_experiment",
        {
            "workspace": w,
            "track": "mpc",
            "title": "Aggressive AdamW lr=5e-3 Schedule",
            "hypothesis": "Higher lr=5e-3 speeds up schedule convergence",
            "single_var_diff": "lr 1e-3 -> 5e-3",
            "cv_score": -0.15,
            "verdict": "REVERT",
            "post_mortem": "Gradient explosion in zone coil rollout at lr=5e-3; never exceed 1e-3 without clipping.",
        },
    )
    fail_obs_id = fail_exp["observation_ids"][0]

    # 3. Newer observation (Day 5) explicitly supersedes OBS-001 (even if someone passes fail_obs_id, dead-end stays intact!)
    c2 = execute_command(
        "checkpoint",
        {
            "workspace": w,
            "insights": ["Cosine Schedule Learning Rate: AdamW lr=3e-4 with cosine decay beats lr=1e-3 on 30-day validation regret"],
            "supersedes": [obs1_id, fail_obs_id],
        },
    )
    obs2_id = c2["captured"]["id"]
    assert obs1_id in c2["superseded_ids"]

    # 4. Baseline vs SOTA experiment chain (IMPROVES_OVER)
    e1 = execute_command(
        "log_experiment",
        {
            "workspace": w,
            "track": "mpc",
            "exp_id": "EXP-MPC-001",
            "title": "Baseline MPC Horizon 12 Validation Regret",
            "hypothesis": "12-step horizon baseline",
            "single_var_diff": "horizon=12",
            "cv_score": 0.80,
            "verdict": "KEEP",
        },
    )
    execute_command(
        "log_experiment",
        {
            "workspace": w,
            "track": "mpc",
            "exp_id": "EXP-MPC-002",
            "baseline_id": e1["exp_id"],
            "title": "Extended MPC Horizon 24 Validation Regret",
            "hypothesis": "24-step horizon captures thermal inertia",
            "single_var_diff": "horizon 12 -> 24",
            "cv_score": 0.91,
            "verdict": "VICTORY_CONFIRMED",
        },
    )

    rec = execute_command("recall", {"workspace": w, "query": "AdamW schedule learning rate validation regret", "limit": 8})
    by_id = {r["id"]: r for r in rec["results"]}
    assert by_id[obs2_id]["score"] > by_id[obs1_id]["score"]
    assert by_id[obs1_id]["superseded_by"] == obs2_id
    assert any(fail_obs_id in w_txt or "EXP-MPC" in w_txt or "lr=5e-3" in w_txt for w_txt in rec["anti_repeat_warnings"])

    rec_exp = execute_command("recall", {"workspace": w, "query": "MPC Horizon Validation Regret", "limit": 6})
    exp_by_id = {r["id"]: r for r in rec_exp["results"]}
    assert exp_by_id["EXP-MPC-002"]["score"] > exp_by_id["EXP-MPC-001"]["score"]
    assert exp_by_id["EXP-MPC-001"]["superseded_by"] == "EXP-MPC-002"


def test_zero_turn_hook_auto_recall_antigravity_and_claude_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify <25ms 0-turn auto-recall excludes superseded facts, deduplicates per session, and resets on compaction."""
    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(tmp_path / "global_hook"))
    ws = tmp_path / "hook_proj"
    init_workspace(ws, project_name="HookRecallProj")
    w = str(ws)

    c_old = execute_command(
        "checkpoint",
        {"workspace": w, "insights": ["Fixed 2K Chiller Valve Deadband: Narrow 2.0K deadband minimizes short-cycling"]},
    )
    c_new = execute_command(
        "checkpoint",
        {
            "workspace": w,
            "insights": ["Schmitt-Trigger Chiller Valve Deadband: Wide-band [328K, 349.5K] eliminates 8.71kW cycling tax"],
            "supersedes": [c_old["captured"]["id"]],
        },
    )
    old_id = c_old["captured"]["id"]
    new_id = c_new["captured"]["id"]
    assert old_id != new_id

    # 1. Antigravity PreInvocation: injects fresh non-superseded new_id in < 25ms, excludes superseded old_id
    t0 = time.perf_counter()
    out1 = dispatch_hook(
        "PreInvocation",
        {
            "conversationId": "sess-1",
            "cwd": w,
            "invocationNum": 1,
            "initialNumSteps": 4,
            "lastUserInput": "Optimize chiller valve deadband to eliminate cycling tax in winter",
        },
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert elapsed_ms < 25.0, f"Hook latency {elapsed_ms:.2f}ms exceeded 25ms kill criterion"
    msg1 = out1["injectSteps"][0]["systemMessage"]["systemMessage"]
    assert "SUPERMEMORY AUTO-RECALL" in msg1
    assert new_id in msg1 and old_id not in msg1

    # 2. Session deduplication: asking a related prompt in the same session does NOT re-inject new_id
    out2 = dispatch_hook(
        "PreInvocation",
        {
            "conversationId": "sess-1",
            "cwd": w,
            "invocationNum": 2,
            "initialNumSteps": 26,
            "lastUserInput": "Tune chiller valve deadband parameters on validation scenarios",
        },
    )
    assert out2 == {}

    # 3. Claude Code UserPromptSubmit after compaction drop (26 -> 4): resets dedup & emits hookSpecificOutput
    out_claude = dispatch_hook(
        "UserPromptSubmit",
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "sess-1",
            "cwd": w,
            "initialNumSteps": 4,
            "prompt": "Re-check chiller valve deadband wide-band hysteresis configuration",
        },
    )
    claude_ctx = out_claude["hookSpecificOutput"]["additionalContext"]
    assert "COMPACTION RECOVERY DETECTED" in claude_ctx
    assert new_id in claude_ctx
