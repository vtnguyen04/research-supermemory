"""Typed Pass/Fail Outcome Ledger, Metric-Direction Inference & L2/L3 Consolidation Digests."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from supermemory.models import ExperimentRecord, MemoryNode, NodeType
from supermemory.storage.sqlite_store import GraphStore

_FAIL_SET = {"REVERT", "FAILED", "REJECTED", "DISCARD", "EARLY_KILLED"}
_PASS_SET = {"VICTORY_CONFIRMED", "KEEP"}


def infer_metric_direction(store: GraphStore, track: str = "") -> str:
    """Infer optimization direction (`lower_is_better` vs `higher_is_better`) strictly within `track` when given."""
    if track:
        saved = store.get_meta(f"track_dir:{track.strip().lower()}")
        if saved in ("lower_is_better", "higher_is_better"):
            return saved
    exps = store.list_experiments(track=track) if track else store.list_experiments()
    neg_wins = sum(
        1 for e in exps if e.verdict.upper() in _PASS_SET and e.delta_vs_baseline is not None and e.delta_vs_baseline < -1e-6
    )
    pos_wins = sum(
        1 for e in exps if e.verdict.upper() in _PASS_SET and e.delta_vs_baseline is not None and e.delta_vs_baseline > 1e-6
    )
    if neg_wins != pos_wins:
        return "lower_is_better" if neg_wins > pos_wins else "higher_is_better"

    pos_fails = sum(
        1 for e in exps if e.verdict.upper() in _FAIL_SET and e.delta_vs_baseline is not None and e.delta_vs_baseline > 1e-6
    )
    neg_fails = sum(
        1 for e in exps if e.verdict.upper() in _FAIL_SET and e.delta_vs_baseline is not None and e.delta_vs_baseline < -1e-6
    )
    if pos_fails > neg_fails:
        return "lower_is_better"
    return "higher_is_better"


def select_best_sota_experiment(store: GraphStore) -> Optional[ExperimentRecord]:
    """Select the primary-track SOTA experiment (`max(track_runs)`) respecting `min` vs `max` direction."""
    exps_all = store.list_experiments()
    scored = [
        e for e in exps_all if e.verdict.upper() not in _FAIL_SET and (e.test_score is not None or e.cv_score is not None)
    ]
    if not scored:
        return None
    confirmed = [e for e in scored if e.verdict.upper() in _PASS_SET]
    pool = confirmed or scored
    by_track: Dict[str, List[ExperimentRecord]] = {}
    for idx, e in enumerate(pool):
        by_track.setdefault(e.track, []).append(e)
    lead_track = max(by_track.keys(), key=lambda tr: (len(by_track[tr]), -next(i for i, x in enumerate(pool) if x.track == tr)))
    same_track = by_track[lead_track]
    direction = infer_metric_direction(store, track=lead_track)
    has_test = [e for e in same_track if e.test_score is not None]
    cand_pool = has_test or same_track

    def _metric_val(rec: ExperimentRecord) -> float:
        return float(rec.test_score if rec.test_score is not None else (rec.cv_score or 0.0))

    return min(cand_pool, key=_metric_val) if direction == "lower_is_better" else max(cand_pool, key=_metric_val)


def summarize_pass_fail_ledger(store: GraphStore, max_wins: int = 3, max_fails: int = 4) -> Dict[str, Any]:
    """Partition all experiments & proposals into Verified Wins vs Falsified Dead-Ends with per-track direction."""
    exps: List[ExperimentRecord] = store.list_experiments()
    passed = [e for e in exps if e.verdict.upper() in _PASS_SET]
    failed = [e for e in exps if e.verdict.upper() in _FAIL_SET]
    rejected_nodes = store.list_nodes(node_types=[NodeType.PROPOSAL.value, NodeType.IDEA.value], status="REJECTED", limit=200)
    dir_cache: Dict[str, str] = {}

    def _win_gain(rec: ExperimentRecord) -> float:
        if rec.delta_vs_baseline is None:
            return 0.0
        tr_dir = dir_cache.setdefault(rec.track, infer_metric_direction(store, track=rec.track))
        return -float(rec.delta_vs_baseline) if tr_dir == "lower_is_better" else float(rec.delta_vs_baseline)

    ranked_wins = sorted(
        passed,
        key=lambda e: (1 if e.verdict.upper() == "VICTORY_CONFIRMED" else 0, round(_win_gain(e), 6), e.created_at),
        reverse=True,
    )
    win_items = [
        f"`{e.exp_id}`({e.single_var_diff[:38]} -> {e.test_summary[:24] or e.cv_summary[:24]})"
        for e in ranked_wins[:max_wins]
    ]

    fail_items: List[str] = [
        f"`{e.exp_id}`[{e.verdict}: {e.single_var_diff[:32]} -> {(e.post_mortem or e.cv_summary)[:42]}]"
        for e in failed[:max_fails]
    ]
    for rj in rejected_nodes[: max(0, max_fails - len(fail_items))]:
        fail_items.append(f"`{rj.id}`[REJECTED: {rj.title[:36]}]")

    return {
        "pass_count": len(passed),
        "fail_count": len(failed) + len(rejected_nodes),
        "metric_direction": infer_metric_direction(store),
        "win_items": win_items,
        "fail_items": fail_items,
    }


def format_capsule_outcome_blocks(store: GraphStore) -> List[Tuple[int, str]]:
    """Render compact L0 Pass vs Fail summary blocks for large (100+ experiment) campaigns."""
    led = summarize_pass_fail_ledger(store)
    blocks: List[Tuple[int, str]] = []
    if led["win_items"]:
        blocks.append((1, f"• [L0 PROVEN WINS ({led['pass_count']} passed)]: " + " | ".join(led["win_items"])))
    if led["fail_items"]:
        blocks.append(
            (1, f"• [L0 FALSIFIED DEAD-ENDS ({led['fail_count']} failed — Never Repeat)]: " + " | ".join(led["fail_items"]))
        )
    return blocks


def build_split_consolidation_digest(
    store: GraphStore,
    track: str,
    batch: List[MemoryNode],
) -> Tuple[str, str]:
    """Synthesize a structured Pass vs Fail Semantic digest from typed `ExperimentRecord` columns."""
    exp_map = {e.exp_id: e for e in store.list_experiments(track=track)}
    wins_short: List[str] = []
    fails_short: List[str] = []
    wins_md: List[str] = []
    fails_md: List[str] = []

    for nd in batch:
        rec = exp_map.get(nd.id)
        status = (rec.verdict if rec else nd.status).upper()
        diff = rec.single_var_diff if rec else nd.title
        if status in _FAIL_SET:
            why = (rec.post_mortem if rec else nd.summary)[:90]
            fails_short.append(f"{nd.id}({diff[:28]})")
            fails_md.append(f"- ❌ **`{nd.id}`** [`{status}`] `{diff[:70]}` — Root cause: {why}")
        else:
            met = (rec.test_summary or rec.cv_summary) if rec else nd.summary[:40]
            wins_short.append(f"{nd.id}({diff[:28]}={met[:20]})")
            wins_md.append(f"- ✅ **`{nd.id}`** [`{status}`] `{diff[:70]}` -> `{met[:60]}`")

    parts = []
    if wins_short:
        parts.append("PASSED: " + ", ".join(wins_short[:4]))
    if fails_short:
        parts.append("FAILED: " + ", ".join(fails_short[:4]))
    summary = f"[{track.upper()} · {len(wins_md)} passed, {len(fails_md)} failed] " + " | ".join(parts)

    body_lines = [
        f"### ✅ Verified Wins (`{len(wins_md)}` runs)",
        *(wins_md or ["- None in this batch."]),
        "",
        f"### ❌ Falsified Dead-Ends (`{len(fails_md)}` runs — Never Repeat)",
        *(fails_md or ["- None in this batch."]),
    ]
    return summary[:235], "\n".join(body_lines)


def collect_observation_consolidation_batches(
    store: GraphStore,
    max_active_obs: int = 24,
    min_cluster_size: int = 4,
) -> List[Tuple[str, str, str, List[str]]]:
    """Group older overflow L2 `OBSERVATION` nodes by parent anchor (`BNK`/`PROP`/track) for REM compaction."""
    active_obs = [
        n
        for n in store.list_nodes(node_types=[NodeType.OBSERVATION.value], limit=5000)
        if n.status == "SCIENTIFIC_INSIGHT"
        and not (n.metadata or {}).get("consolidated")
        and not (n.metadata or {}).get("superseded_by")
    ]
    if len(active_obs) <= max_active_obs:
        return []

    edges = store.list_edges()
    anchor_of: Dict[str, str] = {}
    for ed in edges:
        if ed.source_id.startswith("OBS-") and ed.target_id.startswith(("BNK-", "PROP-", "METH-", "ALGO-")):
            anchor_of.setdefault(ed.source_id, ed.target_id)

    def _obs_seq(nid: str) -> int:
        tail = nid.rsplit("-", 1)[-1]
        return int(tail) if tail.isdigit() else 0

    active_obs.sort(key=lambda n: (n.created_at, _obs_seq(n.id)), reverse=True)
    overflow = active_obs[12:]
    grouped: Dict[str, List[MemoryNode]] = {}
    for nd in overflow:
        key = anchor_of.get(nd.id) or str((nd.metadata or {}).get("track") or "GENERAL").upper()
        grouped.setdefault(key, []).append(nd)

    batches: List[Tuple[str, str, str, List[str]]] = []
    for key, items in grouped.items():
        if len(items) < min_cluster_size:
            continue
        for start in range(0, len(items), 15):
            chunk = items[start : start + 15]
            if len(chunk) < min_cluster_size:
                continue
            bullets = [f"- **`{c.id}`**: {c.title} — {c.summary[:140]}" for c in chunk]
            heads = ", ".join(f"{c.id}({c.title[:26]})" for c in chunk[:4])
            title = f"Distilled L2 Insights: {key} ({len(chunk)} observations)"
            summary = f"[{key} · {len(chunk)} insights] {heads}"[:235]
            batches.append((title, summary, "\n".join(bullets), [c.id for c in chunk]))
    return batches
