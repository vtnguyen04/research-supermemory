"""Real-time PreToolUse Gatekeeper and Workspace Constitutional Auditor."""

from __future__ import annotations

import ast
import fnmatch
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from supermemory.models import CodeGate, EdgeType, GateType, MemoryEdge, MemoryNode, NodeType
from supermemory.storage.sqlite_store import GraphStore


def _glob_matches(rel_path: str, pattern: str) -> bool:
    norm = rel_path.replace("\\", "/").lstrip("./")
    pat = pattern.replace("\\", "/")
    if pat in ("**/*", "*"):
        return True
    if pat.startswith("**/"):
        suffix = pat[3:]
        if fnmatch.fnmatch(norm, suffix) or fnmatch.fnmatch(Path(norm).name, suffix):
            return True
    if "/**/" in pat and _glob_matches(norm, pat.replace("/**/", "/", 1)):
        return True
    return fnmatch.fnmatch(norm, pat)


def _is_excluded(rel_path: str, exclude_globs: List[str]) -> bool:
    for ex in exclude_globs:
        prefix = ex.removesuffix("/**").removesuffix("/*")
        if _glob_matches(rel_path, ex) or rel_path == prefix or rel_path.startswith(prefix + "/"):
            return True
    return False


@dataclass
class GateDecision:
    """Outcome of evaluating gates on a tool call or workspace audit."""

    allowed: bool
    violations: List[str] = field(default_factory=list)
    triggered_gate_ids: List[str] = field(default_factory=list)

    @property
    def reason(self) -> str:
        return " | ".join(self.violations)


class GateEnforcer:
    """Evaluates deterministic CodeGates in < 20ms during hooks and CLI audits."""

    def __init__(self, store: GraphStore) -> None:
        self.store = store

    def freeze_file(self, rel_or_abs_path: str, law_id: str = "LAW-05") -> CodeGate:
        """Compute SHA-256 of a target file and register a hard FROZEN_SHA256 gate."""
        p = Path(rel_or_abs_path)
        abs_p = p if p.is_absolute() else (self.store.workspace_root / p)
        abs_p = abs_p.resolve()
        if not abs_p.is_file():
            raise FileNotFoundError(f"Cannot freeze missing file: {abs_p}")
        rel = str(abs_p.relative_to(self.store.workspace_root)).replace("\\", "/")
        sha = hashlib.sha256(abs_p.read_bytes()).hexdigest()
        gate_id = f"GATE-SHA-{hashlib.md5(rel.encode('utf-8')).hexdigest()[:6].upper()}"
        gate = self.store.upsert_gate(
            CodeGate(
                id=gate_id,
                gate_type=GateType.FROZEN_SHA256.value,
                name=f"Frozen SHA-256 Lock: {rel}",
                law_id=law_id,
                target_glob=rel,
                pattern=sha,
                config={"file": rel, "sha256": sha},
            )
        )
        self.store.upsert_node(
            MemoryNode(
                id=gate_id,
                node_type=NodeType.GATE.value,
                title=gate.name,
                summary=f"SHA-256 locked: `{rel}` = `{sha[:16]}...`",
                file_path=rel,
                tags=["gate", "frozen-sha256", law_id.lower()],
                priority=97,
                metadata=gate.to_dict(),
            ),
            log_event=False,
        )
        self.store.add_edge(MemoryEdge(source_id=law_id, target_id=gate_id, relation=EdgeType.ENFORCED_BY.value))
        self.store.log_event("GATE_FROZEN", gate_id, f"SHA-256 locked {rel} ({law_id})")
        return gate

    def evaluate_tool_call(self, tool_name: str, tool_args: Dict[str, Any]) -> GateDecision:
        """Evaluate active gates before write_file, edit_file, or run_command executes."""
        t_low = (tool_name or "").lower()
        gates = self.store.list_gates(enabled_only=True)
        violations: List[str] = []
        triggered: List[str] = []

        if t_low in ("run_command", "bash"):
            cmd = str(tool_args.get("CommandLine") or tool_args.get("command") or "")
            for g in gates:
                if g.gate_type == GateType.FORBIDDEN_CMD_PATTERN.value and g.pattern:
                    if re.search(g.pattern, cmd):
                        msg = f"[{g.id}/{g.law_id or 'LAW'}] Blocked command matching `{g.name}`"
                        violations.append(msg)
                        triggered.append(g.id)
                        self.store.record_gate_block(g.id, f"{msg}: {cmd[:120]}")
            return GateDecision(allowed=not violations, violations=violations, triggered_gate_ids=triggered)

        if t_low in ("write_file", "edit_file", "write", "edit", "multiedit", "replace_file_content", "multi_replace_file_content"):
            raw_path = str(tool_args.get("Path") or tool_args.get("TargetFile") or tool_args.get("file_path") or "")
            if not raw_path:
                return GateDecision(allowed=True)
            abs_p = (Path(raw_path) if Path(raw_path).is_absolute() else (self.store.workspace_root / raw_path)).resolve()
            if not abs_p.is_relative_to(self.store.workspace_root):
                return GateDecision(allowed=True)
            rel = str(abs_p.relative_to(self.store.workspace_root)).replace("\\", "/")
            candidate_text = self._simulate_file_text(t_low, abs_p, tool_args)
            return self._check_file_gates(rel, candidate_text, gates, record_blocks=True, is_mutation=True)

        return GateDecision(allowed=True)

    def audit_workspace(self, log_audit: bool = False) -> Dict[str, Any]:
        """Run full-workspace constitutional & memory health checks."""
        gates = self.store.list_gates(enabled_only=True)
        violations: List[str] = []
        checked_files = 0
        skip_dirs = {".git", ".venv", "venv", "node_modules", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".supermemory", "dist", "build"}

        for p in sorted(self.store.workspace_root.rglob("*")):
            if not p.is_file():
                continue
            rel_parts = p.relative_to(self.store.workspace_root).parts
            if any(part in skip_dirs for part in rel_parts):
                continue
            rel = "/".join(rel_parts)
            checked_files += 1
            try:
                text = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = ""
            dec = self._check_file_gates(rel, text, gates, record_blocks=False, is_mutation=False, disk_path=p)
            violations.extend(dec.violations)

        # Memory Constitution & Active State line-budget invariants (LAW-07, LAW-08)
        const_file = self.store.mem_dir / "02_CONSTITUTION_AND_LESSONS.md"
        if const_file.is_file():
            c_lines = len(const_file.read_text(encoding="utf-8").splitlines())
            if c_lines >= 250:
                violations.append(f"[LAW-08] 02_CONSTITUTION_AND_LESSONS.md has {c_lines} lines (>= 250 limit)")

        state_file = self.store.mem_dir / "01_ACTIVE_STATE.md"
        if state_file.is_file():
            s_lines = len(state_file.read_text(encoding="utf-8").splitlines())
            if s_lines >= 180:
                violations.append(f"[LAW-07] 01_ACTIVE_STATE.md has {s_lines} lines (>= 180 limit)")

        if log_audit:
            ev_kind = "GATE_AUDIT_PASSED" if not violations else "GATE_AUDIT_FAILED"
            self.store.log_event(
                ev_kind,
                "WORKSPACE_AUDIT",
                f"Audited {checked_files} files across {len(gates)} gates: {len(violations)} violations",
            )
        return {
            "passed": len(violations) == 0,
            "checked_files": checked_files,
            "active_gates": len(gates),
            "violation_count": len(violations),
            "violations": violations,
        }

    def _check_file_gates(
        self,
        rel: str,
        text: str,
        gates: List[CodeGate],
        record_blocks: bool,
        is_mutation: bool,
        disk_path: Path | None = None,
    ) -> GateDecision:
        violations: List[str] = []
        triggered: List[str] = []
        lines = text.splitlines()

        for g in gates:
            excludes = list(g.config.get("exclude_globs") or [])
            if _is_excluded(rel, excludes) or not _glob_matches(rel, g.target_glob):
                continue

            if g.gate_type == GateType.FROZEN_SHA256.value:
                if is_mutation:
                    new_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
                    if new_sha != g.pattern:
                        msg = f"[{g.id}/{g.law_id}] FROZEN FILE VIOLATION: `{rel}` is SHA-256 locked."
                        violations.append(msg)
                        triggered.append(g.id)
                elif disk_path is not None:
                    actual_sha = hashlib.sha256(disk_path.read_bytes()).hexdigest()
                    if actual_sha != g.pattern:
                        violations.append(f"[{g.id}/{g.law_id}] Frozen SHA-256 mismatch on `{rel}`")

            elif g.gate_type == GateType.FORBIDDEN_FILENAME.value and g.pattern:
                if re.search(g.pattern, rel):
                    msg = f"[{g.id}/{g.law_id}] Throwaway/forbidden filename `{rel}` violates `{g.name}`"
                    violations.append(msg)
                    triggered.append(g.id)

            elif g.gate_type == GateType.MAX_LINES.value:
                cap = int(g.config.get("max_lines") or g.pattern or 300)
                if len(lines) >= cap:
                    msg = f"[{g.id}/{g.law_id}] `{rel}` has {len(lines)} lines (must be < {cap}). Split into cohesive modules."
                    violations.append(msg)
                    triggered.append(g.id)

            elif g.gate_type == GateType.AST_SYNTAX.value and rel.endswith(".py") and text.strip():
                try:
                    ast.parse(text, filename=rel)
                except SyntaxError as exc:
                    msg = f"[{g.id}/{g.law_id}] Python SyntaxError in `{rel}:{exc.lineno}`: {exc.msg}"
                    violations.append(msg)
                    triggered.append(g.id)

            elif g.gate_type == GateType.FORBIDDEN_REGEX.value and g.pattern and text:
                ignore_comments = bool(g.config.get("ignore_comments", True))
                for idx, ln in enumerate(lines, 1):
                    if ignore_comments and ln.lstrip().startswith("#"):
                        continue
                    if re.search(g.pattern, ln):
                        msg = f"[{g.id}/{g.law_id}] Forbidden pattern in `{rel}:{idx}` ({g.name}): `{ln.strip()[:90]}`"
                        violations.append(msg)
                        triggered.append(g.id)
                        break

        if record_blocks:
            for gid, msg in zip(triggered, violations):
                self.store.record_gate_block(gid, msg)
        return GateDecision(allowed=not violations, violations=violations, triggered_gate_ids=triggered)

    @staticmethod
    def _simulate_file_text(tool_low: str, abs_p: Path, args: Dict[str, Any]) -> str:
        existing = abs_p.read_text(encoding="utf-8") if abs_p.is_file() else ""
        if tool_low in ("write_file", "write"):
            content = str(args.get("Content") or args.get("content") or "")
            return (existing + content) if args.get("Append") else content
        if tool_low in ("edit_file", "edit"):
            target = str(args.get("Target") or args.get("old_string") or "")
            repl = str(args.get("Replacement") or args.get("new_string") or "")
            return existing.replace(target, repl) if (target and target in existing) else existing
        if tool_low == "multiedit":
            cur = existing
            for ed in args.get("edits") or []:
                if isinstance(ed, dict):
                    t = str(ed.get("old_string") or "")
                    r = str(ed.get("new_string") or "")
                    if t and t in cur:
                        cur = cur.replace(t, r)
            return cur
        return existing
