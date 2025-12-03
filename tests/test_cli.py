from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from airpods.cli import app
from airpods.services import EnvironmentReport
from airpods.system import CheckResult


runner = CliRunner()


class TestCLIBasics:
    """Test basic CLI functionality."""

    def test_version_flag(self):
        """Test --version flag displays version."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "airpods" in result.stdout

    def test_help_flag(self):
        """Test --help flag displays help."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Commands" in result.stdout

    def test_version_command(self):
        """Test version command."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "airpods" in result.stdout


class TestCommandAliases:
    """Test that command aliases work correctly."""

    @patch("airpods.cli.manager")
    @patch("airpods.cli.detect_gpu")
    def test_up_alias(self, mock_gpu, mock_manager):
        """Test 'up' as alias for 'start'."""
        mock_gpu.return_value = (False, "CPU")
        mock_manager.resolve.return_value = []
        mock_manager.ensure_podman.return_value = None

        result = runner.invoke(app, ["up"])
        assert result.exit_code == 0

    @patch("airpods.cli.manager")
    def test_down_alias(self, mock_manager):
        """Test 'down' as alias for 'stop'."""
        mock_manager.resolve.return_value = []
        mock_manager.ensure_podman.return_value = None

        result = runner.invoke(app, ["down"])
        assert result.exit_code == 0

    @patch("airpods.cli.manager")
    def test_ps_alias(self, mock_manager):
        """Test 'ps' as alias for 'status'."""
        mock_manager.resolve.return_value = []
        mock_manager.ensure_podman.return_value = None
        mock_manager.pod_status_rows.return_value = {}

        result = runner.invoke(app, ["ps"])
        assert result.exit_code == 0


class TestDoctorCommand:
    """Test the doctor command behavior."""

    @patch("airpods.cli.ui.show_environment")
    @patch("airpods.cli.manager")
    def test_doctor_success(self, mock_manager, mock_show_env):
        report = EnvironmentReport(checks=[], gpu_available=False, gpu_detail="n/a")
        mock_manager.report_environment.return_value = report

        result = runner.invoke(app, ["doctor"])

        assert result.exit_code == 0
        assert "doctor complete" in result.stdout.lower()
        mock_show_env.assert_called_once_with(report)

    @patch("airpods.cli.ui.show_environment")
    @patch("airpods.cli.manager")
    def test_doctor_missing_dependency(self, mock_manager, mock_show_env):
        report = EnvironmentReport(
            checks=[CheckResult(name="podman", ok=False, detail="not found")],
            gpu_available=False,
            gpu_detail="n/a",
        )
        mock_manager.report_environment.return_value = report

        result = runner.invoke(app, ["doctor"])

        assert result.exit_code == 1
        assert "missing dependencies" in result.stdout.lower()


class TestStatusCommand:
    """Test enhanced status command behavior."""

    @patch("airpods.cli._render_status")
    @patch("airpods.cli._ensure_podman_available")
    @patch("airpods.cli._resolve_services")
    def test_status_watch_handles_interrupt(
        self, mock_resolve, mock_ensure, mock_render
    ):
        mock_resolve.return_value = [MagicMock()]
        mock_render.side_effect = [None]

        with patch("airpods.cli.time.sleep", side_effect=KeyboardInterrupt):
            result = runner.invoke(app, ["status", "--watch", "0.1"])

        assert result.exit_code == 0
        mock_render.assert_called()

    @patch("airpods.cli._ensure_podman_available")
    @patch("airpods.cli._resolve_services")
    def test_status_invalid_watch_value(self, mock_resolve, mock_ensure):
        mock_resolve.return_value = []

        result = runner.invoke(app, ["status", "--watch", "0"])

        assert result.exit_code != 0
        assert "watch interval must be positive" in result.stdout.lower()


class TestServiceResolution:
    """Test service name resolution."""

    @patch("airpods.cli.manager")
    def test_unknown_service_error(self, mock_manager):
        """Test that unknown service names are rejected."""
        from airpods.services import UnknownServiceError

        mock_manager.ensure_podman.return_value = None
        mock_manager.resolve.side_effect = UnknownServiceError("unknown")

        result = runner.invoke(app, ["start", "unknown"])
        assert result.exit_code != 0


class TestConstants:
    """Test that configuration constants are used."""

    def test_default_constants_defined(self):
        """Test that default constants are defined in module."""
        from airpods.cli import (
            DEFAULT_STOP_TIMEOUT,
            DEFAULT_LOG_LINES,
            DEFAULT_PING_TIMEOUT,
        )

        assert isinstance(DEFAULT_STOP_TIMEOUT, int)
        assert isinstance(DEFAULT_LOG_LINES, int)
        assert isinstance(DEFAULT_PING_TIMEOUT, float)
        assert DEFAULT_STOP_TIMEOUT > 0
        assert DEFAULT_LOG_LINES > 0
        assert DEFAULT_PING_TIMEOUT > 0
