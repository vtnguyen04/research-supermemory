# SuperMemory v2.0 Cognitive & Federated Harness (Global Antigravity Protocol)

You operate with a **2-Level Federated Memory** (`Local` per-project folder `.supermemory/` + `Global` cross-project `~/.supermemory/global`) organized into **4 Cognitive Tiers** (`L0 WORKING`, `L1 PROCEDURAL`, `L2 SEMANTIC`, `L3 EPISODIC`) so you NEVER forget across `/compact` or agent switches and NEVER suffer context bloat:

1. **Progressive Recall Before Proposing or Coding (`supermemory_recall`):**
   - Query `supermemory_recall` (searches both Local + Global `PROCEDURAL` & `SEMANTIC` tiers via BM25 + 2-hop graph without dumping raw `EPISODIC` logs). Never repeat a recorded `REJECTED` idea, `REVERT`ed experiment, or `FAILURE_INSIGHT`.
   - If the current folder has no Local `.supermemory/` yet, Global SuperMemory (`scope: "global"`) is still active; run `supermemory_init` (`supermemory init`) whenever the user wants a dedicated Local SuperMemory for that folder.

2. **Agent-Native Semantic Self-Triage on EVERY Turn (Zero Keyword Dependence):**
   - Do NOT wait for explicit keywords — use your **full semantic understanding** of the user's tone, subtle hints, and tool outputs on every turn:
     - **Any user critique, frustration, or mistake uncovered:** Immediately call `supermemory_record_lesson` (consolidate into `LAW-XX` + bind `forbid_regex` / `forbid_cmd_regex` / `freeze_path` `CodeGate`).
     - **Any new user rule, coding preference, or workflow:** Persist via `supermemory_record_lesson` / `supermemory_add_gate` (`scope: "local"` for repo-specific, `scope: "global"` for cross-project preferences).
     - **Any failed experiment, debugging discovery, or reusable insight:** Call `supermemory_log_experiment` (with non-empty `post_mortem` & `insights` -> auto-creates `OBS-XXX` Semantic nodes) or `supermemory_link_knowledge` (`PROCEDURE` / `KNOWLEDGE_NODE`).
     - **Pure read-only Q&A with zero memory delta:** Call `supermemory_checkpoint(status="CLEAN")` before ending your turn so the `Stop` turn-attestation gate passes cleanly.

3. **Anti-Bloat Memory Consolidation (`supermemory_consolidate`):**
   - Keep `01_ACTIVE_STATE.md < 150` lines and `02_CONSTITUTION_AND_LESSONS.md < 200` lines. Periodically merge clusters of raw `EPISODIC` runs/lessons into compact `SEMANTIC` or `PROCEDURAL` nodes (`supermemory_consolidate`), and promote universal breakthroughs to Global (`mode: "promote"`).
