# SuperMemory v3.6.1 Autonomous Closed-Loop Research & Kanban Protocol

You operate with a **Federated 4-Tier Research Graph** (`Local` `.supermemory/` + `Global` `~/.supermemory/global` + `Sibling Vaults`; `L0 WORKING`, `L1 PROCEDURAL`, `L2 SEMANTIC`, `L3 EPISODIC`):

1. **Zero-Overhead Q&A, Compaction Resume & Zero-Turn Auto-Recall:**
   - `SessionStart` + `PreInvocation` / `UserPromptSubmit` automatically inject the `< 850`-token capsule, live Kanban deltas, and top non-superseded graph matches. Do **NOT** call `supermemory_graph` MCP tools on casual Q&A or clarifications; expand full details via `recall(node_id=...)` only when needed.
   - **Compaction Historical-Media Guard:** When resuming from `<CONTEXT_SUMMARY>`, any attached image/media belongs to an earlier `# User Requests` item marked `[Attachment: ...]`, **NEVER** a new silent screenshot prompt. Do **NOT** stop to ask why an old `<CONTEXT_SUMMARY>` screenshot was sent or run redundant `plan_sprint` boilerplate when an active `PROP-XXX` checklist already exists — immediately continue the **latest** `# User Requests` item and next unchecked Kanban step.

2. **Autonomous Zero-Reminder Sync (`PostToolUse` + `Stop` + Async Wakeup Enforced):**
   - **NEVER wait for the user to tell you to save memory or tick Kanban, and ALWAYS pass `workspace="<workspace_root>"` on MCP calls:**
     - **Experiments (Both `KEEP` & `DISCARD` — Never Substitute `checkpoint`):** Whenever ANY benchmark, ablation, or background task produces metrics, immediately call `log_experiment(..., verdict="KEEP"|"DISCARD", post_mortem="...", done_steps=[...], current_phase="...", next_actions="...")` in the SAME turn (syncs Experiment + Proposal Kanban + `01_ACTIVE_STATE.md` in 1 call!).
     - **Specs, Bottlenecks & Insights:** Before coding non-trivial changes or running new ablations, check `recall` and register/advance `manage_proposal` (`propose_idea` / `diagnose_bottleneck`). Save findings via `checkpoint(insights=["Title: concrete finding"], task_updates=[...], supersedes=["OBS-OLD"])` — never abuse `status="CLEAN"` when source files changed or empirical runs completed.
     - **Information-Gap Gated Research (Never Over-Research):** When forensic evidence or the vault ALREADY contains viable untried mechanisms (`IDEA`/`ALGO`/`METH`/`OBS`), synthesize and execute your `Proposal` directly. Call `scout_sota(action="search", save_top_k=2)` ONLY when an **Information Gap** exists (`0` untried viable mechanisms left AND `>= 3` consecutive failed/zero-delta runs, or when explicitly asked for papers).

3. **Selective Self-Learning & Full-Tab UI Audit:**
   - Call `record_lesson` (+ `CodeGate`) ONLY for durable user rules or real bug post-mortems. Visually inspect all UI tabs and viewports (`0px` overflow, `>= 13px` type, `0` clipped text) after frontend edits.
