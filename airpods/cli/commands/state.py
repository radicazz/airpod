"""State command group for backup, restore, and cleanup tasks."""

from __future__ import annotations

import typer

from . import backup, clean
from ..common import COMMAND_CONTEXT
from ..help import command_help_option, maybe_show_command_help, show_command_help
from ..type_defs import CommandMap

state_app = typer.Typer(
    help="Manage backups, restores, and cleanup for airpods state",
    context_settings=COMMAND_CONTEXT,
)


@state_app.callback(invoke_without_command=True)
def _state_root(
    ctx: typer.Context,
    help_: bool = command_help_option(),
) -> None:
    """Entry point for the state command group."""
    maybe_show_command_help(ctx, help_)
    if ctx.invoked_subcommand is None:
        show_command_help(ctx)


def register(app: typer.Typer) -> CommandMap:
    """Register the state command group and its subcommands."""
    backup.register(state_app)
    clean.register(state_app)
    app.add_typer(state_app, name="state")
    return {}
