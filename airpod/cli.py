from __future__ import annotations

import sys
import http.client
from typing import List, Optional

import typer
from rich.table import Table

from airpod import __version__
from airpod import podman, ui
from airpod.config import REGISTRY
from airpod.logging import console, status_spinner
from airpod import state
from airpod.services import ServiceManager, ServiceSpec, UnknownServiceError
from airpod.system import check_dependency, detect_gpu

app = typer.Typer(
    help="Orchestrate local AI services (Ollama, Open WebUI) with Podman + UV.",
    context_settings={"help_option_names": ["-h", "--help"]},
    rich_markup_mode="rich",
)

manager = ServiceManager(REGISTRY)


def _resolve_services(names: Optional[List[str]]) -> List[ServiceSpec]:
    try:
        return manager.resolve(names)
    except UnknownServiceError as exc:  # noqa: B904
        raise typer.BadParameter(str(exc))


def _ensure_podman_available() -> None:
    try:
        manager.ensure_podman()
    except podman.PodmanError as exc:
        console.print(f"[error]{exc}[/]")
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Show CLI version."""
    console.print(f"airpod {__version__}")


@app.command()
def init() -> None:
    """Verify tools, create volumes, and pre-pull images."""
    report = manager.report_environment()
    ui.show_environment(report)

    if report.missing:
        console.print(
            f"[error]The following dependencies are required: {', '.join(report.missing)}. Install them and re-run init.[/]"
        )
        raise typer.Exit(code=1)

    with status_spinner("Ensuring network"):
        manager.ensure_network()

    with status_spinner("Ensuring volumes"):
        manager.ensure_volumes(manager.resolve(None))

    with status_spinner("Pulling images"):
        manager.pull_images(manager.resolve(None))

    # Security: ensure a persistent secret key for Open WebUI sessions.
    with status_spinner("Preparing Open WebUI secret"):
        secret = state.ensure_webui_secret()
    console.print(f"[info]Open WebUI secret stored at {state.webui_secret_path()}[/]")

    ui.success_panel("init complete. pods are ready to start.")


@app.command()
def start(
    service: Optional[List[str]] = typer.Argument(None, help="Services to start (default: all)."),
    force_cpu: bool = typer.Option(False, "--cpu", help="Force CPU even if GPU is present."),
) -> None:
    """Start pods for specified services (default: ollama + open-webui)."""
    specs = _resolve_services(service)
    _ensure_podman_available()
    gpu_available, gpu_detail = detect_gpu()
    console.print(f"[info]GPU: {'enabled' if gpu_available else 'not detected'} ({gpu_detail})[/]")

    with status_spinner("Ensuring network"):
        manager.ensure_network()

    with status_spinner("Ensuring volumes"):
        manager.ensure_volumes(specs)

    with status_spinner("Pulling images"):
        manager.pull_images(specs)

    for spec in specs:
        with status_spinner(f"Starting {spec.name}"):
            manager.start_service(spec, gpu_available=gpu_available, force_cpu=force_cpu)
        console.print(f"[ok]{spec.name} running in pod {spec.pod}[/]")
    ui.success_panel(f"start complete: {', '.join(spec.name for spec in specs)}")


@app.command()
def stop(
    service: Optional[List[str]] = typer.Argument(None, help="Services to stop (default: all)."),
    remove: bool = typer.Option(False, "--remove", "-r", help="Remove pods after stopping."),
    timeout: int = typer.Option(10, "--timeout", "-t", help="Stop timeout seconds."),
) -> None:
    """Stop pods for specified services."""
    specs = _resolve_services(service)
    _ensure_podman_available()
    for spec in specs:
        with status_spinner(f"Stopping {spec.pod}"):
            existed = manager.stop_service(spec, remove=remove, timeout=timeout)
        if not existed:
            console.print(f"[warn]{spec.pod} not found; skipping[/]")
            continue
        console.print(f"[ok]{spec.name} stopped[/]")
    ui.success_panel(f"stop complete: {', '.join(spec.name for spec in specs)}")


@app.command()
def status(service: Optional[List[str]] = typer.Argument(None, help="Services to report (default: all).")) -> None:
    """Show pod status."""
    specs = _resolve_services(service)
    _ensure_podman_available()
    pod_rows = manager.pod_status_rows()

    table = Table(title="Pods", header_style="bold cyan")
    table.add_column("Service")
    table.add_column("Pod")
    table.add_column("Status")
    table.add_column("Ports")
    table.add_column("Containers")
    table.add_column("Ping")

    for spec in specs:
        row = pod_rows.get(spec.pod)
        if not row:
            table.add_row(spec.name, spec.pod, "[warn]absent", "-", "-", "-")
            continue
        port_bindings = manager.service_ports(spec)
        ports = []
        for container_port, bindings in port_bindings.items():
            for binding in bindings or []:
                host_port = binding.get("HostPort", "")
                ports.append(f"{host_port}->{container_port}")
        ports_display = ", ".join(ports) if ports else (", ".join(row.get("Ports", [])) if row.get("Ports") else "-")
        containers = str(row.get("NumberOfContainers", "?") or "?")
        host_port = _extract_host_port(spec, port_bindings)
        ping_status = _ping_service(spec, host_port) if host_port else "-"
        table.add_row(spec.name, spec.pod, row.get("Status", "?"), ports_display, containers, ping_status)

    console.print(table)


def _extract_host_port(spec: ServiceSpec, port_bindings) -> Optional[int]:
    # Prefer actual bindings; fallback to configured host port.
    if port_bindings:
        first_binding = next(iter(port_bindings.values()), None)
        if first_binding:
            host_port = (first_binding[0] or {}).get("HostPort")
            if host_port:
                try:
                    return int(host_port)
                except ValueError:
                    return None
    if spec.ports:
        return spec.ports[0][0]
    return None


def _ping_service(spec: ServiceSpec, port: Optional[int]) -> str:
    if not spec.health_path or port is None:
        return "-"
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=2.0)
        conn.request("GET", spec.health_path)
        resp = conn.getresponse()
        code = resp.status
        conn.close()
        if 200 <= code < 400:
            return "[ok]ok"
        return f"[warn]{code}"
    except Exception as exc:  # noqa: BLE001
        return f"[warn]{type(exc).__name__}"


@app.command()
def logs(
    service: Optional[List[str]] = typer.Argument(None, help="Services to show logs for (default: all)."),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow logs."),
    since: Optional[str] = typer.Option(None, "--since", help="Show logs since RFC3339 timestamp or duration."),
    lines: int = typer.Option(200, "--lines", "-n", help="Number of log lines to show."),
) -> None:
    """Show pod logs."""
    specs = _resolve_services(service)
    _ensure_podman_available()
    if follow and len(specs) > 1:
        console.print("[warn]follow with multiple services will stream sequentially; Ctrl+C to stop.[/]")

    for idx, spec in enumerate(specs):
        if idx > 0:
            console.print()
        ui.info_panel(f"Logs for {spec.name} ({spec.container})")
        code = podman.stream_logs(spec.container, follow=follow, tail=lines, since=since)
        if code != 0:
            console.print(f"[warn]podman logs exited with code {code} for {spec.container}[/]")


def main() -> None:
    try:
        app()
    except podman.PodmanError as exc:
        console.print(f"[error]{exc}[/]")
        sys.exit(1)


if __name__ == "__main__":
    main()
