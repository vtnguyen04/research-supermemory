"""Simulation test for a 7-day autonomous `/goal` A* World Model research campaign."""

from __future__ import annotations

from pathlib import Path

import pytest

from supermemory.bootstrap import init_workspace
from supermemory.hooks.runner import dispatch_hook
from supermemory.mcp.tool_defs import execute_mcp_tool


def test_week_long_world_model_goal_campaign_guarantees(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(tmp_path / "global_wm"))
    ws = tmp_path / "world_model_astar"
    init_workspace(ws, project_name="WorldModel-AStar", active_goal="Achieve A* novelty on Atari100k + MemoryMaze (>90.0 norm score)")
    conv = "conv-goal-7days"
    goal_prompt = "/goal Research về method World Model Novelty đạt chuẩn A* trên Atari100k"

    # Day 1, Step 4: Start /goal session and log failed KL-curiosity experiment
    dispatch_hook(
        "PreInvocation",
        {"conversationId": conv, "workspacePaths": [str(ws)], "invocationNum": 1, "initialNumSteps": 4, "lastUserInput": goal_prompt},
    )
    exp1 = execute_mcp_tool(
        "supermemory_log_experiment",
        {
            "workspace": str(ws),
            "track": "rssm",
            "title": "RSSM Latent KL Curiosity Bonus on Atari100k",
            "hypothesis": "Raw KL divergence bonus in RSSM stochastic state improves exploration",
            "single_var_diff": "Added beta*KL intrinsic reward to RSSM actor",
            "cv_score": 51.2,
            "verdict": "REVERT",
            "post_mortem": "Raw KL curiosity explodes on stochastic TV-noise dynamics.",
            "insights": ["Raw KL curiosity in RSSM overfits stochastic environment noise instead of epistemic uncertainty."],
        },
    )
    assert exp1["observation_ids"] == ["OBS-001"]

    # Same /goal prompt, Step 12: Agent runs a SECOND benchmark command after EXP-1 was already logged!
    dispatch_hook(
        "PostToolUse",
        {
            "conversationId": conv,
            "workspacePaths": [str(ws)],
            "toolCall": {"name": "run_command", "args": {"CommandLine": "python train_world_model.py --horizon 15"}},
        },
    )
    # Stop hook MUST block because turn_memory_handled was reset by the new benchmark execution!
    stop_res = dispatch_hook(
        "Stop",
        {"conversationId": conv, "workspacePaths": [str(ws)], "continuationActive": False, "terminationReason": "NO_TOOL_CALL"},
    )
    assert stop_res["decision"] == "continue"

    # Log SOTA baseline run #2
    execute_mcp_tool(
        "supermemory_log_experiment",
        {
            "workspace": str(ws),
            "track": "rssm",
            "title": "DreamerV3 Symexp Baseline Reproduction",
            "hypothesis": "Establish verified clean baseline",
            "single_var_diff": "Standard symexp twohot loss",
            "cv_score": 78.4,
            "verdict": "KEEP",
        },
    )

    # Day 3, Step 21 (same lastUserInput!): 20-step Long-Horizon Heartbeat fires with SOTA + Dead-End count!
    hb = dispatch_hook(
        "PreInvocation",
        {"conversationId": conv, "workspacePaths": [str(ws)], "invocationNum": 15, "initialNumSteps": 21, "lastUserInput": goal_prompt},
    )
    hb_msg = hb["injectSteps"][0]["systemMessage"]["systemMessage"]
    assert "LONG-HORIZON `/goal` MEMORY HEARTBEAT" in hb_msg
    assert "Best SOTA: `EXP-RSSM-002`" in hb_msg
    assert "Falsified Dead-Ends (Never Repeat): 1" in hb_msg

    # Day 4: Agent forgets Day 1 and tries to propose repeating RSSM Latent KL Curiosity Bonus -> HARD BLOCKED!
    with pytest.raises(ValueError, match="LAW-06 Anti-Repeat Gate"):
        execute_mcp_tool(
            "supermemory_manage_proposal",
            {
                "workspace": str(ws),
                "action": "create",
                "title": "RSSM Latent KL Curiosity Bonus Exploration",
                "why": "Use KL divergence intrinsic reward on RSSM stochastic state for Atari100k",
                "what_changes": "Add KL curiosity bonus",
            },
        )

    # Agent pivots mathematically with explicit `novelty_diff` -> ALLOWED!
    pivoted = execute_mcp_tool(
        "supermemory_manage_proposal",
        {
            "workspace": str(ws),
            "action": "create",
            "title": "RSSM Epistemic Ensemble Disagreement in Bisimulation Space",
            "why": "Separate epistemic uncertainty from stochastic aleatoric noise on Atari100k",
            "what_changes": "Replace raw KL reward with frozen-target bisimulation ensemble variance",
            "novelty_diff": "Replaces aleatoric-sensitive raw KL divergence with reward-equivariant bisimulation ensemble disagreement.",
        },
    )
    assert pivoted["proposal_id"] == "PROP-001"

    # Day 6: Run 5 more track experiments — all EXPERIMENT records stay 100% SACRED & untouched forever!
    exp_ids: list[str] = []
    for idx in range(3, 8):
        out_exp = execute_mcp_tool(
            "supermemory_log_experiment",
            {
                "workspace": str(ws),
                "track": "rssm",
                "title": f"Bisimulation Horizon Ablation H={idx * 5}",
                "hypothesis": f"Test imagination horizon {idx * 5}",
                "single_var_diff": f"horizon={idx * 5}",
                "cv_score": 79.0 + idx,
                "verdict": "KEEP",
            },
        )
        exp_ids.append(out_exp["exp_id"])
    with pytest.raises(ValueError, match="Sacred node"):
        execute_mcp_tool(
            "supermemory_consolidate",
            {
                "workspace": str(ws),
                "mode": "apply_plan",
                "operations": [{"op": "merge", "source_ids": exp_ids[:2], "title": "Illegal Exp Merge", "summary": "Attempting to merge sacred experiments 82.0 83.0.", "content": "Experiments are permanent evidence (82.0, 83.0) and must never be consolidated away."}],
            },
        )

    # Day 7: Context Compaction drops step count from 21 -> 3; capsule stays lean (<850 tokens) and preserves SOTA!
    comp = dispatch_hook(
        "PreInvocation",
        {"conversationId": conv, "workspacePaths": [str(ws)], "invocationNum": 40, "initialNumSteps": 3, "lastUserInput": goal_prompt},
    )
    comp_msg = comp["injectSteps"][0]["systemMessage"]["systemMessage"]
    assert "COMPACTION RECOVERY DETECTED" in comp_msg
    assert len(comp_msg) // 4 < 850
