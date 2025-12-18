# docs/plans/compatibility-docker

Docker runtime support for airpods CLI.

## Status: COMPLETE ✓

The `feature/docker-runtime-support` branch has fully implemented Docker compatibility. Airpods now supports both Podman and Docker as interchangeable container runtimes.

### Key Achievements

- **Runtime Abstraction Layer**: `ContainerRuntime` protocol defines a unified interface for all container operations
- **Dual Runtime Support**: `PodmanRuntime` and `DockerRuntime` adapters provide complete implementations
- **Intelligent Selection**: `get_runtime(prefer)` auto-detects available runtimes with configurable preference
- **Full API Coverage**: All operations (volumes, images, pods, containers, exec, logs, inspect) work identically across both runtimes
- **Runtime-Aware GPU**: Separate GPU attachment logic for Docker (`--gpus`) and Podman (CDI/legacy)
- **Dynamic Dependencies**: Runtime-specific dependency validation via `runtime_deps` configuration
- **Complete Migration**: All CLI commands use the runtime abstraction; zero hardcoded `podman` or `docker` calls outside wrapper modules
- **Comprehensive Testing**: Mock-based unit tests for both runtimes, plus runtime selection and auto-detection tests

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Commands (typer)                      │
│  start, stop, status, logs, doctor, clean, backup, etc.     │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    ServiceManager                            │
│  Orchestrates services via ContainerRuntime interface       │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│               ContainerRuntime (Protocol)                    │
│  ensure_volume, pull_image, ensure_pod, run_container, etc. │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               ▼                              ▼
┌──────────────────────────┐    ┌──────────────────────────────┐
│     PodmanRuntime ✓      │    │     DockerRuntime ✓          │
│  airpods/runtime.py      │    │  airpods/runtime.py          │
└──────────────────────────┘    └──────────────────────────────┘

┌──────────────────────────┐    ┌──────────────────────────────┐
│   podman subprocess ✓    │    │   docker subprocess ✓        │
│  airpods/podman.py       │    │  airpods/docker.py           │
└──────────────────────────┘    └──────────────────────────────┘
```

## Implementation Phases

### Phase 1: Core DockerRuntime ✓ COMPLETE

Created `airpods/docker.py` (subprocess wrapper) and `DockerRuntime` in `airpods/runtime.py` (adapter implementing `ContainerRuntime`).

#### Methods to implement

| Method | Podman Command | Docker Equivalent | Notes |
|--------|---------------|-------------------|-------|
| `ensure_volume(name)` | `podman volume create` | `docker volume create` | Same API |
| `volume_exists(name)` | `podman volume inspect` | `docker volume inspect` | Same API |
| `list_volumes()` | `podman volume ls` | `docker volume ls` | Same API |
| `remove_volume(name)` | `podman volume rm` | `docker volume rm` | Same API |
| `pull_image(image)` | `podman pull` | `docker pull` | Same API |
| `image_exists(image)` | `podman image inspect` | `docker image inspect` | Same API |
| `image_size(image)` | `podman image inspect --format` | `docker image inspect --format` | Format differs |
| `remove_image(image)` | `podman image rm` | `docker image rm` | Same API |
| `container_exists(name)` | `podman container inspect` | `docker container inspect` | Same API |
| `run_container(...)` | `podman run --pod` | `docker run --network` | **Different approach** |
| `stream_logs(...)` | `podman logs` | `docker logs` | Same API |
| `ensure_pod(...)` | `podman pod create` | N/A | **No Docker equivalent** |
| `pod_exists(pod)` | `podman pod inspect` | N/A | **No Docker equivalent** |
| `stop_pod(name)` | `podman pod stop` | `docker stop` (per container) | Different model |
| `remove_pod(name)` | `podman pod rm` | `docker rm` (per container) | Different model |
| `pod_status()` | `podman pod ps --format json` | `docker ps --format '{{json .}}'` | Docker emits JSON per line; we normalize/group |
| `pod_inspect(name)` | `podman pod inspect` | `docker inspect` (network) | Different model |

#### The Pod Problem

Podman pods group containers sharing a network namespace. Docker has no direct equivalent.

**Solution: Use host networking (current approach)**

Both runtimes already use `--network host`, so containers bind directly to host ports. This sidesteps the pod networking issue entirely.

For Docker, the "pod" concept becomes a logical grouping tracked by naming convention:

- Pod name: `ollama`
- Container name: `ollama-0`
- No actual Docker network/compose orchestration needed

```python
# DockerRuntime approach
def ensure_pod(self, pod: str, ports: Iterable[tuple[int,int]], ...) -> bool:
    # No-op for Docker with host networking
    # Pods are just a naming convention
    return False  # Already "exists" conceptually

def run_container(self, *, pod: str, name: str, image: str, ...):
    # Run with --network host, ignore pod parameter
    # Container name already includes the pod prefix by convention
    pass
```

### Phase 2: Refactor Hardcoded Podman Calls ✓ COMPLETE

All direct `podman` subprocess calls have been refactored to use the runtime abstraction:

- `airpods/plugins.py` - Uses `runtime.exec_in_container()` for SQLite operations
- `airpods/ollama.py` - Uses `runtime.exec_in_container()` and `runtime.copy_*()` methods
- `airpods/cli/commands/backup.py` - Routes database exports through runtime
- `airpods/cli/commands/start.py` - Uses runtime for image pulls and container operations
- `airpods/cli/commands/stop.py` - Uses `runtime.list_containers()` and pod operations
- `airpods/cli/commands/clean.py` - Runtime-aware cleanup via abstraction layer
- `airpods/cli/status_view.py` - Uses `runtime.container_inspect()` for uptime/status

### Phase 3: Dynamic Dependencies ✓ COMPLETE

Runtime-specific dependency validation implemented via `runtime_deps` configuration:

- `DependenciesConfig` model includes `runtime_deps` mapping
- Default config distinguishes Podman vs Docker dependencies
- `ServiceManager` validates dependencies based on active runtime
- Doctor command provides runtime-specific remediation hints

### Phase 4: GPU Abstraction ✓ COMPLETE

Runtime-aware GPU attachment logic fully implemented:

- `airpods/gpu.py` provides separate GPU flag logic per runtime
- Docker: Uses `--gpus "device=all,capabilities=compute,utility"` to avoid EGL/Wayland dependencies
- Podman: Uses CDI when available, falls back to legacy `--device` flags with SELinux workarounds
- `get_gpu_device_flag(runtime, config)` intelligently selects appropriate flags
- CUDA version detection and image selection works across both runtimes

### Phase 5: Tests ✓ COMPLETE

Comprehensive test coverage for both runtimes:

- `tests/test_runtime.py` - Runtime selection, auto-detection, protocol compliance
- `tests/test_docker_runtime.py` - Docker-specific functionality with mocked subprocesses
- `tests/test_gpu.py` - GPU detection and flag generation for both runtimes
- Mock-based unit tests验证 command construction without requiring actual containers
- All existing tests pass with both runtimes

## File Changes Summary

### New Files

| File | Purpose | Status |
|------|---------|--------|
| `airpods/docker.py` | Docker subprocess wrapper (mirrors podman.py) | ✓ Complete |
| `tests/test_docker_runtime.py` | Docker helper unit tests (mock-based) | ✓ Complete |

### Modified Files

| File | Changes | Status |
|------|---------|--------|
| `airpods/runtime.py` | Add `DockerRuntime` class, extend protocol, update `get_runtime()` | ✓ Complete |
| `airpods/podman.py` | Add exec/copy/inspect methods | ✓ Complete |
| `tests/test_runtime.py` | Add DockerRuntime tests | ✓ Complete |
| `airpods/gpu.py` | Runtime-aware GPU flag selection | ✓ Complete |
| `airpods/plugins.py` | Use runtime abstraction for exec | ✓ Complete |
| `airpods/ollama.py` | Use runtime abstraction for exec/cp | ✓ Complete |
| `airpods/services.py` | Pass runtime name for dependency selection | ✓ Complete |
| `airpods/configuration/defaults.py` | Split dependencies by runtime | ✓ Complete |
| `airpods/configuration/schema.py` | Update DependenciesConfig model | ✓ Complete |
| `airpods/cli/common.py` | Runtime-aware remediation messages | ✓ Complete |
| `airpods/cli/commands/backup.py` | Use runtime abstraction | ✓ Complete |
| `airpods/cli/commands/start.py` | Use runtime abstraction | ✓ Complete |
| `airpods/cli/commands/stop.py` | Use runtime abstraction | ✓ Complete |
| `airpods/cli/commands/clean.py` | Use runtime abstraction | ✓ Complete |
| `airpods/cli/status_view.py` | Use runtime abstraction | ✓ Complete |

## Estimated Effort

| Phase | Hours | Dependencies |
|-------|-------|--------------|
| Phase 1: Core DockerRuntime | 6-8 | None |
| Phase 2: Refactor hardcoded calls | 4-6 | Phase 1 |
| Phase 3: Dynamic dependencies | 1-2 | Phase 1 |
| Phase 4: GPU abstraction | 2-3 | Phase 1 |
| Phase 5: Tests | 3-4 | Phase 1-4 |
| Documentation | 1-2 | All |

**Total: 17-25 hours**

## Agent Implementation Order

1. Create `airpods/docker.py` with basic wrappers
2. Implement `DockerRuntime` class in `airpods/runtime.py`
3. Update `get_runtime()` to return `DockerRuntime`
4. Add new protocol methods (`exec_in_container`, `copy_to_container`, etc.)
5. Implement new methods in both `PodmanRuntime` and `DockerRuntime`
6. Update `airpods/gpu.py` for runtime-aware GPU flags
7. Refactor each hardcoded file (plugins, ollama, CLI commands)
8. Update configuration schema and defaults
9. Add tests for `DockerRuntime`
10. Update README prerequisites

## Compatibility Notes

- **Host networking**: Both runtimes use `--network host`, ensuring identical port binding behavior
- **Image references**: `docker.io/` prefix works for both runtimes
- **Volume mounts**: Bind mounts and named volumes have identical syntax
- **Environment variables**: Same `-e KEY=VALUE` syntax
- **GPU passthrough**: Different flags but same nvidia-container-toolkit dependency
- **rootless mode**: Both support rootless; Docker requires additional setup

## Success Criteria

All phases complete ✓

- [x] `DockerRuntime` adapter implemented in `airpods/runtime.py`
- [x] Docker subprocess wrapper implemented in `airpods/docker.py`
- [x] `get_runtime("docker")` returns `DockerRuntime` instance
- [x] Protocol extended with exec/copy/inspect methods
- [x] Both PodmanRuntime and DockerRuntime implement full protocol
- [x] Tests verify Docker runtime instantiation and method availability
- [x] All CLI commands refactored to use runtime abstraction
- [x] Runtime-specific dependency validation implemented
- [x] GPU attachment logic works for both Docker and Podman
- [x] Comprehensive test coverage for both runtimes
- [x] `airpods start`, `status`, `stop`, `logs` work identically regardless of runtime
- [x] Configuration schema supports `runtime.prefer` option
- [x] Auto-detection prefers Podman but falls back to Docker gracefully

## Configuration

Users can control runtime selection via `config.toml`:

```toml
[runtime]
prefer = "auto"  # Options: "auto", "podman", "docker"
```

- `"auto"` (default): Auto-detects available runtime, preferring Podman
- `"podman"`: Explicitly use Podman (error if not installed)
- `"docker"`: Explicitly use Docker (error if not installed)

## Usage

Docker support is fully transparent. All existing commands work identically:

```bash
# Auto-detect runtime (prefers Podman, falls back to Docker)
airpods start ollama

# Check which runtime is active
airpods doctor

# View container status (works with either runtime)
airpods status

# All commands are runtime-agnostic
airpods logs ollama
airpods stop
airpods clean --all
```
