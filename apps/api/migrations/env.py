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
    # `disable_existing_loggers=False` is load-bearing, and the default (True)
    # is actively wrong here.
    #
    # `fileConfig` otherwise sets `.disabled = True` on every logger not named
    # in `alembic.ini` -- which is every application logger. Standalone that is
    # harmless, because the process exits when the migration does. Under pytest
    # it is not: the session-scoped `migrated_database` fixture runs migrations
    # in-process, so from the first database test onward every `app.*` logger is
    # silenced for the remainder of the run.
    #
    # That is what made the request-logging assertions fail on CI while passing
    # locally -- locally the database tests skip, so this never executes.
    # Confirmed by reproduction: before the call `app.core.middleware.disabled`
    # is False, after it is True.
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def _as_psycopg_url(url: str) -> str:
    """Return a connection string in the form SQLAlchemy needs.

    Connection strings are stored in the plain `postgresql://` form that
    Supabase, psql and every other tool expects, so they stay copy-pasteable.
    SQLAlchemy reads that bare scheme as "use psycopg2", which is not the driver
    installed here — ProjectOne uses psycopg 3. The `+psycopg` suffix selects it.

    Normalizing here rather than in `.env` keeps the driver choice an
    implementation detail of this file instead of a trap for whoever next copies
    a connection string out of the Supabase dashboard.
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)

    return url


# An explicitly supplied URL wins over the environment's `DATABASE_URL`.
#
# **This override is what stops a test run migrating the development database.**
# The test harness sets `sqlalchemy.url` on its Config before calling
# `command.upgrade` precisely so migrations land on the throwaway database
# (`tests/conftest.py`). Overwriting it unconditionally — which this file did
# until STEP-11 — silently discarded that, and every migration a test run
# applied went to whatever `DATABASE_URL` pointed at instead.
#
# It went unnoticed because CI's `DATABASE_URL` *is* the throwaway container, so
# the two agreed there. On a developer machine they do not, and the result is a
# test run migrating the development project. Found during STEP-11 validation,
# against a real database rather than by reading.
#
# `set_main_option` escapes the value for configparser, which matters because
# passwords routinely contain characters ("%" especially) that would otherwise
# be interpolated.
_explicit_url = config.get_main_option("sqlalchemy.url")

if _explicit_url:
    config.set_main_option("sqlalchemy.url", _as_psycopg_url(_explicit_url))
else:
    config.set_main_option(
        "sqlalchemy.url",
        _as_psycopg_url(get_settings().database_url.get_secret_value()),
    )

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
