"""Regression Suite for Closed-Loop Async Sync, Anti-Dilution Dedup & 5-Stage Memory GC."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from supermemory.bootstrap import init_workspace
from supermemory.hooks.runner import dispatch_hook
from supermemory.kernel import execute_command
from supermemory.storage.snapshot_io import import_snapshot
from supermemory.storage.sqlite_store import GraphStore


def test_async_wakeup_persistent_stop_dirty_clean_guard_and_one_call_exp(tmp_path: Path) -> None:
    """Verify async task wakeup re-arms Stop gate, 2-strike persistence, dirty CLEAN block & 1-call exp sync."""
    ws = tmp_path / "async_proj"
    init_workspace(ws, project_name="AsyncSyncProj")
    w = str(ws)
    t_file = tmp_path / "transcript.jsonl"
    t_file.write_text("", encoding="utf-8")

    prop = execute_command(
        "manage_proposal",
        {
            "workspace": w,
            "action": "create",
            "title": "Pre-Occupancy Hydraulic Cone Guard",
            "why": "Unbounded pre-arrival static pressure causes 260Pa fan spikes.",
            "what_changes": "Add guarded soon_p_max_pa cap in src/schedule_horizon.py.",
            "tasks": ["Implement guarded cap in schedule_horizon.py", "Run 16-scenario ablation suite"],
        },
    )
    pid = prop["proposal_id"]
    execute_command("manage_proposal", {"workspace": w, "action": "advance", "proposal_id": pid, "new_stage": "IMPLEMENTING"})

    # 1. SessionStart + edit source file -> empty checkpoint(status='CLEAN') MUST be rejected!
    dispatch_hook("SessionStart", {"conversationId": "c-async", "cwd": w, "transcriptPath": str(t_file)})
    src_py = ws / "src" / "schedule_horizon.py"
    src_py.parent.mkdir(parents=True, exist_ok=True)
    src_py.write_text("SOON_CAP = 260.0\n", encoding="utf-8")
    dispatch_hook(
        "PostToolUse",
        {"conversationId": "c-async", "cwd": w, "toolCall": {"name": "write_file", "args": {"Path": str(src_py)}}},
    )
    with pytest.raises(ValueError, match="Dirty-Edit Sync Gate"):
        execute_command("checkpoint", {"workspace": w, "status": "CLEAN"})

    # 2. 2-Strike Persistent Stop Gate: 1st Stop blocks AND does NOT clear dirty_files; 2nd Stop ALSO blocks!
    s1 = dispatch_hook("Stop", {"conversationId": "c-async", "cwd": w, "terminationReason": "NO_TOOL_CALL"})
    assert s1["decision"] == "continue"
    s2 = dispatch_hook("Stop", {"conversationId": "c-async", "cwd": w, "terminationReason": "NO_TOOL_CALL"})
    assert s2["decision"] == "continue"

    # Real checkpoint with insight clears dirty lock
    execute_command(
        "checkpoint",
        {"workspace": w, "insights": ["Guarded Soon Cap: Added 260Pa cap in schedule_horizon.py"], "task_updates": [{"id": pid, "done_steps": [0]}]},
    )
    dispatch_hook(
        "PostToolUse",
        {"conversationId": "c-async", "cwd": w, "toolCall": {"name": "call_mcp_tool", "args": {"ServerName": "supermemory_graph", "ToolName": "checkpoint", "Arguments": {"status": "CAPTURED"}}}},
    )
    assert dispatch_hook("Stop", {"conversationId": "c-async", "cwd": w, "terminationReason": "NO_TOOL_CALL"})["decision"] == "allow"

    # 3. Background task finishes 20m later via SYSTEM_MESSAGE -> PreInvocation re-arms sync!
    t_file.write_text(
        json.dumps(
            {
                "step_index": 42,
                "source": "SYSTEM",
                "type": "SYSTEM_MESSAGE",
                "created_at": "2026-11-18T06:00:00Z",
                "content": '[Message] timestamp=2026-11-18T06:00:00Z sender=c-async/task-9988 content=Task finished: score=0.00559',
            }
        )
        + "\n",
        encoding="utf-8",
    )
    pre_wake = dispatch_hook(
        "PreInvocation",
        {"conversationId": "c-async", "cwd": w, "invocationNum": 1, "initialNumSteps": 43, "transcriptPath": str(t_file)},
    )
    assert "Async Wakeup" in pre_wake["injectSteps"][0]["systemMessage"]["systemMessage"]
    s_wake = dispatch_hook("Stop", {"conversationId": "c-async", "cwd": w, "terminationReason": "NO_TOOL_CALL"})
    assert s_wake["decision"] == "continue"

    # 4. 1-call log_experiment with ergonomic aliases (`diff`, `notes`, `score`) + `done_steps` + `current_phase`!
    exp_out = execute_command(
        "log_experiment",
        {
            "workspace": w,
            "track": "ablation",
            "proposal_id": pid,
            "title": "Standby 260Pa Extension Ablation",
            "hypothesis": "Extending 260Pa cap to standby reduces winter fan power",
            "diff": "schedule_horizon.py standby<=260Pa",
            "score": 0.00561,
            "verdict": "DISCARD",
            "notes": "Standby runs at 73Pa mean pressure so 260Pa cap had 0% effect on schedule_horizon.",
            "done_steps": [1],
            "current_phase": "Phase 2 — Verified Soon-Only Cap",
        },
    )
    assert exp_out["exp_id"] == "EXP-ABLATI-001"
    with GraphStore(ws) as store:
        assert store.get_meta("current_phase") == "Phase 2 — Verified Soon-Only Cap"
        p_nd = store.get_node(pid)
        assert p_nd is not None and p_nd.metadata["tasks_done"] == [True, True]


def test_discard_warnings_pre_edit_module_recall_and_obs_dedup(tmp_path: Path) -> None:
    """Verify DISCARD anti-repeat warnings, pre-edit module warning injection & dual-threshold OBS dedup."""
    ws = tmp_path / "dedup_proj"
    init_workspace(ws, project_name="DedupProj")
    w = str(ws)

    execute_command(
        "log_experiment",
        {
            "workspace": w,
            "track": "ablation",
            "title": "K1 Raw Clamp on schedule_horizon",
            "hypothesis": "Tightening raw clamp in schedule_horizon improves cooling",
            "single_var_diff": "schedule_horizon.py K1_RAW_CLAMP",
            "cv_score": 0.0106,
            "verdict": "DISCARD",
            "post_mortem": "schedule_horizon K1_RAW_CLAMP eroded cool_buf and degraded winter (+0.20%).",
        },
    )
    # 1. DISCARD experiment MUST surface in recall anti_repeat_warnings!
    rec = execute_command("recall", {"workspace": w, "query": "schedule_horizon K1_RAW_CLAMP cooling"})
    assert any("EXP-ABLATI-001" in warn and "DISCARD" in warn for warn in rec["anti_repeat_warnings"])

    # 2. Editing schedule_horizon.py automatically injects past dead-end warnings on that module!
    mod_py = ws / "src" / "schedule_horizon.py"
    mod_py.parent.mkdir(parents=True, exist_ok=True)
    mod_py.write_text("x = 1\n", encoding="utf-8")
    notif = dispatch_hook(
        "PostToolUse",
        {
            "hook_event_name": "PostToolUse",
            "session_id": "cc-mod",
            "cwd": w,
            "tool_name": "Edit",
            "tool_input": {"file_path": str(mod_py)},
        },
    )
    assert "EXP-ABLATI-001" in notif["hookSpecificOutput"]["additionalContext"]

    # 3. Near-duplicate evolving OBS auto-supersedes older OBS, and >=0.82 near-identical merges in-place!
    c1 = execute_command(
        "checkpoint",
        {"workspace": w, "insights": ["Soon Pressure Cap 250Pa: Capping pre-occupancy AHU static pressure to 250Pa cuts fairbanks_8 regret by -4.25%"]},
    )
    c2 = execute_command(
        "checkpoint",
        {"workspace": w, "insights": ["Soon Pressure Cap 250Pa: Capping pre-occupancy AHU static pressure to 250Pa cuts fairbanks_8 regret by -4.28%"]},
    )
    assert c2["captured"]["id"] == c1["captured"]["id"]  # In-place update, zero duplicate node!

    c3 = execute_command(
        "checkpoint",
        {"workspace": w, "insights": ["Soon Pressure Cap 260Pa Guarded: Capping pre-occupancy AHU static pressure to 260Pa beats baseline on Panorama-9 (-2.50%)"]},
    )
    assert c3["captured"]["id"] != c1["captured"]["id"]
    with GraphStore(ws) as store:
        old_obs = store.get_node(c1["captured"]["id"])
        assert old_obs is not None and old_obs.status == "SUPERSEDED"


def test_five_stage_gc_failure_digests_macro_sems_archive_and_active_ranker(tmp_path: Path) -> None:
    """Verify O(log N) Macro-SEM merge, FAILURE_INSIGHT digests, archive sweep & Active-Set ranker."""
    ws = tmp_path / "gc_proj"
    init_workspace(ws, project_name="LongHorizonGC")
    w = str(ws)

    bnk = execute_command(
        "diagnose_bottleneck",
        {"workspace": w, "title": "Giant Zone Starvation", "evidence_slice": "z > 400m2", "error_share_pct": 65, "ceiling_gain": 0.08, "falsifiable_rq": "Does log-area scaling fix giant zones?"},
    )
    bid = bnk["bottleneck"]["id"]
    rq_id = bnk["research_question"]["id"]
    idea = execute_command("propose_idea", {"workspace": w, "bottleneck_id": bid, "title": "Log-Area VAV Scaling", "summary": "Scale VAV gain by log(zone_area)"})
    prop = execute_command(
        "manage_proposal",
        {"workspace": w, "action": "create", "bottleneck_id": bid, "idea_ids": [idea["node"]["id"]], "title": "Ship Log-Area VAV Scaling", "why": "Fixes 65% giant-zone slice", "what_changes": "Add log_area factor in vav.py", "tasks": ["Add log_area factor in vav.py"]},
    )
    pid = prop["proposal_id"]
    execute_command("checkpoint", {"workspace": w, "task_updates": [{"id": pid, "done_steps": [0]}]})
    execute_command("record_audit", {"workspace": w, "target_id": pid, "verdict": "APPROVE", "findings": "Verified"})
    with GraphStore(ws) as st_b:
        bnk_nd = st_b.get_node(bid)
        assert bnk_nd is not None
        bnk_nd.status = "RESOLVED"
        st_b.upsert_node(bnk_nd, log_event=False)

    # Generate 22 FAILURE_INSIGHT observations + 22 SEM digests to trigger both Failure Digest & 2nd-order Macro-SEM GC
    for i in range(22):
        with GraphStore(ws) as st:
            from supermemory.models import MemoryNode, NodeType

            obs_p = f"memory/06_KNOWLEDGE_NODES/OBS-F{i:02d}.md"
            (ws / obs_p).parent.mkdir(parents=True, exist_ok=True)
            (ws / obs_p).write_text(f"# OBS-F{i:02d}\nDead-end variant {i} on thermal_valve_{i}\n", encoding="utf-8")
            st.upsert_node(
                MemoryNode(
                    id=f"OBS-F{i:02d}", node_type=NodeType.OBSERVATION.value,
                    title=f"[FAILURE_INSIGHT] Valve failure mode {i}", status="FAILURE_INSIGHT",
                    summary=f"Dead-end variant {i} on thermal_valve_{i} regressed comfort", content="...",
                    file_path=obs_p, metadata={"track": "ablation"},
                ),
                log_event=False,
            )
            sem_p = f"memory/06_KNOWLEDGE_NODES/SEM-{i + 1:03d}.md"
            (ws / sem_p).write_text(f"# SEM-{i + 1:03d}\nSynthesis batch {i}\n", encoding="utf-8")
            st.upsert_node(
                MemoryNode(
                    id=f"SEM-{i + 1:03d}", node_type=NodeType.KNOWLEDGE_NODE.value,
                    title=f"Distilled Synthesis #{i + 1}", status="ACTIVE",
                    summary=f"Distilled batch {i + 1} findings on latent rollout_{i}", content="Full body",
                    file_path=sem_p, metadata={"memory_tier": "SEMANTIC"},
                ),
                log_event=False,
            )

    gc_out = execute_command("consolidate", {"workspace": w, "mode": "gc"})
    assert len(gc_out["failure_digests"]) >= 1
    assert len(gc_out["macro_sems"]) >= 1
    assert gc_out["archived_proposals"] >= 1
    assert gc_out["closed_rqs"] >= 1
    assert gc_out["archived_files"] >= 10

    # Consolidated nodes excluded from Stage-1 recall, while Dead-End Digest surfaces warning & Stage-2 rehydrates from archive!
    r_stage1 = execute_command("recall", {"workspace": w, "query": "thermal_valve_0 regressed comfort"})
    assert all(r["status"] != "CONSOLIDATED" for r in r_stage1["results"])
    assert any("FAILURE INSIGHT" in w_txt for w_txt in r_stage1["anti_repeat_warnings"])
    r_stage2 = execute_command("recall", {"workspace": w, "node_id": "OBS-F00"})
    assert "memory/archive/06_KNOWLEDGE_NODES/" in r_stage2["node"]["file_path"]

    with GraphStore(ws) as st2:
        assert st2.get_node(pid).status == "ARCHIVED"  # type: ignore[union-attr]
        assert st2.get_node(rq_id).status == "ANSWERED"  # type: ignore[union-attr]
        assert st2.get_node(idea["node"]["id"]).status == "IMPLEMENTED"  # type: ignore[union-attr]
        ws_clone = tmp_path / "clone_check"
        ws_clone.mkdir()
        with GraphStore(ws_clone) as cloned:
            stats = import_snapshot(cloned, ws / "memory" / "graph_snapshot.json")
            assert stats["nodes"] > 20


def test_per_window_mcp_isolation_and_uninit_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each window's `default_ws` isolates MCP calls from global `active_workspace.json` & protects uninitialized dirs."""
    from supermemory.cognitive.federation import set_active_workspace
    from supermemory.mcp.server import handle_rpc_request

    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(tmp_path / "global_hub"))
    ws_a, ws_b, ws_uninit = tmp_path / "proj_a", tmp_path / "proj_b", tmp_path / "proj_uninit"
    ws_uninit.mkdir()
    init_workspace(ws_a, project_name="ProjA")
    init_workspace(ws_b, project_name="ProjB")
    set_active_workspace(ws_a)

    # Window B omits `workspace` while `active_workspace.json` points to ProjA -> still writes strictly into ProjB!
    handle_rpc_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "checkpoint", "arguments": {"insights": ["Window B isolated insight on transformer cache"]}}},
        default_ws=ws_b,
    )
    with GraphStore(ws_a) as sa, GraphStore(ws_b) as sb:
        assert not any("Window B isolated" in n.title for n in sa.list_nodes())
        assert any("Window B isolated" in n.title for n in sb.list_nodes())

    # Uninitialized Window C never creates `.supermemory/` on recall or mutating calls until explicit `init`
    handle_rpc_request({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "recall", "arguments": {"query": "cache"}}}, default_ws=ws_uninit)
    handle_rpc_request({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "checkpoint", "arguments": {"insights": ["Global fallback note for uninit repo"]}}}, default_ws=ws_uninit)
    assert not (ws_uninit / ".supermemory").exists()
    handle_rpc_request({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "init", "arguments": {"project_name": "ProjC"}}}, default_ws=ws_uninit)
    assert (ws_uninit / ".supermemory" / "supermemory.db").is_file()
