from __future__ import annotations

from unittest.mock import MagicMock, patch

from airpods.cli import app


@patch("airpods.cli.commands.stop.ui.confirm_action")
@patch("airpods.cli.commands.stop.manager")
@patch("airpods.cli.commands.stop.resolve_services")
@patch("airpods.cli.commands.stop.ensure_podman_available")
def test_stop_remove_cancelled_when_confirmation_declined(
    mock_ensure,
    mock_resolve,
    mock_manager,
    mock_confirm,
    runner,
):
    spec = MagicMock()
    spec.name = "webui"
    spec.pod = "webui"
    spec.container = "webui"
    mock_resolve.return_value = [spec]
    mock_confirm.return_value = False

    result = runner.invoke(app, ["stop", "--remove"])

    assert result.exit_code != 0
    assert "cancelled" in result.stdout.lower()
    mock_confirm.assert_called_once()
    mock_manager.stop_service.assert_not_called()
