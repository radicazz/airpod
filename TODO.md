# TODO

Planned features and improvements for AirPods, organized by priority.

## High Priority

### Container Abstraction (Docker Support)

**Status:** DONE
**Details:** Docker is supported via `DockerRuntime` + `airpods/docker.py`, with runtime auto-detect + `runtime.prefer` selection.

- [x] Implement `DockerRuntime` class + `airpods/docker.py` module
- [x] Handle Docker-specific differences (networking, volumes, GPU)
- [x] Test runtime detection and fallback (`runtime.prefer` config)
- [x] Update `doctor` for both Podman/Docker checks
- [x] Document runtime selection and migration

### Open WebUI Plugin Improvements

**Status:** PARTIAL
**Reference:** Plugin sync + best-effort auto-import are implemented; see `plugins/open-webui/` for examples.

- [x] Plugin sync to WebUI volume during `start`
- [x] Best-effort auto-import of plugins into Open WebUI DB (Admin > Functions)
- [ ] Add more plugin examples (Action, Pipeline, advanced Tools)
- [ ] Create scaffolding: `airpods plugins create <name> --type ...` (new command surface)
- [ ] Add lifecycle management: `enable|disable|update <name>` (new command surface)
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

**Status:** FUNCTIONAL
**Reference:** Service is implemented and enabled by default; docs plan still contains roadmap items.

- [x] Extend schema for `command_args` mapping (CLI-configured services)
- [x] Implement template resolution and CLI flag rendering
- [x] Add `llamacpp` service spec (server)
- [x] Support GGUF model volume and persistence
- [x] Handle CPU vs GPU image selection
- [x] Add health checks (`/health`)
- [x] Account for model load times in startup (startup timeout knobs + polling)
- [ ] Document Open WebUI integration
- [ ] Test quantized models and context configuration
- [ ] Add example configs (chat, embeddings, multi-backend)
- [ ] Evaluate/define `llamacpp-ui` (if still desired)

## Medium Priority

### ComfyUI Service Completion

**Status:** PARTIAL
**Reference:** See `docs/plans/service-comfyui.md`

- [x] ComfyUI service spec present and enabled by default
- [x] Add to default configuration
- [x] Workflows command + model sync utilities (`airpods workflows ...`)
- [x] Config-based custom node installs (git/local + requirements)
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
- [ ] Create CI coverage for multi-runtime smoke tests (Podman + Docker)
- [ ] Performance benchmarks for startup times
- [ ] Plugin import/validation test suite

### Distribution & Packaging

- [ ] Publish to PyPI with automated releases
- [ ] Installation guide for uv tools
- [ ] Build Docker/Podman image for running AirPods itself
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
- [ ] Optional full volume backup/restore (including large model binaries), beyond current configs + metadata backup
- [ ] Migration tools for config format changes
- [ ] Air-gapped/offline installation and image caching
- [ ] Opt-in telemetry and usage statistics

## Completed

- [x] Core CLI (`start`, `stop`, `status`, `logs`, `doctor`, `config`, `clean`)
- [x] Podman-based orchestration
- [x] Docker-based orchestration
- [x] Configuration system (TOML + templates)
- [x] Ollama service with GPU detection
- [x] Open WebUI with secret management
- [x] Plugin sync and auto-import
- [x] Models command with search
- [x] Backup/restore functionality
- [x] Shell completion support
- [x] Comprehensive test suite with CI
- [x] Config-based ComfyUI custom node installs
- [x] llama.cpp service (GGUF server)

---

**Contributing:** Pick an item, open an issue to discuss, then submit a PR. See `AGENTS.md` for workflow and commit conventions.
