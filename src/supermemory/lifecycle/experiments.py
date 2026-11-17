"""Scientific Experiment, Mandatory Post-Mortem Gate, and Insight Crystallizer."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from supermemory.cognitive.outcome_ledger import infer_metric_direction
from supermemory.graph.auto_linker import wire_contextual_edges
from supermemory.graph.supersession import apply_supersedes_links
from supermemory.lifecycle.validators import (
    assert_safe_subpath,
    validate_experiment_schema,
    validate_safe_entity_id,
)
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


def _clip(text: str, limit: int) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    cut = clean[: max(1, limit - 1)]
    sp = cut.rfind(" ")
    return (cut[:sp] if sp > limit // 2 else cut).rstrip(" ,;:-(") + "…"


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
    supersedes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Log an experiment, enforce post-mortem on failures, and crystallize OBSERVATION nodes."""
    clean_track = re.sub(r"[^a-zA-Z0-9_-]+", "_", track.strip() or "main").lower()
    clean_verdict = verdict.strip().upper() or ExperimentVerdict.KEEP.value
    is_explicit_win = clean_verdict in (ExperimentVerdict.VICTORY_CONFIRMED.value, ExperimentVerdict.KEEP.value)
    validate_experiment_schema(title, hypothesis, single_var_diff, clean_verdict, cv_score, cv_summary, test_score, test_summary)
    direction = infer_metric_direction(store, track=clean_track)
    if exp_id.strip():
        exp_id = validate_safe_entity_id(exp_id, "exp_id")
    else:
        exps = store.list_experiments(track=clean_track)
        pref = f"EXP-{clean_track.upper()[:6]}-"
        nums = [int(e.exp_id[len(pref):]) for e in exps if e.exp_id.startswith(pref) and e.exp_id[len(pref):].isdigit()]
        exp_id = f"{pref}{(max(nums) + 1) if nums else (len(exps) + 1):03d}"

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
                worse = (delta > 1e-6) if direction == "lower_is_better" else (delta < -1e-6)
                if worse and not is_explicit_win:
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
    assert_safe_subpath(store.workspace_root / rel_log, store.workspace_root)
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
        improved = delta is not None and (
            (delta < -1e-6 if direction == "lower_is_better" else delta > 1e-6)
            or (is_explicit_win and abs(delta) > 1e-6)
        )
        rel_type = (
            EdgeType.REGRESSED_FROM.value
            if regression_detected
            else (EdgeType.IMPROVES_OVER.value if improved else EdgeType.DERIVED_FROM.value)
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
                title=f"[{obs_kind}] {_clip(ins_text, 84)}",
                status=obs_kind,
                summary=f"(From {exp_id}) {_clip(ins_text, 220)}",
                content=obs_md,
                file_path=obs_rel,
                tags=["observation", clean_track, obs_kind.lower()],
                priority=87,
                metadata={"source_exp_id": exp_id, "track": clean_track, "kind": obs_kind},
            )
        )
        store.add_edge(MemoryEdge(source_id=obs_id, target_id=exp_id, relation=EdgeType.DERIVED_FROM.value))
        wire_contextual_edges(
            store,
            obs_id,
            ins_text,
            context_ids=[exp_id, proposal_id] if proposal_id else [exp_id],
        )
        observation_ids.append(obs_id)

    superseded_ids = apply_supersedes_links(store, observation_ids or [exp_id], supersedes or [])

    # Autonomous REM-sleep consolidation on long-horizon runs (>= 6 unconsolidated episodic runs/track)
    from supermemory.cognitive.tiers import auto_consolidate_episodic
    from supermemory.research.stagnation_guard import sync_stagnation_after_experiment

    auto_cons = auto_consolidate_episodic(store, min_cluster_size=6, repair_fallback=False)
    stagnation_alert = sync_stagnation_after_experiment(store, clean_track)

    out_payload: Dict[str, Any] = {
        "exp_id": exp_id,
        "delta_vs_baseline": delta,
        "regression_detected": regression_detected,
        "observation_ids": observation_ids,
        "superseded_ids": superseded_ids,
        "auto_consolidated_nodes": auto_cons.get("created_semantic_nodes", []),
        "log_path": rel_log,
    }
    if stagnation_alert:
        out_payload["stagnation_alert"] = stagnation_alert
    return out_payload
