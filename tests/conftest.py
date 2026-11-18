"""Global Pytest Isolation: Never pollute ~/.supermemory/global during test suites."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _isolate_supermemory_global_dir(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide an isolated SUPERMEMORY_GLOBAL_DIR per test (individual tests can still override via monkeypatch)."""
    g_tmp: Path = tmp_path_factory.mktemp("sm_global")
    monkeypatch.setenv("SUPERMEMORY_GLOBAL_DIR", str(g_tmp))
