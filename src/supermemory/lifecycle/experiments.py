"""Scientific Experiment, Mandatory Post-Mortem Gate, and Insight Crystallizer."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

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


def _next_obs_id(store: GraphStore) -> str:
    nodes = store.list_nodes(node_types=[NodeType.OBSERVATION.value], limit=5000)
    nums: List[int] = []
    for n in nodes:
        m = re.match(r"^OBS-(\d+)$", n.id)
        if m:
            nums.append(int(m.group(1)))
    return f"OBS-{(max(nums) + 1) if nums else 1:03d}"


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
    insights: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Log an experiment, enforce post-mortem on failures, and crystallize OBSERVATION nodes."""
    clean_track = re.sub(r"[^a-zA-Z0-9_-]+", "_", track.strip() or "main").lower()
    clean_verdict = verdict.strip().upper() or ExperimentVerdict.KEEP.value
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

    clean_insights = [s.strip() for s in (insights or []) if s and s.strip()]
    is_failure = clean_verdict in (
        ExperimentVerdict.REVERT.value,
        ExperimentVerdict.FAILED.value,
        "REJECTED",
    ) or regression_detected

    if is_failure and len((post_mortem or "").strip()) < 10 and not clean_insights:
        raise ValueError(
            f"LAW-06 Gate: Failed/reverted experiment `{exp_id}` MUST include a root-cause "
            "`post_mortem` (>= 10 chars) or `insights` so this dead-end is never repeated."
        )

    if not clean_insights and len((post_mortem or "").strip()) >= 15:
        clean_insights = [post_mortem.strip()]

    exp_dir = store.mem_dir / "experiments" / clean_track
    exp_dir.mkdir(parents=True, exist_ok=True)
    rel_log = f"memory/experiments/{clean_track}/{exp_id}.md"
    insights_md = "\n".join(f"- {ins}" for ins in clean_insights) if clean_insights else "- Recorded atomically."
    log_md = (
        f"# Scientific Experiment Log: `{exp_id}` — {title}\n\n"
        f"- **Timestamp:** `{utc_now_iso()}`\n"
        f"- **Track / Module:** `{clean_track}` | **Verdict:** `{clean_verdict}` | **Leakage Audit:** `{leakage_audit}`\n"
        f"- **Baseline Ref:** `{baseline_id or 'None'}` | **Delta:** `{delta if delta is not None else 'N/A'}`\n"
        f"- **Model / Engine Stack:** `{model_stack or 'N/A'}`\n"
        f"- **Hypothesis:** {hypothesis}\n"
        f"- **Single-Variable Diff:** {single_var_diff}\n"
        f"- **Local / CV Metrics:** `{cv_summary or cv_score}`\n"
        f"- **Test / LB Metrics:** `{test_summary or test_score}`\n"
        f"- **Runtime / Cost / VRAM:** `{runtime_summary or 'N/A'}`\n\n"
        f"## Post-Mortem & Key Takeaways\n\n{post_mortem or 'N/A'}\n\n"
        f"## Crystallized Scientific Insights\n\n{insights_md}\n"
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
        verdict=clean_verdict,
        leakage_audit=leakage_audit.upper(),
        post_mortem=post_mortem or ("; ".join(clean_insights)),
        log_path=rel_log,
    )
    store.upsert_experiment(rec)

    pm_short = f" | Insight: {rec.post_mortem[:90]}" if rec.post_mortem else ""
    summary_line = f"[{clean_verdict}] {hypothesis[:90]} | CV={rec.cv_summary} | Test={rec.test_summary}{pm_short}"
    store.upsert_node(
        MemoryNode(
            id=exp_id,
            node_type=NodeType.EXPERIMENT.value,
            title=title,
            status=clean_verdict,
            summary=summary_line[:240],
            content=log_md,
            file_path=rel_log,
            tags=["experiment", clean_track, clean_verdict.lower()],
            priority=88 if is_failure else 86,
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

    observation_ids: List[str] = []
    obs_dir = store.mem_dir / "06_KNOWLEDGE_NODES"
    obs_dir.mkdir(parents=True, exist_ok=True)
    for ins_text in clean_insights:
        obs_id = _next_obs_id(store)
        obs_rel = f"memory/06_KNOWLEDGE_NODES/{obs_id}.md"
        obs_kind = "FAILURE_INSIGHT" if is_failure else "SCIENTIFIC_INSIGHT"
        obs_md = (
            f"# {obs_id}: Insight from `{exp_id}` ({clean_track})\n\n"
            f"- **Source Experiment:** `{exp_id}` (`{clean_verdict}`)\n"
            f"- **Kind:** `{obs_kind}`\n"
            f"- **Insight / Observation:** {ins_text}\n"
        )
        (store.workspace_root / obs_rel).write_text(obs_md, encoding="utf-8")
        store.upsert_node(
            MemoryNode(
                id=obs_id,
                node_type=NodeType.OBSERVATION.value,
                title=f"[{obs_kind}] {ins_text[:72]}",
                status=obs_kind,
                summary=f"(From {exp_id}) {ins_text[:200]}",
                content=obs_md,
                file_path=obs_rel,
                tags=["observation", clean_track, obs_kind.lower()],
                priority=87,
                metadata={"source_exp_id": exp_id, "track": clean_track, "kind": obs_kind},
            )
        )
        store.add_edge(MemoryEdge(source_id=obs_id, target_id=exp_id, relation=EdgeType.DERIVED_FROM.value))
        observation_ids.append(obs_id)

    # Autonomous REM-sleep consolidation on long-horizon runs (>= 6 unconsolidated episodic runs/track)
    from supermemory.cognitive.tiers import auto_consolidate_episodic

    auto_cons = auto_consolidate_episodic(store, min_cluster_size=6)

    return {
        "exp_id": exp_id,
        "delta_vs_baseline": delta,
        "regression_detected": regression_detected,
        "observation_ids": observation_ids,
        "auto_consolidated_nodes": auto_cons.get("created_semantic_nodes", []),
        "log_path": rel_log,
    }
