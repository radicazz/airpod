from __future__ import annotations

from typing import Dict, List

from airpods import state
from airpods.services import ServiceRegistry, ServiceSpec, VolumeMount


def _webui_secret_env() -> Dict[str, str]:
    return {"WEBUI_SECRET_KEY": state.ensure_webui_secret()}


_SERVICE_SPECS: List[ServiceSpec] = [
    ServiceSpec(
        name="ollama",
        pod="ollama",
        container="ollama-0",
        image="docker.io/ollama/ollama:latest",
        ports=[(11434, 11434)],
        env={
            "OLLAMA_ORIGINS": "*",
            "OLLAMA_HOST": "0.0.0.0",
        },
        volumes=[VolumeMount("airpods_ollama_data", "/root/.ollama")],
        needs_gpu=True,
        health_path="/api/tags",
    ),
    ServiceSpec(
        name="open-webui",
        pod="open-webui",
        container="open-webui-0",
        image="ghcr.io/open-webui/open-webui:latest",
        ports=[(3000, 8080)],
        env={
            # Reach Ollama via the host-published port.
            "OLLAMA_BASE_URL": "http://host.containers.internal:11434",
        },
        env_factory=_webui_secret_env,
        volumes=[VolumeMount("airpods_webui_data", "/app/backend/data")],
        health_path="/",
    ),
]


REGISTRY = ServiceRegistry(_SERVICE_SPECS)
