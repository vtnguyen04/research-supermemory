"""Subagent-Driven Semantic Memory Curation Engine (`review` / `apply_plan` / `restore`) with Zero-Loss Gates."""

from __future__ import annotations

import re
import shutil
from typing import Any, Dict, List, Set

from supermemory.cognitive.tiers import consolidate_nodes
from supermemory.graph.hybrid_ranker import compute_hybrid_similarity
from supermemory.graph.supersession import apply_supersedes_links
from supermemory.models import DEAD_END_STATUSES, EdgeType, MemoryEdge, MemoryNode, MemoryTier, NodeType
from supermemory.storage.sqlite_store import GraphStore

_SACRED_TYPES = {NodeType.LAW.value, NodeType.GATE.value}
_ACTIVE_PROP_STATES = {"PROPOSED", "DESIGNED", "IMPLEMENTING", "CHALLENGED"}
_DEC_NUM_RE = re.compile(r"\b\d+\.\d+\b")


def _seq_num(nid: str) -> int:
    m = re.search(r"(\d+)$", nid or "")
    return int(m.group(1)) if m else 0


def _has_edge(store: GraphStore, nid: str) -> bool:
    return store.conn.execute("SELECT 1 FROM edges WHERE source_id = ? OR target_id = ? LIMIT 1", (nid, nid)).fetchone() is not None


def _active_observations(all_nodes: List[MemoryNode]) -> List[MemoryNode]:
    obs = [
        n for n in all_nodes
        if n.node_type == NodeType.OBSERVATION.value
        and n.status not in ("CONSOLIDATED", "SUPERSEDED")
        and not (n.metadata or {}).get("consolidated")
        and not (n.metadata or {}).get("superseded_by")
    ]
    obs.sort(key=lambda n: (n.created_at, _seq_num(n.id)), reverse=True)
    return obs


def check_curation_pressure(store: GraphStore, mark_prompted: bool = False) -> Dict[str, Any]:
    """O(1) non-destructive check deciding when main agent should spawn `memory-curator` subagent."""
    all_nodes = store.list_nodes(limit=5000)
    total_n = len(all_nodes)
    raw_obs = _active_observations(all_nodes)
    raw_exps = [
        n for n in all_nodes
        if n.node_type == NodeType.EXPERIMENT.value
        and n.status not in ("CONSOLIDATED", "VICTORY_CONFIRMED")
        and not (n.metadata or {}).get("consolidated")
    ]
    audited_props = [n for n in all_nodes if n.node_type == NodeType.PROPOSAL.value and n.status == "AUDITED"]
    orphans = [
        n for n in all_nodes
        if n.node_type in (NodeType.OBSERVATION.value, NodeType.IDEA.value, NodeType.ALGORITHM.value, NodeType.KNOWLEDGE_NODE.value)
        and not _has_edge(store, n.id)
    ]

    reasons: List[str] = []
    if len(raw_obs) >= 24:
        reasons.append(f"{len(raw_obs)} unconsolidated observations")
    if len(raw_exps) >= 14:
        reasons.append(f"{len(raw_exps)} unconsolidated episodic runs")
    if len(audited_props) >= 3:
        reasons.append(f"{len(audited_props)} completed AUDITED proposals")
    if len(orphans) >= 3:
        reasons.append(f"{len(orphans)} unlinked orphan nodes")

    last_prompt_n = int(store.get_meta("last_curation_prompt_nodes") or "0")
    needs = bool(reasons) and ((last_prompt_n == 0) or ((total_n - last_prompt_n) >= 10))
    if needs and mark_prompted:
        store.set_meta("last_curation_prompt_nodes", str(total_n))

    ws_str = str(store.workspace_root)
    prompt = (
        f"Curate SuperMemory in workspace `{ws_str}` with ZERO data loss: "
        f"1) Call `consolidate(mode='review', workspace='{ws_str}')` to inspect candidate duplicate groups, "
        f"verbose observation/experiment clusters, completed specs, and orphans. "
        f"2) Read the full `.md` files (`read_file` or `recall(node_id=...)`) before deciding — NEVER merge observations "
        f"from different slices, cities, seeds, or hyperparameters! "
        f"3) Author rich syntheses preserving ALL concrete metrics/thresholds/configs and submit via "
        f"`consolidate(mode='apply_plan', workspace='{ws_str}', operations=[...])`, then run `audit_gates`."
    )
    return {
        "needs_curation": needs,
        "reasons": reasons,
        "metrics": {
            "total_nodes": total_n,
            "raw_observations": len(raw_obs),
            "unconsolidated_runs": len(raw_exps),
            "audited_proposals": len(audited_props),
            "orphan_nodes": len(orphans),
        },
        "subagent_type": "memory-curator",
        "subagent_prompt": prompt if needs else "",
    }


def build_curation_review_packet(store: GraphStore) -> Dict[str, Any]:
    """Read-only semantic dossier for `memory-curator` (`consolidate(mode='review')` — 0 mutations)."""
    all_nodes = store.list_nodes(limit=5000)
    edges = store.list_edges()
    anchor_of: Dict[str, str] = {}
    for ed in edges:
        if ed.target_id.startswith(("BNK-", "PROP-", "METH-", "ALGO-")):
            anchor_of.setdefault(ed.source_id, ed.target_id)

    active_obs = _active_observations(all_nodes)
    dup_groups: List[Dict[str, Any]] = []
    seen_pairs: Set[tuple[str, str]] = set()
    for obs in active_obs[:80]:
        peers = [p for p in active_obs if p.id != obs.id and p.status == obs.status]
        if not peers:
            continue
        sims = compute_hybrid_similarity(f"{obs.title} {obs.summary}", peers)
        matches = [
            p for p in peers
            if sims.get(p.id, 0.0) >= 0.52 and (min(obs.id, p.id), max(obs.id, p.id)) not in seen_pairs
        ]
        if matches:
            top_m = sorted(matches, key=lambda x: sims.get(x.id, 0.0), reverse=True)[:3]
            for m in top_m:
                seen_pairs.add((min(obs.id, m.id), max(obs.id, m.id)))
            dup_groups.append({
                "similarity_top": round(sims.get(top_m[0].id, 0.0), 3),
                "warning": "Read full `file_path` first! Keep BOTH if they measure different slices, buildings, seeds, or hyperparameters.",
                "nodes": [{"id": x.id, "title": x.title, "status": x.status, "summary": x.summary, "file_path": x.file_path} for x in [obs, *top_m]],
            })
        if len(dup_groups) >= 12:
            break

    by_anchor: Dict[str, List[MemoryNode]] = {}
    for nd in active_obs[8:]:
        key = anchor_of.get(nd.id) or str((nd.metadata or {}).get("track") or "GENERAL").upper()
        by_anchor.setdefault(f"{nd.status}:{key}", []).append(nd)
    obs_batches = [
        {"group_key": k, "count": len(items), "nodes": [{"id": x.id, "title": x.title, "summary": x.summary, "file_path": x.file_path} for x in items[:15]]}
        for k, items in by_anchor.items() if len(items) >= 5
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

    orphans = [
        {"id": n.id, "type": n.node_type, "title": n.title, "summary": n.summary[:140]}
        for n in all_nodes
        if n.node_type in (NodeType.OBSERVATION.value, NodeType.IDEA.value, NodeType.ALGORITHM.value, NodeType.KNOWLEDGE_NODE.value)
        and not _has_edge(store, n.id)
    ]
    return {
        "mode": "REVIEW_PACKET",
        "zero_loss_rules": [
            "NEVER merge observations from distinct slices, buildings, seeds, datasets, or hyperparameters.",
            "Every `merge` operation MUST preserve all concrete decimal metrics, thresholds, and configs inside `content`.",
            "Original nodes & `.md` files are NEVER deleted; `restore` reverses any consolidation in 1 call.",
        ],
        "duplicate_candidate_groups": dup_groups,
        "consolidation_candidate_batches": obs_batches,
        "lifecycle_review_items": lifecycle_items[:20],
        "orphan_nodes": orphans[:20],
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
        raise ValueError("`operations` list must contain at least one reviewed curation operation.")
    merged_ids, superseded_ids, transitioned, linked, restored = [], [], [], [], []

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
            src_nums = {m for sn in src_nodes for m in _DEC_NUM_RE.findall(f"{sn.title} {sn.summary}")}
            if src_nums and not _DEC_NUM_RE.search(f"{summ} {body}"):
                raise ValueError(
                    f"Zero-Loss Curation Gate: Source nodes contain quantitative metrics ({sorted(src_nums)[:4]}), "
                    "but your synthesized `summary`/`content` preserved ZERO numbers. Preserve concrete metrics!"
                )
            res = consolidate_nodes(store, src_ids, str(op.get("target_tier") or MemoryTier.SEMANTIC.value), ttl, summ, body)
            new_id = str(res["created_node"]["id"])
            if any(sn.status.upper() in DEAD_END_STATUSES or sn.status == "FAILURE_INSIGHT" for sn in src_nodes):
                sem_nd = store.get_node(new_id)
                if sem_nd is not None:
                    sem_nd.status = "FAILURE_INSIGHT"
                    sem_nd.metadata["is_dead_end_digest"] = True
                    store.upsert_node(sem_nd, log_event=False)
            merged_ids.append(new_id)
        elif kind == "supersede":
            newer_id = str(op.get("newer_id") or "").strip()
            older_ids = [str(x).strip() for x in (op.get("older_ids") or []) if str(x).strip()]
            reason = str(op.get("reason") or "").strip()
            if not newer_id or not older_ids or len(reason) < 10:
                raise ValueError("Zero-Loss Curation Gate: `supersede` requires `newer_id`, `older_ids`, and semantic `reason` (>=10 chars).")
            for oid in older_ids:
                old_n = store.get_node(oid)
                if old_n is not None:
                    _assert_curatable_source(old_n)
                    if old_n.status.upper() in DEAD_END_STATUSES or old_n.status == "FAILURE_INSIGHT":
                        raise ValueError(f"Zero-Loss Curation Gate: Dead-end warning `{oid}` cannot be superseded into silence; use `merge` to preserve warning.")
            superseded_ids.extend(apply_supersedes_links(store, [newer_id], older_ids))
        elif kind == "transition_status":
            nid, nxt = str(op.get("node_id") or "").strip(), str(op.get("new_status") or "").strip().upper()
            nd = store.get_node(nid)
            if nd is None or nxt not in ("ARCHIVED", "ANSWERED", "IMPLEMENTED", "PROMOTED", "VALIDATED"):
                raise ValueError(f"Invalid `transition_status` target `{nid}` -> `{nxt}`.")
            _assert_curatable_source(nd)
            nd.status = nxt
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
                for k_drop in ("consolidated", "consolidated_into", "superseded_by"):
                    rn.metadata.pop(k_drop, None)
                rn.status = str(rn.metadata.get("kind") or ("SCIENTIFIC_INSIGHT" if rn.node_type == NodeType.OBSERVATION.value else "ACTIVE"))
                fp = (rn.file_path or "").replace("\\", "/")
                if fp.startswith("memory/archive/06_KNOWLEDGE_NODES/") and (store.workspace_root / fp).is_file():
                    dst_rel = f"memory/06_KNOWLEDGE_NODES/{(store.workspace_root / fp).name}"
                    shutil.move(str(store.workspace_root / fp), str(store.workspace_root / dst_rel))
                    rn.file_path = dst_rel
                store.conn.execute("DELETE FROM edges WHERE target_id = ? AND relation = 'SUPERSEDES'", (rid,))
                store.upsert_node(rn, log_event=False)
                restored.append(rid)
        else:
            raise ValueError(f"Unknown curation op `{kind}` (expected merge|supersede|transition_status|link|restore).")

    archived_files = 0
    if archive_cold_files:
        arch_dir = store.mem_dir / "archive" / "06_KNOWLEDGE_NODES"
        for nd in store.list_nodes(node_types=[NodeType.OBSERVATION.value], limit=5000):
            fp = (nd.file_path or "").replace("\\", "/")
            if nd.status in ("CONSOLIDATED", "SUPERSEDED") and fp.startswith("memory/06_KNOWLEDGE_NODES/") and (store.workspace_root / fp).is_file():
                arch_dir.mkdir(parents=True, exist_ok=True)
                dst_rel = f"memory/archive/06_KNOWLEDGE_NODES/{(store.workspace_root / fp).name}"
                shutil.move(str(store.workspace_root / fp), str(store.workspace_root / dst_rel))
                nd.file_path = dst_rel
                store.upsert_node(nd, log_event=False)
                archived_files += 1

    store.set_meta("last_curation_prompt_nodes", str(len(store.list_nodes(limit=5000))))
    store.log_event("SUBAGENT_CURATION_APPLIED", "MEMORY_CURATOR", f"Applied reviewed plan: merged={merged_ids}, superseded={superseded_ids}, status={transitioned}, restored={restored}")
    return {"merged_nodes": merged_ids, "superseded_ids": superseded_ids, "transitioned": transitioned, "linked": linked, "restored": restored, "archived_files": archived_files}
