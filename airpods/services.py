from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from airpods import podman, state
from airpods.system import CheckResult, check_dependency, detect_gpu


class UnknownServiceError(ValueError):
    """Raised when the user references an unknown service name."""


@dataclass(frozen=True)
class VolumeMount:
    """Describe how a host path or Podman volume is attached."""

    source: str
    target: str

    @property
    def is_bind_mount(self) -> bool:
        return Path(self.source).is_absolute()

    def as_tuple(self) -> Tuple[str, str]:
        return self.source, self.target


@dataclass(frozen=True)
class ServiceSpec:
    """Specification for a containerized service."""

    name: str
    pod: str
    container: str
    image: str
    ports: List[Tuple[int, int]] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    env_factory: Optional[Callable[[], Dict[str, str]]] = None
    volumes: List[VolumeMount] = field(default_factory=list)
    needs_gpu: bool = False
    health_path: Optional[str] = None

    def runtime_env(self) -> Dict[str, str]:
        """Merge static env with runtime env from factory."""
        data = dict(self.env)
        if self.env_factory:
            data.update(self.env_factory())
        return data


class ServiceRegistry:
    """Simple catalog + resolver for configured services."""

    def __init__(self, specs: Sequence[ServiceSpec]):
        self._order = list(specs)
        self._specs = {spec.name: spec for spec in specs}

    def all(self) -> List[ServiceSpec]:
        return list(self._order)

    def get(self, name: str) -> Optional[ServiceSpec]:
        return self._specs.get(name)

    def names(self) -> List[str]:
        return [spec.name for spec in self._order]

    def resolve(self, names: Optional[Sequence[str]]) -> List[ServiceSpec]:
        if not names:
            return self.all()
        missing = [name for name in names if name not in self._specs]
        if missing:
            raise UnknownServiceError(
                f"unknown service(s): {', '.join(missing)}. available: {', '.join(self.names())}"
            )
        return [self._specs[name] for name in names]


@dataclass(frozen=True)
class EnvironmentReport:
    checks: List[CheckResult]
    gpu_available: bool
    gpu_detail: str

    @property
    def missing(self) -> List[str]:
        return [check.name for check in self.checks if not check.ok]


class ServiceManager:
    """Performs the common Podman orchestration tasks."""

    def __init__(
        self, registry: ServiceRegistry, network_name: str = "airpods_network"
    ):
        self.registry = registry
        self.network_name = network_name

    # ----------------------------------------------------------------------------------
    # Discovery + validation helpers
    # ----------------------------------------------------------------------------------
    def resolve(self, names: Optional[Sequence[str]]) -> List[ServiceSpec]:
        """Resolve service names to specs, or return all if none specified."""
        return self.registry.resolve(names)

    def report_environment(self) -> EnvironmentReport:
        """Check system dependencies and GPU availability."""
        checks = [
            check_dependency("podman", ["--version"]),
            check_dependency("podman-compose", ["--version"]),
            check_dependency("uv", ["--version"]),
        ]
        gpu_available, gpu_detail = detect_gpu()
        return EnvironmentReport(
            checks=checks, gpu_available=gpu_available, gpu_detail=gpu_detail
        )

    def ensure_podman(self) -> None:
        """Verify podman is installed and available."""
        report = self.report_environment()
        if "podman" in report.missing:
            raise podman.PodmanError("podman is required; install it and retry.")

    # ----------------------------------------------------------------------------------
    # Pod + container orchestration
    # ----------------------------------------------------------------------------------
    def ensure_network(self) -> None:
        """Create the shared pod network if it doesn't exist."""
        podman.ensure_network(self.network_name)

    def ensure_volumes(self, specs: Iterable[ServiceSpec]) -> None:
        """Create all volumes required by the given service specs."""
        for spec in specs:
            for mount in spec.volumes:
                if mount.is_bind_mount:
                    state.ensure_volume_source(mount.source)
                else:
                    podman.ensure_volume(mount.source)

    def pull_images(self, specs: Iterable[ServiceSpec]) -> None:
        """Pull container images for the given service specs."""
        for spec in specs:
            podman.pull_image(spec.image)

    def start_service(
        self, spec: ServiceSpec, *, gpu_available: bool, force_cpu: bool = False
    ) -> None:
        """Start a service by creating its pod and running its container."""
        podman.ensure_pod(spec.pod, spec.ports, network=self.network_name)
        podman.run_container(
            pod=spec.pod,
            name=spec.container,
            image=spec.image,
            env=spec.runtime_env(),
            volumes=[mount.as_tuple() for mount in spec.volumes],
            gpu=spec.needs_gpu and gpu_available and not force_cpu,
        )

    def stop_service(
        self, spec: ServiceSpec, *, remove: bool = False, timeout: int = 10
    ) -> bool:
        """Stop a service's pod; returns True if pod existed."""
        if not podman.pod_exists(spec.pod):
            return False
        podman.stop_pod(spec.pod, timeout=timeout)
        if remove:
            podman.remove_pod(spec.pod)
        return True

    def service_ports(self, spec: ServiceSpec) -> Dict[str, List[Dict[str, str]]]:
        """Extract port bindings from a service's pod."""
        inspect_info = podman.pod_inspect(spec.pod) or {}
        infra = inspect_info.get("InfraConfig", {})
        return infra.get("PortBindings", {})

    def pod_status_rows(self) -> Dict[str, Dict[str, Any]]:
        """Return pod status indexed by pod name."""
        return {row.get("Name"): row for row in podman.pod_status()}
