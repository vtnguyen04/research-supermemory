"""Deduplicates lessons into canonical Laws and crystallizes executable CodeGates."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from supermemory.models import CodeGate, EdgeType, GateType, MemoryEdge, MemoryNode, NodeType, utc_now_iso
from supermemory.storage.sqlite_store import GraphStore


class LessonConsolidator:
    """Prevents unbounded lesson bloat by folding lessons into Laws + CodeGates."""

    def __init__(self, store: GraphStore) -> None:
        self.store = store

    def next_lesson_id(self) -> str:
        existing = self.store.list_nodes(node_types=[NodeType.LESSON.value], limit=5000)
        nums = []
        for n in existing:
            m = re.match(r"^LESSON-(\d+)$", n.id)
            if m:
                nums.append(int(m.group(1)))
        return f"LESSON-{(max(nums) + 1) if nums else 1:03d}"

    def next_law_id(self) -> str:
        existing = self.store.list_nodes(node_types=[NodeType.LAW.value], limit=500)
        nums = []
        for n in existing:
            m = re.match(r"^LAW-(\d+)$", n.id)
            if m:
                nums.append(int(m.group(1)))
        return f"LAW-{(max(nums) + 1) if nums else 1:02d}"

    def next_gate_id(self) -> str:
        existing = self.store.list_gates()
        nums = []
        for g in existing:
            m = re.match(r"^GATE-(\d+)$", g.id)
            if m:
                nums.append(int(m.group(1)))
        return f"GATE-{(max(nums) + 1) if nums else 1:03d}"

    def record_lesson(
        self,
        title: str,
        mistake: str,
        root_cause: str,
        prevention_rule: str,
        user_quote: str = "",
        law_id: str = "",
        lesson_id: str = "",
        new_law_title: str = "",
        forbid_regex: str = "",
        target_glob: str = "**/*.py",
        forbid_cmd_regex: str = "",
        source_exp_id: str = "",
        severity: str = "HIGH",
    ) -> Dict[str, Any]:
        """Record a lesson, fold into a Law, write archive file, and optionally bind a CodeGate."""
        lid = lesson_id.strip() or self.next_lesson_id()
        resolved_law_id = self._resolve_or_create_law(law_id, new_law_title, title, prevention_rule)

        # Write full archival detail to memory/lessons/<LESSON-ID>.md so 0% history is ever lost
        lessons_dir = self.store.mem_dir / "lessons"
        lessons_dir.mkdir(parents=True, exist_ok=True)
        rel_path = f"memory/lessons/{lid}.md"
        full_md = (
            f"# {lid}: {title}\n\n"
            f"- **Recorded At:** `{utc_now_iso()}`\n"
            f"- **Consolidated Under:** `{resolved_law_id}`\n"
            f"- **Severity:** `{severity}`\n"
            f"- **User Quote:** *\"{user_quote or 'N/A'}\"*\n"
            f"- **Mistake Observed:** {mistake}\n"
            f"- **Root Cause:** {root_cause}\n"
            f"- **Permanent Prevention Invariant:** {prevention_rule}\n"
        )
        (self.store.workspace_root / rel_path).write_text(full_md, encoding="utf-8")

        lesson_node = MemoryNode(
            id=lid,
            node_type=NodeType.LESSON.value,
            title=title,
            status="ACTIVE",
            summary=f"{mistake} -> {prevention_rule}"[:240],
            content=full_md,
            file_path=rel_path,
            tags=["lesson", severity.lower(), resolved_law_id.lower()],
            priority=90 if severity.upper() == "HIGH" else 75,
            metadata={
                "user_quote": user_quote,
                "mistake": mistake,
                "root_cause": root_cause,
                "prevention_rule": prevention_rule,
                "law_id": resolved_law_id,
                "severity": severity.upper(),
            },
        )
        self.store.upsert_node(lesson_node)
        self.store.add_edge(
            MemoryEdge(
                source_id=lid,
                target_id=resolved_law_id,
                relation=EdgeType.CONSOLIDATED_INTO.value,
            )
        )

        # Increment recurrence counter on parent LAW metadata
        law_node = self.store.get_node(resolved_law_id)
        if law_node:
            lessons_list = list(law_node.metadata.get("consolidated_lessons") or [])
            if lid not in lessons_list:
                lessons_list.append(lid)
            law_node.metadata["consolidated_lessons"] = lessons_list
            law_node.metadata["recurrence_count"] = len(lessons_list)
            self.store.upsert_node(law_node, log_event=False)

        if source_exp_id:
            self.store.add_edge(
                MemoryEdge(
                    source_id=source_exp_id,
                    target_id=lid,
                    relation=EdgeType.PRODUCED_LESSON.value,
                )
            )

        created_gate: Optional[CodeGate] = None
        if forbid_regex.strip():
            gid = self.next_gate_id()
            created_gate = self.store.upsert_gate(
                CodeGate(
                    id=gid,
                    gate_type=GateType.FORBIDDEN_REGEX.value,
                    name=f"Guard for {lid}: {title[:60]}",
                    law_id=resolved_law_id,
                    lesson_id=lid,
                    target_glob=target_glob or "**/*.py",
                    pattern=forbid_regex.strip(),
                    config={"ignore_comments": True},
                )
            )
        elif forbid_cmd_regex.strip():
            gid = self.next_gate_id()
            created_gate = self.store.upsert_gate(
                CodeGate(
                    id=gid,
                    gate_type=GateType.FORBIDDEN_CMD_PATTERN.value,
                    name=f"CLI Guard for {lid}: {title[:60]}",
                    law_id=resolved_law_id,
                    lesson_id=lid,
                    target_glob="run_command",
                    pattern=forbid_cmd_regex.strip(),
                )
            )

        if created_gate:
            gate_node = MemoryNode(
                id=created_gate.id,
                node_type=NodeType.GATE.value,
                title=created_gate.name,
                summary=f"[{created_gate.gate_type}] pattern=`{created_gate.pattern}` on `{created_gate.target_glob}`",
                tags=["gate", resolved_law_id.lower()],
                priority=95,
                metadata=created_gate.to_dict(),
            )
            self.store.upsert_node(gate_node, log_event=False)
            self.store.add_edge(
                MemoryEdge(
                    source_id=resolved_law_id,
                    target_id=created_gate.id,
                    relation=EdgeType.ENFORCED_BY.value,
                )
            )
            self.store.add_edge(
                MemoryEdge(
                    source_id=created_gate.id,
                    target_id=lid,
                    relation=EdgeType.BLOCKS_RECURRENCE_OF.value,
                )
            )

        self.store.log_event(
            "SELF_LEARNING_COMMIT",
            lid,
            f"Learned {lid} -> {resolved_law_id}" + (f" + {created_gate.id}" if created_gate else ""),
        )
        return {
            "lesson_id": lid,
            "law_id": resolved_law_id,
            "gate_id": created_gate.id if created_gate else None,
            "archive_path": rel_path,
        }

    def _resolve_or_create_law(
        self, law_id: str, new_law_title: str, lesson_title: str, prevention_rule: str
    ) -> str:
        if law_id.strip():
            existing = self.store.get_node(law_id.strip())
            if existing:
                return existing.id
        if new_law_title.strip() or law_id.strip():
            nid = law_id.strip() or self.next_law_id()
            self.store.upsert_node(
                MemoryNode(
                    id=nid,
                    node_type=NodeType.LAW.value,
                    title=new_law_title.strip() or lesson_title,
                    summary=prevention_rule[:220],
                    content=prevention_rule,
                    priority=95,
                    tags=["law", "self-learned"],
                )
            )
            return nid
        hits = self.store.search_fts(f"{lesson_title} {prevention_rule}", limit=8)
        for node, _ in hits:
            if node.node_type == NodeType.LAW.value:
                return node.id
        laws = self.store.list_nodes(node_types=[NodeType.LAW.value], limit=1)
        if laws:
            return "LAW-08" if self.store.get_node("LAW-08") else laws[0].id
        nid = self.next_law_id()
        self.store.upsert_node(
            MemoryNode(
                id=nid,
                node_type=NodeType.LAW.value,
                title=lesson_title,
                summary=prevention_rule[:220],
                content=prevention_rule,
                priority=95,
                tags=["law"],
            )
        )
        return nid
