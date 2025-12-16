# docs/development-mode

## Overview

AirPods supports two runtime modes to allow seamless coexistence of production and development installations:

- **Production mode**: Standard XDG-compliant application behavior
- **Development mode**: Repository-based workflow for contributors

## Production Mode

### Installation

```bash
uv tool install "git+https://github.com/radicazz/airpods.git@main"
```

### Behavior

- **Command**: `airpods`
- **Configuration**: Stored in `~/.config/airpods/` (or `$XDG_CONFIG_HOME/airpods/`)
- **Volumes**: Stored in `~/.config/airpods/volumes/`
- **Podman resources**: Prefixed with `airpods_` (e.g., `airpods_ollama`, `airpods-net`)
- **Repository**: Never touches your cloned repository

### Config Priority

1. `$AIRPODS_CONFIG` (if set)
2. `$AIRPODS_HOME/configs/config.toml` (if `AIRPODS_HOME` is set)
3. `$XDG_CONFIG_HOME/airpods/configs/config.toml`
4. `~/.config/airpods/configs/config.toml`
5. Built-in defaults

## Development Mode

### Setup

```bash
git clone https://github.com/radicazz/airpods.git
cd airpods
uv sync --dev
```

### Running

Use the `dairpods` command or set the environment variable:

```bash
# Option 1: Use dairpods command
uv run dairpods start

# Option 2: Set environment variable
AIRPODS_DEV_MODE=1 uv run airpods start
```

### Behavior

- **Command**: `dairpods`
- **Configuration**: Stored in `<repo>/configs/`
- **Volumes**: Stored in `<repo>/volumes/`
- **Podman resources**: Prefixed with `airpods-dev_` (e.g., `airpods-dev_ollama`, `airpods-dev-net`)
- **XDG directories**: Never touched

### Config Priority

1. `$AIRPODS_CONFIG` (if set)
2. `$AIRPODS_HOME/configs/config.toml` (if `AIRPODS_HOME` is set)
3. `<repo>/configs/config.toml`
4. Built-in defaults

## Isolation

The two modes are completely isolated:

- **Different commands**: `airpods` vs `dairpods`
- **Different paths**: XDG directories vs repository
- **Different Podman resources**: `airpods_*` vs `airpods-dev_*`
- **Can run simultaneously**: Both installations can run at the same time (though they'll compete for GPU)

## Example Workflow

```bash
# Use production for daily work
airpods start ollama
airpods status

# Meanwhile, develop and test changes
cd ~/Code/airpods
uv run dairpods start ollama  # Different container
uv run dairpods status
# ...make changes, test...
uv run dairpods stop

# Production instance is unaffected
airpods status  # Still running
```

## Mode Detection

The runtime mode is detected via:

1. **Script name**: If invoked as `dairpods` → development mode
2. **Environment variable**: If `AIRPODS_DEV_MODE=1` → development mode
3. **Default**: Production mode

Implementation: `airpods/runtime_mode.py`
