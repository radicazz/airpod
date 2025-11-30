# airpod

User-friendly CLI for orchestrating local AI services with ease.

## Features

- One-command setup and start: `uv tool install --from . airpod` then `airpod init` / `airpod start`.
- GPU-aware: detect NVIDIA GPUs and attach to pods when available; gracefully fall back to CPU.
- Opinionated but extensible: defaults for ports/volumes/images, easy to extend with future services like ComfyUI.
- Helpful output: Rich-powered status tables, clear errors, and direct pointers to next steps.

## Getting Started

Make sure you have the following:

- Podman (with podman-compose)
- Python (with uv)
- [optional] NVIDIA GPU Drivers

Setup the tool:

```bash
# Install globally (recommended for users)
uv tool install --from . airpod

# Install locally (recommended for development)
uv venv
source .venv/bin/activate
v pip install -e .
```

Use the CLI:

```bash
# Create & run the services
airpod init
airpod start

# Make sure everything is going well
airpod status

# Stop everything when you're done
airpod stop
```

Feel free to run `airpod --help` to see a full list of available commands.

## Data locations

- Podman bind mounts live under `volumes/` in the project directory by default, keeping large model and WebUI files beside the CLI.
- Secrets and other configs live under `configs/` (for example `configs/webui_secret`).
- Both directories are gitignored; deleting them resets your environment.
- For global installs where the package directory is read-only, set `AIRPOD_HOME=/path/to/state` before running `airpod` to relocate both folders (otherwise the CLI falls back to `~/.config/airpod`).

## License

Check out [LICENSE](./LICENSE) for more details.
