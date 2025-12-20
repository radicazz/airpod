"""Utilities for managing GGUF model files."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse, unquote
from urllib.request import Request, urlopen

from airpods import state


def gguf_models_dir() -> Path:
    return state.resolve_volume_path("airpods_models/gguf")


def ensure_gguf_models_dir() -> Path:
    path = gguf_models_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def infer_filename(url: str) -> Optional[str]:
    parsed = urlparse(url)
    name = unquote(Path(parsed.path).name)
    return name or None


def download_model(url: str, *, name: Optional[str] = None) -> Tuple[Path, int]:
    dest_dir = ensure_gguf_models_dir()
    filename = name or infer_filename(url)
    if not filename:
        raise ValueError("Unable to infer filename from URL; use --name")

    dest = dest_dir / filename
    if dest.exists():
        raise FileExistsError(f"Model already exists: {dest}")

    req = Request(url, headers={"User-Agent": "airpods/gguf"})
    tmp_path = dest.with_suffix(dest.suffix + ".partial")
    bytes_written = 0

    try:
        with urlopen(req) as resp, tmp_path.open("wb") as handle:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                bytes_written += len(chunk)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise

    tmp_path.replace(dest)
    return dest, bytes_written
