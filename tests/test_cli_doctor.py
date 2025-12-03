from __future__ import annotations

from unittest.mock import patch

from airpods.cli import app
from airpods.services import EnvironmentReport
from airpods.system import CheckResult


@patch("airpods.cli.commands.doctor.ui.show_environment")
@patch("airpods.cli.commands.doctor.manager")
def test_doctor_success(mock_manager, mock_show_env, runner):
    report = EnvironmentReport(checks=[], gpu_available=False, gpu_detail="n/a")
    mock_manager.report_environment.return_value = report

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "doctor complete" in result.stdout.lower()
    mock_show_env.assert_called_once_with(report)


@patch("airpods.cli.commands.doctor.ui.show_environment")
@patch("airpods.cli.commands.doctor.manager")
def test_doctor_missing_dependency(mock_manager, mock_show_env, runner):
    report = EnvironmentReport(
        checks=[CheckResult(name="podman", ok=False, detail="not found")],
        gpu_available=False,
        gpu_detail="n/a",
    )
    mock_manager.report_environment.return_value = report

    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "missing dependencies" in result.stdout.lower()


def test_doctor_help_uses_custom_renderer(runner):
    result = runner.invoke(app, ["doctor", "--help"])

    assert result.exit_code == 0
    assert "Usage" in result.stdout
    assert "  airpods doctor [OPTIONS]" in result.stdout
