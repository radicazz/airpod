"""Status view rendering for pod health, ports, and service availability.

This module handles the display logic for the `status` command, including:
- Rendering Rich tables with pod information
- HTTP health checks for running services
- Port binding resolution and URL formatting
"""

from __future__ import annotations

import http.client
import socket
import time
from typing import Any, List, Optional

from rich.table import Table

from airpods.logging import console
from airpods.services import ServiceSpec

from .common import DEFAULT_PING_TIMEOUT, manager


def render_status(specs: List[ServiceSpec]) -> None:
    """Render the pod status table.
    
    Args:
        specs: List of service specifications to check status for.
        
    Note:
        manager.pod_status_rows() returns a dict mapping pod names to status info,
        or an empty dict if no pods are running.
    """
    pod_rows = manager.pod_status_rows()
    if pod_rows is None:
        pod_rows = {}
    table = Table(title="Pods", header_style="bold cyan")
    table.add_column("Service")
    table.add_column("Pod")
    table.add_column("Status")
    table.add_column("Ports")
    table.add_column("Containers")
    table.add_column("Health")
    table.add_column("URL")

    for spec in specs:
        row = pod_rows.get(spec.pod) if pod_rows else None
        if not row:
            table.add_row(spec.name, spec.pod, "[warn]absent", "-", "-", "-", "-")
            continue
        port_bindings = manager.service_ports(spec)
        ports: list[str] = []
        for container_port, bindings in port_bindings.items():
            for binding in bindings or []:
                host_port = binding.get("HostPort", "")
                ports.append(f"{host_port}->{container_port}")
        ports_display = (
            ", ".join(ports) if ports else format_row_ports(row.get("Ports"))
        )
        containers = container_count(row)
        host_ports = collect_host_ports(spec, port_bindings)
        host_port = host_ports[0] if host_ports else None
        health = ping_service(spec, host_port)
        url_text = ", ".join(format_host_urls(host_ports)) if host_ports else "-"
        table.add_row(
            spec.name,
            spec.pod,
            row.get("Status", "?"),
            ports_display,
            containers,
            health,
            url_text,
        )

    console.print(table)


def collect_host_ports(spec: ServiceSpec, port_bindings: dict[str, Any]) -> List[int]:
    """Return the list of host ports published for a service."""
    host_ports: List[int] = []
    for bindings in port_bindings.values():
        for binding in bindings or []:
            host_port = binding.get("HostPort")
            if not host_port:
                continue
            try:
                value = int(host_port)
            except (TypeError, ValueError):
                continue
            if value not in host_ports:
                host_ports.append(value)
    if not host_ports:
        for host_port, _ in spec.ports:
            if host_port not in host_ports:
                host_ports.append(host_port)
    return host_ports


def format_host_urls(host_ports: List[int]) -> List[str]:
    """Format user-friendly localhost URLs for each host port."""
    return [f"http://localhost:{port}" for port in host_ports]


def format_row_ports(entries: Optional[list[str]]) -> str:
    if not entries:
        return "-"
    cleaned = []
    for entry in entries:
        text = entry or ""
        if "/" in text:
            text = text.split("/", 1)[0]
        cleaned.append(text)
    return ", ".join(cleaned) if cleaned else "-"


def container_count(row: dict[str, Any]) -> str:
    value = row.get("NumberOfContainers")
    if isinstance(value, int):
        return str(value)
    containers = row.get("Containers") or row.get("ContainerInfo")
    if isinstance(containers, list):
        return str(len(containers))
    return "?"


def ping_service(spec: ServiceSpec, port: Optional[int]) -> str:
    """Ping a service's health endpoint and return status.
    
    Args:
        spec: Service specification containing health_path
        port: Host port to connect to
        
    Returns:
        Formatted status string with HTTP code and latency, or error type
    """
    if not spec.health_path or port is None:
        return "-"
    try:
        start = time.perf_counter()
        conn = http.client.HTTPConnection(
            "127.0.0.1", port, timeout=DEFAULT_PING_TIMEOUT
        )
        conn.request("GET", spec.health_path)
        resp = conn.getresponse()
        code = resp.status
        conn.close()
        elapsed_ms = (time.perf_counter() - start) * 1000
        if 200 <= code < 400:
            return f"[ok]{code} ({elapsed_ms:.0f} ms)"
        return f"[warn]{code} ({elapsed_ms:.0f} ms)"
    except (
        socket.error,
        http.client.HTTPException,
        OSError,
        ConnectionError,
        TimeoutError,
    ) as exc:
        return f"[warn]{type(exc).__name__}"
    except Exception as exc:
        # Fallback for unexpected errors; log for debugging
        console.print(f"[dim]Unexpected error pinging {spec.name}: {exc}[/dim]")
        return f"[error]{type(exc).__name__}"
