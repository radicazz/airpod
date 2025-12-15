"""Doctor command for environment diagnostics and dependency checks."""

from __future__ import annotations

import typer

from airpods import __version__, ui
from airpods.logging import console
from airpods.system import detect_cuda_compute_capability, detect_dns_servers
from airpods.updates import (
    check_for_update,
    detect_install_source,
    format_upgrade_hint,
    is_update_available,
)
from airpods.cuda import select_cuda_version, get_cuda_info_display

from ..common import COMMAND_CONTEXT, DOCTOR_REMEDIATIONS, manager
from ..help import command_help_option, maybe_show_command_help
from ..type_defs import CommandMap


def register(app: typer.Typer) -> CommandMap:
    @app.command(context_settings=COMMAND_CONTEXT)
    def doctor(
        ctx: typer.Context,
        help_: bool = command_help_option(),
    ) -> None:
        """Re-run environment checks without mutating resources."""
        maybe_show_command_help(ctx, help_)

        report = manager.report_environment()
        ui.show_environment(report)

        # Show CUDA detection info
        has_gpu_cap, gpu_name_cap, compute_cap = detect_cuda_compute_capability()
        if has_gpu_cap and compute_cap:
            selected_cuda = select_cuda_version(compute_cap)
            cuda_info = get_cuda_info_display(
                has_gpu_cap, gpu_name_cap, compute_cap, selected_cuda
            )
            console.print(f"CUDA: [ok]{cuda_info}[/]")
        else:
            cuda_info = get_cuda_info_display(
                has_gpu_cap, gpu_name_cap, compute_cap, "cu126"
            )
            console.print(f"CUDA: [muted]{cuda_info}[/]")

        # Networking hints (common cause of HuggingFace/Ollama download failures)
        effective_dns = manager.network_dns_servers or detect_dns_servers()
        dns_label = ", ".join(effective_dns) if effective_dns else "none"
        console.print(f"Network DNS: [accent]{dns_label}[/]")
        if manager.network_dns_servers == []:
            console.print(
                "[dim]Tip: Set 'runtime.network.dns_servers' in config.toml if you're on a restricted/corporate network.[/dim]"
            )
        if manager.runtime.network_exists(manager.network_name):
            console.print(
                "[dim]Tip: If containers can't reach the internet, recreate the network with 'airpods start --reset-network' (or 'airpods clean --network').[/dim]"
            )

        latest = check_for_update()
        if latest and is_update_available(latest):
            hint = format_upgrade_hint(latest, detect_install_source())
            console.print(
                f"[warn]Update available:[/] {latest.tag} (installed: v{__version__})"
            )
            console.print(f"[dim]{hint}[/dim]")

        if report.missing:
            console.print("[error]Missing dependencies detected:[/]")
            for dep in report.missing:
                guidance = DOCTOR_REMEDIATIONS.get(
                    dep, "Install it or ensure it is on your PATH."
                )
                console.print(f"[error]- {dep}[/] {guidance}")
            console.print(
                "[error]Resolve the missing dependencies and re-run doctor.[/]"
            )
            raise typer.Exit(code=1)

        ui.success_panel("doctor complete: environment ready.")

    return {"doctor": doctor}
