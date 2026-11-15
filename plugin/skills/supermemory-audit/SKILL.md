---
name: supermemory-audit
description: Run Constitutional CodeGate verification plus adversarial Challenger and independent VictoryAuditor sign-off on proposals and experiments.
---

# SuperMemory Adversarial Audit Skill

Use this skill before claiming milestone completion, merging major changes, or archiving an OpenSpec proposal.

## Steps
1. **Automated Gate Scan:** Call `audit_gates` (or `supermemory audit`) to verify `0` violations across `MAX_LINES`, `FORBIDDEN_FILENAME`, `FROZEN_SHA256`, `FORBIDDEN_REGEX`, and `AST_SYNTAX`.
2. **Adversarial Review:** Delegate to the `experiment-challenger` and/or `victory-auditor` subagent to inspect diffs, tests, and experiment evidence with fresh context.
3. **Record Audit Verdict:** Persist the verdict via `record_audit` (`target_id`, `auditor_role: "Challenger" | "VictoryAuditor"`, `verdict: "APPROVE" | "REQUEST_CHANGES"`, `findings`).
4. **Archive Proposal:** Once `APPROVE` is recorded, advance the proposal to `ARCHIVED` via `manage_proposal`.
