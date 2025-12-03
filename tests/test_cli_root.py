from __future__ import annotations

from airpods.cli import app


def test_version_flag(runner):
    """--version flag displays version."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "airpods" in result.stdout


def test_help_flag(runner):
    """--help flag displays rich help."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Commands" in result.stdout


def test_version_command(runner):
    """version command mirrors --version."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "airpods" in result.stdout


def test_start_help_uses_custom_renderer(runner):
    """start --help renders the Rich-powered panel."""
    result = runner.invoke(app, ["start", "--help"])

    assert result.exit_code == 0
    assert "Usage" in result.stdout
    assert "airpods start" in result.stdout
    assert "Start pods for specified services" in result.stdout
