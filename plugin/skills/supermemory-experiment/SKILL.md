---
name: supermemory-experiment
description: Execute and log disciplined single-variable scientific experiments with hypothesis tracking, frozen evaluator checks, monotonic baseline delta calculation, and post-mortem analysis.
---

# SuperMemory Scientific Experiment Skill

Use this skill whenever running ML/AI benchmarks, prompt/pipeline ablations, latency profiling, or algorithmic evaluations.

## Scientific Protocol (`LAW-03` & `LAW-05`)
1. **Pre-Flight Check:**
   - Call `supermemory_recall` on the track/hypothesis to inspect prior runs and dead-ends.
   - Verify frozen evaluators pass `supermemory_audit_gates`.
   - Define **ONE** isolated variable (`single_var_diff`) and a falsifiable `hypothesis`.
2. **Execute & Measure:** Run the evaluation without touching frozen verifier code or hardcoding test examples (`LAW-01`).
3. **Log to Registry:** Call `supermemory_log_experiment` (or `supermemory exp`) with:
   - `track`, `title`, `hypothesis`, `single_var_diff`, `model_stack`
   - `baseline_id`, `proposal_id`
   - `cv_score` / `cv_summary`, `test_score` / `test_summary`, `runtime_summary`
   - `verdict` (`VICTORY_CONFIRMED`, `KEEP`, `ITERATE`, or `REVERT`) and `post_mortem`.
4. **Regression Handling:** If `regression_detected` is `true`, revert the code change immediately (`REVERT`) and record what failed in `post_mortem` (and `supermemory_record_lesson` if caused by a bug/anti-pattern).
