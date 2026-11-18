"""SOLID Hexagonal Command Bus & Declarative Tool Registry (Unit-of-Work Kernel)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from supermemory.cognitive.federation import ensure_global_memory, resolve_default_workspace
from supermemory.storage.snapshot_io import mark_turn_memory_handled
from supermemory.storage.sqlite_store import GraphStore
from supermemory.sync.markdown_compiler import MarkdownCompiler

MutationPredicate = Callable[[Dict[str, Any], Optional[Dict[str, Any]]], bool]
CommandHandler = Callable[[GraphStore, Dict[str, Any]], Dict[str, Any]]
StorelessHandler = Callable[[Dict[str, Any]], Dict[str, Any]]

SCOPE_SCHEMA_PROP: Dict[str, Any] = {
    "type": "string",
    "enum": ["local", "global"],
    "default": "local",
    "description": "Target 'local' project SuperMemory or 'global' (~/.supermemory/global).",
}


@dataclass(frozen=True)
class CommandSpec:
    """Single-source-of-truth specification for a SuperMemory domain command & MCP tool."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Any
    requires_store: bool = True
    mutates_memory: bool | MutationPredicate = True
    clears_lesson_lock: bool = False
    clears_kanban_sync: bool = False
    preserves_dirty_files: bool = False
    is_readonly_research: MutationPredicate | None = None
    fallback_to_global_if_uninit: bool = False

    def check_mutated(self, args: Dict[str, Any], result: Optional[Dict[str, Any]] = None) -> bool:
        if callable(self.mutates_memory):
            return bool(self.mutates_memory(args, result))
        return bool(self.mutates_memory)

    def to_mcp_schema(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


class CommandRegistry:
    """Central registry eliminating multi-file if/elif chains and duplicate UoW boilerplate."""

    def __init__(self) -> None:
        self._specs: Dict[str, CommandSpec] = {}

    def register(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        *,
        requires_store: bool = True,
        mutates_memory: bool | MutationPredicate = True,
        clears_lesson_lock: bool = False,
        clears_kanban_sync: bool = False,
        preserves_dirty_files: bool = False,
        is_readonly_research: MutationPredicate | None = None,
        fallback_to_global_if_uninit: bool = False,
    ) -> Callable[[Any], Any]:
        def _decorator(fn: Any) -> Any:
            self._specs[name] = CommandSpec(
                name=name,
                description=description,
                input_schema=input_schema,
                handler=fn,
                requires_store=requires_store,
                mutates_memory=mutates_memory,
                clears_lesson_lock=clears_lesson_lock,
                clears_kanban_sync=clears_kanban_sync,
                preserves_dirty_files=preserves_dirty_files,
                is_readonly_research=is_readonly_research,
                fallback_to_global_if_uninit=fallback_to_global_if_uninit,
            )
            return fn

        return _decorator

    def get(self, name: str) -> CommandSpec:
        canon = name[12:] if name.startswith("supermemory_") else name
        if canon not in self._specs:
            raise ValueError(f"Unknown SuperMemory command/tool: {name}")
        return self._specs[canon]

    def list_specs(self) -> List[CommandSpec]:
        return list(self._specs.values())

    def mcp_tool_schemas(self) -> List[Dict[str, Any]]:
        return [s.to_mcp_schema() for s in self._specs.values()]

    def classify_mcp_call(
        self,
        t_name: str,
        mcp_srv: str,
        norm_mcp: str,
        inner_args: Dict[str, Any],
    ) -> tuple[bool, bool]:
        """Return `(is_memory_mutation, is_readonly_research)` directly from registered specs."""
        is_sm = "supermemory" in t_name or "supermemory" in mcp_srv or bool(norm_mcp)
        if not is_sm:
            return False, False
        cand = norm_mcp or t_name.split("__")[-1]
        cand = cand[12:] if cand.startswith("supermemory_") else cand
        spec = self._specs.get(cand)
        if spec is None:
            for k, sp in self._specs.items():
                if k in t_name:
                    spec = sp
                    break
        if spec is None:
            return False, False
        ro_res = bool(spec.is_readonly_research(inner_args, None)) if spec.is_readonly_research else False
        return spec.check_mutated(inner_args, None), ro_res

    def execute(
        self,
        name: str,
        args: Dict[str, Any],
        store: Optional[GraphStore] = None,
    ) -> Dict[str, Any]:
        """Execute command inside a managed Unit-of-Work (`GraphStore` + Markdown sync + Attestation)."""
        spec = self.get(name)
        if not spec.requires_store:
            return dict(spec.handler(args))

        if store is not None:
            res = dict(spec.handler(store, args))
            if spec.check_mutated(args, res):
                mark_turn_memory_handled(
                    store,
                    clear_lesson_lock=spec.clears_lesson_lock,
                    clear_kanban_sync=spec.clears_kanban_sync,
                    include_dirty=not spec.preserves_dirty_files,
                )
                MarkdownCompiler(store).compile_all()
            return res

        target_root = self._resolve_target_root(spec, args)
        with GraphStore(target_root) as managed_store:
            res = dict(spec.handler(managed_store, args))
            if spec.check_mutated(args, res):
                mark_turn_memory_handled(
                    managed_store,
                    clear_lesson_lock=spec.clears_lesson_lock,
                    clear_kanban_sync=spec.clears_kanban_sync,
                    include_dirty=not spec.preserves_dirty_files,
                )
                MarkdownCompiler(managed_store).compile_all()
            return res

    @staticmethod
    def _resolve_target_root(spec: CommandSpec, args: Dict[str, Any]) -> Path:
        if str(args.get("scope") or "local").lower() == "global":
            return ensure_global_memory()
        root = resolve_default_workspace(str(args.get("workspace") or ""))
        if (
            spec.fallback_to_global_if_uninit
            and not (root / ".supermemory").is_dir()
            and not (root / "memory" / "graph_snapshot.json").is_file()
        ):
            return ensure_global_memory()
        return root


REGISTRY = CommandRegistry()
