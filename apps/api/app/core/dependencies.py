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
from collections.abc import Callable, Iterator
from functools import lru_cache
from typing import Annotated

import psycopg
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.core.config import Settings, get_settings
from app.core.permissions import WorkspacePermission, WorkspaceRole
from app.core.security import InvalidTokenError
from app.repositories.database import DatabaseRepository
from app.repositories.memberships import MembershipRepository
from app.repositories.session import RequestSessionFactory
from app.repositories.supabase_auth import SupabaseAuthRepository
from app.repositories.users import UserRepository
from app.services.auth_service import AuthService
from app.services.authorization_service import AuthorizationService
from app.services.data_ownership_service import REGISTERED_STORES, DataOwnershipService
from app.services.health_service import HealthService
from app.services.membership_service import MembershipService
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
        InvalidTokenError: when no bearer token is present. Translated to 401
            by `app.core.errors`, with the same body as a token that was
            present and bad — a caller cannot tell the two apart, which is the
            point (CLAUDE.md §24).
    """
    if credentials is None:
        raise InvalidTokenError("No bearer credentials supplied")

    # Deliberately not wrapped in a try/except. Letting the typed error
    # propagate to the registered handler is what keeps the 401 body identical
    # across every cause: a local `HTTPException` here is a second place the
    # message could drift from the one the handler produces.
    return auth_service.authenticate(credentials.credentials)


CurrentUserDep = Annotated[AuthenticatedUser, Depends(get_current_user)]


def get_access_token(credentials: BearerCredentialsDep) -> str:
    """Return the raw bearer token, for the one operation that needs it.

    Sign-out revokes a session upstream and must send the user's own token to do
    it. Every other route wants the verified identity, not the string.

    Raises:
        InvalidTokenError: when no bearer token is present.
    """
    if credentials is None:
        raise InvalidTokenError("No bearer credentials supplied")

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


def get_membership_repository(connection: TenantConnectionDep) -> MembershipRepository:
    """Construct the membership repository over the request's tenant connection."""
    return MembershipRepository(connection)


MembershipRepositoryDep = Annotated[MembershipRepository, Depends(get_membership_repository)]


def get_authorization_service(memberships: MembershipRepositoryDep) -> AuthorizationService:
    """Construct the authorization service with its dependencies."""
    return AuthorizationService(memberships)


AuthorizationServiceDep = Annotated[AuthorizationService, Depends(get_authorization_service)]


def get_membership_service(
    memberships: MembershipRepositoryDep,
    authorization: AuthorizationServiceDep,
) -> MembershipService:
    """Construct the membership service with its dependencies."""
    return MembershipService(memberships, authorization)


MembershipServiceDep = Annotated[MembershipService, Depends(get_membership_service)]


def get_data_ownership_service(
    connection: TenantConnectionDep,
    authorization: AuthorizationServiceDep,
) -> DataOwnershipService:
    """Construct the export/erasure service over the request's tenant connection.

    `REGISTERED_STORES` is passed in rather than imported inside the service, so
    a test can substitute a store registry without monkey-patching a module
    global — and so the registry's contents are visible at the wiring layer,
    where an omission is noticeable.
    """
    return DataOwnershipService(connection, authorization, REGISTERED_STORES)


DataOwnershipServiceDep = Annotated[DataOwnershipService, Depends(get_data_ownership_service)]


def requires(permission: WorkspacePermission) -> Callable[..., WorkspaceRole]:
    """Build a dependency that admits only callers holding `permission`.

    A factory because a FastAPI dependency cannot take arguments of its own: the
    permission has to be captured at import time, in the route declaration, which
    is exactly where it belongs. Requiring a permission then reads as part of the
    route's signature rather than as an `if` buried in a handler (CLAUDE.md §12):

        @router.patch("/{workspace_id}")
        def rename(role: Annotated[WorkspaceRole, Depends(requires(UPDATE_WORKSPACE))]) -> ...

    The `workspace_id` path parameter is taken from the URL by name. Every route
    using this must therefore declare `workspace_id: uuid.UUID` in its path --
    FastAPI raises at startup if it does not, so a mismatch is a boot failure
    rather than a route that silently authorizes against nothing.

    The check is never given a workspace id from a request *body*: a body-supplied
    id is a caller asserting which workspace to authorize against, which is the
    caller choosing their own permission check.

    Args:
        permission: The capability a caller must hold to reach the route.

    Returns:
        A dependency yielding the caller's role, having verified it suffices.
    """

    def dependency(
        workspace_id: uuid.UUID,
        user: CurrentUserDep,
        authorization: AuthorizationServiceDep,
    ) -> WorkspaceRole:
        # `AuthorizationError` propagates to the handler registered in
        # `app.core.errors`, which answers 403 -- never 401. Re-issuing a 401
        # here would tell a correct client its session had failed and send it
        # into a refresh loop over what is a settled "no".
        #
        # Translated there rather than here so that a refusal raised *inside* a
        # service (DataOwnershipService does exactly this) produces the same
        # status and the same body as one raised by this dependency. Two
        # translation sites is how those two answers drift apart, and a
        # difference between them is an oracle (CLAUDE.md §24).
        return authorization.require(workspace_id, user.id, permission)

    return dependency


def user_id_of(user: AuthenticatedUser) -> uuid.UUID:
    """Return the identifier of a verified user."""
    return user.id
