"""Notebook-only setup helpers for inspection notebooks."""

from pathlib import Path

import pandas as pd


def _find_project_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "data/sample").is_dir():
            return candidate
    raise RuntimeError(
        f"Could not find project root containing pyproject.toml and data/sample from {start}"
    )


PROJECT_ROOT = _find_project_root(Path.cwd().resolve())
SAMPLE_DATA_DIR = PROJECT_ROOT / "data/sample"


def configure_display() -> None:
    """Configure pandas display options for notebook review tables."""

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 160)
