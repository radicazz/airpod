"""Shell completion helpers for the airpods CLI."""

from __future__ import annotations

from typing import Any, Iterable, List

import click
import typer
from click.shell_completion import CompletionItem

from airpods.configuration import ConfigurationError, get_config

from .common import manager

CompletionList = List[CompletionItem]


def service_name_completion(
    ctx: typer.Context | None,  # noqa: ARG001 - required by Click shell completion
    param: click.Parameter | None,  # noqa: ARG001
    incomplete: str,
) -> CompletionList:
    """Return service name suggestions filtered by the user's partial input."""

    matches = _match_candidates(manager.registry.names(), incomplete)
    return _as_completion_items(matches)


def config_key_completion(
    ctx: typer.Context | None,  # noqa: ARG001
    param: click.Parameter | None,  # noqa: ARG001
    incomplete: str,
) -> CompletionList:
    """Suggest configuration keys in dot notation for config get/set commands."""

    try:
        config = get_config()
        data = config.to_dict()
    except ConfigurationError:
        data = {}

    keys = sorted(dict.fromkeys(_flatten_keys(data)))
    matches = _match_candidates(keys, incomplete)
    return _as_completion_items(matches)


def _match_candidates(candidates: Iterable[str], needle: str) -> List[str]:
    term = (needle or "").lower()
    return [candidate for candidate in candidates if candidate.lower().startswith(term)]


def _flatten_keys(value: Any, prefix: str | None = None) -> List[str]:
    keys: List[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            next_prefix = f"{prefix}.{key}" if prefix else key
            keys.extend(_flatten_keys(nested, next_prefix))
        return keys
    if isinstance(value, list):
        for index, item in enumerate(value):
            next_prefix = f"{prefix}.{index}" if prefix else str(index)
            keys.extend(_flatten_keys(item, next_prefix))
        return keys
    if prefix:
        keys.append(prefix)
    return keys


def _as_completion_items(matches: List[str]) -> CompletionList:
    return [CompletionItem(match) for match in matches]


__all__ = [
    "service_name_completion",
    "config_key_completion",
]
