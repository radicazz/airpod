"""Runtime mode detection (production vs development)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from airpods.paths import detect_repo_root


@lru_cache(maxsize=1)
def is_dev_mode() -> bool:
    """
    Detect if running in development mode.

    Dev mode is enabled when:
    - The AIRPODS_DEV_MODE environment variable is set to '1'
    - The airpods package is located within a git repository

    Explicit override via AIRPODS_DEV_MODE takes precedence.

    Returns:
        True if in development mode, False for production mode.
    """
    # Check for explicit override first
    env_mode = os.environ.get("AIRPODS_DEV_MODE")
    if env_mode == "1":
        return True
    if env_mode == "0":
        return False

    # Auto-detect: is the airpods package inside a git repository?
    package_path = (
        Path(__file__).resolve().parent
    )  # airpods/runtime_mode.py -> airpods/
    repo_root = detect_repo_root(package_path)
    return repo_root is not None


def get_resource_prefix() -> str:
    """
    Get the resource prefix for Podman resources based on mode.

    Returns:
        'airpods-dev' in dev mode, 'airpods' in production mode.
    """
    return "airpods-dev" if is_dev_mode() else "airpods"


def get_mode_name() -> str:
    """
    Get a human-readable mode name.

    Returns:
        'development' or 'production'
    """
    return "development" if is_dev_mode() else "production"
