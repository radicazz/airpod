# Open WebUI Plugins for AirPods

Auto-installed custom functions for Open WebUI. Automatically synced to the filesystem and imported into the database on `airpods start open-webui`.

## Plugin Categories

### 🔧 Basic Filters
- **system_prompt_enforcer** - Enforce consistent system prompts
- **profanity_filter** - Filter inappropriate language
- **token_counter** - Track and limit token usage
- **code_detector** - Detect programming languages in code blocks

### 🚀 Advanced Workflows
- **vision_joycaption** - Add vision to non-vision models via JoyCaption API
- **twitter_scraper** - Scrape Twitter/X via Nitter (no API required)
- **web_researcher** - Auto web search for current information
- **example_function** - Template for creating custom plugins

## Auto-Installation

Plugins are automatically synced and imported when starting Open WebUI:

```bash
airpods start open-webui
# Output during startup:
# ✓ Synced 8 plugin(s)
# ... (service starts and becomes healthy) ...
# ✓ Auto-imported 8 plugin(s) into Open WebUI
```

The process:
1. **Filesystem sync**: Plugin files are copied from `plugins/open-webui/` to `$AIRPODS_HOME/volumes/webui_plugins/`
2. **Container mount**: The `webui_plugins` directory is mounted to `/app/backend/data/functions` in the container
3. **Database import**: Once Open WebUI is healthy, plugins are automatically imported into the database via the API
4. **Ready to use**: Plugins appear in the Admin Panel → Functions, ready to enable and configure

## Usage

1. Start: `airpods start open-webui`
2. Open http://localhost:3000
3. Go to **Admin Panel → Functions**
4. Plugins are already imported—just enable and configure them
5. Adjust settings (valves) as needed

## Advanced Plugin Examples

### Vision via JoyCaption

Enables image understanding for models like llama3/mistral that lack native vision:

\`\`\`bash
# Deploy JoyCaption (example)
docker run -d --name joycaption -p 5000:5000 --gpus all fancyfeast/joycaption:latest
\`\`\`

Then configure the valve in Open WebUI to point to \`http://joycaption:5000/caption\`.

### Twitter Scraper

Scrapes tweets without Twitter API:

**Trigger examples:**
- "Show me @elonmusk's latest tweets"
- "What's trending on Twitter about AI?"

Uses Nitter (privacy-friendly frontend). Optionally self-host for reliability.

### Web Researcher

Auto-searches when queries need current info:

**Trigger examples:**
- "What is the latest news about GPT-5?"
- "Current Bitcoin price"
- "Recent quantum computing developments"

## Creating Custom Plugins

Template:

\`\`\`python
"""
title: My Plugin
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
        # Modify request before AI
        return body

    def outlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        # Modify response after AI
        return body
\`\`\`

Save in \`plugins/open-webui/\`, restart Open WebUI, enable in Admin Panel.

## Troubleshooting

**Plugins not showing in Functions list:**
- The auto-import happens after the service becomes healthy
- Check the startup output for "Auto-imported X plugin(s)" message
- If import failed, check `airpods logs open-webui` for errors
- Verify files exist in `$AIRPODS_HOME/volumes/webui_plugins/`
- Manual fallback: Use the Open WebUI UI to import from the filesystem

**Auto-import errors:**
- Ensure the WebUI secret is valid (stored in `$AIRPODS_HOME/configs/webui_secret`)
- Check network connectivity: `curl http://localhost:3000/api/config`
- The plugins are still available in the container filesystem at `/app/backend/data/functions/` and can be imported manually through the UI

**Vision/scraping not working:**
- Check external service is running and accessible
- Verify network connectivity in logs
- Update valve URLs to match your setup

**To manually re-import plugins:**
1. Go to Admin Panel → Functions in Open WebUI
2. Click "Import from Filesystem" or use the "+" button
3. Select the plugin files from `/app/backend/data/functions/`

See [Open WebUI Functions docs](https://docs.openwebui.com/features/plugin_system/) for more details.
