# airpods

User-friendly CLI for orchestrating local AI services with ease.

## Features

- One-command setup and start: `uv tool install --from . airpods` then `airpods init` / `airpods start`.
- GPU-aware: detect NVIDIA GPUs and attach to pods when available; gracefully fall back to CPU.
- Opinionated but extensible: defaults for ports/volumes/images, easy to extend with future services like ComfyUI.
- Helpful output: unified Rich/Typer experience with consistent tables, panels, and remediation hints across every command.

## Getting Started

Make sure you have the following:

- Podman (with podman-compose)
- Python (with uv)
- [optional] NVIDIA GPU Drivers

Setup the tool:

```bash
# Install globally (recommended for users)
uv tool install --from . airpods

# Install locally (recommended for development)
uv venv
source .venv/bin/activate
uv pip install -e .
```

Use the CLI:

```bash
# Create & run the services
airpods init
airpods start

# Make sure everything is going well
airpods status

# Stop everything when you're done
airpods stop
```

Feel free to run `airpods --help` to see a full list of available commands.

## Data locations

- Podman named volumes keep service data persistent (`airpods_ollama_data`, `airpods_webui_data`), so you can prune pods without losing models or WebUI history.
- Secrets and other configs live under `~/.config/airpods` (or `$AIRPODS_HOME` / `$XDG_CONFIG_HOME` when set); for example the Open WebUI secret resides at `webui_secret` inside that folder.
- Both volumes and configs are outside your git checkout by default, keeping the repo clean. Remove them via `podman volume rm` or by deleting the config folder to reset your environment.

## License

Check out [LICENSE](./LICENSE) for more details.
