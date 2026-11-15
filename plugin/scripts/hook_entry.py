#!/usr/bin/env python3
"""Antigravity Lifecycle Hook Entrypoint for the SuperMemory Plugin (Cross-Platform Portable)."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

if sys.version_info < (3, 10):
    _home = Path.home()
    for _py in (
        str(_home / ".local/share/uv/tools/supermemory-harness/bin/python"),
        str(_home / ".local/share/supermemory-venv/bin/python"),
        str(_home / ".local/bin/python3.13"),
        str(_home / ".local/bin/python3.12"),
        str(_home / ".local/bin/python3.11"),
        str(_home / ".local/bin/python3.10"),
        shutil.which("python3.13"),
        shutil.which("python3.12"),
        shutil.which("python3.11"),
        shutil.which("python3.10"),
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
    from supermemory.hooks.runner import main_from_stdin

    event_name = sys.argv[1] if len(sys.argv) > 1 else "PreInvocation"
    return main_from_stdin(event_name)


if __name__ == "__main__":
    raise SystemExit(main())
