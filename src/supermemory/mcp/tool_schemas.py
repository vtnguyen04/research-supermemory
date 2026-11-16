"""MCP Tool Schema Facade backed by `supermemory.kernel.get_mcp_tools()`."""

from __future__ import annotations

from supermemory.kernel import get_mcp_tools

MCP_TOOLS = get_mcp_tools()

__all__ = ["MCP_TOOLS"]
