"""Tests for v3.0.3 Zero-Bloat Rule Deduplication, 2-Stage Progressive Recall & Hard Token Budgets."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from supermemory.bootstrap import init_workspace
from supermemory.cognitive.tiers import _est_tokens, build_tiered_capsule
from supermemory.mcp.tool_defs import execute_mcp_tool
from supermemory.models import MemoryNode, NodeType
from supermemory.storage.sqlite_store import GraphStore


def test_v303_zero_bloat_dedup_progressive_recall_capsule_cap_and_event_prune(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(tmp_path / "global_v303"))
    ws = tmp_path / "lean_repo"
    sib = tmp_path / "sib_repo"
    (ws / ".agents" / "rules").mkdir(parents=True)
    (ws / "GEMINI.md").write_text("# OLD — SUPERMEMORY CONSTITUTION\nbloated duplicate", encoding="utf-8")
    (ws / ".agents" / "rules" / "00_supermemory_constitution.md").write_text("bloated rule", encoding="utf-8")

    init_workspace(ws, project_name="LeanRepo")
    init_workspace(sib, project_name="SibRepo")

    # 1. Duplicate rules purged; canonical AGENTS.md < 420 tokens; CLAUDE.md is @AGENTS.md pointer
    assert (ws / "AGENTS.md").is_file()
    assert not (ws / "GEMINI.md").exists()
    assert not (ws / ".agents" / "rules" / "00_supermemory_constitution.md").exists()
    assert (ws / "CLAUDE.md").read_text(encoding="utf-8").strip() == "@AGENTS.md"
    assert _est_tokens((ws / "AGENTS.md").read_text(encoding="utf-8")) < 420

    # Custom hand-written GEMINI.md must NEVER be deleted
    (ws / "GEMINI.md").write_text("# Custom Team Notes\nDo not touch.", encoding="utf-8")
    init_workspace(ws, project_name="LeanRepo")
    assert (ws / "GEMINI.md").is_file()

    # 2. 2-Stage Progressive Recall stays < 3200 bytes (zero spill) & expands Stage-2 node_id
    execute_mcp_tool(
        "scout_sota",
        {
            "workspace": str(sib),
            "action": "register_card",
            "title": "Sparse Attention KV-Cache Eviction",
            "core_mechanism": "Evicts low-utility KV heads with O(1) rolling heavy-hitter sketches.",
            "venue": "ICLR",
            "year": 2025,
        },
    )
    with GraphStore(ws) as store:
        for idx in range(12):
            store.upsert_node(
                MemoryNode(
                    id=f"OBS-BULK-{idx:02d}",
                    node_type=NodeType.OBSERVATION.value,
                    title=f"KV-Cache Attention Compression Observation {idx} " + ("x" * 60),
                    status="FAILURE_INSIGHT",
                    summary="Verbose failure note on attention cache eviction " + ("y" * 180),
                    content="Full detailed markdown body " + ("z" * 900),
                )
            )
        # 3. Hard Capsule Token Budget invariant under extreme saturation + custom tight cap
        for idx in range(6):
            store.upsert_node(
                MemoryNode(
                    id=f"BNK-SAT-{idx}",
                    node_type=NodeType.BOTTLENECK.value,
                    title=f"Heavy Memory Bottleneck Slice {idx} " + ("b" * 50),
                    metadata={"error_share_pct": 40.0 + idx, "ceiling_gain": 0.2},
                )
            )
            store.upsert_node(
                MemoryNode(
                    id=f"PROP-SAT-{idx}",
                    node_type=NodeType.PROPOSAL.value,
                    title=f"Active Proposal Candidate {idx} " + ("p" * 50),
                    status="IMPLEMENTING",
                )
            )
        cap_default = build_tiered_capsule(store, query="attention cache")
        cap_tight = build_tiered_capsule(store, query="attention cache", max_tokens=200)
        assert _est_tokens(cap_default) <= 800
        assert _est_tokens(cap_tight) <= 200
        assert "SUPERMEMORY CONSTITUTIONAL HARNESS ACTIVE" in cap_tight

        # 4. SQLite Event Log Ring-Buffer auto-prunes at 2,000 rows
        for idx in range(2150):
            store.log_event("BENCH_TICK", f"E-{idx}", "tick")
        cnt_auto = store.conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
        assert cnt_auto < 2100
        store.prune_events(max_events=2000)
        assert store.conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"] == 2000

    idx_recall = execute_mcp_tool(
        "recall",
        {"workspace": str(ws), "query": "KV-Cache Attention Eviction", "include_siblings": True},
    )
    assert idx_recall["stage"] == "INDEX_COMPACT"
    assert len(json.dumps(idx_recall, ensure_ascii=False, indent=2)) < 3200
    detail_recall = execute_mcp_tool(
        "recall",
        {"workspace": str(ws), "node_id": "METH-001", "include_siblings": True},
    )
    assert detail_recall["stage"] == "NODE_DETAIL"
    assert detail_recall["scope"] == "SIBLING:SibRepo"
    assert "heavy-hitter" in detail_recall["node"]["content"]
