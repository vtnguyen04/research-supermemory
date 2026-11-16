"""Claude Code Native Installer: Registers MCP server, Lifecycle Hooks, Skills & Subagents."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List


def _resolve_supermemory_bin() -> str:
    local_bin = Path.home() / ".local" / "bin" / "supermemory"
    if local_bin.is_file():
        return str(local_bin)
    found = shutil.which("supermemory")
    return found or str(local_bin)


def _strip_existing_sm_hooks(hook_groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep all non-SuperMemory hook entries (e.g. GitNexus, RTK) intact."""
    kept: List[Dict[str, Any]] = []
    for grp in hook_groups:
        if not isinstance(grp, dict):
            continue
        inner = grp.get("hooks") or []
        filtered = [
            h
            for h in inner
            if isinstance(h, dict)
            and not ("supermemory" in str(h.get("command") or "") and " hook " in str(h.get("command") or ""))
        ]
        if filtered:
            new_grp = dict(grp)
            new_grp["hooks"] = filtered
            kept.append(new_grp)
    return kept


def install_claude_code_integration(
    plugin_src: Path,
    claude_dir: Path | None = None,
    claude_json_path: Path | None = None,
) -> Dict[str, Any]:
    """Install SuperMemory MCP server, 5 lifecycle hooks, 9 skills, and 8 agents into Claude Code."""
    c_dir = (claude_dir or (Path.home() / ".claude")).resolve()
    c_json = (claude_json_path or (Path.home() / ".claude.json")).resolve()
    sm_bin = _resolve_supermemory_bin()

    c_dir.mkdir(parents=True, exist_ok=True)
    skills_dst = c_dir / "skills"
    agents_dst = c_dir / "agents"
    skills_dst.mkdir(parents=True, exist_ok=True)
    agents_dst.mkdir(parents=True, exist_ok=True)

    # 1. Sync 9 skills into ~/.claude/skills/
    installed_skills: List[str] = []
    skills_src = plugin_src / "skills"
    if skills_src.is_dir():
        for sk in sorted(skills_src.iterdir()):
            if sk.is_dir() and (sk / "SKILL.md").is_file():
                dst = skills_dst / sk.name
                if dst.is_symlink() or dst.is_file():
                    dst.unlink()
                elif dst.is_dir():
                    shutil.rmtree(dst)
                shutil.copytree(sk, dst)
                installed_skills.append(sk.name)

    # 2. Sync 8 agents into ~/.claude/agents/
    installed_agents: List[str] = []
    agents_src = plugin_src / "agents"
    if agents_src.is_dir():
        for ag in sorted(agents_src.glob("*.md")):
            dst = agents_dst / ag.name
            shutil.copy2(ag, dst)
            installed_agents.append(ag.stem)

    # 3. Register MCP server `supermemory_graph` in ~/.claude.json
    c_data: Dict[str, Any] = {}
    if c_json.is_file():
        try:
            c_data = json.loads(c_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            c_data = {}
    mcp_servers = c_data.setdefault("mcpServers", {})
    mcp_servers["supermemory_graph"] = {
        "type": "stdio",
        "command": sm_bin,
        "args": ["mcp"],
        "env": {},
    }
    c_json.write_text(json.dumps(c_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 4. Register Hooks & MCP Permissions in ~/.claude/settings.json
    settings_path = c_dir / "settings.json"
    settings: Dict[str, Any] = {}
    if settings_path.is_file():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            settings = {}

    perms = settings.setdefault("permissions", {})
    allow_list: List[str] = list(perms.get("allow") or [])
    for rule in ("mcp__supermemory_graph__*", "Bash(supermemory *)"):
        if rule not in allow_list:
            allow_list.append(rule)
    perms["allow"] = allow_list

    hooks_cfg: Dict[str, Any] = settings.setdefault("hooks", {})
    sm_events: Dict[str, Dict[str, Any]] = {
        "SessionStart": {"matcher": "*", "cmd": f'"{sm_bin}" hook SessionStart', "timeout": 10},
        "UserPromptSubmit": {"matcher": None, "cmd": f'"{sm_bin}" hook UserPromptSubmit', "timeout": 10},
        "PreToolUse": {"matcher": "Write|Edit|MultiEdit|Bash", "cmd": f'"{sm_bin}" hook PreToolUse', "timeout": 10},
        "PostToolUse": {"matcher": "*", "cmd": f'"{sm_bin}" hook PostToolUse', "timeout": 10},
        "Stop": {"matcher": None, "cmd": f'"{sm_bin}" hook Stop', "timeout": 10},
    }
    for ev, spec in sm_events.items():
        existing = _strip_existing_sm_hooks(list(hooks_cfg.get(ev) or []))
        entry: Dict[str, Any] = {
            "hooks": [{"type": "command", "command": spec["cmd"], "timeout": spec["timeout"]}],
        }
        if spec["matcher"]:
            entry["matcher"] = spec["matcher"]
        existing.append(entry)
        hooks_cfg[ev] = existing

    settings_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "mcp_server": "supermemory_graph",
        "binary": sm_bin,
        "skills": installed_skills,
        "agents": installed_agents,
        "hooks": list(sm_events.keys()),
        "settings_path": str(settings_path),
        "claude_json_path": str(c_json),
    }
