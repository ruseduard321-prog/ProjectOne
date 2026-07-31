"""Health check business logic.

Trivial today, but it exists so the router has something to delegate to.
Routers validate input, call services and return responses -- nothing else
(CLAUDE.md 12). Establishing that boundary on the first endpoint is cheaper
than retrofitting it once endpoints have logic worth moving.

This service takes no HTTP types and returns no HTTP types, so it is testable
without the web framework around it.
"""

from app.core.config import Settings
from app.schemas.health import HealthResponse


class HealthService:
    """Reports whether the service is able to serve requests."""

    def __init__(self, settings: Settings) -> None:
        """Store the settings this service reports from."""
        self._settings = settings

    def check(self) -> HealthResponse:
        """Return the current service status.

        A liveness check only: it answers "is this process running and able to
        respond", not "are its dependencies healthy". Dependency checks arrive
        with the dependencies themselves -- the database in STEP-07.
        """
        return HealthResponse(
            status="ok",
            service=self._settings.app_name,
            version=self._settings.version,
            environment=self._settings.environment,
        )
