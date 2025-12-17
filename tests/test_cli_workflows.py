from __future__ import annotations

import json

from airpods.cli import app
from airpods.cli.commands import workflows as workflows_module


def test_workflows_command_shows_in_root_help(runner):
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "workflows" in result.stdout


def test_workflows_help_renders_custom_help(runner):
    result = runner.invoke(app, ["workflows", "--help"])
    assert result.exit_code == 0
    assert "Usage" in result.stdout
    assert "airpods workflows" in result.stdout


def test_extract_model_refs_prompt_format():
    wf = {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "foo.safetensors"},
        },
        "2": {
            "class_type": "LoraLoader",
            "inputs": {"lora_name": "bar.safetensors"},
        },
    }
    refs = workflows_module.extract_model_refs(wf)
    assert any(
        r.filename == "foo.safetensors" and r.folder == "checkpoints" for r in refs
    )
    assert any(r.filename == "bar.safetensors" and r.folder == "loras" for r in refs)


def test_extract_model_refs_workflow_format_best_effort():
    wf = {
        "nodes": [
            {"type": "CheckpointLoaderSimple", "widgets_values": ["foo.safetensors"]}
        ]
    }
    refs = workflows_module.extract_model_refs(wf)
    assert any(r.filename == "foo.safetensors" for r in refs)


def test_workflows_sync_dry_run_requires_mapping_for_missing_models(runner, tmp_path):
    # Create a simple prompt-format workflow in the workspace.
    workspace = workflows_module.comfyui_workspace_dir()
    workspace.mkdir(parents=True, exist_ok=True)
    wf_path = workspace / "wf.json"
    wf_path.write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": "missing.safetensors"},
                }
            }
        ),
        encoding="utf-8",
    )

    # Dry-run without mapping should not hard-fail; it should report the missing
    # models and explain that URL metadata is required to download.
    result = runner.invoke(app, ["workflows", "sync", str(wf_path), "--dry-run"])
    assert result.exit_code == 0
    assert "lack URL metadata" in result.stdout


def test_workflows_sync_dry_run_with_mapping_succeeds(runner, tmp_path):
    workspace = workflows_module.comfyui_workspace_dir()
    workspace.mkdir(parents=True, exist_ok=True)
    wf_path = workspace / "wf2.json"
    wf_path.write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "CheckpointLoaderSimple",
                    "inputs": {"ckpt_name": "missing2.safetensors"},
                }
            }
        ),
        encoding="utf-8",
    )

    mapping_path = tmp_path / "map.json"
    mapping_path.write_text(
        json.dumps(
            {
                "models": {
                    "missing2.safetensors": {
                        "url": "https://huggingface.co/org/repo/resolve/main/missing2.safetensors",
                        "folder": "checkpoints",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["workflows", "sync", str(wf_path), "--map", str(mapping_path), "--dry-run"],
    )
    assert result.exit_code == 0
    assert "Missing models: 1" in result.stdout


def test_workflows_sync_dry_run_uses_workflow_embedded_model_metadata(runner, tmp_path):
    workspace = workflows_module.comfyui_workspace_dir()
    workspace.mkdir(parents=True, exist_ok=True)
    wf_path = workspace / "wf3.json"
    wf_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "CheckpointLoaderSimple",
                        "inputs": [
                            {"name": "ckpt_name", "widget": {"name": "ckpt_name"}}
                        ],
                        "widgets_values": ["missing3.safetensors"],
                        "properties": {
                            "models": [
                                {
                                    "name": "missing3.safetensors",
                                    "url": "https://example.com/missing3.safetensors",
                                    "directory": "checkpoints",
                                }
                            ]
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["workflows", "sync", str(wf_path), "--dry-run"])
    assert result.exit_code == 0
    assert "Missing models: 1" in result.stdout
    assert "models/checkpoints" in result.stdout
    assert "have no URL mapping" not in result.stdout


def test_workflows_sync_download_failure_is_reported_cleanly(
    runner, tmp_path, monkeypatch
):
    workspace = workflows_module.comfyui_workspace_dir()
    workspace.mkdir(parents=True, exist_ok=True)
    wf_path = workspace / "wf4.json"
    wf_path.write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": 1,
                        "type": "CheckpointLoaderSimple",
                        "properties": {
                            "models": [
                                {
                                    "name": "missing4.safetensors",
                                    "url": "https://example.com/missing4.safetensors",
                                    "directory": "checkpoints",
                                }
                            ]
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    def fake_urlopen(*_args, **_kwargs):
        raise TimeoutError("timed out")

    monkeypatch.setattr(workflows_module, "urlopen", fake_urlopen)

    result = runner.invoke(
        app,
        [
            "workflows",
            "sync",
            str(wf_path),
            "--yes",
            "--timeout",
            "1",
            "--retries",
            "0",
        ],
    )
    assert result.exit_code == 1
    assert "download(s) failed" in result.stdout
    assert "Traceback" not in result.stdout
