"""Database connectivity checks.

The repository layer owns data access: services ask questions, repositories
know how to reach the database (CLAUDE.md §12, Backend Architecture). Keeping
the driver here means swapping or pooling it later touches one file.

This module holds only the connectivity probe. Real query repositories arrive
with the first tables in STEP-08.
"""

import psycopg

from app.core.config import Settings


class DatabaseRepository:
    """Reaches the PostgreSQL database."""

    def __init__(self, settings: Settings) -> None:
        """Store the settings holding the connection string."""
        self._settings = settings

    def is_reachable(self) -> bool:
        """Return whether the database answers a trivial query.

        `SELECT 1` rather than merely opening a socket: a connection can be
        established to a port that is listening but unable to serve, and a
        health check that reports "up" in that state is worse than none.

        Exceptions are deliberately swallowed and reduced to a boolean. A
        health endpoint reports status; it must never surface a driver error
        containing the connection string — which holds the password
        (CLAUDE.md §16, §24).
        """
        try:
            with (
                psycopg.connect(
                    self._settings.database_url.get_secret_value(),
                    connect_timeout=self._settings.database_health_timeout_seconds,
                ) as connection,
                connection.cursor() as cursor,
            ):
                cursor.execute("SELECT 1")
                return cursor.fetchone() is not None
        except psycopg.Error:
            return False
