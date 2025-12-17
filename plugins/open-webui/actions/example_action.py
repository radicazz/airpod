"""
title: Example Action
author: airpods
author_url: https://github.com/radicazz/airpods
version: 0.1
description: Example action button that appears in the chat interface
"""

from pydantic import BaseModel, Field
from typing import Optional
import json


class Action:
    class Valves(BaseModel):
        button_label: str = Field(
            default="Summarize", description="Label for the action button"
        )
        enabled: bool = Field(default=True, description="Enable/disable this action")

    def __init__(self):
        self.valves = self.Valves()

    async def action(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__=None,
        __event_call__=None,
        __model__=None,
    ) -> str:
        """
        Action that appears as a button in the UI.

        This example demonstrates:
        - Creating a UI button action
        - Accessing conversation history
        - Using event emitters for status updates
        - Generating summaries or performing operations
        """
        if not self.valves.enabled:
            return "Action is disabled"

        # Emit status
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": f"Executing {self.valves.button_label}...",
                        "done": False,
                    },
                }
            )

        # Get conversation messages
        messages = body.get("messages", [])

        if not messages:
            return "No messages to summarize"

        # Count messages by role
        user_msgs = sum(1 for m in messages if m.get("role") == "user")
        assistant_msgs = sum(1 for m in messages if m.get("role") == "assistant")

        # Create a simple summary
        summary = f"""
📊 **Conversation Summary**

- Total messages: {len(messages)}
- User messages: {user_msgs}
- Assistant messages: {assistant_msgs}

Latest exchange:
"""

        # Add last few messages
        for msg in messages[-3:]:
            role = msg.get("role", "unknown").capitalize()
            content = msg.get("content", "")[:100]  # Truncate long messages
            summary += f"\n**{role}**: {content}..."

        # Emit completion
        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "status",
                    "data": {"description": "Summary complete", "done": True},
                }
            )

        return summary
