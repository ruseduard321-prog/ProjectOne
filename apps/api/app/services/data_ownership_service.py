"""Export and erasure of workspace-owned data.

Structural only. STEP-11's scope is the *mechanics*; the UI that drives them is
a later step. This exists now rather than later because retrofitting deletion is
expensive (CLAUDE.md §16): the shape a feature stores data in decides whether it
can be exported and erased at all, and every table added from here on will be
added against this contract instead of alongside it.

## Why a registry rather than a hardcoded query

Deletion has to be **end-to-end** (CLAUDE.md §16): the primary database, the AI
Memory System, analytics event logs, and search/cache layers. None of the latter
three exist yet. A service that hardcoded today's three tables would need
rewriting for each one, and -- far worse -- would silently keep succeeding while
missing them, reporting a completed erasure that erased two thirds of the data.

`ExportableStore` is therefore the contract a store registers under. A feature
that persists workspace data registers its store here, which is the Definition
of Done obligation CLAUDE.md §16 places on it. A store that is never registered
is visibly absent from this module rather than invisibly absent from a query.

## Erasure is a soft delete, and that is not a compromise

No table has a DELETE policy and `authenticated` holds no DELETE grant, both
deliberately (RLS Policy Pattern). Erasure sets `deleted_at`, which every RLS
policy filters on, so an erased row stops being reachable by any request at the
moment it is marked. What this does *not* do is remove the bytes, and the gap is
stated rather than glossed:

- **Reachability ends immediately.** No policy matches a soft-deleted row.
- **Hard removal is a separate, later concern** -- a scheduled purge running on
  the audited service path, with the 30-day SLA CLAUDE.md §16 sets. It is not in
  this step's scope, and this module deliberately does not pretend to it.
- **Backups age out; they are not purged on request.** A documented, bounded
  exception (CLAUDE.md §16).

Claiming a soft delete is a full erasure would be the kind of confident-sounding
falsehood this project treats as worse than a gap.
"""

import uuid
from dataclasses import dataclass
from typing import Any, Protocol

import psycopg

from app.core.logging import get_logger, log_context
from app.core.permissions import WorkspacePermission
from app.services.authorization_service import AuthorizationService
from app.storage.provider import StorageProvider

logger = get_logger(__name__)

# One exported record. `Any` for the values because each store defines its own
# shape, and an export must carry whatever a store actually holds -- narrowing
# it would mean every new store forces a change here, which is precisely the
# coupling the registry exists to avoid.
ExportedRecord = dict[str, Any]


class ExportableStore(Protocol):
    """A store holding workspace-owned data that must be exportable and erasable.

    Implemented by every store that persists workspace data. The two methods are
    a pair on purpose: a store that can be exported but not erased is a GDPR
    liability, and one that can be erased but not exported takes a user's data
    with no way for them to retain their own copy.
    """

    #: Stable identifier for this store in an export document. Stable because a
    #: user's exported archive should stay comparable across versions.
    name: str

    def export(
        self, connection: psycopg.Connection, workspace_id: uuid.UUID
    ) -> list[ExportedRecord]:
        """Return every record this store holds for a workspace."""
        ...

    def erase(
        self,
        connection: psycopg.Connection,
        workspace_id: uuid.UUID,
        storage: StorageProvider,
    ) -> int:
        """Soft-delete this store's records for a workspace, returning the count.

        `storage` is passed to **every** store, and most of them ignore it —
        their data lives entirely in PostgreSQL, so they name the parameter
        `_storage` and never touch it.

        **Widening this signature was a decision, not a convenience**
        ([[STEP-28 Asset Upload and Download#Decisions]] D1, settled by the
        project owner on 2026-08-16). A store holding bytes outside the database
        cannot erase them through a `psycopg.Connection`, and the alternative —
        deleting objects in `erase_workspace` before delegating to the stores —
        was explicitly rejected. The registry's whole value is that a store
        absent from it is *visible*: an erasure result reporting `"assets": 0` is
        a number a reader can question, while a deletion path living outside the
        registry is one nobody knows to look for. Nine stores carrying an unused
        parameter is a small, uniform cost paid once, in exchange for every
        future store with external bytes having an obvious place to put its
        deletion.
        """
        ...


@dataclass(frozen=True)
class WorkspaceExport:
    """Everything a workspace holds, as one document.

    Frozen: an export is a snapshot of what was read, and a mutable one invites
    a caller to edit the record of what a user was actually given.
    """

    workspace_id: uuid.UUID
    stores: dict[str, list[ExportedRecord]]


@dataclass(frozen=True)
class ErasureResult:
    """What an erasure actually did, per store.

    Returns per-store counts rather than a boolean because "deletion succeeded"
    is not a useful claim to make about a multi-store erasure -- the user, and
    any later audit, needs to know which stores were touched and how much each
    one held. A store missing from this mapping is a store that was never
    registered, which is exactly the failure this shape makes visible.
    """

    workspace_id: uuid.UUID
    erased: dict[str, int]


class WorkspaceMembersStore:
    """The membership rows of a workspace.

    The first registered store, and the reference implementation for the ones
    that follow. It runs entirely over the tenant connection, so RLS is what
    decides which rows it can reach -- an export cannot become a cross-tenant
    read path by being handed the wrong workspace id.
    """

    name = "workspace_members"

    def export(
        self, connection: psycopg.Connection, workspace_id: uuid.UUID
    ) -> list[ExportedRecord]:
        """Return the live membership rows of a workspace."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT user_id, role, created_at FROM public.workspace_members "
                "WHERE workspace_id = %s AND deleted_at IS NULL ORDER BY created_at",
                (workspace_id,),
            )

            return [
                {"user_id": str(row[0]), "role": row[1], "created_at": row[2].isoformat()}
                for row in cursor
            ]

    def erase(
        self,
        connection: psycopg.Connection,
        workspace_id: uuid.UUID,
        _storage: StorageProvider,
    ) -> int:
        """Soft-delete every membership row of a workspace except the actor's.

        Returned 0 unconditionally until STEP-11a: soft-deleting *any*
        `workspace_members` row was impossible for every role, because the SELECT
        policy filtered `deleted_at IS NULL` and the row vanished from the
        statement writing it. That policy no longer carries the filter, so this
        works.

        An `UPDATE`, never a `DELETE` -- no table has a DELETE policy and
        `authenticated` holds no DELETE grant, both deliberately
        ([[RLS Policy Pattern]]).

        **The actor's own row is excluded**, and this time for a rule rather than
        a defect: they are necessarily an `owner` to have reached here
        (`DELETE_WORKSPACE`), and the last-owner trigger would refuse the
        statement outright, failing the whole erasure. Excluding it erases
        everything erasable and leaves the workspace with the single owner who
        asked for it -- who can then transfer or leave deliberately, rather than
        having the choice made for them by a bulk operation.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.workspace_members SET deleted_at = now() "
                "WHERE workspace_id = %s AND deleted_at IS NULL "
                "AND user_id <> auth.uid()",
                (workspace_id,),
            )

            return cursor.rowcount


class AuditLogStore:
    """A workspace's audit trail: exportable, deliberately **not** erasable.

    Registered so the trail appears in an export -- a user is entitled to a copy
    of the record of what was done in their workspace -- while `erase` is a
    documented no-op.

    **This is the one store that deliberately does not erase, and it is a legal
    exception rather than an oversight.** CLAUDE.md §16 states that audit logs
    are retained on their own schedule, independent of user deletion requests,
    "because audit trails exist precisely to survive the events they record".
    An erasure that wiped the audit log would let anyone with `DELETE_WORKSPACE`
    destroy the evidence of what they did on the way out, which is the single
    outcome an audit log exists to prevent.

    It could not erase even if it wanted to: `audit_log` has no `deleted_at`
    column, no UPDATE policy and no UPDATE grant (migration `a3c07d5e91f4`).
    Returning 0 here is the honest report of that, and the per-store count makes
    the exception **visible in the erasure response** rather than silent -- a
    caller sees `"audit_log": 0` and can ask why, which is exactly the
    transparency CLAUDE.md §16 requires when disclosing a retention exception.
    """

    name = "audit_log"

    def export(
        self, connection: psycopg.Connection, workspace_id: uuid.UUID
    ) -> list[ExportedRecord]:
        """Return the workspace's audit trail.

        Subject to `audit_log_select_same_workspace` like every other read, so
        an export cannot reach another tenant's trail by being handed the wrong
        workspace id.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT created_at, action, actor_id, actor_email, target_id, detail "
                "FROM public.audit_log WHERE workspace_id = %s ORDER BY created_at",
                (workspace_id,),
            )

            return [
                {
                    "created_at": row[0].isoformat(),
                    "action": row[1],
                    "actor_id": str(row[2]),
                    "actor_email": row[3],
                    "target_id": str(row[4]) if row[4] else None,
                    "detail": row[5],
                }
                for row in cursor
            ]

    def erase(
        self,
        _connection: psycopg.Connection,
        _workspace_id: uuid.UUID,
        _storage: StorageProvider,
    ) -> int:
        """Erase nothing, and report that plainly.

        See the class docstring: this is a documented retention exception, not a
        gap. Returning 0 rather than raising keeps a whole-workspace erasure
        succeeding for every other store -- the alternative would be an erasure
        that fails entirely because one store is legally required to persist.
        """
        return 0


class ProviderCredentialStore:
    """A workspace's BYOK provider keys: erasable, and exported without key material.

    Registered by [[STEP-18 AI Cost Governance Controls]], closing a gap left by
    STEP-17: the table was created without being registered here, so a workspace
    erasure silently left encrypted provider keys behind. That is a CLAUDE.md §16
    obligation rather than a nicety -- a key authorizing spend on the customer's
    own upstream account is precisely what a departing customer needs removed.

    **The export carries no key, not even the ciphertext.** `last_four` and the
    provider name are what a user needs to know which keys they had configured;
    the encrypted value would be a credential sitting in a file the user is
    invited to download and email to themselves. `CredentialSummary` makes the
    same choice structurally, and this query makes it by omission.
    """

    name = "provider_credentials"

    def export(
        self, connection: psycopg.Connection, workspace_id: uuid.UUID
    ) -> list[ExportedRecord]:
        """Return which providers a workspace had configured, never the keys."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT provider, last_four, created_at FROM public.provider_credentials "
                "WHERE workspace_id = %s AND deleted_at IS NULL ORDER BY provider",
                (workspace_id,),
            )

            return [
                {"provider": row[0], "last_four": row[1], "created_at": row[2].isoformat()}
                for row in cursor
            ]

    def erase(
        self,
        connection: psycopg.Connection,
        workspace_id: uuid.UUID,
        _storage: StorageProvider,
    ) -> int:
        """Soft-delete every stored provider key for a workspace.

        An `UPDATE`, never a `DELETE` -- the table has no DELETE policy and
        `authenticated` holds no DELETE grant, both deliberately
        ([[RLS Policy Pattern]]).

        Requires `owner` or `admin`, which the UPDATE policy enforces. The caller
        reaching here already holds `DELETE_WORKSPACE`, so that is satisfied.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.provider_credentials SET deleted_at = now() "
                "WHERE workspace_id = %s AND deleted_at IS NULL",
                (workspace_id,),
            )

            return cursor.rowcount


class AISpendRecordStore:
    """A workspace's AI spend ledger: exportable, deliberately **not** erasable.

    The second documented retention exception after `AuditLogStore`, and it rests
    on the same reasoning applied to a different obligation. A spend record is a
    **financial record**: it substantiates what a customer was charged, and it is
    the evidence behind any billing dispute, refund or chargeback. Letting the
    party who incurred the spend also erase the record of it is the same defect
    as letting an actor erase their own audit trail.

    It also carries no personal data beyond the workspace it belongs to and an
    optional `actor_id` -- token counts and dollar amounts, not content. Prompts
    and completions are never stored here, which is why retaining it is
    proportionate rather than an erasure loophole.

    Like the audit log, the exception is made **visible** rather than silent: an
    erasure result reports `"ai_spend_records": 0`, which a reader can question,
    instead of the store being quietly absent from the registry.
    """

    name = "ai_spend_records"

    def export(
        self, connection: psycopg.Connection, workspace_id: uuid.UUID
    ) -> list[ExportedRecord]:
        """Return the workspace's spend history.

        Subject to `ai_spend_records_select_same_workspace` like every other
        read, so an export cannot reach another tenant's ledger by being handed
        the wrong workspace id.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT created_at, provider, model, workflow_type, "
                "prompt_tokens, completion_tokens, cost_usd "
                "FROM public.ai_spend_records "
                "WHERE workspace_id = %s AND deleted_at IS NULL ORDER BY created_at",
                (workspace_id,),
            )

            return [
                {
                    "created_at": row[0].isoformat(),
                    "provider": row[1],
                    "model": row[2],
                    "workflow_type": row[3],
                    "prompt_tokens": row[4],
                    "completion_tokens": row[5],
                    "cost_usd": str(row[6]),
                }
                for row in cursor
            ]

    def erase(
        self,
        _connection: psycopg.Connection,
        _workspace_id: uuid.UUID,
        _storage: StorageProvider,
    ) -> int:
        """Erase nothing, and report that plainly.

        See the class docstring: a documented retention exception for financial
        records, not a gap. It could not erase even if it wanted to -- the table
        has no UPDATE policy and `authenticated` holds no UPDATE grant
        (migration `b2e6f0a71c94`), so the ledger is append-only from every
        client path.
        """
        return 0


class ProjectStore:
    """A workspace's projects: exportable and erasable.

    Registered by [[STEP-20 Projects Schema and Lifecycle]] in the same change
    that creates the table, rather than afterwards. Both preceding content
    tables were registered late -- `provider_credentials` by STEP-18 and its
    erase path fixed again by STEP-19 -- and in each case the gap was a
    CLAUDE.md §16 obligation silently broken with nothing covering it.

    A project is the most obviously user-owned data in the system: it is what
    the customer came here to make. An erasure that left projects behind would
    be the clearest possible failure of "users retain ownership of their data".
    """

    name = "projects"

    def export(
        self, connection: psycopg.Connection, workspace_id: uuid.UUID
    ) -> list[ExportedRecord]:
        """Return every live project in a workspace."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, description, status, created_at "
                "FROM public.projects "
                "WHERE workspace_id = %s AND deleted_at IS NULL ORDER BY created_at",
                (workspace_id,),
            )

            return [
                {
                    "id": str(row[0]),
                    "name": row[1],
                    "description": row[2],
                    "status": row[3],
                    "created_at": row[4].isoformat(),
                }
                for row in cursor
            ]

    def erase(
        self,
        connection: psycopg.Connection,
        workspace_id: uuid.UUID,
        _storage: StorageProvider,
    ) -> int:
        """Soft-delete every project in a workspace.

        An `UPDATE`, never a `DELETE` -- the table has no DELETE policy and
        `authenticated` holds no DELETE grant, both deliberately
        ([[RLS Policy Pattern]]).

        This works because `projects_select_same_workspace` does **not** filter
        `deleted_at IS NULL`. Had it done so, this would silently affect zero
        rows -- exactly the defect STEP-19 found on `provider_credentials` after
        it had been failing unnoticed since STEP-17.

        Note it does not need to erase assets first: `assets.project_id` is a
        foreign key to a row that still exists after a soft delete, so nothing
        is orphaned. `AssetStore` erases them independently.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.projects SET deleted_at = now() "
                "WHERE workspace_id = %s AND deleted_at IS NULL",
                (workspace_id,),
            )

            return cursor.rowcount


class AssetStore:
    """A workspace's project assets: exportable and erasable.

    Separate from `ProjectStore` rather than nested inside its export, because
    the registry's per-store counts are what make an erasure auditable. An
    erasure reporting `"projects": 3` while silently having removed forty assets
    tells the reader less than two honest numbers do.

    **The export carries the storage path but not the content.** The bytes live
    outside PostgreSQL, so an export names what exists rather than embedding it.

    **The only store that erases anything outside PostgreSQL.** STEP-28 added the
    storage backend and, with it, this store's obligation to delete from it --
    the end-to-end deletion CLAUDE.md §16 requires, and the reason `erase`
    receives a `StorageProvider` at all.
    """

    name = "assets"

    def export(
        self, connection: psycopg.Connection, workspace_id: uuid.UUID
    ) -> list[ExportedRecord]:
        """Return every live asset in a workspace."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, project_id, name, kind, storage_path, created_at "
                "FROM public.assets "
                "WHERE workspace_id = %s AND deleted_at IS NULL ORDER BY created_at",
                (workspace_id,),
            )

            return [
                {
                    "id": str(row[0]),
                    "project_id": str(row[1]),
                    "name": row[2],
                    "kind": row[3],
                    "storage_path": row[4],
                    "created_at": row[5].isoformat(),
                }
                for row in cursor
            ]

    def erase(
        self,
        connection: psycopg.Connection,
        workspace_id: uuid.UUID,
        storage: StorageProvider,
    ) -> int:
        """Delete a workspace's stored objects, then soft-delete its asset rows.

        ## Row-driven, because there is nothing to enumerate

        `StorageProvider` has no listing operation (ADR-004), so there is no way
        to ask the backend what a workspace owns. **The asset rows are the only
        index of what exists in storage**, which is why the rows are read first
        and each non-null `storage_path` deleted individually. A row whose path
        is null has no object and is skipped.

        ## Objects first, rows second

        The rows are the map. Soft-deleting them first and then failing partway
        through the objects would destroy the only record of which objects were
        left behind -- an erasure that reports success while bytes remain, which
        is the most consequential failure available here precisely because it
        looks like compliance.

        Deleting objects first inverts that: a failure leaves the rows intact and
        the whole operation re-runnable. `delete` is idempotent, so objects
        already removed cost nothing on a second pass.

        ## A storage failure is not swallowed

        It propagates, which aborts `erase_workspace`'s transaction and leaves
        every row in place. That is the honest outcome: the caller learns the
        erasure did not complete, rather than receiving a per-store count that
        implies bytes are gone when they are not.

        **The row soft-delete is unchanged** -- hard removal remains a separate,
        later concern with its own SLA, exactly as this module's docstring says.
        Only the objects are removed for good, and they are removed for good
        because object storage has no `deleted_at` to set.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT storage_path FROM public.assets "
                "WHERE workspace_id = %s AND deleted_at IS NULL "
                "AND storage_path IS NOT NULL",
                (workspace_id,),
            )
            locators = [str(row[0]) for row in cursor]

        for locator in locators:
            # Passed exactly as stored, with the workspace id from the query.
            # Never parsed, split or prefixed -- the locator *is* the logical
            # name (ADR-004).
            storage.delete(workspace_id=workspace_id, logical_name=locator)

        if locators:
            logger.info(
                log_context(
                    event="workspace_objects_erased",
                    workspace_id=workspace_id,
                    objects=len(locators),
                )
            )

        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.assets SET deleted_at = now() "
                "WHERE workspace_id = %s AND deleted_at IS NULL",
                (workspace_id,),
            )

            return cursor.rowcount


class WorkflowRunStore:
    """A workspace's workflow runs: exportable and erasable.

    Registered by [[STEP-22 Minimum Workflow Engine]] in the same change that
    creates the table.

    A run records **what the platform did on the user's behalf** — which is
    their data as much as the project it acted on, and arguably more sensitive:
    it says what they automated and when. An erasure that left runs behind would
    leave a behavioural record of a workspace that had asked to be forgotten.

    Worth contrasting with `AuditLogStore`, which is deliberately un-erasable.
    The distinction is *whose* record it is and *why it exists*: an audit entry
    records a security-relevant action and survives precisely to outlive the
    events it describes (a documented legal exception, CLAUDE.md §16). A workflow
    run is ordinary product usage, so it carries no such exception and is erased
    like any other workspace data.
    """

    name = "workflow_runs"

    def export(
        self, connection: psycopg.Connection, workspace_id: uuid.UUID
    ) -> list[ExportedRecord]:
        """Return every live run in a workspace."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, workflow_type, definition_version, status, project_id, "
                "detail, started_at, finished_at, created_at "
                "FROM public.workflow_runs "
                "WHERE workspace_id = %s AND deleted_at IS NULL ORDER BY created_at",
                (workspace_id,),
            )

            return [
                {
                    "id": str(row[0]),
                    "workflow_type": row[1],
                    "definition_version": row[2],
                    "status": row[3],
                    "project_id": None if row[4] is None else str(row[4]),
                    "detail": row[5],
                    "started_at": None if row[6] is None else row[6].isoformat(),
                    "finished_at": None if row[7] is None else row[7].isoformat(),
                    "created_at": row[8].isoformat(),
                }
                for row in cursor
            ]

    def erase(
        self,
        connection: psycopg.Connection,
        workspace_id: uuid.UUID,
        _storage: StorageProvider,
    ) -> int:
        """Soft-delete every run in a workspace.

        An `UPDATE`, never a `DELETE` — the table has no DELETE policy and
        `authenticated` holds no DELETE grant.

        This works because `workflow_runs_select_same_workspace` does **not**
        filter `deleted_at IS NULL`. Had it done so, this would silently affect
        zero rows — the defect that cost STEP-11a and STEP-19 a step each.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.workflow_runs SET deleted_at = now() "
                "WHERE workspace_id = %s AND deleted_at IS NULL",
                (workspace_id,),
            )

            return cursor.rowcount


class WorkflowStepRunStore:
    """A workspace's workflow step history: exportable and erasable.

    Separate from `WorkflowRunStore` for the reason `AssetStore` is separate from
    `ProjectStore`: per-store counts are what make an erasure auditable, and one
    number covering both would hide whichever of them silently stopped working.

    Step rows carry `detail` — a step's own message, including the reason a run
    failed. That is workspace data and is erased with the rest.
    """

    name = "workflow_step_runs"

    def export(
        self, connection: psycopg.Connection, workspace_id: uuid.UUID
    ) -> list[ExportedRecord]:
        """Return every live step row in a workspace."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, run_id, step_index, step_name, status, detail, "
                "tokens_used, started_at, finished_at "
                "FROM public.workflow_step_runs "
                "WHERE workspace_id = %s AND deleted_at IS NULL "
                "ORDER BY run_id, step_index",
                (workspace_id,),
            )

            return [
                {
                    "id": str(row[0]),
                    "run_id": str(row[1]),
                    "step_index": row[2],
                    "step_name": row[3],
                    "status": row[4],
                    "detail": row[5],
                    "tokens_used": row[6],
                    "started_at": None if row[7] is None else row[7].isoformat(),
                    "finished_at": None if row[8] is None else row[8].isoformat(),
                }
                for row in cursor
            ]

    def erase(
        self,
        connection: psycopg.Connection,
        workspace_id: uuid.UUID,
        _storage: StorageProvider,
    ) -> int:
        """Soft-delete every step row in a workspace."""
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.workflow_step_runs SET deleted_at = now() "
                "WHERE workspace_id = %s AND deleted_at IS NULL",
                (workspace_id,),
            )

            return cursor.rowcount


class ConversationStore:
    """A workspace's conversations: exportable and erasable.

    Registered by [[STEP-23 AI Chat End to End]] in the same change that creates
    the table, following [[STEP-20 Projects Schema and Lifecycle]]'s precedent
    rather than the earlier pattern of registering late and discovering the gap
    a step later.

    **This is the most literally user-owned data in the system.** A project is
    something the user made; a conversation is what they *said*. CLAUDE.md §16's
    "users retain ownership of their data" has no clearer case, and an erasure
    that left conversations behind would leave a transcript of the user's own
    words in a workspace they asked to be cleared.
    """

    name = "conversations"

    def export(
        self, connection: psycopg.Connection, workspace_id: uuid.UUID
    ) -> list[ExportedRecord]:
        """Return every live conversation in a workspace."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, title, project_id, created_at "
                "FROM public.conversations "
                "WHERE workspace_id = %s AND deleted_at IS NULL ORDER BY created_at",
                (workspace_id,),
            )

            return [
                {
                    "id": str(row[0]),
                    "title": row[1],
                    "project_id": None if row[2] is None else str(row[2]),
                    "created_at": row[3].isoformat(),
                }
                for row in cursor
            ]

    def erase(
        self,
        connection: psycopg.Connection,
        workspace_id: uuid.UUID,
        _storage: StorageProvider,
    ) -> int:
        """Soft-delete every conversation in a workspace.

        An `UPDATE`, never a `DELETE`: the table has no DELETE policy and
        `authenticated` holds no DELETE grant. This works because
        `conversations_select_same_workspace` does not filter `deleted_at IS
        NULL` -- the rule four previous steps have now dealt with.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.conversations SET deleted_at = now() "
                "WHERE workspace_id = %s AND deleted_at IS NULL",
                (workspace_id,),
            )

            return cursor.rowcount


class MessageStore:
    """A workspace's chat messages: exportable and erasable.

    Separate from `ConversationStore` for the reason `AssetStore` is separate
    from `ProjectStore`: the per-store counts are what make an erasure auditable,
    and one reporting `"conversations": 2` while silently clearing two hundred
    messages tells the reader less than two honest numbers.

    **The export carries the message content**, deliberately. A conversation
    export listing only titles and timestamps would satisfy the letter of a data
    export while withholding the part the user actually wrote -- and the content
    is the whole of what makes this their data.

    `messages` has no UPDATE *policy* but does hold the UPDATE *grant*, and this
    store is why: erasure runs over the tenant connection, so without the grant
    this method would affect zero rows silently. See the migration's grants note.
    """

    name = "messages"

    def export(
        self, connection: psycopg.Connection, workspace_id: uuid.UUID
    ) -> list[ExportedRecord]:
        """Return every live message in a workspace, in conversation order."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, conversation_id, role, content, provider, model, "
                "token_count, created_at "
                "FROM public.messages "
                "WHERE workspace_id = %s AND deleted_at IS NULL "
                "ORDER BY conversation_id, created_at",
                (workspace_id,),
            )

            return [
                {
                    "id": str(row[0]),
                    "conversation_id": str(row[1]),
                    "role": row[2],
                    "content": row[3],
                    "provider": row[4],
                    "model": row[5],
                    "token_count": row[6],
                    "created_at": row[7].isoformat(),
                }
                for row in cursor
            ]

    def erase(
        self,
        connection: psycopg.Connection,
        workspace_id: uuid.UUID,
        _storage: StorageProvider,
    ) -> int:
        """Soft-delete every message in a workspace."""
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.messages SET deleted_at = now() "
                "WHERE workspace_id = %s AND deleted_at IS NULL",
                (workspace_id,),
            )

            return cursor.rowcount


class DataOwnershipService:
    """Exports and erases everything a workspace owns."""

    def __init__(
        self,
        connection: psycopg.Connection,
        authorization: AuthorizationService,
        stores: tuple[ExportableStore, ...],
        storage: StorageProvider,
    ) -> None:
        """Store the tenant connection, the authorization gate, registry and backend.

        `storage` is held here and handed to every store's `erase`, rather than
        being constructed inside the one store that needs it. That keeps
        `REGISTERED_STORES` a tuple of zero-argument instances -- the shape that
        makes the registry readable as a checklist -- and keeps the backend a
        thing this service is *given* rather than one it goes and finds
        (CLAUDE.md §12).
        """
        self._connection = connection
        self._authorization = authorization
        self._stores = stores
        self._storage = storage

    def export_workspace(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> WorkspaceExport:
        """Return every record a workspace holds, if the caller may export it.

        `EXPORT_WORKSPACE_DATA` rather than `VIEW_WORKSPACE`: a bulk copy of
        every member's data is a materially different act from reading the
        screens one has access to, and `member` deliberately does not hold it
        (see `app/core/permissions.py`).

        Raises:
            AuthorizationError: The caller's role does not permit exporting.
            WorkspaceAccessError: The caller is not a live member.
        """
        self._authorization.require(
            workspace_id, user_id, WorkspacePermission.EXPORT_WORKSPACE_DATA
        )

        return WorkspaceExport(
            workspace_id=workspace_id,
            stores={
                store.name: store.export(self._connection, workspace_id) for store in self._stores
            },
        )

    def erase_workspace(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> ErasureResult:
        """Soft-delete everything a workspace owns, if the caller may delete it.

        `DELETE_WORKSPACE` is owner-only. Destroying a workspace destroys every
        member's work, not only the actor's, so it sits with the single role that
        is also `workspaces.owner_id`.

        Runs inside one transaction: a partial erasure -- some stores cleared,
        others not -- is the worst outcome available here, because it looks like
        a completed deletion to the user while leaving data reachable.

        **The transaction covers the database and nothing else.** `AssetStore`
        deletes objects from a backend PostgreSQL cannot roll back, so a failure
        *after* those deletions leaves the rows intact and the objects gone. That
        asymmetry is deliberate and is the safe direction: a row pointing at a
        deleted object is a visible, fixable inconsistency, while an object
        surviving a reported erasure is an undetectable compliance failure. A
        storage failure propagates rather than being swallowed, so the caller is
        never told an erasure completed when it did not (CLAUDE.md §16).

        Raises:
            AuthorizationError: The caller's role does not permit deletion.
            WorkspaceAccessError: The caller is not a live member.
            StorageError: An object could not be deleted. The transaction rolls
                back, so nothing is reported as erased.
        """
        self._authorization.require(workspace_id, user_id, WorkspacePermission.DELETE_WORKSPACE)

        with self._connection.transaction():
            erased = {
                store.name: store.erase(self._connection, workspace_id, self._storage)
                for store in self._stores
            }

        return ErasureResult(workspace_id=workspace_id, erased=erased)


#: Every store holding workspace-owned data.
#
# A feature that persists workspace data adds itself here, and that registration
# is part of its Definition of Done (CLAUDE.md §16 -- a feature that writes user
# data anywhere is responsible for registering that store with the deletion
# process). The tuple is the checklist: a store absent from it is absent from
# every export and every erasure.
#
# `AuditLogStore` is registered for export but erases nothing, by design -- see
# its docstring. It is in this tuple rather than omitted from it precisely so
# the exception is visible: a store absent from the registry is invisible, while
# one reporting `"audit_log": 0` in every erasure result is a disclosed
# retention exception a reader can question.
REGISTERED_STORES: tuple[ExportableStore, ...] = (
    WorkspaceMembersStore(),
    AuditLogStore(),
    ProviderCredentialStore(),
    AISpendRecordStore(),
    ProjectStore(),
    AssetStore(),
    WorkflowRunStore(),
    WorkflowStepRunStore(),
    ConversationStore(),
    MessageStore(),
)
