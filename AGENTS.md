# Agents & Plan

## Intent
Provide a Rich + Typer-powered CLI (packaged under `airpods/cli/`, installed as the `airpods` command via uv tools) that orchestrates local AI services via Podman. Services are configurable via TOML files with template support. Services: Ollama (GGUF-capable), Open WebUI wired to Ollama, and ComfyUI (using yanwk/comfyui-boot community image; future plan to fork and build custom).

## Runtime Modes
The CLI operates in two distinct modes to avoid conflicts between production and development installations:

### Production Mode (`airpods`)
- **Installation**: Via `uv tool install git+https://github.com/radicazz/airpods.git@main`
- **State directories**: `~/.config/airpods/` or `$XDG_CONFIG_HOME/airpods/`
- **Config priority**: `$AIRPODS_CONFIG` → `$AIRPODS_HOME/configs/config.toml` → XDG paths → defaults (skips repo root)
- **Volumes**: `~/.config/airpods/volumes/{airpods_ollama_data,airpods_webui_data,airpods_comfyui_data}`
- **Podman resources**: `airpods_ollama`, `airpods_webui`, `airpods_comfyui`, `airpods-net`
- **Behavior**: Never touches the git repository; acts as a standard XDG-compliant application

### Development Mode (`airpods`)
- **Installation**: Clone repo + `uv sync --dev` → `uv run airpods` (auto-detects git repository)
- **State directories**: Repository root (e.g., `/path/to/airpods/`)
- **Config priority**: `$AIRPODS_CONFIG` → `$AIRPODS_HOME/configs/config.toml` → `<repo>/configs/config.toml` → defaults
- **Volumes**: `<repo>/volumes/{airpods-dev_ollama_data,airpods-dev_webui_data,airpods-dev_comfyui_data}`
- **Podman resources**: `airpods-dev_ollama`, `airpods-dev_webui`, `airpods-dev_comfyui`, `airpods-dev-net`
- **Behavior**: All state (configs, volumes, secrets) stored in repo; never touches XDG directories

**Mode Detection**: Automatically detects if the airpods package is running from within a git repository (development mode) or from an installed package (production mode). Can be explicitly overridden via `AIRPODS_DEV_MODE` environment variable (`1` for dev, `0` for prod). Implemented in `airpods/runtime_mode.py`.

**Resource Isolation**: Pod names, container names, network names, and volume paths are prefixed based on mode, allowing both installations to run simultaneously without conflicts.

## Command Surface
- Global options: `-v/--version` prints the CLI version; `-h/--help` shows the custom help view plus alias table.
- `start [service...]`: Ensures volumes/images, then launches pods (default both) while explaining when networks, volumes, pods, or containers are reused vs newly created. Waits for each service to report healthy (HTTP ping when available) for up to `cli.startup_timeout` seconds, polling every `cli.startup_check_interval` seconds, with health-less services marked ready once their pod is running. Skips recreation if containers are already running. GPU auto-detected and attached to Ollama; CPU fallback allowed. `--pre-fetch` downloads service images and exits without starting containers for ahead-of-time cache warmups. Exposed aliases: `up`, `run`.
- `stop [service...]`: Graceful stop; optional removal of pods while preserving volumes by default, with an interactive confirmation prompt before destructive removal. Exposed aliases: `down`.
- `status [service...]`: Compact Rich table (Service / Status / Info) summarizing HTTP health plus friendly URLs for running pods, or pod status + port summaries for stopped ones; redundant columns (pod name, uptime, counts) were removed for readability. Exposed aliases: `ps`, `info`.
- `logs [service...]`: Tail logs for specified services or all; supports follow/since/lines.
- `doctor`: Re-run checks without creating resources; surfaces remediation hints without touching pods/volumes.
- `clean`: Remove volumes, images, configs, and user data created by airpods. Offers granular control via flags:
  - `--all/-a`: Remove everything (pods, volumes, images, network, configs)
  - `--pods/-p`: Stop and remove all pods and containers
  - `--volumes/-v`: Remove Podman volumes and bind mount directories
  - `--images/-i`: Remove pulled container images
  - `--network/-n`: Remove the airpods network
  - `--configs/-c`: Remove config files (config.toml, webui_secret)
  - `--force/-f`: Skip confirmation prompts
  - `--dry-run`: Show what would be deleted without deleting
  - `--backup-config`: Backup config.toml before deletion (default: enabled)
- `config`: Manage configuration with subcommands:
  - `init`: Create default config file at `$AIRPODS_HOME/configs/config.toml`
  - `show`: Display current configuration (TOML or JSON format)
  - `path`: Show configuration file location
  - `edit`: Open config in `$EDITOR`
  - `validate`: Check configuration validity
  - `reset`: Reset to defaults with backup
  - `get <key>`: Print specific value using dot notation
  - `set <key> <value>`: Update specific value with validation

## Architecture Notes
- Runtime mode system:
  - `airpods/runtime_mode.py` – Mode detection (`is_dev_mode()`, `get_resource_prefix()`, `get_mode_name()`).
  - `airpods/state.py` – State root selection enforces path separation (repo for dev, XDG for prod).
  - `airpods/configuration/loader.py` – Config discovery skips repo root in production mode.
  - `airpods/config.py` – Service specs apply mode-specific prefixes to pod/container names.
  - `airpods/services.py` – Service manager applies prefix to network name.
- CLI package layout:
  - `airpods/cli/__init__.py` – creates the Typer app, registers commands, exposes legacy compatibility helpers.
  - `airpods/cli/common.py` – shared constants, service manager, and Podman/dependency helpers.
  - `airpods/cli/help.py` – Rich-powered help/alias rendering tables used by the root callback.
  - `airpods/cli/status_view.py` – status table + health probing utilities.
  - `airpods/cli/commands/` – individual command modules (`doctor`, `start`, `stop`, `status`, `logs`, `version`, `config`, `clean`) each registering via `commands.__init__.register`.
  - `airpods/cli/type_defs.py` – shared Typer command mapping type alias.
- Configuration system:
  - `airpods/configuration/` – Pydantic-based config schema, loader, template resolver, and error types.
  - `airpods/configuration/schema.py` – ServiceConfig, RuntimeConfig, CLIConfig, DependenciesConfig models (CLIConfig includes `startup_timeout`/`startup_check_interval` knobs used by `start`).
  - `airpods/configuration/defaults.py` – Built-in default configuration dictionary.
  - `airpods/configuration/loader.py` – Config file discovery, TOML loading, merging, caching.
  - `airpods/configuration/resolver.py` – Template variable resolution (`{{runtime.host_gateway}}`, `{{services.ollama.ports.0.host}}`).
  - Config priority (production): `$AIRPODS_CONFIG` → `$AIRPODS_HOME/configs/config.toml` → `$AIRPODS_HOME/config.toml` (legacy) → `$XDG_CONFIG_HOME/airpods/configs/config.toml` → `$XDG_CONFIG_HOME/airpods/config.toml` (legacy) → `~/.config/airpods/configs/config.toml` → `~/.config/airpods/config.toml` (legacy) → defaults.
  - Config priority (development): `$AIRPODS_CONFIG` → `$AIRPODS_HOME/configs/config.toml` → `$AIRPODS_HOME/config.toml` (legacy) → `<repo_root>/configs/config.toml` → `<repo_root>/config.toml` (legacy) → defaults.
  - Whichever directory provides the active config is treated as `$AIRPODS_HOME`; `configs/`, `volumes/`, and secrets are all created there so runtime assets stay grouped together regardless of which item in the priority list wins.
- Supporting modules: `airpods/podman.py` (subprocess wrapper), `airpods/system.py` (env checks, GPU detection), `airpods/config.py` (service specs from config), `airpods/logging.py` (Rich console themes), `airpods/ui.py` (Rich tables/panels), `airpods/paths.py` (repo root detection), `airpods/state.py` (state directory management), `podcli` (uv/python wrapper script).
- Pod specs dynamically generated from configuration. Service metadata includes `needs_webui_secret` flag for automatic secret injection. Easy to extend services via config files.
- Network aliases are configured at the pod level (not container level) since containers in pods share the pod's network namespace.
- Errors surfaced with clear remediation (install Podman, start podman machine, check GPU drivers).

## Data & Images
- Volumes: `airpods_ollama_data`, `airpods_webui_data`, and `airpods_comfyui_data` are bind-mounted under `$AIRPODS_HOME/volumes/` (e.g., `$AIRPODS_HOME/volumes/airpods_ollama_data`), while the ComfyUI workspace bind (`bind://comfyui/workspace`) lives at `$AIRPODS_HOME/volumes/comfyui/workspace`.
- Images: `docker.io/ollama/ollama:latest`, `ghcr.io/open-webui/open-webui:latest`, `docker.io/yanwk/comfyui-boot:cu128-slim`; pulled during `start` (or via `start --pre-fetch`).
- Secrets: Open WebUI secret persisted at `$AIRPODS_HOME/configs/webui_secret` (or `$XDG_CONFIG_HOME/airpods/configs/webui_secret` or `~/.config/airpods/configs/webui_secret`) during `start` when Open WebUI is enabled, injected via the `needs_webui_secret` flag.
- Networking: Open WebUI targets Ollama via the Podman alias `http://ollama:11434` (configurable via templates).
- Configuration: Optional `config.toml` in `configs/` subdirectory at `$AIRPODS_HOME` or XDG paths; deep-merged with defaults. All airpods configuration files (config.toml, webui_secret, etc.) are stored together in the `configs/` subdirectory.

## Testing Approach
- Unit tests mock subprocess interactions to validate command flow and flags.
- Configuration tests verify schema validation, template resolution, and file merging.
- Test fixtures isolate config artifacts per test via `AIRPODS_HOME` override.
- Integration (later): optional Podman-in-Podman smoke tests; GPU checks skipped when unavailable.

## Development Workflow
- **Local development setup**: Clone repo → `uv sync --dev` → `uv run airpods <command>` (automatically detects git repo, all state stays in repo).
- **Production testing**: Install via `uv tool install git+...` → `airpods <command>` (uses XDG directories).
- **Isolation**: Dev and production modes can coexist; same command name but different paths and Podman resources ensure no conflicts.
- Version bump rules (update `pyproject.toml` before committing):
  - Patch bump (e.g., `0.9.1` → `0.9.2`) for bug fixes and small UX/behavior improvements.
  - Minor bump (e.g., `0.9.1` → `0.10.0`) for large features or meaningful command-surface additions.
  - Major bump only for breaking changes.
- The CI workflow under `.github/workflows/test.yml` now has a `test` job that pins `ubuntu-24.04`, iterates over Python `3.10`‑`3.13`, installs/uses each interpreter via `uv python`, syncs dev/extras, runs `uv run pytest --cov=airpods --cov-report=term-missing --cov-report=xml`, and publishes Codecov only from the 3.13 row.
- The paired `lint` job also targets `ubuntu-24.04`, installs UV, and validates that `python3 -m compileall airpods` can compile every module in the tree.
- Run `uv run pytest` locally when making changes and keep formatting consistency with `uv format`.
- Install `pre-commit` (part of the `dev` extras) and call `pre-commit run --all-files` before finishing your work; the hook runs `uv format`, Prettier checks on YAML/TOML/Markdown, the full pytest suite with coverage, and `python3 -m compileall airpods`, mirroring the CI jobs.
- Before committing, bump the version in `pyproject.toml`: use minor version bumps for large features and patch bumps for everything else (bug fixes, small improvements, etc.).
- Commit messages use lowercase prefixes such as `docs:`, `refactor:`, `feat:`, `fix:`, or `chore:` followed by a concise summary.
