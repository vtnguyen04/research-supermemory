"""Self-audit tests enforcing Clean Code (<300 lines, 0 walrus) and strict Antigravity plugin validity."""

from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _iter_repo_python_files() -> list[Path]:
    files: list[Path] = []
    for folder in ("src", "tests", "plugin/scripts"):
        base = REPO_ROOT / folder
        if base.exists():
            for p in sorted(base.rglob("*.py")):
                if "__pycache__" not in p.parts:
                    files.append(p)
    return files


def test_all_python_files_strictly_under_300_lines() -> None:
    py_files = _iter_repo_python_files()
    assert len(py_files) >= 35
    offenders: list[str] = []
    for p in py_files:
        line_count = len(p.read_text(encoding="utf-8").splitlines())
        if line_count >= 300:
            offenders.append(f"{p.relative_to(REPO_ROOT)} ({line_count} lines)")
    assert not offenders, f"LAW-02 violation (>=300 lines): {offenders}"


def test_zero_walrus_operators_in_ast() -> None:
    offenders: list[str] = []
    for p in _iter_repo_python_files():
        tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        for node in ast.walk(tree):
            if isinstance(node, ast.NamedExpr):
                offenders.append(f"{p.relative_to(REPO_ROOT)}:{node.lineno}")
    assert not offenders, f"Forbidden walrus operator (:=) found: {offenders}"


def test_zero_throwaway_filenames_in_repo() -> None:
    forbidden = re.compile(r"(^|/)(debug_|tmp_|temp_|scratch_|test_hack|.*_v2\.py|.*_copy\.py)")
    bad: list[str] = []
    for p in REPO_ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part in {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"} for part in p.parts):
            continue
        rel = str(p.relative_to(REPO_ROOT)).replace("\\", "/")
        if forbidden.search(rel):
            bad.append(rel)
    assert not bad, f"Throwaway files detected: {bad}"


def test_antigravity_plugin_strict_validation() -> None:
    agy_bin = shutil.which("agy") or str(Path.home() / ".local" / "bin" / "agy")
    assert Path(agy_bin).is_file(), "Antigravity CLI binary `agy` must exist"
    plugin_dir = REPO_ROOT / "plugin"
    proc = subprocess.run(
        [agy_bin, "plugin", "validate", "--strict", "--json", str(plugin_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"agy plugin validate --strict failed:\n{proc.stdout}\n{proc.stderr}"
    report = json.loads(proc.stdout)
    assert report["name"] == "supermemory"
    assert report["components"]["hooks"] == 1
    assert report["components"]["mcpServers"] == 1
    assert report["components"]["rules"] == 1
    assert report["components"]["agents"] >= 4
    assert report["components"]["skills"] >= 7
    assert report["findings"] == []
