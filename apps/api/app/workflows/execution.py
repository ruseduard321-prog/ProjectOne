"""Builds the workflow definition a job executes, bound to a live tenant session.

## Why this module exists

A `WorkflowDefinition` holds steps, and steps hold services bound to a database
connection -- `app/workflows/definitions.py` explains why a module-level
definition would be a cross-tenant leak. On the request path FastAPI's dependency
graph builds that per request. **A worker has no request**, so something has to
build it per unit of work instead, and this is that something.

## Why it is not `app/core/dependencies.py`

It very nearly is, and the reason it cannot be is worth stating rather than
rediscovering. `app/jobs/handlers.py` must not be able to reach `Settings` or
open a connection of its own (ADR-005 §5 constraint 3, asserted by
`tests/test_job_boundary.py`), so the handler is *given* a factory rather than
building one. The factory has to come from somewhere the handler does not import,
and `dependencies.py` imports the job registry -- so a factory living there and
reached from the handler would close an import cycle.

The direction is therefore one-way and deliberate: **`dependencies.py` imports
this module; this module imports nothing from it.** The request path and the
worker path then build a job's definition through exactly one function, which is
the property that matters -- a second construction path is a second set of
governance controls able to disagree with the first.

## What a handler can and cannot reach through this

It receives `WorkflowDefinitionsFactory`: a function of `(workflow_type)`
returning a function of `(session factory)`. It cannot obtain `Settings` from it
and cannot reach the privileged dispatcher through it. The factory it passes in
is always `JobContext.tenant_session`, so every read and write a step performs is
subject to the same RLS policies a request is.

## Why a session factory and not a connection

**This is the difference between a workflow step and a request, and it is the
reason these two adapters exist.** A request owns one connection for its whole
life, and `RequestSessionFactory.authenticated_as` keeps a transaction open for
that life because `SET LOCAL ROLE` and the local JWT claim only survive inside
one. That is fine while the life in question is an HTTP request.

A workflow step's life spans a **provider call**. Handing a step one connection
would therefore leave a `projectone_api` backend `idle in transaction` for the
length of an external network round trip -- up to `ExecutionBudget`'s 300-second
ceiling -- which is exactly the shape ADR-005 §4 rules out ("no transaction is
open while the long work runs") and which `app/repositories/session.py` names as
the thing `c8f1a3d54e29` rejected. An open transaction across an external call
pins the vacuum horizon and is what
`idle_in_transaction_session_timeout` exists to kill -- and being killed there
means being killed *after* the provider was paid.

So the steps here are given readers that open a short session per call and close
it. `AIService.complete` reads the configured providers, releases, calls the
provider holding nothing, and resolves the chosen key in a second short session.
`TestTheProviderCallHoldsNoTenantConnection` in `tests/test_workflows_api.py`
asserts that against `pg_stat_activity` while a real provider call is in flight.

**The privileged spend connection is a separate matter and is not changed here.**
`AISpendService.guard` deliberately holds one connection for a guarded call
rather than making eight, it is `idle` rather than `idle in transaction`, and it
is shared with chat. Narrowing it is a decision about the AI service as a whole.

## The AI path is the same one a request takes

`AIService` is constructed here from the same three parts `get_ai_service` uses:
`AIRouter`, the BYOK credential path, and `AISpendService`. `AIRouter` is
reachable *only* through `AIService`, so a workflow step cannot become a second
path to a provider that spends without passing a CLAUDE.md §15a control.

The one difference is connection scope, above: the credential path is the same
`ProviderCredentialService` over the same repository and the same cipher, reached
one short session at a time instead of over a connection somebody else is
holding. **BYOK isolation is unchanged** -- every lookup runs as `authenticated`
with the run's actor in `auth.uid()`, so the same RLS policy answers it.
"""

from __future__ import annotations

import uuid
from functools import lru_cache

import psycopg

from app.ai.crypto import CredentialCipher, parse_encryption_key
from app.ai.health import ProviderHealthTracker
from app.ai.provider import AIProvider
from app.ai.providers.anthropic import AnthropicProvider
from app.ai.providers.openai import OpenAIProvider
from app.ai.router import AIRouter
from app.core.config import Settings
from app.repositories.ai_spend import AISpendRepository
from app.repositories.projects import Project, ProjectRepository
from app.repositories.provider_credentials import ProviderCredentialRepository
from app.repositories.session import TenantSessionFactory
from app.services.ai_service import AIService
from app.services.ai_spend_service import AISpendService
from app.services.provider_credential_service import ProviderCredentialService
from app.workflows.definitions import build_definition
from app.workflows.models import WorkflowDefinition
from app.workflows.runner import WorkflowDefinitionFactory, WorkflowDefinitionsFactory


@lru_cache
def _provider_health_tracker() -> ProviderHealthTracker:
    """Return the process-wide provider health tracker.

    Cached because the breaker *is* accumulated state: a per-job tracker would
    start empty every time, so a provider could never reach the failure threshold
    and would be retried on every single job during an outage -- the exact
    behaviour `app.ai.health` exists to prevent. Per process, so the API and each
    worker track independently, which is the same stated approximation the
    request path already makes.
    """
    return ProviderHealthTracker()


@lru_cache
def _credential_cipher(encoded_key: str) -> CredentialCipher:
    """Return the process-wide cipher for a given key.

    Cached on the key rather than on `Settings`, which is unhashable. Deriving an
    AES key schedule per step would cost something for no benefit.
    """
    return CredentialCipher(parse_encryption_key(encoded_key))


def default_providers(settings: Settings) -> tuple[AIProvider, ...]:
    """Return every provider this deployment can route to.

    The same registry `get_ai_providers` returns, and deliberately the only other
    place provider classes are named. A test substitutes providers by passing its
    own tuple to `build_workflow_definitions` rather than by patching this.
    """
    return (
        OpenAIProvider(timeout_seconds=settings.ai_provider_timeout_seconds),
        AnthropicProvider(timeout_seconds=settings.ai_provider_timeout_seconds),
    )


# ------------------------------------------------------- session-scoped IO --


class _SessionScopedProjects:
    """A `ProjectReader` that opens and closes a session for the one read it does.

    Satisfies `ProjectReader` structurally rather than by inheritance, so
    `ProjectRepository` keeps its single responsibility: reaching `projects` over
    a connection somebody else's lifetime owns.
    """

    def __init__(self, sessions: TenantSessionFactory) -> None:
        """Store how this reader opens a tenant session."""
        self._sessions = sessions

    def get(self, workspace_id: uuid.UUID, project_id: uuid.UUID) -> Project | None:
        """Return one live project, over a session opened and closed here."""
        with self._sessions() as connection:
            return ProjectRepository(connection).get(workspace_id, project_id)


class _SessionScopedCredentials:
    """A `CredentialReader` whose sessions do not outlive the reads they serve.

    **The reason the provider call holds no tenant connection.** `AIService`
    resolves a key lazily, at the moment the router picks a provider, so a
    credential reader bound to one connection keeps that connection -- and its
    transaction -- open for the whole routing attempt, provider round trips
    included.

    Each call here opens a session, reads, and closes. The decrypted key is a
    local string with no connection attached to it, so the provider call that
    follows holds nothing.
    """

    def __init__(self, sessions: TenantSessionFactory, cipher: CredentialCipher) -> None:
        """Store how this reader opens a tenant session, and the cipher it decrypts with."""
        self._sessions = sessions
        self._cipher = cipher

    def configured_providers(self, workspace_id: uuid.UUID) -> tuple[str, ...]:
        """Return which providers this workspace holds keys for."""
        with self._sessions() as connection:
            return self._service(connection).configured_providers(workspace_id)

    def key_for(self, workspace_id: uuid.UUID, provider: str) -> str:
        """Return one plaintext provider key, over a session closed before returning."""
        with self._sessions() as connection:
            return self._service(connection).key_for(workspace_id, provider)

    def _service(self, connection: psycopg.Connection) -> ProviderCredentialService:
        """Build the real service over one short-lived connection.

        The real one, deliberately: decryption, the missing-key refusal and the
        audit-safe logging are all its behaviour, and reimplementing any of it
        here would be a second BYOK path able to disagree with the first.
        """
        return ProviderCredentialService(ProviderCredentialRepository(connection), self._cipher)


def build_workflow_definitions(
    settings: Settings,
    providers: tuple[AIProvider, ...] | None = None,
) -> WorkflowDefinitionsFactory:
    """Return the factory a workflow handler builds its definitions through.

    Args:
        settings: the deployment's configuration. The handler never sees it.
        providers: substituted by tests. `None` means this deployment's real
            registry, which is what the worker uses.

    Returns:
        A function of `(workflow_type)` returning a function of
        `(TenantSessionFactory)`. No connection crosses this boundary -- what
        crosses is the ability to open a short one.
    """
    resolved = default_providers(settings) if providers is None else providers
    cipher = _credential_cipher(settings.byok_encryption_key.get_secret_value())

    def definitions_for(workflow_type: str) -> WorkflowDefinitionFactory:
        def build(sessions: TenantSessionFactory) -> WorkflowDefinition:
            ai = AIService(
                AIRouter(resolved, _provider_health_tracker()),
                _SessionScopedCredentials(sessions, cipher),
                AISpendService(AISpendRepository(settings)),
            )

            return build_definition(workflow_type, _SessionScopedProjects(sessions), ai)

        return build

    return definitions_for
