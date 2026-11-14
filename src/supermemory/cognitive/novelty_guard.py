"""Pre-Registration Anti-Repeat & Hypothesis Novelty Guard for Long-Horizon R&D."""

from __future__ import annotations

import re
from typing import Dict, List, Set

from supermemory.models import ExperimentVerdict, NodeType
from supermemory.storage.sqlite_store import GraphStore

_STOPWORDS: Set[str] = {
    "the", "and", "for", "with", "from", "into", "using", "via", "add", "use", "new",
    "test", "model", "method", "approach", "experiment", "proposal", "idea", "system",
    "improve", "based", "data", "train", "training", "run", "code", "module", "của",
    "cho", "với", "trong", "bằng", "thử", "thêm", "cải", "thiện", "thuật", "toán",
}


def _concept_tokens(text: str) -> Set[str]:
    words = re.findall(r"[\w]+", (text or "").lower(), flags=re.UNICODE)
    return {w for w in words if len(w) >= 3 and w not in _STOPWORDS and not w.isdigit()}


def _jaccard_and_containment(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter < 2:
        return 0.0
    jacc = inter / len(a | b)
    contain = inter / min(len(a), len(b))
    return round(max(jacc, contain * 0.85), 3)


def enforce_novelty_against_history(
    store: GraphStore,
    candidate_title: str,
    candidate_body: str,
    novelty_diff: str = "",
    dead_end_threshold: float = 0.50,
    duplicate_threshold: float = 0.68,
) -> List[Dict[str, object]]:
    """Block repeating prior REJECTED/REVERT dead-ends or already-executed hypotheses.

    If `novelty_diff` (>= 15 chars) explicitly states what structural/mathematical
    variable differs from prior attempts, the guard allows the pivot and returns matches.
    """
    cand_tokens = _concept_tokens(f"{candidate_title} {candidate_body}")
    if len(cand_tokens) < 3:
        return []

    has_explicit_pivot = len((novelty_diff or "").strip()) >= 15
    candidates = store.list_nodes(
        node_types=[
            NodeType.IDEA.value,
            NodeType.ALGORITHM.value,
            NodeType.PROPOSAL.value,
            NodeType.EXPERIMENT.value,
        ],
        limit=3000,
    )

    matches: List[Dict[str, object]] = []
    for past in candidates:
        past_tokens = _concept_tokens(f"{past.title} {past.summary}")
        sim = _jaccard_and_containment(cand_tokens, past_tokens)
        if sim < dead_end_threshold:
            continue

        is_dead_end = past.status in (
            "REJECTED",
            ExperimentVerdict.REVERT.value,
            ExperimentVerdict.FAILED.value,
        )
        matches.append(
            {
                "id": past.id,
                "type": past.node_type,
                "status": past.status,
                "title": past.title,
                "similarity": sim,
                "is_dead_end": is_dead_end,
                "summary": past.summary[:180],
            }
        )

        if is_dead_end and sim >= dead_end_threshold and not has_explicit_pivot:
            raise ValueError(
                f"LAW-06 Anti-Repeat Gate: Hypothesis overlaps ({int(sim * 100)}%) with known "
                f"DEAD-END `{past.id}` [{past.status}] ('{past.title}': {past.summary[:140]}). "
                "Do NOT repeat failed directions; pivot to a genuinely distinct mechanism or pass "
                "`novelty_diff` (>=15 chars) proving the exact mathematical difference."
            )

        if not is_dead_end and sim >= duplicate_threshold and not has_explicit_pivot:
            raise ValueError(
                f"LAW-06 Duplicate-Work Gate: Hypothesis duplicates ({int(sim * 100)}%) existing "
                f"`{past.id}` [{past.status}] ('{past.title}'). Check `supermemory recall` and extend "
                "the existing work or specify `novelty_diff`."
            )

    return sorted(matches, key=lambda x: float(str(x["similarity"])), reverse=True)
