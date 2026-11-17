"""Anti-Stagnation Research Circuit-Breaker & Structural URL Provenance Gate (Zero Phrase Regex)."""

from __future__ import annotations

from typing import Any, Dict, List, Set
from urllib.parse import urlparse

from supermemory.models import EdgeType, NodeType
from supermemory.storage.sqlite_store import GraphStore

_SCHOLARLY_AND_CODE_HOSTS: tuple[str, ...] = (
    "arxiv.org", "doi.org", "semanticscholar.org", "openalex.org", "openreview.net",
    "aclanthology.org", "proceedings.mlr.press", "neurips.cc", "papers.nips.cc",
    "icml.cc", "iclr.cc", "thecvf.com", "ieee.org", "acm.org", "dl.acm.org",
    "springer.com", "nature.com", "science.org", "sciencedirect.com", "jmlr.org",
    "aaai.org", "ijcai.org", "kaggle.com", "github.com", "huggingface.co",
)

_FAIL_VERDICTS: Set[str] = {"REVERT", "FAILED", "REJECTED", "DISCARD", "EARLY_KILLED"}


def is_verified_external_url(source_url: str) -> bool:
    """Return True only when `source_url` parses as an http(s) URI on a scholarly or open-source host."""
    raw = (source_url or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    host = parsed.hostname.lower().removeprefix("www.")
    return any(host == dom or host.endswith("." + dom) for dom in _SCHOLARLY_AND_CODE_HOSTS)


def validate_method_card_provenance(
    source_url: str,
    fetched_from_api: bool = False,
) -> str:
    """Classify provenance structurally from URI scheme/host or API fetch (`0` text/title regexes)."""
    raw_url = (source_url or "").strip()
    if raw_url:
        parsed = urlparse(raw_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or "." not in parsed.hostname:
            raise ValueError(
                "LAW-01 Structural Citation Gate: `source_url` in `07_METHOD_VAULT` (`METH-XXX`) must be a valid "
                "`https://` external URL (not a local file path). Use `propose_idea(is_algorithm=True)` for internal designs."
            )
    if fetched_from_api or is_verified_external_url(raw_url):
        return "VERIFIED_EXTERNAL"
    return "UNVERIFIED_MANUAL"


def _verified_cards_for_bnk(store: GraphStore, bottleneck_id: str = "") -> List[str]:
    cards = store.list_nodes(node_types=[NodeType.METHOD_CARD.value], limit=500)
    out: List[str] = []
    for c in cards:
        meta = c.metadata or {}
        prov = str(meta.get("provenance") or "")
        if prov == "VERIFIED_EXTERNAL" or is_verified_external_url(str(meta.get("source_url") or "")):
            if not bottleneck_id or str(meta.get("bottleneck_id") or "") == bottleneck_id:
                out.append(c.id)
    return out


def record_verified_scout_cursor(store: GraphStore, provenance: str, bottleneck_id: str = "") -> bool:
    """Advance monotonic experiment/proposal cursors and unlock `stagnation_alert` on verified external scout."""
    if provenance != "VERIFIED_EXTERNAL":
        return False
    exps = store.list_experiments()
    latest_exp = exps[0].exp_id if exps else "NONE"
    store.set_meta("last_scout_exp_cursor", latest_exp)
    if bottleneck_id.strip():
        store.set_meta(f"last_scout_exp_{bottleneck_id.strip()}", latest_exp)
        props = store.list_nodes(node_types=[NodeType.PROPOSAL.value], limit=300)
        rej_ids = [p.id for p in props if p.status.upper() == "REJECTED"]
        store.set_meta(f"last_scout_rej_{bottleneck_id.strip()}", ",".join(rej_ids))
    if store.get_meta("stagnation_alert"):
        store.set_meta("stagnation_alert", "")
        store.log_event("STAGNATION_CLEARED", bottleneck_id.strip() or "VAULT", "Unlocked via verified external SOTA paper scout")
        return True
    return False


def evaluate_stagnation_state(
    store: GraphStore,
    track: str = "",
    bottleneck_id: str = "",
) -> Dict[str, Any]:
    """Detect local hill-climbing plateaus from typed SQLite `verdict` & `delta_vs_baseline` columns (`0` regexes)."""
    all_exps = store.list_experiments()
    cursor_exp = store.get_meta("last_scout_exp_cursor")
    exps = store.list_experiments(track=track) if track else all_exps
    global_cutoff_idx = next((i for i, e in enumerate(all_exps) if e.exp_id == cursor_exp), len(all_exps))
    allowed_ids = {e.exp_id for e in all_exps[:global_cutoff_idx]}
    since_scout = [e for e in exps if e.exp_id in allowed_ids] if cursor_exp else exps

    fail_streak = 0
    for e in since_scout:
        if e.verdict.upper() in _FAIL_VERDICTS:
            fail_streak += 1
        else:
            break

    flat_streak = 0
    for e in since_scout:
        is_fail = e.verdict.upper() in _FAIL_VERDICTS
        is_flat = e.delta_vs_baseline is not None and e.delta_vs_baseline <= 1e-5
        if is_fail or is_flat:
            flat_streak += 1
        else:
            break

    open_bnks = [
        b for b in store.list_nodes(node_types=[NodeType.BOTTLENECK.value], limit=100)
        if b.status not in ("RESOLVED", "ARCHIVED")
    ]
    unresearched_bnks = [b.id for b in open_bnks if not _verified_cards_for_bnk(store, b.id)]

    bnk_fail_count = 0
    bnk_locked = False
    clean_bnk = bottleneck_id.strip()
    if clean_bnk:
        bnk_cursor = store.get_meta(f"last_scout_exp_{clean_bnk}") or cursor_exp
        bnk_cut = next((i for i, e in enumerate(all_exps) if e.exp_id == bnk_cursor), len(all_exps))
        bnk_allowed = {e.exp_id for e in all_exps[:bnk_cut]} if bnk_cursor else {e.exp_id for e in all_exps}
        edges = store.list_edges()
        all_props = store.list_nodes(node_types=[NodeType.PROPOSAL.value], limit=300)
        prop_for_bnk = {p.id for p in all_props if str((p.metadata or {}).get("bottleneck_id") or "") == clean_bnk}
        exp_to_prop = {ed.source_id: ed.target_id for ed in edges if ed.relation == EdgeType.TESTS_HYPOTHESIS.value}
        for e in all_exps:
            linked_prop = e.proposal_id or exp_to_prop.get(e.exp_id, "")
            if e.exp_id in bnk_allowed and linked_prop in prop_for_bnk and e.verdict.upper() in _FAIL_VERDICTS:
                bnk_fail_count += 1
        cleared_rej = set((store.get_meta(f"last_scout_rej_{clean_bnk}") or "").split(",")) - {""}
        bnk_fail_count += sum(1 for p in all_props if p.id in prop_for_bnk and p.status.upper() == "REJECTED" and p.id not in cleared_rej)
        bnk_locked = bnk_fail_count >= 2

    locked = fail_streak >= 2 or flat_streak >= 3 or bnk_locked
    reason = ""
    if bnk_locked:
        reason = f"{bnk_fail_count} failed attempts on `{clean_bnk}` without fresh external SOTA literature"
    elif fail_streak >= 2:
        reason = f"{fail_streak} consecutive failed/reverted runs without fresh external SOTA literature"
    elif flat_streak >= 3:
        reason = f"{flat_streak} consecutive flat/non-improving runs (delta <= 1e-5) without fresh external SOTA literature"

    target_hint = clean_bnk or (unresearched_bnks[0] if unresearched_bnks else "BNK-001")
    directive = (
        f"🚨 ANTI-STAGNATION CIRCUIT-BREAKER: {reason}. Stop local heuristic tweaking! "
        f"Call `scout_sota(action='search', query='<mechanism for {target_hint}>', bottleneck_id='{target_hint}', save_top_k=2)` "
        f"(or `search_web` + `scout_sota(action='register_card', source_url='https://arxiv.org/...')`) to harvest a verified external SOTA paper first."
        if locked
        else ""
    )
    return {
        "locked": locked,
        "reason": reason,
        "fail_streak": fail_streak,
        "flat_streak": flat_streak,
        "bnk_fail_count": bnk_fail_count,
        "unresearched_bottlenecks": unresearched_bnks,
        "directive": directive,
    }


def sync_stagnation_after_experiment(store: GraphStore, track: str) -> str:
    """Update persisted `stagnation_alert` meta after an experiment and return alert string if locked."""
    state = evaluate_stagnation_state(store, track=track)
    if state["locked"]:
        store.set_meta("stagnation_alert", state["directive"])
        store.log_event("STAGNATION_DETECTED", track.upper() or "MAIN", state["reason"])
        return str(state["directive"])
    if store.get_meta("stagnation_alert"):
        store.set_meta("stagnation_alert", "")
    return ""


def enforce_anti_stagnation_on_proposal(store: GraphStore, bottleneck_id: str = "") -> None:
    """Block `manage_proposal(action='create')` when stuck in local hill-climbing without external literature."""
    state = evaluate_stagnation_state(store, bottleneck_id=bottleneck_id)
    if state["locked"]:
        raise ValueError(f"LAW-06 Anti-Stagnation Literature Gate: {state['directive']}")
