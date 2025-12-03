"""Public interface for the airpods configuration system."""

from __future__ import annotations

from .errors import ConfigurationError
from .loader import (
    get_config,
    load_config,
    locate_config_file,
    merge_configs,
    reload_config,
)

__all__ = [
    "ConfigurationError",
    "get_config",
    "load_config",
    "locate_config_file",
    "merge_configs",
    "reload_config",
]
