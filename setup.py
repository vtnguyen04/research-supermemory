"""Setuptools hook that embeds `plugin/` into wheel builds (`supermemory/_plugin_bundle`)."""

from __future__ import annotations

import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py


class BuildPyWithPlugin(_build_py):
    """Copy top-level `plugin/` assets into built wheel so `supermemory install-plugin` works anywhere."""

    def run(self) -> None:
        super().run()
        repo_plugin = Path(__file__).resolve().parent / "plugin"
        if not repo_plugin.is_dir():
            return
        dest = Path(self.build_lib) / "supermemory" / "_plugin_bundle"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(
            repo_plugin,
            dest,
            ignore=shutil.ignore_patterns("lib", "__pycache__", "*.pyc"),
        )


setup(cmdclass={"build_py": BuildPyWithPlugin})
