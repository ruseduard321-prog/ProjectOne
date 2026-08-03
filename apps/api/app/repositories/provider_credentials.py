"""Reads and writes BYOK provider credentials.

**Every method here runs over the tenant connection** (`TenantConnectionDep`),
so RLS is what enforces the workspace boundary rather than a `WHERE workspace_id
= ...` clause this code could forget. The workspace id still appears in queries,
but as a *filter*, never as the security control: a bug in it narrows results, it
does not widen them past the policy.

That distinction is the whole reason this repository takes a connection rather
than a DSN. A repository holding the privileged DSN would look identical at the
call site and have no isolation at all (RLS Policy Pattern -- "The Two
Connections").

## Plaintext never crosses this boundary in the read direction

`credential_for` returns ciphertext. Decryption happens one layer up, in
`ProviderCredentialService`, so the only code holding a plaintext provider key
is the code about to hand it to a provider adapter. This module can be read
end-to-end without finding a place a key could be logged.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import psycopg


@dataclass(frozen=True)
class StoredCredential:
    """One workspace's credential for one provider, still encrypted."""

    id: uuid.UUID
    provider: str
    encrypted_key: str
    last_four: str


@dataclass(frozen=True)
class CredentialSummary:
    """What a client may see about a stored credential.

    Deliberately has **no** field carrying the key, encrypted or otherwise.
    Making that structurally impossible is stronger than remembering to exclude
    it in a serializer: a future endpoint returning this type cannot leak a key
    even by accident (CLAUDE.md §16).
    """

    id: uuid.UUID
    provider: str
    last_four: str


class ProviderCredentialRepository:
    """Reaches `provider_credentials` over an RLS-subject connection."""

    def __init__(self, connection: psycopg.Connection) -> None:
        """Store the tenant-scoped connection every query runs on."""
        self._connection = connection

    def credential_for(
        self,
        workspace_id: uuid.UUID,
        provider: str,
    ) -> StoredCredential | None:
        """Return the live credential for one provider, or None.

        Returns None both when no credential exists and when RLS hid it. The two
        are indistinguishable here by design -- a repository that could tell
        them apart would be a repository capable of seeing across the tenant
        boundary.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, provider, encrypted_key, last_four
                FROM public.provider_credentials
                WHERE workspace_id = %s AND provider = %s AND deleted_at IS NULL
                """,
                (workspace_id, provider),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return StoredCredential(
            id=row[0],
            provider=row[1],
            encrypted_key=row[2],
            last_four=row[3],
        )

    def configured_providers(self, workspace_id: uuid.UUID) -> tuple[str, ...]:
        """Return the provider names this workspace holds live keys for.

        Selection calls this to answer "which providers is this workspace even
        able to use", so it deliberately reads no key material at all -- the
        question is about presence, and a query that returned ciphertext to
        answer it would put keys in memory for no reason.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT provider
                FROM public.provider_credentials
                WHERE workspace_id = %s AND deleted_at IS NULL
                ORDER BY provider
                """,
                (workspace_id,),
            )
            rows = cursor.fetchall()

        return tuple(row[0] for row in rows)

    def list_summaries(self, workspace_id: uuid.UUID) -> tuple[CredentialSummary, ...]:
        """Return what a settings screen may display.

        Never selects `encrypted_key`. [[STEP-19 Settings and BYOK UI]] renders
        these; the column it would need to leak a key is not in the query.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, provider, last_four
                FROM public.provider_credentials
                WHERE workspace_id = %s AND deleted_at IS NULL
                ORDER BY provider
                """,
                (workspace_id,),
            )
            rows = cursor.fetchall()

        return tuple(
            CredentialSummary(id=row[0], provider=row[1], last_four=row[2]) for row in rows
        )

    def store(
        self,
        workspace_id: uuid.UUID,
        provider: str,
        encrypted_key: str,
        last_four: str,
        created_by: uuid.UUID,
    ) -> uuid.UUID:
        """Insert a credential, replacing any live one for the same provider.

        Rotation is soft-delete-then-insert rather than an UPDATE, so the
        previous credential's row survives as history. The partial unique index
        (`uq_provider_credentials_workspace_provider_live`) is what makes the
        two steps safe as a pair: it constrains only live rows, so the old row
        stops colliding the moment it is soft-deleted.

        Both statements run in one transaction -- the caller's request
        transaction, opened by `RequestSessionFactory`. A crash between them
        would otherwise leave a workspace with no credential for a provider it
        had one for a moment ago.

        Returns:
            The new credential's id.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.provider_credentials
                SET deleted_at = now()
                WHERE workspace_id = %s AND provider = %s AND deleted_at IS NULL
                """,
                (workspace_id, provider),
            )
            cursor.execute(
                """
                INSERT INTO public.provider_credentials
                    (workspace_id, provider, encrypted_key, last_four, created_by)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (workspace_id, provider, encrypted_key, last_four, created_by),
            )
            row = cursor.fetchone()

        # RLS refusing an INSERT raises rather than returning no row, so this is
        # genuinely defensive. Asserting it keeps the return type honest instead
        # of `uuid.UUID | None` propagating through every caller.
        if row is None:  # pragma: no cover - defensive
            raise RuntimeError("Credential insert returned no id")

        return uuid.UUID(str(row[0]))

    def revoke(self, workspace_id: uuid.UUID, provider: str) -> bool:
        """Soft-delete the live credential for a provider.

        Returns:
            True if a credential was removed, False if there was none to remove.
            The caller distinguishes those to avoid reporting success for a
            no-op -- but note RLS makes "not yours" and "not there" identical
            here, which is correct.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.provider_credentials
                SET deleted_at = now()
                WHERE workspace_id = %s AND provider = %s AND deleted_at IS NULL
                """,
                (workspace_id, provider),
            )
            return cursor.rowcount > 0
