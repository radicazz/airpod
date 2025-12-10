"""
title: Example Prompt Helper
author: airpods
author_url: https://github.com/radicazz/airpods
version: 0.1.0
description: Minimal example plugin that injects a helpful system prompt and optional response signature.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Filter:
    """Simple example Filter that demonstrates inlet/outlet hooks."""

    class Valves(BaseModel):
        priority: int = Field(
            default=0,
            description="Processing priority (lower runs earlier).",
        )
        instruction: str = Field(
            default="You are a helpful assistant. Keep answers short and clear.",
            description="System message that is ensured before every request.",
        )
        append_signature: bool = Field(
            default=True,
            description="When enabled, add a simple signature to model responses.",
        )

    def __init__(self) -> None:
        self.valves = self.Valves()

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        """Ensure the configured system instruction is present."""
        instruction = self.valves.instruction.strip()
        if not instruction:
            return body

        messages = body.get("messages", [])
        system_msg = next((m for m in messages if m.get("role") == "system"), None)

        if system_msg:
            content = system_msg.get("content", "").strip()
            if instruction not in content:
                separator = "\n\n" if content else ""
                system_msg["content"] = f"{content}{separator}{instruction}".strip()
        else:
            messages.insert(0, {"role": "system", "content": instruction})

        body["messages"] = messages
        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        """Append a lightweight signature so users can see the filter ran."""
        if not self.valves.append_signature:
            return body

        response = body.get("response")
        if isinstance(response, str) and "— Example Plugin" not in response:
            suffix = "\n\n— Example Plugin"
            body["response"] = f"{response}{suffix}"

        return body
