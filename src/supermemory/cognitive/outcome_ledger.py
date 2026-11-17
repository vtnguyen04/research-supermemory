"""Typed Pass/Fail Outcome Ledger & Split REM-Sleep Consolidation Digest (`0` Regexes)."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from supermemory.models import ExperimentRecord, MemoryNode, NodeType
from supermemory.storage.sqlite_store import GraphStore

_FAIL_SET = {"REVERT", "FAILED", "REJECTED", "DISCARD", "EARLY_KILLED"}
_PASS_SET = {"VICTORY_CONFIRMED", "KEEP"}


def summarize_pass_fail_ledger(store: GraphStore, max_wins: int = 3, max_fails: int = 4) -> Dict[str, Any]:
    """Partition all experiments & proposals into Verified Wins vs Falsified Dead-Ends via typed SQL columns."""
    exps: List[ExperimentRecord] = store.list_experiments()
    passed = [e for e in exps if e.verdict.upper() in _PASS_SET]
    failed = [e for e in exps if e.verdict.upper() in _FAIL_SET]
    rejected_nodes = [
        n
        for n in store.list_nodes(node_types=[NodeType.PROPOSAL.value, NodeType.IDEA.value], limit=300)
        if n.status.upper() == "REJECTED"
    ]

    # Rank wins: VICTORY_CONFIRMED first, then newest / largest delta
    ranked_wins = sorted(
        passed,
        key=lambda e: (1 if e.verdict.upper() == "VICTORY_CONFIRMED" else 0, e.created_at),
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
