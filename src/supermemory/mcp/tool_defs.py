"""Thin MCP Transport Adapter delegating 100% to the Hexagonal CommandRegistry (`kernel`)."""

from __future__ import annotations

from typing import Any, Dict

from supermemory.kernel import execute_command, get_mcp_tools

MCP_TOOLS = get_mcp_tools()


def execute_mcp_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch any MCP tool call through the unified Unit-of-Work Kernel."""
    return execute_command(name, args)


__all__ = ["MCP_TOOLS", "execute_mcp_tool"]
