"""Model Context Protocol (MCP) server for SuperMemory."""

from __future__ import annotations


def run_mcp_stdio_server() -> int:
    """Lazily load and run the stdio JSON-RPC MCP server."""
    from supermemory.mcp.server import run_mcp_stdio_server as _run

    return _run()


__all__ = ["run_mcp_stdio_server"]
