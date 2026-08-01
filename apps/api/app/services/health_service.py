"""Health check business logic.

Routers validate input, call services and return responses — nothing else
(CLAUDE.md §12). This service takes no HTTP types and returns no HTTP types, so
it is testable without the web framework around it.
"""

from app.core.config import Settings
from app.repositories.database import DatabaseRepository
from app.schemas.health import DependencyStatus, HealthResponse


class HealthService:
    """Reports whether the service is able to serve requests."""

    def __init__(self, settings: Settings, database: DatabaseRepository) -> None:
        """Store the settings this service reports from and its dependencies."""
        self._settings = settings
        self._database = database

    def check(self) -> HealthResponse:
        """Return the current service status.

        A **readiness** check: it reports whether this instance can actually do
        its job, which means checking the dependencies it needs, not merely
        that the process is running. As of STEP-07 that is the database.

        The distinction matters operationally — an instance that is alive but
        cannot reach its database should be taken out of a load balancer, and
        that only happens if the check says so.
        """
        database_healthy = self._database.is_reachable()

        return HealthResponse(
            status="ok" if database_healthy else "degraded",
            service=self._settings.app_name,
            version=self._settings.version,
            environment=self._settings.environment,
            dependencies=[DependencyStatus(name="database", healthy=database_healthy)],
        )
