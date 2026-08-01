"""FastAPI application entry point.

Composition root: it builds the application, installs the cross-cutting
conventions every endpoint inherits, and mounts routers. No business logic
lives here, and no router imports this module -- keeping the dependency
direction one-way (CLAUDE.md 28).

The conventions themselves live next door: the error contract in
`app.core.errors`, the middleware in `app.core.middleware`, the version prefix
in `app.core.api`. This module only decides that they apply.
"""

from fastapi import FastAPI

from app.core.api import API_PREFIX
from app.core.config import get_settings
from app.core.errors import EXCEPTION_HANDLERS
from app.core.logging import configure_logging
from app.core.middleware import RateLimitMiddleware, RateLimitRule, RequestContextMiddleware
from app.routers import auth, health, workspaces

#: Rate limits, keyed by full request path.
#:
#: The authentication endpoints only. These are the routes reachable *without*
#: a credential, which makes them the ones an attacker can attempt in volume:
#: sign-in is the credential-stuffing target, sign-up the account-spam one, and
#: refresh takes a long-lived token worth guessing at.
#:
#: Authenticated routes are not limited here. They already require a verified
#: token, and a per-workspace quota is a different mechanism answering a
#: different question (cost governance, CLAUDE.md §15a) -- it belongs with the
#: AI work that needs it, not bolted onto an IP-keyed limiter.
#:
#: The numbers are deliberately generous enough that a human never meets them
#: and an automated attempt does. A legitimate user signs in a handful of times
#: an hour; ten attempts a minute from one address is a script.
_RATE_LIMITS = {
    f"{API_PREFIX}/auth/sign-in": RateLimitRule(limit=10, window_seconds=60),
    f"{API_PREFIX}/auth/sign-up": RateLimitRule(limit=5, window_seconds=60),
    f"{API_PREFIX}/auth/refresh": RateLimitRule(limit=30, window_seconds=60),
}


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    A factory rather than a module-level instance so tests can build an
    isolated app, and so configuration is resolved at call time rather than at
    import time.
    """
    settings = get_settings()

    configure_logging()

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="ProjectOne backend API.",
        # The generated OpenAPI document is served under the version prefix
        # too. A v2 mounted alongside v1 would otherwise overwrite the schema
        # of the version it was meant to coexist with.
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
    )

    for exception_type, handler in EXCEPTION_HANDLERS:
        app.add_exception_handler(exception_type, handler)

    # Starlette runs middleware in reverse registration order, so the context
    # middleware is added *last* to run *first*. That ordering matters: the
    # rate limiter logs its refusals, and a refusal logged without a
    # correlation id is the one log line a user cannot quote back.
    app.add_middleware(RateLimitMiddleware, rules=_RATE_LIMITS)
    app.add_middleware(RequestContextMiddleware)

    # `/health` is mounted unversioned, deliberately -- see `API_PREFIX`. It is
    # consumed by orchestrators and uptime checks, and versioning it would mean
    # a deploy configuration change every time the API version moves.
    app.include_router(health.router)

    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(workspaces.router, prefix=API_PREFIX)

    return app


app = create_app()
