"""Adversarial Red-Team Regression Suite (`F-01..F-16`, `C1..C13`) for SuperMemory Harness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from supermemory.bootstrap import init_workspace
from supermemory.cognitive.outcome_ledger import select_best_sota_experiment
from supermemory.cognitive.tiers import build_tiered_capsule
from supermemory.hooks.runner import dispatch_hook
from supermemory.hooks.turn_tracker import _classify_shell_command
from supermemory.kernel import execute_command
from supermemory.mcp.server import handle_rpc_request
from supermemory.models import MemoryNode, NodeType
from supermemory.research.kanban_digest import build_kanban_board_digest
from supermemory.self_learning.detector import SelfLearningDetector
from supermemory.storage.snapshot_io import export_snapshot, get_session_state, import_snapshot
from supermemory.storage.sqlite_store import GraphStore


def test_large_graph_visibility_fts_stopwords_multitrack_sota_and_snapshot_safety(tmp_path: Path) -> None:
    """Verify F-01 (>40 consolidated OBS/PROP blindness), F-02 (50-word FTS), F-03 (SOTA track), and C4 (snapshot)."""
    ws = tmp_path / "scale_proj"
    init_workspace(ws, project_name="ScaleProj")
    w = str(ws)

    with GraphStore(ws) as store:
        for i in range(1, 46):
            store.upsert_node(
                MemoryNode(
                    id=f"OBS-{i:03d}", node_type=NodeType.OBSERVATION.value,
                    title=f"Old Insight {i}", status="CONSOLIDATED", summary=f"Old summary {i}",
                    priority=88, metadata={"consolidated": True},
                ),
                log_event=False,
            )
            store.upsert_node(
                MemoryNode(
                    id=f"PROP-{i:03d}", node_type=NodeType.PROPOSAL.value,
                    title=f"Archived Spec {i}", status="ARCHIVED", summary=f"Done {i}", priority=88,
                ),
                log_event=False,
            )
        store.upsert_node(
            MemoryNode(
                id="OBS-049", node_type=NodeType.OBSERVATION.value,
                title="Fresh Jacobian Breakthrough thermograph_jacobian_v11",
                status="SCIENTIFIC_INSIGHT",
                summary="Exact occupancy-weighted thermograph_jacobian_v11 cut cooling regret to 0.0038.",
                content="Full multi-paragraph body > 400 chars " + ("detail " * 70),
                priority=88,
            ),
            log_event=False,
        )
        store.upsert_node(
            MemoryNode(
                id="PROP-050", node_type=NodeType.PROPOSAL.value,
                title="Active Wave-3 Controller", status="IMPLEMENTING",
                summary="Ship controller", priority=88,
                metadata={"tasks": ["Implement controller", "Run 5-suite gate"], "tasks_done": [False, False]},
            ),
            log_event=False,
        )
        cap = build_tiered_capsule(store)
        kb, _ = build_kanban_board_digest(store)
        assert "OBS-049" in cap
        assert "PROP-050" in kb

    # F-02: Technical token at word #24 of a stopword-heavy prompt MUST still match FTS5!
    long_q = (
        "In the current training pipeline we noticed after running the validation script "
        "that the model with thermograph_jacobian_v11 improved giant zone cooling"
    )
    rec = execute_command("recall", {"workspace": w, "query": long_q})
    assert any(r["id"] == "OBS-049" for r in rec["results"])

    # F-03: Primary track (3 minimization runs) is NOT overwritten by a 1-off smoke run (100.0)!
    execute_command("log_experiment", {"workspace": w, "exp_id": "EXP-MAIN-001", "track": "main", "title": "Baseline Controller v1", "hypothesis": "Establish baseline regret on 16 buildings", "diff": "default PID gains", "test_score": 0.0054, "verdict": "KEEP"})
    execute_command("log_experiment", {"workspace": w, "exp_id": "EXP-MAIN-002", "track": "main", "baseline_id": "EXP-MAIN-001", "title": "Schmitt Hysteresis v2", "hypothesis": "Deadband cuts boiler short-cycling", "diff": "deadband=14K", "test_score": 0.0041, "verdict": "KEEP"})
    execute_command("log_experiment", {"workspace": w, "exp_id": "EXP-MAIN-003", "track": "main", "baseline_id": "EXP-MAIN-002", "title": "Log-Area VAV v3", "hypothesis": "Log-area gain cuts giant-zone cooling regret", "diff": "log_area_scale=True", "test_score": 0.0038, "verdict": "VICTORY_CONFIRMED"})
    execute_command("log_experiment", {"workspace": w, "exp_id": "EXP-SMOKE-001", "track": "smoke", "title": "Fast Unit Smoke", "hypothesis": "Verify unit test suite passes", "diff": "pytest smoke", "test_score": 100.0, "verdict": "KEEP"})
    with GraphStore(ws) as store:
        best = select_best_sota_experiment(store)
        assert best is not None and best.exp_id == "EXP-MAIN-003"
        snap_p = export_snapshot(store, tmp_path / "standalone_snap.json")

    # C4: Standalone snapshot preserves 100% content without reading arbitrary `../../` file_paths
    evil_snap = json.loads(snap_p.read_text(encoding="utf-8"))
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("TOP_SECRET_TOKEN", encoding="utf-8")
    evil_snap["nodes"].append({"id": "OBS-EVIL", "node_type": "OBSERVATION", "title": "Evil", "status": "CONSOLIDATED", "summary": "x", "content": "", "file_path": "../secret.txt"})
    (tmp_path / "evil_snap.json").write_text(json.dumps(evil_snap), encoding="utf-8")
    ws_dest = tmp_path / "dest_ws"
    ws_dest.mkdir()
    with GraphStore(ws_dest) as dst:
        import_snapshot(dst, tmp_path / "evil_snap.json")
        evil_nd = dst.get_node("OBS-EVIL")
        obs49 = dst.get_node("OBS-049")
        assert evil_nd is not None and "TOP_SECRET_TOKEN" not in evil_nd.content
        assert obs49 is not None and len(obs49.content) > 400


def test_shell_quotes_subagent_isolation_async_launches_and_one_strike_stop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify F-05..F-10, C1, C2, C6, I7, Bug #7..#9 across hooks, subagents, shell parser & Stop gate."""
    brain = tmp_path / "brain"
    monkeypatch.setenv("SUPERMEMORY_BRAIN_DIR", str(brain))
    ws = tmp_path / "hook_proj"
    init_workspace(ws, project_name="HookSanity")
    w = str(ws)
    (ws / "README.md").write_text("# HookSanity\n", encoding="utf-8")
    execute_command("add_gate", {"workspace": w, "freeze_path": "README.md"})

    # F-06 & I7: Quote-aware shell classification + frozen-file rg allow vs redirect deny
    assert _classify_shell_command('grep -rn "foo|bar" src/ 2>&1') == "READONLY"
    assert _classify_shell_command("ls -la >/dev/null 2>&1 && pytest -q") == "READONLY"
    assert _classify_shell_command("echo hack > src/model.py") == "SUBSTANTIVE_EXEC"
    allow_rg = dispatch_hook("PreToolUse", {"cwd": w, "toolCall": {"name": "run_command", "args": {"CommandLine": 'rg "score > 0.5" README.md'}}})
    deny_redir = dispatch_hook("PreToolUse", {"cwd": w, "toolCall": {"name": "run_command", "args": {"CommandLine": "echo pwn > README.md"}}})
    assert allow_rg["decision"] == "allow"
    assert deny_redir["decision"] == "deny"

    # C1 / F-09: Subagent transcript (`[Message] sender=parent`, no USER_INPUT) never fires Async Wakeup or blocks Stop!
    sub_id = "subagent-conv-1"
    sub_log = brain / sub_id / ".system_generated" / "logs" / "transcript.jsonl"
    sub_log.parent.mkdir(parents=True, exist_ok=True)
    sub_log.write_text(json.dumps({"step_index": 1, "type": "SYSTEM_MESSAGE", "content": "[Message] sender=parent-uuid content=Review code"}) + "\n", encoding="utf-8")
    sub_pre = dispatch_hook("PreInvocation", {"cwd": w, "conversationId": sub_id, "invocationNum": 1, "initialNumSteps": 2, "lastUserInput": ""})
    sub_stop = dispatch_hook("Stop", {"cwd": w, "conversationId": sub_id, "terminationReason": "NO_TOOL_CALL"})
    assert sub_pre == {}
    assert sub_stop["decision"] == "allow"

    # Bug #7 & F-07: Async launch (`invoke_subagent` or backgrounded `run_command`) never blocks Stop at launch;
    # `IN_FLIGHT_WAIT` clears wakeup while preserving main-agent `dirty_files`!
    main_id = "main-conv-1"
    dispatch_hook("PreInvocation", {"cwd": w, "conversationId": main_id, "invocationNum": 1, "initialNumSteps": 1, "lastUserInput": "Train model on GPU"})
    (ws / "model.py").write_text("lr = 1e-3\n", encoding="utf-8")
    dispatch_hook("PostToolUse", {"cwd": w, "conversationId": main_id, "toolCall": {"name": "write_file", "args": {"Path": str(ws / "model.py")}}})
    execute_command("checkpoint", {"workspace": w, "status": "IN_FLIGHT_WAIT", "note": "Epoch 2/50 running"})
    assert dispatch_hook("Stop", {"cwd": w, "conversationId": main_id, "terminationReason": "NO_TOOL_CALL"})["decision"] == "allow"
    with GraphStore(ws) as st_chk:
        assert "model.py" in get_session_state(st_chk, main_id)["dirty_files"]

    # Background `consolidate` does NOT wipe main-agent `dirty_files`, and `consolidate(review)` never sets literature lock!
    dispatch_hook("PostToolUse", {"cwd": w, "conversationId": main_id, "toolCall": {"name": "call_mcp_tool", "args": {"ServerName": "supermemory_graph", "ToolName": "consolidate", "Arguments": {"mode": "review", "workspace": w}}}})
    with GraphStore(ws) as st_chk2:
        assert st_chk2.get_node("LAW-01") is not None
        assert get_session_state(st_chk2, main_id)["pending_sync_reason"] == ""
        assert "model.py" in get_session_state(st_chk2, main_id)["dirty_files"]

    # F-08: Unsynced edit blocks Stop ONCE (strike 1) and releases immediately on strike 2!
    dispatch_hook("PostToolUse", {"cwd": w, "conversationId": main_id, "toolCall": {"name": "edit_file", "args": {"Path": str(ws / "model.py")}}})
    s1 = dispatch_hook("Stop", {"cwd": w, "conversationId": main_id, "terminationReason": "NO_TOOL_CALL"})
    s2 = dispatch_hook("Stop", {"cwd": w, "conversationId": main_id, "terminationReason": "NO_TOOL_CALL"})
    assert s1["decision"] == "continue"
    assert s2["decision"] == "allow"

    # F-05: 1-call `log_experiment(..., done_steps=[0])` with step [1] still unchecked clears `pending_kanban_sync`!
    prop = execute_command("manage_proposal", {"workspace": w, "action": "create", "title": "Two Step Spec", "why": "Test kanban sync", "what_changes": "Edit model.py", "tasks": ["Run exp 1", "Run final audit"]})
    dispatch_hook("PostToolUse", {"cwd": w, "conversationId": main_id, "toolCall": {"name": "run_command", "args": {"CommandLine": "python train.py"}}})
    execute_command("log_experiment", {"workspace": w, "proposal_id": prop["proposal_id"], "title": "First Training Run", "hypothesis": "Verify lr=1e-3 improves validation score", "diff": "lr=1e-3", "score": 0.91, "done_steps": [0]})
    dispatch_hook("PostToolUse", {"cwd": w, "conversationId": main_id, "toolCall": {"name": "call_mcp_tool", "args": {"ServerName": "supermemory_graph", "ToolName": "log_experiment", "Arguments": {"done_steps": [0]}}}})
    assert dispatch_hook("Stop", {"cwd": w, "conversationId": main_id, "terminationReason": "NO_TOOL_CALL"})["decision"] == "allow"


def test_strict_metric_gate_keep_distinct_challenger_stage_ml_detector_and_subdir_mcp(tmp_path: Path) -> None:
    """Verify C3, C5 (`v1.0` bypass blocked), F-11 (`Challenger`->`CHALLENGED`), F-13 (ML prompt), and I8 (subdir MCP)."""
    ws = tmp_path / "cur_proj"
    init_workspace(ws, project_name="CurProj")
    w = str(ws)

    # C5: `"v1.0"` CANNOT bypass Zero-Loss Metric Gate when source metrics (`0.0038`, `0.0061`) are dropped!
    o1 = execute_command("checkpoint", {"workspace": w, "insights": ["Slice Phoenix: Regret 0.0038 on phoenix_7"]})["captured"]["id"]
    o2 = execute_command("checkpoint", {"workspace": w, "insights": ["Slice Singapore: Regret 0.0061 on singapore_2"]})["captured"]["id"]
    with pytest.raises(ValueError, match="dropped source metrics"):
        execute_command("consolidate", {"workspace": w, "mode": "apply_plan", "operations": [{"op": "merge", "source_ids": [o1, o2], "title": "Synthesized v1.0 Controller Summary", "summary": "Controller v1.0 worked across warm climates with decent stability.", "content": "Detailed multi-sentence architectural overview of controller v1.0 across warm climates that lazily omits both city regret numbers."}]})

    # C3 / F-15: `keep_distinct` marks distinct slices reviewed, and `restore` on DISCARD exp preserves `DISCARD`!
    kd = execute_command("consolidate", {"workspace": w, "mode": "apply_plan", "operations": [{"op": "keep_distinct", "node_ids": [o1, o2], "reason": "Different climate slices"}]})
    assert kd["kept_distinct"] == [o1, o2]
    e1 = execute_command("log_experiment", {"workspace": w, "track": "ablation", "title": "Hard Valve Clip 1", "hypothesis": "Hard clipping valve reduces overshoot", "diff": "clip=1", "score": 0.12, "verdict": "DISCARD", "notes": "Degraded comfort significantly"})["exp_id"]
    e2 = execute_command("log_experiment", {"workspace": w, "track": "ablation", "title": "Hard Valve Clip 2", "hypothesis": "Tighter hard clipping reduces overshoot", "diff": "clip=2", "score": 0.14, "verdict": "DISCARD", "notes": "Degraded comfort even more"})["exp_id"]
    execute_command("consolidate", {"workspace": w, "mode": "apply_plan", "operations": [{"op": "merge", "source_ids": [e1, e2], "title": "Dead-End Clip Sweep (0.12 - 0.14)", "summary": "Hard clipping scored 0.12 and 0.14 regret (both DISCARD).", "content": "Reviewed dead-end valve clipping sweep: clip=1 scored 0.12 and clip=2 scored 0.14, both degrading zone comfort."}]})
    execute_command("consolidate", {"workspace": w, "mode": "restore", "source_ids": [e1]})
    with GraphStore(ws) as st:
        assert st.get_node(e1).status == "DISCARD"  # type: ignore[union-attr]

    # F-11: Challenger APPROVE -> CHALLENGED (stays active!), VictoryAuditor APPROVE -> AUDITED
    p_id = execute_command("manage_proposal", {"workspace": w, "action": "create", "title": "Tube MPC Controller", "why": "Cut peak afternoon cooling power demand", "what_changes": "Add polytopic invariant tube in mpc.py", "tasks": ["Implement polytopic tube in mpc.py"]})["proposal_id"]
    execute_command("record_audit", {"workspace": w, "target_id": p_id, "auditor_role": "Challenger", "verdict": "APPROVE", "findings": "Single-var clean"})
    with GraphStore(ws) as st:
        assert st.get_node(p_id).status == "CHALLENGED"  # type: ignore[union-attr]
    execute_command("record_audit", {"workspace": w, "target_id": p_id, "auditor_role": "VictoryAuditor", "verdict": "APPROVE", "findings": "SOTA verified"})
    with GraphStore(ws) as st:
        assert st.get_node(p_id).status == "AUDITED"  # type: ignore[union-attr]

    # F-13: Ordinary ML engineering prompts mentioning `overfit` / `leakage` / `hardcode` do NOT trigger lesson lock!
    assert SelfLearningDetector.analyze("Regularize the GBDT head so it does not overfit Fold 2 or cause temporal leakage").requires_lesson is False
    assert SelfLearningDetector.analyze("mày lại hardcode tập test rồi, cấm tuyệt đối nhé").requires_lesson is True

    # I8: Subdirectory `default_ws` walks `.parents` to find enclosing `.supermemory` root!
    subdir = ws / "src" / "pkg"
    subdir.mkdir(parents=True)
    handle_rpc_request({"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "checkpoint", "arguments": {"insights": ["Subdir Insight: Routed to parent repo"]}}}, default_ws=subdir)
    with GraphStore(ws) as st:
        assert any("Subdir Insight" in n.title for n in st.list_nodes(limit=50))
