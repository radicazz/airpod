"""Tests for GPU device flag generation."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from airpods.gpu import (
    check_cdi_available,
    detect_nvidia_container_toolkit,
    get_docker_gpu_flag,
    get_gpu_device_flag,
    get_podman_gpu_flag,
)


class TestNvidiaContainerToolkitDetection:
    """Test NVIDIA Container Toolkit detection."""

    @patch("airpods.gpu.shutil.which")
    def test_detect_nvidia_ctk_not_found(self, mock_which):
        """Should return False when nvidia-ctk is not in PATH."""
        mock_which.return_value = None
        installed, msg = detect_nvidia_container_toolkit()
        assert installed is False
        assert msg == "nvidia-ctk not found"

    @patch("airpods.gpu.subprocess.run")
    @patch("airpods.gpu.shutil.which")
    def test_detect_nvidia_ctk_found(self, mock_which, mock_run):
        """Should return True when nvidia-ctk is found and runs."""
        mock_which.return_value = "/usr/bin/nvidia-ctk"
        mock_run.return_value.stdout = "NVIDIA Container Toolkit CLI version 1.18.1"
        installed, version = detect_nvidia_container_toolkit()
        assert installed is True
        assert "1.18.1" in version


class TestCDIAvailability:
    """Test CDI availability checking."""

    @patch("airpods.gpu.subprocess.run")
    def test_cdi_available(self, mock_run):
        """Should return True when CDI list succeeds."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "nvidia.com/gpu=0\nnvidia.com/gpu=all"
        assert check_cdi_available() is True

    @patch("airpods.gpu.subprocess.run")
    def test_cdi_not_available(self, mock_run):
        """Should return False when CDI list fails."""
        mock_run.return_value.returncode = 1
        mock_run.return_value.stdout = ""
        assert check_cdi_available() is False


class TestPodmanGPUFlag:
    """Test Podman GPU flag generation."""

    def test_explicit_flag_returned(self):
        """Should return user-specified flag when not 'auto'."""
        flag = get_podman_gpu_flag("--custom-gpu-flag")
        assert flag == "--custom-gpu-flag"

    @patch("airpods.gpu.detect_nvidia_container_toolkit")
    def test_no_toolkit_returns_none(self, mock_detect):
        """Should return None when toolkit is not installed."""
        mock_detect.return_value = (False, "not found")
        flag = get_podman_gpu_flag()
        assert flag is None

    @patch("airpods.gpu.check_cdi_available")
    @patch("airpods.gpu.detect_nvidia_container_toolkit")
    def test_cdi_method_preferred(self, mock_detect, mock_cdi):
        """Should use CDI method when available."""
        mock_detect.return_value = (True, "1.18.1")
        mock_cdi.return_value = True
        flag = get_podman_gpu_flag()
        assert flag == "--device nvidia.com/gpu=all --security-opt=label=disable"

    @patch("airpods.gpu.check_cdi_available")
    @patch("airpods.gpu.detect_nvidia_container_toolkit")
    def test_legacy_fallback(self, mock_detect, mock_cdi):
        """Should fall back to legacy method when CDI unavailable."""
        mock_detect.return_value = (True, "1.16.0")
        mock_cdi.return_value = False
        flag = get_podman_gpu_flag()
        assert flag == "--gpus all --security-opt=label=disable"


class TestDockerGPUFlag:
    """Test Docker GPU flag generation."""

    def test_explicit_flag_returned(self):
        """Should return user-specified flag when not 'auto'."""
        flag = get_docker_gpu_flag("--custom-gpu-flag")
        assert flag == "--custom-gpu-flag"

    @patch("airpods.gpu.detect_nvidia_container_toolkit")
    def test_no_toolkit_returns_none(self, mock_detect):
        """Should return None when toolkit is not installed."""
        mock_detect.return_value = (False, "not found")
        flag = get_docker_gpu_flag()
        assert flag is None

    @patch("airpods.gpu.detect_nvidia_container_toolkit")
    def test_docker_uses_gpus_with_capabilities(self, mock_detect):
        """Should return --gpus with explicit capabilities for Docker."""
        mock_detect.return_value = (True, "1.18.1")
        flag = get_docker_gpu_flag()
        assert flag == '--gpus "device=all,capabilities=compute,utility"'
        # Ensure no SELinux security-opt is included
        assert "security-opt" not in flag
        # Ensure capabilities are explicitly specified
        assert "capabilities=compute,utility" in flag


class TestGetGPUDeviceFlag:
    """Test runtime-aware GPU flag selection."""

    @patch("airpods.gpu.get_docker_gpu_flag")
    def test_docker_runtime_calls_docker_function(self, mock_docker):
        """Should call get_docker_gpu_flag for docker runtime."""
        mock_docker.return_value = "--gpus all"
        flag = get_gpu_device_flag("docker", "auto")
        mock_docker.assert_called_once_with("auto")
        assert flag == "--gpus all"

    @patch("airpods.gpu.get_podman_gpu_flag")
    def test_podman_runtime_calls_podman_function(self, mock_podman):
        """Should call get_podman_gpu_flag for podman runtime."""
        mock_podman.return_value = (
            "--device nvidia.com/gpu=all --security-opt=label=disable"
        )
        flag = get_gpu_device_flag("podman", "auto")
        mock_podman.assert_called_once_with("auto")
        assert flag == "--device nvidia.com/gpu=all --security-opt=label=disable"

    @patch("airpods.gpu.get_podman_gpu_flag")
    def test_default_runtime_is_podman(self, mock_podman):
        """Should default to podman when runtime not specified."""
        mock_podman.return_value = (
            "--device nvidia.com/gpu=all --security-opt=label=disable"
        )
        flag = get_gpu_device_flag()
        mock_podman.assert_called_once()
