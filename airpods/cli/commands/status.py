"""Status command implementation for displaying pod health and availability."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import typer

from airpods.logging import console

from ..common import COMMAND_CONTEXT, ensure_podman_available, resolve_services
from ..status_view import render_status
from ..type_defs import CommandMap


def register(app: typer.Typer) -> CommandMap:
    @app.command(context_settings=COMMAND_CONTEXT)
    def status(
        service: Optional[list[str]] = typer.Argument(
            None, help="Services to report (default: all)."
        ),
        watch: Optional[float] = typer.Option(
            None, "--watch", "-w", help="Refresh interval in seconds."
        ),
    ) -> None:
        """Show pod status."""
        specs = resolve_services(service)
        ensure_podman_available()
        if watch is not None and watch <= 0:
            raise typer.BadParameter("watch interval must be positive.")

        def _run_once() -> None:
            render_status(specs)

        if watch is None:
            _run_once()
            return

        try:
            while True:
                console.clear()
                _run_once()
                console.print(
                    f"[dim]Refreshed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (Ctrl+C to stop)[/]"
                )
                time.sleep(watch)
        except KeyboardInterrupt:
            console.print("[info]Stopped watching status.")

    return {"status": status}
