"""Compiles SQLite Knowledge Graph into compact, clickable Markdown memory files."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from supermemory.models import CodeGate, MemoryNode, NodeType, utc_now_iso
from supermemory.storage.snapshot_io import export_snapshot
from supermemory.storage.sqlite_store import GraphStore
from supermemory.sync.agent_adapters import generate_agent_files


def _md_cell(text: str, max_len: int = 160) -> str:
    cleaned = " ".join((text or "").replace("|", "\\|").splitlines()).strip()
    return (cleaned[: max_len - 1] + "…") if len(cleaned) > max_len else cleaned


class MarkdownCompiler:
    """Renders deterministic, size-bounded Markdown views + portable JSON snapshot."""

    def __init__(self, store: GraphStore) -> None:
        self.store = store
        self.mem_dir = store.mem_dir
        self.root = store.workspace_root

    def compile_all(self) -> Dict[str, str]:
        self.mem_dir.mkdir(parents=True, exist_ok=True)
        (self.mem_dir / "06_KNOWLEDGE_NODES").mkdir(parents=True, exist_ok=True)
        g_path = self._write_memory_graph()
        s_path = self._write_active_state()
        c_path = self._write_constitution()
        e_path = self._write_experiments_registry()
        snap_path = export_snapshot(self.store)
        generate_agent_files(self.store, install_workspace_hooks=False)
        return {
            "graph": str(g_path),
            "active_state": str(s_path),
            "constitution": str(c_path),
            "experiments": str(e_path),
            "snapshot": str(snap_path),
        }

    def _file_link(self, label: str, rel_path: str) -> str:
        abs_p = (self.root / rel_path).as_posix()
        return f"[{label}](file://{abs_p})"

    def _write_memory_graph(self) -> Path:
        meta = self.store.get_all_meta()
        proj = meta.get("project_name") or self.root.name
        proposals = self.store.list_nodes(node_types=[NodeType.PROPOSAL.value], limit=20)
        bottlenecks = self.store.list_nodes(node_types=[NodeType.BOTTLENECK.value], limit=15)
        knodes = self.store.list_nodes(
            node_types=[NodeType.KNOWLEDGE_NODE.value, NodeType.OBSERVATION.value, NodeType.METHOD_CARD.value], limit=30
        )
        ideas = self.store.list_nodes(
            node_types=[NodeType.IDEA.value, NodeType.ALGORITHM.value], limit=25
        )

        lines: List[str] = [
            f"# 🧠 00. MASTER MEMORY & KNOWLEDGE GRAPH — {proj.upper()}",
            "",
            "> **Purpose:** Central Compaction-Proof Persistent Knowledge Graph. Whether after `/compact`, multi-GB sessions, or switching across Antigravity / Claude Code / Cursor / Codex, reading `01_ACTIVE_STATE.md` + `02_CONSTITUTION_AND_LESSONS.md` (or running `supermemory status`) restores **100% project context, laws, proposals, experiments, and past mistakes** in < 2 seconds.",
            "",
            "## 🗺️ 1. Memory Graph Topology",
            "",
            "```mermaid",
            "flowchart TD",
            '    ROOT["AGENTS.md<br/>(Canonical Always-On Rule + @AGENTS.md Pointer)"] --> MG["memory/00_MEMORY_GRAPH.md<br/>(Central Graph Index)"]',
            '    HOOKS["hooks.json + MCP Server<br/>(SessionStart / PreInvocation / PreToolUse / Stop)"] --> DB[(".supermemory/supermemory.db<br/>SQLite FTS5 + Gates")]',
            '    DB <--> MG',
            '    MG --> STATE["memory/01_ACTIVE_STATE.md<br/>(Live Goals & Next Steps < 150L)"]',
            '    MG --> CONST["memory/02_CONSTITUTION_AND_LESSONS.md<br/>(Laws + Gate Bindings < 200L)"]',
            '    MG --> EXPS["memory/03_EXPERIMENTS_REGISTRY.md<br/>(Scientific Ablation Ledger)"]',
            '    MG --> PROPS["memory/04_PROPOSALS/<br/>(OpenSpec Lifecycle Artifacts)"]',
            '    MG --> IDEAS["memory/05_IDEAS_AND_ALGORITHMS/<br/>(Idea Vault & Dead-End Memory)"]',
            '    MG --> MVAULT["memory/07_METHOD_VAULT/<br/>(Harvested SOTA Method Cards)"]',
            '    MG --> BNKS["memory/08_BOTTLENECKS/<br/>(Pareto Error Slices & RQs)"]',
            "```",
            "",
            "## 📑 2. Core Memory Nodes",
            "",
            "| Node ID | File Link | Role & Mandatory Protocol |",
            "| :--- | :--- | :--- |",
            f"| **`MEM-00`** | {self._file_link('00_MEMORY_GRAPH.md', 'memory/00_MEMORY_GRAPH.md')} | Central topology & clickable index of all memory entities. |",
            f"| **`MEM-01`** | {self._file_link('01_ACTIVE_STATE.md', 'memory/01_ACTIVE_STATE.md')} | Live goals, targets, active proposals & next actions. Read first; update atomically every milestone. |",
            f"| **`MEM-02`** | {self._file_link('02_CONSTITUTION_AND_LESSONS.md', 'memory/02_CONSTITUTION_AND_LESSONS.md')} | **Anti-Regression Constitution (`< 200` lines).** Read 100% in 1 call before acting. |",
            f"| **`MEM-03`** | {self._file_link('03_EXPERIMENTS_REGISTRY.md', 'memory/03_EXPERIMENTS_REGISTRY.md')} | Master scientific experiment & ablation ledger across all tracks. |",
            f"| **`MEM-SNAP`** | {self._file_link('graph_snapshot.json', 'memory/graph_snapshot.json')} | Portable Git-versioned property graph snapshot auto-hydrating SQLite + Web UI. |",
        ]

        if bottlenecks:
            lines.extend(["", "## 🎯 2B. Pareto Bottlenecks & Research Questions", "", "| ID | Status | Share | Ceiling | Title |", "| :--- | :---: | :---: | :---: | :--- |"])
            for b in bottlenecks[:10]:
                sh = b.metadata.get("error_share_pct", "—")
                cg = b.metadata.get("ceiling_gain", "—")
                lines.append(f"| **`{b.id}`** | `{b.status}` | `{sh}%` | `+{cg}` | {_md_cell(b.title, 85)} |")

        if proposals:
            lines.extend(["", "## 🚀 3. Lifecycle Proposals (`IDEA -> DESIGN -> IMPLEMENT -> CHALLENGE -> AUDIT`)", "", "| ID | Stage | Title | Artifact |", "| :--- | :---: | :--- | :--- |"])
            for p in proposals:
                lnk = self._file_link(Path(p.file_path).name, p.file_path) if p.file_path else "—"
                lines.append(f"| **`{p.id}`** | `{p.status}` | {_md_cell(p.title, 90)} | {lnk} |")

        if ideas:
            lines.extend(["", "## 💡 4. Ideas, Algorithms & Dead-End Memory", "", "| ID | Type | Status | Title & Summary |", "| :--- | :---: | :---: | :--- |"])
            for i in ideas[:15]:
                lines.append(f"| **`{i.id}`** | `{i.node_type}` | `{i.status}` | **{_md_cell(i.title, 60)}** — {_md_cell(i.summary, 110)} |")

        if knodes:
            lines.extend(["", "## 📚 5. Domain Knowledge & Observation Nodes", "", "| ID | Type | Title | File |", "| :--- | :---: | :--- | :--- |"])
            for k in knodes[:20]:
                lnk = self._file_link(Path(k.file_path).name, k.file_path) if k.file_path else "—"
                lines.append(f"| **`{k.id}`** | `{k.node_type}` | {_md_cell(k.title, 95)} | {lnk} |")

        out = self.mem_dir / "00_MEMORY_GRAPH.md"
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return out

    def _write_active_state(self) -> Path:
        meta = self.store.get_all_meta()
        proj = meta.get("project_name") or self.root.name
        goal = meta.get("active_goal") or "Deliver verified, generalizable milestones with 0 regressions."
        phase = meta.get("current_phase") or "ACTIVE_DEVELOPMENT"
        targets = meta.get("primary_targets") or "100% test/lint/type gate pass; 0 repeated mistakes."
        next_act = meta.get("next_actions") or "1. Check recall before proposing changes.\n2. Log experiments & lessons atomically."
        notes = meta.get("state_notes") or ""

        proposals = [
            p for p in self.store.list_nodes(node_types=[NodeType.PROPOSAL.value], limit=8)
            if p.status not in ("ARCHIVED", "REJECTED")
        ]
        open_bnks = [
            b for b in self.store.list_nodes(node_types=[NodeType.BOTTLENECK.value], limit=6)
            if b.status not in ("RESOLVED", "ARCHIVED")
        ]
        exps = self.store.list_experiments()[-8:]
        gates = self.store.list_gates(enabled_only=True)
        total_blocks = sum(g.blocked_count for g in gates)

        lines: List[str] = [
            f"# 📍 01. ACTIVE PROJECT STATE — {proj.upper()}",
            "",
            f"**Last Synced:** `{utc_now_iso()}` | **Phase:** `{phase}` | **Active Gates:** `{len(gates)}` (`{total_blocks}` regressions blocked)",
            "",
            "---",
            "",
            "## 🎯 1. Active Strategic Goal & Targets",
            f"- **Primary Objective:** {goal}",
            f"- **Success Metrics / SLA Targets:** {targets}",
            "",
            "## ⚡ 2. Immediate Next Actions",
        ]
        for ln in next_act.splitlines():
            clean = ln.strip()
            if clean:
                lines.append(clean if clean.startswith(("-", "*", "1.", "2.", "3.")) else f"- {clean}")

        if notes.strip():
            lines.extend(["", "## 🧭 3. Architecture & Operational Context", notes.strip()[:1800]])

        if open_bnks:
            lines.extend(["", "## 🎯 3B. Open Pareto Bottlenecks", ""])
            for b in open_bnks[:4]:
                lines.append(f"- **`{b.id}`** (`{b.metadata.get('error_share_pct', 0)}%` err | `+{b.metadata.get('ceiling_gain', 0)}` ceil): {b.title}")

        mcards = [
            m for m in self.store.list_nodes(node_types=[NodeType.METHOD_CARD.value], limit=6)
            if m.status not in ("REJECTED", "ARCHIVED", "CONSOLIDATED")
        ]
        if mcards:
            lines.extend(["", "## 📚 3C. Harvested SOTA Method Vault (`07_METHOD_VAULT`)", ""])
            for mc in mcards[:4]:
                tgt = mc.metadata.get("bottleneck_id") or "General"
                lines.append(f"- **`{mc.id}`** (`{mc.metadata.get('venue', 'SOTA')} {mc.metadata.get('year', '')}` -> `{tgt}`): {mc.title}")

        if proposals:
            lines.extend(["", "## 📋 4. Active Proposals", ""])
            for pr in proposals[:5]:
                lines.append(f"- **`{pr.id}`** (`{pr.status}`): {pr.title} — {_md_cell(pr.summary, 130)}")

        if exps:
            lines.extend(["", "## 🧪 5. Latest Experiments Snapshot", ""])
            for ex in reversed(exps):
                delta_str = f" (Δ={ex.delta_vs_baseline:+g})" if ex.delta_vs_baseline is not None else ""
                lines.append(
                    f"- **`{ex.exp_id}`** [`{ex.track}` | `{ex.verdict}`]: {ex.title} — "
                    f"CV: `{ex.cv_summary or 'N/A'}` | Test: `{ex.test_summary or 'N/A'}`{delta_str}"
                )

        out = self.mem_dir / "01_ACTIVE_STATE.md"
        out.write_text("\n".join(lines[:145]) + "\n", encoding="utf-8")
        return out

    def _write_constitution(self) -> Path:
        laws: List[MemoryNode] = sorted(
            self.store.list_nodes(node_types=[NodeType.LAW.value], limit=50), key=lambda x: x.id
        )
        lessons: List[MemoryNode] = sorted(
            self.store.list_nodes(node_types=[NodeType.LESSON.value], limit=500), key=lambda x: x.id
        )
        gates_by_law: Dict[str, List[CodeGate]] = {}
        for g in self.store.list_gates(enabled_only=True):
            gates_by_law.setdefault(g.law_id, []).append(g)

        lessons_by_law: Dict[str, List[MemoryNode]] = {}
        for ls in lessons:
            lid = str(ls.metadata.get("law_id") or "LAW-08")
            lessons_by_law.setdefault(lid, []).append(ls)

        lines: List[str] = [
            "# 🛡️ 02. ANTI-REGRESSION CONSTITUTION & DEDUPLICATED LESSONS",
            "",
            "> **⚠️ MANDATORY SINGLE-CALL PROTOCOL (`< 200` Lines Cap):**",
            "> Read this ENTIRE Constitution in 1 `read_file` call before acting. Every lesson is consolidated into a canonical `LAW` bound to deterministic `PreToolUse` / `supermemory audit` CodeGates.",
            "",
            "---",
            "",
            "## ⚖️ PART 1: CANONICAL NON-NEGOTIABLE LAWS & EXECUTABLE GATES",
            "",
        ]
        for lw in laws:
            bound_gates = gates_by_law.get(lw.id, [])
            gate_tags = ", ".join(f"`{g.id}` ({g.gate_type})" for g in bound_gates) or "Policy + Audit"
            merged = lessons_by_law.get(lw.id, [])
            merged_str = f" | Consolidated: `{len(merged)}` lessons" if merged else ""
            lines.append(f"### `{lw.id}` — {lw.title}")
            lines.append(f"- **Rule:** {lw.summary or lw.content[:220]}")
            lines.append(f"- **Enforcement Gates:** {gate_tags}{merged_str}")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## 🗂️ PART 2: CONSOLIDATED HISTORICAL LESSONS LEDGER",
            "",
            "| Law | Consolidated Lessons | Key Anti-Regression Takeaways (Full logs in `memory/lessons/`) |",
            "| :--- | :--- | :--- |",
        ])
        for lw in laws:
            merged = lessons_by_law.get(lw.id, [])
            if not merged:
                continue
            ids_str = ", ".join(f"`{m.id}`" for m in merged[-8:])
            if len(merged) > 8:
                ids_str = f"`+{len(merged) - 8} older`, " + ids_str
            highlights = "; ".join(f"{m.id}: {_md_cell(m.title, 65)}" for m in merged[-4:])
            lines.append(f"| **`{lw.id}`** | {ids_str} | {highlights} |")

        out = self.mem_dir / "02_CONSTITUTION_AND_LESSONS.md"
        out.write_text("\n".join(lines[:195]) + "\n", encoding="utf-8")
        return out

    def _write_experiments_registry(self) -> Path:
        exps = self.store.list_experiments()
        by_track: Dict[str, List] = {}
        for ex in exps:
            by_track.setdefault(ex.track, []).append(ex)

        lines: List[str] = [
            "# 🧪 03. MASTER SCIENTIFIC EXPERIMENT & ABLATION REGISTRY",
            "",
            "> **Rule (`LAW-06`):** Every experiment MUST state an explicit hypothesis, isolate a single-variable diff, verify zero leakage, compare monotonically against a baseline, and store full post-mortem details in `memory/experiments/<track>/<EXP_ID>.md`.",
            "",
        ]
        if not by_track:
            lines.append("_No experiments logged yet. Run `supermemory exp log ...` or call MCP `log_experiment`._")
        for track, items in sorted(by_track.items()):
            lines.extend([
                f"## 📊 Track / Module: `{track.upper()}` (`{len(items)}` Experiments)",
                "",
                "| Exp ID | Verdict | Hypothesis & Single-Variable Diff | Stack | CV Score | Test / LB | Δ vs Base | Log |",
                "| :--- | :---: | :--- | :--- | :---: | :---: | :---: | :--- |",
            ])
            for ex in items:
                delta_s = f"`{ex.delta_vs_baseline:+g}`" if ex.delta_vs_baseline is not None else "—"
                lnk = self._file_link(ex.exp_id, ex.log_path) if ex.log_path else ex.exp_id
                hyp_diff = f"**{_md_cell(ex.title, 55)}**: {_md_cell(ex.single_var_diff or ex.hypothesis, 110)}"
                lines.append(
                    f"| **`{ex.exp_id}`** | `{ex.verdict}` | {hyp_diff} | `{_md_cell(ex.model_stack, 35)}` | "
                    f"`{_md_cell(ex.cv_summary, 28)}` | `{_md_cell(ex.test_summary, 28)}` | {delta_s} | {lnk} |"
                )
            lines.append("")

        out = self.mem_dir / "03_EXPERIMENTS_REGISTRY.md"
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return out
