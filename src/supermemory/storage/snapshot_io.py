"""Portable Git-friendly JSON snapshot export/import & session state helpers."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from supermemory.models import CodeGate, ExperimentRecord, MemoryEdge, MemoryNode, NodeType, utc_now_iso

if TYPE_CHECKING:
    from supermemory.storage.sqlite_store import GraphStore


def _serialize_node_for_snapshot(n: MemoryNode) -> Dict[str, Any]:
    d = n.to_dict()
    if n.node_type == NodeType.AGENT_RUN.value and len(d.get("content") or "") > 600:
        d["content"] = str(d["content"])[:600]
    return d


def export_snapshot(store: GraphStore, target_path: Path | None = None) -> Path:
    """Export deterministic compact JSON snapshot of the Knowledge Graph."""
    out_path = target_path or store.snapshot_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    task_rows = store.conn.execute("SELECT * FROM agent_tasks ORDER BY wave ASC, task_id ASC").fetchall()
    tasks_export = [
        {
            "task_id": str(r["task_id"]), "wave": int(r["wave"]), "role": str(r["role"]),
            "title": str(r["title"]), "brief": str(r["brief"]), "status": str(r["status"]),
            "depends_on": json.loads(str(r["depends_on_json"] or "[]")),
            "locked_globs": json.loads(str(r["locked_globs_json"] or "[]")),
            "target_id": str(r["target_id"] or ""), "claimed_by": str(r["claimed_by"] or ""),
            "smoke_gate": str(r["smoke_gate"] or ""), "receipt": json.loads(str(r["receipt_json"] or "{}")),
            "created_at": str(r["created_at"]), "updated_at": str(r["updated_at"]),
        }
        for r in task_rows
    ]
    payload = {
        "schema_version": "3.0.0",
        "project_meta": store.get_all_meta(),
        "nodes": [_serialize_node_for_snapshot(n) for n in store.list_nodes(limit=10000)],
        "edges": [e.to_dict() for e in store.list_edges()],
        "gates": [g.to_dict() for g in store.list_gates()],
        "experiments": [x.to_dict() for x in store.list_experiments()],
        "agent_tasks": tasks_export,
        "events": store.list_events(limit=80),
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return out_path


def import_snapshot(store: GraphStore, source_path: Path) -> Dict[str, int]:
    """Hydrate GraphStore from a portable JSON snapshot without losing provenance."""
    raw = json.loads(source_path.read_text(encoding="utf-8"))
    for k, v in (raw.get("project_meta") or {}).items():
        store.set_meta(str(k), v)
    nodes = raw.get("nodes") or []
    for nd in nodes:
        rel_fp = str(nd.get("file_path") or "")
        body = str(nd.get("content") or "")
        store.upsert_node(
            MemoryNode(
                id=nd["id"], node_type=nd["node_type"], title=nd["title"],
                status=nd.get("status", "ACTIVE"), summary=nd.get("summary", ""), content=body,
                metadata=nd.get("metadata") or {}, file_path=rel_fp, tags=nd.get("tags") or [],
                priority=int(nd.get("priority", 50)),
                created_at=nd.get("created_at", utc_now_iso()), updated_at=nd.get("updated_at", utc_now_iso()),
            ),
            log_event=False,
        )
    edges = raw.get("edges") or []
    for ed in edges:
        store.add_edge(
            MemoryEdge(
                source_id=ed["source_id"], target_id=ed["target_id"], relation=ed["relation"],
                weight=float(ed.get("weight", 1.0)), metadata=ed.get("metadata") or {},
                created_at=ed.get("created_at", utc_now_iso()),
            )
        )
    gates = raw.get("gates") or []
    for gt in gates:
        store.upsert_gate(
            CodeGate(
                id=gt["id"], gate_type=gt["gate_type"], name=gt["name"],
                law_id=gt.get("law_id", ""), lesson_id=gt.get("lesson_id", ""),
                target_glob=gt.get("target_glob", "**/*"), pattern=gt.get("pattern", ""),
                config=gt.get("config") or {}, enabled=bool(gt.get("enabled", True)),
                blocked_count=int(gt.get("blocked_count", 0)), last_blocked_at=gt.get("last_blocked_at"),
                created_at=gt.get("created_at", utc_now_iso()),
            )
        )
    exps = raw.get("experiments") or []
    for ex in exps:
        store.upsert_experiment(
            ExperimentRecord(
                exp_id=ex["exp_id"], track=ex["track"], title=ex["title"],
                hypothesis=ex["hypothesis"], single_var_diff=ex["single_var_diff"],
                model_stack=ex.get("model_stack", ""), baseline_id=ex.get("baseline_id", ""),
                proposal_id=ex.get("proposal_id", ""), cv_score=ex.get("cv_score"),
                cv_summary=ex.get("cv_summary", ""), test_score=ex.get("test_score"),
                test_summary=ex.get("test_summary", ""), delta_vs_baseline=ex.get("delta_vs_baseline"),
                runtime_summary=ex.get("runtime_summary", ""), verdict=ex.get("verdict", "PENDING"),
                leakage_audit=ex.get("leakage_audit", "CLEAN"), post_mortem=ex.get("post_mortem", ""),
                log_path=ex.get("log_path", ""), metadata=ex.get("metadata") or {},
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
    existing_ev_cnt = int(store.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])
    if existing_ev_cnt == 0 and raw.get("events"):
        for ev in reversed(list(raw.get("events") or [])):
            store.conn.execute(
                "INSERT INTO events(event_type, actor, entity_id, summary, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    str(ev.get("event_type") or "EVENT"),
                    str(ev.get("actor") or "supermemory"),
                    str(ev.get("entity_id") or ""),
                    str(ev.get("summary") or ""),
                    str(ev.get("payload_json") or "{}"),
                    str(ev.get("created_at") or utc_now_iso()),
                ),
            )
    store.conn.commit()
    store.log_event("SNAPSHOT_IMPORT", str(source_path.name), f"Hydrated {len(nodes)} nodes, {len(edges)} edges")
    return {"nodes": len(nodes), "edges": len(edges), "gates": len(gates), "experiments": len(exps)}


_EXTRA_DEFAULTS: Dict[str, Any] = {
    "turn_memory_handled": False, "research_campaign_active": False, "last_heartbeat_bucket": 0,
    "last_seen_user_input": "", "pending_sync_reason": "", "pending_kanban_sync": False,
    "last_kanban_fp": "", "last_kanban_inv": 0, "recalled_node_ids": [], "recalled_warnings": [],
    "notified_edit": False, "notified_exec": False, "notified_research": False,
    "unsynced_work_steps": 0, "pending_notifications": [], "last_compaction_marker": "",
    "last_capsule_step": 0, "last_capsule_inv": 0, "last_read_mem": "",
    "last_wakeup_marker": "", "stop_block_streak": 0, "compaction_recall_pending": False,
    "compaction_gate_strikes": 0, "grounded_compaction_marker": "", "strike_compaction_marker": "",
    "ground_next_tail_marker": False,
}


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
        base: Dict[str, Any] = {
            "conversation_id": conversation_id, "invocation_num": 0, "last_step_idx": 0,
            "pending_lesson_lock": False, "pending_lesson_quote": "", "pending_lesson_category": "",
            "dirty_files": [], "unlogged_exp_cmds": [], "compaction_count": 0,
        }
        for k, v in _EXTRA_DEFAULTS.items():
            base[k] = list(v) if isinstance(v, list) else v
        return base

    raw_extra = str(row["unlogged_exp_cmds_json"] or "[]").strip()
    extra_obj = json.loads(raw_extra) if raw_extra.startswith("{") else {"cmds": json.loads(raw_extra or "[]")}
    out: Dict[str, Any] = {
        "conversation_id": str(row["conversation_id"]), "invocation_num": int(row["invocation_num"]),
        "last_step_idx": int(row["last_step_idx"]), "pending_lesson_lock": bool(row["pending_lesson_lock"]),
        "pending_lesson_quote": str(row["pending_lesson_quote"]), "pending_lesson_category": str(row["pending_lesson_category"]),
        "dirty_files": json.loads(row["dirty_files_json"] or "[]"),
        "unlogged_exp_cmds": list(extra_obj.get("cmds") or []), "compaction_count": int(row["compaction_count"]),
    }
    for k, dv in _EXTRA_DEFAULTS.items():
        val = extra_obj.get(k, dv)
        if isinstance(dv, list):
            out[k] = list(val or [])
        elif isinstance(dv, bool):
            out[k] = bool(val)
        elif isinstance(dv, int):
            out[k] = int(val or 0)
        else:
            out[k] = str(val or "")
    return out


def save_session_state(store: GraphStore, state: Dict[str, Any], commit: bool = True) -> None:
    """Persist hook session tracking state atomically."""
    extra_envelope: Dict[str, Any] = {"cmds": list(state.get("unlogged_exp_cmds") or [])}
    for k, dv in _EXTRA_DEFAULTS.items():
        val = state.get(k, dv)
        extra_envelope[k] = list(val or []) if isinstance(dv, list) else val
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
    if commit:
        store.conn.commit()


def mark_turn_memory_handled(
    store: GraphStore,
    clear_lesson_lock: bool = False,
    clear_kanban_sync: bool = False,
    include_dirty: bool = True,
) -> None:
    """Mark recently active main sessions as handled (`1` commit, pruning >24h zombie rows & preserving dirty_files on background curation)."""
    now = datetime.now(timezone.utc)
    stale_cut = (now - timedelta(hours=24)).replace(microsecond=0).isoformat()
    active_cut = (now - timedelta(minutes=45)).replace(microsecond=0).isoformat()
    store.conn.execute("DELETE FROM session_state WHERE updated_at < ?", (stale_cut,))
    rows = store.conn.execute(
        "SELECT conversation_id FROM session_state WHERE updated_at >= ? ORDER BY updated_at DESC LIMIT 6",
        (active_cut,),
    ).fetchall()
    for r in rows:
        st = get_session_state(store, str(r["conversation_id"]))
        st["turn_memory_handled"] = True
        st["stop_block_streak"] = 0
        st["compaction_recall_pending"] = False
        st["compaction_gate_strikes"] = 0
        st["ground_next_tail_marker"] = True
        if st.get("last_compaction_marker") and st["last_compaction_marker"] != "NONE":
            st["grounded_compaction_marker"] = st["last_compaction_marker"]
        if include_dirty:
            st["dirty_files"] = []
        st["pending_sync_reason"] = ""
        st["unsynced_work_steps"] = 0
        st["pending_notifications"] = []
        if clear_lesson_lock:
            st["pending_lesson_lock"] = False
        if clear_kanban_sync:
            st["pending_kanban_sync"] = False
        save_session_state(store, st, commit=False)
    store.conn.commit()


def mark_active_sessions_compaction_grounded(store: GraphStore) -> None:
    """Mark active sessions (`<=45m`) as post-compaction grounded directly from inward kernel `recall`/`status`."""
    active_cut = (datetime.now(timezone.utc) - timedelta(minutes=45)).replace(microsecond=0).isoformat()
    rows = store.conn.execute(
        "SELECT conversation_id FROM session_state WHERE updated_at >= ? ORDER BY updated_at DESC LIMIT 6",
        (active_cut,),
    ).fetchall()
    if not rows:
        return
    for r in rows:
        st = get_session_state(store, str(r["conversation_id"]))
        st["compaction_recall_pending"] = False
        st["compaction_gate_strikes"] = 0
        st["ground_next_tail_marker"] = True
        if st.get("last_compaction_marker") and st["last_compaction_marker"] != "NONE":
            st["grounded_compaction_marker"] = st["last_compaction_marker"]
            st["strike_compaction_marker"] = st["last_compaction_marker"]
        save_session_state(store, st, commit=False)
    store.conn.commit()
