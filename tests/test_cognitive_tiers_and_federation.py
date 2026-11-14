"""End-to-end tests for Cognitive Tiers, Global/Local Federation, Semantic Checkpoints & UI Merge."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from supermemory.bootstrap import init_workspace
from supermemory.cognitive.federation import federated_recall, list_registered_workspaces
from supermemory.cognitive.tiers import classify_tier, compute_tier_telemetry
from supermemory.hooks.runner import dispatch_hook
from supermemory.lifecycle.manager import LifecycleManager
from supermemory.mcp.tool_defs import execute_mcp_tool
from supermemory.storage.sqlite_store import GraphStore
from supermemory.ui.server import create_http_server


def test_failed_experiment_requires_insight_and_warns_future_turns(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(tmp_path / "global_sm"))
    proj = tmp_path / "proj_exp"
    init_workspace(proj, project_name="ExpInsightProj")

    with GraphStore(proj) as store:
        lm = LifecycleManager(store)
        # Lazy REVERT without post_mortem/insights MUST be rejected!
        with pytest.raises(ValueError, match="LAW-06 Gate"):
            lm.log_experiment(
                track="nlp",
                title="Strip Vietnamese Diacritics",
                hypothesis="ASCII normalization speeds up tokenizer",
                single_var_diff="strip_accents=True",
                verdict="REVERT",
                post_mortem="",
            )

        logged = lm.log_experiment(
            track="nlp",
            title="Strip Vietnamese Diacritics",
            hypothesis="ASCII normalization speeds up tokenizer",
            single_var_diff="strip_accents=True",
            cv_score=0.61,
            verdict="REVERT",
            post_mortem="Collapses homographs (ba/bà/bá) causing -14% F1 drop.",
            insights=["Preserve UTF-8 NFC Vietnamese diacritics in lexical + dense retrieval."],
        )
        assert logged["observation_ids"] == ["OBS-001"]
        obs = store.get_node("OBS-001")
        assert obs is not None
        assert classify_tier(obs) == "SEMANTIC"

    rec = federated_recall("Vietnamese diacritics tokenizer", local_ws=proj)
    assert any("OBS-001" in w or "EXP-NLP-001" in w for w in rec["anti_repeat_warnings"])


def test_zero_regex_semantic_turn_attestation_and_live_rule_sync(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(tmp_path / "global_sm"))
    proj = tmp_path / "proj_sem"
    init_workspace(proj, project_name="SemanticProj")
    conv = "conv-sem-1"

    # Subtle phrasing with ZERO regex scolding/rule keywords!
    subtle_msg = "Ủa sao chỗ tính điểm lại dùng print trực tiếp thế nhỉ, nhìn log rối quá."
    pre = dispatch_hook(
        "PreInvocation",
        {"conversationId": conv, "workspacePaths": [str(proj)], "invocationNum": 1, "initialNumSteps": 4, "lastUserInput": subtle_msg},
    )
    assert "SEMANTIC MEMORY TRIAGE ACTIVE" in pre["injectSteps"][0]["systemMessage"]["systemMessage"]

    # Agent forgets to call any supermemory_* tool -> Stop hook catches it without needing regex!
    stop_1 = dispatch_hook(
        "Stop",
        {"conversationId": conv, "workspacePaths": [str(proj)], "continuationActive": False, "terminationReason": "NO_TOOL_CALL"},
    )
    assert stop_1["decision"] == "continue"
    assert "SEMANTIC TURN-ATTESTATION REQUIRED" in stop_1["reason"]

    # Next turn: Agent proactively saves the subtle rule via MCP -> auto-updates AGENTS.md + PreToolUse Gate!
    dispatch_hook(
        "PreInvocation",
        {"conversationId": conv, "workspacePaths": [str(proj)], "invocationNum": 2, "initialNumSteps": 8, "lastUserInput": "Nhớ dùng logger chuẩn nhé, đừng in bừa ra stdout."},
    )
    execute_mcp_tool(
        "supermemory_record_lesson",
        {
            "workspace": str(proj),
            "title": "Use structured logger instead of raw print",
            "mistake": "Used print() in scoring pipeline",
            "root_cause": "Polluted stdout JSON protocol",
            "prevention_rule": "Always use structured logging instead of print()",
            "new_law_title": "Structured Logging Only (No Raw Print)",
            "forbid_regex": r"\bprint\s*\(",
            "target_glob": "src/**/*.py",
        },
    )

    # Verify AGENTS.md was live-updated AND Stop immediately allows AND PreToolUse blocks print()!
    agents_md = (proj / "AGENTS.md").read_text(encoding="utf-8")
    assert "Structured Logging Only" in agents_md

    stop_2 = dispatch_hook(
        "Stop",
        {"conversationId": conv, "workspacePaths": [str(proj)], "continuationActive": False, "terminationReason": "NO_TOOL_CALL"},
    )
    assert stop_2["decision"] == "allow"

    blocked = dispatch_hook(
        "PreToolUse",
        {
            "workspacePaths": [str(proj)],
            "toolCall": {"name": "write_file", "args": {"Path": str(proj / "src" / "score.py"), "Content": "print('hi')\n"}},
        },
    )
    assert blocked["decision"] == "deny"


def test_local_isolation_global_promotion_uninitialized_repo_and_ui_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(tmp_path / "global_sm"))
    proj_a = tmp_path / "project_a"
    proj_b = tmp_path / "project_b"
    uninit_repo = tmp_path / "legacy_no_supermemory"
    uninit_repo.mkdir(parents=True)

    init_workspace(proj_a, project_name="ProjectA")
    init_workspace(proj_b, project_name="ProjectB")

    ws_list = list_registered_workspaces()
    assert len(ws_list) == 3  # Global + ProjectA + ProjectB

    # ProjectA logs a private experiment AND a reusable insight
    execute_mcp_tool(
        "supermemory_log_experiment",
        {
            "workspace": str(proj_a),
            "track": "rag",
            "title": "Secret ProjectA Chunking 256",
            "hypothesis": "256 tokens improves recall",
            "single_var_diff": "chunk=256",
            "cv_score": 0.81,
            "insights": ["SQLite WAL busy_timeout=5000ms prevents lock contention under parallel workers."],
        },
    )
    execute_mcp_tool(
        "supermemory_log_experiment",
        {
            "workspace": str(proj_a),
            "track": "rag",
            "title": "ProjectA Chunking 512",
            "hypothesis": "512 tokens test",
            "single_var_diff": "chunk=512",
            "cv_score": 0.83,
        },
    )

    # ProjectB must NOT see ProjectA's private experiment!
    rec_b_before = federated_recall("Secret ProjectA Chunking", local_ws=proj_b)
    assert not any("Secret ProjectA" in r["title"] for r in rec_b_before["results"])

    # Launch Web UI Server on ProjectA: test Interactive Merge (/api/consolidate) + Promote (/api/promote)
    srv, port = create_http_server(proj_a, host="127.0.0.1", port=0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{port}"
        merge_req = Request(
            f"{base}/api/consolidate",
            data=json.dumps({
                "scope": "local",
                "source_ids": ["EXP-RAG-001", "EXP-RAG-002"],
                "target_tier": "SEMANTIC",
                "title": "Optimal RAG Chunking Range (256-512)",
                "summary": "512-token chunks outperform 256 (+0.02 CV); raw runs consolidated.",
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        merge_out = json.loads(urlopen(merge_req).read().decode("utf-8"))
        assert merge_out["created_node"]["id"] == "SEM-001"
        assert set(merge_out["consolidated_sources"]) == {"EXP-RAG-001", "EXP-RAG-002"}

        # Promote OBS-001 (SQLite WAL busy_timeout) from ProjectA -> Global via Web UI API!
        prom_req = Request(
            f"{base}/api/promote",
            data=json.dumps({"scope": "local", "node_id": "OBS-001"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        prom_out = json.loads(urlopen(prom_req).read().decode("utf-8"))
        assert prom_out["global_id"].startswith("GLB-")

        # Switch Web UI scope to Global and verify promoted node appears in Global Graph!
        g_graph = json.loads(urlopen(f"{base}/api/graph?scope=global").read().decode("utf-8"))
        assert g_graph["is_global"] is True
        assert any(n["id"] == prom_out["global_id"] for n in g_graph["nodes"])
    finally:
        srv.shutdown()
        srv.server_close()

    # Now ProjectB AND uninitialized repo BOTH recall the Global SQLite insight, WITHOUT polluting uninit_repo!
    rec_b_after = federated_recall("SQLite WAL busy_timeout", local_ws=proj_b)
    assert any(r["scope"] == "GLOBAL" and "busy_timeout" in r["summary"] for r in rec_b_after["results"])

    uninit_start = dispatch_hook("SessionStart", {"workspacePaths": [str(uninit_repo)]})
    assert "GLOBAL HARNESS ACTIVE" in uninit_start["injectSteps"][0]["systemMessage"]["systemMessage"]
    assert not (uninit_repo / ".supermemory").exists()
    assert not (uninit_repo / "memory").exists()

    with GraphStore(proj_a) as st_a:
        tel = compute_tier_telemetry(st_a)
        assert tel["consolidated_episodes"] == 2
        assert tel["active_prompt_tokens"] < 850
