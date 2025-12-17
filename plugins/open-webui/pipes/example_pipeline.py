"""
title: Example Pipeline
author: airpods
author_url: https://github.com/radicazz/airpods
version: 0.1
description: Example pipeline that intercepts and modifies messages
"""

from pydantic import BaseModel, Field
from typing import Optional, AsyncIterator
import time


class Pipeline:
    class Valves(BaseModel):
        prefix: str = Field(
            default="🤖 ", description="Prefix to add to all assistant responses"
        )
        simulate_delay: bool = Field(
            default=False, description="Simulate processing delay for demonstration"
        )

    def __init__(self):
        self.valves = self.Valves()
        self.name = "Example Pipeline"

    async def pipe(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__=None,
        __request__=None,
    ) -> str | AsyncIterator[str]:
        """
        Process the message body and optionally stream responses.

        This pipeline demonstrates:
        - Accessing user information
        - Emitting status events
        - Streaming responses
        - Modifying message content
        """
        print(f"Pipeline processing for user: {__user__.get('email', 'unknown')}")

        # Emit status event
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "Processing request...", "done": False},
                }
            )

        # Simulate processing delay if enabled
        if self.valves.simulate_delay:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "Thinking...", "done": False},
                }
            )
            time.sleep(1)

        # Get the last user message
        messages = body.get("messages", [])
        if messages:
            last_message = messages[-1].get("content", "")

            # Generate a simple response with prefix
            response = f"{self.valves.prefix}You said: {last_message}"

            # Emit completion status
            if __event_emitter__:
                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {"description": "Complete!", "done": True},
                    }
                )

            return response

        return f"{self.valves.prefix}No message received"
