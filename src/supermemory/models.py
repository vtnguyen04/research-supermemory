"""Core domain models and lifecycle enums for the SuperMemory Knowledge Graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class NodeType(str, Enum):
    """Canonical node types in the project knowledge graph."""

    LAW = "LAW"
    PROCEDURE = "PROCEDURE"
    LESSON = "LESSON"
    GATE = "GATE"
    IDEA = "IDEA"
    ALGORITHM = "ALGORITHM"
    PROPOSAL = "PROPOSAL"
    EXPERIMENT = "EXPERIMENT"
    OBSERVATION = "OBSERVATION"
    DECISION = "DECISION"
    TASK = "TASK"
    KNOWLEDGE_NODE = "KNOWLEDGE_NODE"
    ARTIFACT = "ARTIFACT"
    AGENT_RUN = "AGENT_RUN"


class MemoryTier(str, Enum):
    """Cognitive architecture memory tiers (CoALA / ACT-R progressive disclosure)."""

    WORKING = "WORKING"
    PROCEDURAL = "PROCEDURAL"
    SEMANTIC = "SEMANTIC"
    EPISODIC = "EPISODIC"


class EdgeType(str, Enum):
    """Typed directed relationships across graph entities."""

    CONSOLIDATED_INTO = "CONSOLIDATED_INTO"
    ENFORCED_BY = "ENFORCED_BY"
    BLOCKS_RECURRENCE_OF = "BLOCKS_RECURRENCE_OF"
    INSPIRED = "INSPIRED"
    PROMOTED_TO = "PROMOTED_TO"
    IMPLEMENTS = "IMPLEMENTS"
    TESTS_HYPOTHESIS = "TESTS_HYPOTHESIS"
    DERIVED_FROM = "DERIVED_FROM"
    IMPROVES_OVER = "IMPROVES_OVER"
    REGRESSED_FROM = "REGRESSED_FROM"
    PRODUCED_LESSON = "PRODUCED_LESSON"
    MODIFIES = "MODIFIES"
    FREEZES = "FREEZES"
    SUPERSEDES = "SUPERSEDES"
    AUDITED_BY = "AUDITED_BY"
    REFERENCES = "REFERENCES"


class GateType(str, Enum):
    """Deterministic enforcement gates evaluated at PreToolUse and CI audit."""

    MAX_LINES = "MAX_LINES"
    FORBIDDEN_FILENAME = "FORBIDDEN_FILENAME"
    FORBIDDEN_REGEX = "FORBIDDEN_REGEX"
    FROZEN_SHA256 = "FROZEN_SHA256"
    FORBIDDEN_CMD_PATTERN = "FORBIDDEN_CMD_PATTERN"
    AST_SYNTAX = "AST_SYNTAX"


class ProposalStage(str, Enum):
    """OpenSpec-inspired 9-stage R&D lifecycle state machine."""

    IDEA = "IDEA"
    PROPOSED = "PROPOSED"
    DESIGNED = "DESIGNED"
    SPECIFIED = "SPECIFIED"
    READY = "READY"
    IMPLEMENTING = "IMPLEMENTING"
    CHALLENGED = "CHALLENGED"
    AUDITED = "AUDITED"
    ARCHIVED = "ARCHIVED"
    REJECTED = "REJECTED"


class ExperimentVerdict(str, Enum):
    """Outcome classification for scientific experiments."""

    PENDING = "PENDING"
    VICTORY_CONFIRMED = "VICTORY_CONFIRMED"
    KEEP = "KEEP"
    REVERT = "REVERT"
    PARK = "PARK"
    FAILED = "FAILED"


@dataclass
class MemoryNode:
    """Universal typed vertex in the SuperMemory Property Graph."""

    id: str
    node_type: str
    title: str
    status: str = "ACTIVE"
    summary: str = ""
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    file_path: str = ""
    tags: List[str] = field(default_factory=list)
    priority: int = 50
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "node_type": self.node_type,
            "title": self.title,
            "status": self.status,
            "summary": self.summary,
            "content": self.content,
            "metadata": self.metadata,
            "file_path": self.file_path,
            "tags": self.tags,
            "priority": self.priority,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class MemoryEdge:
    """Directed typed edge connecting two MemoryNodes."""

    source_id: str
    target_id: str
    relation: str
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation,
            "weight": self.weight,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


@dataclass
class CodeGate:
    """Executable guard binding a Constitutional Law/Lesson to hard runtime checks."""

    id: str
    gate_type: str
    name: str
    law_id: str = ""
    lesson_id: str = ""
    target_glob: str = "**/*"
    pattern: str = ""
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    blocked_count: int = 0
    last_blocked_at: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "gate_type": self.gate_type,
            "name": self.name,
            "law_id": self.law_id,
            "lesson_id": self.lesson_id,
            "target_glob": self.target_glob,
            "pattern": self.pattern,
            "config": self.config,
            "enabled": self.enabled,
            "blocked_count": self.blocked_count,
            "last_blocked_at": self.last_blocked_at,
            "created_at": self.created_at,
        }


@dataclass
class ExperimentRecord:
    """Structured scientific experiment entry linked to graph lineage."""

    exp_id: str
    track: str
    title: str
    hypothesis: str
    single_var_diff: str
    model_stack: str = ""
    baseline_id: str = ""
    proposal_id: str = ""
    cv_score: Optional[float] = None
    cv_summary: str = ""
    test_score: Optional[float] = None
    test_summary: str = ""
    delta_vs_baseline: Optional[float] = None
    runtime_summary: str = ""
    verdict: str = ExperimentVerdict.PENDING.value
    leakage_audit: str = "CLEAN"
    post_mortem: str = ""
    log_path: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exp_id": self.exp_id,
            "track": self.track,
            "title": self.title,
            "hypothesis": self.hypothesis,
            "single_var_diff": self.single_var_diff,
            "model_stack": self.model_stack,
            "baseline_id": self.baseline_id,
            "proposal_id": self.proposal_id,
            "cv_score": self.cv_score,
            "cv_summary": self.cv_summary,
            "test_score": self.test_score,
            "test_summary": self.test_summary,
            "delta_vs_baseline": self.delta_vs_baseline,
            "runtime_summary": self.runtime_summary,
            "verdict": self.verdict,
            "leakage_audit": self.leakage_audit,
            "post_mortem": self.post_mortem,
            "log_path": self.log_path,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }
