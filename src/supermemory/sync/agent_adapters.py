"""Multi-agent harness rule generators (AGENTS.md, GEMINI.md, CLAUDE.md, .agents/, Handoff)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from supermemory.graph.query_engine import QueryEngine
from supermemory.models import NodeType, utc_now_iso
from supermemory.storage.sqlite_store import GraphStore


def _purge_duplicate_rule_files(root: Path) -> List[str]:
    """Remove legacy SuperMemory-generated duplicate rule files that cause 3x-4x prompt injection."""
    removed: List[str] = []
    agy_dup = root / ".agents" / "rules" / "00_supermemory_constitution.md"
    if agy_dup.is_file():
        agy_dup.unlink()
        removed.append(".agents/rules/00_supermemory_constitution.md")
        rules_dir = agy_dup.parent
        if rules_dir.is_dir() and not any(rules_dir.iterdir()):
            rules_dir.rmdir()

    gemini_dup = root / "GEMINI.md"
    if gemini_dup.is_file():
        try:
            txt = gemini_dup.read_text(encoding="utf-8")
            if "SUPERMEMORY CONSTITUTION" in txt:
                gemini_dup.unlink()
                removed.append("GEMINI.md")
        except OSError:
            pass
    return removed


def generate_agent_files(store: GraphStore, install_workspace_hooks: bool = True) -> Dict[str, str]:
    """Generate single canonical AGENTS.md (< 400 tokens) + @AGENTS.md pointer for Claude Code."""
    root = store.workspace_root
    meta = store.get_all_meta()
    proj = meta.get("project_name") or root.name
    max_lines = meta.get("max_lines") or "300"
    laws = sorted(store.list_nodes(node_types=[NodeType.LAW.value], limit=20), key=lambda x: x.id)

    law_bullets = "\n".join(
        f"- **`{lw.id}`** {lw.title[:72]}"
        + (f": {(lw.summary or '')[:60]}" if len(lw.title) < 44 and lw.summary else "")
        for lw in laws
    )

    core_rule_body = (
        f"# {proj.upper()} — SUPERMEMORY CONSTITUTION\n\n"
        f"> **Zero-Overhead:** `SessionStart` injects capsule (`<850` tok). Reply directly on Q&A (`0` MCP calls). "
        f"Before non-trivial edits/proposals, read `memory/01_ACTIVE_STATE.md`, `memory/02_CONSTITUTION_AND_LESSONS.md`, & `recall`.\n\n"
        f"## 1. Laws (PreToolUse Enforced)\n"
        f"{law_bullets}\n\n"
        f"## 2. Vault Routing & Persistence (`<{max_lines}`L)\n"
        f"- **Recall:** `recall(query, include_siblings=True)` -> Stage-2 `recall(node_id=...)` on demand.\n"
        f"- **Research Vaults:** Slices -> `diagnose_bottleneck` (`08_BOTTLENECKS/`); Papers -> `scout_sota` (`07_METHOD_VAULT/`); Specs -> `propose_idea`/`manage_proposal`.\n"
        f"- **Lessons & Benchmarks:** `record_lesson` (+ `CodeGate`) ONLY for durable rules/post-mortems; `log_experiment` for runs; inspect all UI tabs/viewports after UI edits.\n"
    )

    _purge_duplicate_rule_files(root)
    written: Dict[str, str] = {}
    agents_path = root / "AGENTS.md"
    agents_path.write_text(core_rule_body, encoding="utf-8")
    written["AGENTS.md"] = str(agents_path)

    # Lightweight @AGENTS.md import pointer for Claude Code (0 duplicate tokens in Antigravity/Codex)
    claude_path = root / "CLAUDE.md"
    write_claude_ptr = not claude_path.is_file()
    if claude_path.is_file():
        try:
            existing_claude = claude_path.read_text(encoding="utf-8")
            if "SUPERMEMORY CONSTITUTION" in existing_claude or existing_claude.strip().startswith("@AGENTS.md"):
                write_claude_ptr = True
        except OSError:
            write_claude_ptr = False
    if write_claude_ptr:
        claude_path.write_text("@AGENTS.md\n", encoding="utf-8")
        written["CLAUDE.md"] = str(claude_path)

    if install_workspace_hooks:
        hooks_path = root / ".agents" / "hooks.json"
        hooks_path.parent.mkdir(parents=True, exist_ok=True)
        if not hooks_path.exists():
            hooks_cfg = {
                "supermemory-workspace-guard": {
                    "enabled": True,
                    "PreToolUse": [
                        {
                            "matcher": "write_file|edit_file|run_command",
                            "hooks": [{"type": "command", "command": "supermemory hook PreToolUse", "timeout": 10}],
                        }
                    ],
                }
            }
            hooks_path.write_text(json.dumps(hooks_cfg, indent=2) + "\n", encoding="utf-8")
            written[".agents/hooks.json"] = str(hooks_path)

    return written


def generate_handoff_briefing(store: GraphStore) -> Path:
    """Create a comprehensive compaction-proof & cross-agent HANDOFF_BRIEFING.md."""
    qe = QueryEngine(store)
    capsule = qe.build_session_capsule()
    analytics = qe.graph_analytics()
    lessons = store.list_nodes(node_types=[NodeType.LESSON.value], limit=10)
    exps = store.list_experiments()[-6:]

    lines: List[str] = [
        "# 🤝 SUPERMEMORY ZERO-LOSS AGENT HANDOFF BRIEFING",
        "",
        f"- **Generated At:** `{utc_now_iso()}`",
        f"- **Graph Scale:** `{analytics['total_nodes']}` nodes, `{analytics['total_edges']}` edges, "
        f"`{analytics['total_gates']}` active gates (`{analytics['total_blocked_regressions']}` blocked regressions)",
        "",
        "## 1. Executive Capsule",
        "",
        capsule,
        "",
        "## 2. Most Recent Lessons & Forbidden Traps (DO NOT REPEAT)",
        "",
    ]
    if lessons:
        for ls in lessons[-6:]:
            lines.append(f"- **`{ls.id}`** ({ls.title}): {ls.summary}")
    else:
        lines.append("- None recorded yet.")

    lines.extend(["", "## 3. Recent Experiment Lineage", ""])
    if exps:
        for ex in reversed(exps):
            lines.append(
                f"- **`{ex.exp_id}`** [`{ex.track}` / `{ex.verdict}`]: {ex.title} | "
                f"CV=`{ex.cv_summary}` | Test=`{ex.test_summary}` | Post-Mortem: {ex.post_mortem[:140]}"
            )
    else:
        lines.append("- None recorded yet.")

    lines.extend([
        "",
        "## 4. Onboarding Checklist for Incoming Agent",
        "1. Read `memory/01_ACTIVE_STATE.md` and `memory/02_CONSTITUTION_AND_LESSONS.md` in full.",
        "2. Run `supermemory audit` to verify workspace gate compliance before editing.",
        "3. Run `supermemory recall \"<your task>\"` to check prior dead-ends and insights.",
    ])

    out = store.mem_dir / "HANDOFF_BRIEFING.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    store.log_event("HANDOFF_GENERATED", "HANDOFF_BRIEFING", "Generated cross-agent handoff briefing")
    return out
