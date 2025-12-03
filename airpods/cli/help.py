"""Help text rendering and formatting for the CLI.

This module handles custom help display including:
- Root command help with examples
- Command table with alias mappings
- Option formatting
- Rich table rendering for beautiful terminal output
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Tuple

import typer
from rich.table import Table

from airpods import __version__
from airpods.logging import console

from .common import COMMAND_ALIASES

if TYPE_CHECKING:
    import click

HELP_EXAMPLES = [
    ("airpods init", "Verify dependencies, volumes, and secrets before first run."),
    ("airpods start", "Launch Ollama and Open WebUI with GPU auto-detect."),
    (
        "airpods start --cpu open-webui",
        "Force CPU mode when starting only Open WebUI.",
    ),
    ("airpods status", "Show pod health, ports, and ping results."),
    ("airpods logs ollama -n 100", "Tail the latest Ollama logs."),
]


def _alias_groups() -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for alias, canonical in COMMAND_ALIASES.items():
        groups.setdefault(canonical, []).append(alias)
    for aliases in groups.values():
        aliases.sort()
    return groups


COMMAND_ALIAS_GROUPS = _alias_groups()


def show_root_help(ctx: typer.Context) -> None:
    console.print(f"[bold]airpods[/bold] v{__version__}")
    console.print(
        "Orchestrate local AI services (Ollama, Open WebUI) with Podman + UV."
    )
    console.print()
    console.print("[bold cyan]Usage[/bold cyan]")
    console.print("  airpods [OPTIONS] COMMAND [ARGS]...\n")
    console.print("[bold cyan]Commands[/bold cyan]")
    console.print(build_command_table(ctx))
    console.print()
    console.print("[bold cyan]Options[/bold cyan]")
    console.print(build_option_table(ctx))
    console.print()
    console.print("[bold cyan]Examples[/bold cyan]")
    console.print(build_examples_table())


def build_help_table(ctx: typer.Context, rows: Iterable[Tuple[str, str, str]]) -> Table:
    table = Table.grid(padding=(0, 3))
    table.add_column(style="cyan", no_wrap=True)
    table.add_column(style="magenta", no_wrap=True)
    table.add_column()
    for row in rows:
        table.add_row(*row)
    return table


def build_command_table(ctx: typer.Context) -> Table:
    rows = command_help_rows(ctx)
    return build_help_table(ctx, rows)


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
        rows.append((name, alias_text, description))
    return rows


def option_help_rows(ctx: typer.Context):
    import click
    
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


def build_examples_table() -> Table:
    table = Table.grid(padding=(0, 3))
    table.add_column(style="cyan", no_wrap=True)
    table.add_column()
    for command, description in HELP_EXAMPLES:
        table.add_row(f"[bold]{command}[/]", description)
    return table
