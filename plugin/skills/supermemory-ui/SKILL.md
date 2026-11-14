---
name: supermemory-ui
description: Launch the interactive SuperMemory Knowledge Graph Web Observatory to visually explore project Laws, Mistakes/Lessons, Gate Shield blocks, Scientific Experiments, Proposals, and Event Telemetry.
---

# SuperMemory Graph Web Observatory Skill

Use this skill when the user wants to visually inspect the entire project memory graph, mistakes, lessons, proposals, or experiment progression in the browser.

## Launching the Observatory
1. Run `supermemory ui --workspace <workspace_path> --port 8765` (use `IsDaemon: true` if launching from an agent tool call so it stays running in the background).
2. Share the live URL (`http://127.0.0.1:8765`) with the user.
3. Highlight available tabs:
   - **Knowledge Graph:** Interactive force-directed graph with BM25 + 2-hop search, node-type filters, and 1-hop lineage inspector.
   - **Laws, Mistakes & Gates:** Constitutional LAWs, consolidated user corrections, and `PreToolUse` gate block counters.
   - **Scientific Experiments:** Track filter, SVG metric progression curve, and hypothesis/diff ledger.
   - **Proposals & Idea Vault:** OpenSpec stage Kanban + Dead-End Idea/Algorithm vault.
   - **Harness Event Stream:** Real-time hook & self-learning audit log.
