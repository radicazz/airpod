# docs/plans/compatibility-docker

Docker runtime support for airpods CLI.

## Current State

**Phase 1 Complete ✓** - Core Docker runtime implementation is done:

- `ContainerRuntime` Protocol extended with exec/copy/inspect methods
- `PodmanRuntime` class fully implements the extended protocol
- `DockerRuntime` class created in `airpods/docker.py` with full implementation
- `get_runtime(prefer)` factory now returns `DockerRuntime` when `prefer="docker"`
- Configuration schema (`runtime.prefer`) accepts `"auto"`, `"podman"`, `"docker"`
- Tests updated to verify both Podman and Docker runtimes

**Docker is now fully supported at the runtime layer.**

Remaining work: Phases 2-4 (refactoring hardcoded calls, dynamic dependencies, GPU abstraction).

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
│  airpods/podman.py       │    │  airpods/docker.py           │
└──────────────────────────┘    └──────────────────────────────┘
```

## Implementation Phases

### Phase 1: Core DockerRuntime ✓ COMPLETE

Created `airpods/docker.py` implementing `ContainerRuntime` protocol.

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
| `pod_status()` | `podman pod ps --format json` | `docker ps --format json` | Different JSON schema |
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

### Phase 2: Refactor Hardcoded Podman Calls (TODO)

Files with direct `podman` subprocess calls outside the runtime:

| File | Usage | Refactor Approach |
|------|-------|-------------------|
| `airpods/plugins.py` | `podman exec` for SQLite | Add `exec_in_container(container, cmd)` to runtime |
| `airpods/ollama.py` | `podman exec`, `podman cp` | Add `exec_in_container()`, `copy_to_container()` |
| `cli/commands/backup.py` | `podman exec` for DB export | Use runtime abstraction |
| `cli/commands/start.py` | `podman pull`, `podman exec` | Use runtime abstraction |
| `cli/commands/stop.py` | `podman container ls` | Add `list_containers()` to runtime |
| `cli/commands/clean.py` | Image/volume discovery | Use existing runtime methods |
| `cli/status_view.py` | `podman container inspect` | Add `container_inspect()` to runtime |

#### New Runtime Methods Required

```python
class ContainerRuntime(Protocol):
    # ... existing methods ...

    def exec_in_container(
        self, container: str, command: List[str], **kwargs
    ) -> subprocess.CompletedProcess:
        """Execute a command inside a running container."""
        ...

    def copy_to_container(
        self, src: str, container: str, dest: str
    ) -> None:
        """Copy a file from host to container."""
        ...

    def copy_from_container(
        self, container: str, src: str, dest: str
    ) -> None:
        """Copy a file from container to host."""
        ...

    def container_inspect(self, name: str) -> Optional[Dict]:
        """Inspect a container and return its configuration."""
        ...

    def list_containers(self, filters: Optional[Dict] = None) -> List[Dict]:
        """List containers matching filters."""
        ...
```

### Phase 3: Dynamic Dependencies (TODO)

Update dependency checks to be runtime-aware.

```python
# airpods/configuration/defaults.py
"dependencies": {
    "required": ["uv"],  # Common dependency
    "podman": ["podman", "podman-compose"],
    "docker": ["docker", "docker-compose"],  # Optional
    "optional": ["nvidia-smi", "skopeo"],
}

# airpods/services.py - ServiceManager.__init__
def __init__(self, ..., runtime_name: str = "podman"):
    runtime_deps = config.dependencies.get(runtime_name, [])
    self.required_dependencies = config.dependencies.required + runtime_deps
```

### Phase 4: GPU Abstraction (TODO)

Separate GPU device flag logic per runtime.

```python
# airpods/gpu.py

def get_docker_gpu_flag() -> Optional[str]:
    """Docker GPU flags using nvidia-docker runtime."""
    toolkit_installed, _ = detect_nvidia_container_toolkit()
    if not toolkit_installed:
        return None
    return "--gpus all"

def get_podman_gpu_flag() -> Optional[str]:
    """Podman GPU flags using CDI or legacy method."""
    # ... existing logic ...

def get_gpu_device_flag(runtime: str, config_flag: Optional[str] = None) -> Optional[str]:
    if config_flag and config_flag != "auto":
        return config_flag
    if runtime == "docker":
        return get_docker_gpu_flag()
    return get_podman_gpu_flag()
```

### Phase 5: Tests (IN PROGRESS)

Add Docker-specific tests.

**Completed:**
- Updated `tests/test_runtime.py` with `TestDockerRuntime` class
- Verified DockerRuntime instantiation and protocol compliance
- Updated existing tests to accept Docker runtime

**TODO:**
- Add `tests/test_docker_runtime.py` for Docker-specific integration tests
- Add cross-runtime compatibility tests

```
tests/
├── test_runtime.py           # Update to test DockerRuntime
├── test_docker_runtime.py    # New Docker-specific tests
├── test_runtime_compat.py    # Cross-runtime compatibility tests
└── conftest.py               # Fixtures for both runtimes
```

Mock-based tests for unit testing, optional integration tests when Docker available.

## File Changes Summary

### New Files

| File | Purpose | Status |
|------|---------|--------|
| `airpods/docker.py` | Docker subprocess wrapper (mirrors podman.py) | ✓ Complete |
| `tests/test_docker_runtime.py` | Docker runtime unit tests | TODO |

### Modified Files

| File | Changes | Status |
|------|---------|--------|
| `airpods/runtime.py` | Add `DockerRuntime` class, extend protocol, update `get_runtime()` | ✓ Complete |
| `airpods/podman.py` | Add exec/copy/inspect methods | ✓ Complete |
| `tests/test_runtime.py` | Add DockerRuntime tests | ✓ Complete |
| `airpods/gpu.py` | Runtime-aware GPU flag selection | TODO |
| `airpods/plugins.py` | Use runtime abstraction for exec | TODO |
| `airpods/ollama.py` | Use runtime abstraction for exec/cp | TODO |
| `airpods/services.py` | Pass runtime name for dependency selection | TODO |
| `airpods/configuration/defaults.py` | Split dependencies by runtime | TODO |
| `airpods/configuration/schema.py` | Update DependenciesConfig model | TODO |
| `airpods/cli/common.py` | Runtime-aware remediation messages | TODO |
| `airpods/cli/commands/backup.py` | Use runtime abstraction | TODO |
| `airpods/cli/commands/start.py` | Use runtime abstraction | TODO |
| `airpods/cli/commands/stop.py` | Use runtime abstraction | TODO |
| `airpods/cli/commands/clean.py` | Use runtime abstraction | TODO |
| `airpods/cli/status_view.py` | Use runtime abstraction | TODO |

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

### Phase 1 (Complete)
- [x] `DockerRuntime` class implemented in `airpods/docker.py`
- [x] `get_runtime("docker")` returns `DockerRuntime` instance
- [x] Protocol extended with exec/copy/inspect methods
- [x] Both PodmanRuntime and DockerRuntime implement full protocol
- [x] Tests verify Docker runtime instantiation and method availability

### Remaining (Phases 2-5)
- [ ] `airpods doctor` passes with Docker installed (Podman absent)
- [ ] `airpods start ollama` launches Ollama container via Docker
- [ ] `airpods status` shows correct container status
- [ ] `airpods logs ollama` streams logs correctly
- [ ] `airpods stop` cleanly stops containers
- [ ] GPU passthrough works with NVIDIA + Docker
- [ ] All existing tests pass with Docker runtime
- [ ] Docker-specific integration tests added
