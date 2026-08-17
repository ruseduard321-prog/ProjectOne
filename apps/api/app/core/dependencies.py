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

from app.ai.crypto import CredentialCipher, parse_encryption_key
from app.ai.health import ProviderHealthTracker
from app.ai.provider import AIProvider
from app.ai.providers.anthropic import AnthropicProvider
from app.ai.providers.openai import OpenAIProvider
from app.ai.router import AIRouter
from app.core.config import Settings, get_settings
from app.core.permissions import WorkspacePermission, WorkspaceRole
from app.core.security import InvalidTokenError
from app.jobs.registry import JobHandlerRegistry, build_registry
from app.jobs.service import JobService
from app.repositories.ai_spend import AISpendRepository
from app.repositories.audit import AuditRepository
from app.repositories.chat_turns import ChatTurnRepository
from app.repositories.conversations import ConversationRepository
from app.repositories.database import DatabaseRepository
from app.repositories.jobs import JobRepository
from app.repositories.memberships import MembershipRepository
from app.repositories.projects import ProjectRepository
from app.repositories.provider_credentials import ProviderCredentialRepository
from app.repositories.security_events import SecurityEventRepository
from app.repositories.session import RequestSessionFactory
from app.repositories.supabase_auth import SupabaseAuthRepository
from app.repositories.users import UserRepository
from app.repositories.workflows import WorkflowRepository
from app.services.ai_service import AIService
from app.services.ai_spend_service import AISpendService
from app.services.asset_storage_service import AssetStorageService
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService
from app.services.authorization_service import AuthorizationService
from app.services.chat_service import ChatService
from app.services.data_ownership_service import REGISTERED_STORES, DataOwnershipService
from app.services.health_service import HealthService
from app.services.membership_service import MembershipService
from app.services.project_service import ProjectService
from app.services.provider_credential_service import ProviderCredentialService
from app.services.security_event_service import SecurityEventService
from app.services.token_service import AuthenticatedUser, TokenService, build_jwk_client
from app.services.workspace_service import WorkspaceService
from app.storage.factory import build_storage_provider
from app.storage.provider import StorageProvider
from app.workflows.runner import WorkflowRunner

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


def get_audit_repository(settings: SettingsDep) -> AuditRepository:
    """Construct the audit repository."""
    return AuditRepository(settings)


AuditRepositoryDep = Annotated[AuditRepository, Depends(get_audit_repository)]


def get_audit_service(audit: AuditRepositoryDep) -> AuditService:
    """Construct the audit service."""
    return AuditService(audit)


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


def get_security_event_repository(settings: SettingsDep) -> SecurityEventRepository:
    """Construct the security event repository."""
    return SecurityEventRepository(settings)


SecurityEventRepositoryDep = Annotated[
    SecurityEventRepository, Depends(get_security_event_repository)
]


def get_security_event_service(
    events: SecurityEventRepositoryDep,
) -> SecurityEventService:
    """Construct the security event service (FA-06).

    Separate from `get_audit_service` rather than folded into it, because the
    two write to different tables under different rules: an audit entry is
    tenant-scoped and readable by that tenant, a security event is neither.
    """
    return SecurityEventService(events)


SecurityEventServiceDep = Annotated[SecurityEventService, Depends(get_security_event_service)]


def get_membership_service(
    memberships: MembershipRepositoryDep,
    authorization: AuthorizationServiceDep,
    audit: AuditServiceDep,
) -> MembershipService:
    """Construct the membership service with its dependencies."""
    return MembershipService(memberships, authorization, audit)


MembershipServiceDep = Annotated[MembershipService, Depends(get_membership_service)]


def get_workspace_service(
    settings: SettingsDep,
    connection: TenantConnectionDep,
    memberships: MembershipRepositoryDep,
    authorization: AuthorizationServiceDep,
    audit: AuditServiceDep,
) -> WorkspaceService:
    """Construct the workspace service.

    The privileged DSN is unwrapped here rather than inside the service, so the
    one place in the wiring that hands out a bypass-capable credential is
    visible in this module alongside every other dependency — the same reason
    `REGISTERED_STORES` is passed in rather than imported internally.
    """
    return WorkspaceService(
        connection,
        memberships,
        authorization,
        audit,
        settings.database_url.get_secret_value(),
        settings.database_health_timeout_seconds,
    )


WorkspaceServiceDep = Annotated[WorkspaceService, Depends(get_workspace_service)]


@lru_cache
def _cached_storage_provider() -> StorageProvider:
    """Build the storage provider once per process.

    Cached because constructing one builds an S3 client, which resolves
    configuration and sets up a connection pool — per-request construction would
    pay that cost on every upload and download for no benefit, since the client
    is stateless with respect to the caller.

    Zero-argument so `lru_cache` has something hashable to key on: `Settings` is
    a pydantic model and is not hashable, and `get_settings()` is itself cached,
    so reading it inside is equivalent to receiving it.
    """
    return build_storage_provider(get_settings())


def get_storage_provider() -> StorageProvider:
    """Return the configured object-storage backend.

    Exposed through the dependency system rather than imported directly so a
    test can substitute a fake without touching module state — the same reason
    every other collaborator here is a dependency (CLAUDE.md §12).

    Never raises `StorageNotConfiguredError` in a running API: `get_settings()`
    refuses to start without storage configuration (STEP-28 Task 1), so by the
    time a request reaches this the values are present.
    """
    return _cached_storage_provider()


StorageProviderDep = Annotated[StorageProvider, Depends(get_storage_provider)]


def get_data_ownership_service(
    connection: TenantConnectionDep,
    authorization: AuthorizationServiceDep,
    storage: StorageProviderDep,
) -> DataOwnershipService:
    """Construct the export/erasure service over the request's tenant connection.

    `REGISTERED_STORES` is passed in rather than imported inside the service, so
    a test can substitute a store registry without monkey-patching a module
    global — and so the registry's contents are visible at the wiring layer,
    where an omission is noticeable.

    `storage` is passed for the same reason: erasure has to reach the objects an
    asset row points at, and a service that constructed its own backend would be
    one a test cannot isolate from a real bucket (STEP-28 D1).
    """
    return DataOwnershipService(connection, authorization, REGISTERED_STORES, storage)


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


@lru_cache
def _provider_health_tracker() -> ProviderHealthTracker:
    """Return the process-wide provider health tracker.

    Cached because the breaker *is* accumulated state: a per-request tracker
    would start empty every time, so a provider could never reach the failure
    threshold and would be retried on every single request during an outage --
    the exact behaviour `app.ai.health` exists to prevent.

    Per process, so N workers track independently. A stated approximation, with
    the same resolution as the rate limiter's: a shared store is a new
    infrastructure dependency needing its own ADR (CLAUDE.md §10, §28).
    """
    return ProviderHealthTracker()


@lru_cache
def _credential_cipher(encoded_key: str) -> CredentialCipher:
    """Return the process-wide cipher for a given key.

    Cached on the key itself rather than on `Settings`, which is unhashable --
    the same pattern as `_jwk_client`. Constructing an `AESGCM` per request
    would re-derive the key schedule on every call for no benefit.
    """
    return CredentialCipher(parse_encryption_key(encoded_key))


def get_ai_providers(settings: SettingsDep) -> tuple[AIProvider, ...]:
    """Return every provider this deployment can route to.

    The registry, and deliberately the *only* place provider classes are named.
    Adding a provider is one entry here plus its adapter module -- the router,
    the selection logic and every test reach providers through this tuple rather
    than by importing a class (CLAUDE.md §7 -- replaceable without redesign).
    """
    return (
        OpenAIProvider(timeout_seconds=settings.ai_provider_timeout_seconds),
        AnthropicProvider(timeout_seconds=settings.ai_provider_timeout_seconds),
    )


AIProvidersDep = Annotated[tuple[AIProvider, ...], Depends(get_ai_providers)]


def get_ai_router(providers: AIProvidersDep) -> AIRouter:
    """Construct the AI router over the configured providers.

    The router is cheap to build and holds no per-request state -- the health
    tracker it consults is the cached one, and the key resolver is passed per
    call rather than held (see `AIRouter._attempt_provider`). Building it per
    request is therefore correct and keeps the wiring uniform.
    """
    return AIRouter(providers, _provider_health_tracker())


AIRouterDep = Annotated[AIRouter, Depends(get_ai_router)]


def get_provider_credential_repository(
    connection: TenantConnectionDep,
) -> ProviderCredentialRepository:
    """Construct the credential repository over the request's tenant connection.

    `TenantConnectionDep`, never the privileged one. A provider key is tenant
    data, so RLS is what keeps one workspace's key away from another -- reaching
    this table over the privileged connection would look identical here and have
    no isolation at all (RLS Policy Pattern).
    """
    return ProviderCredentialRepository(connection)


ProviderCredentialRepositoryDep = Annotated[
    ProviderCredentialRepository, Depends(get_provider_credential_repository)
]


def get_provider_credential_service(
    settings: SettingsDep,
    repository: ProviderCredentialRepositoryDep,
) -> ProviderCredentialService:
    """Construct the BYOK credential service.

    The encryption key is unwrapped here rather than inside the service, so the
    wiring layer remains the one readable place where a secret is handed to the
    code that uses it -- the same reasoning as the privileged DSN in
    `get_workspace_service`.
    """
    return ProviderCredentialService(
        repository,
        _credential_cipher(settings.byok_encryption_key.get_secret_value()),
    )


ProviderCredentialServiceDep = Annotated[
    ProviderCredentialService, Depends(get_provider_credential_service)
]


def get_project_repository(connection: TenantConnectionDep) -> ProjectRepository:
    """Construct the project repository over the request's tenant connection.

    `TenantConnectionDep`, never the privileged one -- a project and its assets
    are tenant data, so RLS is what keeps one workspace's work away from
    another. Reaching these tables over the privileged connection would look
    identical at the call site and have no isolation at all ([[RLS Policy
    Pattern]] -- "The Two Connections").
    """
    return ProjectRepository(connection)


ProjectRepositoryDep = Annotated[ProjectRepository, Depends(get_project_repository)]


def get_project_service(repository: ProjectRepositoryDep) -> ProjectService:
    """Construct the project lifecycle service."""
    return ProjectService(repository)


ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]


def get_asset_storage_service(
    projects: ProjectServiceDep,
    storage: StorageProviderDep,
) -> AssetStorageService:
    """Construct the asset upload/download service.

    Composed of two collaborators it does not own: the lifecycle service holds
    the asset rows, the provider holds the bytes, and the service between them
    owns only the ordering (STEP-28 Task 5).
    """
    return AssetStorageService(projects, storage)


AssetStorageServiceDep = Annotated[AssetStorageService, Depends(get_asset_storage_service)]


def get_ai_spend_repository(settings: SettingsDep) -> AISpendRepository:
    """Construct the spend repository.

    Takes `Settings` rather than a connection, unlike most repositories: its
    enforcement methods run over the **privileged** connection deliberately, so
    a ceiling is found whether or not the caller could see the row (see the
    repository's module docstring). It opens its own connections rather than
    joining the request's tenant transaction.
    """
    return AISpendRepository(settings)


AISpendRepositoryDep = Annotated[AISpendRepository, Depends(get_ai_spend_repository)]


def get_ai_spend_service(repository: AISpendRepositoryDep) -> AISpendService:
    """Construct the spend governance service."""
    return AISpendService(repository)


AISpendServiceDep = Annotated[AISpendService, Depends(get_ai_spend_service)]


def get_job_repository(connection: TenantConnectionDep) -> JobRepository:
    """Construct the job repository over the request's tenant connection.

    `TenantConnectionDep`, never the privileged one -- and here the distinction
    carries more than usual. Enqueueing on the tenant connection is what makes a
    job commit in the same transaction as the row that motivated it, which is the
    first property ADR-005 §1 chose a database-backed queue for.

    The privileged path to this table exists exactly once, in
    `app/repositories/job_dispatch.py`, and is deliberately **not** wired here:
    nothing on the request path may claim, lease or settle a job.
    """
    return JobRepository(connection)


JobRepositoryDep = Annotated[JobRepository, Depends(get_job_repository)]


@lru_cache
def _job_registry() -> JobHandlerRegistry:
    """Return the process-wide handler registry.

    Cached because building it validates every handler's retry ceiling, and that
    answer cannot change within a process -- the registry is fixed at import.
    Zero-argument so `lru_cache` has something hashable to key on, the same shape
    as `_cached_storage_provider`.
    """
    return build_registry()


def get_job_service(repository: JobRepositoryDep) -> JobService:
    """Construct the enqueue service.

    Takes the registry rather than importing it, so a test can enqueue against
    handlers of its own without patching module state (CLAUDE.md §12).
    """
    return JobService(repository, _job_registry())


JobServiceDep = Annotated[JobService, Depends(get_job_service)]


def get_workflow_repository(connection: TenantConnectionDep) -> WorkflowRepository:
    """Construct the workflow repository over the request's tenant connection.

    `TenantConnectionDep`, never the privileged one. A run is the record of what
    the platform did inside one workspace, so RLS is what keeps one tenant's
    execution history away from another's.
    """
    return WorkflowRepository(connection)


WorkflowRepositoryDep = Annotated[WorkflowRepository, Depends(get_workflow_repository)]


def get_workflow_runner(repository: WorkflowRepositoryDep) -> WorkflowRunner:
    """Construct the workflow runner.

    The runner takes only the repository. Its *definitions* are built per request
    from `app.workflows.definitions`, because a definition holds steps and steps
    hold request-scoped services -- see that module's docstring for why a
    module-level definition would be a cross-tenant leak.
    """
    return WorkflowRunner(repository)


WorkflowRunnerDep = Annotated[WorkflowRunner, Depends(get_workflow_runner)]


def get_ai_service(
    router: AIRouterDep,
    credentials: ProviderCredentialServiceDep,
    spend: AISpendServiceDep,
) -> AIService:
    """Construct the AI service with its dependencies.

    `AIRouter` is deliberately reachable *only* through this service. Exposing
    it as its own route-level dependency would create a second path to a
    provider -- one that spends money without passing a single CLAUDE.md §15a
    control, and one that would look perfectly ordinary at the call site.
    `test_no_ai_call_path_bypasses_governance` asserts this rather than trusting
    it.
    """
    return AIService(router, credentials, spend)


AIServiceDep = Annotated[AIService, Depends(get_ai_service)]


def get_conversation_repository(connection: TenantConnectionDep) -> ConversationRepository:
    """Construct the conversation repository over the request's tenant connection."""
    return ConversationRepository(connection)


ConversationRepositoryDep = Annotated[ConversationRepository, Depends(get_conversation_repository)]


def get_chat_turn_repository(settings: SettingsDep) -> ChatTurnRepository:
    """Construct the turn-claim repository.

    Takes `Settings` rather than the request's tenant connection, deliberately.
    A claim must survive the failure of the call it guards, and the tenant
    connection's transaction is rolled back by exactly that failure -- so a
    claim written there would not be a claim at all. See the module docstring.
    """
    return ChatTurnRepository(settings)


ChatTurnRepositoryDep = Annotated[ChatTurnRepository, Depends(get_chat_turn_repository)]


def get_chat_service(
    conversations: ConversationRepositoryDep,
    projects: ProjectRepositoryDep,
    ai: AIServiceDep,
    turns: ChatTurnRepositoryDep,
) -> ChatService:
    """Construct the chat service.

    Takes `AIService`, never `AIRouter`. That is the same containment
    `get_ai_service` documents: the router is reachable only through the service
    that applies the CLAUDE.md §15a controls, so chat cannot become a second path
    to a provider that spends without a ceiling.
    """
    return ChatService(conversations, projects, ai, turns)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
