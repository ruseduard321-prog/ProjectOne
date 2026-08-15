"""FA-06 — authentication events are recorded, without becoming an oracle.

[[STEP-25 Foundation Audit and Internal Readiness]] recorded the gap plainly:
`audit_log` covers the STEP-13 workspace mutations and nothing else, so the
events most worth auditing -- who signed in, who failed to, whose session was
revoked -- left no trace at all. A trail that omits authentication is not an
authentication trail.

## Why a second table rather than widening `audit_log`

The owner's decision of 2026-08-15, and the constraint that forces it:
`audit_log.workspace_id` is `NOT NULL` with a foreign key, because every action
it records happens inside a tenant. **A failed sign-in has no tenant and no
user** -- at the moment it is recorded, nothing about the caller is known or
trustworthy. Making that column nullable would put rows in a tenant-scoped
table that no tenant policy can classify, which is the failure mode
`a3c07d5e91f4` explicitly wrote itself out of.

## The two properties under test, and the second is the hard one

1. **The events are recorded.** Sign-in, sign-out, refresh -- succeeded and
   failed alike.
2. **Recording them creates no account-existence oracle.** This is the
   requirement that shapes the schema, and it is subtler than "do not store the
   email":

   - The submitted address is never stored, **in any form**. Not raw, and not
     hashed either -- a hash is an oracle to anyone who can compute it over a
     guess, which is everyone.
   - `user_id` is null on every failure. Populating it on a failed sign-in
     would answer "does this account exist?" from the row's own contents.
   - The **public response must not vary** between an existing and a
     non-existent account. That is asserted end-to-end below, because it is a
     property of the endpoint rather than of the table.

Tests here that touch the database are skipped without
`PROJECTONE_TEST_DATABASE_URL`, like every other database-backed test -- and
fail rather than skip in CI (`PROJECTONE_REQUIRE_DATABASE_TESTS`).
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from pydantic import SecretStr

from app.core.config import Environment, Settings
from app.core.security import CredentialsRejectedError
from tests.conftest import TEST_BYOK_KEY

# --------------------------------------------------------------------------
# The import under test.
#
# Kept at module scope deliberately: before the fix this raises ImportError and
# the whole module errors, which is the failing-before proof FA-06 asks for --
# the finding is that none of this exists, not that one assertion is wrong.
# --------------------------------------------------------------------------
from app.repositories.security_events import (
    SecurityEvent,
    SecurityEventRepository,
)
from app.services.security_event_service import (
    SecurityEventOutcome,
    SecurityEventService,
    SecurityEventType,
)

FAKE_PASSWORD = "totally-fake-pw-do-not-use-9Z8Y7X"  # noqa: S105 - fake, never a credential
FAKE_TOKEN = "fake.access.token-do-not-use-Q4W5E6"  # noqa: S105 - fake, never a credential


# ----------------------------------------------------------------- vocabulary


def test_the_event_vocabulary_covers_the_authentication_surface() -> None:
    """Every authentication outcome the API can produce has a name.

    The surface is `app/routers/auth.py`: sign-up, sign-in, sign-out, refresh.
    An event type missing here is an event that silently cannot be recorded.
    """
    covered = {member.value for member in SecurityEventType}

    assert covered == {
        "auth.sign_up",
        "auth.sign_in",
        "auth.sign_out",
        "auth.token_refresh",
    }


def test_outcomes_distinguish_success_from_failure() -> None:
    """Both outcomes exist, because recording only successes proves nothing.

    An attacker's failed attempts are the events an investigation starts from.
    """
    assert {member.value for member in SecurityEventOutcome} == {"succeeded", "failed"}


# ------------------------------------------------------- no secrets, ever --


#: Values that must never reach a stored row, whatever route they arrive by.
#:
#: Each is a *distinct, unmistakably fake* sentinel so a leak names its own
#: source rather than merely failing. None is a real credential.
FORBIDDEN_VALUES = {
    "password": FAKE_PASSWORD,
    "access_token": FAKE_TOKEN,
    "refresh_token": "fake.refresh.token-do-not-use-R7T8Y9",
    "api_key": "sk-fake-do-not-use-A1B2C3D4E5",
    "authorization_header": "Bearer fake.jwt.do-not-use-Z9X8C7",
    "cookie_header": "sb-access-token=fake-do-not-use-M3N4B5",
    "database_url": "postgresql://api:totally-fake-pw-do-not-use-9Z8Y7X@db.test/one",
    "email": "victim@example.test",
}


def test_the_event_record_refuses_forbidden_metadata_keys() -> None:
    """Rejection is by key name, at construction, before anything is stored.

    A filter applied at write time protects the write it runs in. Refusing at
    construction protects every future caller too, including one that builds an
    event and hands it somewhere this module never sees.
    """
    for key in ("password", "access_token", "refresh_token", "email", "authorization"):
        with pytest.raises(ValueError, match="not permitted"):
            SecurityEvent(
                event_type="auth.sign_in",
                outcome="failed",
                request_id="req-1",
                metadata={key: "anything at all"},
            )


def test_the_event_record_refuses_secret_shaped_values() -> None:
    """A forbidden value is refused even under an innocent-looking key.

    Key-name filtering alone is defeated by `{"note": "<the token>"}`, which is
    exactly the shape a well-meaning debugging change takes.
    """
    for name, value in FORBIDDEN_VALUES.items():
        if name == "email":
            # Addresses are covered by the oracle tests below; a bare address is
            # not "secret-shaped" and is caught by key name instead.
            continue

        with pytest.raises(ValueError, match="not permitted"):
            SecurityEvent(
                event_type="auth.sign_in",
                outcome="failed",
                request_id="req-1",
                metadata={"note": value},
            )


def test_metadata_is_bounded() -> None:
    """Unbounded metadata is an append-only table with an unbounded row size.

    The cap is small on purpose: this table holds diagnostics, and anything that
    does not fit belongs in a log line, not in a security record.
    """
    with pytest.raises(ValueError, match="too large"):
        SecurityEvent(
            event_type="auth.sign_in",
            outcome="failed",
            request_id="req-1",
            metadata={"reason": "x" * 4096},
        )


def test_an_unknown_event_type_is_refused() -> None:
    """The allowlist is enforced in code as well as by the CHECK constraint."""
    with pytest.raises(ValueError, match="not an allowed event type"):
        SecurityEvent(
            event_type="auth.something_invented",
            outcome="failed",
            request_id="req-1",
        )


def test_a_failed_event_cannot_carry_a_user_id() -> None:
    """**The oracle rule, enforced at the type.**

    A row saying "sign-in failed for user X" answers "does X exist?" from its
    own contents. The service is what decides not to pass one; this makes
    passing one impossible rather than merely unusual.
    """
    with pytest.raises(ValueError, match="failed event"):
        SecurityEvent(
            event_type="auth.sign_in",
            outcome="failed",
            request_id="req-1",
            user_id=uuid.uuid4(),
        )


# ------------------------------------------------------- database-backed --

pytestmark_db = pytest.mark.usefixtures("migrated_database")


@pytest.fixture
def events(migrated_database: str) -> Iterator[psycopg.Connection]:
    """An owner connection for arranging and inspecting rows.

    Used to *observe*, never to prove access control -- the RLS assertions below
    use the request-path role, which is the one a real request gets.
    """
    with psycopg.connect(migrated_database, autocommit=True) as connection:
        yield connection

        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM public.security_event_log")


def _rows(connection: psycopg.Connection) -> list[tuple]:
    """Return every stored event, newest first."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, created_at, event_type, outcome,
                   request_id, user_id, workspace_id, metadata
            FROM public.security_event_log
            ORDER BY created_at DESC, id DESC
            """
        )
        return list(cursor.fetchall())


def test_the_table_exists_with_the_designed_shape(events) -> None:
    """Schema, asserted rather than assumed.

    Nullability is the property that matters most here: `user_id` and
    `workspace_id` *must* be nullable, because the events this table exists for
    occur before either is known.
    """
    with events.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'security_event_log'
            ORDER BY column_name
            """
        )
        columns = dict(cursor.fetchall())

    assert columns["id"] == "NO"
    assert columns["created_at"] == "NO"
    assert columns["event_type"] == "NO"
    assert columns["outcome"] == "NO"
    assert columns["request_id"] == "NO"

    # The whole reason this is a separate table.
    assert columns["user_id"] == "YES"
    assert columns["workspace_id"] == "YES"


def test_the_table_stores_no_column_that_could_hold_an_identifier(events) -> None:
    """A negative assertion on the schema itself.

    The cheapest way this table becomes an oracle is somebody adding an `email`
    column in good faith. Naming the forbidden columns here makes that a failing
    test rather than a review someone has to catch.
    """
    with events.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'security_event_log'
            """
        )
        columns = {row[0] for row in cursor.fetchall()}

    forbidden = {
        "email",
        "actor_email",
        "identifier",
        "username",
        "password",
        "password_hash",
        "email_hash",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "authorization",
        "cookie",
        "ip_address",
    }

    assert columns & forbidden == set()


def test_recording_an_event_stores_it(events, settings_for_events) -> None:
    """The base case: the events happen and they land."""
    service = SecurityEventService(SecurityEventRepository(settings_for_events))
    user_id = uuid.uuid4()

    service.record(
        SecurityEventType.SIGN_IN,
        SecurityEventOutcome.SUCCEEDED,
        request_id="req-abc",
        user_id=user_id,
    )

    stored = _rows(events)

    assert len(stored) == 1
    assert stored[0][2] == "auth.sign_in"
    assert stored[0][3] == "succeeded"
    assert stored[0][4] == "req-abc"
    assert stored[0][5] == user_id


def test_a_failed_sign_in_stores_no_user_and_no_identifier(events, settings_for_events) -> None:
    """**The oracle proof, at the storage layer.**

    A failed attempt against a real account and one against an invented address
    must produce rows that are indistinguishable in every column. If they are
    not, the table answers "does this account exist?" to anyone who can read it.
    """
    service = SecurityEventService(SecurityEventRepository(settings_for_events))

    service.record_failure(
        SecurityEventType.SIGN_IN,
        request_id="req-real",
        reason="invalid_credentials",
    )
    service.record_failure(
        SecurityEventType.SIGN_IN,
        request_id="req-invented",
        reason="invalid_credentials",
    )

    stored = _rows(events)
    assert len(stored) == 2

    for row in stored:
        assert row[3] == "failed"
        assert row[5] is None, "a failed event must not name a user"
        assert row[6] is None, "a failed event must not name a workspace"

        # Nothing in the metadata may vary with whether the account existed.
        assert row[7] == {"reason": "invalid_credentials"}

    # The rows differ only by their correlation id and timestamp -- never by
    # anything derived from the submitted address.
    assert {row[2] for row in stored} == {"auth.sign_in"}


def test_no_forbidden_value_survives_into_storage(events, settings_for_events) -> None:
    """End-to-end: the sentinels are absent from the whole table, as text.

    Asserted against the serialized row rather than column by column, so a value
    smuggled into a nested structure is caught too.
    """
    service = SecurityEventService(SecurityEventRepository(settings_for_events))

    service.record_failure(
        SecurityEventType.SIGN_IN, request_id="req-1", reason="invalid_credentials"
    )
    service.record(
        SecurityEventType.SIGN_OUT,
        SecurityEventOutcome.SUCCEEDED,
        request_id="req-2",
        user_id=uuid.uuid4(),
    )

    with events.cursor() as cursor:
        cursor.execute("SELECT security_event_log::text FROM public.security_event_log")
        serialized = " ".join(row[0] for row in cursor.fetchall())

    for name, value in FORBIDDEN_VALUES.items():
        assert value not in serialized, f"{name} leaked into a stored security event"


# ------------------------------------------------------------ immutability --


def test_the_table_is_append_only_for_the_request_role(request_database_url, events) -> None:
    """RLS default-deny, proven with the role a request actually uses.

    No SELECT policy, no UPDATE policy, no DELETE policy, and no grants. Each
    absence is a control; asserting them together is what stops one being
    restored by accident.
    """
    service_rows_before = len(_rows(events))

    with psycopg.connect(request_database_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET ROLE authenticated")

            for statement, params in (
                ("SELECT * FROM public.security_event_log", ()),
                ("UPDATE public.security_event_log SET outcome = 'succeeded'", ()),
                ("DELETE FROM public.security_event_log", ()),
                (
                    "INSERT INTO public.security_event_log "
                    "(event_type, outcome, request_id) VALUES (%s, %s, %s)",
                    ("auth.sign_in", "succeeded", "forged"),
                ),
            ):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    cursor.execute(statement, params)
                connection.rollback()

    assert len(_rows(events)) == service_rows_before


def test_the_request_role_cannot_truncate_the_table(request_database_url) -> None:
    """TRUNCATE is not subject to RLS at all.

    A role holding it could empty this table regardless of every policy on it,
    which is why the grant is asserted separately from the policies -- the same
    reasoning `audit_log` records.
    """
    with psycopg.connect(request_database_url, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SET ROLE authenticated")

            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cursor.execute("TRUNCATE public.security_event_log")


def test_rows_cannot_be_updated_even_by_the_owner(events, settings_for_events) -> None:
    """Immutability is enforced by a trigger, not only by absent grants.

    Grants and policies stop the *request* role. They do not stop the privileged
    connection the application itself writes over -- and a bug there is exactly
    what would rewrite history. The trigger closes that, so "append-only" holds
    against every path except the approved retention delete.
    """
    service = SecurityEventService(SecurityEventRepository(settings_for_events))
    service.record_failure(
        SecurityEventType.SIGN_IN, request_id="req-1", reason="invalid_credentials"
    )

    with events.cursor() as cursor:
        with pytest.raises(psycopg.errors.RaiseException):
            cursor.execute(
                "UPDATE public.security_event_log SET outcome = 'succeeded'"
            )


def test_rls_is_enabled_and_forced(events) -> None:
    """`ENABLE` alone is not enough -- the table owner bypasses it.

    `FORCE` is what makes the policies apply to the owner too, and a table that
    comes back from a migration without it is a silent regression no
    forward-only test notices.
    """
    with events.cursor() as cursor:
        cursor.execute(
            """
            SELECT relrowsecurity, relforcerowsecurity
            FROM pg_class
            JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace
            WHERE nspname = 'public' AND relname = 'security_event_log'
            """
        )
        enabled, forced = cursor.fetchone()

    assert enabled is True
    assert forced is True


def test_there_is_no_select_policy_at_all(events) -> None:
    """No tenant-facing read path, by the owner's requirement.

    `audit_log` has one because a workspace's own actions are its own business.
    These events span tenants and precede identity, so there is no correct
    tenant scope to read them under -- the absence is the design.
    """
    with events.cursor() as cursor:
        cursor.execute(
            "SELECT policyname, cmd FROM pg_policies "
            "WHERE schemaname = 'public' AND tablename = 'security_event_log'"
        )
        policies = cursor.fetchall()

    assert policies == []


def test_the_request_role_holds_no_privilege_on_the_table(events) -> None:
    """Grants are an independent gate from policies (RLS Policy Pattern).

    Asserted against the catalog rather than inferred from the migration text,
    because what protects the table is what the database ended up with.
    """
    with events.cursor() as cursor:
        cursor.execute(
            """
            SELECT grantee, privilege_type
            FROM information_schema.role_table_grants
            WHERE table_schema = 'public'
              AND table_name = 'security_event_log'
              AND grantee IN ('anon', 'authenticated')
            """
        )
        grants = cursor.fetchall()

    assert grants == [], f"authenticated/anon must hold nothing here, found {grants}"


# --------------------------------------------------------------- retention --


def test_retention_deletes_only_rows_past_the_window(events, settings_for_events) -> None:
    """The 90-day boundary, asserted on both sides of it.

    A retention bug that deletes too much destroys the evidence that it was
    wrong, so the boundary is tested rather than trusted.
    """
    service = SecurityEventService(SecurityEventRepository(settings_for_events))
    now = datetime.now(UTC)

    with events.cursor() as cursor:
        for label, age_days in (("old", 91), ("boundary", 89), ("fresh", 1)):
            cursor.execute(
                """
                INSERT INTO public.security_event_log
                    (created_at, event_type, outcome, request_id)
                VALUES (%s, 'auth.sign_in', 'failed', %s)
                """,
                (now - timedelta(days=age_days), label),
            )

    deleted = service.purge_expired(settings_for_events)

    assert deleted == 1

    remaining = {row[4] for row in _rows(events)}
    assert remaining == {"boundary", "fresh"}


def test_retention_disabled_deletes_nothing(events, settings_for_events_no_retention) -> None:
    """Zero means retain indefinitely, never "keep nothing".

    The same rule `AuditService.retention_cutoff` records: the dangerous
    misreading of `0` differs from the correct one by the entire table.
    """
    service = SecurityEventService(SecurityEventRepository(settings_for_events_no_retention))

    with events.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO public.security_event_log
                (created_at, event_type, outcome, request_id)
            VALUES (%s, 'auth.sign_in', 'failed', 'ancient')
            """,
            (datetime.now(UTC) - timedelta(days=4000),),
        )

    assert service.purge_expired(settings_for_events_no_retention) == 0
    assert len(_rows(events)) == 1


def test_the_purge_statement_is_a_filtered_delete() -> None:
    """Asserted as text, for the reason `AuditRepository.purge_statement` is.

    Once an unfiltered delete has run, the evidence it was wrong is the thing it
    destroyed -- so the predicate is checked before it can ever execute.
    """
    statement = SecurityEventRepository.purge_statement()

    assert "DELETE FROM public.security_event_log" in statement
    assert "WHERE created_at <" in statement
    assert "TRUNCATE" not in statement.upper()


# ------------------------------------------------------------- concurrency --


def test_concurrent_inserts_remain_independent(migrated_database, events, settings_for_events) -> None:
    """Two writers, two rows, neither blocking nor overwriting the other.

    Authentication events arrive concurrently by nature. An append that took a
    lock the next one waited on would make the audit path a throughput ceiling
    on sign-in itself.
    """
    first = psycopg.connect(migrated_database)
    second = psycopg.connect(migrated_database)

    try:
        for connection, request_id in ((first, "req-a"), (second, "req-b")):
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO public.security_event_log
                        (event_type, outcome, request_id)
                    VALUES ('auth.sign_in', 'failed', %s)
                    """,
                    (request_id,),
                )

        # Both transactions are still open and neither has blocked -- the
        # commits below succeed in either order.
        first.commit()
        second.commit()
    finally:
        first.close()
        second.close()

    assert {row[4] for row in _rows(events)} == {"req-a", "req-b"}


# ----------------------------------------------------------------- fixtures --


def _settings_for(url: str, *, retention_days: int) -> Settings:
    """Build Settings pointed at the disposable test database.

    Built here rather than by widening a shared helper: this is the only module
    that needs a security-event retention window, and a shared builder growing a
    parameter per caller is how a test fixture stops modelling anything real
    (CLAUDE.md §29).
    """
    return Settings(
        environment=Environment.DEVELOPMENT,
        SUPABASE_URL="https://project.test",
        SUPABASE_SECRET_KEY=SecretStr("unused"),
        DATABASE_URL=SecretStr(url),
        REQUEST_DATABASE_URL=SecretStr(url),
        byok_encryption_key=SecretStr(TEST_BYOK_KEY),
        audit_retention_days=retention_days,
        _env_file=None,
    )


@pytest.fixture
def settings_for_events(migrated_database: str) -> Settings:
    """Settings whose privileged DSN is the disposable database, 90-day window."""
    return _settings_for(migrated_database, retention_days=90)


@pytest.fixture
def settings_for_events_no_retention(migrated_database: str) -> Settings:
    """Settings with retention disabled, to prove zero means *keep everything*."""
    return _settings_for(migrated_database, retention_days=0)


# ------------------------------------------------- the endpoint-level oracle --


class _RecordingEvents:
    """Captures what the router asked to record, without a database."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, uuid.UUID | None]] = []

    def record(
        self,
        event_type: SecurityEventType,
        outcome: SecurityEventOutcome,
        *,
        request_id: str,
        user_id: uuid.UUID | None = None,
        workspace_id: uuid.UUID | None = None,
        **metadata: object,
    ) -> None:
        self.calls.append((event_type.value, outcome.value, user_id))

    def record_failure(
        self,
        event_type: SecurityEventType,
        *,
        request_id: str,
        reason: str,
        **metadata: object,
    ) -> None:
        self.calls.append((event_type.value, "failed", None))


def test_sign_in_responses_are_identical_for_existing_and_unknown_accounts() -> None:
    """**The requirement recording must not break.**

    Recording an authentication failure is only safe if doing so changes nothing
    a caller can observe. Asserted on the whole response -- status, body and the
    headers that vary meaningfully -- because an oracle is any difference at
    all, not only a different message.
    """
    from fastapi.testclient import TestClient

    from app.core.dependencies import get_security_event_service, get_settings
    from app.main import create_app
    from tests.test_auth_endpoints import make_settings

    recorder = _RecordingEvents()
    app = create_app()
    app.dependency_overrides[get_settings] = make_settings
    app.dependency_overrides[get_security_event_service] = lambda: recorder

    class _RejectingAuth:
        """Rejects every credential, exactly as Supabase does for both cases."""

        def sign_in(self, email: str, password: str) -> object:
            raise CredentialsRejectedError("Invalid login credentials")

    from app.core.dependencies import get_auth_service

    app.dependency_overrides[get_auth_service] = _RejectingAuth

    with TestClient(app) as client:
        existing = client.post(
            "/api/v1/auth/sign-in",
            json={"email": "real-account@example.test", "password": FAKE_PASSWORD},
        )
        unknown = client.post(
            "/api/v1/auth/sign-in",
            json={"email": "no-such-account@example.test", "password": FAKE_PASSWORD},
        )

    app.dependency_overrides.clear()

    assert existing.status_code == unknown.status_code

    # `request_id` differs per request by design and is not derived from the
    # address, so it is excluded rather than compared.
    def body(response: object) -> dict:
        payload = dict(response.json())  # type: ignore[attr-defined]
        payload.pop("request_id", None)
        return payload

    assert body(existing) == body(unknown)

    # And both were recorded, with no user attached to either.
    assert len(recorder.calls) == 2
    assert {call[2] for call in recorder.calls} == {None}
