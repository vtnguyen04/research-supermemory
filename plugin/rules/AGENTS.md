# SuperMemory v3.0.2 Zero-Overhead Cognitive, Bottleneck-First & Fast-DAG Harness (Global Protocol)

You operate with a **Federated Research Memory** (`Local` `.supermemory/` + `Global` `~/.supermemory/global` + `Sibling Vaults`) across **4 Cognitive Tiers** (`L0 WORKING`, `L1 PROCEDURAL`, `L2 SEMANTIC`, `L3 EPISODIC`):

1. **Zero-Overhead Normal Turns (NO Memory Spam, NO Redundant File Reads):**
   - `SessionStart` automatically injects the active SuperMemory capsule (`Open Bottlenecks`, `Saved SOTA Method Cards`, `Laws`, `Scoreboard`). **Do NOT** re-read `01_ACTIVE_STATE.md` / `02_CONSTITUTION_AND_LESSONS.md` or call `supermemory_graph` MCP tools on normal Q&A, code reading, or conversational clarifications. Answer directly in 1 fast pass.
   - Call `recall` (`include_siblings: true` for R&D) **before starting a non-trivial code change, research proposal, or experiment**.

2. **Bottleneck-First & Zero-Amnesia Research Vault Routing (Enforced at `PreInvocation` & `Stop`):**
   - **Never propose "kitchen-sink" architectures blindly, and NEVER leave research only in chat:**
     - **Pareto Error Slices & Falsifiable RQs:** Save via `diagnose_bottleneck` -> `memory/08_BOTTLENECKS/BNK-XXX.md` + `RQ-XXX`.
     - **Papers & SOTA Mechanisms:** Save via `scout_sota` (`save_top_k >= 1` or `action: "register_card"`) -> `memory/07_METHOD_VAULT/METH-XXX.md`.
     - **Single-Variable Hypotheses / Dead-Ends / Specs:** Save via `propose_idea` or `manage_proposal` -> `memory/05_IDEAS_AND_ALGORITHMS/` & `memory/04_PROPOSALS/`, gated by **Occam ROI** + a **10%-budget early-kill criterion**.
   - **Multi-Agent Fast-DAG Speedup:** On multi-step research sprints, use `orchestrate` to run Wave-1 discovery (`bottleneck-profiler || sota-scout || memory-curator`) in parallel with `< 180`-token receipts and glob-locked Wave-3 slices.

3. **High-Signal Selective Persistence & Full-Tab UI Review:**
   - Call `record_lesson` (+ `CodeGate`) **ONLY** for explicit durable user rules or genuine technical bug post-mortems; log benchmarks via `log_experiment`.
   - After **every** frontend/UI edit, verify zero undefined CSS classes and visually inspect screenshots across **all tabs, modes (Split + Center Modal), and mobile/desktop viewports**, verifying `0px` horizontal overflow, proper card padding/gaps, and `>= 13px` typography.
