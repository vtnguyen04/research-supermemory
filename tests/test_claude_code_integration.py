"""End-to-end tests for Claude Code MCP, Hook Bridge, Gate Enforcer & Installer."""

from __future__ import annotations

import json
from pathlib import Path

from supermemory.bootstrap import init_workspace
from supermemory.hooks.runner import dispatch_hook
from supermemory.sync.claude_installer import install_claude_code_integration


def test_claude_code_installer_idempotent_and_preserves_existing_hooks(tmp_path: Path) -> None:
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    claude_json = tmp_path / ".claude.json"
    claude_json.write_text(
        json.dumps({"mcpServers": {"existing-mcp": {"command": "npx", "args": ["foo"]}}}),
        encoding="utf-8",
    )
    settings_path = claude_dir / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "permissions": {"allow": ["Bash(rtk *)"]},
                "hooks": {
                    "PreToolUse": [
                        {"matcher": "Bash", "hooks": [{"type": "command", "command": "rtk hook claude"}]}
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    plugin_src = Path(__file__).resolve().parents[1] / "plugin"
    res1 = install_claude_code_integration(plugin_src, claude_dir=claude_dir, claude_json_path=claude_json)
    res2 = install_claude_code_integration(plugin_src, claude_dir=claude_dir, claude_json_path=claude_json)

    assert res1["mcp_server"] == "supermemory_graph"
    assert len(res2["skills"]) == 9
    assert len(res2["agents"]) == 8

    c_data = json.loads(claude_json.read_text(encoding="utf-8"))
    assert "existing-mcp" in c_data["mcpServers"]
    assert c_data["mcpServers"]["supermemory_graph"]["args"] == ["mcp"]

    s_data = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "mcp__supermemory_graph__*" in s_data["permissions"]["allow"]
    assert "Bash(rtk *)" in s_data["permissions"]["allow"]
    # Running installer twice must not duplicate PreToolUse hooks (1 rtk + 1 supermemory = 2)
    assert len(s_data["hooks"]["PreToolUse"]) == 2
    assert set(s_data["hooks"].keys()) >= {"SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "Stop"}


def test_claude_code_hooks_session_prompt_gates_and_stop(tmp_path: Path) -> None:
    ws = tmp_path / "proj"
    init_workspace(ws, project_name="ClaudeProj", max_lines=50)

    # 1. SessionStart returns Claude Code hookSpecificOutput.additionalContext
    s_out = dispatch_hook("SessionStart", {"hook_event_name": "SessionStart", "session_id": "cc-1", "cwd": str(ws)})
    assert s_out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "ClaudeProj" in s_out["hookSpecificOutput"]["additionalContext"]

    # 2. PreToolUse blocks Claude Code `Write` when exceeding max_lines (50)
    big_py = "\n".join(f"x_{i} = {i}" for i in range(60))
    pre_block = dispatch_hook(
        "PreToolUse",
        {
            "hook_event_name": "PreToolUse",
            "session_id": "cc-1",
            "cwd": str(ws),
            "tool_name": "Write",
            "tool_input": {"file_path": str(ws / "big.py"), "content": big_py},
        },
    )
    assert pre_block["decision"] == "block"
    assert pre_block["hookSpecificOutput"]["permissionDecision"] == "deny"

    # 3. UserPromptSubmit with explicit rule -> Stop blocks until lesson recorded, then Stop with stop_hook_active=True allows
    u_out = dispatch_hook(
        "UserPromptSubmit",
        {
            "hook_event_name": "UserPromptSubmit",
            "session_id": "cc-1",
            "cwd": str(ws),
            "prompt": "từ giờ trở đi cấm dùng biến toàn cục trong file main.py nhớ kĩ quy tắc này",
        },
    )
    assert u_out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"

    stop_1 = dispatch_hook(
        "Stop",
        {"hook_event_name": "Stop", "session_id": "cc-1", "cwd": str(ws), "stop_hook_active": False},
    )
    assert stop_1["decision"] == "block"
    assert "SELF-LEARNING COMMIT REQUIRED" in stop_1["reason"]

    stop_2 = dispatch_hook(
        "Stop",
        {"hook_event_name": "Stop", "session_id": "cc-1", "cwd": str(ws), "stop_hook_active": True},
    )
    assert stop_2 == {}
