---
name: supermemory-experiment
description: Execute and log disciplined single-variable scientific experiments with hypothesis tracking, frozen evaluator checks, monotonic baseline delta calculation, temporal supersession, and plateau pivot enforcement.
---

# SuperMemory v3.5 Scientific Experiment Skill

Use this skill whenever running ML/AI benchmarks, Kaggle/NeurIPS evaluations, latency profiling, or algorithmic ablations.

## Scientific Protocol (`LAW-03`, `LAW-05` & `LAW-06`)
1. **Pre-Flight Check:** Verify frozen evaluators pass `audit_gates` and isolate **ONE** variable (`single_var_diff`) with a falsifiable `hypothesis` tied to an active Kanban task/proposal.
2. **Execute & Measure:** Run the evaluation without touching frozen verifier code or hardcoding test/scenario IDs (`LAW-01`).
3. **Log & Supersede:** Call `log_experiment` with `track`, `title`, `hypothesis`, `single_var_diff`, `baseline_id`, `proposal_id`, `cv_score`/`test_score`, `verdict`, `post_mortem`, and `supersedes=[...]` (if replacing an older observation), then tick completed Kanban subtasks via `checkpoint(task_updates=[...])`.
4. **Anti-Stagnation Circuit-Breaker:** If `log_experiment` returns `stagnation_alert` (`>= 2` consecutive `REVERT`/`FAILED`/`DISCARD` runs or `>= 3` flat tweaks), **STOP tweaking local parameters immediately** and call `scout_sota(action="search", save_top_k=2)` to pivot to a verified external SOTA mechanism.
