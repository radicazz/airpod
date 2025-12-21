"""
ComfyUI nodes for AirPods (llama.cpp/Ollama + utility text nodes).
"""

from __future__ import annotations

from typing import Any

from . import client

LLAMA_BASE_URL_ENV = "AIRPODS_LLAMACPP_URL"
LLAMA_TIMEOUT_ENV = "AIRPODS_LLAMACPP_TIMEOUT"
LLAMA_DEFAULT_URL = "http://localhost:11435/v1"

OLLAMA_BASE_URL_ENV = "AIRPODS_OLLAMA_URL"
OLLAMA_TIMEOUT_ENV = "AIRPODS_OLLAMA_TIMEOUT"
OLLAMA_DEFAULT_URL = "http://localhost:11434"

LLAMA_HINT = "Check that llama.cpp is running (airpods start llamacpp)."
OLLAMA_HINT = "Check that Ollama is running (airpods start ollama)."


class TextCombine:
    """
    A simple node that combines two text inputs with a separator.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text1": ("STRING", {"multiline": True, "default": "Hello"}),
                "text2": ("STRING", {"multiline": True, "default": "World"}),
                "separator": ("STRING", {"default": " "}),
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "combine"
    CATEGORY = "airpods/text"

    def combine(self, text1, text2, separator):
        """Combine two text strings with a separator."""
        result = f"{text1}{separator}{text2}"
        return (result,)


class TextRepeat:
    """
    A simple node that repeats text a specified number of times.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": "Hello"}),
                "count": ("INT", {"default": 3, "min": 1, "max": 100}),
                "separator": ("STRING", {"default": "\n"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "repeat"
    CATEGORY = "airpods/text"

    def repeat(self, text, count, separator):
        """Repeat text a specified number of times."""
        result = separator.join([text] * count)
        return (result,)


def _llama_base_url(value: str | None) -> str:
    return client.resolve_base_url(value, LLAMA_BASE_URL_ENV, LLAMA_DEFAULT_URL)


def _ollama_base_url(value: str | None) -> str:
    return client.resolve_base_url(value, OLLAMA_BASE_URL_ENV, OLLAMA_DEFAULT_URL)


def _extract_openai_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    first = client.extract_first(choices)
    if isinstance(first, dict):
        text = first.get("text")
        if isinstance(text, str):
            return text
        message = first.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content
    return ""


def _extract_ollama_text(payload: dict[str, Any]) -> str:
    response = payload.get("response")
    if isinstance(response, str):
        return response
    message = payload.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content
    return ""


class LlamaTextCompletion:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "max_tokens": ("INT", {"default": 256, "min": 1, "max": 8192}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0}),
                "top_p": ("FLOAT", {"default": 0.95, "min": 0.0, "max": 1.0}),
            },
            "optional": {
                "stop": ("STRING", {"default": ""}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 2147483647}),
                "model": ("STRING", {"default": ""}),
                "base_url": (
                    "STRING",
                    {
                        "default": client.env_default(
                            LLAMA_BASE_URL_ENV, LLAMA_DEFAULT_URL
                        )
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("text", "raw_json")
    FUNCTION = "complete"
    CATEGORY = "airpods/llama"

    def complete(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        stop: str | None = None,
        seed: int = -1,
        model: str | None = None,
        base_url: str | None = None,
    ):
        payload: dict[str, Any] = {
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stop": client.parse_stop(stop),
            "seed": seed if seed >= 0 else None,
            "model": client.coerce_non_empty(model),
        }
        payload = client.clean_payload(payload)

        base_url = _llama_base_url(base_url)
        timeout = client.env_timeout(LLAMA_TIMEOUT_ENV)
        data, _raw = client.request_json(
            base_url,
            "/completions",
            payload,
            timeout,
            LLAMA_HINT,
        )
        text = _extract_openai_text(data)
        return (text, client.compact_json(data))


class LlamaChatCompletion:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "user": ("STRING", {"multiline": True, "default": ""}),
                "max_tokens": ("INT", {"default": 256, "min": 1, "max": 8192}),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0}),
                "top_p": ("FLOAT", {"default": 0.95, "min": 0.0, "max": 1.0}),
            },
            "optional": {
                "system": ("STRING", {"multiline": True, "default": ""}),
                "messages_json": ("STRING", {"multiline": True, "default": ""}),
                "stop": ("STRING", {"default": ""}),
                "seed": ("INT", {"default": -1, "min": -1, "max": 2147483647}),
                "model": ("STRING", {"default": ""}),
                "base_url": (
                    "STRING",
                    {
                        "default": client.env_default(
                            LLAMA_BASE_URL_ENV, LLAMA_DEFAULT_URL
                        )
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("text", "raw_json")
    FUNCTION = "chat"
    CATEGORY = "airpods/llama"

    def chat(
        self,
        user: str,
        max_tokens: int,
        temperature: float,
        top_p: float,
        system: str | None = None,
        messages_json: str | None = None,
        stop: str | None = None,
        seed: int = -1,
        model: str | None = None,
        base_url: str | None = None,
    ):
        messages = client.build_messages(client.coerce_non_empty(system), user)
        parsed_messages = client.parse_json_input(messages_json, "messages_json")
        if parsed_messages is not None:
            messages = client.ensure_list(parsed_messages, "messages_json")

        payload: dict[str, Any] = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stop": client.parse_stop(stop),
            "seed": seed if seed >= 0 else None,
            "model": client.coerce_non_empty(model),
        }
        payload = client.clean_payload(payload)

        base_url = _llama_base_url(base_url)
        timeout = client.env_timeout(LLAMA_TIMEOUT_ENV)
        data, _raw = client.request_json(
            base_url,
            "/chat/completions",
            payload,
            timeout,
            LLAMA_HINT,
        )
        text = _extract_openai_text(data)
        return (text, client.compact_json(data))


class OllamaGenerate:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("STRING", {"default": "llama3.1:8b"}),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "system": ("STRING", {"multiline": True, "default": ""}),
                "options_json": ("STRING", {"multiline": True, "default": ""}),
                "format": ("STRING", {"default": ""}),
                "stream": ("BOOLEAN", {"default": False}),
                "base_url": (
                    "STRING",
                    {
                        "default": client.env_default(
                            OLLAMA_BASE_URL_ENV, OLLAMA_DEFAULT_URL
                        )
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("text", "raw_json")
    FUNCTION = "generate"
    CATEGORY = "airpods/ollama"

    def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        options_json: str | None = None,
        format: str | None = None,
        stream: bool = False,
        base_url: str | None = None,
    ):
        if stream:
            raise ValueError("streaming is not supported in this node")

        options = client.ensure_dict(
            client.parse_json_input(options_json, "options_json"), "options_json"
        )
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "system": client.coerce_non_empty(system),
            "options": options or None,
            "format": client.coerce_non_empty(format),
            "stream": False,
        }
        payload = client.clean_payload(payload)

        base_url = _ollama_base_url(base_url)
        timeout = client.env_timeout(OLLAMA_TIMEOUT_ENV)
        data, _raw = client.request_json(
            base_url,
            "/api/generate",
            payload,
            timeout,
            OLLAMA_HINT,
        )
        text = _extract_ollama_text(data)
        return (text, client.compact_json(data))


class OllamaChat:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("STRING", {"default": "llama3.1:8b"}),
                "user": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "system": ("STRING", {"multiline": True, "default": ""}),
                "messages_json": ("STRING", {"multiline": True, "default": ""}),
                "options_json": ("STRING", {"multiline": True, "default": ""}),
                "format": ("STRING", {"default": ""}),
                "stream": ("BOOLEAN", {"default": False}),
                "base_url": (
                    "STRING",
                    {
                        "default": client.env_default(
                            OLLAMA_BASE_URL_ENV, OLLAMA_DEFAULT_URL
                        )
                    },
                ),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("text", "raw_json")
    FUNCTION = "chat"
    CATEGORY = "airpods/ollama"

    def chat(
        self,
        model: str,
        user: str,
        system: str | None = None,
        messages_json: str | None = None,
        options_json: str | None = None,
        format: str | None = None,
        stream: bool = False,
        base_url: str | None = None,
    ):
        if stream:
            raise ValueError("streaming is not supported in this node")

        messages = client.build_messages(client.coerce_non_empty(system), user)
        parsed_messages = client.parse_json_input(messages_json, "messages_json")
        if parsed_messages is not None:
            messages = client.ensure_list(parsed_messages, "messages_json")

        options = client.ensure_dict(
            client.parse_json_input(options_json, "options_json"), "options_json"
        )
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "options": options or None,
            "format": client.coerce_non_empty(format),
            "stream": False,
        }
        payload = client.clean_payload(payload)

        base_url = _ollama_base_url(base_url)
        timeout = client.env_timeout(OLLAMA_TIMEOUT_ENV)
        data, _raw = client.request_json(
            base_url,
            "/api/chat",
            payload,
            timeout,
            OLLAMA_HINT,
        )
        text = _extract_ollama_text(data)
        return (text, client.compact_json(data))
