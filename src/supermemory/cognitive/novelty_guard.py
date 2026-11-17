"""Domain-Agnostic TF-IDF Subword N-Gram & Graph-Neighborhood Novelty Guard (Zero Keyword Dictionaries)."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Set

from supermemory.models import ExperimentVerdict, NodeType
from supermemory.storage.sqlite_store import GraphStore

_DEAD_END_STATUSES: Set[str] = {
    "REJECTED",
    ExperimentVerdict.REVERT.value,
    ExperimentVerdict.FAILED.value,
    "DISCARD",
    "EARLY_KILLED",
}


_STOPWORDS: Set[str] = {
    "the", "and", "for", "with", "from", "into", "using", "via", "add", "use", "new",
    "try", "fix", "set", "run", "code", "của", "cho", "với", "trong", "bằng",
}


def _word_set(text: str) -> Set[str]:
    raw = "".join(ch.lower() if (ch.isalnum() or ch == "_") else " " for ch in (text or ""))
    return {w for w in raw.split() if len(w) >= 3 and w not in _STOPWORDS and not w.isdigit()}


def _word_overlap(a: Set[str], b: Set[str]) -> float:
    inter = len(a & b)
    if inter < 2:
        return 0.0
    return max(inter / len(a | b), 0.85 * (inter / min(len(a), len(b))))


def _subword_ngram_tf(text: str) -> Dict[str, float]:
    """Build domain-agnostic word + character 3/4-gram feature vector without static algorithm lists."""
    raw = "".join(ch.lower() if (ch.isalnum() or ch == "_") else " " for ch in (text or ""))
    words = [w for w in raw.split() if len(w) >= 3 and not w.isdigit()]
    feats: Dict[str, float] = {}
    for w in words[:160]:
        feats[f"w:{w}"] = feats.get(f"w:{w}", 0.0) + 1.5
        pad = f"#{w}#"
        for i in range(max(0, len(pad) - 2)):
            g3 = f"c3:{pad[i:i + 3]}"
            feats[g3] = feats.get(g3, 0.0) + 0.45
        for i in range(max(0, len(pad) - 3)):
            g4 = f"c4:{pad[i:i + 4]}"
            feats[g4] = feats.get(g4, 0.0) + 0.65
    return feats


def _idf_cosine(cand_tf: Dict[str, float], doc_tf: Dict[str, float], df: Dict[str, int], n_docs: int) -> float:
    if not cand_tf or not doc_tf:
        return 0.0
    dot = 0.0
    c_sq = 0.0
    d_sq = 0.0
    for k, tf in cand_tf.items():
        idf = math.log(1.0 + (n_docs + 1.0) / (df.get(k, 0) + 1.0))
        v = (1.0 + math.log(tf)) * idf
        c_sq += v * v
        if k in doc_tf:
            dv = (1.0 + math.log(doc_tf[k])) * idf
            dot += v * dv
    if dot <= 0.0:
        return 0.0
    for k, tf in doc_tf.items():
        idf = math.log(1.0 + (n_docs + 1.0) / (df.get(k, 0) + 1.0))
        dv = (1.0 + math.log(tf)) * idf
        d_sq += dv * dv
    denom = math.sqrt(c_sq) * math.sqrt(d_sq)
    return (dot / denom) if denom > 0.0 else 0.0


def extract_mechanism_signature(text: str, bottleneck_id: str = "") -> Dict[str, Any]:
    """Extract structural file/module tokens and linked bottleneck ID (`0` hardcoded domain families)."""
    tokens = (text or "").replace("`", " ").replace("(", " ").replace(")", " ").replace(",", " ").split()
    exts = (".py", ".ts", ".js", ".rs", ".cpp", ".cu", ".yaml", ".toml")
    modules = sorted({t.strip(".:;/") for t in tokens if t.strip(".:;/").endswith(exts)})[:8]
    bnks = [bottleneck_id.strip().lower()] if bottleneck_id and bottleneck_id.strip() else []
    salient = sorted({w.lower() for w in tokens if len(w) >= 5 and w[0].isalpha()})[:10]
    return {
        "families": [],
        "salient_terms": salient,
        "bottlenecks": bnks,
        "modules": modules,
    }


def _structural_context_boost(sig_a: Dict[str, Any], sig_b: Dict[str, Any], text_cos: float) -> float:
    """Boost similarity when two candidates modify the exact same module on the same bottleneck."""
    if text_cos < 0.20:
        return text_cos
    bnk_same = bool(set(sig_a.get("bottlenecks") or []) & set(sig_b.get("bottlenecks") or []))
    mod_same = bool(set(sig_a.get("modules") or []) & set(sig_b.get("modules") or []))
    if bnk_same and mod_same:
        return min(0.96, text_cos + 0.24)
    if mod_same or bnk_same:
        return min(0.94, text_cos + 0.08)
    return text_cos


def enforce_novelty_against_history(
    store: GraphStore,
    candidate_title: str,
    candidate_body: str,
    novelty_diff: str = "",
    bottleneck_id: str = "",
    dead_end_threshold: float = 0.50,
    duplicate_threshold: float = 0.68,
) -> List[Dict[str, object]]:
    """Block repeating prior REJECTED/REVERT/FAILED/DISCARD dead-ends via IDF subword cosine + graph links."""
    cand_txt = f"{candidate_title} {candidate_body}"
    cand_tf = _subword_ngram_tf(cand_txt)
    if len(cand_tf) < 4:
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
        limit=5000,
    )
    if not candidates:
        return []

    # Resolve ground-truth experiment verdicts from the typed SQLite `experiments` table (immune to consolidation!)
    exp_verdicts = {e.exp_id: e.verdict.upper() for e in store.list_experiments()}

    cand_words = _word_set(cand_txt)
    doc_tfs: Dict[str, Dict[str, float]] = {}
    doc_words: Dict[str, Set[str]] = {}
    df: Dict[str, int] = {}
    for past in candidates:
        meta = past.metadata or {}
        diff_txt = f"{meta.get('single_var_diff', '')} {meta.get('hypothesis', '')}"
        full_past = f"{past.title} {past.summary} {diff_txt}"
        tf_map = _subword_ngram_tf(full_past)
        doc_tfs[past.id] = tf_map
        doc_words[past.id] = _word_set(f"{past.title} {diff_txt}" if diff_txt.strip() else full_past)
        for k in tf_map:
            if k in cand_tf:
                df[k] = df.get(k, 0) + 1

    n_docs = len(candidates)
    matches: List[Dict[str, object]] = []
    for past in candidates:
        true_status = exp_verdicts.get(past.id, past.status.upper())
        raw_cos = max(
            _idf_cosine(cand_tf, doc_tfs.get(past.id) or {}, df, n_docs),
            _word_overlap(cand_words, doc_words.get(past.id) or set()),
        )
        past_bnk = str((past.metadata or {}).get("bottleneck_id") or "")
        past_sig = (past.metadata or {}).get("mechanism_fingerprint") or extract_mechanism_signature(
            f"{past.title} {past.summary}", bottleneck_id=past_bnk
        )
        sim = round(_structural_context_boost(cand_sig, past_sig, raw_cos), 3)
        if sim < dead_end_threshold:
            continue

        is_dead_end = true_status in _DEAD_END_STATUSES
        matches.append(
            {
                "id": past.id,
                "type": past.node_type,
                "status": true_status,
                "title": past.title,
                "similarity": sim,
                "mechanism_overlap": sim,
                "is_dead_end": is_dead_end,
                "summary": past.summary[:180],
            }
        )

        if is_dead_end and sim >= dead_end_threshold and not has_explicit_pivot:
            raise ValueError(
                f"LAW-06 Anti-Repeat Gate: Hypothesis overlaps ({int(sim * 100)}% subword/graph similarity) "
                f"with known DEAD-END `{past.id}` [{true_status}] ('{past.title}': {past.summary[:140]}). "
                "Do NOT repeat failed mechanisms; pivot or pass `novelty_diff` (>=15 chars)."
            )

        if not is_dead_end and sim >= duplicate_threshold and not has_explicit_pivot:
            raise ValueError(
                f"LAW-06 Duplicate-Work Gate: Hypothesis duplicates ({int(sim * 100)}%) existing "
                f"`{past.id}` [{true_status}] ('{past.title}'). Check `supermemory recall` or specify `novelty_diff`."
            )

    matches.sort(key=lambda x: float(x["similarity"]), reverse=True)  # type: ignore[arg-type]
    return matches
