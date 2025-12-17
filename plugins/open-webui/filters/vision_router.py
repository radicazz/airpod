"""
title: Vision Router (AirPods)
author: radicazz/airpods
version: 0.1.0
description: Routes user-provided images to a configured vision model (e.g. JoyCaption via Ollama) and injects the output into a text-only model request.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field


def _now() -> float:
    return time.time()


def _as_dict(obj: Any) -> dict | None:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj
    # Some Open WebUI injections hand in pydantic-ish objects.
    if hasattr(obj, "dict"):
        try:
            return obj.dict()  # type: ignore[attr-defined]
        except Exception:
            return None
    return None


def _get_user_valves(__user__: Optional[dict]) -> Any:
    if not __user__:
        return None
    # Open WebUI typically injects __user__["valves"] as a hydrated model-like object.
    if "valves" in __user__:
        return __user__["valves"]
    return None


def _get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _extract_last_user_parts(
    messages: List[dict],
) -> Tuple[int | None, str, List[dict]]:
    """Return (index, user_text, image_blocks) for the last user message.

    Supports common OpenAI-style multimodal message structure:
      {"role":"user","content":[{"type":"text","text":"..."},{"type":"image_url","image_url":{"url":"..."}}]}
    """
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            return i, content, []
        if isinstance(content, list):
            texts: List[str] = []
            images: List[dict] = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                ptype = part.get("type")
                if ptype == "text":
                    t = part.get("text")
                    if isinstance(t, str) and t:
                        texts.append(t)
                if ptype == "image_url":
                    image_url = part.get("image_url") or {}
                    if isinstance(image_url, dict) and isinstance(
                        image_url.get("url"), str
                    ):
                        images.append(
                            {
                                "type": "image_url",
                                "image_url": {"url": image_url["url"]},
                            }
                        )
            return i, "\n".join(texts).strip(), images
        return i, "", []
    return None, "", []


def _strip_images_from_message(msg: dict) -> None:
    content = msg.get("content", "")
    if isinstance(content, str):
        return
    if not isinstance(content, list):
        return
    new_parts: List[dict] = []
    text_accum: List[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text" and isinstance(part.get("text"), str):
            text_accum.append(part["text"])
    if text_accum:
        new_parts.append({"type": "text", "text": "\n".join(text_accum).strip()})
        msg["content"] = new_parts
    else:
        # Ensure downstream text models still have a textual user turn.
        msg["content"] = ""


def _format_template(template: str, **kwargs: Any) -> str:
    # A tiny, predictable formatter: replace {name} placeholders only.
    out = template
    for key, value in kwargs.items():
        out = out.replace("{" + key + "}", str(value))
    return out


def _http_post_json(url: str, payload: dict, timeout_seconds: int) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=timeout_seconds) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        return json.loads(body or "{}")


@dataclass
class _CacheEntry:
    value: str
    expires_at: float


class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=0, description="Filter priority.")
        enabled: bool = Field(default=True, description="Enable/disable this filter.")

        # Ollama's OpenAI-compatible endpoint (AirPods default with host networking).
        ollama_openai_base_url: str = Field(
            default="http://localhost:11434/v1",
            description="Base URL for Ollama's OpenAI-compatible API.",
        )
        vision_timeout_seconds: int = Field(
            default=90, description="Timeout (seconds) for the vision model call."
        )

        default_vision_model_id: str = Field(
            default="",
            description="Fallback vision model id if the user has not set one (e.g. joycaption:latest).",
        )

        vision_system_prompt: str = Field(
            default="",
            description="Optional system prompt for the vision model.",
        )
        vision_user_prompt_template: str = Field(
            default="{user_text}",
            description="User prompt template sent to the vision model. Supports {user_text} and {n_images}.",
        )

        injection_mode: Literal["system_message", "prepend_user", "append_user"] = (
            Field(
                default="system_message",
                description="How to inject caption output into the text model request.",
            )
        )
        injection_template: str = Field(
            default="[Image analysis via {vision_model}]\n{caption}",
            description="Template injected into the text-model prompt. Supports {caption}, {vision_model}, {n_images}.",
        )

        strip_images_from_text_request: bool = Field(
            default=True,
            description="Remove image blocks from the request before passing to a text-only model.",
        )
        skip_when_target_is_vision_model: bool = Field(
            default=True,
            description="Skip if the target model equals the selected vision model id.",
        )

        multi_image_strategy: Literal["single_call", "per_image", "first_only"] = Field(
            default="single_call",
            description="How to caption multiple images.",
        )
        max_caption_chars: int = Field(
            default=8000,
            description="Maximum caption length injected into the request.",
        )

        # Optional simple cache (best-effort; uses image URL string as key).
        cache_enabled: bool = Field(default=True, description="Enable caption caching.")
        cache_ttl_seconds: int = Field(
            default=600, description="Cache TTL for repeated image URLs."
        )

        # Heuristic target gating (optional, for users who only want this on certain models).
        target_model_allow_regex: str = Field(
            default=".*",
            description="Only run when body.model matches this regex (default: all).",
        )

    class UserValves(BaseModel):
        enabled: bool = Field(
            default=True, description="Per-user enable/disable for this filter."
        )
        vision_model_id: str = Field(
            default="",
            description="Per-user default vision model id to use (e.g. joycaption:latest).",
        )

    def __init__(self):
        self.valves = self.Valves()
        self._cache: dict[str, _CacheEntry] = {}

    def _select_vision_model(self, __user__: Optional[dict]) -> str:
        user_valves = _get_user_valves(__user__)
        model_id = str(_get_attr(user_valves, "vision_model_id", "") or "").strip()
        if model_id:
            return model_id
        return str(self.valves.default_vision_model_id or "").strip()

    def _user_enabled(self, __user__: Optional[dict]) -> bool:
        user_valves = _get_user_valves(__user__)
        enabled = _get_attr(user_valves, "enabled", True)
        return bool(enabled)

    def _cache_get(self, key: str) -> Optional[str]:
        if not self.valves.cache_enabled:
            return None
        entry = self._cache.get(key)
        if not entry:
            return None
        if entry.expires_at < _now():
            self._cache.pop(key, None)
            return None
        return entry.value

    def _cache_put(self, key: str, value: str) -> None:
        if not self.valves.cache_enabled:
            return
        self._cache[key] = _CacheEntry(
            value=value, expires_at=_now() + float(self.valves.cache_ttl_seconds)
        )

    def _call_vision_model(
        self, vision_model: str, prompt_text: str, image_blocks: List[dict]
    ) -> str:
        base = self.valves.ollama_openai_base_url.rstrip("/")
        url = f"{base}/chat/completions"

        messages: List[dict] = []
        if self.valves.vision_system_prompt:
            messages.append(
                {"role": "system", "content": self.valves.vision_system_prompt}
            )
        content: List[dict] = [{"type": "text", "text": prompt_text}]
        content.extend(image_blocks)
        messages.append({"role": "user", "content": content})

        payload = {
            "model": vision_model,
            "messages": messages,
            "stream": False,
        }

        data = _http_post_json(
            url, payload, timeout_seconds=int(self.valves.vision_timeout_seconds)
        )
        choice0 = (data.get("choices") or [{}])[0]
        msg = choice0.get("message") or {}
        content_out = msg.get("content", "")
        if isinstance(content_out, str):
            return content_out
        # Some backends may return list-of-parts.
        if isinstance(content_out, list):
            parts: List[str] = []
            for part in content_out:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    parts.append(part["text"])
            return "\n".join(parts).strip()
        return str(content_out)

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        if not self.valves.enabled:
            return body
        if not self._user_enabled(__user__):
            return body

        model_id = str(body.get("model") or "").strip()
        try:
            if not re.match(self.valves.target_model_allow_regex, model_id):
                return body
        except re.error:
            # If regex is invalid, fail open.
            pass

        messages = body.get("messages") or []
        if not isinstance(messages, list):
            return body

        idx, user_text, image_blocks = _extract_last_user_parts(messages)
        if idx is None or not image_blocks:
            return body

        vision_model = self._select_vision_model(__user__)
        if not vision_model:
            # No vision model configured; do nothing.
            return body
        if self.valves.skip_when_target_is_vision_model and model_id == vision_model:
            return body

        n_images = len(image_blocks)
        prompt_text = _format_template(
            self.valves.vision_user_prompt_template,
            user_text=user_text,
            n_images=n_images,
        ).strip()

        # Cache key: vision_model + image URLs + prompt text.
        urls = [b.get("image_url", {}).get("url", "") for b in image_blocks]
        cache_key = json.dumps(
            {
                "m": vision_model,
                "u": urls,
                "p": prompt_text,
                "s": self.valves.multi_image_strategy,
            },
            sort_keys=True,
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            caption = cached
        else:
            if self.valves.multi_image_strategy == "first_only":
                caption = self._call_vision_model(
                    vision_model, prompt_text, image_blocks[:1]
                )
            elif self.valves.multi_image_strategy == "per_image":
                outputs: List[str] = []
                for i, block in enumerate(image_blocks):
                    p = f"{prompt_text}\n\n(Image {i + 1} of {n_images})"
                    outputs.append(self._call_vision_model(vision_model, p, [block]))
                caption = "\n\n".join(o.strip() for o in outputs if o.strip()).strip()
            else:
                caption = self._call_vision_model(
                    vision_model, prompt_text, image_blocks
                )

            caption = (caption or "").strip()
            if (
                self.valves.max_caption_chars
                and len(caption) > self.valves.max_caption_chars
            ):
                caption = caption[: self.valves.max_caption_chars].rstrip() + "…"
            self._cache_put(cache_key, caption)

        injection = _format_template(
            self.valves.injection_template,
            caption=caption,
            vision_model=vision_model,
            n_images=n_images,
        ).strip()

        # Mutate the request:
        # - strip image payloads so non-vision target models don't error
        # - inject the caption text using the configured mode
        last_user_msg = messages[idx]
        if self.valves.strip_images_from_text_request:
            _strip_images_from_message(last_user_msg)

        if self.valves.injection_mode == "system_message":
            messages.insert(idx, {"role": "system", "content": injection})
        elif self.valves.injection_mode == "prepend_user":
            if isinstance(last_user_msg.get("content"), str):
                last_user_msg["content"] = (
                    f"{injection}\n\n{last_user_msg.get('content', '')}".strip()
                )
            else:
                # If still structured, force to text content.
                last_user_msg["content"] = f"{injection}\n\n{user_text}".strip()
        else:  # append_user
            if isinstance(last_user_msg.get("content"), str):
                last_user_msg["content"] = (
                    f"{last_user_msg.get('content', '')}\n\n{injection}".strip()
                )
            else:
                last_user_msg["content"] = f"{user_text}\n\n{injection}".strip()

        body["messages"] = messages
        return body
