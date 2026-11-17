"""Bottleneck-First Diagnostic Ledger, Pareto Error Decomposition & Occam's Razor ROI Gate."""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional

from supermemory.cognitive.novelty_guard import extract_mechanism_signature
from supermemory.models import EdgeType, MemoryEdge, MemoryNode, NodeType
from supermemory.storage.sqlite_store import GraphStore

_BLOAT_PHRASES = (
    "end-to-end rewrite",
    "full rewrite",
    "complete overhaul",
    "kitchen sink",
    "jointly train everything",
    "hybrid meta-ensemble",
)


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:44] or "bottleneck"


def _next_typed_id(store: GraphStore, prefix: str, ntype: str) -> str:
    nodes = store.list_nodes(node_types=[ntype], limit=5000)
    nums: List[int] = []
    pat = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    for nd in nodes:
        m = pat.match(nd.id)
        if m:
            nums.append(int(m.group(1)))
    return f"{prefix}-{(max(nums) + 1) if nums else 1:03d}"


def diagnose_bottleneck(
    store: GraphStore,
    title: str,
    evidence_slice: str,
    error_share_pct: float,
    ceiling_gain: float,
    falsifiable_rq: str,
    metric_name: str = "primary_metric",
    baseline_value: Optional[float] = None,
    kill_criterion: str = "",
    smoke_eval_cmd: str = "",
) -> Dict[str, Any]:
    """Register a quantified BOTTLENECK (BNK-XXX) + linked falsifiable RESEARCH_QUESTION (RQ-XXX)."""
    if not title.strip() or not evidence_slice.strip() or not falsifiable_rq.strip():
        raise ValueError("Bottleneck requires non-empty `title`, `evidence_slice`, and `falsifiable_rq`.")
    if error_share_pct <= 0.0 or error_share_pct > 100.0:
        raise ValueError("`error_share_pct` must be in (0, 100]. Quantify the failure slice share first!")
    if ceiling_gain <= 0.0:
        raise ValueError("`ceiling_gain` must be > 0.0 (oracle upper-bound metric improvement if solved).")

    bnk_id = _next_typed_id(store, "BNK", NodeType.BOTTLENECK.value)
    rq_id = _next_typed_id(store, "RQ", NodeType.RESEARCH_QUESTION.value)
    pareto_priority = round((error_share_pct / 100.0) * ceiling_gain * 100.0, 3)

    bnk_dir = store.mem_dir / "08_BOTTLENECKS"
    bnk_dir.mkdir(parents=True, exist_ok=True)
    rel_path = f"memory/08_BOTTLENECKS/{bnk_id}_{_slugify(title)}.md"
    kill_txt = kill_criterion.strip() or f"Abort at 10% budget if `{metric_name}` fails to improve >= {round(ceiling_gain * 0.15, 4)}."

    md = (
        f"# {bnk_id}: {title}\n\n"
        f"- **Status:** `OPEN` | **Pareto Priority Score:** `{pareto_priority}`\n"
        f"- **Error Slice Share:** `{error_share_pct}%` of total failure/regret\n"
        f"- **Oracle Ceiling Gain (`{metric_name}`):** `+{ceiling_gain}`"
        + (f" (Baseline: `{baseline_value}`)\n" if baseline_value is not None else "\n")
        + f"- **Linked Research Question:** `{rq_id}`\n"
        f"- **Early-Stop Kill Criterion (10% Smoke Gate):** {kill_txt}\n"
        + (f"- **Fast Smoke Command:** `{smoke_eval_cmd}`\n" if smoke_eval_cmd else "")
        + f"\n## 1. Empirical Failure Slice & Evidence\n\n{evidence_slice}\n\n"
        f"## 2. Falsifiable Research Question (`{rq_id}`)\n\n{falsifiable_rq}\n"
    )
    (store.workspace_root / rel_path).write_text(md, encoding="utf-8")

    bnk_node = store.upsert_node(
        MemoryNode(
            id=bnk_id,
            node_type=NodeType.BOTTLENECK.value,
            title=title,
            status="OPEN",
            summary=f"[{error_share_pct}% error share | +{ceiling_gain} {metric_name} ceiling] {evidence_slice[:160]}",
            content=md,
            file_path=rel_path,
            tags=["bottleneck", metric_name.lower()],
            priority=min(99, int(75 + min(24.0, error_share_pct / 4.0))),
            metadata={
                "evidence_slice": evidence_slice,
                "error_share_pct": float(error_share_pct),
                "ceiling_gain": float(ceiling_gain),
                "pareto_priority": pareto_priority,
                "metric_name": metric_name,
                "baseline_value": baseline_value,
                "kill_criterion": kill_txt,
                "smoke_eval_cmd": smoke_eval_cmd,
                "rq_id": rq_id,
            },
        )
    )
    rq_node = store.upsert_node(
        MemoryNode(
            id=rq_id,
            node_type=NodeType.RESEARCH_QUESTION.value,
            title=falsifiable_rq[:140],
            status="OPEN",
            summary=f"Targets `{bnk_id}` ({error_share_pct}% err): {falsifiable_rq[:190]}",
            content=f"# {rq_id}\n\n- **Diagnoses:** `{bnk_id}` ({title})\n- **Question:** {falsifiable_rq}\n- **Kill Criterion:** {kill_txt}\n",
            file_path=rel_path,
            tags=["research_question", bnk_id.lower()],
            priority=86,
            metadata={"bottleneck_id": bnk_id, "kill_criterion": kill_txt},
        )
    )
    store.add_edge(MemoryEdge(source_id=rq_id, target_id=bnk_id, relation=EdgeType.DIAGNOSES.value))
    return {
        "bottleneck": bnk_node.to_dict(),
        "research_question": rq_node.to_dict(),
        "pareto_priority": pareto_priority,
        "next_research_action": (
            f"Scout external SOTA literature for `{bnk_id}` BEFORE proposing local heuristics: "
            f"`scout_sota(action='search', query='<mechanism for {title[:40]}>', bottleneck_id='{bnk_id}', save_top_k=2)`"
        ),
    }


def resolve_bottleneck(
    store: GraphStore,
    bottleneck_id: str,
    resolution_exp_id: str = "",
    note: str = "",
) -> Dict[str, Any]:
    """Mark a diagnosed bottleneck (and its RQ) RESOLVED once verified by an experiment."""
    bnk = store.get_node(bottleneck_id)
    if not bnk or bnk.node_type != NodeType.BOTTLENECK.value:
        raise ValueError(f"Bottleneck `{bottleneck_id}` not found.")
    bnk.status = "RESOLVED"
    bnk.metadata["resolved_by"] = resolution_exp_id
    bnk.metadata["resolution_note"] = note
    store.upsert_node(bnk)

    rq_id = str(bnk.metadata.get("rq_id") or "")
    if rq_id:
        rq = store.get_node(rq_id)
        if rq:
            rq.status = "ANSWERED"
            store.upsert_node(rq, log_event=False)
    if resolution_exp_id and store.get_node(resolution_exp_id):
        store.add_edge(MemoryEdge(source_id=resolution_exp_id, target_id=bottleneck_id, relation=EdgeType.IMPROVES_OVER.value))
    return bnk.to_dict()


def rank_bottlenecks(store: GraphStore, include_resolved: bool = False) -> List[Dict[str, Any]]:
    """Return bottlenecks ranked by Pareto impact (error_share_pct * ceiling_gain) with candidate counts."""
    nodes = store.list_nodes(node_types=[NodeType.BOTTLENECK.value], limit=500)
    edges = store.list_edges()
    items: List[Dict[str, Any]] = []
    for nd in nodes:
        if not include_resolved and nd.status in ("RESOLVED", "ARCHIVED"):
            continue
        meta = nd.metadata or {}
        share = float(meta.get("error_share_pct") or 0.0)
        ceil_g = float(meta.get("ceiling_gain") or 0.0)
        prio = round((share / 100.0) * ceil_g * 100.0, 3)
        cands = [e.source_id for e in edges if e.target_id == nd.id and e.relation == EdgeType.CANDIDATE_FOR.value]
        items.append(
            {
                "id": nd.id,
                "title": nd.title,
                "status": nd.status,
                "error_share_pct": share,
                "ceiling_gain": ceil_g,
                "pareto_priority": prio,
                "metric_name": meta.get("metric_name", "score"),
                "rq_id": meta.get("rq_id", ""),
                "kill_criterion": meta.get("kill_criterion", ""),
                "smoke_eval_cmd": meta.get("smoke_eval_cmd", ""),
                "candidate_ids": cands,
                "summary": nd.summary,
                "file_path": nd.file_path,
            }
        )
    items.sort(key=lambda x: float(x["pareto_priority"]), reverse=True)
    cum = 0.0
    for it in items:
        cum = min(100.0, round(cum + float(it["error_share_pct"]), 2))
        it["cumulative_error_share_pct"] = cum
    return items


def evaluate_occam_gate(
    store: GraphStore,
    title: str,
    body: str,
    bottleneck_id: str = "",
    est_loc: int = 60,
    coupled_vars: int = 1,
    compute_cost: float = 1.0,
    confidence: float = 0.75,
    kill_criterion: str = "",
    strict_occam: bool = False,
    min_roi: float = 1.5,
) -> Dict[str, Any]:
    """Score Occam's Razor ROI and reject bloated multi-variable / ungrounded proposals when strict."""
    enforce_strict = strict_occam or (store.get_meta("strict_occam") == "1")
    bnk_node = store.get_node(bottleneck_id.strip()) if bottleneck_id.strip() else None
    if enforce_strict and (not bnk_node or bnk_node.node_type != NodeType.BOTTLENECK.value):
        raise ValueError(
            "LAW-06 Bottleneck-First Gate: Proposal rejected because no valid `bottleneck_id` (`BNK-XXX`) was linked. "
            "Profile the failure slice via `supermemory_diagnose_bottleneck` BEFORE proposing methods!"
        )

    full_txt = f"{title} {body}"
    sig = extract_mechanism_signature(full_txt, bottleneck_id=bottleneck_id)
    fams = list(sig.get("families") or [])
    low_txt = full_txt.lower().replace("-", " ")
    phrase_hits = [p for p in _BLOAT_PHRASES if p in low_txt]
    plus_components = (1 + title.count("+")) if title.count("+") >= 2 else 1
    inferred_vars = max(int(coupled_vars), plus_components, len(fams) if len(fams) >= 3 else 1, 2 if phrase_hits else 1)

    warnings: List[str] = []
    if inferred_vars > 1:
        warnings.append(
            f"Occam Anti-Bloat Warning: Detected {inferred_vars} coupled variables/paradigms ({', '.join(fams) or 'multi-change'}). "
            "Isolate ONE surgical mechanism first!"
        )
    if est_loc > 250:
        warnings.append(f"Complexity Warning: `est_loc={est_loc}` approaches 300-line ceiling; split or simplify.")
    if not bnk_node:
        warnings.append("Ungrounded Hypothesis: Not linked to a quantified `BNK-XXX` bottleneck.")

    ceil_gain = float((bnk_node.metadata or {}).get("ceiling_gain") or 0.15) if bnk_node else 0.12
    err_share = float((bnk_node.metadata or {}).get("error_share_pct") or 25.0) / 100.0 if bnk_node else 0.25
    loc_penalty = max(1.0, math.log2(1.0 + max(5, int(est_loc)) / 25.0))
    cost_pen = max(0.5, float(compute_cost))
    denom = loc_penalty * cost_pen * max(1, inferred_vars)
    occam_roi = round((ceil_gain * max(0.2, err_share * 2.0) * max(0.1, min(1.0, confidence)) * 100.0) / denom, 2)

    eff_kill = kill_criterion.strip() or (str((bnk_node.metadata or {}).get("kill_criterion") or "") if bnk_node else "")
    if enforce_strict:
        if inferred_vars > 1:
            raise ValueError(
                f"LAW-06 Occam Single-Variable Gate: Kitchen-sink proposal rejected (`coupled_vars={inferred_vars}`, "
                f"families={fams}). Decompose into 1 single-variable ablation on `{bottleneck_id}`!"
            )
        if len(eff_kill) < 10:
            raise ValueError(
                "LAW-03 Early-Stop Gate: Proposal must specify a falsifiable `kill_criterion` (>=10 chars) for the 10% smoke run."
            )
        if occam_roi < min_roi:
            raise ValueError(
                f"Occam ROI Gate: Score `{occam_roi}` < minimum `{min_roi}` (ceiling={ceil_gain}, est_loc={est_loc}, cost={cost_pen}). "
                "Choose a simpler hook or target a higher-share Pareto bottleneck."
            )

    return {
        "occam_roi": occam_roi,
        "coupled_vars": inferred_vars,
        "est_loc": int(est_loc),
        "compute_cost": cost_pen,
        "bottleneck_id": bnk_node.id if bnk_node else "",
        "kill_criterion": eff_kill,
        "mechanism_fingerprint": sig,
        "bloat_warnings": warnings,
    }
