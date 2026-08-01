"""Create the users, workspaces and workspace_members tables.

ProjectOne's two foundational tables, plus the membership table joining them.
This migration also establishes the column conventions every later table
inherits (CLAUDE.md §13), so the choices below are deliberate and are
documented in the vault under `05 Database/`:

- **`id uuid` defaulting to `gen_random_uuid()`.** Identifiers are generated
  without a round trip and never leak row counts or creation order the way a
  serial integer does. `gen_random_uuid()` is built into PostgreSQL 13+, so no
  extension dependency is introduced.
- **`created_at` / `updated_at` are `timestamptz`, never `timestamp`.** A
  timestamp without a zone is ambiguous the moment two regions write to it.
  `updated_at` is maintained by a trigger rather than by application code, so a
  migration, a psql session and the API cannot disagree about it.
- **`deleted_at timestamptz NULL` is the soft-deletion marker** (CLAUDE.md §13).
  A nullable timestamp rather than an `is_deleted` boolean because it records
  *when*, which the boolean cannot, and the boolean is derivable from it.
- **`version integer` is an optimistic-concurrency counter**, incremented by the
  same trigger as `updated_at`. It exists so a later read-modify-write endpoint
  can detect a lost update instead of silently overwriting one.

Membership is its own table, not a `workspace_id` column on `users`. A user
belongs to many workspaces and a workspace holds many users; collapsing that
into a single column would have to be undone by the first invite feature.

**RLS is deliberately NOT enabled here.** It is STEP-09, immediately next. Until
then these tables hold no data and no application code touches them.

Revision ID: 8a6f39b07c12
Revises: 4c310926e967
Create Date: 2026-08-01 10:31:18.300944

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "8a6f39b07c12"
down_revision: str | Sequence[str] | None = "4c310926e967"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Maintains `updated_at` and `version` in the database rather than in
# application code. Every path that writes a row -- the API, a migration, a
# psql session, a future background job -- gets the same behaviour, because
# there is only one implementation and it lives where the data does.
#
# `clock_timestamp()`, NOT `now()`. `now()` returns the *transaction* start
# time, so a row inserted and then updated inside one transaction would keep an
# `updated_at` identical to its `created_at` -- an updated_at that silently
# fails to advance is worse than none, because everything downstream trusts it.
# `clock_timestamp()` reads the actual wall clock at statement execution.
# (`created_at` keeps `now()` deliberately: rows written by one transaction
# should share a creation instant.)
#
# The WHEN clause on each trigger below keeps this from firing on no-op
# updates, so `UPDATE ... SET x = x` does not inflate the version counter.
_TOUCH_ROW_FUNCTION = """
CREATE OR REPLACE FUNCTION touch_row()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = clock_timestamp();
    NEW.version = OLD.version + 1;
    RETURN NEW;
END;
$$;
"""

_TABLES_WITH_TOUCH_TRIGGER = ("users", "workspaces", "workspace_members")


def _standard_columns() -> list[sa.Column]:  # type: ignore[type-arg]
    """Return the column set every ProjectOne table carries.

    Built fresh on each call because a SQLAlchemy `Column` object binds to the
    table it is first attached to and cannot be reused across tables.
    """
    return [
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
    ]


def upgrade() -> None:
    """Create the foundational tables, their constraints and their indexes."""
    op.execute(_TOUCH_ROW_FUNCTION)

    # users -- a profile keyed to Supabase Auth's identity.
    #
    # `id` holds the same value as `auth.users.id`. No foreign key to that
    # table: `auth` is owned and migrated by Supabase, and a cross-schema FK
    # would couple ProjectOne's migrations to a schema this project does not
    # control. STEP-10 owns how identity is linked and enforced.
    #
    # `email` is stored here as well, denormalized from `auth.users`, because
    # every listing screen ("who is in this workspace") would otherwise need to
    # join a schema the API's role may not be able to read. STEP-10 owns
    # keeping it in step with the authoritative copy.
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        *_standard_columns(),
        # citext would be the tidier answer, but it is an extension and this
        # constraint keeps the schema dependency-free. Rejecting rather than
        # silently lowercasing keeps the stored value exactly what was sent.
        sa.CheckConstraint("email = lower(email)", name="ck_users_email_lowercase"),
        sa.CheckConstraint(
            "length(email) BETWEEN 3 AND 320",
            name="ck_users_email_length",
        ),
        sa.CheckConstraint(
            "display_name IS NULL OR length(btrim(display_name)) > 0",
            name="ck_users_display_name_not_blank",
        ),
        sa.CheckConstraint("version >= 1", name="ck_users_version_positive"),
    )

    # Partial: a soft-deleted user must not block re-registration with the same
    # address, but two live users must never share one. A plain UNIQUE would
    # make deletion permanently reserve the address.
    op.create_index(
        "uq_users_email_active",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # workspaces -- the tenant boundary (CLAUDE.md §16). Every tenant-scoped
    # table from here on carries `workspace_id` and filters on it under RLS.
    op.create_table(
        "workspaces",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        # RESTRICT, not CASCADE: deleting a user must not silently destroy the
        # workspaces they own along with everyone else's work inside them.
        # Ownership transfer is a deliberate action, not a delete side effect.
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="RESTRICT",
                name="fk_workspaces_owner_id_users",
            ),
            nullable=False,
        ),
        *_standard_columns(),
        sa.CheckConstraint(
            "length(btrim(name)) BETWEEN 1 AND 120",
            name="ck_workspaces_name_length",
        ),
        sa.CheckConstraint("version >= 1", name="ck_workspaces_version_positive"),
    )

    # Access path: "list the workspaces this user owns" -- the dashboard's
    # first query. Not speculative (CLAUDE.md §13): an unindexed FK also makes
    # every users delete scan this table to enforce RESTRICT.
    op.create_index(
        "ix_workspaces_owner_id",
        "workspaces",
        ["owner_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # workspace_members -- the many-to-many join carrying the member's role.
    #
    # Role is text plus a CHECK rather than a PostgreSQL ENUM: adding a value
    # to an enum is easy, but removing or renaming one requires rewriting the
    # type, which is a locking operation on a live table. A CHECK constraint is
    # altered in one statement. STEP-11 owns what the roles actually permit;
    # this only fixes the vocabulary.
    op.create_table(
        "workspace_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # CASCADE here, unlike workspaces.owner_id: a membership row is
        # meaningless without both sides, and removing one is exactly what
        # should happen when either end goes away.
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "workspaces.id",
                ondelete="CASCADE",
                name="fk_workspace_members_workspace_id_workspaces",
            ),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="CASCADE",
                name="fk_workspace_members_user_id_users",
            ),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), nullable=False, server_default=sa.text("'member'")),
        *_standard_columns(),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'member')",
            name="ck_workspace_members_role_valid",
        ),
        sa.CheckConstraint("version >= 1", name="ck_workspace_members_version_positive"),
    )

    # Partial for the same reason as the users email index: removing someone
    # from a workspace must not permanently prevent re-inviting them.
    op.create_index(
        "uq_workspace_members_active",
        "workspace_members",
        ["workspace_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Access path: "which workspaces does this user belong to" -- runs on every
    # authenticated request once RLS lands in STEP-09. The reverse direction
    # ("who is in this workspace") is served by the unique index above, whose
    # leading column is workspace_id.
    op.create_index(
        "ix_workspace_members_user_id",
        "workspace_members",
        ["user_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    for table in _TABLES_WITH_TOUCH_TRIGGER:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_touch_row
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            WHEN (OLD.* IS DISTINCT FROM NEW.*)
            EXECUTE FUNCTION touch_row();
            """
        )


def downgrade() -> None:
    """Drop everything this migration created, in dependency order.

    Triggers fall with their tables, so they need no explicit drop. The
    function does, because it is schema-level and outlives them.
    """
    op.drop_table("workspace_members")
    op.drop_table("workspaces")
    op.drop_table("users")
    op.execute("DROP FUNCTION IF EXISTS touch_row();")
