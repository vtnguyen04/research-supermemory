# SuperMemory v3.0.3 Zero-Bloat 4-Tier Cognitive & Fast-DAG Protocol

You operate with a **Federated 4-Tier Research Graph** (`Local` `.supermemory/` + `Global` `~/.supermemory/global` + `Sibling Vaults`; `L0 WORKING`, `L1 PROCEDURAL`, `L2 SEMANTIC`, `L3 EPISODIC`):

1. **Zero-Overhead Normal Turns & 2-Stage Progressive Recall:**
   - `SessionStart` injects the `< 850`-token capsule. Do **NOT** re-read memory files or call `supermemory_graph` MCP tools on normal Q&A or clarifications.
   - Before non-trivial code edits or proposals, call `recall` (`compact: true`, `include_siblings: true` for R&D); expand full nodes via `recall(node_id=...)` or `read_file` only when needed.

2. **Bottleneck-First Research Vault Routing (`PreInvocation` & `Stop` Enforced):**
   - Never leave external research only in chat: persist Pareto slices via `diagnose_bottleneck` (`08_BOTTLENECKS/BNK-XXX.md`), SOTA papers via `scout_sota` (`07_METHOD_VAULT/METH-XXX.md`), and single-variable hypotheses via `propose_idea` / `manage_proposal` (gated by Occam ROI + 10% early-kill). Use `orchestrate` for 3-Wave parallel Fast-DAG sprints (`< 180`-token receipts).

3. **Selective Self-Learning & Full-Tab UI Audit:**
   - Call `record_lesson` (+ `CodeGate`) ONLY for explicit durable user rules or real bug post-mortems; log benchmarks via `log_experiment`. Visually inspect all UI tabs, Split/Center Modal modes, and mobile/desktop viewports (`0px` overflow, `>= 13px` type, `0` undefined CSS classes) after frontend edits.
