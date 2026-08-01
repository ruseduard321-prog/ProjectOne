"""Dependency injection wiring.

Every service reaches a router through this module. Services are constructed
per request from declared dependencies -- no module-level singletons, no
service locator, no hidden global state (CLAUDE.md 12).

The indirection looks redundant with one service. It is not: it is the seam
that lets tests override a dependency via `app.dependency_overrides` instead of
monkey-patching imports, and it keeps the wiring in one readable place as the
service count grows.
"""

import uuid
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

import psycopg
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.core.config import Settings, get_settings
from app.core.security import AuthError
from app.repositories.database import DatabaseRepository
from app.repositories.session import RequestSessionFactory
from app.repositories.supabase_auth import SupabaseAuthRepository
from app.repositories.users import UserRepository
from app.services.auth_service import AuthService
from app.services.health_service import HealthService
from app.services.token_service import AuthenticatedUser, TokenService, build_jwk_client

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_database_repository(settings: SettingsDep) -> DatabaseRepository:
    """Construct the database repository."""
    return DatabaseRepository(settings)


DatabaseRepositoryDep = Annotated[DatabaseRepository, Depends(get_database_repository)]


def get_health_service(
    settings: SettingsDep,
    database: DatabaseRepositoryDep,
) -> HealthService:
    """Construct the health service with its dependencies."""
    return HealthService(settings, database)


HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]


@lru_cache
def _jwk_client(jwks_url: str, cache_seconds: int, timeout_seconds: int) -> PyJWKClient:
    """Return the process-wide JWKS client for a given endpoint.

    Cached because the client holds the fetched key set: rebuilding it per
    request would re-fetch JWKS on every call, making Supabase a hard dependency
    of every single request and adding a network round trip to each one. The
    cache *inside* it still expires, so a key rotation is still picked up.

    Keyed on the primitive settings rather than the `Settings` object because
    pydantic models are unhashable — `lru_cache` raises `TypeError` on one. The
    key is also more honest this way: these three values are what actually
    determine whether two callers can share a client.
    """
    return build_jwk_client(jwks_url, cache_seconds, timeout_seconds)


def get_token_service(settings: SettingsDep) -> TokenService:
    """Construct the token verification service."""
    client = _jwk_client(
        f"{settings.supabase_auth_url}/.well-known/jwks.json",
        settings.jwks_cache_seconds,
        settings.supabase_timeout_seconds,
    )
    return TokenService(settings, client)


TokenServiceDep = Annotated[TokenService, Depends(get_token_service)]


def get_auth_service(settings: SettingsDep, token_service: TokenServiceDep) -> AuthService:
    """Construct the authentication service with its dependencies."""
    return AuthService(
        SupabaseAuthRepository(settings),
        UserRepository(settings),
        token_service,
    )


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]

# `auto_error=False` so a missing header arrives here as None rather than as
# FastAPI's own 403. Every rejection then leaves through one place below, with
# one status code and one body — a caller cannot tell "no header" from "bad
# token" from the response, which is the point.
_bearer_scheme = HTTPBearer(auto_error=False, description="Supabase access token")

BearerCredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)]


def get_current_user(
    credentials: BearerCredentialsDep,
    auth_service: AuthServiceDep,
) -> AuthenticatedUser:
    """Return the verified identity behind the request, or reject it.

    Declaring this dependency is what makes a route authenticated. There is no
    "unauthenticated fallback" identity: a route either requires this and gets a
    verified user, or does not use it at all. An anonymous sentinel is how a
    missing check turns into a silent security hole instead of a 401.

    Raises:
        HTTPException: 401 when no valid token is present.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return auth_service.authenticate(credentials.credentials)
    except AuthError as error:
        # `error.public_message` is returned; `str(error)` — which says whether
        # the token expired, failed its signature, or carried the wrong issuer —
        # is not. That distinction is an oracle for an attacker and a debugging
        # aid for us, so it belongs in logs only (CLAUDE.md §24).
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error.public_message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from error


CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]


def get_access_token(credentials: BearerCredentialsDep) -> str:
    """Return the raw bearer token, for the one operation that needs it.

    Sign-out revokes a session upstream and must send the user's own token to do
    it. Every other route wants the verified identity, not the string.

    Raises:
        HTTPException: 401 when no bearer token is present.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials


AccessTokenDep = Annotated[str, Depends(get_access_token)]


def get_request_session_factory(settings: SettingsDep) -> RequestSessionFactory:
    """Construct the factory that opens RLS-subject database sessions."""
    return RequestSessionFactory(settings)


RequestSessionFactoryDep = Annotated[RequestSessionFactory, Depends(get_request_session_factory)]


def get_tenant_connection(
    user: CurrentUserDep,
    factory: RequestSessionFactoryDep,
) -> Iterator[psycopg.Connection]:
    """Yield a database connection scoped to the calling user.

    This is the only sanctioned way for a request to reach a tenant table. It
    depends on `get_current_user`, so a connection cannot be obtained without a
    verified identity, and the identity it carries is always the verified one —
    there is no parameter through which a caller could ask for someone else's.
    """
    with factory.authenticated_as(user.id) as connection:
        yield connection


TenantConnectionDep = Annotated[psycopg.Connection, Depends(get_tenant_connection)]


def user_id_of(user: AuthenticatedUser) -> uuid.UUID:
    """Return the identifier of a verified user."""
    return user.id
