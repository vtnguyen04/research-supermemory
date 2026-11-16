# SuperMemory v3.2 Autonomous Closed-Loop Cognitive & Kanban Protocol

You operate with a **Federated 4-Tier Research Graph** (`Local` `.supermemory/` + `Global` `~/.supermemory/global` + `Sibling Vaults`; `L0 WORKING`, `L1 PROCEDURAL`, `L2 SEMANTIC`, `L3 EPISODIC`):

1. **Zero-Overhead Q&A & 2-Stage Progressive Recall:**
   - `SessionStart` injects the `< 850`-token capsule. Do **NOT** call `supermemory_graph` MCP tools on casual Q&A or clarifications.
   - Before non-trivial code edits, implementations, or proposals, call `recall` (`compact: true`, `include_siblings: true` for R&D); expand full nodes via `recall(node_id=...)` only when needed.

2. **Autonomous Zero-Reminder Sync (Tasks, Insights & Results — `PostToolUse` + `Stop` Enforced):**
   - **NEVER wait for the user to tell you to save memory.** Update SuperMemory proactively in the SAME turn whenever real work, insights, or results occur:
     - **Tasks & Kanban Subtasks:** Create/move active work on Kanban (`orchestrate` or `checkpoint(new_task={...})`) and check off completed steps + stage transitions via 1-call `checkpoint(task_updates=[...], next_actions=...)`.
     - **Technical & Empirical Insights:** Persist every root-cause, architectural finding, or diagnostic observation immediately via `checkpoint(insights=["Title: concrete finding"])` (`OBS-XXX`).
     - **Experiments, Bottlenecks & SOTA Papers:** Log quantitative runs via `log_experiment`, Pareto error slices via `diagnose_bottleneck` (`08_BOTTLENECKS/`), papers via `scout_sota` (`07_METHOD_VAULT/`), and single-variable specs via `propose_idea` / `manage_proposal`.

3. **Selective Self-Learning & Full-Tab UI Audit:**
   - Call `record_lesson` (+ `CodeGate`) ONLY for durable user rules or real bug post-mortems. Visually inspect all UI tabs and viewports (`0px` overflow, `>= 13px` type) after frontend edits.
