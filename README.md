# airpods

[![Tests](https://github.com/radicazz/airpods/actions/workflows/test.yml/badge.svg)](https://github.com/radicazz/airpods/actions/workflows/test.yml) [![Coverage](https://codecov.io/gh/radicazz/airpods/graph/badge.svg)](https://codecov.io/gh/radicazz/airpods)

Run the best free & open-source AI tools from the command-line with ease. This project currently supports the following services:

- [Ollama](https://github.com/ollama/ollama)
- [Open WebUI](https://github.com/open-webui/open-webui)
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI)

## Get Started

### Prerequisites

- [`uv`](https://docs.astral.sh/uv/getting-started/installation/): Install, upgrade & manage `airpods`
- `podman` + `podman-compose`: Run the service containers

### Installation

Install `airpods` with `uv`:

```bash
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
