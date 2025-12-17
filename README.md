# airpods

[![Version](https://img.shields.io/github/v/release/radicazz/airpods?color=blue)](https://github.com/radicazz/airpods/releases) [![Tests](https://github.com/radicazz/airpods/actions/workflows/test.yml/badge.svg)](https://github.com/radicazz/airpods/actions/workflows/test.yml) [![Coverage](https://codecov.io/gh/radicazz/airpods/graph/badge.svg)](https://codecov.io/gh/radicazz/airpods)

Effortlessly orchestrate *free & open-source* AI services from the command-line:

- [Ollama](https://github.com/ollama/ollama) - Language & Vision models for text, coding, tolling and more.
- [Open WebUI](https://github.com/open-webui/open-webui)  -  Feature-packed front-end chat with multi-model support.
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) - Mature node-based UI for image generation workflows.

## Get Started

### Prerequisites

- [`uv`](https://docs.astral.sh/uv/getting-started/installation/): Install, upgrade & manage `airpods`
- `podman` + `podman-compose`: Run the service containers

### Installation

Install `airpods` with `uv`:

```bash
# This is the nighly installation.
uv tool install "git+https://github.com/radicazz/airpods.git@main"
```

> [!IMPORTANT]
> Upgrade your installation with `uv tool upgrade airpods` when a new version is available.

### First Steps

Easily setup & run your favourite services:

```bash
airpods start                       # Runs all available services
airpods start ollama open-webui     # Run specific services
```

View important info about your running services:

```bash
airpods status                      # Get the status of every running service
airpods logs ollama                 # View ollama's latest logs
airpods logs open-webui -f          # Follow open-webui's logs in your terminal
```

Stop your services:

```bash
airpods stop                        # Stop all running services
airpods stop comfyui                # Only stop ComfyUI (if running)
```

---

Run `airpods --help` for all available commands and options.

## License

Check out [LICENSE](./LICENSE) for more details.
