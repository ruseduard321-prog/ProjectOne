"""Health check router.

Contains no logic: it declares the route contract and delegates to the service
(CLAUDE.md 12). If a future change adds a branch or a calculation here, that
change belongs in the service instead.
"""

from fastapi import APIRouter, Response, status

from app.core.dependencies import HealthServiceDep
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service health",
    description=(
        "Readiness check reporting whether the API can serve requests, including "
        "the health of its dependencies. Returns 503 when any dependency is down."
    ),
    responses={
        status.HTTP_200_OK: {"description": "All dependencies healthy."},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": HealthResponse,
            "description": "At least one dependency is unreachable.",
        },
    },
)
def get_health(health_service: HealthServiceDep, response: Response) -> HealthResponse:
    """Return the service's current health.

    Translating the service's verdict into a status code is the router's job —
    HTTP is precisely what this layer owns. The health *decision* stays in the
    service (CLAUDE.md §12).
    """
    health = health_service.check()

    if health.status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return health
