"""Where a workspace's credentials meet the router.

The router knows how to choose and call a provider; the credential service knows
how to decrypt a key. Neither knows about the other, and this is the seam that
joins them without either taking a dependency on the other's concerns.

Thin on purpose. Business logic that belongs to *chat* -- conversation history,
memory, prompt assembly -- is [[STEP-23 AI Chat End to End]]'s, and putting any
of it here would make this the class every future AI feature has to modify.
"""

from __future__ import annotations

import uuid

from app.ai.errors import NoProviderAvailableError
from app.ai.provider import CompletionRequest, CompletionResponse
from app.ai.router import AIRouter
from app.core.logging import get_logger, log_context
from app.services.provider_credential_service import ProviderCredentialService

logger = get_logger(__name__)


class AIService:
    """Runs AI completions on behalf of a workspace."""

    def __init__(
        self,
        router: AIRouter,
        credentials: ProviderCredentialService,
    ) -> None:
        """Wire the router to the workspace's credential store."""
        self._router = router
        self._credentials = credentials

    def complete(
        self,
        workspace_id: uuid.UUID,
        request: CompletionRequest,
        preferred: str | None = None,
    ) -> CompletionResponse:
        """Run one completion for a workspace.

        Args:
            workspace_id: The tenant the call is made for. Read from the
                verified request context by the caller, never from a body.
            request: What to generate.
            preferred: The workspace's provider preference, if any.

        Returns:
            The completion, attributed to whichever provider answered.

        Raises:
            NoProviderAvailableError: the workspace has configured no usable
                provider.
            AllProvidersFailedError: every candidate was tried and failed.
        """
        configured = self._credentials.configured_providers(workspace_id)

        if not configured:
            # An honest, specific failure rather than a generic one: this is the
            # single most likely reason an AI call does not work in a new
            # workspace, and "no provider available" without the reason sends a
            # user looking in the wrong place (CLAUDE.md §15 -- surface
            # uncertainty honestly).
            logger.info(
                log_context(event="ai_no_credentials_configured", workspace_id=workspace_id)
            )
            raise NoProviderAvailableError("This workspace has no AI provider keys configured")

        def resolve_key(provider_name: str) -> str:
            """Decrypt one provider's key, for this workspace only.

            Closes over `workspace_id` from the verified request context, so
            there is no parameter through which a caller could ask for another
            tenant's key -- the same containment the RLS helper functions use
            (RLS Policy Pattern).
            """
            return self._credentials.key_for(workspace_id, provider_name)

        return self._router.complete(
            request=request,
            available_keys=configured,
            key_resolver=resolve_key,
            preferred=preferred,
        )
