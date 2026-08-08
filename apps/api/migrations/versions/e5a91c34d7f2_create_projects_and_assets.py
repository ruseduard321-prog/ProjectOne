"""Create the `projects` and `assets` tables with their RLS policies.

[[STEP-20]] gives ProjectOne its first *content* tables. Everything before this
point was platform machinery -- identity, tenancy, authorization, AI governance.
A project is the first row a user creates because they came here to make
something, and `assets` is what a project accumulates while they do.

Both follow [[RLS Policy Pattern]] and [[Table Conventions]] without deviation.
Three decisions are specific to this pair and are recorded here rather than left
to be inferred from the SQL.

## The lifecycle is a `text` column with a CHECK, and the transitions live in the service

[[Projects]] gives the sequence: Idea -> Planning -> Generation -> Review ->
Editing -> Approval -> Publishing -> Analytics -> Archive. This constraint
enforces the **vocabulary** -- that `status` is one of those nine values and
never a typo -- and nothing more.

**Which transitions are legal is deliberately not expressed here.** A CHECK
constraint sees one row at a time and cannot compare the new status against the
old one; expressing a transition rule in the database would mean a trigger, and
a trigger comparing OLD to NEW is a second copy of a rule the service already
owns, in a language where it is far harder to read and test. `ProjectService`
owns the state machine so it holds for any caller (the step's Task 3), and this
constraint guarantees the service can never be handed a value outside the
vocabulary it reasons about.

That split is the same one `workspace_members.role` uses: the constraint fixes
the vocabulary, `app/core/permissions.py` gives it meaning.

## `assets` carries `workspace_id` as well as `project_id`, and that is not redundant

An asset belongs to exactly one project, and that project belongs to exactly one
workspace, so `workspace_id` is derivable by a join. It is stored anyway,
because the alternative is an RLS policy that joins:

    USING (project_id IN (SELECT id FROM projects WHERE workspace_id IN (...)))

That policy is evaluated per row, reads a second table under RLS itself, and
makes the tenant boundary of `assets` depend on the correctness of the policy on
`projects` rather than on the membership helper directly. Denormalizing one uuid
buys a policy identical in shape to every other tenant table's -- the property
[[RLS Policy Pattern]] exists to preserve.

The redundancy is constrained rather than trusted: a composite foreign key
forces `(project_id, workspace_id)` to match a real pair on `projects`, so an
asset cannot claim a workspace its project does not belong to. Without that,
denormalization would be a way to smuggle a row across the tenant boundary --
insert an asset naming your own workspace and another tenant's project.

## Neither table filters `deleted_at` in its SELECT policy

Both are soft-deleted, so a SELECT policy filtering `deleted_at IS NULL` would
make the soft delete itself impossible: the UPDATE setting `deleted_at` produces
a row the SELECT policy no longer matches, and PostgreSQL refuses it naming
row-level security while pointing at the UPDATE policy where nothing is wrong.

This has cost two previous steps ([[STEP-11a Membership Removal Policy]] on
`workspace_members`, [[STEP-19 Settings and BYOK UI]] on `provider_credentials`)
and it is not repeated here. Liveness is filtered in every query instead --
including the export and erase methods of both registered stores.

Revision ID: e5a91c34d7f2
Revises: d1f70a4c62be
Create Date: 2026-08-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e5a91c34d7f2"
down_revision: str | Sequence[str] | None = "d1f70a4c62be"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CREATE_PROJECTS = """
CREATE TABLE public.projects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,

    -- Required by `touch_row()`, which sets `NEW.version = OLD.version + 1`.
    -- A table carrying that trigger without this column fails every UPDATE with
    -- "record new has no field version".
    version integer NOT NULL DEFAULT 1,

    -- The tenant boundary. NOT NULL like every tenant-scoped table: a nullable
    -- tenant column is a row no policy can classify.
    workspace_id uuid NOT NULL
        CONSTRAINT fk_projects_workspace_id_workspaces
        REFERENCES public.workspaces (id) ON DELETE RESTRICT,

    name text NOT NULL
        CONSTRAINT ck_projects_name_not_blank CHECK (btrim(name) <> '')
        CONSTRAINT ck_projects_name_length CHECK (char_length(name) <= 200),

    -- Nullable rather than defaulted to '': a project with no description and a
    -- project described as the empty string are the same fact, and storing two
    -- representations of it means every reader handles both.
    description text
        CONSTRAINT ck_projects_description_length CHECK (char_length(description) <= 2000),

    -- The lifecycle state. `text` with a CHECK rather than an ENUM, per
    -- Table Conventions: adding or renaming a state is one ALTER rather than a
    -- type rewrite that locks the table.
    --
    -- The vocabulary matches `ProjectStatus` in `app/services/project_service.py`
    -- exactly, and `test_status_vocabulary_matches_the_database` asserts that
    -- rather than trusting it. Which transitions between these values are legal
    -- is the service's rule -- see the module docstring.
    status text NOT NULL DEFAULT 'idea'
        CONSTRAINT ck_projects_status_valid CHECK (status IN (
            'idea',
            'planning',
            'generation',
            'review',
            'editing',
            'approval',
            'publishing',
            'analytics',
            'archive'
        )),

    -- Who created it. Not an FK, for the same reason `audit_log.actor_id` and
    -- `provider_credentials.created_by` are not: the record should outlive the
    -- account that created it rather than block that account's deletion or
    -- cascade away with it.
    created_by uuid NOT NULL,

    -- A project may only be referenced by an asset together with its workspace,
    -- which requires this pair to be uniquely addressable. `id` is already
    -- unique, so this adds no real constraint on the data -- it exists solely to
    -- give the composite foreign key on `assets` something to reference.
    CONSTRAINT uq_projects_id_workspace_id UNIQUE (id, workspace_id)
);
"""

_CREATE_ASSETS = """
CREATE TABLE public.assets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    version integer NOT NULL DEFAULT 1,

    workspace_id uuid NOT NULL
        CONSTRAINT fk_assets_workspace_id_workspaces
        REFERENCES public.workspaces (id) ON DELETE RESTRICT,

    project_id uuid NOT NULL,

    name text NOT NULL
        CONSTRAINT ck_assets_name_not_blank CHECK (btrim(name) <> '')
        CONSTRAINT ck_assets_name_length CHECK (char_length(name) <= 200),

    -- What the asset *is*, kept deliberately coarse. Generation, Publishing and
    -- Analytics are later phases (this step's Scope), so the vocabulary covers
    -- what a project can hold today and is extended by the step that produces a
    -- new kind -- one ALTER, which is why this is a CHECK and not an ENUM.
    kind text NOT NULL
        CONSTRAINT ck_assets_kind_valid CHECK (kind IN (
            'document',
            'image',
            'video',
            'audio'
        )),

    -- Where the bytes live. Nullable because an asset row can legitimately exist
    -- before its content does -- a placeholder created when generation is queued
    -- is the obvious case, and STEP-22 onward fills it. No storage backend is
    -- chosen in this step, so this is an opaque locator rather than a URL with a
    -- format this migration would be guessing at.
    storage_path text
        CONSTRAINT ck_assets_storage_path_length CHECK (char_length(storage_path) <= 1024),

    created_by uuid NOT NULL,

    -- The composite foreign key, and the reason `workspace_id` is stored here at
    -- all. It forces an asset's workspace to be the workspace its project
    -- actually belongs to, so the denormalized column cannot disagree with the
    -- join it replaces.
    --
    -- Without it, `workspace_id` would be a client-supplied claim: an INSERT
    -- naming the caller's own workspace and another tenant's project would
    -- satisfy the RLS policy (which tests `workspace_id`) while attaching a row
    -- to a project the caller cannot see.
    CONSTRAINT fk_assets_project_id_projects
        FOREIGN KEY (project_id, workspace_id)
        REFERENCES public.projects (id, workspace_id) ON DELETE RESTRICT
);
"""

# Partial on `deleted_at IS NULL` throughout: every query filters liveness (the
# filter is not in the policies -- see the module docstring), so an index that
# excludes dead rows serves exactly the queries that exist.
#
# Project names are deliberately *not* unique. Two drafts of the same idea is a
# normal thing to want, and a uniqueness error on a name is a confusing way to
# discover the platform disagreed.
_INDEXES = """
CREATE INDEX ix_projects_workspace_id
    ON public.projects (workspace_id)
    WHERE deleted_at IS NULL;

CREATE INDEX ix_projects_workspace_id_status
    ON public.projects (workspace_id, status)
    WHERE deleted_at IS NULL;

CREATE INDEX ix_assets_project_id
    ON public.assets (project_id)
    WHERE deleted_at IS NULL;

CREATE INDEX ix_assets_workspace_id
    ON public.assets (workspace_id)
    WHERE deleted_at IS NULL;
"""

# ENABLE applies policies to everyone except the table owner; FORCE closes that
# gap. Both, every table -- without FORCE an isolation test connecting as the
# owner passes while proving nothing.
_ENABLE_RLS = """
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.projects FORCE ROW LEVEL SECURITY;
ALTER TABLE public.assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.assets FORCE ROW LEVEL SECURITY;
"""

# Per-command policies, never one FOR ALL: the condition under which a row may be
# read is not the condition under which it may be created.
#
# No DELETE policy on either table, deliberately. Removal is a soft delete -- an
# UPDATE setting `deleted_at`, already governed by the UPDATE policies. RLS
# denies DELETE by default, so the absence is the control.
#
# **No `deleted_at IS NULL` in either SELECT policy.** Both tables are
# soft-deleted; see the module docstring for why that filter would make the soft
# delete impossible.
_POLICIES = """
CREATE POLICY projects_select_same_workspace ON public.projects
FOR SELECT TO authenticated
USING (workspace_id IN (SELECT public.app_current_user_workspaces()));

-- Any live member may create and edit a project. This is the first table where
-- that is the right answer rather than owner/admin: a workspace exists so its
-- members can make things, and a content platform where only administrators may
-- create content is not the product [[Projects]] describes.
--
-- Contrast `provider_credentials`, which is owner/admin because a provider key
-- authorizes spend on the customer's upstream account. The distinction is
-- consequence, not consistency for its own sake.
CREATE POLICY projects_insert_member ON public.projects
FOR INSERT TO authenticated
WITH CHECK (workspace_id IN (SELECT public.app_current_user_workspaces()));

-- USING decides which rows may be touched; WITH CHECK decides what they may
-- become. Both required: without WITH CHECK a member could move a project into
-- another workspace, which is a cross-tenant write dressed as an edit.
CREATE POLICY projects_update_member ON public.projects
FOR UPDATE TO authenticated
USING (workspace_id IN (SELECT public.app_current_user_workspaces()))
WITH CHECK (workspace_id IN (SELECT public.app_current_user_workspaces()));

CREATE POLICY assets_select_same_workspace ON public.assets
FOR SELECT TO authenticated
USING (workspace_id IN (SELECT public.app_current_user_workspaces()));

CREATE POLICY assets_insert_member ON public.assets
FOR INSERT TO authenticated
WITH CHECK (workspace_id IN (SELECT public.app_current_user_workspaces()));

CREATE POLICY assets_update_member ON public.assets
FOR UPDATE TO authenticated
USING (workspace_id IN (SELECT public.app_current_user_workspaces()))
WITH CHECK (workspace_id IN (SELECT public.app_current_user_workspaces()));
"""

# Grants are an independent gate from policies, stated explicitly rather than
# inherited from Supabase's corrected defaults -- depending on a default for a
# security property is how the next platform change silently reopens it.
#
# No DELETE (soft deletion only) and no TRUNCATE, which is not subject to RLS at
# all and would let a holder empty a tenant table regardless of every policy.
_GRANTS = """
REVOKE ALL ON public.projects FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.projects TO authenticated;

REVOKE ALL ON public.assets FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.assets TO authenticated;
"""

# `touch_row` maintains `updated_at` and `version`, established by `8a6f39b07c12`.
# The WHEN clause matches the existing triggers exactly: without it,
# `UPDATE ... SET x = x` inflates the version counter on a no-op.
_TRIGGERS = """
CREATE TRIGGER trg_projects_touch_row
BEFORE UPDATE ON public.projects
FOR EACH ROW
WHEN (OLD.* IS DISTINCT FROM NEW.*)
EXECUTE FUNCTION public.touch_row();

CREATE TRIGGER trg_assets_touch_row
BEFORE UPDATE ON public.assets
FOR EACH ROW
WHEN (OLD.* IS DISTINCT FROM NEW.*)
EXECUTE FUNCTION public.touch_row();
"""


def upgrade() -> None:
    """Create both tables with their RLS policies, grants, indexes and triggers."""
    op.execute(_CREATE_PROJECTS)
    op.execute(_CREATE_ASSETS)
    op.execute(_INDEXES)
    op.execute(_ENABLE_RLS)
    op.execute(_POLICIES)
    op.execute(_GRANTS)
    op.execute(_TRIGGERS)


def downgrade() -> None:
    """Drop both tables.

    Dropping a table removes its policies, indexes, grants and triggers with it;
    they are not dropped individually.

    `assets` first: it holds a foreign key to `projects`, and dropping the
    referenced table while a dependant survives is refused. Written in the
    reverse of the creation order for exactly that reason rather than by
    convention.

    Rolling this back **destroys every project and asset in every workspace**.
    Acceptable during development, where these tables hold nothing a user
    created; a production rollback of this revision is a decision rather than a
    routine operation.
    """
    op.execute("DROP TABLE IF EXISTS public.assets;")
    op.execute("DROP TABLE IF EXISTS public.projects;")
