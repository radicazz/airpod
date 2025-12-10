# Open WebUI Example Plugin for AirPods

AirPods ships a single, easy-to-understand extension that demonstrates how Open WebUI filters work. The code lives in `plugins/open-webui/` and is automatically synced/imported whenever you run `airpods start open-webui`.

## Example Prompt Helper

`example_prompt_helper.py` is a minimal filter that keeps conversations aligned without touching any external APIs.

### Behavior

- **Inlet hook** – injects or extends a system prompt to keep conversations concise
- **Outlet hook** – optionally appends a short signature so you can see the filter ran
- **Valves** – tweak the instruction text, processing priority, and whether the signature is enabled

This plugin is intentionally lightweight so you can copy it to build your own filters, tools, or pipelines.

## Auto-Installation

Every time `airpods start open-webui` runs:

```bash
airpods start open-webui
# ✓ Synced 1 extension(s)
# ... service starts ...
# ✓ Auto-imported 1 extension(s) into Open WebUI
```

Behind the scenes:

1. Files are copied from `plugins/open-webui/` into `$AIRPODS_HOME/volumes/webui_plugins/`
2. That directory is mounted into the container at `/app/backend/data/functions`
3. After Open WebUI becomes healthy, the extension is inserted into the SQLite database
4. The plugin shows up in the Admin Panel ready to enable/configure

## Customize or Build New Extensions

Drop additional `.py` files into `plugins/open-webui/` and they will be synced the same way. Open WebUI supports three extension types:

- **Tools** – real-time data access (HTTP APIs, shell commands, etc.)
- **Functions (Filters)** – mutate requests/responses (system prompts, formatting, moderation)
- **Pipelines** – advanced streaming or workflow orchestration

### Tool Template

```python
"""
title: My Custom Tool
author: you
version: 0.1.0
description: Tool description
"""

from pydantic import BaseModel, Field

class Tools:
    class Valves(BaseModel):
        api_key: str = Field(default="", description="API key if needed")

    def __init__(self):
        self.valves = self.Valves()

    def my_function(self, query: str) -> str:
        return f"Result for: {query}"
```

### Function Template

```python
"""
title: My Custom Function
author: you
version: 0.1.0
"""

from pydantic import BaseModel, Field
from typing import Optional

class Filter:
    class Valves(BaseModel):
        priority: int = Field(default=0)

    def __init__(self):
        self.valves = self.Valves()

    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        return body
```

### Pipeline Template

```python
"""
title: My Custom Pipeline
author: you
version: 0.1.0
"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field

class Pipeline:
    class Valves(BaseModel):
        priority: int = Field(default=0)

    def __init__(self):
        self.valves = self.Valves()
        self.name = "My Pipeline"

    def pipe(
        self, user_message: str, model_id: str, messages: List[Dict], body: Dict
    ) -> Dict[str, Any]:
        return body

    async def on_startup(self):
        print("Pipeline loaded")

    async def on_shutdown(self):
        pass
```

Save the file, restart Open WebUI, and import/enable it in the Admin Panel.

## Troubleshooting

- Ensure `$AIRPODS_HOME/volumes/webui_plugins/` contains the plugin files
- Watch `airpods logs open-webui` for sync/import output
- If imports fail, confirm the WebUI secret exists at `$AIRPODS_HOME/configs/webui_secret`
- You can always import from `/app/backend/data/functions/` inside the container via the Admin Panel

## References

- [Open WebUI Plugin System](https://docs.openwebui.com/features/plugin_system/)
