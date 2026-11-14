#!/home/quynhthu/.local/bin/python3.11
"""Antigravity Stdio MCP Entrypoint for the SuperMemory Plugin."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    for _py in (
        "/home/quynhthu/.local/bin/python3.11",
        shutil.which("python3.11"),
        shutil.which("python3.12"),
        shutil.which("python3.13"),
        str(Path.home() / ".local/share/uv/tools/supermemory-harness/bin/python"),
    ):
        if _py and os.path.isfile(_py) and os.access(_py, os.X_OK):
            os.execv(_py, [_py, *sys.argv])


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
