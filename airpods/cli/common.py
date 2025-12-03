from __future__ import annotations

from typing import Optional

import typer

from airpods import __version__, podman
from airpods.config import REGISTRY
from airpods.logging import console
from airpods.services import ServiceManager, ServiceSpec, UnknownServiceError

HELP_OPTION_NAMES = ["-h", "--help"]
COMMAND_CONTEXT = {"help_option_names": HELP_OPTION_NAMES}

DEFAULT_STOP_TIMEOUT = 10
DEFAULT_LOG_LINES = 200
DEFAULT_PING_TIMEOUT = 2.0

DOCTOR_REMEDIATIONS = {
    "podman": "Install Podman: https://podman.io/docs/installation",
    "podman-compose": "Install podman-compose (often via your package manager).",
    "uv": "Install uv: https://github.com/astral-sh/uv",
}

COMMAND_ALIASES = {
    "up": "start",
    "down": "stop",
    "ps": "status",
}

ALIAS_HELP_TEMPLATE = "[alias]Alias for {canonical}[/]"

manager = ServiceManager(REGISTRY)


def resolve_services(names: Optional[list[str]]) -> list[ServiceSpec]:
    """Resolve names to service specs, surfacing Typer-friendly errors."""
    try:
        return manager.resolve(names)
    except UnknownServiceError as exc:  # noqa: B904
        raise typer.BadParameter(str(exc)) from exc


def ensure_podman_available() -> None:
    """Ensure Podman is available before running commands."""
    try:
        manager.ensure_podman()
    except podman.PodmanError as exc:  # pragma: no cover - interacts with system
        console.print(f"[error]{exc}[/]")
        raise typer.Exit(code=1)


def print_version() -> None:
    console.print(f"[bold]airpods[/bold] [accent]v{__version__}[/]")
