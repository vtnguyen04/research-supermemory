---
name: supermemory-handoff
description: Generate a zero-loss HANDOFF_BRIEFING.md and synchronized graph_snapshot.json before context compaction (/compact) or switching between AI agents (Antigravity, Claude Code, Gemini CLI, Codex).
---

# SuperMemory Compaction & Cross-Agent Handoff Skill

Use this skill whenever preparing for `/compact`, wrapping up a long session, or handing the repository to another agent or teammate.

## Steps
1. Call `update_state` to ensure `active_goal`, `current_phase`, `primary_targets`, and `next_actions` reflect exact reality.
2. If the vault has accumulated many raw observations or completed specs, spawn the `memory-curator` subagent (`consolidate(mode="review")` -> semantic review -> `consolidate(mode="apply_plan")`) so duplicates and older clusters are distilled with zero metric loss.
3. Call `record_audit` with `generate_handoff: true` (or run CLI `supermemory handoff`) and verify `memory/HANDOFF_BRIEFING.md`, `memory/01_ACTIVE_STATE.md`, and `memory/graph_snapshot.json`.
