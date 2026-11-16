"""SuperMemory: Tiered Cognitive Graph, Bottleneck-First Research Engine & Dual-Harness Studio."""

from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def resolve_live_version() -> str:
    """Single source of truth: read live version from repo pyproject.toml or installed package metadata."""
    pyproj = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if pyproj.is_file():
        m = re.search(r'^version\s*=\s*"([^"]+)"', pyproj.read_text(encoding="utf-8"), re.MULTILINE)
        if m:
            return m.group(1)
    try:
        return version("research-supermemory")
    except PackageNotFoundError:
        return "3.3.0"


__version__ = resolve_live_version()

__all__ = ["__version__", "resolve_live_version"]
