"""Research MCP Compatibility Facade backed by `supermemory.kernel`."""

from __future__ import annotations

from typing import Any, Dict

from supermemory.kernel import execute_command, get_mcp_tools
from supermemory.storage.sqlite_store import GraphStore

RESEARCH_TOOL_NAMES = {"diagnose_bottleneck", "scout_sota", "orchestrate"}
RESEARCH_MCP_TOOLS = [t for t in get_mcp_tools() if t["name"] in RESEARCH_TOOL_NAMES]


def execute_research_mcp_tool(name: str, store: GraphStore, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a research tool against an open GraphStore via the unified Kernel."""
    return execute_command(name, args, store=store)


__all__ = ["RESEARCH_MCP_TOOLS", "RESEARCH_TOOL_NAMES", "execute_research_mcp_tool"]
