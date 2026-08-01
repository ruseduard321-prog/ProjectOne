"""Drop the migration pipeline verification table.

`migration_pipeline_check` was STEP-07's throwaway table, created only to prove
the migration pipeline applies, records and rolls back. It carries no
application meaning and nothing references it, so it must not survive into a
schema that holds real tables.

This is a separate migration rather than an edit to `e37e521504a3` on purpose:
migration history is append-only. Editing an applied migration means the file
in the repository no longer describes what ran against any database that
already applied it.

Revision ID: 4c310926e967
Revises: e37e521504a3
Create Date: 2026-08-01 10:31:11.793579

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4c310926e967"
down_revision: str | Sequence[str] | None = "e37e521504a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove the verification table."""
    op.drop_table("migration_pipeline_check")


def downgrade() -> None:
    """Recreate it, identically to `e37e521504a3`.

    Rebuilt column for column so that downgrading leaves the database in the
    exact state the previous revision produced. A downgrade that only
    approximately restores the prior schema is worse than none, because it
    fails at the point the next upgrade assumes what it left behind.
    """
    op.create_table(
        "migration_pipeline_check",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
