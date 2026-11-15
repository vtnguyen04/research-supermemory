---
name: supermemory-research
description: Bottleneck-First Research Loop — profile Pareto error slices (BNK-XXX + RQ-XXX), scout SOTA literature into 07_METHOD_VAULT (METH-XXX), and enforce Occam's Razor ROI against bloated kitchen-sink ideas.
---

# SuperMemory v3.0 Bottleneck-First Research Skill

Use this skill whenever starting R&D, diagnosing model/system bottlenecks, searching SOTA literature, or formulating new research hypotheses.

## 4-Step Bottleneck-First Protocol
1. **Cross-Workspace & Hybrid Utility Recall:** Call `supermemory_recall(query=..., include_siblings=true)` to retrieve high-utility insights, reusable `METHOD_CARD`s across sibling repos, and structural dead-end fingerprints.
2. **Quantify the Pareto Bottleneck First (No Blind Ideation):** Decompose errors/regret on validation slices and call `supermemory_diagnose_bottleneck(action="diagnose", title=..., evidence_slice=..., error_share_pct=..., ceiling_gain=..., falsifiable_rq=..., kill_criterion=...)` to mint `BNK-XXX` + `RQ-XXX`.
3. **Scout SOTA Methods into `07_METHOD_VAULT`:** Call `supermemory_scout_sota(action="search", query=..., bottleneck_id="BNK-001", save_top_k=2)` (or `action="register_card"`) to store concise `METH-XXX` cards with core math mechanism, failure assumptions, complexity cost, and `< 100 LOC` integration hook.
4. **Occam's Razor ROI Gate:** Call `supermemory_diagnose_bottleneck(action="propose_hypothesis", bottleneck_id="BNK-001", coupled_vars=1, est_loc=..., kill_criterion=...)`. Never couple multiple paradigms in one experiment; let `Occam ROI` select the simplest high-ceiling mechanism.
