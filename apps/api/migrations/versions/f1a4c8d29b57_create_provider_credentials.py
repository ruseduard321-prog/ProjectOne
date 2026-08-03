"""Create the BYOK provider credential store.

[[STEP-17]] makes the AI Router provider-agnostic, and [[AI Providers]] requires
Bring Your Own Key. A workspace's provider key is **tenant data of the most
sensitive kind available in this system**: it authorizes spend on an account
ProjectOne does not own, and a leak is a financial loss for the customer rather
than an inconvenience.

It therefore follows [[RLS Policy Pattern]] exactly, plus two constraints that
pattern does not impose:

## The key is stored encrypted, and this migration cannot decrypt it

The column holds ciphertext produced by the application (`app/ai/crypto.py`)
using a key from `PROJECTONE_BYOK_ENCRYPTION_KEY`. That secret lives in the
environment, never in the database and never in source control (CLAUDE.md §16,
§28a), so a database backup on its own does not yield usable provider keys.

This is defence in depth, not a replacement for RLS. RLS stops one tenant
reading another's row; encryption stops a leaked backup, a mis-scoped support
query, or a future admin path from yielding a usable credential. Both, because
either alone has a failure mode the other covers.

## No SELECT policy on the ciphertext is not possible, so the API never selects it for a client

`authenticated` needs SELECT to let the router read a key at call time, so the
policy exists. What does *not* exist is any route returning the column: the
schema layer exposes a `last_four` hint and never the value
([[STEP-19 Settings and BYOK UI]] renders that hint). The database enforces the
tenant boundary; the API enforces that even the right tenant never gets its own
key back.

## One live key per workspace per provider

A partial unique index rather than a plain one, so a soft-deleted row does not
block re-adding a key for the same provider. Without the `deleted_at IS NULL`
predicate, rotating a key twice would fail on the second attempt with a
constraint violation that reads as a bug.

Revision ID: f1a4c8d29b57
Revises: a3c07d5e91f4
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f1a4c8d29b57"
down_revision: str | Sequence[str] | None = "a3c07d5e91f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CREATE_TABLE = """
CREATE TABLE public.provider_credentials (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,

    -- Required by `touch_row()`, which sets `NEW.version = OLD.version + 1`.
    -- A table carrying that trigger without this column fails on every UPDATE
    -- with "record new has no field version" -- caught during implementation by
    -- reading the function rather than assuming its shape.
    version integer NOT NULL DEFAULT 1,

    -- The tenant boundary. NOT NULL, like every tenant-scoped table: a nullable
    -- tenant column is a row no policy can classify.
    workspace_id uuid NOT NULL
        CONSTRAINT fk_provider_credentials_workspace_id_workspaces
        REFERENCES public.workspaces (id) ON DELETE RESTRICT,

    -- Which provider the key is for. `text` with a CHECK rather than an ENUM,
    -- per Table Conventions: adding a provider is one ALTER rather than a type
    -- rewrite that locks the table.
    --
    -- The vocabulary matches `PROVIDER_NAME` in each adapter exactly. A value
    -- here that no adapter answers to is a key that can never be used, so the
    -- constraint is what makes that a loud failure at write time.
    provider text NOT NULL
        CONSTRAINT ck_provider_credentials_provider_valid CHECK (provider IN (
            'openai',
            'anthropic'
        )),

    -- The encrypted key. Never plaintext, never readable without the
    -- environment secret -- see the module docstring.
    encrypted_key text NOT NULL,

    -- The last four characters of the *plaintext* key, stored separately so a
    -- settings screen can say "sk-...a1b2" without the API ever decrypting
    -- anything. Four characters is too few to narrow a brute-force search
    -- meaningfully and is the established convention users recognise from
    -- payment forms.
    last_four text NOT NULL
        CONSTRAINT ck_provider_credentials_last_four_length CHECK (char_length(last_four) <= 4),

    -- Who added it. Not an FK, for the same reason `audit_log.actor_id` is not:
    -- the record should outlive the account that created it rather than block
    -- that account's deletion or cascade away with it.
    created_by uuid NOT NULL
);
"""

# One live key per workspace per provider. Partial, so rotation (soft-delete the
# old row, insert a new one) does not collide with the row it is replacing.
_INDEXES = """
CREATE UNIQUE INDEX uq_provider_credentials_workspace_provider_live
    ON public.provider_credentials (workspace_id, provider)
    WHERE deleted_at IS NULL;

CREATE INDEX ix_provider_credentials_workspace_id
    ON public.provider_credentials (workspace_id)
    WHERE deleted_at IS NULL;
"""

# ENABLE applies policies to everyone except the table owner; FORCE closes that
# gap. Both, every table -- without FORCE an isolation test connecting as the
# owner passes while proving nothing (RLS Policy Pattern).
_ENABLE_RLS = """
ALTER TABLE public.provider_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.provider_credentials FORCE ROW LEVEL SECURITY;
"""

# Per-command policies, never one FOR ALL: the condition under which a row may
# be read is not the condition under which it may be created.
#
# No DELETE policy, deliberately. Removal is a soft delete -- an UPDATE setting
# `deleted_at`, already governed by the UPDATE policy. RLS denies DELETE by
# default, so the absence is the control.
_POLICIES = """
CREATE POLICY provider_credentials_select_same_workspace ON public.provider_credentials
FOR SELECT TO authenticated
USING (
    deleted_at IS NULL
    AND workspace_id IN (SELECT public.app_current_user_workspaces())
);

-- Writes require owner or admin, not mere membership. A provider key authorizes
-- spend on the workspace's own upstream account, so it belongs with the roles
-- that already control billing-adjacent settings -- consistent with the
-- role-aware UPDATE policies STEP-11 established on `workspaces`.
CREATE POLICY provider_credentials_insert_privileged ON public.provider_credentials
FOR INSERT TO authenticated
WITH CHECK (
    workspace_id IN (SELECT public.app_current_user_workspaces_as(ARRAY['owner','admin']))
);

-- USING decides which rows may be touched; WITH CHECK decides what they may
-- become. Both are required: without WITH CHECK, an admin could move a
-- credential row to a workspace they do not administer.
CREATE POLICY provider_credentials_update_privileged ON public.provider_credentials
FOR UPDATE TO authenticated
USING (
    deleted_at IS NULL
    AND workspace_id IN (SELECT public.app_current_user_workspaces_as(ARRAY['owner','admin']))
)
WITH CHECK (
    workspace_id IN (SELECT public.app_current_user_workspaces_as(ARRAY['owner','admin']))
);
"""

# Grants are an independent gate from policies, stated explicitly rather than
# inherited from Supabase's defaults -- depending on a default for a security
# property is how the next platform change silently reopens it.
#
# No DELETE (soft deletion only) and no TRUNCATE, which is not subject to RLS at
# all and would let a holder empty the table regardless of every policy above.
_GRANTS = """
REVOKE ALL ON public.provider_credentials FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.provider_credentials TO authenticated;
"""

# `touch_row` maintains `updated_at` and `version`, established by
# `8a6f39b07c12`. The WHEN clause matches the existing triggers exactly: without
# it, `UPDATE ... SET x = x` inflates the version counter on a no-op.
_TRIGGER = """
CREATE TRIGGER trg_provider_credentials_touch_row
BEFORE UPDATE ON public.provider_credentials
FOR EACH ROW
WHEN (OLD.* IS DISTINCT FROM NEW.*)
EXECUTE FUNCTION public.touch_row();
"""


def upgrade() -> None:
    """Create the credential store with its RLS policies, grants and trigger."""
    op.execute(_CREATE_TABLE)
    op.execute(_INDEXES)
    op.execute(_ENABLE_RLS)
    op.execute(_POLICIES)
    op.execute(_GRANTS)
    op.execute(_TRIGGER)


def downgrade() -> None:
    """Drop the credential store.

    Dropping the table removes its policies, indexes, grants and trigger with
    it; they are not dropped individually.

    Rolling this back **destroys every stored provider key**. They are encrypted
    with an environment secret and cannot be recovered from a plaintext source,
    so every workspace would have to re-enter its keys. Acceptable during
    development; a production rollback of this revision is a decision rather
    than a routine operation.
    """
    op.execute("DROP TABLE IF EXISTS public.provider_credentials;")
