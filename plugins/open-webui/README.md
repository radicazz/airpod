# Open WebUI Extensions for AirPods

This directory holds the example extension plus notes for building your own Open WebUI plugins (tools, filters, pipelines). Files here are auto-synced into Open WebUI every time you run `airpods start open-webui`.

## Example Prompt Helper (included)

`example_prompt_helper.py` is a tiny filter that shows the core pattern:

- **Inlet** – adds/extends a system prompt before the LLM
- **Outlet** – optionally appends a signature so you know it ran
- **Valves** – user-editable settings surfaced in the WebUI Admin panel

Use it as a starting point for your own plugins.

## Auto-Installation

Every time `airpods start open-webui` runs:

```bash
airpods start open-webui
# ✓ Synced 1 extension(s)
# ... service starts ...
# ✓ Auto-imported 1 extension(s) into Open WebUI
```

Behind the scenes:

1. Files are copied (recursively) from `plugins/open-webui/` into `$AIRPODS_HOME/volumes/webui_plugins/` (stale files there are pruned)
2. That directory is mounted into the container at `/app/backend/data/functions`
3. After Open WebUI becomes healthy, the extension is inserted into the SQLite database
4. The plugin shows up in the Admin Panel ready to enable/configure

### Discovery Rules

- Files live anywhere under `plugins/open-webui/` (e.g., `filters/alpha.py`, `pipelines/rag.py`); the directory tree is mirrored into `$AIRPODS_HOME/volumes/webui_plugins/`.
- `__init__.py` and filenames that start with `_` are ignored so you can stash helpers next to real plugins.
- Only modules that define a `Filter` class (`inlet`/`outlet`), a `Pipeline` (`pipe`) or expose an `action` coroutine are auto-imported into the `function` table. Pure tool modules (only a `Tools` class) are copied but skipped so they can be managed via Open WebUI’s native Tools UI without generating broken function entries.
- The `airpods plugins` helpers (`list_available_plugins`, `list_installed_plugins`, and the importer) all share this detection logic. When plugins are nested, their IDs are derived from the relative path (e.g., `filters/alpha.py` becomes `filters.alpha`) so same‑named files in different folders stay distinct.

## Build Your Own

Drop additional `.py` files into `plugins/open-webui/`; they are synced and importable on next start. Open WebUI supports three extension types:

- **Tools** – expose callable functions to the model for real-time work (HTTP, shell, DB, etc.)
- **Functions / Filters** – mutate request/response payloads (prompt shaping, moderation, formatting)
- **Pipelines** – orchestrate streaming or multi-step flows around message bodies

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

## Key Concepts from Open WebUI Docs

- **Valves**: Define an inner `Valves(BaseModel)` with `Field(..., description=...)`; values surface in the Admin UI and live in `self.valves` for runtime use.
- **Filters**: Implement `inlet` (pre-LLM) and/or `outlet` (post-LLM); always return the (possibly mutated) `body` dict. Auto-wired params include `__user__`, `__metadata__`, `__request__`.
- **Pipelines**: Provide a `pipe` method working on the message body; to stream, emit chunks with `__event_emitter__` (e.g., `send_event("data", chunk)` then `send_event("response", body)`).
- **Tools**: Methods on a `Tools` class (with type hints) become callable tools; use valves for config such as API keys.
- **Reserved args**: Avoid shadowing injected params like `__body__`, `__user__`, `__metadata__`, `__request__`, `__connection__`, `__response__`, `__llm__`, `__task__`, `__event_emitter__`, `__run__`, `__logger__`, `__webhook__`, `__plugin__`.
- **Events**: Plugins can push real-time UI updates via `__event_emitter__` and can prompt users with `__event_call__`; routing metadata is automatically managed.

## How Plugins Land in Open WebUI

- Storage: The Open WebUI backend uses SQLite by default at `/app/backend/data/webui.db` (mounted to `$AIRPODS_HOME/volumes/webui_data/` in the container).
- Tables (different surfaces): Admin “Functions” uses the `function` table (columns: id, user_id, name, type, content, meta, valves, is_active, is_global, created_at, updated_at). Workspace “Tools” uses the `tool` table (id, user_id, name, content, specs, meta, valves, access_control, created_at, updated_at).
- Import flow (AirPods): during `airpods start open-webui`, plugin files are copied to `/app/backend/data/functions`; then rows are inserted into the `function` table so filters/actions appear in Admin automatically. Workspace tools still need to be uploaded via the WebUI (Tools > Import JSON) or inserted into the `tool` table if you script it.
- Auto-import details: the importer uses each filename stem as the stable `id`, title-cases it for `name`, auto-detects `type` (`action` if `def action`, `pipeline` if `class Pipeline`/`def pipe`, `filter` if it spots a `Filter`/`inlet`/`outlet`). Files without any of those hooks (e.g., tool-only modules) are skipped. Imported rows set `is_active=1`, `is_global=0`, owner `system`, and include the file body plus a description showing source + detected type. Upserts keep existing IDs updated without duplicates. (See `airpods/plugins.py`.)
- Valves storage: the `valves` column in both tables holds JSON matching your inner `Valves` model. AirPods leaves it empty on import so code defaults apply; editing a plugin’s settings in the Admin UI writes the chosen values back to `valves`, and Open WebUI hydrates `self.valves` from that JSON on every call.

## Helpful Links

- Plugin system overview: https://docs.openwebui.com/features/plugin/
- Filter functions: https://docs.openwebui.com/features/plugin/functions/filter
- Pipe/pipeline functions: https://docs.openwebui.com/features/plugin/functions/pipe
- Action hook: http://docs.openwebui.com/features/plugin/functions/action
- Tools: https://docs.openwebui.com/features/plugin/tools/
- Tool dev guide: https://docs.openwebui.com/features/plugin/tools/development
- Plugin events: https://docs.openwebui.com/features/plugin/development/events
- Valves: https://docs.openwebui.com/features/plugin/development/valves
- Reserved args: https://docs.openwebui.com/features/plugin/development/reserved-args
- Pipelines feature page: https://docs.openwebui.com/features/pipelines/

## Troubleshooting

- Ensure `$AIRPODS_HOME/volumes/webui_plugins/` contains the plugin files
- Watch `airpods logs open-webui` for sync/import output
- If imports fail, confirm the WebUI secret exists at `$AIRPODS_HOME/configs/webui_secret`
- You can always import from `/app/backend/data/functions/` inside the container via the Admin Panel

## References

- [Open WebUI Plugin System](https://docs.openwebui.com/features/plugin_system/)
