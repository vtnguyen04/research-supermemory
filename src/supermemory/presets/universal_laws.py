"""Universal Engineering & AI R&D Laws distilled from ZALOAI's 89 battle lessons."""

from __future__ import annotations

from typing import List, Tuple

from supermemory.models import CodeGate, EdgeType, GateType, MemoryEdge, MemoryNode, NodeType


def build_universal_constitution(max_lines: int = 500) -> Tuple[List[MemoryNode], List[CodeGate], List[MemoryEdge]]:
    """Return canonical seed Laws, executable CodeGates, and ENFORCED_BY edges."""
    laws: List[MemoryNode] = [
        MemoryNode(
            id="LAW-01",
            node_type=NodeType.LAW.value,
            title="Zero Hardcoding, Zero Test-Set Tuning & 100% Statistical Generalization",
            priority=100,
            summary="Never patch failing test/eval samples with sample IDs, dataset-specific entity regexes, or static lookup overrides.",
            content=(
                "All algorithmic improvements MUST generalize statistically and structurally to unseen private/production data. "
                "Inspecting evaluation errors is solely for diagnosing root-cause systemic mechanisms — NEVER for adding "
                "sample-ID conditionals, hardcoded entity dictionaries, or static test-split overrides."
            ),
            tags=["generalization", "anti-leakage", "anti-hardcode"],
        ),
        MemoryNode(
            id="LAW-02",
            node_type=NodeType.LAW.value,
            title=f"Strict SOLID Clean Code (< {max_lines} Lines/File) & Zero Throwaway Scripts",
            priority=98,
            summary=f"Every source file must remain strictly < {max_lines} lines, modular, typed, lint-clean, with zero debug_/tmp_/*_v2 scripts.",
            content=(
                f"Maintain cohesive single-responsibility modules strictly under {max_lines} lines. "
                "Never cram dense unreadable one-liners to bypass line caps, and never leave throwaway debug_*.py, "
                "tmp_*.py, scratch_*.py, or *_v2.py files in the repository."
            ),
            tags=["clean-code", "solid", "modularity"],
        ),
        MemoryNode(
            id="LAW-03",
            node_type=NodeType.LAW.value,
            title="Pre-Flight Test Gate, Early-Stop Guardrails & Root-Cause One-Pass Fixes",
            priority=95,
            summary="Always pass automated unit/type/lint gates before launching benchmarks, and enforce early-stop thresholds.",
            content=(
                "Never launch expensive evaluations blind. Run pytest/ruff/mypy pre-flight checks first, "
                "configure automatic early-stop thresholds on benchmarks so broken runs abort immediately, "
                "and trace root causes across all callers before editing."
            ),
            tags=["testing", "early-stop", "pre-flight"],
        ),
        MemoryNode(
            id="LAW-04",
            node_type=NodeType.LAW.value,
            title="Zero API/Compute Waste, Mandatory Caching & Incremental Checkpoints",
            priority=94,
            summary="Enable prompt/response caching, flush incremental checkpoints, and never wipe valid caches or kill healthy jobs.",
            content=(
                "Treat API credits and GPU hours as scarce capital: enable prompt caching, persist SQLite/JSONL "
                "checkpoints incrementally (including negative/unanswerable results), never pass cache-disabling flags "
                "or rm -f active checkpoints, and respect hardware placement rules (remote GPU vs local laptop)."
            ),
            tags=["cost", "caching", "checkpoints", "compute"],
        ),
        MemoryNode(
            id="LAW-05",
            node_type=NodeType.LAW.value,
            title="Cryptographic Artifact Integrity & True Method Output Separation",
            priority=93,
            summary="Freeze verified baselines/verifiers via SHA-256 and strictly separate method outputs from ground-truth labels.",
            content=(
                "Official deliverables and frozen verifiers are protected by SHA-256 locks. Never overwrite verified "
                "deliverables with unverified runs or ground-truth files, and verify monotonic rank non-regression."
            ),
            tags=["integrity", "sha256", "monotonic"],
        ),
        MemoryNode(
            id="LAW-06",
            node_type=NodeType.LAW.value,
            title="Spec-First Lifecycle & Scientific Single-Variable Experimentation",
            priority=92,
            summary="Track every Idea -> Proposal/Spec -> Hypothesis-Driven Experiment -> Adversarial Challenger & Victory Audit.",
            content=(
                "Before non-trivial implementation, check the Idea/Experiment graph for prior dead-ends, record a clear "
                "Proposal/Spec, isolate single-variable diffs in experiments, measure CV + latency + cost, and require "
                "adversarial Challenger/Victory Audit verification before claiming completion."
            ),
            tags=["lifecycle", "experiments", "openspec", "audit"],
        ),
        MemoryNode(
            id="LAW-07",
            node_type=NodeType.LAW.value,
            title="Atomic Real-Time Memory Sync & Compaction-Proof Handoff",
            priority=99,
            summary="Read Active State + Constitution before acting; commit every result, architecture directive, and decision in the same turn.",
            content=(
                "Never allow memory/01_ACTIVE_STATE.md, 02_CONSTITUTION_AND_LESSONS.md, or 03_EXPERIMENTS_REGISTRY.md "
                "to go stale by even 1 turn. Persist full strategic user architectures immediately so /compact or "
                "switching to another agent loses 0% context."
            ),
            tags=["memory", "compaction-proof", "handoff"],
        ),
        MemoryNode(
            id="LAW-08",
            node_type=NodeType.LAW.value,
            title="Self-Learning Lesson-to-Code-Gate Crystallization",
            priority=100,
            summary="Every user correction or post-mortem failure must consolidate into a Law AND bind an executable CodeGate.",
            content=(
                "Performative markdown apologies without technical enforcement are forbidden. Whenever a mistake or "
                "user correction occurs, dissect the root cause, consolidate into LAW-01..N (keeping the Constitution "
                "< 200 lines), and attach a deterministic PreToolUse / pytest gate so recurrence is physically impossible."
            ),
            tags=["self-learning", "code-gate", "anti-regression"],
        ),
    ]

    gates: List[CodeGate] = [
        CodeGate(
            id="GATE-001",
            gate_type=GateType.MAX_LINES.value,
            name=f"Source File Max {max_lines} Lines",
            law_id="LAW-02",
            target_glob="**/*.py",
            pattern=str(max_lines),
            config={"max_lines": max_lines, "exclude_globs": ["tests/**", ".venv/**", "build/**", "dist/**"]},
        ),
        CodeGate(
            id="GATE-002",
            gate_type=GateType.FORBIDDEN_FILENAME.value,
            name="Ban Throwaway Debug/Tmp/Versioned Scripts",
            law_id="LAW-02",
            target_glob="**/*",
            pattern=r"(^|/)(?:debug_|tmp_|scratch_|temp_)[^/]*\.(?:py|sh|js|ts)$|(^|/)[^/]+_v[2-9]\.py$",
            config={"exclude_globs": ["tests/**", ".supermemory/**"]},
        ),
        CodeGate(
            id="GATE-003",
            gate_type=GateType.AST_SYNTAX.value,
            name="Python AST Syntax Validity Gate",
            law_id="LAW-03",
            target_glob="**/*.py",
            pattern="ast_parse",
            config={},
        ),
        CodeGate(
            id="GATE-004",
            gate_type=GateType.FORBIDDEN_CMD_PATTERN.value,
            name="Protect Checkpoints & Submissions From Destructive rm -f / Cache Wipe",
            law_id="LAW-04",
            target_glob="run_command",
            pattern=r"\brm\s+-[rf]+\s+[^\n]*(?:submission\.jsonl|checkpoint|sql_llm_cache\.sqlite|supermemory\.db)\b|\b(?:DATAMATE_NO_CACHE|LIFEMATE_CACHE_ONLY)=1\b",
            config={},
        ),
    ]

    edges: List[MemoryEdge] = [
        MemoryEdge(source_id=g.law_id, target_id=g.id, relation=EdgeType.ENFORCED_BY.value)
        for g in gates
        if g.law_id
    ]
    return laws, gates, edges
