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

Simply use `uv run airpods` - it will automatically detect that you're in a git repository:

```bash
# Automatically uses development mode
uv run airpods start

# Force production mode (even in repo)
AIRPODS_DEV_MODE=0 uv run airpods start

# Force development mode (explicit)
AIRPODS_DEV_MODE=1 uv run airpods start
```

### Behavior

- **Command**: `airpods` (same as production)
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

- **Same command name**: `airpods` (mode auto-detected)
- **Different paths**: XDG directories vs repository
- **Different Podman resources**: `airpods_*` vs `airpods-dev_*`
- **Can run simultaneously**: Both installations can run at the same time (though they'll compete for GPU)

## Example Workflow

```bash
# Use production for daily work (installed via uv tool)
airpods start ollama
airpods status

# Meanwhile, develop and test changes (in git repo)
cd ~/Code/airpods
uv run airpods start ollama  # Automatically uses dev mode, different container
uv run airpods status
# ...make changes, test...
uv run airpods stop

# Production instance is unaffected
airpods status  # Still running
```

## Mode Detection

The runtime mode is automatically detected via:

1. **Environment variable override**:
   - `AIRPODS_DEV_MODE=1` → forces development mode
   - `AIRPODS_DEV_MODE=0` → forces production mode
2. **Git repository detection**: If the `airpods` package is located within a git repository → development mode
3. **Default**: Production mode (when installed via `uv tool install`)

### How It Works

- **Production install**: Package installs to `~/.local/share/uv/tools/` or similar (no `.git` directory) → production mode
- **Development clone**: Package source is in cloned repository (`.git` exists) → development mode
- **Manual override**: Set `AIRPODS_DEV_MODE` to explicitly control mode

Implementation: `airpods/runtime_mode.py`
