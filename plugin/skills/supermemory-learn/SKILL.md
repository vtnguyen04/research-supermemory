---
name: supermemory-learn
description: Self-Learning Mistake-to-Gate workflow. Converts user corrections, scoldings, or bug post-mortems into deduplicated Constitutional LAWs and real-time PreToolUse CodeGates.
---

# SuperMemory Self-Learning Toolkit Skill

Activate this skill IMMEDIATELY whenever:
- The user corrects, critiques, or scolds an agent mistake (note: the `Stop` hook will block turn completion until `record_lesson` or `supermemory learn` is executed!), OR
- You uncover a non-trivial bug, silent fallback, data leak, or regression.

## Mistake-to-Gate Protocol
1. **5-Whys Root Cause:** Identify the structural flaw (`root_cause`), not just the surface symptom.
2. **Deduplicate into Existing LAW:** Check existing `LAW-01..LAW-XX` via `status` so `02_CONSTITUTION_AND_LESSONS.md` stays compact (`< 200` lines). Only mint a new `LAW` if truly orthogonal.
3. **Bind Mechanical Guard:** Whenever possible, express the mistake pattern as:
   - `forbid_regex` + `target_glob` (blocks source code writes at `PreToolUse`), or
   - `forbid_cmd_regex` (blocks destructive/banned shell commands at `PreToolUse`), or
   - `add_gate` with `freeze_path` (SHA-256 file lock).
4. **Commit:** Call `record_lesson` (`title`, `mistake`, `root_cause`, `prevention_rule`, `user_quote`, `law_id`, `forbid_regex`, `forbid_cmd_regex`). This archives full details in `memory/lessons/LESSON-XXX.md`, updates the Knowledge Graph, compiles Markdown, and clears any active `pending_lesson_lock`.
