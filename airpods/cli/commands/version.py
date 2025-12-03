"""Version command for displaying CLI version information."""

from __future__ import annotations

import typer

from ..common import COMMAND_CONTEXT, print_version
from ..help import command_help_option, maybe_show_command_help
from ..type_defs import CommandMap


def register(app: typer.Typer) -> CommandMap:
    @app.command(context_settings=COMMAND_CONTEXT)
    def version(
        ctx: typer.Context,
        help_: bool = command_help_option(),
    ) -> None:
        """Show CLI version."""
        maybe_show_command_help(ctx, help_)
        print_version()

    return {"version": version}
