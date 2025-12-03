from __future__ import annotations

from unittest.mock import patch

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
