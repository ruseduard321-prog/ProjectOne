"""Dependency injection wiring.

Every service reaches a router through this module. Services are constructed
per request from declared dependencies -- no module-level singletons, no
service locator, no hidden global state (CLAUDE.md 12).

The indirection looks redundant with one service. It is not: it is the seam
that lets tests override a dependency via `app.dependency_overrides` instead of
monkey-patching imports, and it keeps the wiring in one readable place as the
service count grows.
"""

from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.health_service import HealthService

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_health_service(settings: SettingsDep) -> HealthService:
    """Construct the health service with its dependencies."""
    return HealthService(settings)


HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
