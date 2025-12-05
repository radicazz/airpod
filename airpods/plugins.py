"""Plugin management utilities for Open WebUI."""

from __future__ import annotations

import shutil
from pathlib import Path

from airpods.logging import console
from airpods.paths import detect_repo_root
from airpods.state import volumes_dir


def get_plugins_source_dir() -> Path:
    """Get the source directory containing bundled plugins."""
    source_root = detect_repo_root(Path(__file__).resolve())
    if source_root is None:
        # When installed as a package, fall back to the site-packages root
        source_root = Path(__file__).resolve().parent.parent
    return source_root / "plugins" / "open-webui"


def get_plugins_target_dir() -> Path:
    """Get the target directory where plugins should be copied."""
    return volumes_dir() / "webui_plugins"


def sync_plugins(force: bool = False) -> int:
    """Sync bundled plugins to the webui_plugins volume directory.

    Args:
        force: If True, overwrite existing plugins even if they're newer.

    Returns:
        Number of plugins synced.
    """
    source_dir = get_plugins_source_dir()
    target_dir = get_plugins_target_dir()

    if not source_dir.exists():
        console.print(f"[warn]Plugin source directory not found: {source_dir}[/]")
        return 0

    target_dir.mkdir(parents=True, exist_ok=True)

    synced = 0
    plugin_files = [
        p
        for p in source_dir.glob("*.py")
        if p.name != "__init__.py" and not p.name.startswith("_")
    ]
    desired_names = {p.name for p in plugin_files}

    for plugin_file in plugin_files:
        target_file = target_dir / plugin_file.name

        should_copy = force or not target_file.exists()
        if not should_copy and target_file.exists():
            source_mtime = plugin_file.stat().st_mtime
            target_mtime = target_file.stat().st_mtime
            should_copy = source_mtime > target_mtime

        if should_copy:
            shutil.copy2(plugin_file, target_file)
            synced += 1

    removed = 0
    for target_file in target_dir.glob("*.py"):
        if target_file.name in desired_names or target_file.name == "__init__.py":
            continue
        try:
            target_file.unlink()
            removed += 1
        except FileNotFoundError:
            continue

    if removed:
        console.print(f"[info]Removed {removed} stale plugin(s)")

    return synced


def list_available_plugins() -> list[str]:
    """List all available bundled plugins."""
    source_dir = get_plugins_source_dir()
    if not source_dir.exists():
        return []

    return [
        p.stem
        for p in source_dir.glob("*.py")
        if p.name != "__init__.py" and not p.name.startswith("_")
    ]


def list_installed_plugins() -> list[str]:
    """List all installed plugins."""
    target_dir = get_plugins_target_dir()
    if not target_dir.exists():
        return []

    return [
        p.stem
        for p in target_dir.glob("*.py")
        if p.name != "__init__.py" and not p.name.startswith("_")
    ]
