from __future__ import annotations

from unittest.mock import MagicMock, patch

from airpods.cli import app


@patch("airpods.cli.commands.start.ui.confirm_action")
@patch("airpods.cli.commands.start.manager")
@patch("airpods.cli.commands.start.resolve_services")
@patch("airpods.cli.commands.start.ensure_podman_available")
@patch("airpods.cli.commands.start.detect_gpu")
def test_start_cancelled_when_confirmation_declined(
    mock_detect_gpu,
    mock_ensure,
    mock_resolve,
    mock_manager,
    mock_confirm,
    runner,
):
    spec = MagicMock()
    spec.name = "ollama"
    spec.container = "ollama"
    spec.pod = "ollama"
    spec.image = "docker.io/ollama/ollama:latest"
    spec.volumes = []
    spec.ports = []
    mock_resolve.return_value = [spec]
    mock_detect_gpu.return_value = (False, "cpu")
    mock_ensure.return_value = None
    mock_manager.ensure_network.return_value = False
    mock_manager.ensure_volumes.return_value = []
    mock_manager.pull_images.return_value = None
    mock_manager.container_exists.return_value = True
    mock_confirm.return_value = False

    result = runner.invoke(app, ["start"])

    assert result.exit_code != 0
    assert "cancelled" in result.stdout.lower()
    mock_confirm.assert_called_once()
    mock_manager.start_service.assert_not_called()


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
