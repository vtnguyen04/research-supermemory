# SuperMemory v2.5 Zero-Overhead Cognitive & Federated Harness (Global Protocol)

You operate with a **2-Level Federated Memory** (`Local` `.supermemory/` + `Global` `~/.supermemory/global`) across **4 Cognitive Tiers** (`L0 WORKING`, `L1 PROCEDURAL`, `L2 SEMANTIC`, `L3 EPISODIC`):

1. **Zero-Overhead Normal Turns (NO Memory Spam, NO Redundant File Reads):**
   - `SessionStart` automatically injects the active SuperMemory capsule. **Do NOT** re-read `01_ACTIVE_STATE.md` / `02_CONSTITUTION_AND_LESSONS.md` or call `supermemory_checkpoint` / `supermemory_record_lesson` on normal Q&A, code reading, or conversational clarifications (e.g., *"who said to edit yet?"*, *"explain X"*). Answer directly in 1 fast pass with **zero** memory tool calls.
   - Only call `supermemory_recall` or read `01_ACTIVE_STATE.md` + `02_CONSTITUTION_AND_LESSONS.md` **before starting a non-trivial code change, architectural proposal, or experiment**.

2. **High-Signal Selective Persistence (Only When Real Learning or Milestones Occur):**
   - **Explicit Rule or Real Technical Post-Mortem:** Call `supermemory_record_lesson` (+ `CodeGate` if mechanically checkable) **ONLY** when the user defines a durable rule/preference (`scope: "local"` or `"global"`) or when a genuine bug/architectural mistake was committed and diagnosed.
   - **Scientific Experiments & Milestones:** Call `supermemory_log_experiment` (with non-empty `post_mortem` & `insights` on failures) when benchmarks finish, and `supermemory_update_state` when project milestones change.

3. **Mandatory Post-Fix Full-Tab Visual UI Review:**
   - After **every** frontend/UI edit, never stop after checking a single view: render and visually inspect screenshots across **all tabs, modes, drawers, and mobile/desktop viewports**, verifying zero horizontal overflow (`scrollWidth <= innerWidth`), readable typography (`>= 13px`), and clean pagination.
