"""Make revoking a provider credential possible at all.

**A defect inherited from [[STEP-17 AI Router and Provider Abstraction]], found
by running the revoke route [[STEP-19 Settings and BYOK UI]] adds.** Until this
step nothing ever revoked a key, so nothing exercised the path -- the repository
method existed, was unit-tested against a fake, and had never once run against
PostgreSQL.

Soft-deleting a `provider_credentials` row was refused for **every role,
including `owner`**, with:

    new row violates row-level security policy for table "provider_credentials"

## The cause, established by experiment rather than by reading

`provider_credentials_select_same_workspace` filtered `deleted_at IS NULL`.
Revocation is an `UPDATE` that *sets* `deleted_at`, so the row it produces no
longer satisfies that SELECT policy -- and PostgreSQL applies the SELECT policy
to an `UPDATE`'s resulting row when the statement's `WHERE` clause requires the
row to be visible. The write is therefore refused by the policy that governs
reading, not by the one that governs writing.

Confirmed by narrowing rather than by inference, against a live database:

| Statement | Result |
|---|---|
| `UPDATE ... SET last_four = '9999'` | **1 row** -- the UPDATE policy passes |
| `UPDATE ... SET deleted_at = now()` | **refused** |
| the same, with `deleted_at` dropped from the SELECT policy | **1 row** |

So the UPDATE policy was never the problem, and neither was the grant.

## The fix is the one STEP-11a already established

[[STEP-11a Membership Removal Policy]] hit this exact defect on
`workspace_members` and resolved it by moving the `deleted_at` filter **out of
the SELECT policy and into the queries**. The reasoning it recorded applies here
without modification: *a policy answers "whose rows may this caller touch", which
is a tenant question that `deleted_at` has nothing to do with.* Liveness is a
query concern.

`provider_credentials` and the STEP-18 governance tables were written after that
fix and copied the older shape anyway -- which is worth naming plainly, because
it is the second time this pattern has cost a step.

## Tenant isolation is provably unchanged

The predicate that enforces the boundary is `app_current_user_workspaces()`, and
it is untouched. What widens is *liveness*, not *visibility*: a caller can now
see their own workspace's soft-deleted credential rows, which are rows they were
always entitled to and which carry no plaintext key.

Every query is already explicit about liveness --
`ProviderCredentialRepository.credential_for`, `configured_providers`,
`list_summaries` and `revoke` all carry `deleted_at IS NULL` in their `WHERE`
clauses -- so no caller's results change. Verified rather than asserted: the
STEP-19 suite covers listing after a revoke and cross-tenant reads over the
request connection.

## Scope

**Only `provider_credentials` is changed here.** The same latent defect exists on
`ai_budgets`, `ai_shutdown_switches`, `users` and `workspaces`, and is recorded
in [[RLS Policy Pattern]] rather than fixed, because no route in this step
soft-deletes any of them and widening a migration to tables a step does not touch
is exactly the scope creep CLAUDE.md §29/§35 forbids. Each becomes a defect the
moment a route soft-deletes that table, and the note now says so.

Revision ID: d1f70a4c62be
Revises: c9d3b71e08af
Create Date: 2026-08-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d1f70a4c62be"
down_revision: str | Sequence[str] | None = "c9d3b71e08af"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Dropped and recreated rather than altered: PostgreSQL has no
# `ALTER POLICY ... USING` that can be expressed as one idempotent statement
# alongside the rest of this file's style, and the pair is atomic inside the
# migration's transaction regardless.
#
# `deleted_at IS NULL` is gone from the predicate, and its absence is the whole
# change. The tenant clause is byte-identical to STEP-17's -- isolation is not
# being adjusted here, only liveness, which belongs in the queries.
_FIX_SELECT_POLICY = """
DROP POLICY provider_credentials_select_same_workspace ON public.provider_credentials;

CREATE POLICY provider_credentials_select_same_workspace ON public.provider_credentials
FOR SELECT TO authenticated
USING (
    workspace_id IN (SELECT public.app_current_user_workspaces())
);
"""

_RESTORE_SELECT_POLICY = """
DROP POLICY provider_credentials_select_same_workspace ON public.provider_credentials;

CREATE POLICY provider_credentials_select_same_workspace ON public.provider_credentials
FOR SELECT TO authenticated
USING (
    deleted_at IS NULL
    AND workspace_id IN (SELECT public.app_current_user_workspaces())
);
"""


def upgrade() -> None:
    """Move the liveness filter out of the SELECT policy."""
    op.execute(_FIX_SELECT_POLICY)


def downgrade() -> None:
    """Restore STEP-17's policy, reinstating the defect.

    Stated rather than glossed: downgrading past this revision makes revoking a
    provider credential impossible again. That is the correct behaviour for a
    downgrade -- it returns the schema to what the previous code expected -- but
    an operator should know the route breaks rather than discover it.
    """
    op.execute(_RESTORE_SELECT_POLICY)
