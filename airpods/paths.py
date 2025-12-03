"""Helpers for resolving project and configuration paths."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

REPO_SENTINELS: Iterable[str] = (".git", "pyproject.toml", "uv.lock")


def detect_repo_root(start: Optional[Path] = None) -> Optional[Path]:
    """Walk upward from ``start`` (default: cwd) to find the repo root."""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if any((candidate / marker).exists() for marker in REPO_SENTINELS):
            return candidate
    return None
