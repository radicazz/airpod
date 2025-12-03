"""Start command implementation for launching Podman containers."""

from __future__ import annotations

from typing import Optional

import typer

from airpods import ui
from airpods.logging import console, status_spinner
from airpods.system import detect_gpu

from ..common import COMMAND_CONTEXT, ensure_podman_available, manager, resolve_services
from ..type_defs import CommandMap


def register(app: typer.Typer) -> CommandMap:
    @app.command(context_settings=COMMAND_CONTEXT)
    def start(
        service: Optional[list[str]] = typer.Argument(
            None, help="Services to start (default: all)."
        ),
        force_cpu: bool = typer.Option(
            False, "--cpu", help="Force CPU even if GPU is present."
        ),
    ) -> None:
        """Start pods for specified services (default: ollama + open-webui)."""
        specs = resolve_services(service)
        ensure_podman_available()
        gpu_available, gpu_detail = detect_gpu()
        console.print(
            f"[info]GPU: {'enabled' if gpu_available else 'not detected'} ({gpu_detail})[/]"
        )

        with status_spinner("Ensuring network"):
            manager.ensure_network()

        with status_spinner("Ensuring volumes"):
            manager.ensure_volumes(specs)

        with status_spinner("Pulling images"):
            manager.pull_images(specs)

        for spec in specs:
            with status_spinner(f"Starting {spec.name}"):
                manager.start_service(
                    spec, gpu_available=gpu_available, force_cpu=force_cpu
                )
            console.print(f"[ok]{spec.name} running in pod {spec.pod}[/]")
        ui.success_panel(f"start complete: {', '.join(spec.name for spec in specs)}")

    return {"start": start}
