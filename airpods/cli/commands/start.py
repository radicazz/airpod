"""Start command implementation for launching Podman containers."""

from __future__ import annotations

import queue
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional

import typer
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from airpods.logging import console, status_spinner
from airpods.system import detect_gpu, detect_cuda_compute_capability
from airpods.cuda import select_cuda_version, get_cuda_info_display
from airpods.services import ServiceSpec

from ..common import (
    COMMAND_CONTEXT,
    ensure_podman_available,
    format_transfer_label,
    is_verbose_mode,
    manager,
    print_network_status,
    print_volume_status,
    print_config_info,
    refresh_cli_context,
    resolve_services,
    get_cli_config,
)
from ..completions import service_name_completion
from ..help import command_help_option, maybe_show_command_help
from ..status_view import check_service_health, collect_host_ports
from ..type_defs import CommandMap


def register(app: typer.Typer) -> CommandMap:
    @app.command(context_settings=COMMAND_CONTEXT)
    def start(
        ctx: typer.Context,
        help_: bool = command_help_option(),
        service: Optional[list[str]] = typer.Argument(
            None,
            help="Services to start (default: all).",
            shell_complete=service_name_completion,
        ),
        force_cpu: bool = typer.Option(
            False, "--cpu", help="Force CPU even if GPU is present."
        ),
        sequential: bool = typer.Option(
            False,
            "--sequential",
            help="Pull images sequentially (overrides cli.max_concurrent_pulls).",
        ),
        pre_fetch: bool = typer.Option(
            False,
            "--pre-fetch",
            help="Download service images without starting containers.",
        ),
        wait: bool = typer.Option(
            False,
            "--wait",
            help="Wait for HTTP health checks before returning (may take a while for some services).",
        ),
    ) -> None:
        """Start pods for specified services."""
        maybe_show_command_help(ctx, help_)

        # Ensure user config exists
        from airpods.configuration import locate_config_file
        from airpods.state import configs_dir
        from airpods.configuration.defaults import DEFAULT_CONFIG_DICT
        import tomlkit
        from airpods.paths import detect_repo_root

        user_config_path = configs_dir() / "config.toml"
        repo_root = detect_repo_root()

        config_path = locate_config_file()
        if not user_config_path.exists():
            should_create = config_path is None
            if not should_create and repo_root and config_path:
                should_create = config_path.is_relative_to(repo_root)
            if should_create:
                user_config_path.parent.mkdir(parents=True, exist_ok=True)
                document = tomlkit.document()
                document.update(DEFAULT_CONFIG_DICT)
                user_config_path.write_text(tomlkit.dumps(document), encoding="utf-8")
                console.print(f"[ok]Created default config at {user_config_path}[/]")
                refresh_cli_context()
                config_path = user_config_path

        if config_path is None:
            config_path = locate_config_file()

        # Check verbose mode from context
        verbose = is_verbose_mode(ctx)
        print_config_info(config_path, verbose=verbose)

        specs = resolve_services(service)
        ensure_podman_available()

        # Enable CUDA logging during startup flows
        import airpods.config as config_module

        config_module.ENABLE_COMFY_CUDA_LOG = True

        cli_config = get_cli_config()
        max_concurrent_pulls = 1 if sequential else cli_config.max_concurrent_pulls

        if pre_fetch:
            _pull_images_with_progress(specs, max_concurrent=max_concurrent_pulls)
            return

        if not specs:
            console.print(
                "[warn]No services are enabled for this configuration; nothing to start.[/]"
            )
            return

        # Check what's already running first
        pod_rows = manager.pod_status_rows() or {}
        already_running = []
        needs_start = []

        for spec in specs:
            row = pod_rows.get(spec.pod)
            if row and row.get("Status") == "Running":
                # Verify the container is actually running
                if manager.container_exists(spec):
                    already_running.append(spec)
                else:
                    needs_start.append(spec)
            else:
                needs_start.append(spec)

        # If everything is already running, just report and exit
        if not needs_start:
            console.print("[ok]All services already running[/]")
            from airpods.cli.status_view import render_status

            render_status(specs)
            return

        # Report what's already running
        if already_running:
            running_names = ", ".join(spec.name for spec in already_running)
            console.print(f"Already running: [ok]{running_names}[/]")

        # Only process services that need to be started
        specs_to_start = needs_start

        # Show GPU status
        gpu_available, gpu_detail = detect_gpu()
        if gpu_available:
            console.print(f"GPU: [ok]enabled[/] ({gpu_detail})")
        else:
            console.print(f"GPU: [muted]not detected[/] ({gpu_detail})")

        # Show CUDA detection info if ComfyUI is being started
        comfyui_specs = [s for s in specs_to_start if s.name == "comfyui"]
        if comfyui_specs:
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

        # Only ensure network/volumes if we're actually starting something
        with status_spinner("Ensuring network"):
            network_created = manager.ensure_network()
        print_network_status(network_created, manager.network_name, verbose=verbose)

        with status_spinner("Ensuring volumes"):
            volume_results = manager.ensure_volumes(specs_to_start)
        print_volume_status(volume_results, verbose=verbose)

        # Sync Open WebUI plugins if webui is being started
        from airpods import plugins

        webui_specs = [s for s in specs_to_start if s.name == "open-webui"]
        if webui_specs:
            with status_spinner("Syncing Open WebUI plugins"):
                synced = plugins.sync_plugins()
            # Only show plugin sync messages if changes were made
            if synced > 0:
                console.print(f"[ok]Synced {synced} plugin(s)[/]")
            elif verbose:
                console.print("[info]Plugins already up-to-date[/]")

        # Simple log-based startup process
        service_urls: dict[str, str] = {}
        failed_services = []
        timeout_services = []

        # Pull images with live progress so long pulls don't feel like a hang.
        _pull_images_with_progress(
            specs_to_start, max_concurrent=max_concurrent_pulls, verbose=verbose
        )

        # Start services with simple logging
        for spec in specs_to_start:
            console.print(f"Starting [accent]{spec.name}[/]...")

            try:
                with status_spinner(f"Launching {spec.name}"):
                    manager.start_service(
                        spec,
                        gpu_available=gpu_available,
                        force_cpu_override=force_cpu,
                    )
            except Exception as e:
                console.print(f"[error]✗ Failed to start {spec.name}: {e}[/]")
                failed_services.append(spec.name)
                continue

        # If we're not waiting for readiness, return after pods are launched.
        if not wait:
            started = [
                spec.name for spec in specs_to_start if spec.name not in failed_services
            ]
            if started:
                console.print(
                    f"[ok]✓ Launched {len(started)} service{'s' if len(started) != 1 else ''}: {', '.join(started)}[/]"
                )
            if failed_services:
                console.print(
                    f"[error]✗ Failed services: {', '.join(failed_services)}. "
                    "Check logs with 'airpods logs'[/]"
                )
                raise typer.Exit(code=1)
            console.print(
                "[dim]Tip: Use 'airpods status' to check readiness and URLs, or 'airpods logs <service>' to watch startup.[/dim]"
            )
            return

        # Wait for health checks with timeout
        start_time = time.time()
        timeout_seconds = cli_config.startup_timeout
        check_interval = cli_config.startup_check_interval

        with status_spinner(
            f"Waiting for services to become ready (up to {timeout_seconds}s)"
        ) as status:
            while True:
                elapsed = time.time() - start_time
                if elapsed >= timeout_seconds:
                    break

                pod_rows = manager.pod_status_rows() or {}
                all_done = True
                pending: list[str] = []

                for spec in specs_to_start:
                    if spec.name in failed_services:
                        continue

                    if spec.name in service_urls:
                        continue  # Already healthy / ready

                    row = pod_rows.get(spec.pod)
                    if not row:
                        all_done = False
                        pending.append(spec.name)
                        continue

                    pod_status = (row.get("Status") or "").strip()

                    if pod_status in {"Exited", "Error"}:
                        if spec.name not in failed_services:
                            failed_services.append(spec.name)
                        continue

                    if pod_status != "Running":
                        all_done = False
                        pending.append(spec.name)
                        continue

                    port_bindings = manager.service_ports(spec)
                    host_ports = collect_host_ports(spec, port_bindings)
                    host_port = host_ports[0] if host_ports else None

                    if not spec.health_path or host_port is None:
                        # No health check needed; pod running is "ready".
                        if host_port:
                            service_urls[spec.name] = f"http://localhost:{host_port}"
                        else:
                            service_urls[spec.name] = ""
                        continue

                    if check_service_health(spec, host_port):
                        service_urls[spec.name] = f"http://localhost:{host_port}"
                    else:
                        all_done = False
                        pending.append(spec.name)

                if all_done:
                    break

                remaining = max(0, int(timeout_seconds - elapsed))
                if pending:
                    pending_label = ", ".join(pending)
                    status.update(
                        f"[info]Waiting ({remaining}s left): {pending_label}[/]"
                    )
                else:
                    status.update(f"[info]Waiting ({remaining}s left)[/]")

                time.sleep(check_interval)

        # Handle timeouts
        for spec in specs_to_start:
            if spec.name not in failed_services and spec.name not in service_urls:
                timeout_services.append(spec.name)

        # Categorize results
        healthy_services = [
            name for name in service_urls.keys() if name not in failed_services
        ]
        failed = failed_services

        # Show clean completion summary
        if healthy_services:
            urls = [
                service_urls.get(name)
                for name in healthy_services
                if service_urls.get(name)
            ]
            url_display = f" • {', '.join(urls)}" if urls else ""
            console.print(
                f"[ok]✓ Started {len(healthy_services)} service{'s' if len(healthy_services) != 1 else ''}{url_display}[/]"
            )

        if failed:
            console.print(
                f"[error]✗ Failed services: {', '.join(failed)}. "
                "Check logs with 'airpods logs'[/]"
            )
            raise typer.Exit(code=1)

        if timeout_services:
            console.print(
                f"[warn]⏱ Timed out services: {', '.join(timeout_services)}. "
                "Services may still be starting. Check with 'airpods status'[/]"
            )

        # Auto-pull Ollama models if configured and service is healthy
        ollama_specs = [s for s in specs_to_start if s.name == "ollama"]
        if (
            ollama_specs
            and "ollama" in service_urls
            and "ollama" not in failed_services
        ):
            from airpods import ollama as ollama_module
            from airpods.cli.common import get_ollama_port
            from airpods.configuration import get_config

            config = get_config()
            auto_pull = config.services.get("ollama", None)
            auto_pull_models = auto_pull.auto_pull_models if auto_pull else []

            if auto_pull_models:
                port = get_ollama_port()

                # Get list of installed models
                try:
                    installed = ollama_module.list_models(port)
                    installed_names = {m.get("name") for m in installed}

                    # Filter out models that are already installed
                    to_pull = [m for m in auto_pull_models if m not in installed_names]

                    if to_pull:
                        console.print(
                            f"[info]Auto-pulling {len(to_pull)} model(s)...[/]"
                        )

                        for model_name in to_pull:
                            try:
                                console.print(f"  Pulling [accent]{model_name}[/]...")
                                ollama_module.pull_model(model_name, port)
                                console.print(f"  [ok]✓ {model_name} ready[/]")
                            except Exception as e:
                                console.print(
                                    f"  [warn]Failed to pull {model_name}: {e}[/]"
                                )
                    elif verbose:
                        console.print("[info]All auto-pull models already installed[/]")

                except Exception as e:
                    console.print(f"[warn]Auto-pull failed: {e}[/]")

        # Auto-import plugins into Open WebUI if service is healthy
        if (
            webui_specs
            and "open-webui" in service_urls
            and "open-webui" not in failed_services
        ):
            with status_spinner("Auto-importing plugins into Open WebUI"):
                try:
                    plugins_dir = plugins.get_plugins_target_dir()
                    container_name = webui_specs[0].container
                    owner_id = plugins.resolve_plugin_owner_user_id(
                        container_name, cli_config.plugin_owner
                    )
                    imported = plugins.import_plugins_to_webui(
                        plugins_dir,
                        admin_user_id=owner_id,
                        container_name=container_name,
                    )
                    if imported > 0:
                        console.print(
                            f"[ok]✓ Auto-imported {imported} plugin(s) into Open WebUI[/]"
                        )
                    elif verbose:
                        console.print(
                            "[info]No new plugins to import (may already exist)[/]"
                        )
                except Exception as e:
                    console.print(
                        f"[warn]Plugin auto-import failed: {e}. "
                        "Plugins are synced to filesystem and can be imported manually via UI.[/]"
                    )

    return {"start": start}


@dataclass(frozen=True)
class _PullEvent:
    kind: str
    task_id: int
    payload: str = ""


def _pull_images_with_progress(
    specs: list[ServiceSpec], *, max_concurrent: int, verbose: bool = False
) -> None:
    if not specs:
        console.print("[warn]No services enabled; nothing to initialize.[/]")
        return

    events: queue.Queue[_PullEvent] = queue.Queue()
    max_workers = max(1, max_concurrent)

    def _iter_pull_lines(stream: str):
        # Podman may emit carriage-return progress; normalize to line events.
        for chunk in stream.splitlines():
            for part in chunk.split("\r"):
                line = part.strip()
                if line:
                    yield line

    def _pull_one(spec: ServiceSpec, task_id: int) -> None:
        start = time.perf_counter()
        events.put(_PullEvent("start", task_id))
        try:
            proc = subprocess.Popen(
                ["podman", "pull", spec.image],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except OSError as exc:
            events.put(_PullEvent("error", task_id, str(exc)))
            return
        output: list[str] = []
        try:
            assert proc.stdout is not None
            for raw in proc.stdout:
                output.append(raw)
                for line in _iter_pull_lines(raw):
                    events.put(_PullEvent("line", task_id, line))
        finally:
            rc = proc.wait()

        if rc != 0:
            detail = "".join(output).strip()
            events.put(_PullEvent("error", task_id, detail))
            return

        elapsed = time.perf_counter() - start
        size = manager.runtime.image_size(spec.image)
        transfer = format_transfer_label(size, elapsed) or f"{elapsed:.1f}s"
        events.put(_PullEvent("done", task_id, transfer))

    title = "[info]Pulling Images"
    if verbose:
        title = "[info]Pulling Images (live)"

    with Progress(
        SpinnerColumn(style="accent"),
        TextColumn("{task.fields[service]}", style="cyan", justify="right"),
        BarColumn(bar_width=None),
        TextColumn("{task.fields[status]}", style="muted", markup=True),
        TextColumn("{task.fields[transfer]}", style="dim", justify="right"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        tasks: dict[int, ServiceSpec] = {}
        task_ids: dict[str, int] = {}

        for spec in specs:
            task_id = progress.add_task(
                title,
                total=None,
                service=spec.name,
                status="Waiting…",
                transfer="",
            )
            tasks[task_id] = spec
            task_ids[spec.name] = task_id

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(_pull_one, spec, task_ids[spec.name]) for spec in specs
            ]

            failures: list[tuple[str, str]] = []
            done_count = 0
            while done_count < len(specs):
                try:
                    event = events.get(timeout=0.1)
                except queue.Empty:
                    continue

                if event.kind == "start":
                    progress.update(event.task_id, status="Pulling…", transfer="")
                elif event.kind == "line":
                    # Keep status compact; podman emits a lot of noise.
                    line = event.payload
                    if len(line) > 80:
                        line = f"{line[:77]}…"
                    progress.update(event.task_id, status=line)
                elif event.kind == "done":
                    progress.update(
                        event.task_id,
                        status="[ok]✓ Ready[/]",
                        transfer=event.payload,
                        total=1,
                        completed=1,
                    )
                    done_count += 1
                elif event.kind == "error":
                    spec = tasks.get(event.task_id)
                    failures.append((spec.name if spec else "unknown", event.payload))
                    progress.update(
                        event.task_id,
                        status="[error]✗ Failed[/]",
                        transfer="",
                        total=1,
                        completed=1,
                    )
                    done_count += 1

            for future in futures:
                future.result()

        if failures:
            if verbose:
                for name, detail in failures:
                    if detail:
                        console.print(f"[error]{name} pull error:[/] {detail}")
            console.print("[error]✗ Failed to pull one or more images[/]")
            raise typer.Exit(code=1)
