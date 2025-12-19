"""GPU device detection and device flag generation for Podman."""

from __future__ import annotations

import shutil
import subprocess
from typing import Optional, Tuple


def detect_nvidia_container_toolkit() -> Tuple[bool, str]:
    """
    Detect if NVIDIA Container Toolkit is installed.

    Returns:
        (installed, version_or_error)
    """
    if shutil.which("nvidia-ctk") is None:
        return False, "nvidia-ctk not found"

    try:
        proc = subprocess.run(
            ["nvidia-ctk", "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=True,
            timeout=5,
        )
        output = proc.stdout.strip()
        # Extract version from output like "NVIDIA Container Toolkit CLI version 1.18.1"
        if "version" in output.lower():
            parts = output.split()
            for i, part in enumerate(parts):
                if part.lower() == "version" and i + 1 < len(parts):
                    return True, parts[i + 1]
        return True, output
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, Exception) as e:
        return False, f"nvidia-ctk check failed: {e}"


def check_cdi_available() -> bool:
    """
    Check if NVIDIA CDI (Container Device Interface) is available.

    Returns:
        True if CDI is configured and available
    """
    try:
        proc = subprocess.run(
            ["nvidia-ctk", "cdi", "list"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            timeout=5,
        )
        # If the command succeeds and has output, CDI is available
        return proc.returncode == 0 and bool(proc.stdout.strip())
    except (subprocess.TimeoutExpired, Exception):
        return False


def get_podman_gpu_flag(config_flag: Optional[str] = None) -> Optional[str]:
    """
    Determine the appropriate GPU device flag for Podman.

    Args:
        config_flag: User-configured flag from config (can be "auto", explicit flag, or None)

    Returns:
        Device flag string to pass to Podman, or None if no GPU support detected
    """
    # If user specified an explicit flag (not "auto"), use it
    if config_flag and config_flag != "auto":
        return config_flag

    # Auto-detection: check for NVIDIA Container Toolkit
    toolkit_installed, _ = detect_nvidia_container_toolkit()
    if not toolkit_installed:
        return None

    # Check if CDI is available (modern method, recommended)
    if check_cdi_available():
        # Use CDI method - works with Podman 3.2+ and nvidia-ctk 1.16+
        return "--device nvidia.com/gpu=all --security-opt=label=disable"

    # Fallback to legacy method (requires nvidia-container-runtime)
    # This may not work on all systems, but is the best fallback
    return "--gpus all --security-opt=label=disable"


def get_docker_gpu_flag(config_flag: Optional[str] = None) -> Optional[str]:
    """
    Determine the appropriate GPU device flag for Docker.

    Args:
        config_flag: User-configured flag from config (can be "auto", explicit flag, or None)

    Returns:
        Device flag string to pass to Docker, or None if no GPU support detected
    """
    # If user specified an explicit flag (not "auto"), use it
    if config_flag and config_flag != "auto":
        return config_flag

    # Auto-detection: check for NVIDIA Container Toolkit
    toolkit_installed, _ = detect_nvidia_container_toolkit()
    if not toolkit_installed:
        return None

    # Docker uses --gpus with explicit capabilities to avoid mounting display libraries
    # This prevents errors with missing EGL/Wayland libraries on headless systems
    return '--gpus "device=all,capabilities=compute,utility"'


def get_gpu_device_flag(
    runtime: str = "podman", config_flag: Optional[str] = None
) -> Optional[str]:
    """
    Determine the appropriate GPU device flag for the specified runtime.

    Args:
        runtime: Container runtime ("podman" or "docker")
        config_flag: User-configured flag from config (can be "auto", explicit flag, or None)

    Returns:
        Device flag string to pass to the runtime, or None if no GPU support detected
    """
    if runtime == "docker":
        return get_docker_gpu_flag(config_flag)
    return get_podman_gpu_flag(config_flag)


def get_cdi_setup_instructions() -> str:
    """Return instructions for setting up NVIDIA CDI."""
    return """
NVIDIA CDI Setup Required

To enable GPU support in Podman containers, configure NVIDIA CDI:

  1. Generate CDI specification:
     sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml

  2. Verify CDI is working:
     nvidia-ctk cdi list

  3. Restart Ollama:
     airpods stop ollama
     airpods start ollama

For more information:
  https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html
""".strip()
