"""Doctor command for environment diagnostics and dependency checks."""

from __future__ import annotations

import typer

from airpods import __version__, gpu as gpu_utils, ui
from airpods.logging import console
from airpods.system import detect_cuda_compute_capability
from airpods.updates import (
    check_for_update,
    detect_install_source,
    format_upgrade_hint,
    is_update_available,
)
from airpods.cuda import select_cuda_version, get_cuda_info_display
from airpods.paths import detect_repo_root

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

        # Check GPU passthrough setup (NVIDIA Container Toolkit + CDI)
        toolkit_installed, toolkit_version = gpu_utils.detect_nvidia_container_toolkit()
        if toolkit_installed:
            console.print(f"NVIDIA Container Toolkit: [ok]{toolkit_version}[/]")

            # Check CDI configuration
            if gpu_utils.check_cdi_available():
                console.print("NVIDIA CDI: [ok]configured[/]")
            else:
                console.print("NVIDIA CDI: [warn]not configured[/]")
                console.print("[dim]GPU pass-through may not work. Run:[/]")
                console.print(
                    "[dim]  sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml[/]"
                )
        else:
            console.print(f"NVIDIA Container Toolkit: [warn]{toolkit_version}[/]")
            if has_gpu_cap:
                console.print(
                    "[dim]GPU detected but Container Toolkit not found. Install it for GPU support in containers.[/]"
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
