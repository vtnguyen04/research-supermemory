"""Atomic 1-Call Turn Sync (`checkpoint`) & Kanban Kernel Helpers for Zero-Reminder Memory."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from supermemory.cognitive.curator_engine import check_curation_pressure
from supermemory.graph.auto_linker import find_near_duplicate_insights, wire_contextual_edges
from supermemory.graph.supersession import apply_supersedes_links
from supermemory.lifecycle.manager import LifecycleManager
from supermemory.lifecycle.validators import assert_all_steps_completed, validate_insight_schema
from supermemory.models import MemoryNode, MemoryTier, NodeType, utc_now_iso
from supermemory.research.kanban_ops import (
    add_subtask,
    delete_task,
    extract_task_steps,
    move_task_stage,
    toggle_subtask,
)
from supermemory.research.orchestrator import _row_to_task, enqueue_task
from supermemory.storage.snapshot_io import get_session_state, mark_turn_memory_handled
from supermemory.storage.sqlite_store import GraphStore
from supermemory.sync.markdown_compiler import MarkdownCompiler

_PROP_STAGE_ALIAS = {
    "BACKLOG": "PROPOSED",
    "READY": "DESIGNED",
    "IN_PROGRESS": "IMPLEMENTING",
    "RUNNING": "IMPLEMENTING",
    "DONE": "AUDITED",
}


def _mint_insight_node(
    store: GraphStore,
    title: str,
    summary: str,
    tier: str = "SEMANTIC",
    note: str = "",
    context_ids: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    t_clean = title.strip()[:160]
    s_clean = (summary or title).strip()
    validate_insight_schema(t_clean, s_clean)
    tier_up = "PROCEDURAL" if tier.strip().upper() == "PROCEDURAL" else MemoryTier.SEMANTIC.value
    ntype = NodeType.PROCEDURE.value if tier_up == "PROCEDURAL" else NodeType.OBSERVATION.value
    pref = "PROC" if tier_up == "PROCEDURAL" else "OBS"

    existing = store.list_nodes(node_types=[ntype], limit=5000)
    for ex in existing:
        if ex.title.strip().lower() == t_clean.lower() and ex.summary.strip().lower() == s_clean[:240].strip().lower():
            wire_contextual_edges(store, ex.id, f"{t_clean} {s_clean} {note}", context_ids=context_ids)
            return ex.to_dict()

    related_obs = find_near_duplicate_insights(store, t_clean, s_clean) if ntype == NodeType.OBSERVATION.value else []
    nums = [int(m.group(1)) for x in existing for m in [re.match(rf"^{pref}-(\d+)$", x.id)] if m]
    nid = f"{pref}-{(max(nums) + 1) if nums else 1:03d}"
    kn_dir = store.mem_dir / "06_KNOWLEDGE_NODES"
    kn_dir.mkdir(parents=True, exist_ok=True)
    rel_path = f"memory/06_KNOWLEDGE_NODES/{nid}.md"
    md = f"# {nid}: {t_clean}\n\n- **Captured At:** `{utc_now_iso()}`\n- **Tier:** `{tier_up}`\n\n{s_clean}\n"
    (store.workspace_root / rel_path).write_text(md, encoding="utf-8")

    nd = store.upsert_node(
        MemoryNode(
            id=nid,
            node_type=ntype,
            title=t_clean,
            status="SCIENTIFIC_INSIGHT" if ntype == NodeType.OBSERVATION.value else "ACTIVE",
            summary=s_clean[:240],
            content=s_clean,
            file_path=rel_path,
            tags=["auto-insight", tier_up.lower()],
            priority=88,
            metadata={"memory_tier": tier_up, "note": note, "related_candidates": related_obs},
        )
    )
    wire_contextual_edges(store, nid, f"{t_clean} {s_clean} {note}", context_ids=context_ids)
    return nd.to_dict()


def execute_atomic_checkpoint(store: GraphStore, args: Dict[str, Any]) -> Dict[str, Any]:
    """Persist insights, Kanban task/subtask progress, and L0 state in one atomic call."""
    captured_insights: List[Dict[str, Any]] = []
    mutated = False
    tier = str(args.get("memory_tier") or MemoryTier.SEMANTIC.value)
    note = str(args.get("note") or "")
    ctx_ids = [
        str(u.get("id") or u.get("item_id") or "").strip()
        for u in (args.get("task_updates") or [])
        if isinstance(u, dict) and str(u.get("id") or u.get("item_id") or "").strip()
    ]

    if args.get("insight_title") and args.get("insight_summary"):
        captured_insights.append(
            _mint_insight_node(
                store, str(args["insight_title"]), str(args["insight_summary"]), tier=tier, note=note, context_ids=ctx_ids
            )
        )
        mutated = True

    for raw_ins in args.get("insights") or []:
        txt = str(raw_ins or "").strip()
        if not txt:
            continue
        head = txt.split(":", 1)[0].strip() if ":" in txt[:90] else txt[:84]
        captured_insights.append(_mint_insight_node(store, head, txt, tier=tier, note=note, context_ids=ctx_ids))
        mutated = True

    raw_sup = args.get("supersedes") or []
    sup_list = [s.strip() for s in raw_sup.split(",") if s.strip()] if isinstance(raw_sup, str) else [str(s).strip() for s in raw_sup if str(s).strip()]
    superseded_ids: List[str] = []
    related_candidates = list(
        dict.fromkeys(sid for item in captured_insights for sid in ((item.get("metadata") or {}).get("related_candidates") or []))
    )
    if sup_list and captured_insights:
        superseded_ids.extend(apply_supersedes_links(store, [str(x["id"]) for x in captured_insights], sup_list))
        mutated = True

    created_task = None
    new_task = args.get("new_task")
    if isinstance(new_task, dict) and str(new_task.get("title") or "").strip():
        raw_steps = new_task.get("steps")
        steps = [str(s).strip() for s in raw_steps if str(s).strip()] if isinstance(raw_steps, list) else None
        t_obj = enqueue_task(
            store,
            role=str(new_task.get("role") or "self"),
            title=str(new_task["title"]).strip(),
            brief=str(new_task.get("brief") or note),
            steps=steps,
        )
        tgt_stage = str(new_task.get("stage") or "IN_PROGRESS").strip().upper()
        if tgt_stage in ("IN_PROGRESS", "RUNNING", "DONE"):
            created_task = move_task_stage(store, t_obj.task_id, tgt_stage, agent_name="agent").get("task")
        else:
            created_task = t_obj.to_dict()
        mutated = True

    applied_tasks: List[Dict[str, Any]] = []
    for upd in args.get("task_updates") or []:
        if not isinstance(upd, dict):
            continue
        iid = str(upd.get("id") or upd.get("item_id") or "").strip()
        if not iid:
            continue
        kind = "PROPOSAL" if iid.upper().startswith("PROP-") else str(upd.get("kind") or "TASK").upper()
        for step_txt in upd.get("add_steps") or []:
            if str(step_txt).strip():
                add_subtask(store, kind, iid, str(step_txt).strip())
        for s_idx in upd.get("done_steps") or []:
            toggle_subtask(store, kind, iid, int(s_idx), done=True)
        if upd.get("stage"):
            raw_st = str(upd["stage"]).strip().upper()
            if kind == "PROPOSAL":
                mapped = _PROP_STAGE_ALIAS.get(raw_st, raw_st)
                LifecycleManager(store).advance_proposal(iid, mapped, note)
            else:
                if raw_st == "DONE":
                    row = store.conn.execute("SELECT * FROM agent_tasks WHERE task_id = ?", (iid,)).fetchone()
                    if row:
                        t_steps = extract_task_steps(_row_to_task(row).to_dict())
                        assert_all_steps_completed(iid, [s["text"] for s in t_steps], [bool(s["done"]) for s in t_steps])
                move_task_stage(store, iid, raw_st, agent_name="agent")
        applied_tasks.append({"id": iid, "kind": kind})
        mutated = True

    meta_changed = []
    for meta_key in ("active_goal", "current_phase", "next_actions"):
        if args.get(meta_key) is not None and str(args[meta_key]).strip():
            store.set_meta(meta_key, str(args[meta_key]).strip())
            meta_changed.append(meta_key)
            mutated = True

    if not mutated and str(args.get("status") or "").upper() == "CLEAN":
        s_rows = store.conn.execute("SELECT conversation_id FROM session_state").fetchall()
        dirty_all = [
            f
            for r in s_rows
            for f in (get_session_state(store, str(r["conversation_id"])).get("dirty_files") or [])
        ]
        if dirty_all:
            shown = ", ".join(dict.fromkeys(dirty_all))[:120]
            raise ValueError(
                f"LAW-07 Dirty-Edit Sync Gate: Cannot attest empty `status='CLEAN'` while workspace source files were modified (`{shown}`). "
                "Include at least one concrete `insights=['Title: what changed & why']` or `task_updates=[...]` (or call `log_experiment`)."
            )

    if meta_changed and not (captured_insights or created_task or applied_tasks):
        store.log_event("CHECKPOINT_SYNCED", "L0_STATE", f"Synced L0 state ({', '.join(meta_changed)}){': ' + note[:80] if note else ''}")
    if mutated:
        MarkdownCompiler(store).compile_all()
    kanban_touched = bool(created_task or applied_tasks or str(args.get("status") or "").upper() == "CLEAN")
    mark_turn_memory_handled(store, clear_kanban_sync=kanban_touched)
    out: Dict[str, Any] = {
        "status": "CAPTURED" if mutated else str(args.get("status") or "CLEAN"),
        "turn_memory_handled": True,
        "captured": captured_insights[0] if len(captured_insights) == 1 else captured_insights or None,
        "superseded_ids": superseded_ids,
        "created_task": created_task,
        "updated_tasks": applied_tasks,
    }
    if related_candidates:
        out["related_existing_insights"] = related_candidates
    if mutated:
        curation = check_curation_pressure(store)
        if curation["needs_curation"]:
            out["curation_needed"] = curation
    if captured_insights and any(re.search(r"[+-]\d+\.\d+%|\b0\.\d{3,}\b", str(c.get("summary") or "")) for c in captured_insights):
        out["experiment_reminder"] = (
            "If this insight came from a quantitative benchmark/ablation run (KEEP or DISCARD), "
            "ensure it is also logged in `log_experiment` so `03_EXPERIMENTS_REGISTRY.md` & SOTA tracking stay complete."
        )
    return out


def execute_kanban_orchestrate_ext(act: str, store: GraphStore, args: Dict[str, Any]) -> Dict[str, Any] | None:
    """Handle Kanban actions (`move`, `toggle_step`, `add_step`, `delete`) inside Kernel `orchestrate`."""
    if act == "move":
        return move_task_stage(
            store,
            task_id=str(args["task_id"]).strip(),
            target_stage=str(args.get("target_stage") or args.get("status") or "IN_PROGRESS"),
            agent_name=str(args.get("agent_name") or "agent"),
        )
    if act == "toggle_step":
        iid = str(args.get("item_id") or args.get("task_id") or "").strip()
        kind = "PROPOSAL" if iid.upper().startswith("PROP-") else str(args.get("kind") or "TASK")
        done_v = args.get("done")
        return toggle_subtask(store, kind, iid, int(args["step_idx"]), done=bool(done_v) if done_v is not None else None)
    if act == "add_step":
        iid = str(args.get("item_id") or args.get("task_id") or "").strip()
        kind = "PROPOSAL" if iid.upper().startswith("PROP-") else str(args.get("kind") or "TASK")
        return add_subtask(store, kind, iid, str(args["text"]).strip())
    if act == "delete":
        deleted = delete_task(store, str(args["task_id"]).strip())
        MarkdownCompiler(store).compile_all()
        return {"deleted": deleted}
    return None
