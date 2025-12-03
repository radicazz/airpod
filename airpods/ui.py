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
        detail = _clean_detail(check.name, check.detail)
        table.add_row(check.name, status, detail)
    table.add_row(
        "gpu (nvidia)",
        "[ok]ok" if report.gpu_available else "[warn]not detected",
        _clean_detail("gpu (nvidia)", report.gpu_detail),
    )
    console.print(table)


def success_panel(message: str) -> None:
    """Display a success message in a green panel."""
    console.print(Panel.fit(f"[ok]{message}[/]", border_style="green"))


def info_panel(message: str) -> None:
    """Display an info message in a cyan panel."""
    console.print(Panel.fit(f"[info]{message}[/]", border_style="cyan"))


def _clean_detail(name: str, detail: str) -> str:
    """Reduce duplicated version lines by preferring lines matching the check name."""
    if not detail:
        return ""
    lines = [line.strip() for line in detail.splitlines() if line.strip()]
    if not lines:
        return ""
    if len(lines) == 1:
        return lines[0]
    normalized = name.lower().replace(" ", "")
    matching = [line for line in lines if normalized in line.lower().replace(" ", "")]
    selected = matching or lines
    return "\n".join(selected)
