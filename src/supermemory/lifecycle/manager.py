"""Lifecycle state machine for Ideas, Algorithms, Proposals, Experiments, and Audits."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from supermemory.graph.query_engine import QueryEngine
from supermemory.lifecycle.experiments import record_scientific_experiment
from supermemory.models import (
    EdgeType,
    ExperimentVerdict,
    MemoryEdge,
    MemoryNode,
    NodeType,
    ProposalStage,
    utc_now_iso,
)
from supermemory.storage.sqlite_store import GraphStore


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:48] or "change"


class LifecycleManager:
    """Manages end-to-end R&D artifacts, lineage edges, and Challenger/Victory audits."""

    def __init__(self, store: GraphStore) -> None:
        self.store = store
        self.query = QueryEngine(store)

    def _next_id(self, prefix: str, node_type: str) -> str:
        nodes = self.store.list_nodes(node_types=[node_type], limit=5000)
        nums: List[int] = []
        pat = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
        for n in nodes:
            m = pat.match(n.id)
            if m:
                nums.append(int(m.group(1)))
        return f"{prefix}-{(max(nums) + 1) if nums else 1:03d}"

    def register_idea(
        self,
        title: str,
        summary: str,
        expected_impact: str = "",
        risks: str = "",
        status: str = "SEED",
        rejection_reason: str = "",
        is_algorithm: bool = False,
        invariants: str = "",
        inspired_by: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        ntype = NodeType.ALGORITHM.value if is_algorithm else NodeType.IDEA.value
        prefix = "ALGO" if is_algorithm else "IDEA"
        prior = self.query.recall(f"{title} {summary}", limit=5, hops=1)
        nid = self._next_id(prefix, ntype)

        ideas_dir = self.store.mem_dir / "05_IDEAS_AND_ALGORITHMS"
        ideas_dir.mkdir(parents=True, exist_ok=True)
        rel_path = f"memory/05_IDEAS_AND_ALGORITHMS/{nid}_{_slugify(title)}.md"
        md = (
            f"# {nid}: {title}\n\n"
            f"- **Type:** `{ntype}` | **Status:** `{status.upper()}`\n"
            f"- **Created:** `{utc_now_iso()}`\n"
            f"- **Summary:** {summary}\n"
            f"- **Expected Impact / Generalization Proof:** {expected_impact or 'N/A'}\n"
            f"- **Mathematical / Structural Invariants:** {invariants or 'N/A'}\n"
            f"- **Known Risks / Failure Modes:** {risks or 'N/A'}\n"
            + (f"- **Rejection / Dead-End Reason:** {rejection_reason}\n" if rejection_reason else "")
        )
        (self.store.workspace_root / rel_path).write_text(md, encoding="utf-8")

        node = self.store.upsert_node(
            MemoryNode(
                id=nid,
                node_type=ntype,
                title=title,
                status=status.upper(),
                summary=(f"[REJECTED: {rejection_reason}] " if rejection_reason else "") + summary[:220],
                content=md,
                file_path=rel_path,
                tags=[ntype.lower(), status.lower()],
                priority=80 if status.upper() != "REJECTED" else 65,
                metadata={
                    "expected_impact": expected_impact,
                    "risks": risks,
                    "invariants": invariants,
                    "rejection_reason": rejection_reason,
                },
            )
        )
        for src_id in inspired_by or []:
            self.store.add_edge(MemoryEdge(source_id=src_id, target_id=nid, relation=EdgeType.INSPIRED.value))
        return {"node": node.to_dict(), "prior_warnings": prior["anti_repeat_warnings"]}

    def create_proposal(
        self,
        title: str,
        why: str,
        what_changes: str,
        design_notes: str = "",
        tasks: Optional[List[str]] = None,
        idea_ids: Optional[List[str]] = None,
        proposal_id: str = "",
    ) -> Dict[str, Any]:
        pid = proposal_id.strip() or self._next_id("PROP", NodeType.PROPOSAL.value)
        slug = f"{pid}_{_slugify(title)}"
        prop_dir = self.store.mem_dir / "04_PROPOSALS" / slug
        prop_dir.mkdir(parents=True, exist_ok=True)

        (prop_dir / "proposal.md").write_text(
            f"# {pid}: {title}\n\n## Why\n\n{why}\n\n## What Changes\n\n{what_changes}\n",
            encoding="utf-8",
        )
        if design_notes:
            (prop_dir / "design.md").write_text(
                f"# Technical Design — {pid}: {title}\n\n{design_notes}\n", encoding="utf-8"
            )
        task_items = tasks or ["Implement core vertical slice with unit tests", "Run Challenger & Victory Audit"]
        tasks_md = f"# Implementation Tasks — {pid}\n\n" + "\n".join(f"- [ ] {t}" for t in task_items) + "\n"
        (prop_dir / "tasks.md").write_text(tasks_md, encoding="utf-8")

        stage = ProposalStage.DESIGNED.value if design_notes else ProposalStage.PROPOSED.value
        rel_dir = f"memory/04_PROPOSALS/{slug}/proposal.md"
        node = self.store.upsert_node(
            MemoryNode(
                id=pid,
                node_type=NodeType.PROPOSAL.value,
                title=title,
                status=stage,
                summary=why[:240],
                content=f"{why}\n\n{what_changes}\n\n{design_notes}",
                file_path=rel_dir,
                tags=["proposal", stage.lower()],
                priority=88,
                metadata={"slug": slug, "tasks": task_items, "audits": []},
            )
        )
        for iid in idea_ids or []:
            self.store.add_edge(MemoryEdge(source_id=iid, target_id=pid, relation=EdgeType.PROMOTED_TO.value))
        return {"proposal_id": pid, "stage": stage, "path": rel_dir, "node": node.to_dict()}

    def advance_proposal(self, proposal_id: str, new_stage: str, note: str = "") -> MemoryNode:
        node = self.store.get_node(proposal_id)
        if not node:
            raise ValueError(f"Proposal not found: {proposal_id}")
        valid_stages = {s.value for s in ProposalStage}
        st = new_stage.upper()
        if st not in valid_stages:
            raise ValueError(f"Invalid stage '{new_stage}'. Valid: {sorted(valid_stages)}")
        if st == ProposalStage.ARCHIVED.value and not node.metadata.get("audits"):
            raise ValueError(
                f"LAW-06 Gate: Cannot ARCHIVE {proposal_id} without at least one Challenger/Victory Audit verdict."
            )
        node.status = st
        if note:
            node.content = f"{node.content}\n\n### Stage -> `{st}` ({utc_now_iso()})\n{note}"
        self.store.upsert_node(node)
        return node

    def log_experiment(self, **kwargs: Any) -> Dict[str, Any]:
        return record_scientific_experiment(self.store, **kwargs)

    def record_audit_verdict(
        self,
        target_id: str,
        auditor_role: str,
        verdict: str,
        findings: str,
        monotonic_verified: bool = True,
        zero_leakage_verified: bool = True,
    ) -> Dict[str, Any]:
        audit_id = self._next_id("AUDIT", NodeType.AGENT_RUN.value)
        clean_verdict = verdict.upper()
        node = self.store.upsert_node(
            MemoryNode(
                id=audit_id,
                node_type=NodeType.AGENT_RUN.value,
                title=f"{auditor_role} Audit on {target_id}: {clean_verdict}",
                status=clean_verdict,
                summary=findings[:240],
                content=findings,
                tags=["audit", auditor_role.lower(), clean_verdict.lower()],
                priority=85,
                metadata={
                    "target_id": target_id,
                    "auditor_role": auditor_role,
                    "verdict": clean_verdict,
                    "monotonic_verified": monotonic_verified,
                    "zero_leakage_verified": zero_leakage_verified,
                },
            )
        )
        self.store.add_edge(MemoryEdge(source_id=target_id, target_id=audit_id, relation=EdgeType.AUDITED_BY.value))
        target_node = self.store.get_node(target_id)
        if target_node:
            audits = list(target_node.metadata.get("audits") or [])
            audits.append({"audit_id": audit_id, "role": auditor_role, "verdict": clean_verdict})
            target_node.metadata["audits"] = audits
            if target_node.node_type == NodeType.PROPOSAL.value and clean_verdict == "APPROVE":
                target_node.status = ProposalStage.AUDITED.value
            elif target_node.node_type == NodeType.EXPERIMENT.value and clean_verdict == "APPROVE":
                target_node.status = ExperimentVerdict.VICTORY_CONFIRMED.value
            self.store.upsert_node(target_node, log_event=False)
        return node.to_dict()
