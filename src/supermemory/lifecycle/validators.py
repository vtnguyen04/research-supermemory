"""Deterministic Schema & Task-List Validators for Proposals, Insights, Experiments & Kanban."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

_LAZY_TITLES = {"untitled", "untitled proposal", "todo", "test", "fix", "update", "temp", "wip"}
_LAZY_INSIGHTS = {"ok", "done", "clean", "fixed", "fixed bug", "updated", "updated code", "none", "n/a"}


def validate_proposal_schema(
    title: str,
    why: str,
    what_changes: str,
    tasks: Optional[List[str]] = None,
) -> List[str]:
    """Validate OpenSpec Proposal quality and return normalized concrete task steps."""
    t_clean = (title or "").strip()
    w_clean = (why or "").strip()
    c_clean = (what_changes or "").strip()

    if len(t_clean) < 6 or t_clean.lower() in _LAZY_TITLES:
        raise ValueError(
            "Proposal Schema Gate (LAW-06): `title` must be specific (>= 6 chars, not 'Untitled Proposal')."
        )
    if len(w_clean) < 12:
        raise ValueError(
            "Proposal Schema Gate (LAW-06): `why` must state the concrete bottleneck or motivation (>= 12 chars)."
        )
    if len(c_clean) < 12:
        raise ValueError(
            "Proposal Schema Gate (LAW-06): `what_changes` must specify the concrete single-variable mechanism/scope (>= 12 chars)."
        )

    if tasks is not None and len(tasks) > 0:
        cleaned = [str(x).strip() for x in tasks if str(x).strip()]
        if any(len(step) < 6 for step in cleaned):
            raise ValueError(
                "Proposal Task-List Gate (LAW-06): Every step in `tasks` must be an actionable step (>= 6 chars)."
            )
        return cleaned

    return [
        f"Implement single-variable slice: {c_clean[:100]}",
        "Run empirical verification / test suite & log_experiment",
        "Complete Challenger & Victory Audit sign-off",
    ]


def validate_insight_schema(title: str, summary: str) -> None:
    """Reject empty or placeholder 1-2 word insights so L2 Semantic memory stays high-signal."""
    combined = f"{(title or '').strip()} {(summary or '').strip()}".strip()
    low = (summary or title or "").strip().lower().rstrip(".")
    if low in _LAZY_INSIGHTS or len((summary or title or "").strip()) < 15 or len(combined) < 20:
        raise ValueError(
            "Insight Schema Gate (LAW-07): Saved insight is too vague (< 15 chars). "
            "State a concrete root-cause, mechanism, or empirical observation, or pass `status='CLEAN'` with no `insights` if purely cosmetic."
        )


def validate_experiment_schema(
    title: str,
    hypothesis: str,
    single_var_diff: str,
    verdict: str,
    cv_score: Optional[float],
    cv_summary: str,
    test_score: Optional[float],
    test_summary: str,
) -> None:
    """Reject hollow experiment logs missing hypothesis, diff, or positive-verdict metrics."""
    if len((title or "").strip()) < 5 or (title or "").strip().lower() in _LAZY_TITLES:
        raise ValueError("LAW-06 Gate (Experiment Schema): `title` must be descriptive (>= 5 chars).")
    if len((hypothesis or "").strip()) < 10:
        raise ValueError("LAW-06 Gate (Experiment Schema): `hypothesis` must state a falsifiable claim (>= 10 chars).")
    if len((single_var_diff or "").strip()) < 6:
        raise ValueError("LAW-06 Gate (Experiment Schema): `single_var_diff` must specify what changed (>= 6 chars).")
    is_positive = (verdict or "KEEP").strip().upper() not in ("REVERT", "FAILED", "REJECTED", "DISCARD")
    has_metric = (
        cv_score is not None
        or test_score is not None
        or bool((cv_summary or "").strip())
        or bool((test_summary or "").strip())
    )
    if is_positive and not has_metric:
        raise ValueError(
            "Experiment Schema Gate (LAW-06): Positive verdict requires at least one metric (`cv_score`, `test_score`, `cv_summary`, or `test_summary`)."
        )


def assert_all_steps_completed(item_id: str, steps_text: List[str], steps_done: List[bool]) -> None:
    """Block transitioning a Proposal or Kanban Task to DONE/AUDITED while checklist items remain unchecked."""
    if not steps_text:
        return
    unchecked = [
        f"#[{idx}] {txt[:60]}"
        for idx, txt in enumerate(steps_text)
        if not (idx < len(steps_done) and bool(steps_done[idx]))
    ]
    if unchecked:
        shown = ", ".join(unchecked[:3]) + (f" (+{len(unchecked) - 3} more)" if len(unchecked) > 3 else "")
        raise ValueError(
            f"Task-List Discipline Gate (LAW-06): Cannot mark `{item_id}` as DONE/AUDITED while {len(unchecked)}/{len(steps_text)} "
            f"checklist step(s) are still unchecked ({shown}). Complete and check off each step in order first."
        )


def summarize_active_task_focus(proposals: List[Dict[str, Any]], tasks: List[Dict[str, Any]]) -> str:
    """Build a multi-item active Kanban pointer (newest first) showing exact next `[idx]` steps."""
    import re

    def _num(raw_id: str) -> int:
        m = re.search(r"(\d+)$", raw_id or "")
        return int(m.group(1)) if m else 0

    running = sorted([t for t in tasks if str(t.get("status") or "").upper() == "RUNNING"], key=lambda x: -_num(str(x.get("task_id", ""))))
    queued = sorted([t for t in tasks if str(t.get("status") or "").upper() == "QUEUED"], key=lambda x: -_num(str(x.get("task_id", ""))))
    parts: List[str] = []
    for t in (running + queued)[:2]:
        steps = t.get("steps") or []
        done_cnt = sum(1 for s in steps if s.get("done"))
        nxt = next(((i, s.get("text", "")) for i, s in enumerate(steps) if not s.get("done")), None)
        step_hint = f' -> #[{nxt[0]}]: "{str(nxt[1])[:55]}"' if nxt else ""
        parts.append(f"`{t['task_id']}`[{t['status']} {done_cnt}/{len(steps)}] {str(t.get('title', ''))[:36]}{step_hint}")

    stage_rank = {"IMPLEMENTING": 0, "CHALLENGED": 1, "DESIGNED": 2, "PROPOSED": 3}
    open_props = sorted(
        [p for p in proposals if str(p.get("status") or "").upper() in stage_rank],
        key=lambda p: (stage_rank.get(str(p.get("status") or "").upper(), 9), -_num(str(p.get("id", "")))),
    )
    for p in open_props[: (1 if parts else 2)]:
        meta = p.get("metadata") or {}
        p_tasks = [str(x).strip() for x in (meta.get("tasks") or []) if str(x).strip()]
        p_done = [bool(x) for x in (meta.get("tasks_done") or [])]
        done_cnt = sum(1 for i in range(len(p_tasks)) if i < len(p_done) and p_done[i])
        nxt_p = next(((i, txt) for i, txt in enumerate(p_tasks) if not (i < len(p_done) and p_done[i])), None)
        step_hint = f' -> #[{nxt_p[0]}]: "{nxt_p[1][:55]}"' if nxt_p else ""
        parts.append(f"`{p['id']}`[{p['status']} {done_cnt}/{len(p_tasks)}] {str(p.get('title', ''))[:36]}{step_hint}")
    return " | ".join(parts)
