"""5-Stage Long-Horizon Memory Hygiene, O(log N) Hierarchical Compaction & Archive GC."""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from supermemory.models import EdgeType, MemoryEdge, MemoryNode, MemoryTier, NodeType, utc_now_iso
from supermemory.storage.sqlite_store import GraphStore


def _seq_num(nid: str) -> int:
    m = re.search(r"(\d+)$", nid or "")
    return int(m.group(1)) if m else 0


def _next_sem_id(store: GraphStore) -> str:
    existing = store.list_nodes(node_types=[NodeType.KNOWLEDGE_NODE.value], limit=5000)
    nums = [int(m.group(1)) for n in existing for m in [re.match(r"^SEM-(\d+)$", n.id)] if m]
    return f"SEM-{(max(nums) + 1) if nums else 1:03d}"


def _anchor_lookup(store: GraphStore) -> Dict[str, str]:
    anchor_of: Dict[str, str] = {}
    for ed in store.list_edges():
        if ed.target_id.startswith(("BNK-", "PROP-", "METH-", "ALGO-")):
            anchor_of.setdefault(ed.source_id, ed.target_id)
    return anchor_of


def _compact_failure_insights(store: GraphStore, anchor_of: Dict[str, str]) -> List[str]:
    """Keep 12 newest FAILURE_INSIGHT raw nodes; merge older clusters into Dead-End SEM digests."""
    fails = [
        n for n in store.list_nodes(node_types=[NodeType.OBSERVATION.value], limit=5000)
        if n.status == "FAILURE_INSIGHT" and not (n.metadata or {}).get("consolidated")
    ]
    if len(fails) <= 20:
        return []
    fails.sort(key=lambda n: (n.created_at, _seq_num(n.id)), reverse=True)
    grouped: Dict[str, List[MemoryNode]] = {}
    for nd in fails[12:]:
        key = anchor_of.get(nd.id) or str((nd.metadata or {}).get("track") or "GENERAL").upper()
        grouped.setdefault(key, []).append(nd)

    created: List[str] = []
    kn_dir = store.mem_dir / "06_KNOWLEDGE_NODES"
    kn_dir.mkdir(parents=True, exist_ok=True)
    for key, items in grouped.items():
        for start in range(0, len(items), 15):
            chunk = items[start : start + 15]
            if len(chunk) < 4:
                continue
            sem_id = _next_sem_id(store)
            rel_path = f"memory/06_KNOWLEDGE_NODES/{sem_id}.md"
            bullets = [f"- ❌ **`{c.id}`**: {c.summary[:160]}" for c in chunk]
            heads = "; ".join(c.summary[:42] for c in chunk[:3])
            summary = f"[DEAD-END DIGEST · {key} · {len(chunk)} failures] {heads}"[:235]
            md = (
                f"# {sem_id} [FAILURE_INSIGHT]: Dead-End Digest — {key}\n\n"
                f"- **Consolidated At:** `{utc_now_iso()}` | **Count:** `{len(chunk)}` failures\n\n"
                + "\n".join(bullets)
                + "\n"
            )
            (store.workspace_root / rel_path).write_text(md, encoding="utf-8")
            store.upsert_node(
                MemoryNode(
                    id=sem_id, node_type=NodeType.KNOWLEDGE_NODE.value,
                    title=f"Falsified Dead-End Digest: {key} ({len(chunk)} items)",
                    status="FAILURE_INSIGHT", summary=summary, content=md, file_path=rel_path,
                    tags=["consolidated", "dead-end-digest", key.lower()], priority=90,
                    metadata={"memory_tier": MemoryTier.SEMANTIC.value, "is_dead_end_digest": True, "source_ids": [c.id for c in chunk]},
                ),
                log_event=False,
            )
            for c in chunk:
                store.add_edge(MemoryEdge(source_id=c.id, target_id=sem_id, relation=EdgeType.CONSOLIDATED_INTO.value))
                c.status = "CONSOLIDATED"
                c.metadata["consolidated"] = True
                c.metadata["consolidated_into"] = sem_id
                store.upsert_node(c, log_event=False)
            if key.startswith(("BNK-", "PROP-", "METH-", "ALGO-")) and store.get_node(key) is not None:
                store.add_edge(MemoryEdge(source_id=sem_id, target_id=key, relation=EdgeType.REFERENCES.value))
            created.append(sem_id)
    return created


def _compact_second_order_sems(store: GraphStore, anchor_of: Dict[str, str]) -> List[str]:
    """Bound active SEM-* digests to O(log N) via 2nd-order Macro-SEM hierarchical merging."""
    sems = [
        n for n in store.list_nodes(node_types=[NodeType.KNOWLEDGE_NODE.value], limit=3000)
        if n.id.startswith("SEM-") and n.status == "ACTIVE"
        and not (n.metadata or {}).get("consolidated") and not (n.metadata or {}).get("macro_consolidated")
    ]
    if len(sems) <= 20:
        return []
    sems.sort(key=lambda n: (n.created_at, _seq_num(n.id)), reverse=True)
    grouped: Dict[str, List[MemoryNode]] = {}
    for nd in sems[10:]:
        key = anchor_of.get(nd.id) or "PROJECT"
        grouped.setdefault(key, []).append(nd)

    created: List[str] = []
    kn_dir = store.mem_dir / "06_KNOWLEDGE_NODES"
    kn_dir.mkdir(parents=True, exist_ok=True)
    for key, items in grouped.items():
        for start in range(0, len(items), 8):
            chunk = items[start : start + 8]
            if len(chunk) < 3:
                continue
            macro_id = _next_sem_id(store)
            rel_path = f"memory/06_KNOWLEDGE_NODES/{macro_id}.md"
            bullets = [f"- **`{c.id}`** ({c.title}): {c.summary[:160]}" for c in chunk]
            summary = f"[MACRO-SYNTHESIS · {key} · {len(chunk)} digests] " + " | ".join(c.title[:36] for c in chunk[:3])
            md = f"# {macro_id} [MACRO-SEMANTIC]: {key} Synthesis\n\n" + "\n".join(bullets) + "\n"
            (store.workspace_root / rel_path).write_text(md, encoding="utf-8")
            store.upsert_node(
                MemoryNode(
                    id=macro_id, node_type=NodeType.KNOWLEDGE_NODE.value,
                    title=f"Macro-Synthesis: {key} ({len(chunk)} digests)", status="ACTIVE",
                    summary=summary[:235], content=md, file_path=rel_path,
                    tags=["consolidated", "macro-semantic"], priority=91,
                    metadata={"memory_tier": MemoryTier.SEMANTIC.value, "macro_consolidated": True, "source_ids": [c.id for c in chunk]},
                ),
                log_event=False,
            )
            for c in chunk:
                store.add_edge(MemoryEdge(source_id=c.id, target_id=macro_id, relation=EdgeType.CONSOLIDATED_INTO.value))
                c.status = "CONSOLIDATED"
                c.metadata["consolidated"] = True
                c.metadata["consolidated_into"] = macro_id
                store.upsert_node(c, log_event=False)
            created.append(macro_id)
    return created


def _normalize_lifecycle_statuses(store: GraphStore) -> Dict[str, int]:
    """Auto-archive AUDITED proposals, close answered RQs, and sync IDEA/ALGO statuses."""
    edges = store.list_edges()
    archived_props = 0
    for p in store.list_nodes(node_types=[NodeType.PROPOSAL.value], limit=1000):
        if p.status == "AUDITED":
            audits = list((p.metadata or {}).get("audits") or [])
            tasks = list((p.metadata or {}).get("tasks") or [])
            done = list((p.metadata or {}).get("tasks_done") or [])
            all_done = bool(tasks) and all(i < len(done) and bool(done[i]) for i in range(len(tasks)))
            if all_done or any(isinstance(a, dict) and str(a.get("verdict") or "").upper() == "APPROVE" for a in audits):
                p.status = "ARCHIVED"
                store.upsert_node(p, log_event=False)
                archived_props += 1

    resolved_bnks = {
        b.id for b in store.list_nodes(node_types=[NodeType.BOTTLENECK.value], limit=500) if b.status == "RESOLVED"
    }
    closed_rqs = 0
    for ed in edges:
        rq_cand = ed.source_id if (ed.target_id in resolved_bnks and ed.source_id.startswith("RQ-")) else (
            ed.target_id if (ed.source_id in resolved_bnks and ed.target_id.startswith("RQ-")) else ""
        )
        if rq_cand:
            rq = store.get_node(rq_cand)
            if rq is not None and rq.status == "OPEN":
                rq.status = "ANSWERED"
                store.upsert_node(rq, log_event=False)
                closed_rqs += 1

    prop_status = {p.id: p.status for p in store.list_nodes(node_types=[NodeType.PROPOSAL.value], limit=1000)}
    status_map = {"APPROVED": "VALIDATED", "ACTIVE": "VALIDATED", "PROPOSED": "SEED", "VALIDATING": "SEED"}
    synced_ideas = 0
    for nd in store.list_nodes(node_types=[NodeType.IDEA.value, NodeType.ALGORITHM.value], limit=1000):
        nxt = status_map.get(nd.status.upper(), nd.status.upper())
        linked_p = [
            ed.target_id if ed.source_id == nd.id else ed.source_id
            for ed in edges
            if (ed.source_id == nd.id and ed.target_id in prop_status)
            or (ed.target_id == nd.id and ed.source_id in prop_status)
        ]
        if any(prop_status[pid] in ("ARCHIVED", "AUDITED") for pid in linked_p) and nxt not in ("REJECTED", "ARCHIVED"):
            nxt = "IMPLEMENTED"
        elif any(prop_status[pid] in ("IMPLEMENTING", "DESIGNED", "PROPOSED") for pid in linked_p) and nxt == "SEED":
            nxt = "PROMOTED"
        if nxt != nd.status:
            nd.status = nxt
            store.upsert_node(nd, log_event=False)
            synced_ideas += 1
    return {"archived_proposals": archived_props, "closed_rqs": closed_rqs, "synced_ideas": synced_ideas}


def _archive_cold_markdown_files(store: GraphStore) -> int:
    """Move CONSOLIDATED / SUPERSEDED raw knowledge markdown files into `memory/archive/`."""
    moved = 0
    arch_dir = store.mem_dir / "archive" / "06_KNOWLEDGE_NODES"
    for nd in store.list_nodes(node_types=[NodeType.OBSERVATION.value, NodeType.KNOWLEDGE_NODE.value], limit=5000):
        if nd.status not in ("CONSOLIDATED", "SUPERSEDED"):
            continue
        fp = (nd.file_path or "").replace("\\", "/")
        if not fp.startswith("memory/06_KNOWLEDGE_NODES/"):
            continue
        src = store.workspace_root / fp
        if not src.is_file():
            continue
        arch_dir.mkdir(parents=True, exist_ok=True)
        dst_rel = f"memory/archive/06_KNOWLEDGE_NODES/{src.name}"
        shutil.move(str(src), str(store.workspace_root / dst_rel))
        nd.file_path = dst_rel
        store.upsert_node(nd, log_event=False)
        moved += 1
    return moved


def run_memory_hygiene_gc(store: GraphStore, archive_disk_files: bool = True) -> Dict[str, Any]:
    """Execute 5-stage long-horizon GC: failure digests, Macro-SEMs, lifecycle sync, archive & SQLite prune."""
    anchor_of = _anchor_lookup(store)
    fail_sems = _compact_failure_insights(store, anchor_of)
    macro_sems = _compact_second_order_sems(store, anchor_of)
    lc_stats = _normalize_lifecycle_statuses(store)
    archived_files = _archive_cold_markdown_files(store) if archive_disk_files else 0

    now = datetime.now(timezone.utc)
    cut_cache = (now - timedelta(days=30)).replace(microsecond=0).isoformat()
    cut_sess = (now - timedelta(days=14)).replace(microsecond=0).isoformat()
    store.conn.execute("DELETE FROM http_cache WHERE created_at < ?", (cut_cache,))
    store.conn.execute("DELETE FROM session_state WHERE updated_at < ?", (cut_sess,))
    store.prune_events(max_events=1500)
    store.conn.commit()
    return {
        "failure_digests": fail_sems,
        "macro_sems": macro_sems,
        "archived_files": archived_files,
        **lc_stats,
    }
