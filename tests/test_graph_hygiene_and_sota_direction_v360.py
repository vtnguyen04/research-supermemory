"""Regression suite for SuperMemory v3.6.0: Zero-Orphan Graph Hygiene, L2 Compaction & Minimization SOTA."""

from __future__ import annotations

from pathlib import Path

from supermemory.bootstrap import init_workspace
from supermemory.cognitive.outcome_ledger import infer_metric_direction
from supermemory.cognitive.tiers import auto_consolidate_episodic, build_tiered_capsule
from supermemory.hooks.runner import dispatch_hook
from supermemory.kernel import execute_command
from supermemory.lifecycle.manager import LifecycleManager
from supermemory.models import MemoryNode, NodeType
from supermemory.research.bottleneck_engine import diagnose_bottleneck
from supermemory.research.orchestrator import clear_completed_tasks, plan_research_sprint
from supermemory.storage.sqlite_store import GraphStore
from supermemory.sync.agent_adapters import generate_handoff_briefing
from supermemory.ui.api_research import enrich_graph_payload_v3


def _degree_of(store: GraphStore, node_id: str) -> int:
    row = store.conn.execute(
        "SELECT COUNT(*) AS c FROM edges WHERE source_id = ? OR target_id = ?",
        (node_id, node_id),
    ).fetchone()
    return int(row["c"]) if row else 0


def test_zero_orphan_checkpoint_and_near_duplicate_supersession(tmp_path: Path) -> None:
    ws = tmp_path / "ws_orphan"
    init_workspace(ws, project_name="OrphanGuard")
    with GraphStore(ws) as store:
        bnk = diagnose_bottleneck(
            store,
            title="Overnight Boiler Micro-Pulse Cycling",
            evidence_slice="82% gas regret from 6-step valve pulses",
            error_share_pct=82.0,
            ceiling_gain=0.0012,
            falsifiable_rq="Does wide-band Schmitt hysteresis eliminate overnight gas pulses?",
        )["bottleneck"]["id"]

        r1 = execute_command(
            "checkpoint",
            {"insights": [f"Schmitt Hysteresis Sweep: On {bnk}, widening deadband to 14K cut overnight pulses by 74%."]},
            store=store,
        )
        obs1 = r1["captured"]["id"]
        assert _degree_of(store, obs1) >= 1

        # Insight with zero explicit IDs still links to active open bottleneck/anchor (0 orphans)
        r2 = execute_command(
            "checkpoint",
            {"insights": ["Morning Chiller Ramp: Delayed precooling avoids zero-occupancy thermal losses."]},
            store=store,
        )
        obs2 = r2["captured"]["id"]
        assert _degree_of(store, obs2) >= 1

        # Near-duplicate updated insight automatically supersedes obs1
        r3 = execute_command(
            "checkpoint",
            {"insights": [f"Schmitt Hysteresis Sweep Updated: On {bnk}, widening deadband to 16K cut overnight pulses by 81%."]},
            store=store,
        )
        obs3 = r3["captured"]["id"]
        assert obs1 in r3["superseded_ids"]
        old_nd = store.get_node(obs1)
        assert old_nd is not None and old_nd.status == "SUPERSEDED"
        assert _degree_of(store, obs3) >= 1


def test_l2_observation_compaction_and_retroactive_orphan_repair(tmp_path: Path) -> None:
    ws = tmp_path / "ws_compact"
    init_workspace(ws, project_name="L2Compact")
    with GraphStore(ws) as store:
        bnk_id = diagnose_bottleneck(
            store,
            title="High-Frequency Actuator Jitter",
            evidence_slice="64% cubic fan penalty",
            error_share_pct=64.0,
            ceiling_gain=0.04,
            falsifiable_rq="Can velocity damping cut cubic fan spikes?",
        )["bottleneck"]["id"]

        # Simulate a legacy unlinked degree-0 ALGO node
        store.upsert_node(
            MemoryNode(
                id="ALGO-099",
                node_type=NodeType.ALGORITHM.value,
                title=f"Legacy Velocity Damper for {bnk_id}",
                status="SEED",
                summary=f"Targets {bnk_id} via quadratic slew penalty.",
                content=" quadratic slew penalty ",
            )
        )
        assert _degree_of(store, "ALGO-099") == 0

        # Mint 28 distinct positive observations + 1 FAILURE_INSIGHT
        for idx in range(28):
            oid = f"OBS-{idx + 1:03d}"
            store.upsert_node(
                MemoryNode(
                    id=oid,
                    node_type=NodeType.OBSERVATION.value,
                    title=f"Observation slice {idx} on {bnk_id}",
                    status="SCIENTIFIC_INSIGHT",
                    summary=f"Empirical slice {idx} metric note on {bnk_id}",
                    content=f"Detail {idx} referencing {bnk_id}",
                    metadata={"track": "ctrl"},
                )
            )
        store.upsert_node(
            MemoryNode(
                id="OBS-900",
                node_type=NodeType.OBSERVATION.value,
                title="Failure Warning: Aggressive clip diverges",
                status="FAILURE_INSIGHT",
                summary="Hard clipping causes oscillation.",
                content="Never hard-clip valve.",
            )
        )

        res = auto_consolidate_episodic(store, min_cluster_size=4)
        assert res["repaired_orphans"] >= 1
        assert _degree_of(store, "ALGO-099") >= 1
        assert len(res["created_semantic_nodes"]) >= 1

        fail_obs = store.get_node("OBS-900")
        assert fail_obs is not None and fail_obs.status == "FAILURE_INSIGHT"
        cons_obs = [
            n for n in store.list_nodes(node_types=[NodeType.OBSERVATION.value], limit=100)
            if n.status == "CONSOLIDATED" and (n.metadata or {}).get("consolidated")
        ]
        assert len(cons_obs) >= 12


def test_minimization_sota_direction_and_info_gap_sprint(tmp_path: Path) -> None:
    ws = tmp_path / "ws_min_sota"
    init_workspace(ws, project_name="MinRegret")
    with GraphStore(ws) as store:
        lm = LifecycleManager(store)
        lm.log_experiment(
            track="val16",
            exp_id="EXP-BASE",
            title="PID Water Baseline",
            hypothesis="Baseline PID regret",
            single_var_diff="Default PID gains",
            test_score=0.0541,
            verdict="KEEP",
        )
        lm.log_experiment(
            track="val16",
            exp_id="EXP-WIN-1",
            baseline_id="EXP-BASE",
            title="Schmitt Reservoir Glide",
            hypothesis="Reduce boiler cycling regret",
            single_var_diff="Add [328K, 349.5K] hysteresis",
            test_score=0.0041,
            verdict="VICTORY_CONFIRMED",
        )
        lm.log_experiment(
            track="val16",
            exp_id="EXP-BAD-2",
            baseline_id="EXP-WIN-1",
            title="Over-Tight Deadband",
            hypothesis="Test 2K deadband",
            single_var_diff="Narrow deadband to 2K",
            test_score=0.0089,
            verdict="REVERT",
            post_mortem="2K deadband triggered constant boiler short-cycling.",
        )

        assert infer_metric_direction(store) == "lower_is_better"
        capsule = build_tiered_capsule(store)
        assert "Best SOTA: `EXP-WIN-1` (val16 = 0.0041)" in capsule
        assert "Best SOTA: `EXP-BASE`" not in capsule

        payload = enrich_graph_payload_v3(store, {"nodes": []})
        assert payload["metric_direction"] == "lower_is_better"
        assert payload["metric_direction_by_track"]["val16"] == "lower_is_better"

        # Empty vault -> Wave 1 includes sota-scout
        sp1 = plan_research_sprint(store, goal="Cut cooling regret")
        assert sp1["tasks"][1]["role"] == "sota-scout"

        # Add untried ALGO -> Wave 1 audits vault candidates instead of forcing arXiv search
        clear_completed_tasks(store)
        lm.register_idea(
            title="Dual-Horizon Comfort Barrier",
            summary="Soft barrier on indoor operative temperature",
            is_algorithm=True,
        )
        sp2 = plan_research_sprint(store, goal="Cut cooling regret")
        assert sp2["tasks"][1]["role"] == "memory-curator"
        assert "Untried Vault Mechanisms" in sp2["tasks"][1]["title"]


def test_auto_recall_precision_and_handoff_newest_slicing(tmp_path: Path) -> None:
    ws = tmp_path / "ws_handoff"
    init_workspace(ws, project_name="HandoffPrecision")
    with GraphStore(ws) as store:
        lm = LifecycleManager(store)
        store.upsert_node(
            MemoryNode(
                id="OBS-UI-COLOR",
                node_type=NodeType.OBSERVATION.value,
                title="Daylight Canvas Palette Contrast",
                status="SCIENTIFIC_INSIGHT",
                summary="Use warm alabaster background and dark ink borders in CSS.",
                content="CSS color palette notes",
            )
        )
        # Unrelated prompt sharing only short function words/3-grams must NOT inject OBS-UI-COLOR
        out = dispatch_hook(
            "PreInvocation",
            {
                "cwd": str(ws),
                "conversationId": "conv-prec-1",
                "invocationNum": 1,
                "initialNumSteps": 2,
                "lastUserInput": "Hiện tại những thực nghiệm đang chạy có kết quả thế nào rồi?",
            },
        )
        txt = str(out)
        assert "OBS-UI-COLOR" not in txt

        for i in range(1, 9):
            lm.log_experiment(
                track="main",
                exp_id=f"EXP-SEQ-{i:03d}",
                title=f"Sequential Run {i}",
                hypothesis=f"Test step {i}",
                single_var_diff=f"Param={i}",
                cv_score=float(i) * 0.1,
                verdict="KEEP",
            )
        for j in range(1, 13):
            store.upsert_node(
                MemoryNode(
                    id=f"LESSON-{j:03d}",
                    node_type=NodeType.LESSON.value,
                    title=f"Critical Trap {j}",
                    status="CONSOLIDATED",
                    summary=f"Never repeat mistake {j}",
                    created_at=f"2026-11-17T00:{j:02d}:00+00:00",
                )
            )
        hpath = generate_handoff_briefing(store)
        md = hpath.read_text(encoding="utf-8")
        assert "EXP-SEQ-008" in md
        assert "EXP-SEQ-001" not in md
        assert "LESSON-012" in md
