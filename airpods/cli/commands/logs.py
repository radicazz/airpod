"""Logs command for viewing and following container logs."""

from __future__ import annotations

from typing import Optional

import typer

from airpods import ui
from airpods.logging import console

from ..common import (
    COMMAND_CONTEXT,
    DEFAULT_LOG_LINES,
    ensure_podman_available,
    manager,
    resolve_services,
)
from ..completions import service_name_completion
from ..help import command_help_option, maybe_show_command_help
from ..type_defs import CommandMap


def register(app: typer.Typer) -> CommandMap:
    @app.command(context_settings=COMMAND_CONTEXT)
    def logs(
        ctx: typer.Context,
        help_: bool = command_help_option(),
        service: Optional[list[str]] = typer.Argument(
            None,
            help="Services to show logs for (default: all).",
            shell_complete=service_name_completion,
        ),
        follow: bool = typer.Option(False, "--follow", "-f", help="Follow logs."),
        since: Optional[str] = typer.Option(
            None, "--since", help="Show logs since RFC3339 timestamp or duration."
        ),
        lines: int = typer.Option(
            DEFAULT_LOG_LINES, "--lines", "-n", help="Number of log lines to show."
        ),
    ) -> None:
        """Show pod logs."""
        maybe_show_command_help(ctx, help_)
        specs = resolve_services(service)
        ensure_podman_available()
        if follow and len(specs) > 1:
            console.print(
                "[warn]follow with multiple services will stream sequentially; Ctrl+C to stop.[/]"
            )

        for idx, spec in enumerate(specs):
            if idx > 0:
                console.print()
            ui.info_panel(f"Logs for {spec.name} ({spec.container})")
            code = manager.stream_logs(
                spec.container, follow=follow, tail=lines, since=since
            )
            if code != 0:
                console.print(
                    f"[warn]podman logs exited with code {code} for {spec.container}[/]"
                )

    return {"logs": logs}
