"""Doctor command for environment diagnostics and dependency checks."""

from __future__ import annotations

import typer

from airpods import __version__, gpu as gpu_utils, ui
from airpods.logging import console
from airpods.system import (
    detect_cuda_compute_capability,
    detect_dns_servers,
    detect_vpn_mtu_issues,
)
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

        # Check for VPN MTU issues that can cause HTTPS timeouts
        has_vpn_issue, vpn_iface, vpn_mtu, has_mss_clamping = detect_vpn_mtu_issues()
        if has_vpn_issue and vpn_iface:
            if has_mss_clamping:
                console.print(
                    f"VPN MTU: [ok]MSS clamping configured for {vpn_iface}[/]"
                )
            else:
                console.print(
                    f"VPN MTU Issue: [warn]detected ({vpn_iface}, MTU {vpn_mtu})[/]"
                )
                console.print(
                    "[dim]Containers may experience HTTPS timeouts. Choose one solution:[/]"
                )
                console.print(
                    "[dim]• Quick fix: Use host networking for affected services[/]"
                )
                console.print(
                    '[dim]  Edit config.toml: services.comfyui.network_mode = "host"[/]'
                )
                console.print(
                    "[dim]• System-wide fix: Enable MSS clamping (requires sudo)[/]"
                )
                try:
                    repo_root = detect_repo_root()
                    if repo_root:
                        script_path = repo_root / "scripts" / "mss-clamping"
                        if script_path.exists():
                            console.print(f"[dim]  Run: sudo {script_path} enable[/]")
                        else:
                            console.print(
                                "[dim]  Run: sudo scripts/mss-clamping enable[/]"
                            )
                    else:
                        console.print("[dim]  Run: sudo scripts/mss-clamping enable[/]")
                except Exception:
                    console.print("[dim]  Run: sudo scripts/mss-clamping enable[/]")
                console.print("[dim]See: docs/troubleshooting-network-vpn.md[/]")

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
