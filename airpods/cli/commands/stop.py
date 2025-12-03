"""Stop command implementation for gracefully stopping Podman containers."""

from __future__ import annotations

from typing import Optional

import typer

from airpods import ui
from airpods.logging import console, status_spinner

from ..common import (
    COMMAND_CONTEXT,
    DEFAULT_STOP_TIMEOUT,
    ensure_podman_available,
    manager,
    resolve_services,
)
from ..type_defs import CommandMap


def register(app: typer.Typer) -> CommandMap:
    @app.command(context_settings=COMMAND_CONTEXT)
    def stop(
        service: Optional[list[str]] = typer.Argument(
            None, help="Services to stop (default: all)."
        ),
        remove: bool = typer.Option(
            False, "--remove", "-r", help="Remove pods after stopping."
        ),
        timeout: int = typer.Option(
            DEFAULT_STOP_TIMEOUT, "--timeout", "-t", help="Stop timeout seconds."
        ),
    ) -> None:
        """Stop pods for specified services."""
        specs = resolve_services(service)
        ensure_podman_available()
        for spec in specs:
            with status_spinner(f"Stopping {spec.pod}"):
                existed = manager.stop_service(spec, remove=remove, timeout=timeout)
            if not existed:
                console.print(f"[warn]{spec.pod} not found; skipping[/]")
                continue
            console.print(f"[ok]{spec.name} stopped[/]")
        ui.success_panel(f"stop complete: {', '.join(spec.name for spec in specs)}")

    return {"stop": stop}
