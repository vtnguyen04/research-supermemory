"""End-to-end tests for the SuperMemory Interactive Web Management Console API."""

from __future__ import annotations

import json
import re
import threading
import urllib.request
from pathlib import Path
from typing import Any, Dict

import pytest

from supermemory.bootstrap import init_workspace
from supermemory.ui.server import STATIC_DIR, create_http_server


def _post_json(base: str, route: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    req = urllib.request.Request(
        f"{base}{route}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(base: str, route: str) -> Dict[str, Any]:
    with urllib.request.urlopen(f"{base}{route}", timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def test_full_ui_management_console_crud_and_lifecycle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(tmp_path / "global_ui"))
    default_proj = tmp_path / "proj_default"
    init_workspace(default_proj, project_name="DefaultConsole")

    srv, port = create_http_server(default_proj, host="127.0.0.1", port=0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"

    try:
        # 1. Init a brand-new workspace directly from the UI
        new_proj = tmp_path / "proj_created_from_ui"
        init_res = _post_json(
            base,
            "/api/workspaces/init",
            {"path": str(new_proj), "name": "UIManagedApp", "goal": "Manage everything visually", "max_lines": 300},
        )
        assert init_res["project"] == "UIManagedApp"
        assert (new_proj / "AGENTS.md").is_file()
        sc = str(new_proj)

        # 2. Update L0 Working State from the UI
        st_res = _post_json(
            base,
            "/api/state",
            {
                "scope": sc,
                "active_goal": "Ship zero-CLI management experience",
                "current_phase": "v2.1 UI Studio",
                "next_actions": "Test inline CRUD",
            },
        )
        assert st_res["meta"]["active_goal"] == "Ship zero-CLI management experience"
        assert "Ship zero-CLI management experience" in (new_proj / "memory" / "01_ACTIVE_STATE.md").read_text(encoding="utf-8")

        # 3. Create, Edit, Link Edge, and Delete Nodes via Inspector API
        n1 = _post_json(
            base,
            "/api/node/upsert",
            {
                "scope": sc,
                "node_type": "PROCEDURE",
                "memory_tier": "PROCEDURAL",
                "title": "Standard Release Playbook",
                "summary": "Always run audit before tagging",
                "content": "Step 1: pytest\nStep 2: audit",
            },
        )["node"]
        assert n1["id"] == "PROC-001"

        edited = _post_json(
            base,
            "/api/node/upsert",
            {"scope": sc, "id": "PROC-001", "title": "Updated Release Playbook", "status": "VERIFIED"},
        )["node"]
        assert edited["title"] == "Updated Release Playbook"
        assert edited["status"] == "VERIFIED"

        edge_res = _post_json(
            base,
            "/api/edge/add",
            {"scope": sc, "source_id": "PROC-001", "target_id": "LAW-03", "relation": "GOVERNED_BY"},
        )
        assert edge_res["linked"] is True

        # 4. Create Lesson + Rule + Gate, Toggle Gate, Audit, Delete Gate
        ls_res = _post_json(
            base,
            "/api/lessons",
            {
                "scope": sc,
                "new_law_title": "No Hardcoded Ports",
                "title": "Avoid hardcoded port 9999",
                "mistake": "Bound static port in test",
                "root_cause": "Port collision in CI",
                "prevention_rule": "Use port=0 for ephemeral test servers",
                "forbid_regex": r"port\s*=\s*9999",
            },
        )
        assert "No Hardcoded Ports" in (new_proj / "AGENTS.md").read_text(encoding="utf-8")
        gid = ls_res["gate_id"]
        assert gid

        assert _post_json(base, "/api/gates", {"scope": sc, "action": "toggle", "gate_id": gid, "enabled": False})["toggled"] is True
        assert _post_json(base, "/api/audit", {"scope": sc})["passed"] is True
        assert _post_json(base, "/api/gates", {"scope": sc, "action": "delete", "gate_id": gid})["deleted"] is True

        # 5. Create Idea, Create/Advance/Audit/Archive Proposal, Log Experiment, and Generate Handoff
        idea = _post_json(
            base,
            "/api/ideas",
            {"scope": sc, "title": "Naive Regex Only", "summary": "Misses subtle phrasing", "status": "REJECTED", "rejection_reason": "Brittle"},
        )["node"]
        assert idea["status"] == "REJECTED"

        prop = _post_json(
            base,
            "/api/proposals",
            {"scope": sc, "action": "create", "title": "Visual Kanban", "why": "Fast stage control", "design_notes": "1-click buttons"},
        )
        pid = prop["proposal_id"]
        _post_json(base, "/api/proposals", {"scope": sc, "action": "advance", "proposal_id": pid, "new_stage": "IMPLEMENTING"})
        _post_json(base, "/api/proposals", {"scope": sc, "action": "audit", "proposal_id": pid, "verdict": "APPROVE"})
        arch = _post_json(base, "/api/proposals", {"scope": sc, "action": "advance", "proposal_id": pid, "new_stage": "ARCHIVED"})
        assert arch["node"]["status"] == "ARCHIVED"

        exp = _post_json(
            base,
            "/api/experiments",
            {
                "scope": sc,
                "track": "ui",
                "title": "UI Latency Check",
                "hypothesis": "Local JSON endpoints respond in <10ms",
                "single_var_diff": "Added api_actions.py",
                "cv_score": 99.5,
                "verdict": "VICTORY_CONFIRMED",
                "insights": "Zero-CDN vanilla JS keeps UI instant.",
            },
        )
        assert exp["exp_id"] == "EXP-UI-001"
        assert exp["observation_ids"] == ["OBS-001"]

        ho = _post_json(base, "/api/handoff", {"scope": sc})
        assert "HANDOFF BRIEFING" in ho["markdown"]

        # Delete temporary PROC-001 node and verify removal
        assert _post_json(base, "/api/node/delete", {"scope": sc, "node_id": "PROC-001"})["deleted"] is True
        gdata = _get_json(base, f"/api/graph?scope={sc}")
        assert all(n["id"] != "PROC-001" for n in gdata["nodes"])
    finally:
        srv.shutdown()
        srv.server_close()


def test_production_ui_design_system_and_accessibility_contract(tmp_path: Path) -> None:
    proj = tmp_path / "proj_ui_contract"
    init_workspace(proj, project_name="UIContractApp")
    srv, port = create_http_server(proj, host="127.0.0.1", port=0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"

    expected_assets = [
        "/",
        "/styles.css",
        "/icons.js",
        "/graph_canvas.js",
        "/inspector.js",
        "/merge_studio.js",
        "/modals.js",
        "/views.js",
        "/app.js",
    ]
    emoji_rx = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")
    confirm_rx = re.compile(r"\bwindow\.(alert|confirm)\s*\(")

    try:
        fetched: Dict[str, str] = {}
        for route in expected_assets:
            with urllib.request.urlopen(f"{base}{route}", timeout=5) as resp:
                assert resp.status == 200
                fetched[route] = resp.read().decode("utf-8")

        html = fetched["/"]
        css = fetched["/styles.css"]
        assert "SuperMemory Observatory" in html
        assert 'role="tablist"' in html
        assert 'role="tab"' in html
        assert 'role="tabpanel"' in html
        assert "<dialog" in html
        assert "skip-link" in html
        assert ":focus-visible" in css
        assert "font-variant-numeric: tabular-nums" in css
        assert "--bg-canvas:" in css and "--sp-4: 1rem" in css

        js_files = sorted(STATIC_DIR.glob("*.js"))
        assert len(js_files) == 7
        for js_path in js_files:
            lines = js_path.read_text(encoding="utf-8").splitlines()
            assert len(lines) < 200, f"{js_path.name} exceeds 200 lines ({len(lines)})"

        for route, content in fetched.items():
            assert not emoji_rx.search(content), f"Emoji detected in {route}"
            assert not confirm_rx.search(content), f"Browser confirm/alert detected in {route}"
            if route != "/styles.css":
                assert 'style="' not in content, f"Inline HTML style attribute detected in {route}"
    finally:
        srv.shutdown()
        srv.server_close()
