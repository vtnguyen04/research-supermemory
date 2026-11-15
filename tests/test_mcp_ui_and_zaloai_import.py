"""Integration tests for Stdio MCP Server, Web Observatory HTTP API, and ZALOAI Importer."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from urllib.request import urlopen

import pytest

from supermemory.bootstrap import init_workspace
from supermemory.storage.sqlite_store import GraphStore
from supermemory.sync.markdown_compiler import MarkdownCompiler
from supermemory.sync.zaloai_importer import import_zaloai_workspace
from supermemory.ui.server import create_http_server

REPO_ROOT = Path(__file__).resolve().parents[1]
ZALOAI_ROOT = Path(os.environ.get("ZALOAI_REF_DIR", str(Path.home() / "Documents" / "AI-project" / "ZALOAI")))


def test_stdio_mcp_server_end_to_end(tmp_path: Path) -> None:
    mcp_script = REPO_ROOT / "plugin" / "scripts" / "mcp_entry.py"
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "supermemory_init",
                "arguments": {"workspace": str(tmp_path), "project_name": "MCPDemo", "max_lines": 300},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "supermemory_record_lesson",
                "arguments": {
                    "workspace": str(tmp_path),
                    "title": "Never swallow exceptions silently",
                    "mistake": "Used bare except pass in API client",
                    "root_cause": "Hid timeout root cause during evaluation",
                    "prevention_rule": "Forbid bare except blocks in production code",
                    "law_id": "LAW-06",
                    "forbid_regex": r"^\s*except\s*:",
                },
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "supermemory_recall",
                "arguments": {"workspace": str(tmp_path), "query": "bare except timeout"},
            },
        },
        {"jsonrpc": "2.0", "id": 6, "method": "resources/list"},
    ]
    stdin_payload = "\n".join(json.dumps(r) for r in requests) + "\n"
    proc = subprocess.run(
        [sys.executable, str(mcp_script)],
        input=stdin_payload,
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [json.loads(line) for line in proc.stdout.strip().splitlines() if line.strip()]
    by_id = {msg["id"]: msg for msg in lines}

    assert by_id[1]["result"]["serverInfo"]["name"] == "supermemory"
    tools = by_id[2]["result"]["tools"]
    assert len(tools) == 17
    assert {t["name"] for t in tools} >= {
        "supermemory_init",
        "supermemory_recall",
        "supermemory_record_lesson",
        "supermemory_log_experiment",
        "supermemory_manage_proposal",
        "supermemory_checkpoint",
        "supermemory_consolidate",
        "supermemory_diagnose_bottleneck",
        "supermemory_scout_sota",
        "supermemory_orchestrate",
    }

    lesson_res = json.loads(by_id[4]["result"]["content"][0]["text"])
    assert lesson_res["lesson_id"] == "LESSON-001"
    assert lesson_res["gate_id"] == "GATE-005"

    recall_res = json.loads(by_id[5]["result"]["content"][0]["text"])
    assert any("LESSON-001" in w for w in recall_res["anti_repeat_warnings"])
    assert len(by_id[6]["result"]["resources"]) == 4


def test_graph_observatory_web_ui_server(tmp_path: Path) -> None:
    init_workspace(tmp_path, project_name="ObservatoryProject")
    srv, port = create_http_server(tmp_path, host="127.0.0.1", port=0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{port}"
        html = urlopen(f"{base}/").read().decode("utf-8")
        assert "SuperMemory Observatory" in html
        js = urlopen(f"{base}/app.js").read().decode("utf-8")
        assert "ForceGraphCanvas" in js

        graph_data = json.loads(urlopen(f"{base}/api/graph").read().decode("utf-8"))
        assert graph_data["project"] == "ObservatoryProject"
        assert graph_data["analytics"]["total_nodes"] >= 12
        assert len(graph_data["gates"]) >= 4

        node_data = json.loads(urlopen(f"{base}/api/node/LAW-01").read().decode("utf-8"))
        assert node_data["node"]["id"] == "LAW-01"

        search_data = json.loads(urlopen(f"{base}/api/search?q=hardcoding").read().decode("utf-8"))
        assert len(search_data["results"]) >= 1
    finally:
        srv.shutdown()
        srv.server_close()


@pytest.mark.skipif(not ZALOAI_ROOT.is_dir(), reason="ZALOAI reference repo not present on disk")
def test_real_zaloai_workspace_import_read_only(tmp_path: Path) -> None:
    init_workspace(tmp_path, project_name="ZALOAI-SuperMemory")
    with GraphStore(tmp_path) as store:
        counts = import_zaloai_workspace(ZALOAI_ROOT, store)
        MarkdownCompiler(store).compile_all()
        analytics = store.list_nodes(limit=5000)

    assert counts["laws"] >= 10
    assert counts["lessons"] >= 10
    assert counts["experiments"] >= 35
    assert counts["knowledge_nodes"] == 2
    assert counts["proposals"] >= 1
    assert counts["gates"] >= 4
    assert len(analytics) >= 65
    assert (tmp_path / "memory" / "03_EXPERIMENTS_REGISTRY.md").is_file()
