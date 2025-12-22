"""ComfyUI AirPods Tools custom nodes."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

from .nodes import (
    LlamaChatCompletion,
    LlamaTextCompletion,
    OllamaChat,
    OllamaGenerate,
    TextCombine,
    TextRepeat,
)

NODE_CLASS_MAPPINGS = {
    "AirPodsLlamaTextCompletion": LlamaTextCompletion,
    "AirPodsLlamaChatCompletion": LlamaChatCompletion,
    "AirPodsOllamaGenerate": OllamaGenerate,
    "AirPodsOllamaChat": OllamaChat,
    "AirPodsTextCombine": TextCombine,
    "AirPodsTextRepeat": TextRepeat,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "AirPodsLlamaTextCompletion": "Llama Text Completion (AirPods)",
    "AirPodsLlamaChatCompletion": "Llama Chat Completion (AirPods)",
    "AirPodsOllamaGenerate": "Ollama Generate (AirPods)",
    "AirPodsOllamaChat": "Ollama Chat (AirPods)",
    "AirPodsTextCombine": "Text Combine (AirPods)",
    "AirPodsTextRepeat": "Text Repeat (AirPods)",
}

_HOOK_STARTED = False


def _env_flag(name: str, default: bool = True) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _read_marker(marker: Path) -> dict[str, str]:
    try:
        content = marker.read_text(encoding="utf-8").strip()
    except OSError:
        return {}
    if not content:
        return {}
    data: dict[str, str] = {}
    for line in content.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key:
            data[key] = value
    return data


def _write_marker(marker: Path, *, mode: str, container_id: str | None = None) -> None:
    lines = [f"mode={mode}"]
    if container_id:
        lines.append(f"container_id={container_id}")
    marker.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _detect_container_id() -> str | None:
    try:
        data = Path("/proc/self/cgroup").read_text(encoding="utf-8", errors="ignore")
    except OSError:
        data = ""
    match = re.search(r"([0-9a-f]{64})", data)
    if match:
        return match.group(1)
    host = os.getenv("HOSTNAME", "")
    if re.fullmatch(r"[0-9a-f]{12,64}", host):
        return host
    return None


def _requirements_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _collect_requirements(root: Path) -> list[Path]:
    requirements: list[Path] = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        if entry.name.startswith("."):
            continue
        req = entry / "requirements.txt"
        if req.is_file():
            requirements.append(req)
    return requirements


def _should_install(req: Path, *, container_id: str | None) -> bool:
    marker = req.parent / ".airpods-requirements.installed"
    if not marker.exists():
        return True
    try:
        if marker.stat().st_mtime < req.stat().st_mtime:
            return True
    except OSError:
        return True
    meta = _read_marker(marker)
    if meta.get("mode") == "user":
        return not (container_id and meta.get("container_id") == container_id)
    return False


def _run_pip(
    args: list[str], *, clear_target: bool = False
) -> subprocess.CompletedProcess:
    """Run pip with restricted environment variables."""
    env = {}
    # Only include necessary environment variables
    for key in ("PATH", "HOME", "PYTHONPATH"):
        if key in os.environ:
            env[key] = os.environ[key]
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    if clear_target:
        # When using --user, ensure no target-related env vars are set
        env["PIP_NO_USER"] = "0"
        env["PIP_CONFIG_FILE"] = "/dev/null"
    return subprocess.run(
        [sys.executable, "-m", "pip", *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _is_permission(detail: str) -> bool:
    lowered = detail.lower()
    return (
        "permission denied" in lowered
        or "errno 13" in lowered
        or "read-only file system" in lowered
    )


def _is_externally_managed(detail: str) -> bool:
    lowered = detail.lower()
    return (
        "externally-managed-environment" in lowered or "externally managed" in lowered
    )


def _install_requirements(req: Path, *, target: Path, container_id: str | None) -> bool:
    _ensure_airpods_package(target)
    target.mkdir(parents=True, exist_ok=True)
    base_args = [
        "install",
        "-r",
        str(req),
        "--target",
        str(target),
        "--upgrade",
        "--no-input",
    ]
    result = _run_pip(base_args)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        if _is_externally_managed(detail):
            result = _run_pip(base_args + ["--break-system-packages"])
            if result.returncode == 0:
                _write_marker(
                    req.parent / ".airpods-requirements.installed", mode="target"
                )
                return True
            detail = (result.stderr or result.stdout or "").strip()

        if _is_permission(detail):
            user_args = [
                "install",
                "-r",
                str(req),
                "--user",
                "--upgrade",
                "--no-input",
            ]
            fallback = _run_pip(user_args, clear_target=True)
            if fallback.returncode != 0:
                fallback_detail = (fallback.stderr or fallback.stdout or "").strip()
                if _is_externally_managed(fallback_detail):
                    fallback = _run_pip(
                        user_args + ["--break-system-packages"], clear_target=True
                    )
                    if fallback.returncode == 0:
                        _write_marker(
                            req.parent / ".airpods-requirements.installed",
                            mode="user",
                            container_id=container_id,
                        )
                        return True
                    fallback_detail = (fallback.stderr or fallback.stdout or "").strip()
                print(
                    f"[airpods] requirements install failed for {req.parent.name}: {fallback_detail}"
                )
                return False

            _write_marker(
                req.parent / ".airpods-requirements.installed",
                mode="user",
                container_id=container_id,
            )
            return True

        print(f"[airpods] requirements install failed for {req.parent.name}: {detail}")
        return False

    _write_marker(req.parent / ".airpods-requirements.installed", mode="target")
    return True


def _ensure_airpods_package(target: Path) -> None:
    package_root = target.parent
    package_root.mkdir(parents=True, exist_ok=True)
    init_file = package_root / "__init__.py"
    if init_file.exists():
        return
    init_file.write_text(
        '"""Internal AirPods helper package."""\n'
        "NODE_CLASS_MAPPINGS = {}\n"
        "NODE_DISPLAY_NAME_MAPPINGS = {}\n",
        encoding="utf-8",
    )


def _requirements_worker() -> None:
    time.sleep(1.5)
    root = _requirements_root()
    if not root.exists():
        return
    container_id = _detect_container_id()
    requirements = _collect_requirements(root)
    if not requirements:
        return
    target = root / ".airpods" / "site-packages"
    installed = 0
    for req in requirements:
        if not _should_install(req, container_id=container_id):
            continue
        if _install_requirements(req, target=target, container_id=container_id):
            installed += 1
    if installed:
        print(f"[airpods] installed custom node requirements: {installed}")


def _start_requirements_hook() -> None:
    if not _env_flag("AIRPODS_COMFYUI_REQUIREMENTS_HOOK", True):
        return
    global _HOOK_STARTED
    if _HOOK_STARTED:
        return
    _HOOK_STARTED = True
    threading.Thread(target=_requirements_worker, daemon=True).start()


try:
    _start_requirements_hook()
except Exception as exc:
    print(f"[airpods] requirements hook skipped: {exc}")
    traceback.print_exc()
