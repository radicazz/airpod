# airpods

[![Tests](https://github.com/radicazz/airpods/actions/workflows/test.yml/badge.svg)](https://github.com/radicazz/airpods/actions/workflows/test.yml) [![Coverage](https://codecov.io/gh/radicazz/airpods/graph/badge.svg)](https://codecov.io/gh/radicazz/airpods)

User-friendly CLI for orchestrating local AI services with Podman.

## Prerequisites

- `uv`: Python environment & dependency manager
- `podman` & `podman-compose`: Container runtime
- *(optional)* `nvidia-smi`: GPU support

## Installation

```bash
git clone https://github.com/radicazz/airpods.git && cd airpods

# Local (project folder) installation
uv venv && source .venv/bin/activate
uv pip install -e . '.[dev]'

# Global installation (from a local checkout)
uv tool install --from . airpods
```

### Install with `uv tool` (recommended)

Stable (pin to a release tag):

```bash
uv tool install "git+https://github.com/radicazz/airpods.git@vX.Y.Z"
```

Nightly (track `main`):

```bash
uv tool install "git+https://github.com/radicazz/airpods.git@main"
```

Upgrading:

- Nightly: `uv tool upgrade airpods`
- Stable: install the new tag, e.g. `uv tool install --upgrade "git+https://github.com/radicazz/airpods.git@vX.Y.Z"`

## Quick Start

```bash
# (Optional) prefetch images
airpods start --pre-fetch

# Start services
airpods start

# Check status
airpods status

# Stop services
airpods stop
```

Run `airpods --help` for all available commands and options.

## License

Check out [LICENSE](./LICENSE) for more details.
