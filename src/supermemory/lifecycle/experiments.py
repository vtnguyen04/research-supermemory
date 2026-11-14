"""Scientific Experiment & Monotonic Delta Logger for the R&D Lifecycle."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from supermemory.models import (
    EdgeType,
    ExperimentRecord,
    ExperimentVerdict,
    MemoryEdge,
    MemoryNode,
    NodeType,
    utc_now_iso,
)
from supermemory.storage.sqlite_store import GraphStore


def record_scientific_experiment(
    store: GraphStore,
    track: str,
    title: str,
    hypothesis: str,
    single_var_diff: str,
    model_stack: str = "",
    baseline_id: str = "",
    proposal_id: str = "",
    exp_id: str = "",
    cv_score: Optional[float] = None,
    cv_summary: str = "",
    test_score: Optional[float] = None,
    test_summary: str = "",
    runtime_summary: str = "",
    verdict: str = ExperimentVerdict.KEEP.value,
    leakage_audit: str = "CLEAN",
    post_mortem: str = "",
) -> Dict[str, Any]:
    """Log an experiment, compute monotonic delta against baseline, and write Markdown log."""
    clean_track = re.sub(r"[^a-zA-Z0-9_-]+", "_", track.strip() or "main").lower()
    if not exp_id.strip():
        exps = store.list_experiments(track=clean_track)
        exp_id = f"EXP-{clean_track.upper()[:6]}-{len(exps) + 1:03d}"

    delta: Optional[float] = None
    regression_detected = False
    if baseline_id:
        prev_list = [e for e in store.list_experiments() if e.exp_id == baseline_id]
        if prev_list:
            prev = prev_list[0]
            cur_metric = test_score if test_score is not None else cv_score
            prev_metric = prev.test_score if prev.test_score is not None else prev.cv_score
            if cur_metric is not None and prev_metric is not None:
                delta = round(cur_metric - prev_metric, 6)
                if delta < 0:
                    regression_detected = True

    exp_dir = store.mem_dir / "experiments" / clean_track
    exp_dir.mkdir(parents=True, exist_ok=True)
    rel_log = f"memory/experiments/{clean_track}/{exp_id}.md"
    log_md = (
        f"# Scientific Experiment Log: `{exp_id}` — {title}\n\n"
        f"- **Timestamp:** `{utc_now_iso()}`\n"
        f"- **Track / Module:** `{clean_track}` | **Verdict:** `{verdict.upper()}` | **Leakage Audit:** `{leakage_audit}`\n"
        f"- **Baseline Ref:** `{baseline_id or 'None'}` | **Delta:** `{delta if delta is not None else 'N/A'}`\n"
        f"- **Model / Engine Stack:** `{model_stack or 'N/A'}`\n"
        f"- **Hypothesis:** {hypothesis}\n"
        f"- **Single-Variable Diff:** {single_var_diff}\n"
        f"- **Local / CV Metrics:** `{cv_summary or cv_score}`\n"
        f"- **Test / LB Metrics:** `{test_summary or test_score}`\n"
        f"- **Runtime / Cost / VRAM:** `{runtime_summary or 'N/A'}`\n\n"
        f"## Post-Mortem & Key Takeaways\n\n{post_mortem or 'Recorded atomically via SuperMemory.'}\n"
    )
    (store.workspace_root / rel_log).write_text(log_md, encoding="utf-8")

    rec = ExperimentRecord(
        exp_id=exp_id,
        track=clean_track,
        title=title,
        hypothesis=hypothesis,
        single_var_diff=single_var_diff,
        model_stack=model_stack,
        baseline_id=baseline_id,
        proposal_id=proposal_id,
        cv_score=cv_score,
        cv_summary=cv_summary or (str(cv_score) if cv_score is not None else ""),
        test_score=test_score,
        test_summary=test_summary or (str(test_score) if test_score is not None else ""),
        delta_vs_baseline=delta,
        runtime_summary=runtime_summary,
        verdict=verdict.upper(),
        leakage_audit=leakage_audit.upper(),
        post_mortem=post_mortem,
        log_path=rel_log,
    )
    store.upsert_experiment(rec)

    summary_line = f"[{verdict.upper()}] {hypothesis[:110]} | CV={rec.cv_summary} | Test={rec.test_summary}"
    store.upsert_node(
        MemoryNode(
            id=exp_id,
            node_type=NodeType.EXPERIMENT.value,
            title=title,
            status=verdict.upper(),
            summary=summary_line[:240],
            content=log_md,
            file_path=rel_log,
            tags=["experiment", clean_track, verdict.lower()],
            priority=86,
            metadata=rec.to_dict(),
        )
    )
    if baseline_id:
        rel_type = (
            EdgeType.REGRESSED_FROM.value
            if regression_detected
            else (EdgeType.IMPROVES_OVER.value if (delta and delta > 0) else EdgeType.DERIVED_FROM.value)
        )
        store.add_edge(MemoryEdge(source_id=exp_id, target_id=baseline_id, relation=rel_type))
    if proposal_id:
        store.add_edge(MemoryEdge(source_id=exp_id, target_id=proposal_id, relation=EdgeType.TESTS_HYPOTHESIS.value))

    return {
        "exp_id": exp_id,
        "delta_vs_baseline": delta,
        "regression_detected": regression_detected,
        "log_path": rel_log,
    }
