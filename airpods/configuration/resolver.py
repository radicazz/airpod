"""Template resolution for configuration values."""

from __future__ import annotations

import re
from typing import Any, Dict

from .errors import ConfigurationError
from .schema import AirpodsConfig

TEMPLATE_PATTERN = re.compile(r"\{\{([^}]+)\}\}")
MAX_RESOLUTION_DEPTH = 100


def resolve_templates(config: AirpodsConfig) -> AirpodsConfig:
    """Resolve supported template variables inside configuration strings."""
    data = config.to_dict()

    context = {
        "runtime": data.get("runtime", {}),
        "services": {},
    }
    for service_name, service_data in data.get("services", {}).items():
        ports = service_data.get("ports", [])
        ports_list = []
        if isinstance(ports, dict):
            ports_list = [ports]
        elif isinstance(ports, list):
            ports_list = ports
        context["services"][service_name] = {
            "ports": ports_list,
            "image": service_data.get("image"),
            "pod": service_data.get("pod"),
            "default_model": service_data.get("default_model"),
        }

    services = data.get("services", {})
    for service_name, service_data in services.items():
        env = service_data.get("env", {})
        for key, value in list(env.items()):
            if isinstance(value, str) and "{{" in value:
                env[key] = _resolve_string(
                    value, context, location=f"services.{service_name}.env.{key}"
                )

        default_model = service_data.get("default_model")
        if isinstance(default_model, str) and "{{" in default_model:
            service_data["default_model"] = _resolve_string(
                default_model,
                context,
                location=f"services.{service_name}.default_model",
            )
            context["services"][service_name]["default_model"] = service_data[
                "default_model"
            ]

        default_model_url = service_data.get("default_model_url")
        if isinstance(default_model_url, str) and "{{" in default_model_url:
            service_data["default_model_url"] = _resolve_string(
                default_model_url,
                context,
                location=f"services.{service_name}.default_model_url",
            )

        command_args = service_data.get("command_args", {})
        if isinstance(command_args, dict):
            for key, value in list(command_args.items()):
                command_args[key] = _resolve_value(
                    value,
                    context,
                    location=f"services.{service_name}.command_args.{key}",
                )

        entrypoint = service_data.get("entrypoint_override")
        if isinstance(entrypoint, list):
            service_data["entrypoint_override"] = [
                _resolve_value(
                    item,
                    context,
                    location=f"services.{service_name}.entrypoint_override",
                )
                for item in entrypoint
            ]

    return AirpodsConfig.from_dict(data)


def _resolve_string(template: str, context: Dict[str, Any], *, location: str) -> str:
    missing: list[str] = []
    iteration = 0
    stack: list[str] = []

    current = template
    while "{{" in current:
        if iteration >= MAX_RESOLUTION_DEPTH:
            raise ConfigurationError(
                f"Circular reference or excessive nesting detected in {location}"
            )
        iteration += 1

        def _replace(match: re.Match[str]) -> str:
            path = match.group(1).strip()
            if path in stack:
                raise ConfigurationError(
                    f"Circular reference detected: {{{{{path}}}}} in {location}"
                )
            stack.append(path)
            try:
                value = _lookup_path(path, context)
            finally:
                stack.pop()
            if value is None:
                missing.append(path)
                return match.group(0)
            return str(value)

        resolved = TEMPLATE_PATTERN.sub(_replace, current)
        if resolved == current:
            break
        current = resolved

    if missing:
        refs = ", ".join(sorted(set(missing)))
        raise ConfigurationError(
            f"Unknown template reference(s) [{refs}] in {location}"
        )
    return current


def _lookup_path(path: str, context: Dict[str, Any]) -> Any:
    keys = path.split(".")
    value: Any = context
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        elif isinstance(value, list):
            try:
                index = int(key)
                value = value[index] if 0 <= index < len(value) else None
            except (ValueError, IndexError):
                return None
        else:
            return None
    return value


def _resolve_value(value: Any, context: Dict[str, Any], *, location: str) -> Any:
    if isinstance(value, str) and "{{" in value:
        return _resolve_string(value, context, location=location)
    if isinstance(value, list):
        resolved = []
        for item in value:
            if isinstance(item, str) and "{{" in item:
                resolved.append(_resolve_string(item, context, location=location))
            else:
                resolved.append(item)
        return resolved
    return value
