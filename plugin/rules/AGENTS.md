# SuperMemory v3.5 Autonomous Closed-Loop Research & Kanban Protocol

You operate with a **Federated 4-Tier Research Graph** (`Local` `.supermemory/` + `Global` `~/.supermemory/global` + `Sibling Vaults`; `L0 WORKING`, `L1 PROCEDURAL`, `L2 SEMANTIC`, `L3 EPISODIC`):

1. **Zero-Overhead Q&A & Zero-Turn Auto-Recall:**
   - `SessionStart` + `PreInvocation` / `UserPromptSubmit` automatically inject the `< 850`-token capsule, live Kanban deltas, and top non-superseded graph matches. Do **NOT** call `supermemory_graph` MCP tools on casual Q&A or clarifications; expand full details via `recall(node_id=...)` only when needed.

2. **Autonomous Zero-Reminder Sync (`PostToolUse` + `Stop` Enforced):**
   - **NEVER wait for the user to tell you to save memory or tick Kanban.** Sync in the SAME turn whenever work occurs:
     - **Kanban & Subtasks:** Follow injected `📋 LIVE KANBAN BOARD` items and tick completed steps / transition stages via 1-call `checkpoint(task_updates=[{"id": "...", "stage": "IN_PROGRESS", "done_steps": [...]}], next_actions=...)`.
     - **Insights & Temporal Supersession:** Save findings via `checkpoint(insights=["Title: concrete finding"], supersedes=["OBS-OLD"])` so newer truths automatically demote outdated observations.
     - **Experiments & Anti-Stagnation Research Pivot:** Log quantitative runs via `log_experiment`. If `>= 2` runs fail/revert (`REVERT`/`FAILED`/`DISCARD`) or `>= 3` runs plateau (`delta <= 1e-5`), **STOP local parameter tweaking immediately** and call `scout_sota(action="search", query=..., bottleneck_id="BNK-...", save_top_k=2)` (or `search_web` + `register_card` with a verified `arxiv.org`/`doi.org`/`semanticscholar.org` URL). **NEVER** disguise internal heuristics as `METH-XXX` papers (use `propose_idea(is_algorithm=True)` for internal designs).

3. **Selective Self-Learning & Full-Tab UI Audit:**
   - Call `record_lesson` (+ `CodeGate`) ONLY for durable user rules or real bug post-mortems. Visually inspect all UI tabs and viewports (`0px` overflow, `>= 13px` type, `0` clipped text) after frontend edits.
