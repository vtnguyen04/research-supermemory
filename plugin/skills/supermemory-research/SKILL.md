---
name: supermemory-research
description: Bottleneck-First & Anti-Stagnation Research Loop — profile Pareto error slices (BNK-XXX + RQ-XXX), scout verified external SOTA literature into 07_METHOD_VAULT (METH-XXX), and break local hill-climbing plateaus.
---

# SuperMemory v3.5 Bottleneck-First & Anti-Stagnation Research Skill

Use this skill whenever starting R&D, diagnosing bottlenecks, hitting an experiment plateau (`>= 2` failed/reverted runs or `>= 3` flat tweaks), or searching external SOTA literature.

## 4-Step Anti-Stagnation & Zero-Hallucination Protocol
1. **Cross-Workspace Recall:** Call `recall(query=..., include_siblings=true)` to surface current non-superseded insights, reusable `METHOD_CARD`s, and `Dead-End` warnings.
2. **Quantify the Pareto Bottleneck First:** Decompose validation failure slices and call `diagnose_bottleneck(action="diagnose", title=..., evidence_slice=..., error_share_pct=..., ceiling_gain=..., falsifiable_rq=..., kill_criterion=...)` (`BNK-XXX` + `RQ-XXX`).
3. **Scout Verified External SOTA (`07_METHOD_VAULT`):** Call `scout_sota(action="search", query=..., bottleneck_id="BNK-...", save_top_k=2)` (or `search_web` + `scout_sota(action="register_card", source_url="https://arxiv.org/...")`). **Strict Citation Gate:** `METH-XXX` is strictly for external scholarly papers/repositories — NEVER register internal forensic notes or local heuristics as fake papers (use `propose_idea(is_algorithm=True)` for internal designs).
4. **Occam Single-Variable Spec:** Create a single-variable proposal via `manage_proposal(bottleneck_id="BNK-...", coupled_vars=1, tasks=[...])` and tick each Kanban subtask via `checkpoint(task_updates=[...])` as you execute.
