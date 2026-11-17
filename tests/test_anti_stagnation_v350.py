"""Tests for SuperMemory v3.5.0: Anti-Stagnation Research Circuit-Breaker & Verified Citation Gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from supermemory.bootstrap import init_workspace
from supermemory.hooks.runner import dispatch_hook
from supermemory.kernel import execute_command
from supermemory.research.sota_scout import scout_sota_papers
from supermemory.storage.sqlite_store import GraphStore


def test_anti_hallucination_citation_gate_blocks_fake_internal_papers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure structural URI parsing classifies provenance with zero phrase regexes and preserves dead-ends across consolidation."""
    from supermemory.cognitive.tiers import build_tiered_capsule

    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(tmp_path / "global_cit"))
    ws = tmp_path / "cit_proj"
    init_workspace(ws, project_name="CitationProj")
    w = str(ws)

    # 1. Card without scholarly URL is structurally tagged UNVERIFIED_MANUAL regardless of venue wording (0 phrase regex!)
    unv = execute_command(
        "scout_sota",
        {
            "workspace": w, "action": "register_card",
            "title": "Wide-Band Schmitt-Trigger Reservoir Hysteresis",
            "core_mechanism": "Local deadband heuristic",
            "venue": "Any Custom Venue Text", "year": 2026,
        },
    )
    assert unv["method_card"]["metadata"]["provenance"] == "UNVERIFIED_MANUAL"

    # 2. Local file path or non-http URI disguised as source_url -> HARD BLOCKED structurally by urlparse
    with pytest.raises(ValueError, match="Structural Citation Gate"):
        execute_command(
            "scout_sota",
            {
                "workspace": w, "action": "register_card",
                "title": "Local Controller Notes", "core_mechanism": "Valve clamp",
                "venue": "ICML", "source_url": "file:///home/user/notes.md",
            },
        )

    # 3. Real arXiv URL -> VERIFIED_EXTERNAL
    ok = execute_command(
        "scout_sota",
        {
            "workspace": w, "action": "register_card",
            "title": "Economic Tube Model Predictive Control for Commercial HVAC",
            "core_mechanism": "Tightens polytopic disturbance invariant tubes around electricity prices.",
            "venue": "arXiv", "year": 2025, "source_url": "https://arxiv.org/abs/2502.04321",
        },
    )
    assert ok["method_card"]["metadata"]["provenance"] == "VERIFIED_EXTERNAL"

    # 4. Multi-run REM-sleep consolidation splits PASSED vs FAILED and NEVER erases REVERT dead-ends!
    execute_command(
        "log_experiment",
        {
            "workspace": w, "track": "gbdt", "title": "CatBoost Quantile Loss alpha=0.95",
            "hypothesis": "Asymmetric quantile loss improves tail calibration",
            "single_var_diff": "loss=Quantile:alpha=0.95", "cv_score": 0.612, "verdict": "REVERT",
            "post_mortem": "Severe median bias degraded overall RMSE by +14%.",
        },
    )
    for idx in range(2, 7):
        execute_command(
            "log_experiment",
            {
                "workspace": w, "track": "gbdt", "title": f"CatBoost Symmetric Depth={idx + 3} Ensemble",
                "hypothesis": f"Depth {idx + 3} improves feature interactions",
                "single_var_diff": f"depth={idx + 3}", "cv_score": 0.80 + idx * 0.01, "verdict": "KEEP",
            },
        )

    sem_detail = execute_command("recall", {"workspace": w, "node_id": "SEM-001"})
    assert "Verified Wins" in sem_detail["node"]["content"] and "Falsified Dead-Ends" in sem_detail["node"]["content"]
    # Even AFTER consolidation into SEM-001, repeating the REVERTED CatBoost Quantile Loss is STILL HARD-BLOCKED (0 keyword lists)!
    with pytest.raises(ValueError, match="Anti-Repeat Gate"):
        execute_command(
            "manage_proposal",
            {
                "workspace": w, "action": "create",
                "title": "CatBoost Quantile Loss alpha=0.95 Tail Calibration",
                "why": "Try asymmetric quantile loss alpha=0.95 on CatBoost",
                "what_changes": "Switch CatBoost objective to Quantile:alpha=0.95",
            },
        )
    with GraphStore(ws) as store:
        cap = build_tiered_capsule(store)
        assert "PROVEN WINS" in cap and "FALSIFIED DEAD-ENDS" in cap


def test_consecutive_failure_plateau_locks_proposals_until_verified_external_scout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify >=2 consecutive failed/discarded runs lock local tweaking and unverified cards cannot cheat unlock."""
    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(tmp_path / "global_stag"))
    ws = tmp_path / "stag_proj"
    init_workspace(ws, project_name="StagProj")
    w = str(ws)

    bnk = execute_command(
        "diagnose_bottleneck",
        {
            "workspace": w,
            "title": "Open-Valve Boiler Recharge Spikes",
            "evidence_slice": "627-886 kW spikes every 6 steps on winter strips",
            "error_share_pct": 71.5,
            "ceiling_gain": 0.00065,
            "falsifiable_rq": "Can continuous enthalpy modulation eliminate 6-step recharge spikes?",
        },
    )
    bnk_id = bnk["bottleneck"]["id"]
    assert "scout_sota" in bnk["next_research_action"]

    r1 = execute_command(
        "log_experiment",
        {
            "workspace": w, "track": "main", "title": "Threshold Tweak 328K -> 326K",
            "hypothesis": "Lowering tank threshold reduces spikes", "single_var_diff": "low_k=326.0",
            "cv_score": 0.0045, "verdict": "REVERT", "post_mortem": "Regressed morning comfort on minneapolis_2.",
        },
    )
    assert "stagnation_alert" not in r1

    r2 = execute_command(
        "log_experiment",
        {
            "workspace": w, "track": "main", "title": "Threshold Tweak 328K -> 327K",
            "hypothesis": "Smaller threshold shift avoids comfort regression", "single_var_diff": "low_k=327.0",
            "cv_score": 0.0044, "verdict": "DISCARD", "post_mortem": "Still regresses comfort without cutting spike.",
        },
    )
    assert "ANTI-STAGNATION CIRCUIT-BREAKER" in r2["stagnation_alert"]

    pre = dispatch_hook(
        "PreInvocation",
        {"conversationId": "c-stag", "cwd": w, "invocationNum": 3, "initialNumSteps": 20, "lastUserInput": "tiếp tục tối ưu điểm đi"},
    )
    assert "ANTI-STAGNATION CIRCUIT-BREAKER" in pre["injectSteps"][0]["systemMessage"]["systemMessage"]

    with pytest.raises(ValueError, match="Anti-Stagnation Literature Gate"):
        execute_command(
            "manage_proposal",
            {
                "workspace": w, "action": "create", "bottleneck_id": bnk_id,
                "title": "Try Threshold 327.4K Heuristic", "why": "Nudge tank threshold one more time on winter strips",
                "what_changes": "Set tank_low_k = 327.4 in config.py",
                "novelty_diff": "Uses fractional 327.4K setpoint instead of integer 327K.",
            },
        )

    # Unverified manual card (no scholarly URL) CANNOT cheat the stagnation lock!
    unv = execute_command(
        "scout_sota",
        {
            "workspace": w, "action": "register_card", "bottleneck_id": bnk_id,
            "title": "Unverified Manual Note", "core_mechanism": "Guessing smoother ramp", "venue": "ICML",
        },
    )
    assert unv["method_card"]["metadata"]["provenance"] == "UNVERIFIED_MANUAL"
    with pytest.raises(ValueError, match="Anti-Stagnation Literature Gate"):
        execute_command(
            "manage_proposal",
            {
                "workspace": w, "action": "create", "bottleneck_id": bnk_id,
                "title": "Still Guessing Ramp Heuristic", "why": "Try linear valve ramp without real paper",
                "what_changes": "Add ad-hoc valve ramp factor in boiler.py",
                "novelty_diff": "Adds ad-hoc 0.5x linear valve ramp multiplier.",
            },
        )

    with GraphStore(ws) as store:
        scout_sota_papers(
            store,
            query="economic model predictive control stratified thermal storage",
            bottleneck_id=bnk_id,
            save_top_k=1,
            offline_fixtures=[
                {
                    "title": "Economic MPC for Stratified Thermal Energy Storage with Smooth Valve Actuation",
                    "abstract": "Formulates convex L1-rate-penalized economic MPC eliminating recharge spikes.",
                    "year": 2025, "venue": "arXiv", "citations": 14,
                    "url": "https://arxiv.org/abs/2501.09999", "source": "arxiv",
                }
            ],
        )

    unlocked_prop = execute_command(
        "manage_proposal",
        {
            "workspace": w, "action": "create", "bottleneck_id": bnk_id,
            "title": "Convex L1-Rate-Penalized Economic MPC Valve Actuation",
            "why": "Apply arXiv:2501.09999 L1 rate penalty to eliminate 627-886 kW recharge spikes",
            "what_changes": "Add convex delta-u L1 rate penalty in hydraulic MPC objective",
            "novelty_diff": "Pivots from static deadband thresholds to arXiv:2501.09999 L1 rate-penalized economic MPC.",
        },
    )
    assert unlocked_prop["proposal_id"].startswith("PROP-")


def test_bottleneck_thrashing_forces_literature_pivot_per_bottleneck(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify >=2 failed attempts on one BNK-XXX locks that bottleneck even if another track had a KEEP run."""
    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(tmp_path / "global_thr"))
    ws = tmp_path / "thrash_proj"
    init_workspace(ws, project_name="ThrashProj")
    w = str(ws)

    bnk = execute_command(
        "diagnose_bottleneck",
        {
            "workspace": w, "title": "94% Chiller Cooling Floor",
            "evidence_slice": "Singapore & Phoenix cooling electricity floor",
            "error_share_pct": 64.9, "ceiling_gain": 0.00055,
            "falsifiable_rq": "Can enthalpy-aware free cooling break the 94% chiller floor?",
        },
    )
    bnk_id = bnk["bottleneck"]["id"]

    p1 = execute_command(
        "manage_proposal",
        {
            "workspace": w, "action": "create", "bottleneck_id": bnk_id,
            "title": "Cooling Attempt 1: Fixed 60% Duty Cap",
            "why": "Clamp cooling duty cycle on singapore_5", "what_changes": "Clamp ahu_duty <= 0.60 in cooling.py",
        },
    )
    execute_command(
        "log_experiment",
        {
            "workspace": w, "track": "cooling", "proposal_id": p1["proposal_id"],
            "title": "Fixed 60% Duty Cap Run", "hypothesis": "60% cap cuts chiller power",
            "single_var_diff": "duty_cap=0.60", "cv_score": 0.0051, "verdict": "REVERT",
            "post_mortem": "Zone temp violated comfort ceiling by 1.2K.",
        },
    )
    execute_command(
        "log_experiment",
        {
            "workspace": w, "track": "winter", "title": "Winter Baseline Verification",
            "hypothesis": "Verify winter baseline", "single_var_diff": "winter_check=1",
            "cv_score": 0.0039, "verdict": "KEEP",
        },
    )

    p2 = execute_command(
        "manage_proposal",
        {
            "workspace": w, "action": "create", "bottleneck_id": bnk_id,
            "title": "Cooling Attempt 2: Fixed 75% Duty Cap",
            "why": "Relax cooling duty cap to 75% on singapore_5", "what_changes": "Clamp ahu_duty <= 0.75 in cooling.py",
            "novelty_diff": "Relaxes duty cap from 60% to 75% to preserve zone comfort.",
        },
    )
    execute_command(
        "log_experiment",
        {
            "workspace": w, "track": "cooling", "proposal_id": p2["proposal_id"],
            "title": "Fixed 75% Duty Cap Run", "hypothesis": "75% cap balances power and comfort",
            "single_var_diff": "duty_cap=0.75", "cv_score": 0.0049, "verdict": "FAILED",
            "post_mortem": "Still regresses afternoon latent humidity cooling load.",
        },
    )
    execute_command(
        "log_experiment",
        {
            "workspace": w, "track": "winter", "title": "Winter Warmup Check",
            "hypothesis": "Verify warmup timing", "single_var_diff": "warmup=15m",
            "cv_score": 0.0038, "verdict": "KEEP",
        },
    )

    with pytest.raises(ValueError, match="Anti-Stagnation Literature Gate"):
        execute_command(
            "manage_proposal",
            {
                "workspace": w, "action": "create", "bottleneck_id": bnk_id,
                "title": "Cooling Attempt 3: Fixed 82% Duty Cap",
                "why": "Try 82% duty cap on singapore_5", "what_changes": "Clamp ahu_duty <= 0.82 in cooling.py",
                "novelty_diff": "Adjusts cap to 82%.",
            },
        )
