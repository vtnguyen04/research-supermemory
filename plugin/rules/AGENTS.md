# SuperMemory Constitutional Harness (Global Antigravity Protocol)

When working inside any workspace initialized with SuperMemory (`memory/00_MEMORY_GRAPH.md` or `.supermemory/supermemory.db`), you MUST enforce Zero-Amnesia and Self-Learning Anti-Regression discipline across compactions and agent handoffs:

1. **Recall Before Proposing or Coding (`supermemory_recall`):**
   - Before proposing an idea, refactoring a module, or launching an experiment, query `supermemory_recall` (or CLI `supermemory recall "<topic>"`) to retrieve Constitutional `LAW`s, past `LESSON`s, prior `EXPERIMENT` verdicts, and `REJECTED` dead-end ideas. Never repeat a recorded dead-end without a new falsifiable mechanism.
2. **Self-Learning Mistake-to-Gate Loop (`supermemory_record_lesson`):**
   - Whenever the user corrects/scolds an error, or a bug/regression is uncovered, IMMEDIATELY call `supermemory_record_lesson` (or `supermemory learn`) BEFORE ending your turn.
   - Consolidate the root cause into an existing `LAW` (never bloat `02_CONSTITUTION_AND_LESSONS.md` past 200 lines) and attach a `forbid_regex` / `forbid_cmd_regex` / `FROZEN_SHA256` `CodeGate` whenever mechanically enforceable so `PreToolUse` blocks any recurrence.
3. **Clean Code & Anti-Sprawl (`LAW-02`):**
   - Keep source files modular (`< 300` lines by default unless workspace config specifies otherwise).
   - Never create throwaway scripts (`debug_*.py`, `tmp_*.py`, `*_v2.py`) in the project tree.
   - Never modify frozen evaluators/verifiers protected by `FROZEN_SHA256` gates.
4. **OpenSpec Lifecycle & Scientific Single-Variable Experiments:**
   - Track non-trivial architecture changes via `supermemory_propose_idea` and `supermemory_manage_proposal` (`PROPOSED -> DESIGNED -> IMPLEMENTING -> CHALLENGED -> AUDITED -> ARCHIVED`).
   - Log every benchmark/experiment run via `supermemory_log_experiment` with an explicit `hypothesis`, `single_var_diff`, CV/Test metrics, baseline comparison, and `post_mortem`.
5. **Compaction & Handoff Survival (`supermemory_update_state`):**
   - Before `/compact`, milestone completion, or switching to another agent, call `supermemory_update_state` (and `supermemory_record_audit` with `generate_handoff: true` when handing off) so `memory/01_ACTIVE_STATE.md` and `memory/graph_snapshot.json` remain 100% up to date.
