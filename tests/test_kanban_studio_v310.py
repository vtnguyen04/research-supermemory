"""End-to-end tests for SuperMemory Studio v3.1 Kanban Board, Subtask Checklists & Progress Telemetry."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict

import pytest

from supermemory.bootstrap import init_workspace
from supermemory.ui.server import create_http_server


def _post(base: str, route: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    req = urllib.request.Request(
        f"{base}{route}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(base: str, route: str) -> Dict[str, Any]:
    with urllib.request.urlopen(f"{base}{route}", timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_kanban_transitions_subtask_progress_and_proposal_sync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(tmp_path / "global_kb"))
    ws = tmp_path / "kanban_ws"
    init_workspace(ws, project_name="KanbanStudio")

    srv, port = create_http_server(ws, host="127.0.0.1", port=0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"

    try:
        # 1. Enqueue task with 3 custom subtasks and a dependent task
        t1 = _post(
            base,
            "/api/orchestrate",
            {
                "action": "enqueue",
                "title": "Profile Ranker Slice",
                "role": "bottleneck-profiler",
                "wave": 1,
                "locked_globs": "src/ranker/**",
                "brief": "Quantify slice errors.",
                "steps": "Measure baseline\nIsolate worst slice\nRegister BNK-001",
            },
        )["task"]
        tid1 = t1["task_id"]
        assert len(t1["receipt"]["steps"]) == 3

        t2 = _post(
            base,
            "/api/orchestrate",
            {
                "action": "enqueue",
                "title": "Overlapping Ranker Edit",
                "role": "slice-builder",
                "wave": 2,
                "depends_on": tid1,
                "locked_globs": "src/ranker/core.py",
                "brief": "Single-var fix.",
            },
        )["task"]
        tid2 = t2["task_id"]

        g0 = _get(base, "/api/graph")
        ov0 = g0["execution_overview"]
        assert ov0["ready_count"] == 1
        assert ov0["backlog_count"] == 1

        # 2. Toggle subtask 0 on QUEUED task -> auto-promotes to RUNNING & updates progress
        _post(base, "/api/orchestrate", {"action": "toggle_step", "kind": "TASK", "item_id": tid1, "step_idx": 0})
        g1 = _get(base, "/api/graph")
        task1_live = next(t for t in g1["agent_tasks"] if t["task_id"] == tid1)
        assert task1_live["status"] == "RUNNING"
        assert task1_live["kanban_col"] == "IN_PROGRESS"
        assert task1_live["steps_done"] == 1
        assert task1_live["progress_pct"] == 33

        # 3. Verify glob-lease conflict blocks moving overlapping tid2 into IN_PROGRESS
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _post(base, "/api/orchestrate", {"action": "move", "task_id": tid2, "target_stage": "IN_PROGRESS"})
        assert exc_info.value.code == 400

        # 4. Append a 4th subtask dynamically, then move tid1 to DONE -> 100% completion
        _post(base, "/api/orchestrate", {"action": "add_step", "kind": "TASK", "item_id": tid1, "text": "Verify smoke gate"})
        _post(base, "/api/orchestrate", {"action": "move", "task_id": tid1, "target_stage": "DONE"})
        g2 = _get(base, "/api/graph")
        task1_done = next(t for t in g2["agent_tasks"] if t["task_id"] == tid1)
        assert task1_done["kanban_col"] == "DONE"
        assert task1_done["progress_pct"] == 100
        assert task1_done["steps_done"] == 4
        # Dependent tid2 is now automatically READY!
        task2_ready = next(t for t in g2["agent_tasks"] if t["task_id"] == tid2)
        assert task2_ready["kanban_col"] == "READY"

        # 5. Requeue tid1 back to READY, update its title, and delete tid2
        _post(base, "/api/orchestrate", {"action": "move", "task_id": tid1, "target_stage": "READY"})
        _post(base, "/api/orchestrate", {"action": "update", "task_id": tid1, "title": "Updated Profiler Task", "role": "bottleneck-profiler", "wave": 1})
        assert _post(base, "/api/orchestrate", {"action": "delete", "task_id": tid2})["deleted"] is True

        # 6. Create an OpenSpec Proposal and toggle its checklist subtasks -> syncs tasks.md on disk!
        prop = _post(
            base,
            "/api/proposals",
            {"action": "create", "title": "Kanban Sync Spec", "why": "Track proposal tasks", "tasks": "Write unit test\nRun audit"},
        )
        pid = prop["proposal_id"]
        _post(base, "/api/proposals", {"action": "advance", "proposal_id": pid, "new_stage": "IMPLEMENTING"})
        g_prop0 = _get(base, "/api/graph")
        pnode0 = next(n for n in g_prop0["nodes"] if n["id"] == pid)
        assert pnode0["metadata"]["progress_pct"] == 0

        long_step = "Verify_setpoint_energy_carbon_regret_PlantOperatingPointOptimizer_" + ("x" * 160)
        _post(base, "/api/orchestrate", {"action": "toggle_step", "kind": "PROPOSAL", "item_id": pid, "step_idx": 0, "done": True})
        _post(base, "/api/orchestrate", {"action": "add_step", "kind": "PROPOSAL", "item_id": pid, "text": long_step})
        g3 = _get(base, "/api/graph")
        pnode = next(n for n in g3["nodes"] if n["id"] == pid)
        assert pnode["metadata"]["tasks_done"] == [True, False, False]
        assert pnode["metadata"]["progress_pct"] == 33
        assert len(pnode["metadata"]["tasks"][2]) > 200
        tasks_md_files = list((ws / "memory" / "04_PROPOSALS").glob(f"{pid}_*/tasks.md"))
        assert len(tasks_md_files) == 1
        md_txt = tasks_md_files[0].read_text(encoding="utf-8")
        assert "- [x] Write unit test" in md_txt
        assert f"- [ ] {long_step}" in md_txt
    finally:
        srv.shutdown()
        srv.server_close()
