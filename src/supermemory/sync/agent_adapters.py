"""Multi-agent harness rule generators (AGENTS.md, GEMINI.md, CLAUDE.md, .agents/, Handoff)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from supermemory.graph.query_engine import QueryEngine
from supermemory.models import NodeType, utc_now_iso
from supermemory.storage.sqlite_store import GraphStore


def generate_agent_files(store: GraphStore, install_workspace_hooks: bool = True) -> Dict[str, str]:
    """Generate concise (< 6 KB) Always-On rules for Antigravity, Claude Code, Cursor, and Codex."""
    root = store.workspace_root
    meta = store.get_all_meta()
    proj = meta.get("project_name") or root.name
    max_lines = meta.get("max_lines") or "300"
    laws = sorted(store.list_nodes(node_types=[NodeType.LAW.value], limit=20), key=lambda x: x.id)

    law_bullets = "\n".join(
        f"{idx}. **`{lw.id}` — {lw.title}:** {lw.summary}"
        for idx, lw in enumerate(laws, 1)
    )

    core_rule_body = (
        f"# 🧠 {proj.upper()} — SUPERMEMORY CONSTITUTION & ZERO-OVERHEAD HARNESS\n\n"
        f"> **⚡ FAST ZERO-OVERHEAD PROTOCOL (NO TURN-SPAM):**\n"
        f"> - `SessionStart` already injects your active capsule. On normal Q&A, chat clarifications, or read-only turns, **do NOT** re-read memory files or call `supermemory_graph` MCP tools — reply directly!\n"
        f"> - **Before non-trivial code edits or new proposals**, read [01_ACTIVE_STATE.md](memory/01_ACTIVE_STATE.md), [02_CONSTITUTION_AND_LESSONS.md](memory/02_CONSTITUTION_AND_LESSONS.md), and query MCP `recall`.\n\n"
        f"---\n\n"
        f"## ⚖️ 1. Non-Negotiable Constitutional Laws (Enforced by PreToolUse & Audit Gates)\n\n"
        f"{law_bullets}\n\n"
        f"---\n\n"
        f"## 🔄 2. Selective High-Signal Memory Loop (Anti-Spam)\n\n"
        f"1. **Progressive Recall (`L1 PROCEDURAL` + `L2 SEMANTIC`):** Query MCP `recall` before proposing/coding non-trivial features so falsified dead-ends are never repeated.\n"
        f"2. **Selective Self-Learning (Never Spam on Casual Chat):** Call MCP `record_lesson` (+ `CodeGate`) **ONLY** for explicit user rules/preferences (`scope='local'` or `'global'`) or genuine technical bug post-mortems — NEVER on casual clarifications. Log real benchmarks via MCP `log_experiment` ([03_EXPERIMENTS_REGISTRY.md](memory/03_EXPERIMENTS_REGISTRY.md)).\n"
        f"3. **Clean Code (`< {max_lines}` lines/file) & Full-Tab UI Visual Audit:** Keep [00_MEMORY_GRAPH.md](memory/00_MEMORY_GRAPH.md) & `01_ACTIVE_STATE.md` synced on milestone completions, and visually inspect ALL UI tabs/viewports after any frontend change.\n"
    )

    written: Dict[str, str] = {}
    for fname in ("AGENTS.md", "GEMINI.md", "CLAUDE.md"):
        fpath = root / fname
        fpath.write_text(core_rule_body, encoding="utf-8")
        written[fname] = str(fpath)

    # Antigravity .agents/rules/ always_on rule
    agy_rules_dir = root / ".agents" / "rules"
    agy_rules_dir.mkdir(parents=True, exist_ok=True)
    agy_rule_path = agy_rules_dir / "00_supermemory_constitution.md"
    agy_rule_path.write_text(
        "---\n"
        "trigger: always_on\n"
        "description: Mandatory SuperMemory knowledge graph recall, anti-regression laws, and self-learning gate loop.\n"
        "---\n\n"
        + core_rule_body,
        encoding="utf-8",
    )
    written[".agents/rules/00_supermemory_constitution.md"] = str(agy_rule_path)

    if install_workspace_hooks:
        hooks_path = root / ".agents" / "hooks.json"
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
