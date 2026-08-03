"""Create the AI spend governance tables.

[[STEP-18 AI Cost Governance Controls]] implements CLAUDE.md §15a, which treats
AI provider spend as a production risk on the same tier as a security
vulnerability. This migration creates the three tables that enforcement stands
on, and the shape of each one is a decision rather than an obvious default.

## Why three tables and not one

They answer three different questions, at three different rates, with three
different lifetimes:

| Table | Question | Written |
|---|---|---|
| `ai_spend_records` | *What did we spend, on what?* | Once per call, append-only |
| `ai_budgets` | *Are we allowed to spend more?* | Read and updated on every call |
| `ai_shutdown_switches` | *Is spending disabled entirely?* | Rarely, in an incident |

Folding the ceiling into the ledger would mean answering "may this call proceed"
with `SELECT sum(cost) FROM ai_spend_records WHERE ...` on every request -- an
aggregate over a table that grows without bound, and, far worse, a **check that
races**. Two concurrent calls both read "under budget", both proceed, and the
ceiling is exceeded by design rather than by accident. `ai_budgets` holds a
running total that is compared and incremented in **one statement**, so
PostgreSQL's row lock settles the race instead of application logic that would
have to be right on every path.

## The reserve/settle pattern, and why the ledger cannot be the ceiling

A budget must be enforced *before* the call, and the cost of a call is not known
until after it returns. A ceiling checked afterwards is an invoice.

So spend is **reserved** at an estimated worst case before the call and
**settled** to the real figure afterwards, both against `ai_budgets.spent_usd`.
Between those two moments the workspace is charged more than it has actually
spent, which is the safe direction: a concurrent call sees the pessimistic
figure and is refused, rather than seeing an optimistic one and overshooting.

`ai_spend_records` is written only on settlement, from the provider's own
reported `TokenUsage`. It is the attribution and anomaly-detection source, and
it is deliberately **not** what the ceiling reads.

## Why the switches table exists rather than an environment variable

CLAUDE.md §15a requires a documented, fast path to disable AI spend for one
workspace, one workflow type, or the whole platform **without a code deploy**.
An environment variable fails that requirement in the way that matters: changing
it requires restarting every worker, which is a deploy in all but name and is
exactly the wrong operation to be performing during a cost incident.

A row in a table is read on the next call, in every worker, with no restart.

## The platform-wide switch is the one row that is not tenant data

`ai_shutdown_switches.workspace_id` is **nullable**, and a NULL means the switch
applies to the whole platform. That row belongs to no tenant, so it is
deliberately unreachable over the request connection: the SELECT policy matches
only workspace-scoped rows, and the platform row is read over the privileged
path (`AISpendRepository.platform_shutdown`). A tenant that could read it would
learn about a platform-wide incident; a tenant that could *write* it could
disable AI for every other customer.

Revision ID: b2e6f0a71c94
Revises: f1a4c8d29b57
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b2e6f0a71c94"
down_revision: str | Sequence[str] | None = "f1a4c8d29b57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# --------------------------------------------------------------------------
# The ledger
# --------------------------------------------------------------------------

_CREATE_SPEND_RECORDS = """
CREATE TABLE public.ai_spend_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,

    -- Required by `touch_row()`, which sets `NEW.version = OLD.version + 1`.
    -- A table carrying that trigger without this column fails on every UPDATE.
    version integer NOT NULL DEFAULT 1,

    workspace_id uuid NOT NULL
        CONSTRAINT fk_ai_spend_records_workspace_id_workspaces
        REFERENCES public.workspaces (id) ON DELETE RESTRICT,

    -- Which provider answered. Matches `PROVIDER_NAME` in each adapter. Not
    -- constrained to a fixed list here, unlike `provider_credentials.provider`:
    -- that column decides whether a key can ever be used, so a typo must fail
    -- loudly at write time. This one is a record of something that already
    -- happened, and refusing to record a completed call because a new provider
    -- was added without a migration would lose the spend rather than the typo.
    provider text NOT NULL,

    -- The specific model, which the provider chose if the caller did not. Kept
    -- separate from `provider` because cost varies by model far more than by
    -- vendor, and an anomaly is usually a model change rather than a vendor one.
    model text NOT NULL,

    -- What incurred the spend. CLAUDE.md §15a requires a ceiling per workflow
    -- type as well as per workspace, so this is the dimension that one is keyed
    -- on -- see `ai_budgets.workflow_type`.
    workflow_type text NOT NULL,

    -- Reported by the provider, never estimated. `TokenUsage` is already
    -- normalised across vendors (STEP-17), which is why this needs no
    -- per-provider accounting.
    prompt_tokens integer NOT NULL
        CONSTRAINT ck_ai_spend_records_prompt_tokens_nonnegative CHECK (prompt_tokens >= 0),
    completion_tokens integer NOT NULL
        CONSTRAINT ck_ai_spend_records_completion_tokens_nonnegative
        CHECK (completion_tokens >= 0),

    -- `numeric`, never a float. Money in binary floating point accumulates
    -- error, and a budget ceiling compared against an accumulated float is a
    -- ceiling that drifts. 12 digits with 6 after the point holds a single
    -- call's fraction-of-a-cent cost and a large lifetime total alike.
    cost_usd numeric(12, 6) NOT NULL
        CONSTRAINT ck_ai_spend_records_cost_nonnegative CHECK (cost_usd >= 0),

    -- Who triggered it. Not an FK, for the same reason `audit_log.actor_id` is
    -- not: the record should outlive the account that caused it.
    actor_id uuid
);
"""

# Both indexes carry `deleted_at IS NULL` to match the SELECT policy's predicate,
# so a policy-filtered query stays index-served (Table Conventions).
#
# The workspace+created_at index is what anomaly detection reads: it compares a
# recent window against a baseline window, which is a range scan per workspace.
_SPEND_RECORD_INDEXES = """
CREATE INDEX ix_ai_spend_records_workspace_created
    ON public.ai_spend_records (workspace_id, created_at DESC)
    WHERE deleted_at IS NULL;

CREATE INDEX ix_ai_spend_records_workspace_workflow
    ON public.ai_spend_records (workspace_id, workflow_type)
    WHERE deleted_at IS NULL;
"""


# --------------------------------------------------------------------------
# The ceilings
# --------------------------------------------------------------------------

_CREATE_BUDGETS = """
CREATE TABLE public.ai_budgets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    version integer NOT NULL DEFAULT 1,

    workspace_id uuid NOT NULL
        CONSTRAINT fk_ai_budgets_workspace_id_workspaces
        REFERENCES public.workspaces (id) ON DELETE RESTRICT,

    -- NULL means "this budget covers the whole workspace, every workflow".
    -- A non-NULL value scopes it to one workflow type.
    --
    -- CLAUDE.md §15a requires both ceilings, and they are enforced as a
    -- conjunction rather than a choice: a call must pass the workspace budget
    -- AND its workflow budget, so neither can be used to escape the other.
    -- Modelling both in one table rather than two keeps that check one query.
    workflow_type text,

    -- The ceiling. NOT NULL: a budget row with no limit is a row that means
    -- nothing, and "no row" already expresses "no configured ceiling".
    limit_usd numeric(12, 6) NOT NULL
        CONSTRAINT ck_ai_budgets_limit_positive CHECK (limit_usd > 0),

    -- The running total, compared and incremented in one statement. This is the
    -- column that makes the ceiling race-free -- see the module docstring.
    spent_usd numeric(12, 6) NOT NULL DEFAULT 0
        CONSTRAINT ck_ai_budgets_spent_nonnegative CHECK (spent_usd >= 0),

    -- When the running total was last reset to zero. A budget is per-period,
    -- and without this the ceiling would be a lifetime cap that every workspace
    -- eventually hits and never recovers from.
    period_started_at timestamptz NOT NULL DEFAULT now(),

    -- How long a period lasts. Interval rather than a hardcoded month so a
    -- workflow-type ceiling can be daily while a workspace ceiling is monthly,
    -- which is the usual shape: the workspace cap is the bill, the workflow cap
    -- is the runaway detector.
    period_interval interval NOT NULL DEFAULT '30 days',

    -- A per-budget kill switch distinct from the shutdown table below. This one
    -- is the *spend circuit breaker* CLAUDE.md §15a requires as a mechanism
    -- separate from the availability breaker: it trips automatically on
    -- anomalous spend and stops calls rather than rerouting them.
    breaker_tripped_at timestamptz,
    breaker_reason text
);
"""

# One budget row per workspace per scope. Partial on `deleted_at IS NULL` so a
# removed budget does not block configuring a new one.
#
# Two indexes, not one: PostgreSQL treats NULLs as distinct in a unique index, so
# a single index on (workspace_id, workflow_type) would permit unlimited rows
# with a NULL workflow_type -- exactly the workspace-wide budget that must be
# unique. `NULLS NOT DISTINCT` would solve it on PostgreSQL 15+, but two explicit
# partial indexes say what is meant without depending on that version behaviour.
_BUDGET_INDEXES = """
CREATE UNIQUE INDEX uq_ai_budgets_workspace_workflow_live
    ON public.ai_budgets (workspace_id, workflow_type)
    WHERE deleted_at IS NULL AND workflow_type IS NOT NULL;

CREATE UNIQUE INDEX uq_ai_budgets_workspace_default_live
    ON public.ai_budgets (workspace_id)
    WHERE deleted_at IS NULL AND workflow_type IS NULL;
"""


# --------------------------------------------------------------------------
# Emergency shutdown
# --------------------------------------------------------------------------

_CREATE_SHUTDOWN = """
CREATE TABLE public.ai_shutdown_switches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    version integer NOT NULL DEFAULT 1,

    -- NULL means PLATFORM-WIDE. The one row in this schema that is not tenant
    -- data, and the reason the SELECT policy below cannot simply route through
    -- `app_current_user_workspaces()` -- see the module docstring.
    workspace_id uuid
        CONSTRAINT fk_ai_shutdown_switches_workspace_id_workspaces
        REFERENCES public.workspaces (id) ON DELETE RESTRICT,

    -- NULL means "every workflow type in this scope".
    workflow_type text,

    -- Why it was disabled. NOT NULL because a kill switch with no stated reason
    -- is one nobody can safely decide to turn off again.
    reason text NOT NULL,

    -- Who threw it. Nullable: a switch thrown by an automated anomaly response
    -- has no human actor, and recording a fake one would be worse than a NULL.
    activated_by uuid
);
"""

_SHUTDOWN_INDEXES = """
CREATE INDEX ix_ai_shutdown_switches_workspace
    ON public.ai_shutdown_switches (workspace_id)
    WHERE deleted_at IS NULL;

-- The platform-wide switch is read on every AI call, so it gets its own index
-- rather than scanning. Partial and tiny: at most a handful of live rows.
CREATE INDEX ix_ai_shutdown_switches_platform
    ON public.ai_shutdown_switches (workflow_type)
    WHERE deleted_at IS NULL AND workspace_id IS NULL;
"""


# --------------------------------------------------------------------------
# RLS -- ENABLE and FORCE, every table (RLS Policy Pattern)
# --------------------------------------------------------------------------

_ENABLE_RLS = """
ALTER TABLE public.ai_spend_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_spend_records FORCE ROW LEVEL SECURITY;

ALTER TABLE public.ai_budgets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_budgets FORCE ROW LEVEL SECURITY;

ALTER TABLE public.ai_shutdown_switches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_shutdown_switches FORCE ROW LEVEL SECURITY;
"""

# Per-command policies, never one FOR ALL (RLS Policy Pattern).
#
# ## `ai_spend_records` has no INSERT policy, by design
#
# Same reasoning as `audit_log`: a client able to write its own spend records
# could forge them, and a forged spend record is worse than a missing one --
# a workspace could write a negative-looking history, or flood the ledger to
# poison its own anomaly baseline. Records are written on the privileged path by
# `AISpendRepository.record`, which is the audited-service-path shape CLAUDE.md
# §16 requires for operations RLS deliberately forbids.
#
# No UPDATE policy either: the ledger is append-only. A spend record describes
# something that already happened and cannot un-happen.
_SPEND_RECORD_POLICIES = """
CREATE POLICY ai_spend_records_select_same_workspace ON public.ai_spend_records
FOR SELECT TO authenticated
USING (
    deleted_at IS NULL
    AND workspace_id IN (SELECT public.app_current_user_workspaces())
);
"""

# ## `ai_budgets`: members read, owners and admins write
#
# The same asymmetry as `provider_credentials`, for the same reason. Every member
# needs to *read* the budget -- a tripped ceiling has to be explainable to the
# person whose request was refused -- while changing a spend limit is a
# billing-adjacent decision belonging to the roles that already control them.
#
# `spent_usd` is deliberately reachable by neither: it is maintained on the
# privileged path during reserve/settle, so a workspace cannot grant itself more
# budget by rewriting its own running total. The UPDATE policy exists for
# configuration (`limit_usd`, `period_interval`) via a route STEP-19 will add.
_BUDGET_POLICIES = """
CREATE POLICY ai_budgets_select_same_workspace ON public.ai_budgets
FOR SELECT TO authenticated
USING (
    deleted_at IS NULL
    AND workspace_id IN (SELECT public.app_current_user_workspaces())
);

CREATE POLICY ai_budgets_insert_privileged ON public.ai_budgets
FOR INSERT TO authenticated
WITH CHECK (
    workspace_id IN (SELECT public.app_current_user_workspaces_as(ARRAY['owner','admin']))
);

CREATE POLICY ai_budgets_update_privileged ON public.ai_budgets
FOR UPDATE TO authenticated
USING (
    deleted_at IS NULL
    AND workspace_id IN (SELECT public.app_current_user_workspaces_as(ARRAY['owner','admin']))
)
WITH CHECK (
    workspace_id IN (SELECT public.app_current_user_workspaces_as(ARRAY['owner','admin']))
);
"""

# ## `ai_shutdown_switches`: the platform row is invisible to every tenant
#
# `workspace_id IS NOT NULL` is load-bearing in all three policies, and it is the
# one place this schema departs from the standard one-line tenant predicate.
#
# Without it on SELECT, `workspace_id IN (SELECT ...)` would already exclude the
# platform row -- NULL IN (...) is NULL, not true -- so the extra clause is
# redundant *there*. It is stated anyway because relying on NULL comparison
# semantics for a security boundary is the kind of correctness that survives
# until someone rewrites the predicate in a way that looks equivalent.
#
# On INSERT it is genuinely load-bearing: without it, a WITH CHECK evaluating to
# NULL would... also refuse. But an admin inserting `workspace_id = NULL` must be
# refused *explicitly*, because that row would disable AI for every customer on
# the platform.
_SHUTDOWN_POLICIES = """
CREATE POLICY ai_shutdown_switches_select_same_workspace ON public.ai_shutdown_switches
FOR SELECT TO authenticated
USING (
    deleted_at IS NULL
    AND workspace_id IS NOT NULL
    AND workspace_id IN (SELECT public.app_current_user_workspaces())
);

CREATE POLICY ai_shutdown_switches_insert_privileged ON public.ai_shutdown_switches
FOR INSERT TO authenticated
WITH CHECK (
    workspace_id IS NOT NULL
    AND workspace_id IN (SELECT public.app_current_user_workspaces_as(ARRAY['owner','admin']))
);

CREATE POLICY ai_shutdown_switches_update_privileged ON public.ai_shutdown_switches
FOR UPDATE TO authenticated
USING (
    deleted_at IS NULL
    AND workspace_id IS NOT NULL
    AND workspace_id IN (SELECT public.app_current_user_workspaces_as(ARRAY['owner','admin']))
)
WITH CHECK (
    workspace_id IS NOT NULL
    AND workspace_id IN (SELECT public.app_current_user_workspaces_as(ARRAY['owner','admin']))
);
"""

# Grants are an independent gate from policies, stated explicitly rather than
# inherited (RLS Policy Pattern). No DELETE, no TRUNCATE -- TRUNCATE especially,
# which is not subject to RLS at all and would let a holder empty the spend
# ledger regardless of every policy above.
#
# `ai_spend_records` gets SELECT only: it has no INSERT or UPDATE policy, so
# granting either would be surface with nothing behind it.
_GRANTS = """
REVOKE ALL ON public.ai_spend_records FROM anon, authenticated;
GRANT SELECT ON public.ai_spend_records TO authenticated;

REVOKE ALL ON public.ai_budgets FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.ai_budgets TO authenticated;

REVOKE ALL ON public.ai_shutdown_switches FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.ai_shutdown_switches TO authenticated;
"""

# `touch_row` maintains `updated_at` and `version` (established by `8a6f39b07c12`).
# The WHEN clause matches every existing trigger: without it, `UPDATE ... SET x = x`
# inflates the version counter on a no-op.
#
# `ai_spend_records` gets no trigger: it is append-only, so there is no UPDATE for
# one to fire on.
_TRIGGERS = """
CREATE TRIGGER trg_ai_budgets_touch_row
BEFORE UPDATE ON public.ai_budgets
FOR EACH ROW
WHEN (OLD.* IS DISTINCT FROM NEW.*)
EXECUTE FUNCTION public.touch_row();

CREATE TRIGGER trg_ai_shutdown_switches_touch_row
BEFORE UPDATE ON public.ai_shutdown_switches
FOR EACH ROW
WHEN (OLD.* IS DISTINCT FROM NEW.*)
EXECUTE FUNCTION public.touch_row();
"""


def upgrade() -> None:
    """Create the spend ledger, the budget ceilings and the shutdown switches."""
    op.execute(_CREATE_SPEND_RECORDS)
    op.execute(_SPEND_RECORD_INDEXES)
    op.execute(_CREATE_BUDGETS)
    op.execute(_BUDGET_INDEXES)
    op.execute(_CREATE_SHUTDOWN)
    op.execute(_SHUTDOWN_INDEXES)
    op.execute(_ENABLE_RLS)
    op.execute(_SPEND_RECORD_POLICIES)
    op.execute(_BUDGET_POLICIES)
    op.execute(_SHUTDOWN_POLICIES)
    op.execute(_GRANTS)
    op.execute(_TRIGGERS)


def downgrade() -> None:
    """Drop the governance tables.

    Dropping each table removes its policies, indexes, grants and triggers with
    it; they are not dropped individually.

    **Rolling this back removes every spend ceiling.** The code that enforces
    them fails closed when the tables are absent (`AISpendRepository` raises
    rather than returning "no limit"), so a rollback disables AI calls rather
    than uncapping them -- which is the correct direction for a control whose
    absence costs money.
    """
    op.execute("DROP TABLE IF EXISTS public.ai_shutdown_switches;")
    op.execute("DROP TABLE IF EXISTS public.ai_budgets;")
    op.execute("DROP TABLE IF EXISTS public.ai_spend_records;")
