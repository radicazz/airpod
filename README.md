# airpods

[![Tests](https://github.com/radicazz/airpods/actions/workflows/test.yml/badge.svg)](https://github.com/radicazz/airpods/actions/workflows/test.yml)

User-friendly CLI for orchestrating local AI services with Podman.

## Prerequisites

- `uv`: Python environment & dependency manager
- `podman` & `podman-compose`: Container runtime
- *(optional)* `nvidia-smi`: GPU support

## Installation

```bash
# Development setup
git clone https://github.com/radicazz/airpods.git && cd airpods
uv venv && source .venv/bin/activate
uv pip install -e . '.[dev]'

# Global installation
uv tool install --from . airpods
```

## Quick Start

```bash
# Prefetch images & create volumes
airpods start --init

# Start services
airpods start

# Check status
airpods status

# Stop services
airpods stop

# Clean up everything (back up data first!)
airpods backup --dest ~/backups
airpods clean --all
```

## Back up / restore state

```bash
# Capture configs, Open WebUI DB, plugins, and Ollama metadata (no GGUF blobs)
airpods backup --dest ~/backups

# Restore into fresh volumes, keeping current configs backed up automatically
airpods restore ~/backups/airpods-backup-20250712.tar.gz
```

Run `airpods --help` for all available commands and options.

## License

Check out [LICENSE](./LICENSE) for more details.
