"""Request-scoped database sessions that are actually subject to RLS.

This module is the load-bearing piece of ProjectOne's multi-tenancy. STEP-09 put
eight RLS policies on the tenant tables, but a policy only runs for a role that
is subject to it — and `postgres` (what `DATABASE_URL` connects as) carries
`rolbypassrls`, so PostgreSQL skips policies for it entirely. An API querying
tenant tables over that connection would read every workspace's rows while every
isolation test still passed, because those tests connect as `authenticated`.

Two connections therefore exist, and the split is deliberate:

| Connection | Role | Subject to RLS | Used for |
|---|---|---|---|
| `DATABASE_URL` | `postgres` | **No** — `rolbypassrls` | Alembic migrations only |
| `REQUEST_DATABASE_URL` | `projectone_api` | **Yes** | Every request |

`projectone_api` is created by migration `d7b95c1f4e08`, which documents why it
exists rather than Supabase's `authenticator` (reserved, and unalterable by
`postgres` on managed Supabase). Two of its attributes carry the weight, both
verified in `pg_roles` rather than assumed:

- **`rolbypassrls = false`** — policies apply to it, which is the entire point.
- **`rolinherit = false`** — it is granted `authenticated` but holds none of its
  privileges until it explicitly `SET ROLE`s. A request path that skipped the
  role switch would therefore read **nothing** rather than everything: the bug
  fails closed.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import psycopg

from app.core.config import Settings

# The role every request runs as. The STEP-09 policies are written
# `TO authenticated`, so a session in any other role matches no policy.
_REQUEST_ROLE = "authenticated"

# The session variable `auth.uid()` reads (RLS Policy Pattern).
_CLAIM_SETTING = "request.jwt.claim.sub"


class RequestSessionFactory:
    """Opens database sessions that carry a caller's identity into RLS."""

    def __init__(self, settings: Settings) -> None:
        """Store the settings holding the request-path connection string."""
        self._settings = settings

    @contextmanager
    def authenticated_as(self, user_id: uuid.UUID) -> Iterator[psycopg.Connection]:
        """Yield a connection scoped to one user, inside one transaction.

        Everything that makes this safe happens in a **transaction**, not on the
        connection:

        - `SET LOCAL ROLE authenticated` switches off the bypass.
        - `set_config(..., is_local => true)` sets the JWT claim.

        Both revert when the transaction ends — on commit *and* on rollback,
        verified against the live database during STEP-10. That is what makes
        connection reuse safe. The session-scoped forms (`SET ROLE`,
        `set_config(..., false)`) look equivalent and are a cross-tenant breach
        waiting to happen: the claim outlives the request and the next caller to
        borrow that pooled connection inherits the previous caller's identity.
        That exact leak was reproduced during STEP-10 before this was written —
        a session that had "no claim" read another user's workspace.

        `set_config` rather than `SET LOCAL`: `SET` does not accept bind
        parameters, so a user id could only reach it through string
        interpolation. `set_config` takes it as a parameter, which keeps a value
        that ultimately comes from a token out of the SQL text entirely.

        Args:
            user_id: The verified `sub` claim. Must come from
                `TokenService.verify`, never from client-supplied input.

        Yields:
            A connection whose queries are subject to the RLS policies, seeing
            only what this user is entitled to see.
        """
        with psycopg.connect(
            self._settings.request_database_url.get_secret_value(),
            connect_timeout=self._settings.database_health_timeout_seconds,
        ) as connection:
            with connection.transaction(), connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {_REQUEST_ROLE}")
                cursor.execute(
                    "SELECT set_config(%s, %s, true)",
                    (_CLAIM_SETTING, str(user_id)),
                )

                yield connection
