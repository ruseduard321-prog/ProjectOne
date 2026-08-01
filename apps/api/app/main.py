"""FastAPI application entry point.

Composition root: it builds the application and mounts routers. No business
logic lives here, and no router imports this module -- keeping the dependency
direction one-way (CLAUDE.md 28).
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.security import AuthorizationError, LastOwnerError
from app.routers import auth, health, workspaces


def _last_owner_conflict(_request: Request, exception: Exception) -> JSONResponse:
    """Translate the last-owner rule into a 409.

    **409, not 403.** The caller holds every permission the action requires --
    an owner leaving their own workspace has `LEAVE_WORKSPACE`. What refuses
    them is the workspace's state, and no amount of re-authenticating or
    role-changing would help. A 403 here would send an owner looking for a
    permission problem that does not exist.

    Unlike the authorization messages, this body is deliberately specific: it
    names transferring ownership as the remedy. It leaks nothing an owner does
    not already know, and withholding it would leave them stuck.
    """
    message = getattr(exception, "public_message", "Conflict")

    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": message})


def _authorization_denied(_request: Request, exception: Exception) -> JSONResponse:
    """Translate a refused permission into a 403.

    Registered once here rather than repeated as a `try/except` in every route
    that can raise it. A service may enforce a permission without the route
    knowing (see `DataOwnershipService`), and a check whose HTTP mapping depends
    on each router remembering to catch it is a check that eventually surfaces
    as a 500.

    403, not 401: the caller authenticated successfully and the answer is still
    no. `public_message` names neither the caller's role nor the permission
    required -- that detail is a map of the permission model, and belongs in the
    log (CLAUDE.md §24).
    """
    # Starlette types every handler as taking `Exception`, so the narrowing is
    # done here rather than in the signature. It cannot fail in practice --
    # FastAPI only routes the class this is registered against — but falling
    # back to the base message keeps a mis-registration a correct 403 rather
    # than an AttributeError inside the error handler.
    message = getattr(exception, "public_message", AuthorizationError.public_message)

    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": message},
    )


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

    app.add_exception_handler(AuthorizationError, _authorization_denied)
    app.add_exception_handler(LastOwnerError, _last_owner_conflict)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(workspaces.router)

    return app


app = create_app()
