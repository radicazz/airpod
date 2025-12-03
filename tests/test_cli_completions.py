from __future__ import annotations

import airpods.cli.completions as cli_completions
from airpods.configuration import ConfigurationError


def _completion_values(items):
    return [getattr(item, "value", item) for item in items]


def test_service_completion_filters_candidates(monkeypatch):
    monkeypatch.setattr(
        cli_completions.manager.registry,
        "names",
        lambda: ["ollama", "open-webui", "comfyui"],
    )

    result = cli_completions.service_name_completion(None, None, "o")

    assert _completion_values(result) == ["ollama", "open-webui"]


def test_config_key_completion_includes_nested_values(monkeypatch):
    class DummyConfig:
        def to_dict(self):
            return {
                "cli": {"stop_timeout": 20},
                "services": {
                    "ollama": {
                        "ports": [
                            {"host": 11434, "container": 11434},
                        ]
                    }
                },
            }

    monkeypatch.setattr(cli_completions, "get_config", lambda: DummyConfig())

    cli_keys = _completion_values(
        cli_completions.config_key_completion(None, None, "cli.")
    )
    service_keys = _completion_values(
        cli_completions.config_key_completion(None, None, "services.oll")
    )

    assert "cli.stop_timeout" in cli_keys
    assert "services.ollama.ports.0.host" in service_keys


def test_config_key_completion_handles_errors(monkeypatch):
    def _boom():
        raise ConfigurationError("broken")

    monkeypatch.setattr(cli_completions, "get_config", _boom)

    assert (
        _completion_values(cli_completions.config_key_completion(None, None, "cli"))
        == []
    )
