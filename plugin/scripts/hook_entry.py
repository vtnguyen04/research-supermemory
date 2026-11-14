#!/usr/bin/env python3
"""Antigravity Lifecycle Hook Entrypoint for the SuperMemory Plugin."""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_path() -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    bundled_lib = plugin_root / "lib"
    repo_src = plugin_root.parent / "src"
    for candidate in (bundled_lib, repo_src):
        if (candidate / "supermemory").is_dir():
            sys.path.insert(0, str(candidate))
            return


def main() -> int:
    _bootstrap_path()
    from supermemory.hooks.runner import main_from_stdin

    event_name = sys.argv[1] if len(sys.argv) > 1 else "PreInvocation"
    return main_from_stdin(event_name)


if __name__ == "__main__":
    raise SystemExit(main())
