"""Subagent-Driven Semantic Memory Curation Engine (`review` / `apply_plan` / `restore`) with Zero-Loss Gates."""

from __future__ import annotations

import math
import re
import shutil
from typing import Any, Dict, List, Set

from supermemory.cognitive.tiers import consolidate_nodes
from supermemory.graph.hybrid_ranker import compute_hybrid_similarity
from supermemory.graph.supersession import apply_supersedes_links
from supermemory.models import DEAD_END_STATUSES, EdgeType, MemoryEdge, MemoryNode, MemoryTier, NodeType
from supermemory.storage.sqlite_store import GraphStore

_SACRED_TYPES = {
    NodeType.LAW.value,
    NodeType.GATE.value,
    NodeType.EXPERIMENT.value,
    NodeType.LESSON.value,
    NodeType.METHOD_CARD.value,
}
_ACTIVE_PROP_STATES = {"PROPOSED", "DESIGNED", "IMPLEMENTING", "CHALLENGED"}
_ISO_TS_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[^\s`]*")
_METRIC_TOK_RE = re.compile(r"(?<![A-Za-z0-9_.-])(?:\d+\.\d{2,}|\d+(?:\.\d+)?%)(?![0-9.])")


def _seq_num(nid: str) -> int:
    m = re.search(r"(\d+)$", nid or "")
    return int(m.group(1)) if m else 0


def _extract_metrics(text: str) -> Set[str]:
    clean = _ISO_TS_RE.sub(" ", text or "")
    return {m.rstrip("0").rstrip(".") if ("." in m and not m.endswith("%")) else m for m in _METRIC_TOK_RE.findall(clean)}


def _unreviewed_observations(all_nodes: List[MemoryNode]) -> List[MemoryNode]:
    obs = [
        n for n in all_nodes
        if n.node_type == NodeType.OBSERVATION.value and n.status not in ("CONSOLIDATED", "SUPERSEDED")
        and not any((n.metadata or {}).get(k) for k in ("consolidated", "superseded_by", "curator_reviewed"))
    ]
    obs.sort(key=lambda n: (n.created_at, _seq_num(n.id)), reverse=True)
    return obs


def check_curation_pressure(store: GraphStore, mark_prompted: bool = False) -> Dict[str, Any]:
    """Fast SQLite check deciding when `memory-curator` should sweep stale/redundant transient notes (never experiments!)."""
    all_nodes = store.list_nodes(limit=5000)
    total_n = len(all_nodes)
    raw_obs = _unreviewed_observations(all_nodes)
    audited_props = [n for n in all_nodes if n.node_type == NodeType.PROPOSAL.value and n.status == "AUDITED"]
    linked_ids = {str(r[0]) for r in store.conn.execute("SELECT source_id FROM edges UNION SELECT target_id FROM edges").fetchall()}
    orphans = [n for n in all_nodes if n.node_type in (NodeType.OBSERVATION.value, NodeType.IDEA.value, NodeType.ALGORITHM.value, NodeType.KNOWLEDGE_NODE.value) and n.id not in linked_ids]

    reasons = [
        lbl for cond, lbl in (
            (len(raw_obs) >= 25, f"{len(raw_obs)} unreviewed working observations"),
            (len(audited_props) >= 3, f"{len(audited_props)} completed AUDITED proposals"),
            (len(orphans) >= 3, f"{len(orphans)} unlinked orphan nodes"),
        ) if cond
    ]
    last_prompt_n = int(store.get_meta("last_curation_prompt_nodes") or "0")
    needs = bool(reasons) and ((last_prompt_n == 0) or ((total_n - last_prompt_n) >= 12))
    if needs and mark_prompted:
        store.set_meta("last_curation_prompt_nodes", str(total_n))
    ws_str = str(store.workspace_root)
    prompt = (
        f"Curate ONLY stale/obsolete/duplicate transient notes in `{ws_str}` (NEVER touch experiments or valuable empirical results!): "
        f"1) Call `consolidate(mode='review', workspace='{ws_str}')` and read full `.md` files. "
        f"2) Keep ALL real empirical results, slice metrics, and scientific findings intact via `op='keep_distinct'`. "
        f"3) Only `supersede` outdated draft/progress notes replaced by final results, `merge` redundant duplicate remarks, "
        f"and archive completed `AUDITED` specs via `consolidate(mode='apply_plan', workspace='{ws_str}', operations=[...])`."
    )
    return {
        "needs_curation": needs, "reasons": reasons, "subagent_type": "memory-curator", "subagent_prompt": prompt if needs else "",
        "metrics": {"total_nodes": total_n, "raw_observations": len(raw_obs), "audited_proposals": len(audited_props), "orphan_nodes": len(orphans)},
    }


def build_curation_review_packet(store: GraphStore) -> Dict[str, Any]:
    """Read-only semantic dossier for `memory-curator` (`consolidate(mode='review')` — 0 mutations)."""
    all_nodes = store.list_nodes(limit=5000)
    edges = store.list_edges()
    exp_anchor: Dict[str, str] = {}
    anchor_of: Dict[str, str] = {}
    for ed in edges:
        if ed.source_id.startswith("EXP-") and ed.target_id.startswith(("BNK-", "PROP-")):
            exp_anchor.setdefault(ed.source_id, ed.target_id)
    for ed in edges:
        if ed.target_id.startswith(("BNK-", "PROP-", "METH-", "ALGO-")):
            anchor_of.setdefault(ed.source_id, ed.target_id)
        elif ed.target_id in exp_anchor:
            anchor_of.setdefault(ed.source_id, exp_anchor[ed.target_id])

    active_obs = _unreviewed_observations(all_nodes)
    dup_groups: List[Dict[str, Any]] = []
    seen_pairs: Set[tuple[str, str]] = set()
    for obs in active_obs[:80]:
        peers = [p for p in active_obs if p.id != obs.id and p.status == obs.status]
        if not peers:
            continue
        sims = compute_hybrid_similarity(f"{obs.title} {obs.summary}", peers)
        matches = [p for p in peers if sims.get(p.id, 0.0) >= 0.52 and (min(obs.id, p.id), max(obs.id, p.id)) not in seen_pairs]
        if matches:
            top_m = sorted(matches, key=lambda x: sims.get(x.id, 0.0), reverse=True)[:3]
            for m in top_m:
                seen_pairs.add((min(obs.id, m.id), max(obs.id, m.id)))
            dup_groups.append({
                "similarity_top": round(sims.get(top_m[0].id, 0.0), 3),
                "warning": "Read full `file_path` first! Use `op='keep_distinct'` if they measure different slices, cities, seeds, or hyperparameters.",
                "nodes": [{"id": x.id, "title": x.title, "status": x.status, "summary": x.summary, "file_path": x.file_path} for x in [obs, *top_m]],
            })
        if len(dup_groups) >= 12:
            break

    by_anchor: Dict[str, List[MemoryNode]] = {}
    for nd in active_obs[6:]:
        key = anchor_of.get(nd.id) or str((nd.metadata or {}).get("track") or "GENERAL").upper()
        by_anchor.setdefault(f"{nd.status}:{key}", []).append(nd)
    obs_batches = [
        {"group_key": k, "count": len(items), "nodes": [{"id": x.id, "title": x.title, "summary": x.summary, "file_path": x.file_path} for x in items[:15]]}
        for k, items in by_anchor.items() if len(items) >= 3
    ]

    resolved_bnks = {b.id for b in all_nodes if b.node_type == NodeType.BOTTLENECK.value and b.status == "RESOLVED"}
    lifecycle_items: List[Dict[str, Any]] = [
        {"id": p.id, "type": "PROPOSAL", "current_status": p.status, "suggested_status": "ARCHIVED", "title": p.title}
        for p in all_nodes if p.node_type == NodeType.PROPOSAL.value and p.status == "AUDITED"
    ]
    for ed in edges:
        rq_id = ed.source_id if (ed.target_id in resolved_bnks and ed.source_id.startswith("RQ-")) else (
            ed.target_id if (ed.source_id in resolved_bnks and ed.target_id.startswith("RQ-")) else ""
        )
        if rq_id:
            rq_n = store.get_node(rq_id)
            if rq_n is not None and rq_n.status == "OPEN":
                lifecycle_items.append({"id": rq_n.id, "type": "RESEARCH_QUESTION", "current_status": "OPEN", "suggested_status": "ANSWERED", "title": rq_n.title})

    linked_ids = {ed.source_id for ed in edges} | {ed.target_id for ed in edges}
    orphans = [
        {"id": n.id, "type": n.node_type, "title": n.title, "summary": n.summary[:140]}
        for n in all_nodes if n.node_type in (NodeType.OBSERVATION.value, NodeType.IDEA.value, NodeType.ALGORITHM.value, NodeType.KNOWLEDGE_NODE.value) and n.id not in linked_ids
    ]
    return {
        "mode": "REVIEW_PACKET",
        "zero_loss_rules": [
            "EXPERIMENTS (`EXP-*`), LESSONS, METHOD_CARDS, LAWS, GATES & real empirical findings are SACRED — NEVER merge, supersede, or hide them!",
            "ONLY curate low-value/obsolete transient clutter (stale progress polls, superseded draft notes, exact/redundant duplicate remarks).",
            "Mark valuable distinct empirical observations with `op='keep_distinct'` so they remain permanently first-class.",
        ],
        "duplicate_candidate_groups": dup_groups, "consolidation_candidate_batches": obs_batches,
        "lifecycle_review_items": lifecycle_items[:20], "orphan_nodes": orphans[:20],
    }


def _assert_curatable_source(nd: MemoryNode) -> None:
    if nd.node_type in _SACRED_TYPES:
        raise ValueError(f"Zero-Loss Curation Gate: Sacred node `{nd.id}` (`{nd.node_type}`) cannot be consolidated or superseded.")
    if nd.node_type == NodeType.EXPERIMENT.value and nd.status == "VICTORY_CONFIRMED":
        raise ValueError(f"Zero-Loss Curation Gate: Verified SOTA/Victory experiment `{nd.id}` cannot be consolidated.")
    if nd.node_type == NodeType.PROPOSAL.value and nd.status in _ACTIVE_PROP_STATES:
        raise ValueError(f"Zero-Loss Curation Gate: Active proposal `{nd.id}` (`{nd.status}`) cannot be consolidated or hidden.")
    if nd.node_type == NodeType.BOTTLENECK.value and nd.status == "OPEN":
        raise ValueError(f"Zero-Loss Curation Gate: Open bottleneck `{nd.id}` cannot be consolidated or hidden.")


def apply_curated_plan(store: GraphStore, operations: List[Dict[str, Any]], archive_cold_files: bool = False) -> Dict[str, Any]:
    """Execute LLM-reviewed curation plan from `memory-curator` under strict Zero-Loss Guardrails."""
    if not operations:
        raise ValueError("`operations` list must contain at least one reviewed curation operation (use `op='keep_distinct'` if keeping all separate).")
    merged_ids, superseded_ids, transitioned, linked, restored, kept_distinct = [], [], [], [], [], []

    for op in operations:
        kind = str(op.get("op") or "").strip().lower()
        if kind == "merge":
            src_ids = [str(x).strip() for x in (op.get("source_ids") or []) if str(x).strip()]
            src_nodes = [n for sid in src_ids for n in [store.get_node(sid)] if n is not None]
            if len(src_nodes) < 2:
                raise ValueError(f"`merge` requires `>= 2` valid source nodes (got `{src_ids}`).")
            for sn in src_nodes:
                _assert_curatable_source(sn)
            ttl, summ, body = str(op.get("title") or "").strip(), str(op.get("summary") or "").strip(), str(op.get("content") or "").strip()
            if len(ttl) < 10 or len(summ) < 40 or len(body) < 80:
                raise ValueError("Zero-Loss Curation Gate: `merge` requires substantive `title` (>=10), `summary` (>=40), and `content` (>=80 chars).")
            src_metrics = {m for sn in src_nodes for m in _extract_metrics(f"{sn.title} {sn.summary} {sn.content}")}
            dst_metrics = _extract_metrics(f"{ttl} {summ} {body}")
            if src_metrics:
                req_cnt = len(src_metrics) if len(src_metrics) <= 4 else math.ceil(len(src_metrics) * 0.75)
                kept_cnt = len(src_metrics & dst_metrics)
                if kept_cnt < req_cnt:
                    missing = sorted(src_metrics - dst_metrics)[:6]
                    raise ValueError(
                        f"Zero-Loss Curation Gate: Synthesis dropped source metrics {missing} "
                        f"(preserved {kept_cnt}/{len(src_metrics)}). Preserve all key quantitative metrics!"
                    )
            res = consolidate_nodes(store, src_ids, str(op.get("target_tier") or MemoryTier.SEMANTIC.value), ttl, summ, body)
            new_id = str(res["created_node"]["id"])
            dead_flags = [sn.status.upper() in DEAD_END_STATUSES or sn.status == "FAILURE_INSIGHT" for sn in src_nodes]
            if any(dead_flags):
                sem_nd = store.get_node(new_id)
                if sem_nd is not None:
                    if all(dead_flags):
                        sem_nd.status = "FAILURE_INSIGHT"
                        sem_nd.metadata["is_dead_end_digest"] = True
                    else:
                        sem_nd.metadata["has_dead_end_warnings"] = True
                    store.upsert_node(sem_nd, log_event=False)
            merged_ids.append(new_id)
        elif kind == "supersede":
            newer_id = str(op.get("newer_id") or "").strip()
            older_ids = [str(x).strip() for x in (op.get("older_ids") or []) if str(x).strip()]
            reason = str(op.get("reason") or "").strip()
            if not newer_id or store.get_node(newer_id) is None or not older_ids or len(reason) < 10:
                raise ValueError("Zero-Loss Curation Gate: `supersede` requires existing `newer_id`, `older_ids`, and semantic `reason` (>=10 chars).")
            for oid in older_ids:
                old_n = store.get_node(oid)
                if old_n is not None:
                    _assert_curatable_source(old_n)
                    if old_n.status.upper() in DEAD_END_STATUSES or old_n.status == "FAILURE_INSIGHT":
                        raise ValueError(f"Zero-Loss Curation Gate: Dead-end warning `{oid}` cannot be superseded into silence; use `merge` to preserve warning.")
            superseded_ids.extend(apply_supersedes_links(store, [newer_id], older_ids))
        elif kind in ("keep_distinct", "mark_reviewed"):
            for kid in [str(x).strip() for x in (op.get("node_ids") or []) if str(x).strip()]:
                kn = store.get_node(kid)
                if kn is not None:
                    kn.metadata["curator_reviewed"] = True
                    store.upsert_node(kn, log_event=False)
                    kept_distinct.append(kid)
        elif kind == "transition_status":
            nid, nxt = str(op.get("node_id") or "").strip(), str(op.get("new_status") or "").strip().upper()
            nd = store.get_node(nid)
            if nd is None or nxt not in ("ARCHIVED", "ANSWERED", "IMPLEMENTED", "PROMOTED", "VALIDATED"):
                raise ValueError(f"Invalid `transition_status` target `{nid}` -> `{nxt}`.")
            _assert_curatable_source(nd)
            nd.status = nxt
            if nxt == "ARCHIVED":
                nd.priority = min(nd.priority, 35)
            store.upsert_node(nd, log_event=False)
            transitioned.append(f"{nid}->{nxt}")
        elif kind == "link":
            s_id, t_id = str(op.get("source_id") or "").strip(), str(op.get("target_id") or "").strip()
            rel = str(op.get("relation") or EdgeType.REFERENCES.value).strip().upper()
            if store.get_node(s_id) is None or store.get_node(t_id) is None:
                raise ValueError(f"Both `source_id` (`{s_id}`) and `target_id` (`{t_id}`) must exist.")
            store.add_edge(MemoryEdge(source_id=s_id, target_id=t_id, relation=rel))
            linked.append(f"{s_id}->{t_id}")
        elif kind == "restore":
            for rid in [str(x).strip() for x in (op.get("node_ids") or []) if str(x).strip()]:
                rn = store.get_node(rid)
                if rn is None:
                    continue
                prior_st = str(rn.metadata.pop("prior_status", "") or rn.metadata.get("verdict") or rn.metadata.get("kind") or "")
                prior_pr = rn.metadata.pop("prior_priority", None)
                for k_drop in ("consolidated", "consolidated_into", "superseded_by"):
                    rn.metadata.pop(k_drop, None)
                rn.status = prior_st or ("SCIENTIFIC_INSIGHT" if rn.node_type == NodeType.OBSERVATION.value else "ACTIVE")
                rn.priority = int(prior_pr) if prior_pr is not None else 88
                fp = (rn.file_path or "").replace("\\", "/")
                if fp.startswith("memory/archive/") and (store.workspace_root / fp).is_file():
                    dst_rel = "memory/" + fp.removeprefix("memory/archive/")
                    (store.workspace_root / dst_rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(store.workspace_root / fp), str(store.workspace_root / dst_rel))
                    rn.file_path = dst_rel
                store.conn.execute("DELETE FROM edges WHERE target_id = ? AND relation = 'SUPERSEDES'", (rid,))
                store.upsert_node(rn, log_event=False)
                restored.append(rid)
        else:
            raise ValueError(f"Unknown curation op `{kind}` (expected merge|supersede|keep_distinct|transition_status|link|restore).")

    archived_files = 0
    if archive_cold_files:
        for nd in store.list_nodes(node_types=[NodeType.OBSERVATION.value, NodeType.KNOWLEDGE_NODE.value], limit=5000):
            fp = (nd.file_path or "").replace("\\", "/")
            if nd.status in ("CONSOLIDATED", "SUPERSEDED") and fp.startswith("memory/06_KNOWLEDGE_NODES/") and (store.workspace_root / fp).is_file():
                dst_rel = f"memory/archive/06_KNOWLEDGE_NODES/{(store.workspace_root / fp).name}"
                (store.workspace_root / dst_rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(store.workspace_root / fp), str(store.workspace_root / dst_rel))
                nd.file_path = dst_rel
                store.upsert_node(nd, log_event=False)
                archived_files += 1

    store.set_meta("last_curation_prompt_nodes", str(len(store.list_nodes(limit=5000))))
    store.log_event("SUBAGENT_CURATION_APPLIED", "MEMORY_CURATOR", f"Applied reviewed plan: merged={merged_ids}, superseded={superseded_ids}, kept={len(kept_distinct)}, status={transitioned}, restored={restored}")
    return {"merged_nodes": merged_ids, "superseded_ids": superseded_ids, "kept_distinct": kept_distinct, "transitioned": transitioned, "linked": linked, "restored": restored, "archived_files": archived_files}
