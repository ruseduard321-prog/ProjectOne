"""Make a chat message genuinely immutable, not merely documented as one.

`a7d24e91f3b6` created `messages` with `messages_soft_delete_member`, whose
`WITH CHECK (deleted_at IS NOT NULL)` was described there as making a transcript
immutable. **It does not**, and this revision is the correction.

## What the policy actually guaranteed

A `WITH CHECK` constrains the row an UPDATE *produces*. That clause constrains
exactly one column of it. A single statement setting `content` **and**
`deleted_at` therefore satisfies the policy completely:

    UPDATE public.messages SET content = 'rewritten', deleted_at = now() ...

The policy permitted rewriting history as long as the rewrite also deleted it.
The test guarding immutability updated `content` *alone* -- which the policy
genuinely does refuse, because the resulting row has a null `deleted_at` -- so it
passed while testing the one variation that was never the risk.

Confirmed against the live development database before this was written: the
statement above succeeded and the stored content changed.

## Why this is a trigger and not a better policy

There is no better policy. RLS shows a policy only the candidate row, never the
row being replaced, so "content must equal what it was" is not expressible: it is
a claim about `OLD` and `NEW` together. A `BEFORE UPDATE` trigger is what
PostgreSQL provides for that comparison, and `app_protect_last_owner` on
`workspace_members` already uses one for an invariant of the same shape.

Policy and trigger are both required and neither subsumes the other. The policy
bounds *who* may update and *what kind of row* results; the trigger bounds *what
may change*.

## Why a separate revision rather than an amendment

`a7d24e91f3b6` had already been applied to the shared development database when
this hole was found. Amending it in place would have left every already-migrated
environment permanently defective while every freshly-built schema was correct,
with nothing recording the divergence -- the failure mode [[CLAUDE|CLAUDE.md]]
§13's expand/contract rule exists to prevent. A new revision reaches both.

This migration is additive and rollback-safe: it adds a constraint that no
existing *correct* write violates. The only writes it refuses are ones that were
never supposed to succeed.

## The permitted set is a whitelist

Three columns may change: `deleted_at`, written by the soft delete itself, and
`updated_at` / `version`, maintained by `touch_row`. Everything else is refused.

Stated as a whitelist rather than a blacklist deliberately -- a column added to
`messages` later is then immutable by default, and making it mutable becomes a
decision someone has to write down here. A blacklist would silently admit every
column added after today, which is how this class of guard rots.

Revision ID: b4e8c02d71fa
Revises: a7d24e91f3b6
Create Date: 2026-08-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b4e8c02d71fa"
down_revision: str | Sequence[str] | None = "a7d24e91f3b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# `SECURITY DEFINER` with `SET search_path = ''` for the same escalation reason
# as `app_protect_last_owner`: a trigger function runs with the table owner's
# rights, so an attacker-controlled `search_path` must not be able to redirect
# any name it resolves. Every reference below is schema-qualified or a column.
_FUNCTION = """
CREATE OR REPLACE FUNCTION public.app_messages_immutable()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.workspace_id IS DISTINCT FROM OLD.workspace_id
       OR NEW.conversation_id IS DISTINCT FROM OLD.conversation_id
       OR NEW.role IS DISTINCT FROM OLD.role
       OR NEW.content IS DISTINCT FROM OLD.content
       OR NEW.provider IS DISTINCT FROM OLD.provider
       OR NEW.model IS DISTINCT FROM OLD.model
       OR NEW.token_count IS DISTINCT FROM OLD.token_count
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
    THEN
        -- 23514 (check_violation), matching `app_protect_last_owner`. This is an
        -- integrity rule rather than a permission one: the caller may well hold
        -- every privilege the statement needs, and the answer is still no.
        RAISE EXCEPTION 'message % is immutable', OLD.id
            USING ERRCODE = '23514',
                  HINT = 'A message may only be soft-deleted, never edited.';
    END IF;

    RETURN NEW;
END;
$$;
"""

# Named `app_messages_immutable` rather than `trg_...` for a reason that matters:
# BEFORE triggers fire in **alphabetical order by name**, and a modified NEW from
# an earlier trigger is what later ones see. `app_...` sorts before
# `trg_messages_touch_row`, so this compares the row the *caller* submitted
# rather than one `touch_row` has already advanced two columns of -- which would
# make `updated_at` and `version` appear changed on every legitimate soft delete.
_TRIGGER = """
CREATE TRIGGER app_messages_immutable
BEFORE UPDATE ON public.messages
FOR EACH ROW
EXECUTE FUNCTION public.app_messages_immutable();
"""


def upgrade() -> None:
    """Add the immutability guard to `messages`."""
    op.execute(_FUNCTION)
    op.execute(_TRIGGER)


def downgrade() -> None:
    """Remove the guard, restoring the defect this revision exists to close.

    Worth being explicit about: rolling this back does not merely remove a
    constraint, it makes stored messages editable again. That is the correct
    behaviour for a downgrade -- it must return the schema to what the previous
    revision described -- but it is not a neutral operation.
    """
    op.execute("DROP TRIGGER IF EXISTS app_messages_immutable ON public.messages;")
    op.execute("DROP FUNCTION IF EXISTS public.app_messages_immutable();")
