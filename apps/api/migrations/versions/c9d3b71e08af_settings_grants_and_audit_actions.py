"""Narrow the budget UPDATE grant to configuration, and audit the settings actions.

[[STEP-19 Settings and BYOK UI]] puts the first HTTP routes in front of the AI
layer. Two database changes are required before those routes are safe to expose,
and both close gaps that earlier steps recorded rather than resolved.

## 1. `spent_usd` becomes unwritable by a tenant

[[STEP-18 AI Cost Governance Controls]] left this stated exposure:

> An owner can currently zero their own `spent_usd`, because PostgreSQL policies
> are per-row and the UPDATE policy must exist for configuration.

That was correct and honest at the time -- STEP-18 exposed no route, so nobody
could reach the write. STEP-19 adds `PUT .../ai/budgets`, so the exposure stops
being theoretical: a request body is now the shortest path to the running total
that every spend ceiling is enforced against. A workspace that can zero it can
spend without limit while every control above continues to report success, which
is the worst shape a cost-control defect can take.

**RLS cannot close it.** A policy is evaluated per row and cannot say "these
columns only" -- both the AI Cost Governance note and the STEP-18 outcome reached
that conclusion independently. The mechanism that *can* is a column-level grant,
which PostgreSQL evaluates before any policy runs.

So the table-wide `UPDATE` grant is revoked and replaced by a grant on exactly
the two columns a settings screen configures:

    GRANT UPDATE (limit_usd, period_interval) ON public.ai_budgets TO authenticated;

`spent_usd`, `breaker_tripped_at` and `breaker_reason` are then unwritable over
the request connection **regardless of what any route accepts**. The request
schema (`BudgetUpdateRequest`) is still the first gate and still rejects the
field; this is the second, and it is the one that holds when a future route
forgets. Two independent mechanisms for one property, the standard this project
has applied since [[STEP-16a Developer Session Inspector]].

`updated_at` and `version` are maintained by the `touch_row` trigger, which runs
as the table owner rather than as the caller -- so narrowing the caller's grant
does not stop the trigger writing them. Verified rather than assumed: the
validation for this step performs a real UPDATE over the request connection and
confirms `version` still increments.

## 2. Storing and revoking a provider key becomes auditable

`ck_audit_log_action_valid` constrains `audit_log.action` to the five values
STEP-13 defined, so recording a BYOK change today would be refused by the
database. Storing a key that authorizes spend against a workspace's own provider
account, and revoking one, are exactly the consequential actions
[[Table - audit_log]] exists to record -- an unexplained provider key appearing in
a workspace is a security question somebody will need answered.

Three values are added. Budget changes are audited alongside them for the same
reason: raising a ceiling is a decision about money, and "who raised it" is the
first question asked after a surprising invoice.

The constraint is dropped and recreated rather than altered in place, which is
how PostgreSQL requires a CHECK to change. It is `NOT VALID`-free deliberately:
the table's existing rows all hold values from the previous list, which the new
list is a strict superset of, so the validating scan cannot fail. On a large
table that scan would be a lock worth avoiding; `audit_log` is young and this
runs in milliseconds.

## Expand/contract safety

Both changes are backward compatible with the currently-running code
(CLAUDE.md §13):

- Code deployed before this migration never writes `spent_usd` over the request
  connection -- no route existed that could -- so revoking the grant breaks
  nothing that was running.
- Widening a CHECK constraint's accepted set can only accept more, never less,
  so previously-valid writes stay valid.

Neither change requires the corresponding code deploy to be rolled back with it.

Revision ID: c9d3b71e08af
Revises: b2e6f0a71c94
Create Date: 2026-08-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c9d3b71e08af"
down_revision: str | Sequence[str] | None = "b2e6f0a71c94"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# --------------------------------------------------------------------------
# Column-level grant on ai_budgets
# --------------------------------------------------------------------------

# REVOKE first, then GRANT the narrower right. PostgreSQL treats a table-level
# UPDATE grant and a column-level one as independent: granting columns without
# revoking the table would leave the wider grant in place and change nothing.
_NARROW_BUDGET_UPDATE = """
REVOKE UPDATE ON public.ai_budgets FROM authenticated;
GRANT UPDATE (limit_usd, period_interval) ON public.ai_budgets TO authenticated;
"""

_WIDEN_BUDGET_UPDATE = """
REVOKE UPDATE (limit_usd, period_interval) ON public.ai_budgets FROM authenticated;
GRANT UPDATE ON public.ai_budgets TO authenticated;
"""


# --------------------------------------------------------------------------
# Audit action vocabulary
# --------------------------------------------------------------------------

_PREVIOUS_ACTIONS = (
    "'workspace.created'",
    "'member.added'",
    "'member.removed'",
    "'member.left'",
    "'ownership.transferred'",
)

_ADDED_ACTIONS = (
    "'provider_key.stored'",
    "'provider_key.revoked'",
    "'budget.updated'",
)


def _action_constraint(values: Sequence[str]) -> str:
    """Return SQL replacing the action CHECK with one accepting `values`."""
    accepted = ",\n            ".join(values)

    return f"""
ALTER TABLE public.audit_log
    DROP CONSTRAINT ck_audit_log_action_valid;

ALTER TABLE public.audit_log
    ADD CONSTRAINT ck_audit_log_action_valid CHECK (action IN (
            {accepted}
    ));
"""


def upgrade() -> None:
    """Narrow the budget grant and widen the audit vocabulary."""
    op.execute(_NARROW_BUDGET_UPDATE)
    op.execute(_action_constraint(_PREVIOUS_ACTIONS + _ADDED_ACTIONS))


def downgrade() -> None:
    """Restore the table-wide grant and the original audit vocabulary.

    The constraint narrows on the way down, so any row written with one of the
    three new actions would fail the recreated CHECK. That is the correct
    behaviour rather than a flaw: a downgrade that silently dropped audit rows to
    make itself succeed would destroy exactly the records the table exists to
    keep. An operator hitting this needs to decide what happens to those rows,
    which is a decision a migration must not make on their behalf.
    """
    op.execute(_action_constraint(_PREVIOUS_ACTIONS))
    op.execute(_WIDEN_BUDGET_UPDATE)
