---
name: supermemory-ui
description: Launch the interactive SuperMemory Knowledge Graph Web Observatory to visually explore project Laws, Mistakes/Lessons, Gate Shield blocks, Scientific Experiments, Proposals, and Event Telemetry.
---

# SuperMemory Graph Web Observatory Skill

Use this skill when the user wants to visually inspect the entire project memory graph, mistakes, lessons, proposals, or experiment progression in the browser.

## Launching the Observatory
1. Run `supermemory ui --workspace <workspace_path> --port 8765` (use `IsDaemon: true` if launching from an agent tool call so it stays running in the background).
2. Share the live URL (`http://127.0.0.1:8765`) with the user.
3. Highlight available 8 Studio tabs:
   - **Knowledge Graph:** Interactive Force / Radial / Hierarchy / Lanes graph with `Active Core` decluttering, BM25 + 2-hop search, and lineage inspector.
   - **Kanban & Tasks:** Drag-and-drop task/proposal board + dense list view with subtask checkboxes.
   - **Research & DAG:** Pareto bottleneck ranking, SOTA `METH-XXX` method vault, and 3-wave Fast-DAG sprint waves.
   - **Laws & Gates:** Constitutional LAWs, consolidated user corrections, and `PreToolUse` gate block counters.
   - **Tier Compaction:** 4-tier token telemetry and REM consolidation studio (`L3/L2 -> SEM-XXX`).
   - **Experiment Ledger:** Track filter, chronological SVG metric progression curve, and minimization/maximization sorting.
   - **Proposals & Ideas:** OpenSpec proposal stage progression + Insights / Algorithms / Dead-End vault.
   - **System Events:** Live hook, recall (`MEMORY_RECALLED`/`MEMORY_READ`), compaction, and audit telemetry stream.
