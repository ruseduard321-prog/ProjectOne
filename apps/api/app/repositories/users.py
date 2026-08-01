"""Profile row access for `public.users`.

Two connections appear here for two different reasons, and the distinction is
the whole design:

- **Provisioning** (`ensure_profile`) runs over the **privileged** connection.
  It has to: `users` has no INSERT policy at all, so no client-side role can
  create a profile row. This is the audited service path CLAUDE.md §16 requires
  for the one operation RLS deliberately forbids — not a convenience bypass.
- **Reading** (`read_visible_profiles`) runs over the **request** connection, as
  `authenticated`, subject to every policy. Anything a request can reach goes
  through that path.

Provisioning is confined to sign-up and email reconciliation. Widening it to
ordinary reads or writes would re-open the bypass STEP-09 closed.
"""

import uuid
from dataclasses import dataclass

import psycopg

from app.core.config import Settings


@dataclass(frozen=True)
class UserProfile:
    """A row of `public.users`."""

    id: uuid.UUID
    email: str
    display_name: str | None


class UserRepository:
    """Reads and provisions `public.users` rows."""

    def __init__(self, settings: Settings) -> None:
        """Store the settings holding both connection strings."""
        self._settings = settings

    def ensure_profile(self, user_id: uuid.UUID, email: str) -> UserProfile:
        """Create or reconcile the profile row for an authenticated identity.

        This is where the `auth.users` ↔ `public.users` link is established.
        STEP-08 left `users.id` holding the same value as `auth.users.id` with
        **no foreign key** between them, because `auth` is owned and migrated by
        Supabase and a cross-schema FK would couple ProjectOne's migration
        history to a schema it does not control (Table - users). The link is
        therefore a convention, and this method is what enforces it.

        **Why an application-side upsert and not a trigger on `auth.users`.**
        A trigger would be automatic and would fire even for identities created
        outside this API — genuinely attractive. It was rejected because it
        requires creating a trigger *on a Supabase-owned table in a
        Supabase-owned schema*: exactly the coupling the missing FK exists to
        avoid, and unversioned by Alembic, so the link would live somewhere the
        migration history cannot see and code review cannot reach. An upsert
        here is visible, testable, and rolls back with the code that ships it.

        The trade-off is stated plainly rather than hidden: an identity created
        directly in the Supabase dashboard gets no profile row until it first
        authenticates through this API. `ON CONFLICT` makes that self-healing —
        the row appears on first authenticated request — instead of a permanent
        inconsistency.

        `email` is also reconciled here, which is the second thing STEP-08 left
        to this step. The token's address is authoritative; the `users` copy is
        a denormalization, so when a user changes their address upstream this
        brings the copy back in step on their next request rather than letting
        the two silently diverge.

        Args:
            user_id: The verified `sub` claim.
            email: The address from the token — authoritative.

        Returns:
            The profile row as it now stands.
        """
        with (
            psycopg.connect(
                self._settings.database_url.get_secret_value(),
                connect_timeout=self._settings.database_health_timeout_seconds,
            ) as connection,
            connection.cursor() as cursor,
        ):
            cursor.execute(
                """
                INSERT INTO public.users (id, email)
                VALUES (%s, %s)
                ON CONFLICT (id) DO UPDATE
                    SET email = EXCLUDED.email
                    -- Only touch the row when the address actually changed.
                    -- Without this, every authenticated request would write,
                    -- bumping `version` and `updated_at` via the STEP-08
                    -- trigger and making optimistic concurrency meaningless.
                    WHERE public.users.email IS DISTINCT FROM EXCLUDED.email
                RETURNING id, email, display_name
                """,
                (user_id, email.lower()),
            )

            row = cursor.fetchone()

            if row is None:
                # DO UPDATE ... WHERE that matches nothing returns no row, which
                # is the common case: the profile exists and the email is
                # unchanged. Read it back rather than reporting a failure.
                cursor.execute(
                    "SELECT id, email, display_name FROM public.users WHERE id = %s",
                    (user_id,),
                )
                row = cursor.fetchone()

            if row is None:
                raise RuntimeError(f"Profile row for {user_id} could not be provisioned")

            return UserProfile(id=row[0], email=row[1], display_name=row[2])

    @staticmethod
    def read_visible_profiles(connection: psycopg.Connection) -> list[UserProfile]:
        """Return every user row the caller's session is permitted to see.

        Takes an already-authenticated connection rather than opening one, so
        the caller cannot accidentally invoke this over the privileged
        connection — the session's identity is the connection's, and this
        function has no way to widen it.

        What comes back is decided entirely by `users_select_self_or_co_member`:
        the caller, plus anyone sharing a live workspace with them.
        """
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, email, display_name FROM public.users ORDER BY email")
            return [UserProfile(id=row[0], email=row[1], display_name=row[2]) for row in cursor]
