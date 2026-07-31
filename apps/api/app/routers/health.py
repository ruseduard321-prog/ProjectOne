"""Health check router.

Contains no logic: it declares the route contract and delegates to the service
(CLAUDE.md 12). If a future change adds a branch or a calculation here, that
change belongs in the service instead.
"""

from fastapi import APIRouter

from app.core.dependencies import HealthServiceDep
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health",
    description="Liveness check reporting that the API process is running and able to respond.",
)
def get_health(health_service: HealthServiceDep) -> HealthResponse:
    """Return the service's current health."""
    return health_service.check()
