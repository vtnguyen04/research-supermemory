"""SOLID Clean Architecture Invariant Tests: OCP Registry, Single-Source Version & Lazy CLI Isolation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

from supermemory import __version__, resolve_live_version
from supermemory.bootstrap import init_workspace
from supermemory.kernel import REGISTRY, CommandRegistry
from supermemory.ui.server import create_http_server


def test_ocp_single_registration_drives_schema_uow_and_hook_classifier(tmp_path: Path) -> None:
    """Prove adding a brand-new command requires 1 decorated function and 0 edits to MCP/Hook/UI."""
    ws = tmp_path / "ocp_proj"
    init_workspace(ws, project_name="OCPProj")

    reg = CommandRegistry()

    @reg.register(
        name="custom_domain_probe",
        description="Single-file extensible command test.",
        input_schema={"type": "object", "properties": {"tag": {"type": "string"}}},
        mutates_memory=True,
    )
    def _handle_probe(store: object, args: dict[str, object]) -> dict[str, object]:
        store.set_meta("probe_tag", str(args.get("tag") or "ok"))  # type: ignore[attr-defined]
        return {"recorded": True, "tag": args.get("tag")}

    # 1. MCP schema auto-generated
    schemas = reg.mcp_tool_schemas()
    assert len(schemas) == 1 and schemas[0]["name"] == "custom_domain_probe"

    # 2. Hook mutation classifier auto-recognizes it without any hardcoded string set
    mutated, ro_res = reg.classify_mcp_call("mcp__supermemory_graph__custom_domain_probe", "", "", {"tag": "v1"})
    assert mutated is True and ro_res is False

    # 3. Unit-of-Work executes handler + compiles Markdown automatically
    out = reg.execute("custom_domain_probe", {"workspace": str(ws), "tag": "solid"})
    assert out == {"recorded": True, "tag": "solid"}
    assert (ws / "memory" / "01_ACTIVE_STATE.md").is_file()
    assert len(REGISTRY.list_specs()) == 17


def test_single_source_version_and_dynamic_html_stamping(tmp_path: Path) -> None:
    """Ensure version lives only in pyproject.toml and stamps dynamically into index.html."""
    repo_root = Path(__file__).resolve().parents[1]
    init_py = (repo_root / "src" / "supermemory" / "__init__.py").read_text(encoding="utf-8")
    html_tpl = (repo_root / "src" / "supermemory" / "ui" / "static" / "index.html").read_text(encoding="utf-8")

    assert "__version__ = resolve_live_version()" in init_py
    assert "{{SM_VERSION}}" in html_tpl
    assert __version__ == resolve_live_version()

    ws = tmp_path / "ver_proj"
    init_workspace(ws, project_name="VerProj")
    srv, port = create_http_server(ws, host="127.0.0.1", port=0)
    import threading

    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        rendered = urlopen(f"http://127.0.0.1:{port}/").read().decode("utf-8")
        assert "{{SM_VERSION}}" not in rendered
        assert f'content="{__version__}"' in rendered
        assert f"?v={__version__}" in rendered
    finally:
        srv.shutdown()
        srv.server_close()


def test_cli_lazy_imports_isolate_hooks_from_ui_and_mcp() -> None:
    """Ensure importing `supermemory.cli` does not eagerly import UI server or MCP server."""
    code = (
        "import sys, supermemory.cli; "
        "assert 'supermemory.ui.server' not in sys.modules; "
        "assert 'supermemory.mcp.server' not in sys.modules"
    )
    res = subprocess.run([sys.executable, "-c", code], check=False, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_zero_circular_imports_and_inward_kernel_boundary() -> None:
    """Verify every import order across kernel/mcp/hooks/ui succeeds and kernel never imports adapters."""
    repo_root = Path(__file__).resolve().parents[1]
    for py_file in (repo_root / "src" / "supermemory" / "kernel").glob("*.py"):
        src = py_file.read_text(encoding="utf-8")
        for outward in ("supermemory.mcp", "supermemory.ui", "supermemory.hooks", "supermemory.cli"):
            assert outward not in src, f"{py_file.name} violated Hexagonal boundary by importing {outward}"

    orders = [
        "import supermemory.kernel, supermemory.mcp.tool_defs",
        "import supermemory.mcp.tool_defs, supermemory.kernel",
        "import supermemory.mcp.checkpoint_sync, supermemory.kernel",
        "import supermemory.kernel.lifecycle_cmds, supermemory.mcp.server",
        "import supermemory.hooks.runner, supermemory.hooks.claude_bridge",
    ]
    for stmt in orders:
        res = subprocess.run([sys.executable, "-c", stmt], check=False, capture_output=True, text=True)
        assert res.returncode == 0, f"Failed `{stmt}`: {res.stderr}"


def test_immutable_audit_and_system_events_completeness(tmp_path: Path) -> None:
    """Verify audits, gates, Kanban steps, L0 checkpoints, and Stop hook interceptions emit live events."""
    from supermemory.hooks.runner import dispatch_hook
    from supermemory.kernel import execute_command
    from supermemory.storage.sqlite_store import GraphStore

    ws = tmp_path / "ev_proj"
    init_workspace(ws, project_name="EvProj")
    w = str(ws)

    execute_command("add_gate", {"workspace": w, "name": "TestGate", "pattern": "BAD_TOK", "gate_type": "FORBIDDEN_REGEX"})
    execute_command("audit_gates", {"workspace": w})
    execute_command(
        "checkpoint",
        {
            "workspace": w,
            "new_task": {"title": "Verify live events feed", "steps": ["Emit audit event", "Verify UI feed"]},
            "current_phase": "Phase 1",
        },
    )
    execute_command("orchestrate", {"workspace": w, "action": "toggle_step", "item_id": "DAG-001", "step_idx": 0, "done": True})

    src_f = ws / "app.py"
    src_f.write_text("x = 1\n", encoding="utf-8")
    dispatch_hook("PostToolUse", {"cwd": w, "conversationId": "c1", "toolCall": {"name": "write_file", "args": {"Path": str(src_f)}}})
    stop_res = dispatch_hook("Stop", {"cwd": w, "conversationId": "c1", "terminationReason": "NO_TOOL_CALL"})
    assert stop_res["decision"] == "continue"

    with GraphStore(ws) as store:
        ev_types = {e["event_type"] for e in store.list_events(limit=50)}
    assert {"GATE_UPSERTED", "GATE_AUDIT_PASSED", "DAG_TASK_ENQUEUED", "KANBAN_STEP_TOGGLED", "STOP_GATE_ENFORCED"} <= ev_types


def test_changelog_sync_gate_enforces_documented_releases(tmp_path: Path) -> None:
    """Ensure CHANGELOG.md tracks live pyproject.toml version and CHANGELOG_SYNC blocks undocumented bumps."""
    import re

    from supermemory.gates.enforcer import GateEnforcer
    from supermemory.kernel import execute_command
    from supermemory.storage.sqlite_store import GraphStore

    repo_root = Path(__file__).resolve().parents[1]
    live_ver = resolve_live_version()
    repo_cl = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(rf"^##\s+\[{re.escape(live_ver)}\]\s+-\s+\d{{4}}-\d{{2}}-\d{{2}}\b", repo_cl, re.MULTILINE)

    ws = tmp_path / "cl_proj"
    init_workspace(ws, project_name="ClProj")
    (ws / "pyproject.toml").write_text('[project]\nname = "demo"\nversion = "1.0.0"\n', encoding="utf-8")
    (ws / "CHANGELOG.md").write_text("# Changelog\n\n## [1.0.0] - 2026-11-17\n- Initial\n", encoding="utf-8")
    execute_command(
        "add_gate",
        {"workspace": str(ws), "gate_type": "CHANGELOG_SYNC", "name": "Require Changelog", "law_id": "LAW-07", "target_glob": "pyproject.toml", "pattern": "CHANGELOG.md"},
    )
    with GraphStore(ws) as store:
        enf = GateEnforcer(store)
        blocked = enf.evaluate_tool_call(
            "edit_file",
            {"Path": str(ws / "pyproject.toml"), "Target": 'version = "1.0.0"', "Replacement": 'version = "1.1.0"'},
        )
        assert not blocked.allowed and "1.1.0" in blocked.reason
        (ws / "CHANGELOG.md").write_text("# Changelog\n\n## [1.1.0] - 2026-11-17\n- Feature\n\n## [1.0.0] - 2026-11-17\n", encoding="utf-8")
        allowed = enf.evaluate_tool_call(
            "edit_file",
            {"Path": str(ws / "pyproject.toml"), "Target": 'version = "1.0.0"', "Replacement": 'version = "1.1.0"'},
        )
        assert allowed.allowed
