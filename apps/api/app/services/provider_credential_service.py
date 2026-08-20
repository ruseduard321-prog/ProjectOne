"""BYOK credential management: the only place a provider key exists in plaintext.

Two responsibilities, and the boundary between them is the point:

- **The repository** holds ciphertext and never decrypts.
- **This service** decrypts, and hands the result straight to a provider adapter.

Nothing above this layer ever receives a plaintext key. `AIRouter` calls
`key_for` and passes the result directly into `provider.complete(...)`; no route,
no schema and no log statement in this codebase can reach one.

## Why decryption is not in the repository

A repository that returned plaintext would make every caller a potential leak
site, and the natural thing to do with a repository result is log it while
debugging. Keeping decryption one layer up means the number of places holding a
plaintext key is exactly two -- this module and the adapter it hands the key to.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from app.ai.crypto import CredentialCipher, CredentialEncryptionError
from app.ai.errors import NoProviderAvailableError
from app.core.logging import get_logger, log_context
from app.repositories.provider_credentials import (
    CredentialSummary,
    ProviderCredentialRepository,
)

logger = get_logger(__name__)

#: How many trailing characters of a key are retained for display.
_LAST_FOUR = 4

#: Below this length a key is almost certainly a typo or a truncated paste.
#: Deliberately loose: provider key formats change, and a strict pattern here
#: would reject a valid new-format key and be discovered only by a user unable
#: to save one. The provider's own 401 is the authoritative rejection.
_MINIMUM_KEY_LENGTH = 8


class CredentialReader(Protocol):
    """The two credential reads an AI completion performs.

    `AIService` needs to know which providers a workspace has keys for, and to
    decrypt one of them at the moment a provider is actually chosen. It never
    stores, lists or deletes, so it asks for nothing that can.

    A Protocol rather than the concrete service, because **the two callers own
    their connections differently**. A request owns one connection for its whole
    life and hands it over; a workflow step must not, because its execution spans
    a provider call and a connection held across that call is an open transaction
    held across a network round trip (ADR-005 §4). The concrete
    `ProviderCredentialService` satisfies this as written, so the request path is
    unchanged; `app/workflows/execution.py` satisfies it with a session per call.
    """

    def configured_providers(self, workspace_id: uuid.UUID) -> tuple[str, ...]:
        """Return which providers this workspace holds keys for."""
        ...

    def key_for(self, workspace_id: uuid.UUID, provider: str) -> str:
        """Return the plaintext key for one provider."""
        ...


class ProviderCredentialService:
    """Stores, retrieves and decrypts workspace provider credentials."""

    def __init__(
        self,
        repository: ProviderCredentialRepository,
        cipher: CredentialCipher,
    ) -> None:
        """Store the repository and the cipher keys are encrypted with."""
        self._repository = repository
        self._cipher = cipher

    def configured_providers(self, workspace_id: uuid.UUID) -> tuple[str, ...]:
        """Return which providers this workspace holds keys for."""
        return self._repository.configured_providers(workspace_id)

    def list_summaries(self, workspace_id: uuid.UUID) -> tuple[CredentialSummary, ...]:
        """Return displayable summaries, never key material."""
        return self._repository.list_summaries(workspace_id)

    def key_for(self, workspace_id: uuid.UUID, provider: str) -> str:
        """Return the plaintext key for a provider.

        **The only method in the codebase that produces a plaintext provider
        key.** Its result goes directly into a provider adapter and nowhere
        else.

        Raises:
            NoProviderAvailableError: when the workspace has no live credential
                for this provider, or the stored value cannot be decrypted. The
                two are deliberately one error: from the caller's perspective
                both mean "this provider cannot be used for this workspace", and
                distinguishing them would tell a caller that a key exists but is
                broken -- which is a fact about another tenant's data if the row
                was hidden by RLS.
        """
        stored = self._repository.credential_for(workspace_id, provider)

        if stored is None:
            raise NoProviderAvailableError(
                f"No credential stored for provider {provider}", provider
            )

        try:
            return self._cipher.decrypt(stored.encrypted_key)
        except CredentialEncryptionError:
            # Logged without the ciphertext, without the key, and without the
            # workspace's other credentials. A decryption failure almost always
            # means the encryption key was rotated without re-encrypting, which
            # is an operational event worth alerting on (CLAUDE.md §26).
            logger.exception(
                log_context(
                    event="byok_decryption_failed",
                    provider=provider,
                    credential_id=stored.id,
                )
            )
            raise NoProviderAvailableError(
                f"Stored credential for {provider} could not be decrypted", provider
            ) from None

    def store(
        self,
        workspace_id: uuid.UUID,
        provider: str,
        plaintext_key: str,
        created_by: uuid.UUID,
    ) -> CredentialSummary:
        """Encrypt and store a provider key, replacing any existing one.

        Args:
            workspace_id: The tenant the key belongs to.
            provider: Which provider it authenticates against.
            plaintext_key: The key itself. Never logged, and not returned.
            created_by: The verified caller.

        Returns:
            A summary carrying `last_four` and no key material.

        Raises:
            ValueError: if the key is implausibly short. Raised before anything
                is written, so a typo does not replace a working credential.
        """
        key = plaintext_key.strip()

        if len(key) < _MINIMUM_KEY_LENGTH:
            raise ValueError("The API key is too short to be valid")

        encrypted = self._cipher.encrypt(key)
        last_four = key[-_LAST_FOUR:]

        credential_id = self._repository.store(
            workspace_id=workspace_id,
            provider=provider,
            encrypted_key=encrypted,
            last_four=last_four,
            created_by=created_by,
        )

        # No key, no ciphertext, no last_four -- the event and its subject only.
        logger.info(
            log_context(
                event="byok_credential_stored",
                provider=provider,
                workspace_id=workspace_id,
            )
        )

        return CredentialSummary(id=credential_id, provider=provider, last_four=last_four)

    def revoke(self, workspace_id: uuid.UUID, provider: str) -> bool:
        """Soft-delete a stored credential.

        Returns:
            True when a credential was removed.
        """
        removed = self._repository.revoke(workspace_id, provider)

        if removed:
            logger.info(
                log_context(
                    event="byok_credential_revoked",
                    provider=provider,
                    workspace_id=workspace_id,
                )
            )

        return removed
