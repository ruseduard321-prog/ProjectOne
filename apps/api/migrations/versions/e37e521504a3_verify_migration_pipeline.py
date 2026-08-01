"""Verify the migration pipeline.

Creates and drops a single throwaway table. It exists to prove the migration
pipeline works end to end — apply, record, roll back — before any real schema
depends on it. Verifying rollback now is the whole point: an untested downgrade
path is discovered during an incident, which is the worst possible time
(STEP-07).

This carries no application meaning and nothing may reference it. The first
real tables arrive with STEP-08.

Revision ID: e37e521504a3
Revises:
Create Date: 2026-08-01 00:09:52.685680

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e37e521504a3"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the throwaway verification table."""
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


def downgrade() -> None:
    """Drop it again, restoring the schema to empty."""
    op.drop_table("migration_pipeline_check")
