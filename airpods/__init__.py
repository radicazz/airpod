"""AirPods project metadata helpers."""

from __future__ import annotations

from functools import lru_cache
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Dict

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # Python 3.10 fallback
    try:  # pragma: no cover - requires optional dependency
        import tomli as tomllib  # type: ignore
    except ModuleNotFoundError:  # pragma: no cover
        tomllib = None  # type: ignore

PROJECT_NAME = "airpods"
PYPROJECT_PATH = Path(__file__).resolve().parent.parent / "pyproject.toml"


def _load_pyproject_metadata() -> Dict[str, Any]:
    if tomllib is None or not PYPROJECT_PATH.exists():
        return {}
    with PYPROJECT_PATH.open("rb") as fh:
        data = tomllib.load(fh)
    project_data = data.get("project", {})
    if isinstance(project_data, dict):
        return project_data
    return {}


@lru_cache(maxsize=1)
def _project_metadata() -> Dict[str, Any]:
    try:
        metadata = importlib_metadata.metadata(PROJECT_NAME)
        return {
            "name": metadata.get("Name"),
            "version": metadata.get("Version"),
            "description": metadata.get("Summary"),
        }
    except importlib_metadata.PackageNotFoundError:  # pragma: no cover - dev checkout
        return _load_pyproject_metadata()


_META = _project_metadata()
__version__ = _META.get("version", "0.0.0")
__description__ = _META.get(
    "description",
    "Rich, user-friendly CLI for orchestrating local AI services with Podman and UV.",
)


def project_metadata() -> Dict[str, Any]:
    """Return cached project metadata sourced from package metadata or pyproject."""
    return dict(_META)


__all__ = ["__version__", "__description__", "project_metadata"]
