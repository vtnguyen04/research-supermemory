"""Tests for SuperMemory v3.5.2: Information-Gap Gated Research, Minimization Deltas & Zero-Regex Novelty."""

from __future__ import annotations

from pathlib import Path

import pytest

from supermemory.bootstrap import init_workspace
from supermemory.cognitive.tiers import build_tiered_capsule
from supermemory.hooks.runner import dispatch_hook
from supermemory.kernel import execute_command
from supermemory.models import EdgeType
from supermemory.research.sota_scout import scout_sota_papers
from supermemory.self_learning.detector import SelfLearningDetector
from supermemory.storage.sqlite_store import GraphStore


def test_structural_provenance_and_lossless_consolidation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure structural URI parsing classifies provenance (0 phrase regexes) and consolidation preserves dead-ends."""
    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(tmp_path / "global_cit"))
    ws = tmp_path / "cit_proj"
    init_workspace(ws, project_name="CitationProj")
    w = str(ws)

    unv = execute_command(
        "scout_sota",
        {
            "workspace": w, "action": "register_card",
            "title": "Wide-Band Schmitt-Trigger Reservoir Hysteresis",
            "core_mechanism": "Local deadband heuristic", "venue": "Custom Venue", "year": 2026,
        },
    )
    assert unv["method_card"]["metadata"]["provenance"] == "UNVERIFIED_MANUAL"

    with pytest.raises(ValueError, match="Structural Citation Gate"):
        execute_command(
            "scout_sota",
            {
                "workspace": w, "action": "register_card",
                "title": "Local Controller Notes", "core_mechanism": "Valve clamp",
                "venue": "ICML", "source_url": "file:///home/user/notes.md",
            },
        )

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


def test_minimization_wins_and_method_proposals_never_trigger_false_research(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify negative deltas on minimization metrics (RMSE/Regret) and 'đề xuất method' never force research."""
    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(tmp_path / "global_min"))
    ws = tmp_path / "min_proj"
    init_workspace(ws, project_name="MinRegretProj")
    w = str(ws)

    # 1. Method proposal prompt MUST NOT trigger RESEARCH_CAMPAIGN auto-routing
    sig = SelfLearningDetector.analyze("Hãy đề xuất phương pháp và thuật toán tối ưu cho BNK-010 từ dữ liệu hiện có")
    assert sig.category == "NONE"

    # 2. 4 consecutive minimization breakthroughs (0.0050 -> 0.0042 -> 0.0037 -> 0.0033, negative delta!)
    prev_id = ""
    scores = [0.0050, 0.0042, 0.0037, 0.0033]
    for i, sc in enumerate(scores):
        out = execute_command(
            "log_experiment",
            {
                "workspace": w, "track": "main", "baseline_id": prev_id,
                "title": f"Minimization Regret Breakthrough Step {i + 1}",
                "hypothesis": f"Step {i + 1} cuts validation regret",
                "single_var_diff": f"step_opt={i + 1}", "cv_score": sc, "verdict": "KEEP",
            },
        )
        assert out["regression_detected"] is False
        assert "stagnation_alert" not in out
        prev_id = out["exp_id"]

    with GraphStore(ws) as store:
        edges = store.list_edges(prev_id)
        assert any(ed.relation == EdgeType.IMPROVES_OVER.value for ed in edges)


def test_information_gap_gate_allows_untried_vault_ideas_and_locks_only_when_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify research lock triggers ONLY when >=3 runs fail AND 0 untried ideas/methods exist in vault."""
    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(tmp_path / "global_igap"))
    ws = tmp_path / "igap_proj"
    init_workspace(ws, project_name="InfoGapProj")
    w = str(ws)

    bnk = execute_command(
        "diagnose_bottleneck",
        {
            "workspace": w, "title": "Open-Valve Boiler Recharge Spikes",
            "evidence_slice": "627-886 kW spikes every 6 steps on winter strips",
            "error_share_pct": 71.5, "ceiling_gain": 0.00065,
            "falsifiable_rq": "Can continuous enthalpy modulation eliminate 6-step recharge spikes?",
        },
    )
    bnk_id = bnk["bottleneck"]["id"]
    assert "manage_proposal" in bnk["next_step"]

    # 3 consecutive failed runs with 0 untried ideas in vault -> INFORMATION-GAP PLATEAU LOCKS!
    for idx in range(3):
        res = execute_command(
            "log_experiment",
            {
                "workspace": w, "track": "main", "title": f"Threshold Tweak #{idx + 1}",
                "hypothesis": "Nudge tank threshold", "single_var_diff": f"low_k={326 + idx * 0.4}",
                "cv_score": 0.0045, "verdict": "REVERT", "post_mortem": "Regressed winter comfort.",
            },
        )
    assert "INFORMATION-GAP PLATEAU DETECTED" in res["stagnation_alert"]

    pre = dispatch_hook(
        "PreInvocation",
        {"conversationId": "c-gap", "cwd": w, "invocationNum": 2, "initialNumSteps": 10, "lastUserInput": "tiếp tục đi"},
    )
    assert "INFORMATION-GAP PLATEAU DETECTED" in pre["injectSteps"][0]["systemMessage"]["systemMessage"]

    with pytest.raises(ValueError, match="Anti-Stagnation Literature Gate"):
        execute_command(
            "manage_proposal",
            {
                "workspace": w, "action": "create", "bottleneck_id": bnk_id,
                "title": "Blind Threshold Guess #4", "why": "Nudge threshold again without new idea",
                "what_changes": "Set tank_low_k = 327.8", "novelty_diff": "Tries 327.8K scalar tweak.",
            },
        )

    # Case A: If an untried internal ALGORITHM from forensic analysis is logged in vault -> Proposal ALLOWED without forced paper search!
    idea = execute_command(
        "propose_idea",
        {
            "workspace": w, "is_algorithm": True, "bottleneck_id": bnk_id,
            "title": "Exact Return-Water Enthalpy Mass-Balance Feedforward",
            "summary": "Derive exact coil mass-flow feedforward from return-water enthalpy balance.",
        },
    )
    prop_from_vault = execute_command(
        "manage_proposal",
        {
            "workspace": w, "action": "create", "bottleneck_id": bnk_id,
            "title": "Implement Return-Water Enthalpy Feedforward",
            "why": "Use untried forensic enthalpy balance from ALGO-001",
            "what_changes": "Wire enthalpy feedforward in boiler.py",
        },
    )
    assert prop_from_vault["proposal_id"].startswith("PROP-")

    # Mark ALGO-001 REJECTED -> vault now has 0 untried candidates again -> locked until verified external paper!
    with GraphStore(ws) as store:
        nd = store.get_node(idea["node"]["id"])
        assert nd is not None
        nd.status = "REJECTED"
        store.upsert_node(nd, log_event=False)

    with pytest.raises(ValueError, match="Anti-Stagnation Literature Gate"):
        execute_command(
            "manage_proposal",
            {
                "workspace": w, "action": "create", "bottleneck_id": bnk_id,
                "title": "Another Blind Tweak #5", "why": "Vault is empty again",
                "what_changes": "Change scalar gain to 0.85", "novelty_diff": "Changes gain scalar to 0.85.",
            },
        )

    with GraphStore(ws) as store:
        scout_sota_papers(
            store, query="economic MPC thermal storage", bottleneck_id=bnk_id, save_top_k=1,
            offline_fixtures=[
                {
                    "title": "Convex L1-Rate Economic MPC for Thermal Storage",
                    "abstract": "Eliminates recharge spikes via L1 rate penalty.",
                    "year": 2025, "venue": "arXiv", "citations": 12,
                    "url": "https://arxiv.org/abs/2501.09999", "source": "arxiv",
                }
            ],
        )

    unlocked = execute_command(
        "manage_proposal",
        {
            "workspace": w, "action": "create", "bottleneck_id": bnk_id,
            "title": "Apply L1-Rate Economic MPC", "why": "Test arXiv:2501.09999 mechanism",
            "what_changes": "Add L1 delta-u penalty in mpc.py", "novelty_diff": "Applies arXiv:2501.09999 L1 rate penalty.",
        },
    )
    assert unlocked["proposal_id"].startswith("PROP-")
