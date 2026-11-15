"""Multi-Agent Fast-DAG Scheduler, Atomic Glob-Lease Bus & 10% Early-Kill Cascade."""

from __future__ import annotations

import fnmatch
import json
import re
from typing import Any, Dict, List, Optional

from supermemory.models import AgentTask, utc_now_iso
from supermemory.storage.sqlite_store import GraphStore


def _row_to_task(row: Any) -> AgentTask:
    return AgentTask(
        task_id=str(row["task_id"]),
        wave=int(row["wave"]),
        role=str(row["role"]),
        title=str(row["title"]),
        brief=str(row["brief"]),
        status=str(row["status"]),
        depends_on=json.loads(str(row["depends_on_json"] or "[]")),
        locked_globs=json.loads(str(row["locked_globs_json"] or "[]")),
        target_id=str(row["target_id"] or ""),
        claimed_by=str(row["claimed_by"] or ""),
        smoke_gate=str(row["smoke_gate"] or ""),
        receipt=json.loads(str(row["receipt_json"] or "{}")),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def _next_task_num(store: GraphStore) -> int:
    rows = store.conn.execute("SELECT task_id FROM agent_tasks").fetchall()
    nums = [int(m.group(1)) for r in rows for m in [re.search(r"(\d+)$", str(r["task_id"]))] if m]
    return (max(nums) + 1) if nums else 1


def _globs_conflict(globs_a: List[str], globs_b: List[str]) -> bool:
    if not globs_a or not globs_b:
        return False
    for ga in globs_a:
        ca = ga.strip().rstrip("/")
        base_a = ca.split("*")[0].rstrip("/")
        for gb in globs_b:
            cb = gb.strip().rstrip("/")
            base_b = cb.split("*")[0].rstrip("/")
            if ca == cb or fnmatch.fnmatch(ca, cb) or fnmatch.fnmatch(cb, ca):
                return True
            if base_a and base_b and (base_a.startswith(base_b) or base_b.startswith(base_a)):
                return True
    return False


def _compact_receipt(receipt: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Enforce <180-token structured handoff receipt so coordinator context never bloats."""
    if not receipt:
        return {}
    compact: Dict[str, Any] = {}
    for idx, (k, v) in enumerate(receipt.items()):
        if idx >= 8:
            break
        key = str(k)[:32]
        if isinstance(v, (int, float, bool)) or v is None:
            compact[key] = v
        elif isinstance(v, list):
            compact[key] = [str(x)[:60] for x in v[:6]]
        else:
            compact[key] = str(v)[:160]
    return compact


def enqueue_task(
    store: GraphStore,
    role: str,
    title: str,
    brief: str,
    wave: int = 1,
    depends_on: Optional[List[str]] = None,
    locked_globs: Optional[List[str]] = None,
    target_id: str = "",
    smoke_gate: str = "",
    task_id: str = "",
) -> AgentTask:
    """Enqueue or update a DAG task node in SQLite `agent_tasks`."""
    tid = task_id.strip() or f"DAG-{_next_task_num(store):03d}"
    now = utc_now_iso()
    task = AgentTask(
        task_id=tid,
        wave=max(1, int(wave)),
        role=role.strip() or "self",
        title=title.strip(),
        brief=brief.strip(),
        status="QUEUED",
        depends_on=[d.strip() for d in (depends_on or []) if d.strip()],
        locked_globs=[g.strip() for g in (locked_globs or []) if g.strip()],
        target_id=target_id.strip(),
        smoke_gate=smoke_gate.strip(),
        created_at=now,
        updated_at=now,
    )
    store.conn.execute(
        "INSERT INTO agent_tasks(task_id, wave, role, title, brief, status, depends_on_json, "
        "locked_globs_json, target_id, claimed_by, smoke_gate, receipt_json, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(task_id) DO UPDATE SET wave=excluded.wave, role=excluded.role, title=excluded.title, "
        "brief=excluded.brief, status=excluded.status, depends_on_json=excluded.depends_on_json, "
        "locked_globs_json=excluded.locked_globs_json, target_id=excluded.target_id, "
        "smoke_gate=excluded.smoke_gate, updated_at=excluded.updated_at",
        (
            task.task_id, task.wave, task.role, task.title, task.brief, task.status,
            json.dumps(task.depends_on, ensure_ascii=False), json.dumps(task.locked_globs, ensure_ascii=False),
            task.target_id, "", task.smoke_gate, "{}", task.created_at, task.updated_at,
        ),
    )
    store.conn.commit()
    return task


def plan_research_sprint(
    store: GraphStore,
    goal: str,
    bottleneck_id: str = "",
    smoke_cmd: str = "pytest -q",
    target_globs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Compile a 3-Wave Multi-Agent Research Sprint DAG with parallel discovery & smoke-gated slice."""
    base_n = _next_task_num(store)
    ids = [f"DAG-{base_n + i:03d}" for i in range(6)]
    globs = target_globs if target_globs is not None else ["src/**"]
    tgt = bottleneck_id.strip()
    specs = [
        (ids[0], 1, "bottleneck-profiler", f"Profile Error Slices & Pareto Bottleneck: {goal[:55]}",
         "Decompose validation errors/regret by slice; register `BNK-XXX` + falsifiable `RQ-XXX`.", [], [], ""),
        (ids[1], 1, "sota-scout", f"Scout SOTA Method Cards: {goal[:55]}",
         "Query arXiv/Semantic Scholar/OpenAlex (SQLite cached) and mint `METH-XXX` cards with integration hooks.", [], [], ""),
        (ids[2], 1, "memory-curator", "Federated + Sibling Vault Recall & Dead-End Check",
         "Run hybrid utility recall (`include_siblings=True`) to surface reusable wins and dead-end fingerprints.", [], [], ""),
        (ids[3], 2, "hypothesis-architect", "Synthesize High-Occam-ROI Single-Variable Spec",
         "Rank `METH-XXX` against top `BNK-XXX` by Occam ROI; emit single-variable proposal + 10% kill criterion.", [ids[0], ids[1], ids[2]], [], ""),
        (ids[4], 2, "experiment-challenger", "Adversarial Red-Team Audit (Leakage & Anti-Bloat)",
         "Verify 0 test leakage, 1 isolated variable, valid `BNK-XXX` link, and 0 dead-end mechanism collision.", [ids[3]], [], ""),
        (ids[5], 3, "slice-builder", "Execute Glob-Locked Vertical Slice + 10% Smoke Gate",
         "Implement <300L slice under glob lease, run 10% smoke gate first (EARLY_KILL if flat), then log experiment.", [ids[4]], globs, smoke_cmd),
    ]
    created = [
        enqueue_task(store, role=rl, title=ttl, brief=brf, wave=wv, depends_on=deps, locked_globs=lk, target_id=tgt, smoke_gate=smk, task_id=tid).to_dict()
        for tid, wv, rl, ttl, brf, deps, lk, smk in specs
    ]
    store.log_event("SPRINT_PLANNED", ids[0], f"Planned 3-Wave Fast-DAG ({len(created)} tasks) for: {goal[:80]}")
    return {"sprint_goal": goal, "tasks": created, "parallel_wave1_ids": ids[:3]}


def list_tasks(store: GraphStore, status: str = "", wave: int = 0) -> List[AgentTask]:
    """List DAG tasks ordered by wave and ID."""
    tasks = [_row_to_task(r) for r in store.conn.execute("SELECT * FROM agent_tasks ORDER BY wave ASC, task_id ASC").fetchall()]
    if status:
        tasks = [t for t in tasks if t.status == status.upper()]
    if wave > 0:
        tasks = [t for t in tasks if t.wave == wave]
    return tasks


def claim_next_task(store: GraphStore, agent_name: str, role: str = "") -> Optional[Dict[str, Any]]:
    """Atomically claim the next dependency-ready, glob-conflict-free task in SQLite WAL."""
    cur = store.conn.cursor()
    cur.execute("BEGIN IMMEDIATE")
    try:
        all_tasks = [_row_to_task(r) for r in cur.execute("SELECT * FROM agent_tasks ORDER BY wave ASC, task_id ASC").fetchall()]
        by_id = {t.task_id: t for t in all_tasks}
        running_globs = [g for t in all_tasks if t.status == "RUNNING" for g in t.locked_globs]
        for cand in all_tasks:
            if cand.status != "QUEUED" or (role and cand.role != role):
                continue
            if not all((by_id.get(d) is not None and by_id[d].status == "DONE") for d in cand.depends_on):
                continue
            if _globs_conflict(cand.locked_globs, running_globs):
                continue
            now = utc_now_iso()
            worker = agent_name.strip() or "worker"
            cur.execute("UPDATE agent_tasks SET status='RUNNING', claimed_by=?, updated_at=? WHERE task_id=?", (worker, now, cand.task_id))
            store.conn.commit()
            cand.status = "RUNNING"
            cand.claimed_by = worker
            cand.updated_at = now
            store.log_event("DAG_TASK_CLAIMED", cand.task_id, f"{worker} claimed {cand.task_id} ({cand.role})")
            return cand.to_dict()
        store.conn.commit()
        return None
    except Exception:
        store.conn.rollback()
        raise


def complete_task(store: GraphStore, task_id: str, status: str = "DONE", receipt: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Complete or early-kill a DAG task with <180-token receipt and cascade kill-gate cancellations."""
    clean_st = status.strip().upper()
    if clean_st not in ("DONE", "FAILED", "EARLY_KILLED", "SKIPPED"):
        raise ValueError(f"Invalid task completion status: {status}")
    if not store.conn.execute("SELECT 1 FROM agent_tasks WHERE task_id = ?", (task_id,)).fetchone():
        raise ValueError(f"Task `{task_id}` not found.")

    comp = _compact_receipt(receipt)
    now = utc_now_iso()
    store.conn.execute("UPDATE agent_tasks SET status=?, receipt_json=?, updated_at=? WHERE task_id=?", (clean_st, json.dumps(comp, ensure_ascii=False), now, task_id))
    cascaded: List[str] = []
    if clean_st in ("FAILED", "EARLY_KILLED"):
        all_t = [_row_to_task(r) for r in store.conn.execute("SELECT * FROM agent_tasks").fetchall()]
        blocked = {task_id}
        changed = True
        while changed:
            changed = False
            for t in all_t:
                if t.status == "QUEUED" and any(d in blocked for d in t.depends_on):
                    store.conn.execute("UPDATE agent_tasks SET status='CANCELLED_BY_KILL_GATE', updated_at=? WHERE task_id=?", (now, t.task_id))
                    t.status = "CANCELLED_BY_KILL_GATE"
                    blocked.add(t.task_id)
                    cascaded.append(t.task_id)
                    changed = True
    store.conn.commit()
    store.log_event("DAG_TASK_FINISHED", task_id, f"{task_id} -> {clean_st} (cascaded={len(cascaded)})")
    updated = _row_to_task(store.conn.execute("SELECT * FROM agent_tasks WHERE task_id = ?", (task_id,)).fetchone())
    return {"task": updated.to_dict(), "cascaded_cancelled": cascaded}


def dag_telemetry(store: GraphStore) -> Dict[str, Any]:
    """Summarize multi-agent DAG queue states, parallel readiness, and active glob leases."""
    tasks = list_tasks(store)
    by_id = {t.task_id: t for t in tasks}
    by_status: Dict[str, int] = {}
    active_leases: List[Dict[str, Any]] = []
    running_globs: List[str] = []
    for t in tasks:
        by_status[t.status] = by_status.get(t.status, 0) + 1
        if t.status == "RUNNING" and t.locked_globs:
            running_globs.extend(t.locked_globs)
            active_leases.append({"task_id": t.task_id, "claimed_by": t.claimed_by, "globs": t.locked_globs})
    ready = [
        t.task_id for t in tasks
        if t.status == "QUEUED"
        and all((by_id.get(d) is not None and by_id[d].status == "DONE") for d in t.depends_on)
        and not _globs_conflict(t.locked_globs, running_globs)
    ]
    return {"total_tasks": len(tasks), "counts_by_status": by_status, "ready_parallel_task_ids": ready, "active_glob_leases": active_leases}
