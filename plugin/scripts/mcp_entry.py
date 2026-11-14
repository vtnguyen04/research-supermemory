#!/usr/bin/env python3
"""Antigravity Stdio MCP Entrypoint for the SuperMemory Plugin."""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_path() -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    bundled_lib = plugin_root / "lib"
    repo_src = plugin_root.parent / "src"
    for candidate in (repo_src, bundled_lib):
        if (candidate / "supermemory").is_dir():
            sys.path.insert(0, str(candidate))
            return


def main() -> int:
    _bootstrap_path()
    from supermemory.mcp.server import run_mcp_stdio_server

    return run_mcp_stdio_server()


if __name__ == "__main__":
    raise SystemExit(main())
