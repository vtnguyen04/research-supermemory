# SuperMemory v3.6.0 Autonomous Closed-Loop Research & Kanban Protocol

You operate with a **Federated 4-Tier Research Graph** (`Local` `.supermemory/` + `Global` `~/.supermemory/global` + `Sibling Vaults`; `L0 WORKING`, `L1 PROCEDURAL`, `L2 SEMANTIC`, `L3 EPISODIC`):

1. **Zero-Overhead Q&A & Zero-Turn Auto-Recall:**
   - `SessionStart` + `PreInvocation` / `UserPromptSubmit` automatically inject the `< 850`-token capsule, live Kanban deltas, and top non-superseded graph matches. Do **NOT** call `supermemory_graph` MCP tools on casual Q&A or clarifications; expand full details via `recall(node_id=...)` only when needed.

2. **Autonomous Zero-Reminder Sync (`PostToolUse` + `Stop` Enforced):**
   - **NEVER wait for the user to tell you to save memory or tick Kanban.** Sync in the SAME turn whenever work occurs:
     - **Kanban & Subtasks:** Follow injected `📋 LIVE KANBAN BOARD` items and tick completed steps / transition stages via 1-call `checkpoint(task_updates=[{"id": "...", "stage": "IN_PROGRESS", "done_steps": [...]}], next_actions=...)`.
     - **Insights & Temporal Supersession:** Save findings via `checkpoint(insights=["Title: concrete finding"], supersedes=["OBS-OLD"])` so newer truths automatically demote outdated observations.
     - **Information-Gap Gated Research (Never Over-Research):** When forensic evidence or the vault ALREADY contains viable untried mechanisms (`IDEA`/`ALGO`/`METH`/`OBS`), synthesize and execute your `Proposal` directly — do **NOT** run external paper searches unnecessarily. Call `scout_sota(action="search", save_top_k=2)` ONLY when an **Information Gap** exists (`0` untried viable mechanisms left AND `>= 3` consecutive failed/zero-delta runs, or when explicitly asked for papers). Use `propose_idea(is_algorithm=True)` for internal designs; reserve `METH-XXX` strictly for external URLs (`arxiv.org`/`doi.org`/`semanticscholar.org`).

3. **Selective Self-Learning & Full-Tab UI Audit:**
   - Call `record_lesson` (+ `CodeGate`) ONLY for durable user rules or real bug post-mortems. Visually inspect all UI tabs and viewports (`0px` overflow, `>= 13px` type, `0` clipped text) after frontend edits.
