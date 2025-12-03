"""Version command for displaying CLI version information."""

from __future__ import annotations

import typer

from ..common import COMMAND_CONTEXT, print_version
from ..type_defs import CommandMap


def register(app: typer.Typer) -> CommandMap:
    @app.command(context_settings=COMMAND_CONTEXT)
    def version() -> None:
        """Show CLI version."""
        print_version()

    return {"version": version}
