---
name: supermemory-research
description: Information-Gap Gated Research Loop — profile Pareto error slices (BNK-XXX + RQ-XXX), synthesize directly when vault knowledge suffices, and scout external SOTA papers ONLY when an information gap or >=3-run plateau occurs.
---

# SuperMemory v3.6.1 Information-Gap Gated Research Skill

Use this skill ONLY when diagnosing new Pareto bottlenecks, when explicitly asked for external papers, or when hitting a genuine Information Gap (`0` untried viable ideas/methods in the vault AND `>= 3` consecutive failed or `|delta| <= 1e-5` runs). **Do NOT run external paper searches when proposing a method from already-clear forensic evidence.**

## Decision Protocol: Synthesize vs. External Research
1. **Recall Existing Vault First:** Check `recall(query=..., include_siblings=true)` for Proven Wins, Falsified Dead-Ends, and untried `IDEA` / `ALGO` / `METH` nodes.
2. **If Vault / Forensic Evidence Already Explains the Fix (No Information Gap):** Log internal designs via `propose_idea(is_algorithm=True)` and proceed directly to `manage_proposal(bottleneck_id="BNK-...", coupled_vars=1, tasks=[...])` without calling `scout_sota`.
3. **If Information Gap Exists (`0` Untried Mechanisms or `>= 3`-Run Plateau):** Call `scout_sota(action="search", query=..., bottleneck_id="BNK-...", save_top_k=2)` (or `search_web` + `scout_sota(action="register_card", source_url="https://arxiv.org/...")`) to harvest verified external literature into `07_METHOD_VAULT`.
