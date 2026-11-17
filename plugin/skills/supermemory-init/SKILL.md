---
name: supermemory-init
description: Initialize SuperMemory Knowledge Graph, Constitutional Laws, PreToolUse CodeGates, and multi-agent rules in a project, or import an existing ZALOAI/OpenSpec workspace.
---

# SuperMemory Initialization Skill

Use this skill when bootstrapping SuperMemory in a new or existing project so that every Law, Lesson, CodeGate, Idea, Proposal, and Scientific Experiment survives context compaction and cross-agent handoffs.

## Steps
1. Call MCP tool `init` (or run CLI `supermemory init . --name "<ProjectName>" --max-lines 500 --goal "<PrimaryGoal>"`).
2. Freeze critical evaluators, benchmark scripts, or ground-truth schemas using `add_gate` (`freeze_path: "<relpath>"`, `law_id: "LAW-05"`) or `supermemory gate freeze <relpath>`.
3. Update initial active state via `update_state` (`active_goal`, `current_phase`, `primary_targets`, `next_actions`).
4. Run `audit_gates` (or `supermemory audit`) to confirm baseline Clean Code compliance (`0` violations).
