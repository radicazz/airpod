from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from airpods import plugins


def test_sync_plugins_copies_and_preserves_user_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source_dir = tmp_path / "plugins" / "open-webui"
    source_dir.mkdir(parents=True)
    (source_dir / "alpha.py").write_text("print('alpha')", encoding="utf-8")
    (source_dir / "beta.py").write_text("print('beta')", encoding="utf-8")

    target_root = tmp_path / "state" / "volumes"
    target_dir = target_root / "webui_plugins"
    target_dir.mkdir(parents=True)
    (target_dir / "alpha.py").write_text("old", encoding="utf-8")
    (target_dir / "legacy.py").write_text("legacy", encoding="utf-8")

    monkeypatch.setattr(plugins, "detect_repo_root", lambda _start=None: tmp_path)
    monkeypatch.setattr(plugins, "volumes_dir", lambda: target_root)

    synced = plugins.sync_plugins(force=True, prune=False)

    assert synced == 2
    assert (target_dir / "alpha.py").read_text(encoding="utf-8") == "print('alpha')"
    assert (target_dir / "beta.py").exists()
    # User files should be preserved
    assert (target_dir / "legacy.py").exists()


def test_import_functions_uses_container(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plugin_dir = tmp_path
    (plugin_dir / "gamma.py").write_text(
        dedent(
            """
            class Filter:
                def inlet(self, body, __user__=None):
                    return body
            """
        ),
        encoding="utf-8",
    )
    (plugin_dir / "tools" / "gamma_tool.py").parent.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "tools" / "gamma_tool.py").write_text(
        "class Tools:\n    pass\n", encoding="utf-8"
    )

    captured: dict[str, list[str]] = {}
    calls: list[list[str]] = []

    class DummyResult:
        returncode = 0
        stdout = "Imported gamma: 1"
        stderr = ""

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        captured["cmd"] = cmd
        calls.append(cmd)
        return DummyResult()

    import subprocess

    monkeypatch.setattr(subprocess, "run", fake_run)

    imported = plugins.import_plugins_to_webui(
        plugin_dir, admin_user_id="owner", container_name="custom-container"
    )

    assert imported == 1
    assert captured["cmd"][2] == "custom-container"
    assert "user_id = excluded.user_id" in captured["cmd"][-1]
    assert len(calls) == 1


def test_list_available_plugins_discovers_nested_filters(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source_dir = tmp_path / "plugins" / "open-webui"
    (source_dir / "filters").mkdir(parents=True)
    (source_dir / "filters" / "alpha.py").write_text(
        "class Filter:\n    pass\n", encoding="utf-8"
    )
    (source_dir / "tools").mkdir(parents=True)
    (source_dir / "tools" / "tool.py").write_text(
        "class Tools:\n    pass\n", encoding="utf-8"
    )

    monkeypatch.setattr(plugins, "detect_repo_root", lambda _start=None: tmp_path)

    assert plugins.list_available_plugins() == ["filters.alpha"]


def test_list_installed_plugins_discovers_nested_filters(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target_root = tmp_path / "state" / "volumes"
    plugin_dir = target_root / "webui_plugins" / "filters"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "omega.py").write_text("class Filter:\n    pass\n", encoding="utf-8")
    tools_dir = target_root / "webui_plugins" / "tools"
    tools_dir.mkdir(parents=True)
    (tools_dir / "tool.py").write_text("class Tools:\n    pass\n", encoding="utf-8")

    monkeypatch.setattr(plugins, "volumes_dir", lambda: target_root)

    assert plugins.list_installed_plugins() == ["filters.omega"]


def test_resolve_plugin_owner_auto_prefers_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    class DummyResult:
        returncode = 0
        stderr = ""

        def __init__(self, stdout: str):
            self.stdout = stdout

    outputs = ["admin-user\n"]

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(cmd)
        return DummyResult(outputs.pop(0) if outputs else "")

    import subprocess

    monkeypatch.setattr(subprocess, "run", fake_run)

    owner = plugins.resolve_plugin_owner_user_id("open-webui-0", mode="auto")
    assert owner == "admin-user"
    assert len(calls) == 1


def test_resolve_plugin_owner_auto_creates_default_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyResult:
        returncode = 0
        stderr = ""

        def __init__(self, stdout: str):
            self.stdout = stdout

    # Outputs: no existing admin, no users exist, create default admin
    outputs = ["", "", "test-admin-id\n"]

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        return DummyResult(outputs.pop(0) if outputs else "")

    import subprocess

    monkeypatch.setattr(subprocess, "run", fake_run)

    owner = plugins.resolve_plugin_owner_user_id("open-webui-0", mode="auto")
    assert owner == "test-admin-id"


def test_resolve_plugin_owner_admin_mode_uses_system_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DummyResult:
        returncode = 0
        stderr = ""

        def __init__(self, stdout: str):
            self.stdout = stdout

    outputs = [""]

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        return DummyResult(outputs.pop(0) if outputs else "")

    import subprocess

    monkeypatch.setattr(subprocess, "run", fake_run)

    owner = plugins.resolve_plugin_owner_user_id("open-webui-0", mode="admin")
    assert owner == "system"


def test_sync_comfyui_plugins_copies_directories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source_dir = tmp_path / "plugins" / "comfyui"
    source_dir.mkdir(parents=True)

    # Create a directory-based custom node (package with __init__.py)
    (source_dir / "custom_node_a").mkdir()
    (source_dir / "custom_node_a" / "__init__.py").write_text(
        "# Custom node A", encoding="utf-8"
    )
    (source_dir / "custom_node_a" / "node.py").write_text(
        "# Node implementation", encoding="utf-8"
    )

    # Create a single-file custom node
    (source_dir / "simple_node.py").write_text("# Simple node", encoding="utf-8")

    target_root = tmp_path / "state" / "volumes"
    target_dir = target_root / "comfyui_custom_nodes"

    monkeypatch.setattr(plugins, "detect_repo_root", lambda _start=None: tmp_path)
    monkeypatch.setattr(plugins, "volumes_dir", lambda: target_root)

    synced = plugins.sync_comfyui_plugins(force=True, prune=False)

    assert synced == 2
    assert (target_dir / "custom_node_a" / "__init__.py").exists()
    assert (target_dir / "custom_node_a" / "node.py").exists()
    assert (target_dir / "simple_node.py").exists()


def test_sync_comfyui_plugins_prunes_removed_items(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source_dir = tmp_path / "plugins" / "comfyui"
    source_dir.mkdir(parents=True)

    # Create one custom node in source
    (source_dir / "custom_node_a").mkdir()
    (source_dir / "custom_node_a" / "__init__.py").write_text(
        "# Custom node A", encoding="utf-8"
    )

    target_root = tmp_path / "state" / "volumes"
    target_dir = target_root / "comfyui_custom_nodes"
    target_dir.mkdir(parents=True)

    # Create legacy items in target that don't exist in source
    (target_dir / "old_node").mkdir()
    (target_dir / "old_node" / "__init__.py").write_text("# Old", encoding="utf-8")
    (target_dir / "legacy.py").write_text("# Legacy", encoding="utf-8")

    monkeypatch.setattr(plugins, "detect_repo_root", lambda _start=None: tmp_path)
    monkeypatch.setattr(plugins, "volumes_dir", lambda: target_root)

    synced = plugins.sync_comfyui_plugins(force=True, prune=True)

    assert synced == 1
    assert (target_dir / "custom_node_a").exists()
    assert not (target_dir / "old_node").exists()
    assert not (target_dir / "legacy.py").exists()


def test_sync_comfyui_plugins_skips_non_package_dirs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source_dir = tmp_path / "plugins" / "comfyui"
    source_dir.mkdir(parents=True)

    # Create a directory without __init__.py (not a package)
    (source_dir / "not_a_package").mkdir()
    (source_dir / "not_a_package" / "readme.txt").write_text("Docs", encoding="utf-8")

    target_root = tmp_path / "state" / "volumes"

    monkeypatch.setattr(plugins, "detect_repo_root", lambda _start=None: tmp_path)
    monkeypatch.setattr(plugins, "volumes_dir", lambda: target_root)

    synced = plugins.sync_comfyui_plugins(force=True, prune=False)

    assert synced == 0
    assert not (target_root / "comfyui_custom_nodes" / "not_a_package").exists()
