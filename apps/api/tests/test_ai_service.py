"""The seam joining a workspace's credentials to the router.

Small, because the service is. The assertions worth making here are about
*tenant scoping* -- that the key resolver handed to the router can only ever
resolve keys for the workspace the request was made for.
"""

from __future__ import annotations

import os
import uuid

import pytest

from app.ai.crypto import CredentialCipher
from app.ai.errors import NoProviderAvailableError
from app.ai.health import ProviderHealthTracker
from app.ai.provider import CompletionRequest, Message, Role
from app.ai.router import AIRouter
from app.services.ai_service import AIService
from app.services.provider_credential_service import ProviderCredentialService
from tests.test_ai_router import FakeProvider
from tests.test_byok_credentials import FakeRepository

KEY_A = "sk-workspace-a-key-000000000"  # noqa: S105 - test fixture
KEY_B = "sk-workspace-b-key-111111111"  # noqa: S105 - test fixture


def a_request() -> CompletionRequest:
    """Build a minimal completion request."""
    return CompletionRequest(messages=(Message(role=Role.USER, content="Hi"),))


def build(
    providers: tuple[FakeProvider, ...],
) -> tuple[AIService, ProviderCredentialService]:
    """Wire a service over fake providers and an in-memory credential store.

    The credential service is returned alongside the AI service so tests seed
    keys through its public API rather than reaching into a private attribute.
    """
    credentials = ProviderCredentialService(FakeRepository(), CredentialCipher(os.urandom(32)))
    router = AIRouter(providers, ProviderHealthTracker())

    return AIService(router, credentials), credentials


def test_a_workspace_with_no_keys_gets_an_honest_error() -> None:
    # The single most likely reason an AI call fails in a new workspace. A
    # generic "no provider available" sends the user looking in the wrong place.
    service, _ = build((FakeProvider("openai"),))

    with pytest.raises(NoProviderAvailableError):
        service.complete(uuid.uuid4(), a_request())


def test_a_configured_workspace_completes() -> None:
    service, credentials = build((FakeProvider("openai"),))
    workspace = uuid.uuid4()
    credentials.store(workspace, "openai", KEY_A, uuid.uuid4())

    response = service.complete(workspace, a_request())

    assert response.provider == "openai"


def test_the_provider_receives_this_workspaces_key() -> None:
    provider = FakeProvider("openai")
    service, credentials = build((provider,))
    workspace = uuid.uuid4()
    credentials.store(workspace, "openai", KEY_A, uuid.uuid4())

    service.complete(workspace, a_request())

    assert provider.keys_seen == [KEY_A]


def test_one_workspaces_call_never_receives_another_workspaces_key() -> None:
    """The cross-tenant assertion this service exists to make safe.

    The resolver closes over the verified `workspace_id`, so there is no
    parameter through which a caller could ask for another tenant's key -- the
    same containment the RLS helper functions use.
    """
    provider = FakeProvider("openai")
    service, credentials = build((provider,))
    workspace_a, workspace_b = uuid.uuid4(), uuid.uuid4()
    credentials.store(workspace_a, "openai", KEY_A, uuid.uuid4())
    credentials.store(workspace_b, "openai", KEY_B, uuid.uuid4())

    service.complete(workspace_b, a_request())

    assert provider.keys_seen == [KEY_B]
    assert KEY_A not in provider.keys_seen


def test_only_providers_the_workspace_has_keys_for_are_offered() -> None:
    # A provider with no key is not a candidate, so the router must never be
    # asked to resolve one -- which would raise rather than skip.
    openai = FakeProvider("openai", cost=0.001)
    anthropic = FakeProvider("anthropic", cost=0.002)
    service, credentials = build((openai, anthropic))
    workspace = uuid.uuid4()
    credentials.store(workspace, "anthropic", KEY_A, uuid.uuid4())

    response = service.complete(workspace, a_request())

    assert response.provider == "anthropic"
    assert openai.calls == 0
