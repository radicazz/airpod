from __future__ import annotations

import pytest
from typer.testing import CliRunner

from airpods import state
from airpods.cli.common import refresh_cli_context
from airpods.configuration.loader import locate_config_file


@pytest.fixture(autouse=True)
def isolate_config(tmp_path, monkeypatch):
    """Force configuration artifacts into a temporary directory per test."""

    home = tmp_path / "airpods-home"
    monkeypatch.setenv("AIRPODS_HOME", str(home))
    state.clear_state_root_override()
    locate_config_file.cache_clear()
    refresh_cli_context()
    yield


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
