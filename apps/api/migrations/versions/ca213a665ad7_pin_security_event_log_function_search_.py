"""Pin `search_path` on the security event log's immutability trigger.

`b2e94c17a5d3` created `public.security_event_log_forbid_update()` without
`SET search_path = ''`. It is one of **two** functions in this schema that omit
it — `touch_row()` is the other, and is deliberately out of scope here for the
reason recorded at the end of this docstring. The remaining seven all carry it.

The omission is an oversight rather than a decision: [[RLS Policy Pattern]]
already requires it of invoker triggers in as many words — "Keep
`SET search_path = ''` regardless" — and `app_jobs_queue_state_not_client_writable()`,
the other `SECURITY INVOKER` trigger function, carries it. Supabase's advisor
reports the gap as `function_search_path_mutable`.

## What this is worth, stated honestly

Nothing is exploitable today, and the reason is worth writing down rather than
asserting. The function is `SECURITY INVOKER`, so it holds no elevated rights to
redirect in the first place; and its body resolves **no schema object at all** —
a single `RAISE EXCEPTION` with a literal message and a literal errcode. There
is no unqualified name for a hostile `search_path` to capture.

What this buys is the next edit. A trigger body that grows one unqualified
reference — a lookup table, a helper, an operator from a non-default schema —
acquires the vulnerability silently, and nothing in the suite would have noticed:
before this change, no test asserted `search_path` on any of the nine functions
in this schema. `test_the_trigger_function_pins_its_search_path` is the durable
half of the fix.

## Why `ALTER FUNCTION` rather than `CREATE OR REPLACE FUNCTION`

`CREATE OR REPLACE` would restate the whole body to change one setting, and
restating a body is how it drifts. `ALTER FUNCTION ... SET` writes `proconfig`
and nothing else. Verified against a real database before this was written:
body, owner, volatility, parallel safety, `prosecdef`, the trigger binding and
the existing EXECUTE grants are all identical either side of the statement, and
`trg_security_event_log_forbid_update` goes on refusing updates unchanged.

`touch_row()` carries the same advisor warning and is deliberately **not**
included here — 13 triggers across 13 tables is a different change with a
different blast radius, and the project owner scoped it out as its own task.

Revision ID: ca213a665ad7
Revises: 7b4360bcefed
Create Date: 2026-08-19 13:07:30.837625

"""

from collections.abc import Sequence

from alembic import op

revision: str = "ca213a665ad7"
down_revision: str | Sequence[str] | None = "7b4360bcefed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Only `proconfig` is written. Nothing about the body, the owner, the grants or
# the trigger binding is restated, so nothing about them can drift here.
_PIN_SEARCH_PATH = """
ALTER FUNCTION public.security_event_log_forbid_update()
SET search_path = '';
"""


def upgrade() -> None:
    """Pin the trigger function's `search_path`, changing nothing else.

    Idempotent: re-running writes the same `proconfig` value and does not raise.
    """
    op.execute(_PIN_SEARCH_PATH)


def downgrade() -> None:
    """Deliberately do nothing, rather than restore a reported warning.

    **Asymmetric by the project owner's explicit decision of 2026-08-19**, and
    recorded here rather than left to be inferred from an empty body.

    A faithful restoration was available and would have worked: `ALTER FUNCTION
    ... RESET search_path` returns `proconfig` to NULL, which is exactly the
    pre-migration state — verified against a real database by comparing the full
    `pg_proc` row either side, not assumed. It is not used. The owner's rule is
    that a downgrade must never move the database back into a state Supabase has
    already reported, and `function_search_path_mutable` is such a state.

    Rollback-safety — the property `database-engineer` check 5 actually protects
    — is unaffected either way. Nothing depends on the `search_path` of this
    function being mutable: the body resolves no schema object, so it behaves
    identically pinned or not, and no application code calls it at all. Only
    `trg_security_event_log_forbid_update` invokes it, and that is unchanged.
    Downgrading past this revision therefore breaks no previous version of the
    application.

    `scripts/migration_cycle_drill.py` (FA-02) compares functions as
    `routine_name, data_type` and does not read `proconfig`, so it is blind to
    this setting in either direction and neither forces nor forbids the choice.
    The decision rests on the owner's rule above, not on the drill.

    Downgrading below `b2e94c17a5d3` drops the function outright, which makes
    this revision's effect moot at that point regardless.
    """
