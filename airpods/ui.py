"""UI utilities for rich console output."""

from __future__ import annotations

from rich.panel import Panel
from rich.table import Table

from airpods.logging import console
from airpods.services import EnvironmentReport


def show_environment(report: EnvironmentReport) -> None:
    """Display environment checks in a formatted table."""
    table = Table(title="Environment", show_header=True, header_style="bold cyan")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Details")
    for check in report.checks:
        status = "[ok]ok" if check.ok else "[error]missing"
        table.add_row(check.name, status, check.detail)
    table.add_row("gpu (nvidia)", "[ok]ok" if report.gpu_available else "[warn]not detected", report.gpu_detail)
    console.print(table)


def success_panel(message: str) -> None:
    """Display a success message in a green panel."""
    console.print(Panel.fit(f"[ok]{message}[/]", border_style="green"))


def info_panel(message: str) -> None:
    """Display an info message in a cyan panel."""
    console.print(Panel.fit(f"[info]{message}[/]", border_style="cyan"))

