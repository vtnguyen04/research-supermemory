"""Hybrid BM25 + Multi-Hop Graph Retrieval and Anti-Amnesia Context Capsule."""

from __future__ import annotations

from typing import Any, Dict, List

from supermemory.graph.hybrid_ranker import rank_hybrid_graph
from supermemory.models import ExperimentVerdict, MemoryNode, NodeType
from supermemory.storage.sqlite_store import GraphStore


class QueryEngine:
    """Combines FTS5 BM25, Subword N-Gram TF-IDF, Empirical Utility & Personalized PageRank."""

    def __init__(self, store: GraphStore) -> None:
        self.store = store

    def recall(self, query: str, limit: int = 10, hops: int = 1) -> Dict[str, Any]:
        """Search graph with Hybrid BM25 + N-gram TF-IDF + Utility PageRank & surface warnings."""
        seed_hits = self.store.search_fts(query, limit=max(limit, 12))
        ranked, connected_edges = rank_hybrid_graph(
            self.store,
            query=query,
            fts_hits=seed_hits,
            limit=limit,
            hops=hops,
        )
        warnings = self._extract_anti_repeat_warnings(ranked)
        return {
            "query": query,
            "match_count": len(ranked),
            "anti_repeat_warnings": warnings,
            "results": ranked[: limit + 8],
            "edges": connected_edges[:30],
        }

    def build_session_capsule(self, user_input: str = "") -> str:
        """Compile a compact (< 1,200 token) Constitutional + Active State + Recall capsule."""
        meta = self.store.get_all_meta()
        proj_name = meta.get("project_name") or self.store.workspace_root.name
        goal = meta.get("active_goal") or "Maintain 100% constitutional compliance and zero regressions."
        next_actions = meta.get("next_actions") or "Inspect memory/01_ACTIVE_STATE.md before acting."

        laws = self.store.list_nodes(node_types=[NodeType.LAW.value], limit=15)
        gates = self.store.list_gates(enabled_only=True)
        proposals = [
            p
            for p in self.store.list_nodes(node_types=[NodeType.PROPOSAL.value], limit=10)
            if p.status not in ("ARCHIVED", "REJECTED")
        ]
        exps = self.store.list_experiments()[-5:]

        lines: List[str] = [
            f"🧠 SUPERMEMORY CONSTITUTIONAL HARNESS ACTIVE — Project: `{proj_name}`",
            f"• Active Goal: {goal}",
            f"• Next Actions: {next_actions}",
            f"• Active Guardrails: {len(laws)} Laws | {len(gates)} Deterministic PreToolUse Gates",
        ]
        if laws:
            lines.append("• Non-Negotiable Laws:")
            for lw in sorted(laws, key=lambda x: x.id):
                rec = lw.metadata.get("recurrence_count", 0)
                rec_tag = f" [consolidated {rec} lessons]" if rec else ""
                lines.append(f"  - `{lw.id}`: {lw.title}{rec_tag}")

        if proposals:
            lines.append("• Active Lifecycle Proposals:")
            for pr in proposals[:4]:
                lines.append(f"  - `{pr.id}` [{pr.status}]: {pr.title}")

        if exps:
            lines.append("• Recent Scientific Experiments:")
            for ex in exps[-3:]:
                sc = f"CV={ex.cv_score}" if ex.cv_score is not None else ex.cv_summary
                lines.append(f"  - `{ex.exp_id}` ({ex.track}) [{ex.verdict}]: {ex.title} ({sc})")

        if user_input.strip():
            rec = self.recall(user_input, limit=4, hops=1)
            if rec["anti_repeat_warnings"]:
                lines.append("⚠️ ANTI-REPEAT MEMORY WARNINGS FOR THIS TURN:")
                for w in rec["anti_repeat_warnings"][:4]:
                    lines.append(f"  - {w}")
            elif rec["results"]:
                lines.append("• Relevant Graph Nodes Recalled:")
                for r in rec["results"][:3]:
                    lines.append(f"  - [{r['type']}] `{r['id']}`: {r['title']} — {r['summary'][:110]}")

        return "\n".join(lines)

    def _extract_anti_repeat_warnings(self, ranked_items: List[Dict[str, Any]]) -> List[str]:
        warnings: List[str] = []
        for item in ranked_items:
            nid = item["id"]
            ntype = item["type"]
            status = item["status"]
            if ntype == NodeType.LESSON.value:
                warnings.append(f"PAST MISTAKE `{nid}` ({item['title']}): {item['summary'][:150]}")
            elif ntype in (NodeType.IDEA.value, NodeType.PROPOSAL.value) and status == "REJECTED":
                warnings.append(f"DEAD-END {ntype} `{nid}` was previously REJECTED: {item['summary'][:150]}")
            elif ntype == NodeType.EXPERIMENT.value and status in (
                ExperimentVerdict.REVERT.value,
                ExperimentVerdict.FAILED.value,
            ):
                warnings.append(f"FAILED/REVERTED EXPERIMENT `{nid}` ({item['title']}): {item['summary'][:150]}")
            elif ntype == NodeType.OBSERVATION.value and status == "FAILURE_INSIGHT":
                warnings.append(f"FAILURE INSIGHT `{nid}`: {item['summary'][:160]}")
        return warnings

    def graph_analytics(self) -> Dict[str, Any]:
        """Compute node/edge counts, gate shield stats, bottlenecks, methods & experiment progression."""
        all_nodes: List[MemoryNode] = self.store.list_nodes(limit=10000)
        by_type: Dict[str, int] = {}
        open_bottlenecks = 0
        for n in all_nodes:
            by_type[n.node_type] = by_type.get(n.node_type, 0) + 1
            if n.node_type == NodeType.BOTTLENECK.value and n.status not in ("RESOLVED", "ARCHIVED"):
                open_bottlenecks += 1
        gates = self.store.list_gates()
        exps = self.store.list_experiments()
        edges = self.store.list_edges()
        return {
            "total_nodes": len(all_nodes),
            "total_edges": len(edges),
            "nodes_by_type": by_type,
            "open_bottlenecks": open_bottlenecks,
            "method_cards": by_type.get(NodeType.METHOD_CARD.value, 0),
            "total_gates": len(gates),
            "total_blocked_regressions": sum(g.blocked_count for g in gates),
            "total_experiments": len(exps),
            "verified_victories": sum(
                1 for e in exps if e.verdict in (ExperimentVerdict.VICTORY_CONFIRMED.value, ExperimentVerdict.KEEP.value)
            ),
            "reverted_experiments": sum(
                1 for e in exps if e.verdict in (ExperimentVerdict.REVERT.value, ExperimentVerdict.FAILED.value)
            ),
        }
