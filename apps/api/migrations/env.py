"""Alembic migration environment.

Reads the database URL from the application's validated settings rather than
from `alembic.ini`, so that:

- no connection string is ever committed (CLAUDE.md §16), and
- migrations and the running application cannot disagree about which database
  they target — both resolve `DATABASE_URL` through the same `Settings` object.

ProjectOne has no ORM and no SQLAlchemy models. `target_metadata` is therefore
`None` and autogenerate is deliberately unavailable: migrations here are
hand-written SQL, reviewed like any other code. Adopting an ORM later is an ADR
decision, not a quiet change to this file.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _sqlalchemy_url() -> str:
    """Return DATABASE_URL in the form SQLAlchemy needs.

    `DATABASE_URL` is stored in the plain `postgresql://` form that Supabase,
    psql and every other tool expects, so it stays copy-pasteable. SQLAlchemy
    reads that bare scheme as "use psycopg2", which is not the driver installed
    here — ProjectOne uses psycopg 3. The `+psycopg` suffix selects it.

    Normalizing here rather than in `.env` keeps the driver choice an
    implementation detail of this file instead of a trap for whoever next
    copies a connection string out of the Supabase dashboard.
    """
    url = get_settings().database_url.get_secret_value()

    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)

    return url


# Injected at runtime from the validated environment. set_main_option escapes
# the value for configparser, which matters because passwords routinely contain
# characters ("%" especially) that would otherwise be interpolated.
config.set_main_option("sqlalchemy.url", _sqlalchemy_url())

# No ORM models — see the module docstring.
target_metadata = None


def run_migrations_offline() -> None:
    """Emit migration SQL without connecting to a database.

    Used to review exactly what a migration would do (`alembic upgrade head
    --sql`) before it touches anything real.
    """
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live database.

    Each migration runs inside a transaction, so a failure part-way through
    rolls back rather than leaving the schema half-applied.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
