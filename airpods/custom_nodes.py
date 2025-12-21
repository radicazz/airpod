"""Helpers for managing ComfyUI custom nodes."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from airpods.configuration import get_config
from airpods.configuration.schema import CustomNodeInstall
from airpods.logging import console
from airpods.plugins import get_comfyui_plugins_target_dir


@dataclass(frozen=True)
class CustomNodeResult:
    name: str
    dest: Path
    action: str
    detail: str | None = None


@dataclass(frozen=True)
class CustomNodeRequirement:
    name: str
    host_path: Path
    container_path: str
    marker_path: Path


def get_custom_node_specs() -> list[CustomNodeInstall]:
    """Return enabled custom node specs from config."""
    config = get_config()
    service = config.services.get("comfyui")
    if not service or not service.enabled:
        return []
    custom_nodes = service.custom_nodes
    if not custom_nodes:
        return []
    return [node for node in custom_nodes.install if node.enabled]


def custom_nodes_target_dir() -> Path:
    """Return the host-side custom nodes volume directory."""
    return get_comfyui_plugins_target_dir()


def node_destination(
    node: CustomNodeInstall, *, target_root: Path | None = None
) -> Path:
    """Resolve the on-disk destination path for a custom node."""
    root = target_root or custom_nodes_target_dir()
    dest = root / node.name

    if node.path:
        source = Path(node.path)
        if source.is_file():
            suffix = source.suffix or ".py"
            if dest.suffix != suffix:
                dest = dest.with_suffix(suffix)

    return dest


def custom_nodes_keep_entries(nodes: Iterable[CustomNodeInstall]) -> set[str]:
    """Return relative paths in custom_nodes that should not be pruned."""
    root = custom_nodes_target_dir()
    keep: set[str] = set()
    for node in nodes:
        dest = node_destination(node, target_root=root)
        try:
            rel = dest.relative_to(root)
        except ValueError:
            continue
        keep.add(rel.as_posix())
    return keep


def _dir_mtime(path: Path) -> float:
    latest = path.stat().st_mtime
    for item in path.rglob("*"):
        if item.is_file():
            latest = max(latest, item.stat().st_mtime)
    return latest


def _should_copy_tree(src: Path, dest: Path) -> bool:
    if not dest.exists():
        return True
    return _dir_mtime(src) > _dir_mtime(dest)


def _copy_tree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git"))


def _copy_file(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _git_available() -> bool:
    return shutil.which("git") is not None


def prepare_custom_nodes(
    nodes: Iterable[CustomNodeInstall], *, verbose: bool = False
) -> list[CustomNodeResult]:
    """Ensure configured custom nodes exist in the custom_nodes volume."""
    target_root = custom_nodes_target_dir()
    target_root.mkdir(parents=True, exist_ok=True)

    results: list[CustomNodeResult] = []

    for node in nodes:
        dest = node_destination(node, target_root=target_root)

        if node.path:
            source = Path(node.path)
            if source.is_dir():
                if _should_copy_tree(source, dest):
                    _copy_tree(source, dest)
                    results.append(
                        CustomNodeResult(node.name, dest, "copied", str(source))
                    )
                else:
                    results.append(
                        CustomNodeResult(node.name, dest, "skipped", "up-to-date")
                    )
                continue

            if source.is_file():
                if not dest.exists() or source.stat().st_mtime > dest.stat().st_mtime:
                    _copy_file(source, dest)
                    results.append(
                        CustomNodeResult(node.name, dest, "copied", str(source))
                    )
                else:
                    results.append(
                        CustomNodeResult(node.name, dest, "skipped", "up-to-date")
                    )
                continue

            results.append(
                CustomNodeResult(node.name, dest, "error", f"path not found: {source}")
            )
            continue

        if node.repo:
            if dest.exists():
                results.append(
                    CustomNodeResult(node.name, dest, "skipped", "already present")
                )
                continue

            if not _git_available():
                results.append(
                    CustomNodeResult(node.name, dest, "error", "git not found on PATH")
                )
                continue

            try:
                subprocess.run(
                    ["git", "clone", node.repo, str(dest)],
                    check=True,
                    capture_output=not verbose,
                    text=True,
                )
                if node.ref:
                    subprocess.run(
                        ["git", "-C", str(dest), "checkout", node.ref],
                        check=True,
                        capture_output=not verbose,
                        text=True,
                    )
                results.append(
                    CustomNodeResult(
                        node.name,
                        dest,
                        "cloned",
                        node.ref or "default",
                    )
                )
            except subprocess.CalledProcessError as exc:
                detail = exc.stderr.strip() if exc.stderr else str(exc)
                results.append(CustomNodeResult(node.name, dest, "error", detail))

    return results


def collect_requirements(
    nodes: Iterable[CustomNodeInstall],
    *,
    container_custom_nodes_dir: str,
) -> list[CustomNodeRequirement]:
    """Collect requirement files for configured nodes (host + container paths)."""
    requirements: list[CustomNodeRequirement] = []
    target_root = custom_nodes_target_dir()
    container_root = Path(container_custom_nodes_dir)

    for node in nodes:
        req = node.requirements
        if not req:
            continue
        if node.path and Path(node.path).is_file():
            continue

        host_req = Path(req)
        if not host_req.is_absolute():
            host_req = (target_root / node.name / host_req).resolve()

        if not host_req.exists():
            console.print(
                f"[warn]Custom node requirements not found for {node.name}: {host_req}[/]"
            )
            continue

        marker = host_req.parent / ".airpods-requirements.installed"
        if marker.exists() and marker.stat().st_mtime >= host_req.stat().st_mtime:
            continue

        try:
            rel = host_req.relative_to(target_root)
        except ValueError:
            console.print(
                f"[warn]Requirements file is outside custom_nodes volume for {node.name}: {host_req}[/]"
            )
            continue

        container_req = (container_root / rel).as_posix()
        requirements.append(
            CustomNodeRequirement(node.name, host_req, container_req, marker)
        )

    return requirements


def install_requirements(
    *,
    runtime,
    container_name: str,
    requirements: Iterable[CustomNodeRequirement],
) -> list[CustomNodeResult]:
    """Install requirements inside a running container."""
    results: list[CustomNodeResult] = []
    for req in requirements:
        try:
            result = runtime.exec_in_container(
                container_name,
                ["python3", "-m", "pip", "install", "-r", req.container_path],
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except Exception as exc:  # pragma: no cover - runtime-specific failures
            results.append(CustomNodeResult(req.name, req.host_path, "error", str(exc)))
            continue

        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            results.append(CustomNodeResult(req.name, req.host_path, "error", detail))
        else:
            req.marker_path.parent.mkdir(parents=True, exist_ok=True)
            req.marker_path.touch()
            results.append(CustomNodeResult(req.name, req.host_path, "installed"))

    return results
