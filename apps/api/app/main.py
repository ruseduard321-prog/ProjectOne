"""FastAPI application entry point.

Composition root: it builds the application and mounts routers. No business
logic lives here, and no router imports this module -- keeping the dependency
direction one-way (CLAUDE.md 28).
"""

from fastapi import FastAPI

from app.core.config import get_settings
from app.routers import health


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    A factory rather than a module-level instance so tests can build an
    isolated app, and so configuration is resolved at call time rather than at
    import time.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="ProjectOne backend API.",
    )

    app.include_router(health.router)

    return app


app = create_app()
