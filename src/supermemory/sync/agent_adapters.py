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

    state_uri = (root / "memory/01_ACTIVE_STATE.md").as_posix()
    const_uri = (root / "memory/02_CONSTITUTION_AND_LESSONS.md").as_posix()
    graph_uri = (root / "memory/00_MEMORY_GRAPH.md").as_posix()
    exp_uri = (root / "memory/03_EXPERIMENTS_REGISTRY.md").as_posix()

    law_bullets = "\n".join(
        f"{idx}. **`{lw.id}` — {lw.title}:** {lw.summary}"
        for idx, lw in enumerate(laws, 1)
    )

    core_rule_body = (
        f"# 🧠 {proj.upper()} — MANDATORY SUPERMEMORY HARNESS & CONSTITUTION\n\n"
        f"> **⚠️ CRITICAL EVERY-TURN PROTOCOL (COMPACTION & MULTI-AGENT PROOF):**\n"
        f"> Before proposing or editing any code, ALWAYS read:\n"
        f"> 1. [01_ACTIVE_STATE.md](file://{state_uri}) (Live goals, phase & next steps)\n"
        f"> 2. [02_CONSTITUTION_AND_LESSONS.md](file://{const_uri}) (`< 200` lines — read 100% in ONE call!)\n"
        f"> 3. Query prior ideas/experiments/mistakes via `supermemory recall \"<topic>\"` (or MCP `supermemory_recall`).\n\n"
        f"---\n\n"
        f"## ⚖️ 1. Non-Negotiable Constitutional Laws (Enforced by PreToolUse & Audit Gates)\n\n"
        f"{law_bullets}\n\n"
        f"---\n\n"
        f"## 🔄 2. Cognitive Tiers, Semantic Self-Triage & Federated Loop\n\n"
        f"1. **Federated Progressive Recall (`L1 PROCEDURAL` + `L2 SEMANTIC`):** Query `supermemory recall \"<topic>\"` (`supermemory_recall`) before proposing/coding. Raw `L3 EPISODIC` logs stay paged on disk so context never bloats.\n"
        f"2. **Agent-Native Semantic Self-Triage (Every Turn):** Use YOUR semantic comprehension (never wait for magic keywords): autonomously persist any subtle/explicit user critique (`supermemory_record_lesson` + `CodeGate`), new rule/preference (`scope='local'` or `'global'`), failed experiment/insight (`supermemory_log_experiment` with `insights` -> [03_EXPERIMENTS_REGISTRY.md](file://{exp_uri})), or state update; if pure read-only Q&A, call `supermemory_checkpoint`.\n"
        f"3. **Spec-First & Clean Code (`< {max_lines}` lines/file):** Track non-trivial work via `PROPOSAL` (`PROPOSED -> ... -> AUDITED -> ARCHIVED`), consolidate episodic clusters via `supermemory consolidate`, and keep [00_MEMORY_GRAPH.md](file://{graph_uri}) & `01_ACTIVE_STATE.md` synced atomically.\n"
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
