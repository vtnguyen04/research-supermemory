"""Pre-Registration Anti-Repeat & Structural Mechanism Novelty Guard for Long-Horizon R&D."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Set

from supermemory.models import ExperimentVerdict, NodeType
from supermemory.storage.sqlite_store import GraphStore

_STOPWORDS: Set[str] = {
    "the", "and", "for", "with", "from", "into", "using", "via", "add", "use", "new",
    "test", "model", "method", "approach", "experiment", "proposal", "idea", "system",
    "improve", "based", "data", "train", "training", "run", "code", "module", "của",
    "cho", "với", "trong", "bằng", "thử", "thêm", "cải", "thiện", "thuật", "toán",
}

_MECHANISM_FAMILIES: Dict[str, Set[str]] = {
    "kalman_bayesian": {"kalman", "ekf", "ukf", "covariance", "posterior", "bayesian", "gaussian_filter"},
    "optimal_transport": {"sinkhorn", "hungarian", "wasserstein", "bipartite", "entropic", "ot_assign", "transport"},
    "contrastive_metric": {"infonce", "contrastive", "triplet", "supcon", "margin_loss", "metric_learning"},
    "attention_transformer": {"transformer", "self_attention", "cross_attention", "multihead", "mha", "flash_attn"},
    "mpc_optimal_control": {"mpc", "receding_horizon", "pontryagin", "lqr", "lyapunov", "cvar"},
    "graph_propagation": {"gnn", "gat", "gcn", "message_passing", "laplacian", "pagerank"},
    "rl_policy_opt": {"ppo", "grpo", "reinforce", "actor_critic", "pomdp", "q_learning", "td_error"},
    "regularization_smoothing": {"ema", "dropout", "spectral_norm", "label_smoothing", "huber", "ema_decay"},
    "hybrid_retrieval": {"bm25", "tfidf", "rerank", "rrf", "dense_sparse"},
}


def _concept_tokens(text: str) -> Set[str]:
    words = re.findall(r"[\w]+", (text or "").lower(), flags=re.UNICODE)
    return {w for w in words if len(w) >= 3 and w not in _STOPWORDS and not w.isdigit()}


def extract_mechanism_signature(text: str, bottleneck_id: str = "") -> Dict[str, Any]:
    """Extract canonical math/algo operator families, target modules, and bottleneck ID."""
    low = (text or "").lower()
    words = set(re.findall(r"[a-z0-9_]+", low))
    families: List[str] = []
    for fam, triggers in _MECHANISM_FAMILIES.items():
        matched = False
        for trig in triggers:
            if trig in words or (len(trig) >= 5 and trig in low):
                matched = True
                break
        if matched:
            families.append(fam)

    bnk_ids = set(re.findall(r"\bbnk-\d+\b", low))
    if bottleneck_id and bottleneck_id.strip():
        bnk_ids.add(bottleneck_id.strip().lower())
    modules = sorted(set(re.findall(r"\b[a-z0-9_]+\.(?:py|ts|js|rs|cpp)\b", low)))
    return {
        "families": sorted(families),
        "bottlenecks": sorted(bnk_ids),
        "modules": modules[:8],
    }


def _mechanism_overlap(sig_a: Dict[str, Any], sig_b: Dict[str, Any]) -> float:
    fams_a = set(sig_a.get("families") or [])
    fams_b = set(sig_b.get("families") or [])
    if not fams_a or not fams_b:
        return 0.0
    fam_inter = len(fams_a & fams_b)
    if fam_inter == 0:
        return 0.0
    fam_score = fam_inter / len(fams_a | fams_b)
    bnk_a = set(sig_a.get("bottlenecks") or [])
    bnk_b = set(sig_b.get("bottlenecks") or [])
    mod_a = set(sig_a.get("modules") or [])
    mod_b = set(sig_b.get("modules") or [])
    same_target = bool((bnk_a and (bnk_a & bnk_b)) or (mod_a and (mod_a & mod_b)))
    if same_target:
        return round(min(0.95, 0.55 + 0.40 * fam_score), 3)
    return round(0.42 * fam_score, 3)


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
    bottleneck_id: str = "",
    dead_end_threshold: float = 0.50,
    duplicate_threshold: float = 0.68,
) -> List[Dict[str, object]]:
    """Block repeating prior REJECTED/REVERT dead-ends by lexical OR structural mechanism signature."""
    cand_txt = f"{candidate_title} {candidate_body}"
    cand_tokens = _concept_tokens(cand_txt)
    if len(cand_tokens) < 3:
        return []

    cand_sig = extract_mechanism_signature(cand_txt, bottleneck_id=bottleneck_id)
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
        past_txt = f"{past.title} {past.summary}"
        past_tokens = _concept_tokens(past_txt)
        lex_sim = _jaccard_and_containment(cand_tokens, past_tokens)
        past_bnk = str((past.metadata or {}).get("bottleneck_id") or "")
        past_sig = (past.metadata or {}).get("mechanism_fingerprint") or extract_mechanism_signature(
            f"{past_txt} {past.content[:400]}", bottleneck_id=past_bnk
        )
        mech_sim = _mechanism_overlap(cand_sig, past_sig)
        sim = max(lex_sim, mech_sim)
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
                "mechanism_overlap": mech_sim,
                "is_dead_end": is_dead_end,
                "summary": past.summary[:180],
            }
        )

        if is_dead_end and sim >= dead_end_threshold and not has_explicit_pivot:
            raise ValueError(
                f"LAW-06 Anti-Repeat Gate: Hypothesis overlaps ({int(sim * 100)}%, mechanism={int(mech_sim * 100)}%) "
                f"with known DEAD-END `{past.id}` [{past.status}] ('{past.title}': {past.summary[:140]}). "
                "Do NOT repeat rebranded failed mechanisms; pivot or pass `novelty_diff` (>=15 chars)."
            )

        if not is_dead_end and sim >= duplicate_threshold and not has_explicit_pivot:
            raise ValueError(
                f"LAW-06 Duplicate-Work Gate: Hypothesis duplicates ({int(sim * 100)}%) existing "
                f"`{past.id}` [{past.status}] ('{past.title}'). Check `supermemory recall` or specify `novelty_diff`."
            )

    return sorted(matches, key=lambda x: float(str(x["similarity"])), reverse=True)
