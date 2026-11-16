"""SuperMemory Hexagonal Application Kernel: Unified Command Bus for CLI, MCP, Web API & Hooks."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from supermemory.kernel import governance_cmds as _gov  # noqa: F401
from supermemory.kernel import knowledge_cmds as _know  # noqa: F401
from supermemory.kernel import lifecycle_cmds as _life  # noqa: F401
from supermemory.kernel import research_cmds as _res  # noqa: F401
from supermemory.kernel.registry import REGISTRY, CommandRegistry, CommandSpec
from supermemory.storage.sqlite_store import GraphStore


def execute_command(
    name: str,
    args: Dict[str, Any],
    store: Optional[GraphStore] = None,
) -> Dict[str, Any]:
    """Execute any registered SuperMemory domain command through the shared Unit-of-Work Kernel."""
    return REGISTRY.execute(name, args, store=store)


def get_mcp_tools() -> List[Dict[str, Any]]:
    """Return all MCP JSON tool schemas directly from the single CommandRegistry."""
    return REGISTRY.mcp_tool_schemas()


def classify_mcp_call(
    t_name: str,
    mcp_srv: str,
    norm_mcp: str,
    inner_args: Dict[str, Any],
) -> tuple[bool, bool]:
    """Check `(is_memory_mutation, is_readonly_research)` from CommandSpec metadata."""
    return REGISTRY.classify_mcp_call(t_name, mcp_srv, norm_mcp, inner_args)


__all__ = [
    "REGISTRY",
    "CommandRegistry",
    "CommandSpec",
    "classify_mcp_call",
    "execute_command",
    "get_mcp_tools",
]
