# TODO

Planned features and improvements for AirPods, organized by priority.

## High Priority

### Container Abstraction (Docker Support)

**Status:** IN PROGRESS
**Details:** `ContainerRuntime` Protocol exists in `airpods/runtime.py`; Docker implementation needed.

- [ ] Implement `DockerRuntime` class + `airpods/docker.py` module
- [ ] Handle Docker-specific differences (networking, volumes, GPU)
- [ ] Test runtime detection and fallback (`runtime.prefer` config)
- [ ] Update `doctor` for both Podman/Docker checks
- [ ] Document runtime selection and migration

### Open WebUI Plugin Improvements

**Status:** FUNCTIONAL
**Reference:** See `plugins/open-webui/` for current examples.

- [ ] Add more plugin examples (Action, Pipeline, advanced Tools)
- [ ] Create scaffolding: `airpods plugins create <name> --type ...`
- [ ] Add lifecycle management: `enable|disable|update <name>`
- [ ] Improve validation and error reporting
- [ ] Support CLI-based valve configuration
- [ ] Add testing framework/helpers
- [ ] Better dev docs and shared utilities

### Authentication & Gateway Service

**Status:** PLANNED
**Reference:** See `docs/plans/service-gateway.md`

- [ ] Extend schema for gateway service config
- [ ] Add `auth_secret` management
- [ ] Implement Caddy service spec with volumes and Caddyfile template
- [ ] Generate Basic Auth configuration
- [ ] Update `start` to launch gateway when `auth_enabled=true`
- [ ] Hide Open WebUI from host when gateway active
- [ ] Add gateway health checks and status reporting
- [ ] Update `status`, `stop`, `logs` for gateway
- [ ] Document auth setup and security
- [ ] Support advanced auth (OIDC, external IdP)

### llama.cpp Service

**Status:** PLANNED
**Reference:** See `docs/plans/service-llama.md`

- [ ] Extend schema for `command_args` mapping (CLI-configured services)
- [ ] Implement template resolution and CLI flag rendering
- [ ] Add `llamacpp` + `llamacpp-ui` service specs
- [ ] Support GGUF model volume and persistence
- [ ] Handle CPU vs GPU image selection
- [ ] Add health checks (`/health`, `/v1/models`)
- [ ] Account for model load times in startup
- [ ] Document Open WebUI integration
- [ ] Test quantized models and context configuration
- [ ] Add example configs (chat, embeddings, multi-backend)

## Medium Priority

### ComfyUI Service Completion

**Status:** PLANNED
**Reference:** See `docs/plans/service-comfyui.md`

- [ ] Review and finalize ComfyUI service spec
- [ ] Add to default configuration
- [ ] Support custom workflows and model management
- [ ] Document integration and usage
- [ ] Test GPU access and workspace volumes

### Models Command Enhancement

**Status:** PARTIAL
**Reference:** See `docs/commands/models.md`, `docs/plans/models-edit.md`

- [ ] Implement `airpods models edit <name>` (Modelfile modification)
- [ ] Add `airpods models create` for building new models
- [ ] Improve search filters and output formatting
- [ ] Add batch operations (pull multiple, pattern-matched delete)

### Web Portal & UI

**Status:** PLANNED

- [ ] Create airpods-webui backend (FastAPI/Starlette)
- [ ] Implement `/portal` routes mirroring CLI operations
- [ ] Build frontend for service management
- [ ] Integrate with gateway for auth/routing
- [ ] Support browser-based workspace/config management

## Lower Priority

### Testing & Quality

- [ ] Expand unit test coverage (target >90%)
- [ ] Add integration tests with real Podman/Docker
- [ ] Create CI workflow for multi-runtime testing
- [ ] Performance benchmarks for startup times
- [ ] Plugin import/validation test suite

### Distribution & Packaging

- [ ] Publish to PyPI with automated releases
- [ ] Installation guide for uv tools
- [ ] Build Docker/Podman image for running AirPods itself
- [ ] Shell completion generation (bash/zsh/fish)
- [ ] Package for Homebrew, AUR, etc.

### Documentation

**Reference:** See `docs/goals.md` for overall project scope.

- [ ] User guides for common workflows
- [ ] Troubleshooting section with common issues
- [ ] Comprehensive config options reference
- [ ] Video tutorials for getting started
- [ ] API reference from docstrings

### Features & Improvements

- [ ] Custom networks (beyond host networking)
- [ ] Resource limits config (CPU, memory)
- [ ] Service dependencies and startup ordering
- [ ] Multi-machine orchestration (remote Podman/Docker)
- [ ] Backup/restore for volumes and configs
- [ ] Migration tools for config format changes
- [ ] Air-gapped/offline installation and image caching
- [ ] Opt-in telemetry and usage statistics

## Completed

- [x] Core CLI (`start`, `stop`, `status`, `logs`, `doctor`, `config`, `clean`)
- [x] Podman-based orchestration
- [x] Configuration system (TOML + templates)
- [x] Ollama service with GPU detection
- [x] Open WebUI with secret management
- [x] Plugin sync and auto-import
- [x] Models command with search
- [x] Backup/restore functionality
- [x] Shell completion support
- [x] Comprehensive test suite with CI

---

**Contributing:** Pick an item, open an issue to discuss, then submit a PR. See `AGENTS.md` for workflow and commit conventions.
