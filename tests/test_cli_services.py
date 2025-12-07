from __future__ import annotations

from unittest.mock import patch, ANY

import pytest

from airpods.cli import app


@patch("airpods.cli.commands.start.ensure_podman_available")
@patch("airpods.cli.commands.start.manager")
@patch("airpods.cli.common.manager")
def test_unknown_service_error(
    mock_common_manager, mock_start_manager, mock_ensure, runner
):
    """Unknown service names should surface Typer errors."""
    from airpods.services import UnknownServiceError

    mock_ensure.return_value = None
    mock_start_manager.ensure_network.return_value = False
    mock_common_manager.resolve.side_effect = UnknownServiceError("unknown")

    result = runner.invoke(app, ["start", "unknown"])
    assert result.exit_code != 0


@patch("airpods.cli.commands.start.manager")
@patch("airpods.cli.commands.start.get_cli_config")
@patch("airpods.cli.commands.start.ensure_podman_available")
@patch("airpods.cli.commands.start.resolve_services")
def test_start_respects_configured_concurrency(
    mock_resolve, mock_ensure, mock_get_cli_config, mock_manager, runner
):
    mock_resolve.return_value = [
        type("Spec", (), {"name": "ollama", "pod": "pod", "image": "img"})
    ]
    mock_get_cli_config.return_value = type("Config", (), {"max_concurrent_pulls": 5})
    mock_manager.pod_status_rows.return_value = {}
    mock_manager.ensure_network.return_value = False
    mock_manager.ensure_volumes.return_value = []
    mock_manager.pull_images.return_value = None

    result = runner.invoke(app, ["start"])

    assert result.exit_code == 0
    mock_manager.pull_images.assert_any_call(
        mock_resolve.return_value,
        progress_callback=ANY,
        max_concurrent=5,
    )


@patch("airpods.cli.commands.start.manager")
@patch("airpods.cli.commands.start.get_cli_config")
@patch("airpods.cli.commands.start.ensure_podman_available")
@patch("airpods.cli.commands.start.resolve_services")
def test_start_sequential_flag_forces_single_pull(
    mock_resolve, mock_ensure, mock_get_cli_config, mock_manager, runner
):
    mock_resolve.return_value = [
        type("Spec", (), {"name": "ollama", "pod": "pod", "image": "img"})
    ]
    mock_get_cli_config.return_value = type("Config", (), {"max_concurrent_pulls": 5})
    mock_manager.pod_status_rows.return_value = {}
    mock_manager.ensure_network.return_value = False
    mock_manager.ensure_volumes.return_value = []
    mock_manager.pull_images.return_value = None

    result = runner.invoke(app, ["start", "--sequential"])

    assert result.exit_code == 0
    mock_manager.pull_images.assert_any_call(
        mock_resolve.return_value,
        progress_callback=ANY,
        max_concurrent=1,
    )
