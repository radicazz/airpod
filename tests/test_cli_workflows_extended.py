"""Extended test coverage for workflows command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from urllib.error import HTTPError, URLError

import pytest
import typer

from airpods.cli import app
from airpods.cli.commands import workflows as workflows_module
from airpods.cli.commands.workflows import (
    DownloadError,
    ModelRef,
    _coerce_filename,
    _dedupe_refs,
    _download_to_path,
    _extract_model_refs_prompt_format,
    _extract_model_refs_workflow_format,
    _flatten_strings,
    _load_mapping,
    _normalize_hf_url,
    comfyui_models_dir,
    comfyui_workflows_dir,
    comfyui_workspace_dir,
    extract_model_refs,
)


# Test helper functions
class TestCoerceFilename:
    def test_valid_safetensors(self):
        assert _coerce_filename("model.safetensors") == "model.safetensors"

    def test_valid_ckpt(self):
        assert _coerce_filename("checkpoint.ckpt") == "checkpoint.ckpt"

    def test_valid_with_path(self):
        assert _coerce_filename("/path/to/model.pt") == "model.pt"

    def test_non_string(self):
        assert _coerce_filename(123) is None
        assert _coerce_filename(None) is None
        assert _coerce_filename([]) is None

    def test_empty_string(self):
        assert _coerce_filename("") is None
        assert _coerce_filename("   ") is None

    def test_dot_paths(self):
        assert _coerce_filename(".") is None
        assert _coerce_filename("..") is None

    def test_no_model_extension(self):
        assert _coerce_filename("notamodel.txt") is None
        assert _coerce_filename("readme.md") is None

    def test_all_model_extensions(self):
        extensions = [".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".onnx", ".gguf"]
        for ext in extensions:
            assert _coerce_filename(f"model{ext}") == f"model{ext}"


class TestFlattenStrings:
    def test_single_string(self):
        assert _flatten_strings("test") == ["test"]

    def test_list_of_strings(self):
        assert _flatten_strings(["a", "b", "c"]) == ["a", "b", "c"]

    def test_nested_dict(self):
        result = _flatten_strings({"key1": "val1", "key2": {"nested": "val2"}})
        assert "val1" in result
        assert "val2" in result

    def test_mixed_types(self):
        result = _flatten_strings(
            {"str": "test", "num": 123, "list": ["a", "b"], "dict": {"nested": "c"}}
        )
        assert "test" in result
        assert "a" in result
        assert "b" in result
        assert "c" in result

    def test_empty_structures(self):
        assert _flatten_strings({}) == []
        assert _flatten_strings([]) == []

    def test_non_string_values(self):
        result = _flatten_strings([1, 2, None, True, False])
        assert result == []


class TestExtractModelRefsPromptFormat:
    def test_basic_extraction(self):
        data = {
            "1": {"inputs": {"ckpt_name": "model.safetensors"}},
            "2": {"inputs": {"lora_name": "lora.safetensors"}},
        }
        refs = _extract_model_refs_prompt_format(data)
        assert len(refs) == 2
        assert any(
            r.filename == "model.safetensors" and r.folder == "checkpoints"
            for r in refs
        )
        assert any(
            r.filename == "lora.safetensors" and r.folder == "loras" for r in refs
        )

    def test_unknown_input_key(self):
        data = {"1": {"inputs": {"unknown_key": "model.safetensors"}}}
        refs = _extract_model_refs_prompt_format(data)
        assert len(refs) == 1
        assert refs[0].folder is None

    def test_non_dict_node(self):
        data = {"1": "not a dict", "2": {"inputs": {"ckpt_name": "model.safetensors"}}}
        refs = _extract_model_refs_prompt_format(data)
        assert len(refs) == 1

    def test_missing_inputs(self):
        data = {"1": {"class_type": "SomeNode"}}
        refs = _extract_model_refs_prompt_format(data)
        assert len(refs) == 0

    def test_non_string_input_value(self):
        data = {"1": {"inputs": {"ckpt_name": 123}}}
        refs = _extract_model_refs_prompt_format(data)
        assert len(refs) == 0

    def test_invalid_filename(self):
        data = {"1": {"inputs": {"ckpt_name": "not_a_model.txt"}}}
        refs = _extract_model_refs_prompt_format(data)
        assert len(refs) == 0

    def test_all_input_key_mappings(self):
        mappings = {
            "vae_name": "vae",
            "clip_name": "clip",
            "control_net_name": "controlnet",
            "unet_name": "unet",
            "upscale_model": "upscale_models",
        }
        for key, expected_folder in mappings.items():
            data = {"1": {"inputs": {key: "model.safetensors"}}}
            refs = _extract_model_refs_prompt_format(data)
            assert len(refs) == 1
            assert refs[0].folder == expected_folder


class TestExtractModelRefsWorkflowFormat:
    def test_with_models_metadata(self):
        data = {
            "nodes": [
                {
                    "id": 1,
                    "properties": {
                        "models": [
                            {
                                "name": "model.safetensors",
                                "directory": "checkpoints",
                                "url": "https://example.com/model.safetensors",
                            }
                        ]
                    },
                }
            ]
        }
        refs = _extract_model_refs_workflow_format(data)
        assert any(
            r.filename == "model.safetensors"
            and r.folder == "checkpoints"
            and r.url == "https://example.com/model.safetensors"
            for r in refs
        )

    def test_with_widgets_values(self):
        data = {
            "nodes": [
                {
                    "id": 1,
                    "inputs": [{"name": "ckpt_name", "widget": {"name": "ckpt_name"}}],
                    "widgets_values": ["model.safetensors"],
                }
            ]
        }
        refs = _extract_model_refs_workflow_format(data)
        assert any(
            r.filename == "model.safetensors" and r.folder == "checkpoints"
            for r in refs
        )

    def test_non_list_nodes(self):
        data = {"nodes": "not a list"}
        refs = _extract_model_refs_workflow_format(data)
        assert len(refs) == 0

    def test_non_dict_model_metadata(self):
        data = {
            "nodes": [
                {
                    "id": 1,
                    "properties": {"models": ["not", "dict", "values"]},
                }
            ]
        }
        refs = _extract_model_refs_workflow_format(data)
        # Should still extract from flattened strings
        assert isinstance(refs, list)

    def test_empty_model_name(self):
        data = {
            "nodes": [
                {
                    "id": 1,
                    "properties": {
                        "models": [{"name": "", "directory": "checkpoints"}]
                    },
                }
            ]
        }
        refs = _extract_model_refs_workflow_format(data)
        # Empty names should be filtered out
        assert not any(r.filename == "" for r in refs)

    def test_missing_widget(self):
        data = {
            "nodes": [
                {
                    "id": 1,
                    "inputs": [{"name": "ckpt_name"}],  # No widget key
                    "widgets_values": ["model.safetensors"],
                }
            ]
        }
        refs = _extract_model_refs_workflow_format(data)
        # Should still find via flatten_strings
        assert any(r.filename == "model.safetensors" for r in refs)

    def test_unknown_widget_name(self):
        data = {
            "nodes": [
                {
                    "id": 1,
                    "inputs": [{"name": "unknown_param", "widget": {"name": "test"}}],
                    "widgets_values": ["model.safetensors"],
                }
            ]
        }
        refs = _extract_model_refs_workflow_format(data)
        # Should find via flatten_strings but without folder
        assert any(r.filename == "model.safetensors" for r in refs)


class TestExtractModelRefs:
    def test_detects_prompt_format(self):
        wf = {"1": {"inputs": {"ckpt_name": "model.safetensors"}}}
        refs = extract_model_refs(wf)
        assert any(r.folder == "checkpoints" for r in refs)

    def test_detects_workflow_format(self):
        wf = {"nodes": [{"id": 1, "widgets_values": ["model.safetensors"]}]}
        refs = extract_model_refs(wf)
        assert len(refs) >= 1

    def test_empty_workflow(self):
        refs = extract_model_refs({})
        assert len(refs) == 0


class TestDedupeRefs:
    def test_removes_duplicates(self):
        refs = [
            ModelRef("model.safetensors", "checkpoints", None, None, "src1"),
            ModelRef("model.safetensors", "checkpoints", None, None, "src2"),
        ]
        result = _dedupe_refs(refs)
        assert len(result) == 1

    def test_prefers_refs_with_folder(self):
        refs = [
            ModelRef("model.safetensors", None, None, None, "src1"),
            ModelRef("model.safetensors", "checkpoints", None, None, "src2"),
        ]
        result = _dedupe_refs(refs)
        assert len(result) == 1
        assert result[0].folder == "checkpoints"

    def test_prefers_refs_with_url(self):
        refs = [
            ModelRef("model.safetensors", "checkpoints", None, None, "src1"),
            ModelRef(
                "model.safetensors", "checkpoints", None, "https://example.com", "src2"
            ),
        ]
        result = _dedupe_refs(refs)
        assert len(result) == 1
        assert result[0].url == "https://example.com"

    def test_different_subdirs_kept_separate(self):
        refs = [
            ModelRef("model.safetensors", "checkpoints", "v1", None, "src1"),
            ModelRef("model.safetensors", "checkpoints", "v2", None, "src2"),
        ]
        result = _dedupe_refs(refs)
        assert len(result) == 2

    def test_same_filename_different_folders_prefers_url(self):
        """When same file appears in different folders, prefer the one with URL."""
        refs = [
            ModelRef(
                "clip_vision_g.safetensors",
                "clip_vision",
                None,
                "https://example.com/model",
                "src1",
            ),
            ModelRef("clip_vision_g.safetensors", "clip", None, None, "src2"),
        ]
        result = _dedupe_refs(refs)
        # Should only keep the one with URL (clip_vision folder)
        assert len(result) == 1
        assert result[0].folder == "clip_vision"
        assert result[0].url == "https://example.com/model"

    def test_same_filename_different_folders_no_url(self):
        """When same file appears in different folders without URLs, keep first one."""
        refs = [
            ModelRef("model.safetensors", "checkpoints", None, None, "src1"),
            ModelRef("model.safetensors", "loras", None, None, "src2"),
        ]
        result = _dedupe_refs(refs)
        # Should only keep one (the first based on scoring)
        assert len(result) == 1
        assert result[0].folder in ("checkpoints", "loras")

    def test_same_filename_different_folders_both_have_url(self):
        """When same file appears in different folders with URLs, prefer first one with URL."""
        refs = [
            ModelRef(
                "model.safetensors",
                "checkpoints",
                None,
                "https://example.com/1",
                "src1",
            ),
            ModelRef(
                "model.safetensors", "loras", None, "https://example.com/2", "src2"
            ),
        ]
        result = _dedupe_refs(refs)
        # Should keep first one with URL
        assert len(result) == 1
        assert result[0].folder == "checkpoints"
        assert result[0].url == "https://example.com/1"


class TestLoadMapping:
    def test_load_json_mapping(self, tmp_path):
        mapping_file = tmp_path / "map.json"
        mapping_file.write_text(
            json.dumps(
                {
                    "models": {
                        "model.safetensors": "https://example.com/model.safetensors",
                        "lora.safetensors": {
                            "url": "https://example.com/lora.safetensors",
                            "folder": "loras",
                        },
                    }
                }
            )
        )
        result = _load_mapping(mapping_file)
        assert "model.safetensors" in result
        assert (
            result["model.safetensors"]["url"]
            == "https://example.com/model.safetensors"
        )
        assert "lora.safetensors" in result
        assert result["lora.safetensors"]["folder"] == "loras"

    def test_load_toml_mapping(self, tmp_path):
        mapping_file = tmp_path / "map.toml"
        mapping_file.write_text(
            """
[models]
"model.safetensors" = "https://example.com/model.safetensors"

[models."lora.safetensors"]
url = "https://example.com/lora.safetensors"
folder = "loras"
"""
        )
        result = _load_mapping(mapping_file)
        assert "model.safetensors" in result
        assert "lora.safetensors" in result

    def test_missing_file(self, tmp_path):
        with pytest.raises(typer.BadParameter, match="not found"):
            _load_mapping(tmp_path / "nonexistent.json")

    def test_invalid_structure(self, tmp_path):
        mapping_file = tmp_path / "invalid.json"
        mapping_file.write_text(json.dumps({"not_models": {}}))
        result = _load_mapping(mapping_file)
        assert result == {}

    def test_filters_entries_without_url(self, tmp_path):
        mapping_file = tmp_path / "map.json"
        mapping_file.write_text(
            json.dumps(
                {
                    "models": {
                        "no_url.safetensors": {"folder": "checkpoints"},
                        "with_url.safetensors": {
                            "url": "https://example.com/model.safetensors"
                        },
                    }
                }
            )
        )
        result = _load_mapping(mapping_file)
        assert "no_url.safetensors" not in result
        assert "with_url.safetensors" in result


class TestNormalizeHfUrl:
    def test_converts_blob_to_resolve(self):
        url = "https://huggingface.co/user/repo/blob/main/model.safetensors"
        result = _normalize_hf_url(url)
        assert "resolve" in result
        assert "blob" not in result

    def test_leaves_resolve_unchanged(self):
        url = "https://huggingface.co/user/repo/resolve/main/model.safetensors"
        result = _normalize_hf_url(url)
        assert result == url

    def test_non_hf_url_unchanged(self):
        url = "https://example.com/model.safetensors"
        result = _normalize_hf_url(url)
        assert result == url


class TestDownloadToPath:
    def test_skips_existing_file(self, tmp_path):
        dest = tmp_path / "existing.bin"
        dest.write_text("content")
        _download_to_path("https://example.com", dest, overwrite=False)
        assert dest.read_text() == "content"

    def test_invalid_timeout(self, tmp_path):
        with pytest.raises(typer.BadParameter, match="timeout"):
            _download_to_path("https://example.com", tmp_path / "file", timeout_s=0)

    def test_invalid_retries(self, tmp_path):
        with pytest.raises(typer.BadParameter, match="retries"):
            _download_to_path("https://example.com", tmp_path / "file", retries=-1)

    def test_invalid_scheme(self, tmp_path):
        with pytest.raises(typer.BadParameter, match="http"):
            _download_to_path("ftp://example.com", tmp_path / "file")

    def test_http_error_retry(self, tmp_path, monkeypatch):
        call_count = []

        def fake_urlopen(*args, **kwargs):
            call_count.append(1)
            raise HTTPError(None, 404, "Not Found", {}, None)

        monkeypatch.setattr(workflows_module, "urlopen", fake_urlopen)

        with pytest.raises(DownloadError, match="404"):
            _download_to_path(
                "https://example.com/file",
                tmp_path / "file",
                timeout_s=1,
                retries=2,
            )
        assert len(call_count) == 3  # 1 initial + 2 retries

    def test_url_error(self, tmp_path, monkeypatch):
        def fake_urlopen(*args, **kwargs):
            raise URLError("Connection failed")

        monkeypatch.setattr(workflows_module, "urlopen", fake_urlopen)

        with pytest.raises(DownloadError):
            _download_to_path(
                "https://example.com/file",
                tmp_path / "file",
                timeout_s=1,
                retries=0,
            )

    def test_os_error(self, tmp_path, monkeypatch):
        def fake_urlopen(*args, **kwargs):
            raise OSError("Disk error")

        monkeypatch.setattr(workflows_module, "urlopen", fake_urlopen)

        with pytest.raises(DownloadError):
            _download_to_path(
                "https://example.com/file",
                tmp_path / "file",
                timeout_s=1,
                retries=0,
            )


# Test CLI commands
def test_path_cmd(runner):
    result = runner.invoke(app, ["workflows", "path"])
    assert result.exit_code == 0
    assert "Workspace:" in result.stdout
    assert "Workflows:" in result.stdout


def test_path_cmd_help(runner):
    result = runner.invoke(app, ["workflows", "path", "--help"])
    assert result.exit_code == 0
    assert "host paths" in result.stdout


def test_list_cmd_no_workflows(runner, tmp_path, monkeypatch):
    # Point to empty directory
    def fake_workflows_dir():
        return tmp_path / "empty"

    monkeypatch.setattr(workflows_module, "comfyui_workflows_dir", fake_workflows_dir)
    result = runner.invoke(app, ["workflows", "list"])
    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_list_cmd_with_workflows(runner, tmp_path, monkeypatch):
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    (workflows_dir / "test1.json").write_text("{}")
    (workflows_dir / "test2.json").write_text("{}")

    def fake_workflows_dir():
        return workflows_dir

    monkeypatch.setattr(workflows_module, "comfyui_workflows_dir", fake_workflows_dir)
    result = runner.invoke(app, ["workflows", "list"])
    assert result.exit_code == 0
    assert "test1.json" in result.stdout
    assert "test2.json" in result.stdout


def test_list_cmd_with_limit(runner, tmp_path, monkeypatch):
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    for i in range(10):
        (workflows_dir / f"test{i}.json").write_text("{}")

    def fake_workflows_dir():
        return workflows_dir

    monkeypatch.setattr(workflows_module, "comfyui_workflows_dir", fake_workflows_dir)
    result = runner.invoke(app, ["workflows", "list", "--limit", "3"])
    assert result.exit_code == 0
    assert "…and" in result.stdout


def test_remove_cmd_deletes_workflow(runner, tmp_path, monkeypatch):
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()

    wf_path = workflows_dir / "to-delete.json"
    wf_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        workflows_module, "comfyui_workflows_dir", lambda: workflows_dir
    )
    monkeypatch.setattr(
        workflows_module, "comfyui_workspace_dir", lambda: workspace_dir
    )

    result = runner.invoke(app, ["workflows", "remove", "to-delete.json", "--yes"])
    assert result.exit_code == 0
    assert not wf_path.exists()


def test_remove_cmd_dry_run_does_not_delete(runner, tmp_path, monkeypatch):
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()

    wf_path = workflows_dir / "keep.json"
    wf_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        workflows_module, "comfyui_workflows_dir", lambda: workflows_dir
    )
    monkeypatch.setattr(
        workflows_module, "comfyui_workspace_dir", lambda: workspace_dir
    )

    result = runner.invoke(app, ["workflows", "remove", "keep.json", "--dry-run"])
    assert result.exit_code == 0
    assert wf_path.exists()
    assert "Would remove" in result.stdout


def test_remove_cmd_rejects_outside_paths(runner, tmp_path, monkeypatch):
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()

    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        workflows_module, "comfyui_workflows_dir", lambda: workflows_dir
    )
    monkeypatch.setattr(
        workflows_module, "comfyui_workspace_dir", lambda: workspace_dir
    )

    result = runner.invoke(app, ["workflows", "remove", str(outside), "--yes"])
    assert result.exit_code == 2
    assert "outside" in result.stdout.lower()


def test_sync_dry_run_interactive_folder_prompt_builds_mapping_template(
    runner, tmp_path, monkeypatch
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wf_path = workspace / "wf.json"
    wf_path.write_text(
        json.dumps({"1": {"inputs": {"ckpt_name": "missing.safetensors"}}})
    )

    models_root = tmp_path / "models"
    (models_root / "checkpoints").mkdir(parents=True)

    monkeypatch.setattr(workflows_module, "comfyui_workspace_dir", lambda: workspace)
    monkeypatch.setattr(workflows_module, "comfyui_models_dir", lambda: models_root)

    # Prompts:
    # - folder search (default is fine): blank
    # - select folder: 1
    # - subdir: blank
    result = runner.invoke(
        app,
        ["workflows", "sync", str(wf_path), "--dry-run", "--interactive"],
        input="\n1\n\n",
    )
    assert result.exit_code == 0
    assert '"missing.safetensors"' in result.stdout
    assert '"folder": "checkpoints"' in result.stdout


def test_api_cmd(runner):
    result = runner.invoke(app, ["workflows", "api"])
    assert result.exit_code == 0
    assert "localhost" in result.stdout
    assert "/prompt" in result.stdout
    assert "/queue" in result.stdout


def test_pull_cmd_missing_filename(runner):
    result = runner.invoke(
        app,
        ["workflows", "pull", "https://example.com/", "--folder", "checkpoints"],
    )
    assert result.exit_code != 0
    assert "filename" in result.stdout.lower()


def test_pull_cmd_with_explicit_name(runner, tmp_path, monkeypatch):
    models_dir = tmp_path / "models"
    models_dir.mkdir()

    def fake_models_dir():
        return models_dir

    def fake_download(*args, **kwargs):
        # Simulate successful download
        pass

    monkeypatch.setattr(workflows_module, "comfyui_models_dir", fake_models_dir)
    monkeypatch.setattr(workflows_module, "_download_to_path", fake_download)

    result = runner.invoke(
        app,
        [
            "workflows",
            "pull",
            "https://example.com/model",
            "--folder",
            "checkpoints",
            "--name",
            "custom.safetensors",
        ],
    )
    assert result.exit_code == 0
    assert "complete" in result.stdout.lower()


def test_pull_cmd_download_error(runner, tmp_path, monkeypatch):
    models_dir = tmp_path / "models"
    models_dir.mkdir()

    def fake_models_dir():
        return models_dir

    def fake_download(*args, **kwargs):
        raise DownloadError("Network error")

    monkeypatch.setattr(workflows_module, "comfyui_models_dir", fake_models_dir)
    monkeypatch.setattr(workflows_module, "_download_to_path", fake_download)

    result = runner.invoke(
        app,
        [
            "workflows",
            "pull",
            "https://example.com/model.safetensors",
            "--folder",
            "checkpoints",
        ],
    )
    assert result.exit_code == 1
    assert "failed" in result.stdout.lower()


def test_sync_no_models_found(runner, tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    wf_path = workspace / "empty.json"
    wf_path.write_text(json.dumps({}))

    def fake_workspace_dir():
        return workspace

    monkeypatch.setattr(workflows_module, "comfyui_workspace_dir", fake_workspace_dir)

    result = runner.invoke(app, ["workflows", "sync", str(wf_path)])
    assert result.exit_code == 0
    assert "No model-like references" in result.stdout


def test_sync_all_models_present(runner, tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    models = tmp_path / "models"
    (models / "checkpoints").mkdir(parents=True)
    (models / "checkpoints" / "model.safetensors").write_text("fake")

    wf_path = workspace / "test.json"
    wf_path.write_text(
        json.dumps({"1": {"inputs": {"ckpt_name": "model.safetensors"}}})
    )

    def fake_workspace_dir():
        return workspace

    def fake_models_dir():
        return models

    monkeypatch.setattr(workflows_module, "comfyui_workspace_dir", fake_workspace_dir)
    monkeypatch.setattr(workflows_module, "comfyui_models_dir", fake_models_dir)

    result = runner.invoke(app, ["workflows", "sync", str(wf_path)])
    assert result.exit_code == 0
    assert "No missing models" in result.stdout


def test_sync_workflow_not_found(runner):
    result = runner.invoke(app, ["workflows", "sync", "nonexistent.json"])
    assert result.exit_code != 0
    assert "not found" in result.stdout.lower()


def test_comfyui_models_dir_no_service(monkeypatch):
    monkeypatch.setattr(workflows_module.config_module.REGISTRY, "get", lambda x: None)
    with pytest.raises(typer.BadParameter, match="not enabled"):
        comfyui_models_dir()


def test_comfyui_workflows_dir_multiple_paths(tmp_path, monkeypatch):
    # Test fallback logic
    def fake_find_mount(suffix):
        return None

    def fake_workspace_dir():
        return tmp_path

    monkeypatch.setattr(workflows_module, "_find_comfyui_mount", fake_find_mount)
    monkeypatch.setattr(workflows_module, "comfyui_workspace_dir", fake_workspace_dir)

    result = comfyui_workflows_dir()
    assert result == tmp_path
