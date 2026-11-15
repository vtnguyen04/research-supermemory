---
name: supermemory-propose
description: Manage the full Idea -> Algorithm -> OpenSpec Proposal lifecycle (PROPOSED -> DESIGNED -> IMPLEMENTING -> CHALLENGED -> AUDITED -> ARCHIVED) with mandatory Dead-End Anti-Repeat checks.
---

# SuperMemory Proposal & Idea Vault Skill

Use this skill before implementing non-trivial features, algorithms, or architectural changes.

## Workflow
1. **Anti-Repeat Recall:** Call `recall` with the core concept/module keywords. Review all `anti_repeat_warnings`, past `LESSON`s, and `REJECTED` ideas.
2. **Idea / Algorithm Registration:** Call `propose_idea` to record the candidate `IDEA` or `ALGORITHM` (`is_algorithm: true` with explicit `invariants`). If an idea is discarded during analysis, log it with `status: "REJECTED"` and `rejection_reason` so future agents never waste time re-inventing it.
3. **Create OpenSpec Artifacts:** Call `manage_proposal` (`action: "create"`, `title`, `why`, `what_changes`, `design_notes`, `tasks`). This writes `openspec/changes/<PROP-ID>/{proposal.md,design.md,tasks.md}` and links it into the Knowledge Graph.
4. **Stage Progression:** Advance stages via `manage_proposal` (`action: "advance"`). Note that `ARCHIVED` is strictly blocked until `Challenger` or `VictoryAuditor` records an `APPROVE` verdict!
