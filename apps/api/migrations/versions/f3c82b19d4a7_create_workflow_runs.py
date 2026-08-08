"""Create the `workflow_runs` and `workflow_step_runs` tables with their RLS policies.

[[STEP-22]] gives ProjectOne its first tables that exist to record **what the
platform did on a user's behalf**, rather than what a user made. Everything
before this point was either platform machinery or user-created content; a run is
the audit trail of an automated process, and it is what makes [[Workflow Engine]]'s
five execution principles -- deterministic, observable, resumable, versioned,
independently executable -- true rather than aspirational.

Both follow [[RLS Policy Pattern]] and [[Table Conventions]] without deviation.
Four decisions are specific to this pair.

## Persistence *is* resumability

A run's state lives in these tables and nowhere else. There is no in-memory
registry of running workflows, deliberately: a process that holds run state in
memory loses every in-flight run when it restarts, and "resumable" then means
"resumable as long as nothing goes wrong", which is the opposite of the
requirement. The engine writes a step's outcome before starting the next one, so
the last committed row is always an honest answer to "where did this run get to".

## `definition_version` is stored on the run, not looked up

A run records the version of the workflow definition it executed. Reading the
*current* version at display time would mean a run that executed version 1 is
reported as having executed version 2 the moment the definition changes --
rewriting history to match the present, which is precisely what [[CLAUDE|CLAUDE.md]]
§7's "versioned" requirement exists to prevent.

## Step outputs are persisted, and that is not optional

`workflow_step_runs.output` stores what each step returned. It looks like a
convenience and is not: a run that pauses for approval resumes in a **different
request**, so a later step reading its predecessor's output from memory would
find nothing there.

That was found by running the real workflow rather than reasoning about it --
the planning agent resumed after approval, could not see the validation step's
result, and failed the run. The engine's own tests missed it because their steps
ignore their inputs. **A resumable engine whose steps cannot see earlier outputs
is resumable only for workflows whose steps do not communicate**, which is not
the engine [[Agent Architecture]] describes.

## The step index is unique per run, and that is the resumability guarantee

`uq_workflow_step_runs_run_id_step_index` makes it impossible for one run to hold
two rows for the same step. Without it, a resumed run that re-executed a step
would insert a second row and the run's history would show a step twice with no
indication which one counted -- and the "resume from the last completed step"
query would have to guess.

## `workflow_step_runs` carries `workspace_id` as well as `run_id`

The same reasoning as `assets` in `e5a91c34d7f2`, and the same protection: a
composite foreign key to `(id, workspace_id)` on `workflow_runs` forces a step's
workspace to be the workspace its run belongs to. Without it the denormalized
column would be a client-supplied claim, and an INSERT naming the caller's own
workspace with another tenant's `run_id` would satisfy the RLS policy while
attaching a step to a run the caller cannot see.

## Neither table filters `deleted_at` in its SELECT policy

Both are soft-deleted (workspace erasure reaches them, [[CLAUDE|CLAUDE.md]] §16),
so a SELECT policy filtering `deleted_at IS NULL` would make the soft delete
itself impossible. This has cost two previous steps and is not repeated here --
see [[RLS Policy Pattern#A SELECT policy that filters deleted at makes soft
deletion impossible]].

Revision ID: f3c82b19d4a7
Revises: e5a91c34d7f2
Create Date: 2026-08-08
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f3c82b19d4a7"
down_revision: str | Sequence[str] | None = "e5a91c34d7f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CREATE_WORKFLOW_RUNS = """
CREATE TABLE public.workflow_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    version integer NOT NULL DEFAULT 1,

    workspace_id uuid NOT NULL
        CONSTRAINT fk_workflow_runs_workspace_id_workspaces
        REFERENCES public.workspaces (id) ON DELETE RESTRICT,

    -- Which workflow definition ran. `text` rather than an FK to a definitions
    -- table: definitions are declared in code (`app/workflows/definitions.py`),
    -- not stored, because a workflow's steps are executable Python rather than
    -- data. A definitions *table* would be a second source of truth that could
    -- disagree with the code that actually runs.
    workflow_type text NOT NULL
        CONSTRAINT ck_workflow_runs_type_not_blank CHECK (btrim(workflow_type) <> '')
        CONSTRAINT ck_workflow_runs_type_length CHECK (char_length(workflow_type) <= 100),

    -- The version of that definition, as it was when this run started.
    --
    -- Stored rather than resolved at read time: see the module docstring. A run
    -- must keep describing what actually executed even after the definition
    -- changes underneath it.
    definition_version integer NOT NULL
        CONSTRAINT ck_workflow_runs_definition_version_positive CHECK (definition_version >= 1),

    -- Where the run is. The vocabulary matches `RunStatus` in
    -- `app/workflows/models.py` exactly, and a test asserts that against this
    -- constraint rather than trusting the two were edited together -- the defect
    -- STEP-21 paid for on `assets.kind`.
    --
    -- `awaiting_approval` is a first-class state rather than a boolean flag on
    -- `running`: a run waiting for a human is not running, and conflating them
    -- would make "how many runs are executing" unanswerable.
    status text NOT NULL DEFAULT 'pending'
        CONSTRAINT ck_workflow_runs_status_valid CHECK (status IN (
            'pending',
            'running',
            'awaiting_approval',
            'completed',
            'failed'
        )),

    -- The project this run acts on, when it acts on one. Nullable because not
    -- every workflow is project-scoped, and the composite FK below is what keeps
    -- a non-null value honest.
    project_id uuid,

    -- Why a run failed, or why it is waiting. Nullable, and null on a healthy
    -- run rather than an empty string -- the same reasoning as
    -- `projects.description`.
    detail text
        CONSTRAINT ck_workflow_runs_detail_length CHECK (char_length(detail) <= 2000),

    -- Who started it. Not an FK, matching `projects.created_by`: the record
    -- should outlive the account that triggered it.
    triggered_by uuid NOT NULL,

    started_at timestamptz,
    finished_at timestamptz,

    -- Exists solely so `workflow_step_runs` can reference the pair. `id` is
    -- already unique, so this constrains no data.
    CONSTRAINT uq_workflow_runs_id_workspace_id UNIQUE (id, workspace_id),

    -- A run naming a project must name one in its own workspace. The same
    -- composite-FK protection `assets` uses, for the same reason: `project_id`
    -- would otherwise be a claim the RLS policy cannot check.
    CONSTRAINT fk_workflow_runs_project_id_projects
        FOREIGN KEY (project_id, workspace_id)
        REFERENCES public.projects (id, workspace_id) ON DELETE RESTRICT
);
"""

_CREATE_WORKFLOW_STEP_RUNS = """
CREATE TABLE public.workflow_step_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    version integer NOT NULL DEFAULT 1,

    workspace_id uuid NOT NULL
        CONSTRAINT fk_workflow_step_runs_workspace_id_workspaces
        REFERENCES public.workspaces (id) ON DELETE RESTRICT,

    run_id uuid NOT NULL,

    -- Position in the definition's step sequence, zero-based. Stored rather than
    -- derived from `created_at`: two steps completing inside the same
    -- transaction would share a timestamp, and "which step came first" would
    -- then depend on an ordering PostgreSQL is free to vary.
    step_index integer NOT NULL
        CONSTRAINT ck_workflow_step_runs_index_non_negative CHECK (step_index >= 0),

    -- The step's name in the definition, denormalized so a run's history stays
    -- readable after the definition is edited. A run that executed a step called
    -- "plan" should keep saying so even if that step is later renamed.
    step_name text NOT NULL
        CONSTRAINT ck_workflow_step_runs_name_not_blank CHECK (btrim(step_name) <> '')
        CONSTRAINT ck_workflow_step_runs_name_length CHECK (char_length(step_name) <= 100),

    -- Matches `StepStatus` in `app/workflows/models.py`.
    status text NOT NULL DEFAULT 'pending'
        CONSTRAINT ck_workflow_step_runs_status_valid CHECK (status IN (
            'pending',
            'running',
            'awaiting_approval',
            'completed',
            'failed',
            'skipped'
        )),

    detail text
        CONSTRAINT ck_workflow_step_runs_detail_length CHECK (char_length(detail) <= 2000),

    -- What this step produced, so a later step can read it after a resume.
    --
    -- **This column is what makes resumption correct**, not merely possible. A
    -- run that pauses for approval resumes in a different request -- and a
    -- later step reading `StepContext.outputs` would find it empty, because
    -- outputs held only in memory do not survive the process. The planning
    -- agent hitting exactly that is how this was found: it resumed after
    -- approval and could not see the validation step's result.
    --
    -- `jsonb` rather than `text`: a step's output is structured (the validation
    -- step returns a mapping), and storing JSON as text would mean every reader
    -- parses it and one of them eventually parses it differently.
    --
    -- Nullable, because a step may legitimately produce nothing.
    output jsonb,

    started_at timestamptz,
    finished_at timestamptz,

    -- What this step consumed, so a run's cost is answerable from its own
    -- history rather than only from the global spend ledger. Zero for a step
    -- that made no AI call, which is honest rather than null: the step ran and
    -- spent nothing.
    tokens_used integer NOT NULL DEFAULT 0
        CONSTRAINT ck_workflow_step_runs_tokens_non_negative CHECK (tokens_used >= 0),

    -- One row per step per run. This is what makes "resume from the last
    -- completed step" a question with one answer -- see the module docstring.
    CONSTRAINT uq_workflow_step_runs_run_id_step_index UNIQUE (run_id, step_index),

    CONSTRAINT fk_workflow_step_runs_run_id_workflow_runs
        FOREIGN KEY (run_id, workspace_id)
        REFERENCES public.workflow_runs (id, workspace_id) ON DELETE RESTRICT
);
"""

# Partial on `deleted_at IS NULL` throughout: every query filters liveness (the
# filter is not in the policies), so an index excluding dead rows serves exactly
# the queries that exist.
_INDEXES = """
CREATE INDEX ix_workflow_runs_workspace_id
    ON public.workflow_runs (workspace_id)
    WHERE deleted_at IS NULL;

CREATE INDEX ix_workflow_runs_workspace_id_status
    ON public.workflow_runs (workspace_id, status)
    WHERE deleted_at IS NULL;

CREATE INDEX ix_workflow_runs_project_id
    ON public.workflow_runs (project_id)
    WHERE deleted_at IS NULL AND project_id IS NOT NULL;

CREATE INDEX ix_workflow_step_runs_run_id
    ON public.workflow_step_runs (run_id)
    WHERE deleted_at IS NULL;

CREATE INDEX ix_workflow_step_runs_workspace_id
    ON public.workflow_step_runs (workspace_id)
    WHERE deleted_at IS NULL;
"""

_ENABLE_RLS = """
ALTER TABLE public.workflow_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflow_runs FORCE ROW LEVEL SECURITY;
ALTER TABLE public.workflow_step_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workflow_step_runs FORCE ROW LEVEL SECURITY;
"""

# Per-command policies, never one FOR ALL.
#
# **No `deleted_at IS NULL` in either SELECT policy** -- both tables are
# soft-deleted by workspace erasure, and that filter would make the erasure
# impossible. See the module docstring.
#
# Any live member may read and write these, matching `projects`: a run is the
# record of work done on the workspace's shared content, and a member who cannot
# see what the platform did on their project cannot audit it. **Approval is
# gated at the API by `UPDATE_WORKSPACE`** (owner/admin, the project owner's
# decision on 2026-08-08) rather than by a policy -- the distinction is that RLS
# answers "whose rows", while approval is an *action* on a row the member can
# already see. Enforcing approval in a policy would mean a member's approval
# affected zero rows and returned success, which is the silent no-op
# `AuthorizationService` exists to turn into an honest 403.
_POLICIES = """
CREATE POLICY workflow_runs_select_same_workspace ON public.workflow_runs
FOR SELECT TO authenticated
USING (workspace_id IN (SELECT public.app_current_user_workspaces()));

CREATE POLICY workflow_runs_insert_member ON public.workflow_runs
FOR INSERT TO authenticated
WITH CHECK (workspace_id IN (SELECT public.app_current_user_workspaces()));

CREATE POLICY workflow_runs_update_member ON public.workflow_runs
FOR UPDATE TO authenticated
USING (workspace_id IN (SELECT public.app_current_user_workspaces()))
WITH CHECK (workspace_id IN (SELECT public.app_current_user_workspaces()));

CREATE POLICY workflow_step_runs_select_same_workspace ON public.workflow_step_runs
FOR SELECT TO authenticated
USING (workspace_id IN (SELECT public.app_current_user_workspaces()));

CREATE POLICY workflow_step_runs_insert_member ON public.workflow_step_runs
FOR INSERT TO authenticated
WITH CHECK (workspace_id IN (SELECT public.app_current_user_workspaces()));

CREATE POLICY workflow_step_runs_update_member ON public.workflow_step_runs
FOR UPDATE TO authenticated
USING (workspace_id IN (SELECT public.app_current_user_workspaces()))
WITH CHECK (workspace_id IN (SELECT public.app_current_user_workspaces()));
"""

# Stated explicitly rather than inherited from Supabase's corrected defaults --
# depending on a default for a security property is how the next platform change
# silently reopens it. No DELETE (soft deletion only) and no TRUNCATE (not
# subject to RLS at all).
_GRANTS = """
REVOKE ALL ON public.workflow_runs FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.workflow_runs TO authenticated;

REVOKE ALL ON public.workflow_step_runs FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.workflow_step_runs TO authenticated;
"""

_TRIGGERS = """
CREATE TRIGGER trg_workflow_runs_touch_row
BEFORE UPDATE ON public.workflow_runs
FOR EACH ROW
WHEN (OLD.* IS DISTINCT FROM NEW.*)
EXECUTE FUNCTION public.touch_row();

CREATE TRIGGER trg_workflow_step_runs_touch_row
BEFORE UPDATE ON public.workflow_step_runs
FOR EACH ROW
WHEN (OLD.* IS DISTINCT FROM NEW.*)
EXECUTE FUNCTION public.touch_row();
"""


def upgrade() -> None:
    """Create both tables with their RLS policies, grants, indexes and triggers."""
    op.execute(_CREATE_WORKFLOW_RUNS)
    op.execute(_CREATE_WORKFLOW_STEP_RUNS)
    op.execute(_INDEXES)
    op.execute(_ENABLE_RLS)
    op.execute(_POLICIES)
    op.execute(_GRANTS)
    op.execute(_TRIGGERS)


def downgrade() -> None:
    """Drop both tables.

    Dropping a table removes its policies, indexes, grants and triggers with it.

    `workflow_step_runs` first: it holds a foreign key to `workflow_runs`, and
    dropping the referenced table while a dependant survives is refused.

    Rolling this back **destroys every workflow run and its history in every
    workspace**. The runs are a record of what the platform did on users'
    behalf, so a production rollback of this revision discards an audit trail
    rather than merely a cache -- a decision rather than a routine operation.
    """
    op.execute("DROP TABLE IF EXISTS public.workflow_step_runs;")
    op.execute("DROP TABLE IF EXISTS public.workflow_runs;")
