---
name: supermemory-orchestrate
description: Multi-Agent Fast-DAG Sprint Orchestration — fan out Wave-1 parallel discovery (bottleneck-profiler || sota-scout || memory-curator), gate Wave-2 hypothesis synthesis, and run glob-locked Wave-3 slices with 10% early-kill cascades.
---

# SuperMemory v3.0 Multi-Agent Fast-DAG Orchestrator Skill

Use this skill to accelerate research & engineering throughput via parallel subagents without file collisions, context bloat, or wasted GPU/API runs.

## 3-Wave Fast-DAG Workflow
1. **Compile Sprint DAG:** Call `orchestrate(action="plan_sprint", goal=..., bottleneck_id=..., smoke_cmd=..., target_globs=["src/**"])`.
2. **Wave 1 — Parallel Read-Only Discovery (Spawn Concurrently):**
   - Spawn `bottleneck-profiler`, `sota-scout`, and `memory-curator` in parallel (`workspace="inherit"`). Each worker claims its Wave-1 task and returns a `< 180`-token JSON receipt.
3. **Wave 2 — Occam Synthesis & Adversarial Red-Team:**
   - Run `hypothesis-architect` to mint a single-variable `PROP-XXX` linked to `BNK-XXX`, followed by `experiment-challenger` to verify zero leakage and zero dead-end mechanism collision.
4. **Wave 3 — Glob-Locked Execution & 10% Early-Kill Cascade:**
   - Spawn `slice-builder` (`workspace="share"` when running parallel non-overlapping globs). If the 10% smoke gate fails `kill_criterion`, mark `status="EARLY_KILLED"` so downstream tasks auto-cancel immediately; otherwise verify with `victory-auditor`.
