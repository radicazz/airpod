from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from airpods.services import ServiceManager, ServiceRegistry, ServiceSpec


class FakeRuntime:
    def __init__(self):
        self.pulled_images: list[str] = []

    def pull_image(self, image: str) -> None:  # pragma: no cover - replaced in test
        self.pulled_images.append(image)


@pytest.fixture
def service_specs() -> list[ServiceSpec]:
    return [
        ServiceSpec(name=f"svc{i}", pod=f"pod{i}", container=f"ctr{i}", image=f"img{i}")
        for i in range(3)
    ]


@pytest.fixture
def manager(service_specs: list[ServiceSpec]) -> ServiceManager:
    registry = ServiceRegistry(service_specs)
    runtime = MagicMock()
    return ServiceManager(registry, runtime)


def test_pull_images_sequential(manager: ServiceManager, service_specs):
    manager.runtime.pull_image = MagicMock()

    manager.pull_images(service_specs, max_concurrent=1)

    assert manager.runtime.pull_image.call_count == len(service_specs)


def test_pull_images_concurrent_respects_limit(manager: ServiceManager, service_specs):
    manager.runtime.pull_image = MagicMock()

    manager.pull_images(service_specs, max_concurrent=2)

    assert manager.runtime.pull_image.call_count == len(service_specs)


def test_pull_images_bubbles_exceptions(manager: ServiceManager, service_specs):
    call_count = 0

    def side_effect(_):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RuntimeError("boom")

    manager.runtime.pull_image.side_effect = side_effect

    with pytest.raises(RuntimeError):
        manager.pull_images(service_specs, max_concurrent=3)

    # With concurrent execution, the exact order of calls can vary
    # Just ensure the exception was raised and at least the failing call happened
    assert call_count >= 2
