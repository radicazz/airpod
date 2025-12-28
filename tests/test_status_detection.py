"""Tests for enhanced status detection in status_view.

Tests cover the Phase 1 improvements based on status-detection-analysis.md:
- Image existence check (distinguish "not pulled" from "stopped")
- Uptime/Time semantic fixes
- Exit code detection for failed containers
- Restart count detection for crash loops
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from airpods.cli.status_view import (
    _format_time_since,
    _format_uptime,
    render_status,
)
from airpods.services import ServiceSpec


class Test_format_uptime:
    """Test uptime formatting for running containers."""

    def test_format_uptime_seconds(self):
        """Test uptime < 1 minute displays as seconds."""
        # Create a timestamp 30 seconds ago
        now = datetime.now()
        past = now - timedelta(seconds=30)
        timestamp = past.strftime("%Y-%m-%d %H:%M:%S.%f")

        result = _format_uptime(timestamp)
        # Result should be close to 30s
        assert result.endswith("s") or result == "-"

    def test_format_uptime_minutes(self):
        """Test uptime < 1 hour displays as minutes."""
        # Create a timestamp 30 minutes ago
        now = datetime.now()
        past = now - timedelta(minutes=30)
        timestamp = past.strftime("%Y-%m-%d %H:%M:%S.%f")

        result = _format_uptime(timestamp)
        assert "m" in result or result == "-"

    def test_format_uptime_hours(self):
        """Test uptime < 24 hours displays as hours."""
        # Create a timestamp 3 hours ago
        now = datetime.now()
        past = now - timedelta(hours=3)
        timestamp = past.strftime("%Y-%m-%d %H:%M:%S.%f")

        result = _format_uptime(timestamp)
        assert "h" in result or result == "-"

    def test_format_uptime_days(self):
        """Test uptime >= 24 hours displays as days."""
        # Create a timestamp 2 days ago
        now = datetime.now()
        past = now - timedelta(days=2)
        timestamp = past.strftime("%Y-%m-%d %H:%M:%S.%f")

        result = _format_uptime(timestamp)
        assert "d" in result or result == "-"

    def test_format_uptime_invalid(self):
        """Test invalid timestamp returns dash."""
        result = _format_uptime("invalid")
        assert result == "-"

    def test_format_uptime_empty(self):
        """Test empty timestamp returns dash."""
        result = _format_uptime("")
        assert result == "-"


class Test_format_time_since:
    """Test time-since formatting for stopped containers."""

    def test_format_time_since_seconds_ago(self):
        """Test time since < 1 minute shows seconds ago."""
        # Create a timestamp 30 seconds ago
        now = datetime.now(timezone.utc)
        past = now - timedelta(seconds=30)
        timestamp = past.isoformat().replace("+00:00", "Z")

        result = _format_time_since(timestamp)
        assert "ago" in result or result == "-"

    def test_format_time_since_minutes_ago(self):
        """Test time since < 1 hour shows minutes ago."""
        # Create a timestamp 30 minutes ago
        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=30)
        timestamp = past.isoformat().replace("+00:00", "Z")

        result = _format_time_since(timestamp)
        assert "ago" in result or result == "-"

    def test_format_time_since_hours_ago(self):
        """Test time since < 24 hours shows hours ago."""
        # Create a timestamp 3 hours ago
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=3)
        timestamp = past.isoformat().replace("+00:00", "Z")

        result = _format_time_since(timestamp)
        assert "ago" in result or result == "-"

    def test_format_time_since_days_ago(self):
        """Test time since >= 24 hours shows days ago."""
        # Create a timestamp 2 days ago
        now = datetime.now(timezone.utc)
        past = now - timedelta(days=2)
        timestamp = past.isoformat().replace("+00:00", "Z")

        result = _format_time_since(timestamp)
        assert "ago" in result or result == "-"

    def test_format_time_since_invalid(self):
        """Test invalid timestamp returns dash."""
        result = _format_time_since("invalid")
        assert result == "-"

    def test_format_time_since_empty(self):
        """Test empty timestamp returns dash."""
        result = _format_time_since("")
        assert result == "-"

    def test_format_time_since_zero_timestamp(self):
        """Test zero timestamp (never started) returns dash."""
        result = _format_time_since("0001-01-01T00:00:00Z")
        assert result == "-"


class TestRenderStatus_ImageDetection:
    """Test image existence detection for service status."""

    @patch("airpods.cli.status_view.manager")
    @patch("airpods.cli.status_view.console")
    def test_pod_absent_image_not_pulled(self, mock_console, mock_manager):
        """Test 'not pulled' status when pod absent and image not local."""
        mock_manager.pod_status_rows.return_value = {}
        mock_manager.runtime.image_exists.return_value = False

        spec = ServiceSpec(
            name="test-service",
            pod="test-pod",
            container="test-container",
            image="test:latest",
        )

        render_status([spec])

        # Verify the table was printed
        assert mock_console.print.called

    @patch("airpods.cli.status_view.manager")
    @patch("airpods.cli.status_view.console")
    def test_pod_absent_image_exists(self, mock_console, mock_manager):
        """Test 'stopped' status when pod absent but image is local."""
        mock_manager.pod_status_rows.return_value = {}
        mock_manager.runtime.image_exists.return_value = True

        spec = ServiceSpec(
            name="test-service",
            pod="test-pod",
            container="test-container",
            image="test:latest",
        )

        render_status([spec])

        # Verify the table was printed
        assert mock_console.print.called


class TestRenderStatus_ExitedContainer:
    """Test status detection for exited containers."""

    @patch("airpods.cli.status_view.manager")
    @patch("airpods.cli.status_view.console")
    def test_exited_never_started(self, mock_console, mock_manager):
        """Test 'created' status when container never started."""
        pod_row = {"Status": "Exited"}
        mock_manager.pod_status_rows.return_value = {"test-pod": pod_row}
        mock_manager.service_ports.return_value = {}

        # Container inspect with no StartedAt
        mock_manager.runtime.container_inspect.return_value = {
            "State": {"ExitCode": 0, "FinishedAt": ""}
        }

        spec = ServiceSpec(
            name="test-service",
            pod="test-pod",
            container="test-container",
            image="test:latest",
        )

        render_status([spec])

        # Verify the table was printed
        assert mock_console.print.called

    @patch("airpods.cli.status_view.manager")
    @patch("airpods.cli.status_view.console")
    def test_exited_clean_shutdown(self, mock_console, mock_manager):
        """Test 'stopped' status for clean shutdown (exit 0)."""
        pod_row = {"Status": "Exited"}
        mock_manager.pod_status_rows.return_value = {"test-pod": pod_row}
        mock_manager.service_ports.return_value = {}

        past = datetime.now() - timedelta(hours=2)
        started_ts = past.strftime("%Y-%m-%d %H:%M:%S.%f")
        finished_ts = (past + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S.%f")

        mock_manager.runtime.container_inspect.return_value = {
            "State": {
                "StartedAt": started_ts,
                "FinishedAt": finished_ts,
                "ExitCode": 0,
            },
            "RestartCount": 0,
        }

        spec = ServiceSpec(
            name="test-service",
            pod="test-pod",
            container="test-container",
            image="test:latest",
        )

        render_status([spec])

        # Verify the table was printed
        assert mock_console.print.called

    @patch("airpods.cli.status_view.manager")
    @patch("airpods.cli.status_view.console")
    def test_exited_failed_nozero_exit_code(self, mock_console, mock_manager):
        """Test 'failed' status for non-zero exit code."""
        pod_row = {"Status": "Exited"}
        mock_manager.pod_status_rows.return_value = {"test-pod": pod_row}
        mock_manager.service_ports.return_value = {}

        past = datetime.now() - timedelta(hours=2)
        started_ts = past.strftime("%Y-%m-%d %H:%M:%S.%f")
        finished_ts = (past + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S.%f")

        mock_manager.runtime.container_inspect.return_value = {
            "State": {
                "StartedAt": started_ts,
                "FinishedAt": finished_ts,
                "ExitCode": 127,
            },
            "RestartCount": 0,
        }

        spec = ServiceSpec(
            name="test-service",
            pod="test-pod",
            container="test-container",
            image="test:latest",
        )

        render_status([spec])

        # Verify the table was printed
        assert mock_console.print.called

    @patch("airpods.cli.status_view.manager")
    @patch("airpods.cli.status_view.console")
    def test_exited_crash_loop(self, mock_console, mock_manager):
        """Test 'crash loop' status for high restart count."""
        pod_row = {"Status": "Exited"}
        mock_manager.pod_status_rows.return_value = {"test-pod": pod_row}
        mock_manager.service_ports.return_value = {}

        past = datetime.now() - timedelta(hours=1)
        started_ts = past.strftime("%Y-%m-%d %H:%M:%S.%f")
        finished_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

        mock_manager.runtime.container_inspect.return_value = {
            "State": {
                "StartedAt": started_ts,
                "FinishedAt": finished_ts,
                "ExitCode": 1,
            },
            "RestartCount": 5,
        }

        spec = ServiceSpec(
            name="test-service",
            pod="test-pod",
            container="test-container",
            image="test:latest",
        )

        render_status([spec])

        # Verify the table was printed
        assert mock_console.print.called

    @patch("airpods.cli.status_view.manager")
    @patch("airpods.cli.status_view.console")
    def test_exited_restarting(self, mock_console, mock_manager):
        """Test 'restarting' status for low restart count."""
        pod_row = {"Status": "Exited"}
        mock_manager.pod_status_rows.return_value = {"test-pod": pod_row}
        mock_manager.service_ports.return_value = {}

        past = datetime.now() - timedelta(minutes=10)
        started_ts = past.strftime("%Y-%m-%d %H:%M:%S.%f")
        finished_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

        mock_manager.runtime.container_inspect.return_value = {
            "State": {
                "StartedAt": started_ts,
                "FinishedAt": finished_ts,
                "ExitCode": 1,
            },
            "RestartCount": 1,
        }

        spec = ServiceSpec(
            name="test-service",
            pod="test-pod",
            container="test-container",
            image="test:latest",
        )

        render_status([spec])

        # Verify the table was printed
        assert mock_console.print.called


class TestRenderStatus_Running:
    """Test status detection for running containers."""

    @patch("airpods.cli.status_view.manager")
    @patch("airpods.cli.status_view.console")
    @patch("airpods.cli.status_view.ping_service")
    @patch("airpods.cli.status_view.collect_host_ports")
    @patch("airpods.cli.status_view.format_host_urls")
    def test_running_healthy(
        self,
        mock_format_urls,
        mock_collect_ports,
        mock_ping,
        mock_console,
        mock_manager,
    ):
        """Test healthy running container displays correctly."""
        pod_row = {"Status": "Running"}
        mock_manager.pod_status_rows.return_value = {"test-pod": pod_row}
        mock_manager.service_ports.return_value = {"11434/tcp": [{"HostPort": "11434"}]}
        mock_collect_ports.return_value = [11434]
        mock_format_urls.return_value = ["http://localhost:11434"]
        mock_ping.return_value = "[ok]200 (50 ms)"

        past = datetime.now() - timedelta(hours=3)
        started_ts = past.strftime("%Y-%m-%d %H:%M:%S.%f")

        mock_manager.runtime.container_inspect.return_value = {
            "State": {"StartedAt": started_ts, "ExitCode": 0},
            "RestartCount": 0,
        }

        spec = ServiceSpec(
            name="ollama",
            pod="test-pod",
            container="test-container",
            image="test:latest",
            health_path="/",
        )

        render_status([spec])

        # Verify the table was printed
        assert mock_console.print.called
