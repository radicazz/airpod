"""Runtime mode detection (production vs development)."""

from __future__ import annotations

import os
import sys
from functools import lru_cache


@lru_cache(maxsize=1)
def is_dev_mode() -> bool:
    """
    Detect if running in development mode.
    
    Dev mode is enabled when:
    - The script name contains 'dairpods'
    - The AIRPODS_DEV_MODE environment variable is set to '1'
    
    Returns:
        True if in development mode, False for production mode.
    """
    # Check environment variable first
    if os.environ.get("AIRPODS_DEV_MODE") == "1":
        return True
    
    # Check if invoked via dairpods script
    if len(sys.argv) > 0:
        script_name = os.path.basename(sys.argv[0])
        if "dairpods" in script_name:
            return True
    
    return False


def get_resource_prefix() -> str:
    """
    Get the resource prefix for Podman resources based on mode.
    
    Returns:
        'airpods-dev' in dev mode, 'airpods' in production mode.
    """
    return "airpods-dev" if is_dev_mode() else "airpods"


def get_mode_name() -> str:
    """
    Get a human-readable mode name.
    
    Returns:
        'development' or 'production'
    """
    return "development" if is_dev_mode() else "production"
