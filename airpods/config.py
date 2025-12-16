from __future__ import annotations

from typing import Dict, List, Optional

from airpods import state
from airpods.configuration import get_config
from airpods.configuration.errors import ConfigurationError
from airpods.configuration.schema import AirpodsConfig, ServiceConfig
from airpods.services import ServiceRegistry, ServiceSpec, VolumeMount
from airpods.cuda import select_cuda_version
from airpods.comfyui import (
    select_comfyui_image,
    select_provider,
    get_default_env,
    get_comfyui_volumes,
)
from airpods.system import detect_cuda_compute_capability
from airpods.logging import console


ENABLE_COMFY_CUDA_LOG = False


_BIND_VOLUME_PREFIX = "bind://"


def _webui_secret_env() -> Dict[str, str]:
    return {"WEBUI_SECRET_KEY": state.ensure_webui_secret()}


def _resolve_volume_source(source: str) -> str:
    if not source:
        raise ConfigurationError("volume source cannot be empty")
    if source.startswith(_BIND_VOLUME_PREFIX):
        relative = source[len(_BIND_VOLUME_PREFIX) :].strip()
        if not relative:
            raise ConfigurationError(
                "bind:// volume sources must include a relative path (e.g. bind://comfyui/workspace)"
            )
        try:
            return str(state.resolve_volume_path(relative))
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise ConfigurationError(str(exc)) from exc
    return source


def _resolve_cuda_image(
    name: str, service: ServiceConfig, config: AirpodsConfig
) -> str:
    """Resolve CUDA-specific image for ComfyUI service based on GPU capability detection."""
    if name != "comfyui":
        return service.image

    # Priority chain: service override → runtime setting → auto-detection → fallback
    selected_cuda_version = None
    selection_source = None

    # Detect GPU capability for provider selection
    has_gpu, gpu_name, compute_cap = detect_cuda_compute_capability()

    if service.cuda_override:
        selected_cuda_version = service.cuda_override
        selection_source = f"service override ({service.cuda_override})"
    elif config.runtime.cuda_version != "auto":
        selected_cuda_version = config.runtime.cuda_version
        selection_source = f"runtime setting ({config.runtime.cuda_version})"
    else:
        # Auto-detection
        if has_gpu and compute_cap:
            selected_cuda_version = select_cuda_version(compute_cap)
            major, minor = compute_cap
            selection_source = (
                f"auto-detected (compute {major}.{minor} → {selected_cuda_version})"
            )
        else:
            # Fallback to cu126 (backwards compatible default)
            selected_cuda_version = "cu126"
            selection_source = f"fallback (GPU detection failed: {gpu_name})"

    # Select provider (yanwk vs mmartial) based on GPU capability
    # Respects user preference from config, or auto-selects based on GPU
    provider_pref = config.runtime.comfyui_provider
    provider = select_provider(compute_cap, provider_pref)

    # Force CPU if GPU is disabled for this service
    force_cpu = service.gpu.force_cpu or not service.gpu.enabled
    resolved_image = select_comfyui_image(
        selected_cuda_version, force_cpu=force_cpu, provider=provider
    )

    # Log the selection for transparency
    if ENABLE_COMFY_CUDA_LOG and resolved_image != service.image:
        console.print(f"[info]ComfyUI CUDA: {selection_source} → {resolved_image}[/]")

    return resolved_image


def _get_comfyui_provider(config: AirpodsConfig):
    """Detect ComfyUI provider based on GPU capability and config."""
    has_gpu, gpu_name, compute_cap = detect_cuda_compute_capability()
    # Use runtime.comfyui_provider setting (defaults to "auto")
    provider_pref = config.runtime.comfyui_provider
    return select_provider(compute_cap, provider_pref)


def _get_comfyui_provider_env(config: AirpodsConfig) -> Dict[str, str]:
    """Get provider-specific environment variables for ComfyUI."""
    provider = _get_comfyui_provider(config)
    return get_default_env(provider)


def _service_spec_from_config(
    name: str, service: ServiceConfig, config: AirpodsConfig
) -> ServiceSpec:
    # Handle ComfyUI provider-specific volumes
    if name == "comfyui":
        provider = _get_comfyui_provider(config)
        provider_volumes = get_comfyui_volumes(provider)

        # Build volumes from config, then add provider-specific defaults
        volumes = []
        for vol_name, mount in service.volumes.items():
            volumes.append(
                VolumeMount(_resolve_volume_source(mount.source), mount.target)
            )

        # Add provider-specific volumes if not already configured
        configured_targets = {vol.target for vol in volumes}
        for vol_name, (source_suffix, target) in provider_volumes.items():
            if target not in configured_targets:
                volumes.append(
                    VolumeMount(
                        _resolve_volume_source(f"bind://{source_suffix}"), target
                    )
                )
    else:
        # Non-ComfyUI services use standard volume handling
        volumes = [
            VolumeMount(_resolve_volume_source(mount.source), mount.target)
            for mount in service.volumes.values()
        ]

    ports = [(port.host, port.container) for port in service.ports]
    env_factory = _webui_secret_env if service.needs_webui_secret else None

    # Resolve CUDA-aware image for ComfyUI
    resolved_image = _resolve_cuda_image(name, service, config)

    # Build environment variables with provider-specific defaults
    env = dict(service.env)
    if name == "comfyui":
        # Add provider-specific environment variables (mmartial needs extra env vars)
        provider_env = _get_comfyui_provider_env(config)
        # User-configured env takes precedence over provider defaults
        for key, value in provider_env.items():
            if key not in env:
                env[key] = value

    # Conditionally inject Ollama configuration for open-webui service
    if name == "open-webui" and service.auto_configure_ollama:
        ollama_service = config.services.get("ollama")
        if ollama_service and ollama_service.ports:
            ollama_port = ollama_service.ports[0].host
            env.update(
                {
                    "OLLAMA_BASE_URL": f"http://localhost:{ollama_port}",
                    "OPENAI_API_BASE_URL": f"http://localhost:{ollama_port}/v1",
                    "OPENAI_API_KEY": "ollama",
                }
            )

    # Set userns_mode for mmartial ComfyUI (needs keep-id for proper file ownership at pod level)
    userns_mode = None
    if name == "comfyui":
        provider = _get_comfyui_provider(config)
        if provider == "mmartial":
            userns_mode = "keep-id"

    return ServiceSpec(
        name=name,
        pod=service.pod,
        container=service.container,
        image=resolved_image,
        ports=ports,
        env=env,
        env_factory=env_factory,
        volumes=volumes,
        pids_limit=service.pids_limit,
        needs_gpu=service.gpu.enabled,
        health_path=service.health.path,
        force_cpu=service.gpu.force_cpu,
        userns_mode=userns_mode,
    )


def _load_service_specs(config: Optional[AirpodsConfig] = None) -> List[ServiceSpec]:
    config = config or get_config()
    specs: List[ServiceSpec] = []
    for name, service in config.services.items():
        if not service.enabled:
            continue
        specs.append(_service_spec_from_config(name, service, config))
    return specs


REGISTRY = ServiceRegistry(_load_service_specs())


def reload_registry(config: Optional[AirpodsConfig] = None) -> ServiceRegistry:
    """Rebuild the service registry from the latest configuration."""
    global REGISTRY
    REGISTRY = ServiceRegistry(_load_service_specs(config))
    return REGISTRY