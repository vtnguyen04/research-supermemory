"""End-to-end verification of Research SuperMemory v3.0 (All 4 Pillars + MCP/CLI/UI APIs)."""

from __future__ import annotations

import json
import threading
import urllib.request
from pathlib import Path
from typing import Any, Dict

import pytest

from supermemory.bootstrap import init_workspace
from supermemory.cli import main as cli_main
from supermemory.cognitive.federation import federated_recall
from supermemory.graph.query_engine import QueryEngine
from supermemory.lifecycle.manager import LifecycleManager
from supermemory.mcp.tool_defs import execute_mcp_tool
from supermemory.models import MemoryNode, NodeType
from supermemory.research.bottleneck_engine import (
    diagnose_bottleneck,
    evaluate_occam_gate,
    rank_bottlenecks,
)
from supermemory.research.orchestrator import (
    claim_next_task,
    complete_task,
    dag_telemetry,
    enqueue_task,
    plan_research_sprint,
)
from supermemory.research.sota_scout import _cache_put, scout_sota_papers
from supermemory.storage.sqlite_store import GraphStore
from supermemory.ui.server import create_http_server


def test_pillar1_hybrid_utility_pagerank_sibling_vault_and_mechanism_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(tmp_path / "global_v3"))
    ws_a = tmp_path / "repo_alpha"
    ws_b = tmp_path / "repo_beta"
    init_workspace(ws_a, project_name="AlphaVision")
    init_workspace(ws_b, project_name="BetaControl")

    # Populate Repo A with a verified SOTA METHOD_CARD
    execute_mcp_tool(
        "supermemory_scout_sota",
        {
            "workspace": str(ws_a),
            "action": "register_card",
            "title": "Adaptive Pre-Cooling Lyapunov Filter",
            "core_mechanism": "Stabilizes pre-cooling slab trajectory via discrete Lyapunov barrier.",
            "venue": "ICML",
            "year": 2025,
        },
    )

    with GraphStore(ws_b) as store_b:
        lm = LifecycleManager(store_b)
        # Log two observations with identical lexical terms, one backed by a high-delta VICTORY experiment
        store_b.upsert_node(
            MemoryNode(
                id="OBS-NEUTRAL",
                node_type=NodeType.OBSERVATION.value,
                title="Thermal Slab Regularization Note",
                summary="Preliminary note on slab regularization behavior.",
            )
        )
        lm.log_experiment(
            track="ctrl",
            exp_id="EXP-WIN-01",
            title="Thermal Slab Regularization Gain",
            hypothesis="Slab regularization cuts peak regret",
            single_var_diff="Added lambda=0.05 slab regularizer",
            cv_score=0.92,
            verdict="VICTORY_CONFIRMED",
            insights=["Thermal Slab Regularization slashed regret by 44% across climates."],
        )
        exp_rec = store_b.list_experiments()[0]
        exp_rec.delta_vs_baseline = 0.25
        store_b.upsert_experiment(exp_rec)

        # Subword N-gram recall ("precool" without hyphen) + Sibling Vault recall from Repo A
        sib_res = federated_recall("precooling lyapunov", local_ws=ws_b, include_siblings=True)
        scopes = [r["scope"] for r in sib_res["results"]]
        assert any(s.startswith("SIBLING:AlphaVision") for s in scopes)

        # Utility PageRank: OBS-001 (linked to VICTORY EXP-WIN-01) outranks OBS-NEUTRAL
        rec = QueryEngine(store_b).recall("Thermal Slab Regularization", limit=6, hops=1)
        obs_ids = [r["id"] for r in rec["results"] if r["id"] in ("OBS-001", "OBS-NEUTRAL")]
        assert obs_ids[0] == "OBS-001"

        # Mechanism Fingerprint Dead-End Guard: Sinkhorn REVERTED on BNK-001 blocks rebranded OT on BNK-001
        bnk = diagnose_bottleneck(
            store_b,
            title="Track ID Switches Under Occlusion",
            evidence_slice="crowded_pedestrian slice (58% of IDSW)",
            error_share_pct=58.0,
            ceiling_gain=0.14,
            falsifiable_rq="Does optimal transport reduce crowded IDSW >= 20%?",
        )["bottleneck"]
        lm.register_idea(
            title="Sinkhorn Assignment on tracker.py",
            summary="Use Sinkhorn optimal transport matching in tracker.py",
            status="REJECTED",
            rejection_reason="Collapsed on low-confidence detections",
            bottleneck_id=bnk["id"],
        )
        with pytest.raises(ValueError, match="Anti-Repeat Gate"):
            lm.create_proposal(
                title="Entropic Wasserstein Bipartite Matching",
                why="Fix crowded occlusion switches",
                what_changes="Add entropic transport assignment inside tracker.py",
                bottleneck_id=bnk["id"],
            )


def test_pillar2_and_3_sota_scout_cache_pareto_bottlenecks_and_occam_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(tmp_path / "global_p23"))
    ws = tmp_path / "research_lab"
    init_workspace(ws, project_name="ResearchLab")

    with GraphStore(ws) as store:
        b_low = diagnose_bottleneck(
            store,
            title="Minor Cold-Climate Drift",
            evidence_slice="alaska_winter (12% regret)",
            error_share_pct=12.0,
            ceiling_gain=0.03,
            falsifiable_rq="Does bias term fix cold drift?",
        )["bottleneck"]
        b_high = diagnose_bottleneck(
            store,
            title="Desert Night Slab Overheating",
            evidence_slice="phoenix_summer (64% regret)",
            error_share_pct=64.0,
            ceiling_gain=0.15,
            falsifiable_rq="Does night pre-cooling guard cut desert regret >= 35%?",
            kill_criterion="Kill at 10% budget if phoenix regret drops < 0.02.",
        )["bottleneck"]

        ranked = rank_bottlenecks(store)
        assert [r["id"] for r in ranked] == [b_high["id"], b_low["id"]]
        assert ranked[0]["cumulative_error_share_pct"] == 64.0
        assert ranked[1]["cumulative_error_share_pct"] == 76.0

        # SOTA Scout offline fixture + SQLite cache verification + METH-XXX vault creation
        fixtures = [
            {
                "title": "Model Predictive Night Pre-Cooling for Commercial HVAC",
                "abstract": "Receding horizon MPC barrier cuts desert cooling regret by 40%.",
                "year": 2025,
                "venue": "NeurIPS",
                "citations": 38,
                "url": "https://arxiv.org/abs/2501.00001",
                "source": "arxiv",
            },
            {
                "title": "Old Legacy Heuristic",
                "abstract": "Outdated rule.",
                "year": 2018,
                "venue": "Workshop",
                "citations": 2,
                "url": "",
                "source": "arxiv",
            },
        ]
        s_res = scout_sota_papers(
            store,
            query="desert night pre-cooling MPC",
            min_year=2023,
            bottleneck_id=b_high["id"],
            save_top_k=1,
            offline_fixtures=fixtures,
        )
        assert len(s_res["papers"]) == 1
        assert len(s_res["saved_method_cards"]) == 1
        meth_id = s_res["saved_method_cards"][0]["id"]
        assert meth_id == "METH-001"
        assert (ws / "memory" / "07_METHOD_VAULT").is_dir()

        # Verify SQLite HTTP cache prevents network call on cached key
        import hashlib

        ckey = hashlib.sha256(b"arxiv:cached query:6").hexdigest()[:24]
        _cache_put(store, ckey, "arxiv", "cached query", fixtures[:1])
        cached_res = scout_sota_papers(store, query="cached query", sources=("arxiv",), min_year=2023)
        assert cached_res["cache_hits"] == 1
        assert len(cached_res["papers"]) == 1

        # Strict Occam Gatekeeper: reject ungrounded & kitchen-sink multi-variable bloat
        with pytest.raises(ValueError, match="Bottleneck-First Gate"):
            evaluate_occam_gate(store, "Random Idea", "Add GNN", strict_occam=True)

        with pytest.raises(ValueError, match="Occam Single-Variable Gate"):
            evaluate_occam_gate(
                store,
                "Kitchen-Sink Transformer + GNN + Kalman + PPO Rewrite",
                "Combine cross_attention transformer with message_passing gnn, kalman filter, and ppo policy",
                bottleneck_id=b_high["id"],
                strict_occam=True,
            )

        # Clean single-variable hypothesis passes with high Occam ROI
        clean_prop = execute_mcp_tool(
            "supermemory_diagnose_bottleneck",
            {
                "workspace": str(ws),
                "action": "propose_hypothesis",
                "title": "Night Guard Interlock on Desert Slab",
                "what_changes": "Add 25-line guard_hi clamp when ambient temperature exceeds comfort band.",
                "bottleneck_id": b_high["id"],
                "est_loc": 25,
                "coupled_vars": 1,
            },
        )
        assert clean_prop["occam"]["occam_roi"] > 5.0


def test_pillar4_fast_dag_glob_leases_early_kill_cli_and_http(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(tmp_path / "global_p4"))
    ws = tmp_path / "dag_lab"
    init_workspace(ws, project_name="DAGLab")

    assert cli_main([
        "bottleneck", "-w", str(ws), "add",
        "--title", "Tail Latency Spike", "--slice", "p99_batch",
        "--share", "50", "--ceiling", "0.20", "--rq", "Does batching cut p99?",
    ]) == 0

    with GraphStore(ws) as store:
        sprint = plan_research_sprint(store, goal="Eliminate p99 spike", bottleneck_id="BNK-001")
        assert len(sprint["tasks"]) == 6
        tel0 = dag_telemetry(store)
        assert len(tel0["ready_parallel_task_ids"]) == 3

        # Claim all 3 parallel Wave-1 tasks concurrently; Wave-2 must stay blocked until Wave-1 finishes
        c1 = claim_next_task(store, "w1", role="bottleneck-profiler")
        c2 = claim_next_task(store, "w2", role="sota-scout")
        c3 = claim_next_task(store, "w3", role="memory-curator")
        assert c1 and c2 and c3
        assert claim_next_task(store, "w4") is None

        for cid in (c1["task_id"], c2["task_id"], c3["task_id"]):
            complete_task(store, cid, status="DONE", receipt={"note": "x" * 600})
        t1 = store.conn.execute("SELECT receipt_json FROM agent_tasks WHERE task_id=?", (c1["task_id"],)).fetchone()
        assert len(json.loads(str(t1["receipt_json"]))["note"]) <= 160

        # Test Early-Kill Cascade: killing Wave-2 architect cancels downstream challenger & builder
        w2_arch = claim_next_task(store, "arch")
        assert w2_arch and w2_arch["role"] == "hypothesis-architect"
        kill_out = complete_task(store, w2_arch["task_id"], status="EARLY_KILLED", receipt={"reason": "Low ROI"})
        assert len(kill_out["cascaded_cancelled"]) == 2

        # Test Glob Lease Lock conflict vs disjoint parallel slices
        enqueue_task(store, role="slice-builder", title="Slice A", brief="A", wave=3, locked_globs=["src/core/**"], task_id="SLICE-A")
        enqueue_task(store, role="slice-builder", title="Slice B Overlap", brief="B", wave=3, locked_globs=["src/core/ranker.py"], task_id="SLICE-B")
        enqueue_task(store, role="slice-builder", title="Slice C Disjoint", brief="C", wave=3, locked_globs=["src/ui/**"], task_id="SLICE-C")
        s_first = claim_next_task(store, "builder-1", role="slice-builder")
        s_second = claim_next_task(store, "builder-2", role="slice-builder")
        assert s_first and s_first["task_id"] == "SLICE-A"
        assert s_second and s_second["task_id"] == "SLICE-C"  # SLICE-B skipped due to glob conflict!

    # Verify HTTP API v3.0 endpoints
    srv, port = create_http_server(ws, host="127.0.0.1", port=0)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/scout",
            data=json.dumps({"action": "register_card", "title": "HTTP Card", "core_mechanism": "Fast batching", "bottleneck_id": "BNK-001"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert json.loads(resp.read().decode())["method_card"]["id"] == "METH-001"
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/graph", timeout=5) as resp:
            gpayload: Dict[str, Any] = json.loads(resp.read().decode())
            assert len(gpayload["bottlenecks"]) == 1
            assert len(gpayload["method_cards"]) == 1
            assert len(gpayload["agent_tasks"]) >= 6
    finally:
        srv.shutdown()
        srv.server_close()
