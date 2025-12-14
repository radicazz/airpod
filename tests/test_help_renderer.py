from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import airpods.cli.help as cli_help
import airpods.cli.common as cli_common


def test_command_description_falls_back_to_docstring():
    """Ensure help descriptions derive from docstrings when explicit help is missing."""

    def sample():
        """Docstring first line.

        Additional detail ignored."""

    command = SimpleNamespace(help=None, short_help=None, callback=sample)
    assert cli_help._command_description(command) == "Docstring first line."


def test_check_service_availability_any_with_running_services():
    """Test that 'any' returns available when services are running."""
    mock_rows = {
        "ollama-pod": {"Status": "Running"},
    }
    with patch.object(cli_common.manager, "pod_status_rows", return_value=mock_rows):
        is_available, reason = cli_common.check_service_availability("any")
        assert is_available is True
        assert reason == ""


def test_check_service_availability_any_with_no_running_services():
    """Test that 'any' returns unavailable when no services are running."""
    mock_rows = {
        "ollama-pod": {"Status": "Exited"},
    }
    with patch.object(cli_common.manager, "pod_status_rows", return_value=mock_rows):
        is_available, reason = cli_common.check_service_availability("any")
        assert is_available is False
        assert reason == "no services running"


def test_check_service_availability_any_with_empty_pods():
    """Test that 'any' returns unavailable when no pods exist."""
    with patch.object(cli_common.manager, "pod_status_rows", return_value={}):
        is_available, reason = cli_common.check_service_availability("any")
        assert is_available is False
        assert reason == "no services running"


def test_check_service_availability_any_with_exception():
    """Test that 'any' returns unavailable on exception."""
    with patch.object(
        cli_common.manager, "pod_status_rows", side_effect=Exception("Test error")
    ):
        is_available, reason = cli_common.check_service_availability("any")
        assert is_available is False
        assert reason == "no services running"
