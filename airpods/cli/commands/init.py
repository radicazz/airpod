"""Init command for initial setup, volume creation, and image pulling."""

from __future__ import annotations

import typer

from airpods import state, ui
from airpods.logging import console, status_spinner

from ..common import COMMAND_CONTEXT, manager
from ..type_defs import CommandMap


def register(app: typer.Typer) -> CommandMap:
    @app.command(context_settings=COMMAND_CONTEXT)
    def init() -> None:
        """Verify tools, create volumes, and pre-pull images."""
        report = manager.report_environment()
        ui.show_environment(report)

        if report.missing:
            console.print(
                f"[error]The following dependencies are required: {', '.join(report.missing)}. Install them and re-run init.[/]"
            )
            raise typer.Exit(code=1)

        with status_spinner("Ensuring network"):
            manager.ensure_network()

        specs = manager.resolve(None)

        with status_spinner("Ensuring volumes"):
            manager.ensure_volumes(specs)

        with status_spinner("Pulling images"):
            manager.pull_images(specs)

        with status_spinner("Preparing Open WebUI secret"):
            secret = state.ensure_webui_secret()
        console.print(
            f"[info]Open WebUI secret stored at {state.webui_secret_path()}[/]"
        )

        ui.success_panel("init complete. pods are ready to start.")

    return {"init": init}
