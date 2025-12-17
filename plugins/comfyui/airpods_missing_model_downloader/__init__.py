"""
AirPods Missing Model Downloader (ComfyUI)

Adds a small QoL improvement to ComfyUI's "missing models" screen:
alongside the existing "Copy link" / "Download" actions, a third button
can download the referenced model directly onto the ComfyUI server into
the correct models folder.

This is intentionally implemented as a custom-nodes package (even though
it defines no nodes) so it can:
- register backend HTTP routes via PromptServer
- ship a frontend web extension via WEB_DIRECTORY
"""

from __future__ import annotations

import asyncio
import os
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional
from urllib.parse import urlparse

try:
    import aiohttp
    from aiohttp import web
    import folder_paths
    from server import PromptServer

    _COMFY_AVAILABLE = True
except Exception:  # pragma: no cover - only available inside ComfyUI runtime
    _COMFY_AVAILABLE = False


WEB_DIRECTORY = "./web"

# No nodes; keep mappings empty to avoid confusing users.
NODE_CLASS_MAPPINGS: dict[str, Any] = {}
NODE_DISPLAY_NAME_MAPPINGS: dict[str, str] = {}

_MODEL_EXTENSIONS = (
    ".safetensors",
    ".ckpt",
    ".pt",
    ".pth",
    ".bin",
    ".onnx",
    ".gguf",
)

_FOLDER_KEY_ALIASES = {
    # Common "models/<key>" folders used in ComfyUI.
    "checkpoint": "checkpoints",
    "checkpoints": "checkpoints",
    "ckpt": "checkpoints",
    "lora": "loras",
    "loras": "loras",
    "vae": "vae",
    "clip": "clip",
    "clip_vision": "clip_vision",
    "controlnet": "controlnet",
    "unet": "unet",
    "upscale_models": "upscale_models",
    "embeddings": "embeddings",
    "hypernetworks": "hypernetworks",
}


def _allowed_download_domains() -> set[str]:
    raw = os.environ.get(
        "AIRPODS_MODEL_DOWNLOAD_ALLOW_DOMAINS",
        "huggingface.co,cdn-lfs.huggingface.co",
    )
    return {d.strip().lower() for d in raw.split(",") if d.strip()}


def _normalize_hf_url(url: str) -> str:
    # Prefer HF "resolve" URLs so we download the actual artifact.
    # Example:
    #   https://huggingface.co/org/repo/blob/main/file.safetensors
    # -> https://huggingface.co/org/repo/resolve/main/file.safetensors
    return re.sub(r"(/)blob(/)", r"\1resolve\2", url)


def _sanitize_filename(filename: str) -> str:
    name = Path(filename).name
    if not name:
        raise ValueError("filename is required")
    if name in {".", ".."}:
        raise ValueError("invalid filename")
    return name


def _sanitize_subdir(subdir: str) -> str:
    if not subdir:
        return ""
    # Normalize separators and strip leading slashes so it stays relative.
    clean = subdir.replace("\\", "/").lstrip("/")
    parts = [p for p in clean.split("/") if p and p not in {".", ".."}]
    return "/".join(parts)


def _coerce_folder_key(folder_key: str) -> str:
    key = (folder_key or "").strip()
    if not key:
        raise ValueError("folder_key is required")
    key = key.replace("\\", "/").strip("/")
    if key.startswith("models/"):
        key = key[len("models/") :]
    # Allow keys like "checkpoints/sdxl" coming from UI parsing.
    key = key.split("/", 1)[0].strip()
    key_lower = key.lower()
    return _FOLDER_KEY_ALIASES.get(key_lower, key_lower)


def _ensure_url_allowed(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("only http(s) urls are allowed")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("url has no hostname")
    if host not in _allowed_download_domains():
        raise ValueError(
            f"domain not allowed: {host} (set AIRPODS_MODEL_DOWNLOAD_ALLOW_DOMAINS to override)"
        )


def _resolve_model_dir(folder_key: str) -> Path:
    # Ask ComfyUI where this class of models should live.
    try:
        candidates = folder_paths.get_folder_paths(folder_key)
    except Exception as exc:  # pragma: no cover - depends on ComfyUI internals
        raise ValueError(f"unknown model folder key: {folder_key}") from exc

    for candidate in candidates:
        path = Path(candidate)
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception:
            continue
        if os.access(str(path), os.W_OK):
            return path

    raise ValueError(f"no writable directory available for folder key: {folder_key}")


def _resolve_dest_path(folder_key: str, subdir: str, filename: str) -> Path:
    base = _resolve_model_dir(folder_key)
    clean_subdir = _sanitize_subdir(subdir)
    name = _sanitize_filename(filename)
    dest = base / clean_subdir / name if clean_subdir else base / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Guard: dest must stay within base.
    resolved_base = base.resolve()
    resolved_dest = dest.resolve()
    if resolved_base not in resolved_dest.parents and resolved_dest != resolved_base:
        raise ValueError("invalid destination path")
    return dest


@dataclass
class DownloadJob:
    job_id: str
    url: str
    folder_key: str
    subdir: str
    filename: str
    dest_path: str
    status: Literal["queued", "downloading", "done", "error"] = "queued"
    bytes_done: int = 0
    bytes_total: Optional[int] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())


_JOBS: dict[str, DownloadJob] = {}
_JOBS_LOCK = asyncio.Lock()


async def _download_file(
    job: DownloadJob, overwrite: bool, hf_token: str | None
) -> None:
    job.status = "downloading"
    url = _normalize_hf_url(job.url)
    headers = {}
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"

    dest = Path(job.dest_path)
    if dest.exists() and not overwrite:
        job.status = "done"
        return

    tmp = dest.with_suffix(dest.suffix + ".part")
    if tmp.exists():
        try:
            tmp.unlink()
        except Exception:
            pass

    timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers, allow_redirects=True) as resp:
            if resp.status >= 400:
                text = await resp.text()
                raise RuntimeError(f"download failed ({resp.status}): {text[:200]}")

            cl = resp.headers.get("Content-Length")
            if cl and cl.isdigit():
                job.bytes_total = int(cl)

            tmp.parent.mkdir(parents=True, exist_ok=True)
            with tmp.open("wb") as f:
                async for chunk in resp.content.iter_chunked(1024 * 256):
                    if not chunk:
                        continue
                    f.write(chunk)
                    job.bytes_done += len(chunk)

    tmp.replace(dest)
    job.status = "done"


async def _run_job(job: DownloadJob, overwrite: bool, hf_token: str | None) -> None:
    try:
        await _download_file(job, overwrite=overwrite, hf_token=hf_token)
    except Exception as exc:
        job.status = "error"
        job.error = str(exc)


async def _handle_download(request: web.Request) -> web.Response:
    payload = await request.json()

    url = str(payload.get("url", "")).strip()
    folder_key = str(payload.get("folder_key", "")).strip()
    subdir = str(payload.get("subdir", "")).strip()
    filename = str(payload.get("filename", "")).strip()
    overwrite = bool(payload.get("overwrite", False))
    hf_token = payload.get("hf_token") or os.environ.get("HF_TOKEN") or None

    if not url:
        return web.json_response({"ok": False, "error": "url is required"}, status=400)
    try:
        _ensure_url_allowed(url)
        coerced_key = _coerce_folder_key(folder_key)
        # If filename is missing, fall back to the URL's basename.
        if not filename:
            filename = Path(urlparse(url).path).name
        # Basic sanity: models should typically have a known extension.
        if filename and not any(
            filename.lower().endswith(ext) for ext in _MODEL_EXTENSIONS
        ):
            # Don't hard-fail; just allow (some assets may be .yaml/.json etc).
            pass
        dest = _resolve_dest_path(coerced_key, subdir, filename)
    except Exception as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=400)

    job_id = uuid.uuid4().hex
    job = DownloadJob(
        job_id=job_id,
        url=url,
        folder_key=coerced_key,
        subdir=_sanitize_subdir(subdir),
        filename=_sanitize_filename(filename),
        dest_path=str(dest),
    )

    async with _JOBS_LOCK:
        _JOBS[job_id] = job

    asyncio.create_task(_run_job(job, overwrite=overwrite, hf_token=hf_token))
    return web.json_response({"ok": True, "job_id": job_id, "dest_path": job.dest_path})


async def _handle_job_status(request: web.Request) -> web.Response:
    job_id = request.match_info.get("job_id", "")
    async with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if not job:
        return web.json_response({"ok": False, "error": "job not found"}, status=404)
    return web.json_response(
        {
            "ok": True,
            "job_id": job.job_id,
            "status": job.status,
            "bytes_done": job.bytes_done,
            "bytes_total": job.bytes_total,
            "error": job.error,
            "dest_path": job.dest_path,
        }
    )


def _register_routes() -> None:
    # Register aiohttp routes onto the ComfyUI PromptServer.
    PromptServer.instance.routes.post("/airpods/models/download")(_handle_download)
    PromptServer.instance.routes.get("/airpods/models/download/{job_id}")(
        _handle_job_status
    )


if _COMFY_AVAILABLE:  # pragma: no cover - only runs inside ComfyUI
    _register_routes()
