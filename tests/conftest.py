from __future__ import annotations

import pytest
from typer.testing import CliRunner

from airpods import state
from airpods.configuration import reload_config
from airpods.configuration.loader import locate_config_file


@pytest.fixture(autouse=True)
def isolate_config(tmp_path, monkeypatch):
    """Force configuration artifacts into a temporary directory per test."""

    home = tmp_path / "airpods-home"
    monkeypatch.setenv("AIRPODS_HOME", str(home))
    state.state_root.cache_clear()
    locate_config_file.cache_clear()
    reload_config()
    yield


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
