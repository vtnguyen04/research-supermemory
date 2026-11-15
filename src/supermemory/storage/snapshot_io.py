"""Portable Git-friendly JSON snapshot export/import & session state helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from supermemory.models import CodeGate, ExperimentRecord, MemoryEdge, MemoryNode, utc_now_iso

if TYPE_CHECKING:
    from supermemory.storage.sqlite_store import GraphStore


def export_snapshot(store: GraphStore, target_path: Path | None = None) -> Path:
    """Export deterministic Git-committable JSON snapshot of the Knowledge Graph."""
    out_path = target_path or store.snapshot_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    task_rows = store.conn.execute("SELECT * FROM agent_tasks ORDER BY wave ASC, task_id ASC").fetchall()
    tasks_export = [
        {
            "task_id": str(r["task_id"]),
            "wave": int(r["wave"]),
            "role": str(r["role"]),
            "title": str(r["title"]),
            "brief": str(r["brief"]),
            "status": str(r["status"]),
            "depends_on": json.loads(str(r["depends_on_json"] or "[]")),
            "locked_globs": json.loads(str(r["locked_globs_json"] or "[]")),
            "target_id": str(r["target_id"] or ""),
            "claimed_by": str(r["claimed_by"] or ""),
            "smoke_gate": str(r["smoke_gate"] or ""),
            "receipt": json.loads(str(r["receipt_json"] or "{}")),
            "created_at": str(r["created_at"]),
            "updated_at": str(r["updated_at"]),
        }
        for r in task_rows
    ]
    payload = {
        "schema_version": "3.0.0",
        "project_meta": store.get_all_meta(),
        "nodes": [n.to_dict() for n in store.list_nodes(limit=10000)],
        "edges": [e.to_dict() for e in store.list_edges()],
        "gates": [g.to_dict() for g in store.list_gates()],
        "experiments": [x.to_dict() for x in store.list_experiments()],
        "agent_tasks": tasks_export,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path


def import_snapshot(store: GraphStore, source_path: Path) -> Dict[str, int]:
    """Hydrate GraphStore from a portable JSON snapshot without losing provenance."""
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    for k, v in (raw.get("project_meta") or {}).items():
        store.set_meta(str(k), v)
    nodes = raw.get("nodes") or []
    for nd in nodes:
        store.upsert_node(
            MemoryNode(
                id=nd["id"],
                node_type=nd["node_type"],
                title=nd["title"],
                status=nd.get("status", "ACTIVE"),
                summary=nd.get("summary", ""),
                content=nd.get("content", ""),
                metadata=nd.get("metadata") or {},
                file_path=nd.get("file_path", ""),
                tags=nd.get("tags") or [],
                priority=int(nd.get("priority", 50)),
                created_at=nd.get("created_at", utc_now_iso()),
                updated_at=nd.get("updated_at", utc_now_iso()),
            ),
            log_event=False,
        )
    edges = raw.get("edges") or []
    for ed in edges:
        store.add_edge(
            MemoryEdge(
                source_id=ed["source_id"],
                target_id=ed["target_id"],
                relation=ed["relation"],
                weight=float(ed.get("weight", 1.0)),
                metadata=ed.get("metadata") or {},
                created_at=ed.get("created_at", utc_now_iso()),
            )
        )
    gates = raw.get("gates") or []
    for gt in gates:
        store.upsert_gate(
            CodeGate(
                id=gt["id"],
                gate_type=gt["gate_type"],
                name=gt["name"],
                law_id=gt.get("law_id", ""),
                lesson_id=gt.get("lesson_id", ""),
                target_glob=gt.get("target_glob", "**/*"),
                pattern=gt.get("pattern", ""),
                config=gt.get("config") or {},
                enabled=bool(gt.get("enabled", True)),
                blocked_count=int(gt.get("blocked_count", 0)),
                last_blocked_at=gt.get("last_blocked_at"),
                created_at=gt.get("created_at", utc_now_iso()),
            )
        )
    exps = raw.get("experiments") or []
    for ex in exps:
        store.upsert_experiment(
            ExperimentRecord(
                exp_id=ex["exp_id"],
                track=ex["track"],
                title=ex["title"],
                hypothesis=ex["hypothesis"],
                single_var_diff=ex["single_var_diff"],
                model_stack=ex.get("model_stack", ""),
                baseline_id=ex.get("baseline_id", ""),
                proposal_id=ex.get("proposal_id", ""),
                cv_score=ex.get("cv_score"),
                cv_summary=ex.get("cv_summary", ""),
                test_score=ex.get("test_score"),
                test_summary=ex.get("test_summary", ""),
                delta_vs_baseline=ex.get("delta_vs_baseline"),
                runtime_summary=ex.get("runtime_summary", ""),
                verdict=ex.get("verdict", "PENDING"),
                leakage_audit=ex.get("leakage_audit", "CLEAN"),
                post_mortem=ex.get("post_mortem", ""),
                log_path=ex.get("log_path", ""),
                metadata=ex.get("metadata") or {},
                created_at=ex.get("created_at", utc_now_iso()),
            )
        )
    for tk in raw.get("agent_tasks") or []:
        now = utc_now_iso()
        store.conn.execute(
            "INSERT INTO agent_tasks(task_id, wave, role, title, brief, status, depends_on_json, "
            "locked_globs_json, target_id, claimed_by, smoke_gate, receipt_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(task_id) DO UPDATE SET status=excluded.status, claimed_by=excluded.claimed_by, "
            "receipt_json=excluded.receipt_json, updated_at=excluded.updated_at",
            (
                tk["task_id"], int(tk.get("wave", 1)), tk.get("role", "self"), tk["title"],
                tk.get("brief", ""), tk.get("status", "QUEUED"),
                json.dumps(tk.get("depends_on") or [], ensure_ascii=False),
                json.dumps(tk.get("locked_globs") or [], ensure_ascii=False),
                tk.get("target_id", ""), tk.get("claimed_by", ""), tk.get("smoke_gate", ""),
                json.dumps(tk.get("receipt") or {}, ensure_ascii=False),
                tk.get("created_at", now), tk.get("updated_at", now),
            ),
        )
    store.conn.commit()
    store.log_event("SNAPSHOT_IMPORT", str(source_path.name), f"Hydrated {len(nodes)} nodes, {len(edges)} edges")
    return {"nodes": len(nodes), "edges": len(edges), "gates": len(gates), "experiments": len(exps)}


def get_session_state(store: GraphStore, conversation_id: str) -> Dict[str, Any]:
    """Read or initialize hook session tracking state for a conversation."""
    row = store.conn.execute(
        "SELECT * FROM session_state WHERE conversation_id = ?", (conversation_id,)
    ).fetchone()
    if not row:
        now = utc_now_iso()
        store.conn.execute(
            "INSERT INTO session_state(conversation_id, updated_at) VALUES (?, ?)",
            (conversation_id, now),
        )
        store.conn.commit()
        return {
            "conversation_id": conversation_id,
            "invocation_num": 0,
            "last_step_idx": 0,
            "pending_lesson_lock": False,
            "pending_lesson_quote": "",
            "pending_lesson_category": "",
            "dirty_files": [],
            "unlogged_exp_cmds": [],
            "turn_memory_handled": False,
            "research_campaign_active": False,
            "last_heartbeat_bucket": 0,
            "last_seen_user_input": "",
            "pending_sync_reason": "",
            "compaction_count": 0,
        }
    raw_extra = str(row["unlogged_exp_cmds_json"] or "[]").strip()
    extra_obj = json.loads(raw_extra) if raw_extra.startswith("{") else {"cmds": json.loads(raw_extra or "[]")}
    return {
        "conversation_id": str(row["conversation_id"]),
        "invocation_num": int(row["invocation_num"]),
        "last_step_idx": int(row["last_step_idx"]),
        "pending_lesson_lock": bool(row["pending_lesson_lock"]),
        "pending_lesson_quote": str(row["pending_lesson_quote"]),
        "pending_lesson_category": str(row["pending_lesson_category"]),
        "dirty_files": json.loads(row["dirty_files_json"] or "[]"),
        "unlogged_exp_cmds": list(extra_obj.get("cmds") or []),
        "turn_memory_handled": bool(extra_obj.get("turn_memory_handled", False)),
        "research_campaign_active": bool(extra_obj.get("research_campaign_active", False)),
        "last_heartbeat_bucket": int(extra_obj.get("last_heartbeat_bucket", 0)),
        "last_seen_user_input": str(extra_obj.get("last_seen_user_input") or ""),
        "pending_sync_reason": str(extra_obj.get("pending_sync_reason") or ""),
        "compaction_count": int(row["compaction_count"]),
    }


def save_session_state(store: GraphStore, state: Dict[str, Any]) -> None:
    """Persist hook session tracking state atomically."""
    extra_envelope = {
        "cmds": list(state.get("unlogged_exp_cmds") or []),
        "turn_memory_handled": bool(state.get("turn_memory_handled", False)),
        "research_campaign_active": bool(state.get("research_campaign_active", False)),
        "last_heartbeat_bucket": int(state.get("last_heartbeat_bucket", 0)),
        "last_seen_user_input": str(state.get("last_seen_user_input") or ""),
        "pending_sync_reason": str(state.get("pending_sync_reason") or ""),
    }
    store.conn.execute(
        """
        INSERT INTO session_state(conversation_id, invocation_num, last_step_idx,
            pending_lesson_lock, pending_lesson_quote, pending_lesson_category,
            dirty_files_json, unlogged_exp_cmds_json, compaction_count, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(conversation_id) DO UPDATE SET
            invocation_num=excluded.invocation_num, last_step_idx=excluded.last_step_idx,
            pending_lesson_lock=excluded.pending_lesson_lock,
            pending_lesson_quote=excluded.pending_lesson_quote,
            pending_lesson_category=excluded.pending_lesson_category,
            dirty_files_json=excluded.dirty_files_json,
            unlogged_exp_cmds_json=excluded.unlogged_exp_cmds_json,
            compaction_count=excluded.compaction_count, updated_at=excluded.updated_at
        """,
        (
            state["conversation_id"],
            int(state.get("invocation_num", 0)),
            int(state.get("last_step_idx", 0)),
            int(bool(state.get("pending_lesson_lock", False))),
            str(state.get("pending_lesson_quote", "")),
            str(state.get("pending_lesson_category", "")),
            json.dumps(state.get("dirty_files") or [], ensure_ascii=False),
            json.dumps(extra_envelope, ensure_ascii=False),
            int(state.get("compaction_count", 0)),
            utc_now_iso(),
        ),
    )
    store.conn.commit()


def mark_turn_memory_handled(store: GraphStore, clear_lesson_lock: bool = False) -> None:
    """Mark all active conversation sessions in this store as having persisted/attested memory."""
    rows = store.conn.execute("SELECT conversation_id FROM session_state").fetchall()
    for r in rows:
        st = get_session_state(store, str(r["conversation_id"]))
        st["turn_memory_handled"] = True
        st["dirty_files"] = []
        st["pending_sync_reason"] = ""
        if clear_lesson_lock:
            st["pending_lesson_lock"] = False
        save_session_state(store, st)
