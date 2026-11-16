"""Kanban Board Transitions, Granular Subtask Checklists & Unified Execution Telemetry."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from supermemory.models import NodeType, utc_now_iso
from supermemory.research.orchestrator import _globs_conflict, _row_to_task, complete_task, list_tasks
from supermemory.storage.sqlite_store import GraphStore

ROLE_DEFAULT_STEPS: Dict[str, List[str]] = {
    "bottleneck-profiler": [
        "Decompose validation slice metrics",
        "Quantify Pareto error share & ceiling gain",
        "Register BNK-XXX + falsifiable RQ-XXX",
    ],
    "sota-scout": [
        "Query arXiv / Semantic Scholar / OpenAlex",
        "Filter candidate mechanisms for target BNK",
        "Mint METH-XXX cards with integration hooks",
    ],
    "memory-curator": [
        "Run hybrid recall across Local + Sibling vaults",
        "Verify zero dead-end mechanism collisions",
        "Sync compact L0 active state",
    ],
    "hypothesis-architect": [
        "Rank METH-XXX candidates by Occam ROI",
        "Isolate strictly 1 variable (coupled_vars=1)",
        "Define 10% smoke-budget early-kill gate",
    ],
    "experiment-challenger": [
        "Audit train/val/test split isolation",
        "Verify single-variable diff & BNK-XXX link",
        "Record adversarial red-team verdict",
    ],
    "slice-builder": [
        "Acquire conflict-free file-glob lease",
        "Implement <300L slice & pass 10% smoke gate",
        "Pass full test suite & log_experiment",
    ],
}
FALLBACK_STEPS = [
    "Scope requirements & verify dependencies",
    "Execute implementation / analysis",
    "Verify outputs & record handoff receipt",
]
DONE_STATUSES = {"DONE", "FAILED", "EARLY_KILLED", "CANCELLED_BY_KILL_GATE", "SKIPPED"}


def default_steps_for_role(role: str) -> List[str]:
    """Return concrete 3-step execution checklist for a specialist agent role."""
    return list(ROLE_DEFAULT_STEPS.get(role.strip(), FALLBACK_STEPS))


def extract_task_steps(task_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract normalized subtask checklist items from task receipt or role defaults."""
    rec = task_dict.get("receipt") if isinstance(task_dict.get("receipt"), dict) else {}
    raw = rec.get("steps") if isinstance(rec, dict) else None
    is_done = str(task_dict.get("status") or "").upper() == "DONE"
    if isinstance(raw, list) and raw:
        out = [
            {"text": str(s.get("text") if isinstance(s, dict) else s).strip()[:260], "done": True if is_done else (bool(s.get("done", False)) if isinstance(s, dict) else False)}
            for s in raw[:16]
        ]
        out = [x for x in out if x["text"]]
        if out:
            return out
    return [{"text": s, "done": is_done} for s in default_steps_for_role(str(task_dict.get("role") or ""))]


def _compute_pct(status: str, steps: List[Dict[str, Any]]) -> int:
    st = status.upper()
    if st == "DONE":
        return 100
    done_cnt = sum(1 for s in steps if s.get("done"))
    base = round((done_cnt / len(steps)) * 100) if steps else 0
    return 15 if (st == "RUNNING" and base == 0) else min(100, max(0, base))


def enrich_execution_state(tasks: List[Dict[str, Any]], ready_ids: List[str], nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Enrich tasks & proposals with subtask progress, Kanban column, and sprint KPIs."""
    ready_set = set(ready_ids)
    counts = {"BACKLOG": 0, "READY": 0, "IN_PROGRESS": 0, "DONE": 0, "HALTED": 0}
    sub_done, sub_total, pct_sum, total_items = 0, 0, 0, 0
    workers = set()

    for t in tasks:
        st = str(t.get("status") or "QUEUED").upper()
        steps = extract_task_steps(t)
        s_done = sum(1 for s in steps if s.get("done"))
        pct = _compute_pct(st, steps)
        if st == "RUNNING":
            col = "IN_PROGRESS"
            if t.get("claimed_by"):
                workers.add(str(t["claimed_by"]))
        elif st in DONE_STATUSES:
            col = "DONE"
            if st != "DONE":
                counts["HALTED"] += 1
        elif str(t.get("task_id")) in ready_set:
            col = "READY"
        else:
            col = "BACKLOG"
        counts[col] += 1
        t.update({"steps": steps, "steps_done": s_done, "steps_total": len(steps), "progress_pct": pct, "kanban_col": col})
        sub_done += s_done
        sub_total += len(steps)
        pct_sum += pct
        total_items += 1

    for n in nodes:
        if n.get("node_type") != NodeType.PROPOSAL.value:
            continue
        meta = n.setdefault("metadata", {})
        raw_tasks = [str(x).strip() for x in (meta.get("tasks") or []) if str(x).strip()]
        st = str(n.get("status") or "PROPOSED").upper()
        finished = st in ("AUDITED", "ARCHIVED")
        raw_done = list(meta.get("tasks_done") or [])
        norm_done = [True if finished else (bool(raw_done[i]) if i < len(raw_done) else False) for i in range(len(raw_tasks))]
        meta["tasks_done"] = norm_done
        s_done = sum(1 for d in norm_done if d)
        ratio_pct = round((s_done / len(raw_tasks)) * 100) if raw_tasks else 0
        if finished:
            pct, col = 100, "DONE"
        elif st in ("IMPLEMENTING", "CHALLENGED"):
            pct, col = (ratio_pct if raw_tasks else 55), "IN_PROGRESS"
        elif st == "DESIGNED":
            pct, col = (ratio_pct if raw_tasks else 25), "READY"
        else:
            pct, col = ratio_pct, "BACKLOG"
        meta.update({"progress_pct": pct, "kanban_col": col})
        if st == "ARCHIVED":
            continue
        counts[col] += 1
        sub_done += s_done
        sub_total += len(raw_tasks)
        pct_sum += pct
        total_items += 1

    return {
        "total_items": total_items,
        "backlog_count": counts["BACKLOG"],
        "ready_count": counts["READY"],
        "in_progress_count": counts["IN_PROGRESS"],
        "done_count": counts["DONE"],
        "halted_count": counts["HALTED"],
        "subtasks_done": sub_done,
        "subtasks_total": sub_total,
        "overall_pct": round(pct_sum / total_items) if total_items > 0 else 0,
        "active_workers": sorted(workers),
    }


def move_task_stage(store: GraphStore, task_id: str, target_stage: str, agent_name: str = "studio") -> Dict[str, Any]:
    """Transition a DAG task to any Kanban column or lifecycle status."""
    row = store.conn.execute("SELECT * FROM agent_tasks WHERE task_id = ?", (task_id,)).fetchone()
    if not row:
        raise ValueError(f"Task `{task_id}` not found.")
    task = _row_to_task(row)
    tgt, now = target_stage.strip().upper(), utc_now_iso()

    if tgt in ("BACKLOG", "READY", "QUEUED"):
        rec = dict(task.receipt or {})
        if isinstance(rec.get("steps"), list) and task.status == "DONE":
            rec["steps"] = [{"text": str(s.get("text", "")), "done": False} for s in rec["steps"] if isinstance(s, dict)]
        store.conn.execute(
            "UPDATE agent_tasks SET status='QUEUED', claimed_by='', receipt_json=?, updated_at=? WHERE task_id=?",
            (json.dumps(rec, ensure_ascii=False), now, task_id),
        )
        store.conn.commit()
        store.log_event("DAG_TASK_MOVED", task_id, f"{task_id} -> QUEUED")
    elif tgt in ("IN_PROGRESS", "RUNNING"):
        running_globs = [g for t in list_tasks(store, status="RUNNING") if t.task_id != task_id for g in t.locked_globs]
        if _globs_conflict(task.locked_globs, running_globs):
            raise ValueError(f"Glob lease conflict: {task.locked_globs} overlaps an active RUNNING task.")
        worker = agent_name.strip() or task.claimed_by or "studio"
        store.conn.execute("UPDATE agent_tasks SET status='RUNNING', claimed_by=?, updated_at=? WHERE task_id=?", (worker, now, task_id))
        store.conn.commit()
        store.log_event("DAG_TASK_MOVED", task_id, f"{task_id} -> RUNNING ({worker})")
    elif tgt in ("DONE", "FAILED", "EARLY_KILLED", "SKIPPED"):
        steps = extract_task_steps(task.to_dict())
        rec = dict(task.receipt or {})
        rec["steps"] = [{"text": s["text"], "done": True} for s in steps] if tgt == "DONE" else steps
        return complete_task(store, task_id=task_id, status=tgt, receipt=rec)
    else:
        raise ValueError(f"Unsupported Kanban target stage: {target_stage}")

    updated = _row_to_task(store.conn.execute("SELECT * FROM agent_tasks WHERE task_id = ?", (task_id,)).fetchone())
    return {"task": updated.to_dict(), "cascaded_cancelled": []}


def _sync_prop_tasks_md(store: GraphStore, slug: str, pid: str, tasks: List[str], flags: List[bool]) -> None:
    tpath = store.mem_dir / "04_PROPOSALS" / slug / "tasks.md"
    if slug and tpath.parent.is_dir():
        lines = [f"- [{'x' if (i < len(flags) and flags[i]) else ' '}] {t}" for i, t in enumerate(tasks)]
        tpath.write_text(f"# Implementation Tasks — {pid}\n\n" + "\n".join(lines) + "\n", encoding="utf-8")


def toggle_subtask(store: GraphStore, item_kind: str, item_id: str, step_idx: int, done: Optional[bool] = None) -> Dict[str, Any]:
    """Toggle a checklist subtask on either a DAG-XXX task or a PROP-XXX proposal."""
    if item_kind.strip().upper() == "PROPOSAL":
        node = store.get_node(item_id)
        if not node:
            raise ValueError(f"Proposal `{item_id}` not found.")
        tasks = [str(x).strip() for x in (node.metadata.get("tasks") or []) if str(x).strip()]
        if step_idx < 0 or step_idx >= len(tasks):
            raise ValueError(f"Subtask index {step_idx} out of range for `{item_id}`.")
        cur_done = list(node.metadata.get("tasks_done") or [])
        flags = [bool(cur_done[i]) if i < len(cur_done) else False for i in range(len(tasks))]
        flags[step_idx] = (not flags[step_idx]) if done is None else bool(done)
        node.metadata["tasks_done"] = flags
        store.upsert_node(node, log_event=False)
        _sync_prop_tasks_md(store, str(node.metadata.get("slug") or ""), node.id, tasks, flags)
        store.log_event("KANBAN_STEP_TOGGLED", item_id, f"{item_id} step #{step_idx + 1}/{len(tasks)} -> {'DONE' if flags[step_idx] else 'OPEN'}")
        return {"item_id": item_id, "kind": "PROPOSAL", "steps_done": sum(1 for f in flags if f), "steps_total": len(tasks)}

    row = store.conn.execute("SELECT * FROM agent_tasks WHERE task_id = ?", (item_id,)).fetchone()
    if not row:
        raise ValueError(f"Task `{item_id}` not found.")
    task = _row_to_task(row)
    steps = extract_task_steps(task.to_dict())
    if step_idx < 0 or step_idx >= len(steps):
        raise ValueError(f"Subtask index {step_idx} out of range for `{item_id}`.")
    steps[step_idx]["done"] = (not steps[step_idx]["done"]) if done is None else bool(done)
    rec = dict(task.receipt or {})
    rec["steps"] = steps
    new_st, claimed = task.status, task.claimed_by
    if new_st == "QUEUED" and steps[step_idx]["done"]:
        running_globs = [g for t in list_tasks(store, status="RUNNING") for g in t.locked_globs]
        if not _globs_conflict(task.locked_globs, running_globs):
            new_st, claimed = "RUNNING", (claimed or "studio")
    elif new_st == "DONE" and not all(s["done"] for s in steps):
        new_st, claimed = "RUNNING", (claimed or "studio")
    store.conn.execute(
        "UPDATE agent_tasks SET status=?, claimed_by=?, receipt_json=?, updated_at=? WHERE task_id=?",
        (new_st, claimed, json.dumps(rec, ensure_ascii=False), utc_now_iso(), item_id),
    )
    store.conn.commit()
    store.log_event("KANBAN_STEP_TOGGLED", item_id, f"{item_id} step #{step_idx + 1}/{len(steps)} -> {'DONE' if steps[step_idx]['done'] else 'OPEN'}")
    return {"item_id": item_id, "kind": "TASK", "status": new_st, "steps": steps}


def add_subtask(store: GraphStore, item_kind: str, item_id: str, text: str) -> Dict[str, Any]:
    """Append a new checklist subtask to a DAG-XXX task or PROP-XXX proposal."""
    clean = text.strip()[:260]
    if not clean:
        raise ValueError("Subtask text cannot be empty.")
    if item_kind.strip().upper() == "PROPOSAL":
        node = store.get_node(item_id)
        if not node:
            raise ValueError(f"Proposal `{item_id}` not found.")
        tasks = [str(x).strip() for x in (node.metadata.get("tasks") or []) if str(x).strip()][:15]
        cur_done = list(node.metadata.get("tasks_done") or [])
        flags = [bool(cur_done[i]) if i < len(cur_done) else False for i in range(len(tasks))]
        tasks.append(clean)
        flags.append(False)
        node.metadata.update({"tasks": tasks, "tasks_done": flags})
        store.upsert_node(node, log_event=False)
        _sync_prop_tasks_md(store, str(node.metadata.get("slug") or ""), node.id, tasks, flags)
        store.log_event("KANBAN_STEP_ADDED", item_id, f"{item_id} + step: {clean[:85]}")
        return {"item_id": item_id, "kind": "PROPOSAL", "steps_total": len(tasks)}

    row = store.conn.execute("SELECT * FROM agent_tasks WHERE task_id = ?", (item_id,)).fetchone()
    if not row:
        raise ValueError(f"Task `{item_id}` not found.")
    task = _row_to_task(row)
    steps = extract_task_steps(task.to_dict())[:15]
    steps.append({"text": clean, "done": False})
    rec = dict(task.receipt or {})
    rec["steps"] = steps
    new_st = "RUNNING" if task.status == "DONE" else task.status
    store.conn.execute(
        "UPDATE agent_tasks SET status=?, receipt_json=?, updated_at=? WHERE task_id=?",
        (new_st, json.dumps(rec, ensure_ascii=False), utc_now_iso(), item_id),
    )
    store.conn.commit()
    store.log_event("KANBAN_STEP_ADDED", item_id, f"{item_id} + step: {clean[:85]}")
    return {"item_id": item_id, "kind": "TASK", "steps": steps}


def delete_task(store: GraphStore, task_id: str) -> bool:
    """Delete a single DAG task node from SQLite."""
    cur = store.conn.execute("DELETE FROM agent_tasks WHERE task_id = ?", (task_id.strip(),))
    store.conn.commit()
    if cur.rowcount:
        store.log_event("DAG_TASK_DELETED", task_id, f"Deleted task {task_id}")
        return True
    return False
