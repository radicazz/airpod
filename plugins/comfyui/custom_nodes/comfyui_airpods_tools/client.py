"""
Minimal HTTP JSON client helpers for ComfyUI AirPods tools.
"""

from __future__ import annotations

import http.client
import json
import os
from typing import Any, Iterable
from urllib.parse import urlparse


def env_default(key: str, default: str) -> str:
    value = os.environ.get(key, "").strip()
    return value or default


def env_timeout(key: str, default: float = 120.0) -> float:
    raw = os.environ.get(key, "").strip()
    if not raw:
        return default
    try:
        parsed = float(raw)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def resolve_base_url(base_url: str | None, env_key: str, default: str) -> str:
    if base_url:
        return base_url.strip()
    return env_default(env_key, default)


def parse_json_input(value: str | None, label: str) -> Any | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON") from exc


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def coerce_non_empty(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


def _parse_base_url(base_url: str) -> tuple[str, str, int, str]:
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.hostname:
        raise ValueError("base_url must include http:// or https://")
    scheme = parsed.scheme.lower()
    host = parsed.hostname
    port = parsed.port or (443 if scheme == "https" else 80)
    base_path = parsed.path.rstrip("/")
    return scheme, host, port, base_path


def _build_path(base_path: str, path: str) -> str:
    if not path.startswith("/"):
        path = f"/{path}"
    if base_path:
        return f"{base_path}{path}"
    return path


def request_json(
    base_url: str,
    path: str,
    payload: dict[str, Any],
    timeout: float,
    hint: str,
) -> tuple[dict[str, Any], str]:
    scheme, host, port, base_path = _parse_base_url(base_url)
    target_path = _build_path(base_path, path)
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    conn: http.client.HTTPConnection | http.client.HTTPSConnection | None = None
    try:
        if scheme == "https":
            conn = http.client.HTTPSConnection(host, port, timeout=timeout)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=timeout)
        conn.request("POST", target_path, body=body, headers=headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise RuntimeError(f"Unable to connect to {base_url}. {hint}") from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    if resp.status >= 400:
        excerpt = raw[:200]
        raise RuntimeError(f"Request failed ({resp.status}): {excerpt}. {hint}")

    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError("Response was not valid JSON") from exc

    return data, raw


def ensure_list(value: Any, label: str) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    raise ValueError(f"{label} must be a JSON list")


def ensure_dict(value: Any, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    raise ValueError(f"{label} must be a JSON object")


def parse_stop(value: str | None) -> str | list[str] | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.startswith("["):
        parsed = parse_json_input(raw, "stop")
        if parsed is None:
            return None
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        if isinstance(parsed, str):
            return parsed
        raise ValueError("stop must be a string or JSON list")
    return raw


def build_messages(system: str | None, user: str | None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    if user is not None:
        messages.append({"role": "user", "content": user})
    return messages


def extract_first(items: Iterable[Any]) -> Any | None:
    for item in items:
        return item
    return None
