"""Help text rendering and formatting for the CLI.

This module handles custom help display including:
- Root command help with examples
- Command table with alias mappings
- Option formatting
- Rich table rendering for beautiful terminal output
"""

from __future__ import annotations

from typing import Iterable, Sequence

import click
import typer
from rich.table import Table

from airpods import __description__, ui
from airpods.logging import PALETTE, console

from .common import COMMAND_ALIASES


def _alias_groups() -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for alias, canonical in COMMAND_ALIASES.items():
        groups.setdefault(canonical, []).append(alias)
    for aliases in groups.values():
        aliases.sort()
    return groups


COMMAND_ALIAS_GROUPS = _alias_groups()


def show_root_help(ctx: typer.Context) -> None:
    console.print(__description__)
    console.print()
    console.print("[section]Usage[/section]")
    console.print("  airpods [OPTIONS] COMMAND [ARGS]...\n")
    console.print("[section]Commands[/section]")
    console.print(build_command_table(ctx))
    console.print()
    console.print("[section]Options[/section]")
    console.print(build_option_table(ctx))


def build_help_table(
    ctx: typer.Context,
    rows: Iterable[tuple[str, ...]],
    *,
    column_styles: Sequence[dict[str, object]] | None = None,
) -> Table:
    table = ui.themed_grid(padding=(0, 3))
    styles = column_styles or (
        {"style": f"bold {PALETTE['green']}", "no_wrap": True},
        {"style": f"bold {PALETTE['purple']}", "no_wrap": True},
        {"style": PALETTE["fg"]},
    )
    for column in styles:
        table.add_column(**column)
    for row in rows:
        table.add_row(*row)
    return table


def build_command_table(ctx: typer.Context) -> Table:
    rows = command_help_rows(ctx)
    column_styles = (
        {"style": f"bold {PALETTE['green']}", "no_wrap": True},
        {"style": f"bold {PALETTE['purple']}", "no_wrap": True},
        {"style": f"bold {PALETTE['cyan']}", "no_wrap": True},
        {"style": PALETTE["fg"]},
    )
    return build_help_table(ctx, rows, column_styles=column_styles)


def build_option_table(ctx: typer.Context) -> Table:
    rows = option_help_rows(ctx)
    return build_help_table(ctx, rows)


def command_help_rows(ctx: typer.Context):
    command_group = ctx.command
    if command_group is None:
        return []
    rows = []
    for name in command_group.list_commands(ctx):
        command = command_group.get_command(ctx, name)
        if not command or command.hidden:
            continue
        alias_text = ", ".join(COMMAND_ALIAS_GROUPS.get(name, []))
        description = (command.help or command.short_help or "").strip()
        option_hint = command_param_hint(command)
        rows.append((name, alias_text, option_hint, description))
    return rows


def option_help_rows(ctx: typer.Context):
    rows = []
    if ctx.command is None:
        return rows
    for param in ctx.command.params:
        if not isinstance(param, click.Option):
            continue
        name = primary_long_option(param)
        short_text = format_short_options(param)
        description = (param.help or "").strip()
        rows.append((name, short_text, description))
    return rows


def command_param_hint(command: click.Command) -> str:
    arguments = [param for param in command.params if isinstance(param, click.Argument)]
    if arguments:
        return format_argument_hint(arguments[0])
    options = [param for param in command.params if isinstance(param, click.Option)]
    if options:
        return primary_long_option(options[0]) or options[0].opts[0]
    return ""


def format_argument_hint(param: click.Argument) -> str:
    name = param.metavar or param.human_readable_name or param.name or ""
    if not name:
        return ""
    normalized = name.replace("_", " ").strip()
    normalized = normalized.replace(" ", "-").upper()
    return f"<{normalized}>"


def primary_long_option(param: "click.Option") -> str:
    for opt in param.opts:
        if opt.startswith("--"):
            return opt
    return param.opts[0] if param.opts else ""


def format_short_options(param: "click.Option") -> str:
    seen: list[str] = []
    for opt in list(param.opts) + list(param.secondary_opts):
        if not opt.startswith("-") or opt.startswith("--"):
            continue
        if opt not in seen:
            seen.append(opt)
    return ", ".join(seen)
