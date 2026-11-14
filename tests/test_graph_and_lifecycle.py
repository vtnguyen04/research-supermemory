"""Tests for GraphStore, Snapshot Hydration, Hybrid Recall, Proposals, and Scientific Experiments."""

from __future__ import annotations

from pathlib import Path

import pytest

from supermemory.bootstrap import init_workspace
from supermemory.graph.query_engine import QueryEngine
from supermemory.lifecycle.manager import LifecycleManager
from supermemory.models import EdgeType
from supermemory.storage.sqlite_store import GraphStore
from supermemory.sync.agent_adapters import generate_handoff_briefing
from supermemory.sync.markdown_compiler import MarkdownCompiler


def test_init_recall_and_git_clone_snapshot_hydration(tmp_path: Path) -> None:
    res = init_workspace(tmp_path, project_name="AlphaHarness", max_lines=300, active_goal="Win Top 1")
    assert Path(res["workspace"]) == tmp_path.resolve()
    assert (tmp_path / "memory" / "00_MEMORY_GRAPH.md").is_file()
    assert (tmp_path / "memory" / "01_ACTIVE_STATE.md").is_file()
    assert (tmp_path / "memory" / "02_CONSTITUTION_AND_LESSONS.md").is_file()
    assert (tmp_path / "memory" / "graph_snapshot.json").is_file()

    with GraphStore(tmp_path) as store:
        lm = LifecycleManager(store)
        dead = lm.register_idea(
            title="Regex Keyword Heuristic on Public Set",
            summary="Manually tune regex rules for observed test questions.",
            status="REJECTED",
            rejection_reason="Overfits public set and violates LAW-01 zero-hardcode.",
        )
        assert dead["node"]["id"] == "IDEA-001"
        MarkdownCompiler(store).compile_all()

    # Simulate fresh git clone / deleted SQLite binary DB: GraphStore MUST auto-hydrate from snapshot!
    db_file = tmp_path / ".supermemory" / "supermemory.db"
    assert db_file.is_file()
    for f in (tmp_path / ".supermemory").glob("supermemory.db*"):
        f.unlink()
    assert not db_file.exists()

    with GraphStore(tmp_path) as restored:
        assert restored.get_meta("project_name") == "AlphaHarness"
        idea = restored.get_node("IDEA-001")
        assert idea is not None
        assert idea.status == "REJECTED"

        # Proposing a similar idea must immediately surface Anti-Repeat Dead-End Warning!
        lm2 = LifecycleManager(restored)
        second = lm2.register_idea(
            title="Regex Heuristic Rules for Test Queries",
            summary="Tune regex keyword heuristic on test questions.",
            status="SEED",
        )
        assert any("IDEA-001" in w for w in second["prior_warnings"])

        rec = QueryEngine(restored).recall("regex keyword heuristic test", hops=1)
        assert rec["match_count"] >= 2
        assert any("DEAD-END IDEA `IDEA-001`" in w for w in rec["anti_repeat_warnings"])


def test_proposal_audit_gate_and_monotonic_experiments(tmp_path: Path) -> None:
    init_workspace(tmp_path, project_name="SciLab")
    with GraphStore(tmp_path) as store:
        lm = LifecycleManager(store)
        prop = lm.create_proposal(
            title="Hybrid BM25 + Dense Reranker",
            why="Pure lexical search misses semantic paraphrases.",
            what_changes="Add cross-encoder reranking stage on top-20 candidates.",
            design_notes="Keep latency < 80ms via batching.",
            tasks=["Add reranker module", "Run 5-fold CV benchmark"],
            idea_ids=["LAW-03"],
        )
        pid = prop["proposal_id"]
        assert pid == "PROP-001"
        assert prop["stage"] == "DESIGNED"

        lm.advance_proposal(pid, "IMPLEMENTING", note="Started vertical slice")
        # LAW-06 Gate: Attempting to ARCHIVE before Challenger/VictoryAuditor sign-off MUST fail!
        with pytest.raises(ValueError, match="LAW-06 Gate"):
            lm.advance_proposal(pid, "ARCHIVED")

        # Log Baseline + Improved + Regressed Scientific Experiments
        e1 = lm.log_experiment(
            track="retrieval",
            title="BM25 Baseline",
            hypothesis="Establish clean lexical baseline.",
            single_var_diff="Initial BM25 k1=1.5 b=0.75",
            proposal_id=pid,
            cv_score=0.720,
            test_score=0.715,
            verdict="KEEP",
        )
        assert e1["exp_id"] == "EXP-RETRIE-001"
        assert e1["delta_vs_baseline"] is None

        e2 = lm.log_experiment(
            track="retrieval",
            title="Add Cross-Encoder Top-20",
            hypothesis="Reranking top-20 improves Recall@5.",
            single_var_diff="Enable BGE reranker on top-20",
            baseline_id=e1["exp_id"],
            proposal_id=pid,
            cv_score=0.768,
            test_score=0.760,
            verdict="KEEP",
        )
        assert e2["delta_vs_baseline"] == pytest.approx(0.045)
        assert e2["regression_detected"] is False
        edges_e2 = store.list_edges(e2["exp_id"])
        assert any(ed.relation == EdgeType.IMPROVES_OVER.value and ed.target_id == e1["exp_id"] for ed in edges_e2)

        e3 = lm.log_experiment(
            track="retrieval",
            title="Aggressive Truncation 64 Tokens",
            hypothesis="Truncate passages to 64 tokens for speed.",
            single_var_diff="max_passage_tokens 512 -> 64",
            baseline_id=e2["exp_id"],
            cv_score=0.710,
            test_score=0.705,
            verdict="REVERT",
            post_mortem="Drops tail context; reverted immediately.",
        )
        assert e3["delta_vs_baseline"] == pytest.approx(-0.055)
        assert e3["regression_detected"] is True
        edges_e3 = store.list_edges(e3["exp_id"])
        assert any(ed.relation == EdgeType.REGRESSED_FROM.value and ed.target_id == e2["exp_id"] for ed in edges_e3)

        # Independent VictoryAuditor approves PROP-001 -> now ARCHIVED succeeds!
        audit_node = lm.record_audit_verdict(
            target_id=pid,
            auditor_role="VictoryAuditor",
            verdict="APPROVE",
            findings="Verified +0.045 monotonic gain with zero data leakage.",
        )
        assert audit_node["status"] == "APPROVE"
        archived = lm.advance_proposal(pid, "ARCHIVED", note="Merged to main")
        assert archived.status == "ARCHIVED"

        compiled = MarkdownCompiler(store).compile_all()
        assert len(Path(compiled["active_state"]).read_text(encoding="utf-8").splitlines()) < 150
        assert len(Path(compiled["constitution"]).read_text(encoding="utf-8").splitlines()) < 200
        handoff = generate_handoff_briefing(store)
        assert handoff.is_file()
        assert "EXP-RETRIE-002" in handoff.read_text(encoding="utf-8")
