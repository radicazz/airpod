"""Type definitions for the CLI module.

This module provides type aliases used throughout the CLI package to ensure
type safety and consistency across command registration and handling.
"""

from __future__ import annotations

from typing import Dict

from typer.models import CommandFunctionType

# Maps command names to their handler functions for registration
CommandMap = Dict[str, CommandFunctionType]
