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

    # Patch the default config to skip dependency checks
    # since runtime operations are mocked in tests
    from airpods.configuration import defaults

    original_config = defaults.DEFAULT_CONFIG_DICT.copy()
    defaults.DEFAULT_CONFIG_DICT["dependencies"]["skip_checks"] = True

    state.clear_state_root_override()
    locate_config_file.cache_clear()
    refresh_cli_context()
    yield

    # Restore original config after test
    defaults.DEFAULT_CONFIG_DICT.clear()
    defaults.DEFAULT_CONFIG_DICT.update(original_config)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()
