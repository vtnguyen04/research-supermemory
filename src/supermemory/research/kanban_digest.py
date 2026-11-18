"""Live Kanban Board Digest, Revision Fingerprinting & Markdown Checklist Renderer."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from supermemory.models import NodeType
from supermemory.research.kanban_ops import extract_task_steps
from supermemory.research.orchestrator import list_tasks
from supermemory.storage.sqlite_store import GraphStore


def _id_num(raw_id: str) -> int:
    m = re.search(r"(\d+)$", raw_id or "")
    return int(m.group(1)) if m else 0


def collect_active_kanban_items(store: GraphStore) -> List[Dict[str, Any]]:
    """Collect active `RUNNING`/`QUEUED` DAG tasks and `IMPLEMENTING`/`DESIGNED` Proposals (newest first)."""
    items: List[Dict[str, Any]] = []
    all_tasks = [t.to_dict() for t in list_tasks(store)]
    active_tasks = [t for t in all_tasks if str(t.get("status") or "").upper() in ("RUNNING", "QUEUED")]
    active_tasks.sort(
        key=lambda t: (0 if str(t.get("status") or "").upper() == "RUNNING" else 1, -_id_num(str(t.get("task_id") or "")))
    )
    for t in active_tasks:
        steps = extract_task_steps(t)
        done_cnt = sum(1 for s in steps if s.get("done"))
        nxt: Optional[Tuple[int, str]] = next(
            ((i, str(s.get("text") or "")) for i, s in enumerate(steps) if not s.get("done")),
            None,
        )
        items.append(
            {
                "id": str(t["task_id"]),
                "kind": "TASK",
                "status": str(t.get("status") or "QUEUED").upper(),
                "title": str(t.get("title") or ""),
                "steps": steps,
                "done_cnt": done_cnt,
                "total_cnt": len(steps),
                "next_step": nxt,
            }
        )

    stage_rank = {"IMPLEMENTING": 0, "CHALLENGED": 1, "DESIGNED": 2, "PROPOSED": 3}
    props = [
        p
        for p in store.list_nodes(
            node_types=[NodeType.PROPOSAL.value],
            exclude_statuses=["ARCHIVED", "AUDITED", "REJECTED", "CONSOLIDATED"],
            limit=80,
        )
        if p.status.upper() in stage_rank
    ]
    props.sort(key=lambda p: (stage_rank.get(p.status.upper(), 9), -_id_num(p.id)))
    for p in props:
        meta = p.metadata or {}
        p_tasks = [str(x).strip() for x in (meta.get("tasks") or []) if str(x).strip()]
        p_done = [bool(x) for x in (meta.get("tasks_done") or [])]
        steps = [
            {"text": txt, "done": (i < len(p_done) and p_done[i])}
            for i, txt in enumerate(p_tasks)
        ]
        done_cnt = sum(1 for s in steps if s["done"])
        nxt = next(((i, s["text"]) for i, s in enumerate(steps) if not s["done"]), None)
        items.append(
            {
                "id": p.id,
                "kind": "PROPOSAL",
                "status": p.status.upper(),
                "title": p.title,
                "steps": steps,
                "done_cnt": done_cnt,
                "total_cnt": len(steps),
                "next_step": nxt,
            }
        )
    return items


def has_unchecked_kanban_items(store: GraphStore) -> bool:
    """Return True if any active Kanban Task or Proposal has unchecked subtask steps."""
    return any(it["next_step"] is not None or it["status"] == "QUEUED" for it in collect_active_kanban_items(store))


def build_kanban_board_digest(store: GraphStore, max_items: int = 4) -> Tuple[str, str]:
    """Build a compact <130-token live Kanban digest + SHA-1 board state fingerprint."""
    active = [it for it in collect_active_kanban_items(store) if it["next_step"] is not None or it["status"] == "QUEUED"]
    if not active:
        return "", ""
    fp_raw = json.dumps(
        [(it["id"], it["status"], [bool(s["done"]) for s in it["steps"]], [s["text"] for s in it["steps"]]) for it in active],
        ensure_ascii=False,
    )
    fp = hashlib.sha1(fp_raw.encode("utf-8")).hexdigest()[:12]
    lines = ["📋 LIVE KANBAN BOARD (Follow & Tick Steps Automatically — Never Wait to Be Reminded):"]
    for it in active[:max_items]:
        nxt = it["next_step"]
        nxt_str = f' -> Next #[{nxt[0]}]: "{nxt[1][:72]}"' if nxt else ""
        lines.append(f"  • `{it['id']}` [{it['status']} {it['done_cnt']}/{it['total_cnt']}] {it['title'][:48]}{nxt_str}")
    sample = active[0]
    s_idx = sample["next_step"][0] if sample["next_step"] else 0
    st_hint = ', "stage": "IN_PROGRESS"' if sample["status"] in ("QUEUED", "PROPOSED", "DESIGNED") else ""
    lines.append(f'  ↳ Sync step: `checkpoint(task_updates=[{{"id": "{sample["id"]}"{st_hint}, "done_steps": [{s_idx}]}}])`')
    return "\n".join(lines), fp


def render_active_state_kanban_md(store: GraphStore, max_items: int = 4) -> List[str]:
    """Render live Kanban tasks & subtask checkboxes for `memory/01_ACTIVE_STATE.md`."""
    active = collect_active_kanban_items(store)[:max_items]
    if not active:
        return []
    out = ["", "## 📋 3A. Live Kanban Board & Subtask Checklists", ""]
    for it in active:
        out.append(f"- **`{it['id']}`** [`{it['status']}` · `{it['done_cnt']}/{it['total_cnt']}`]: {it['title']}")
        for idx, s in enumerate(it["steps"][:5]):
            mark = "x" if s["done"] else " "
            out.append(f"  - [{mark}] `#[{idx}]` {s['text'][:110]}")
    return out
