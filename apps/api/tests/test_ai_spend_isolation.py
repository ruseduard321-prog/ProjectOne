"""Tenant isolation and atomicity for the spend governance tables, against a real database.

These cover exactly the two properties `tests/fakes.py` cannot, and says so:

1. **RLS actually isolates the spend tables.** A fake proving "our in-memory dict
   returned nothing" says nothing about whether a policy holds. These connect as
   `authenticated` with a JWT claim set, exactly as a request does.
2. **`try_reserve` is atomic under concurrency.** The compare-and-increment is the
   single mechanism standing between a budget ceiling and a TOCTOU race, and it
   is PostgreSQL's row lock doing the work -- which a single-threaded fake cannot
   demonstrate.

**Which database.** `PROJECTONE_TEST_DATABASE_URL`, never `DATABASE_URL`. These
create and destroy rows, so pointing them at the development Supabase project
would make running the suite destructive. Skipped when the variable is absent;
CI sets it, so the coverage is not quietly lost there.
"""

from __future__ import annotations

import datetime as dt
import threading
import uuid
from decimal import Decimal

import psycopg
import pytest

from app.repositories.ai_spend import AISpendRepository
from tests.conftest import Identity, seed_identity


@pytest.fixture
def spend_repository(migrated_database: str) -> AISpendRepository:
    """Return a repository pointed at the throwaway database.

    Constructed with a minimal settings stand-in rather than real `Settings`, so
    the suite needs no environment beyond the test database URL.
    """

    class _Settings:
        database_url = _Secret(migrated_database)
        database_health_timeout_seconds = 10

    return AISpendRepository(_Settings())  # type: ignore[arg-type]


class _Secret:
    """Minimal `SecretStr` stand-in exposing only what the repository calls."""

    def __init__(self, value: str) -> None:
        self._value = value

    def get_secret_value(self) -> str:
        """Return the wrapped connection string."""
        return self._value


def as_user(url: str, user_id: uuid.UUID) -> psycopg.Connection:
    """Open a connection acting as one authenticated user.

    `SET ROLE` plus the JWT claim, exactly as `RequestSessionFactory` does on a
    real request -- so what these tests exercise is the policy a request meets.
    """
    connection = psycopg.connect(url)

    with connection.cursor() as cursor:
        cursor.execute("SET ROLE authenticated")
        cursor.execute("SELECT set_config('request.jwt.claim.sub', %s, false)", (str(user_id),))

    return connection


@pytest.fixture
def two_tenants(admin_connection: psycopg.Connection) -> tuple[Identity, Identity]:
    """Seed two unrelated workspaces."""
    return seed_identity(admin_connection, "spend-a"), seed_identity(admin_connection, "spend-b")


def seed_spend(
    connection: psycopg.Connection,
    workspace_id: uuid.UUID,
    cost: Decimal = Decimal("1.00"),
) -> None:
    """Insert a spend record over the owner connection.

    The owner, deliberately: `ai_spend_records` has no INSERT policy and
    `authenticated` holds no INSERT grant, so a client genuinely cannot create
    one -- which is the property `test_a_tenant_cannot_forge_a_spend_record`
    asserts.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.ai_spend_records "
            "(workspace_id, provider, model, workflow_type, "
            " prompt_tokens, completion_tokens, cost_usd) "
            "VALUES (%s, 'openai', 'gpt-4o-mini', 'chat', 10, 20, %s)",
            (workspace_id, cost),
        )


class TestSpendRecordIsolation:
    """One workspace's spend ledger is invisible to another."""

    def test_a_tenant_reads_its_own_spend_records(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        alice, _ = two_tenants
        seed_spend(admin_connection, alice.workspace_id)

        with as_user(request_database_url, alice.user_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM public.ai_spend_records WHERE workspace_id = %s",
                    (alice.workspace_id,),
                )
                count = cursor.fetchone()

        assert count is not None
        assert count[0] == 1

    def test_a_tenant_cannot_read_another_workspaces_spend(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        """Spend history is commercially sensitive: it reveals usage volume."""
        alice, bob = two_tenants
        seed_spend(admin_connection, bob.workspace_id)

        with as_user(request_database_url, alice.user_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM public.ai_spend_records WHERE workspace_id = %s",
                    (bob.workspace_id,),
                )
                count = cursor.fetchone()

        assert count is not None
        assert count[0] == 0

    def test_a_tenant_cannot_forge_a_spend_record(
        self,
        request_database_url: str,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        """The ledger is append-only *from the privileged path only*.

        A client able to write its own spend records could poison its own anomaly
        baseline, making a real runaway look ordinary.
        """
        alice, _ = two_tenants

        with as_user(request_database_url, alice.user_id) as connection:
            with pytest.raises(psycopg.Error):  # noqa: PT012 - the insert is the assertion
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO public.ai_spend_records "
                        "(workspace_id, provider, model, workflow_type, "
                        " prompt_tokens, completion_tokens, cost_usd) "
                        "VALUES (%s, 'openai', 'x', 'chat', 1, 1, 0.01)",
                        (alice.workspace_id,),
                    )

    def test_a_tenant_cannot_rewrite_its_own_spend_history(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        """No UPDATE policy and no UPDATE grant -- a financial record is immutable."""
        alice, _ = two_tenants
        seed_spend(admin_connection, alice.workspace_id)

        with as_user(request_database_url, alice.user_id) as connection:
            with pytest.raises(psycopg.Error):  # noqa: PT012 - the update is the assertion
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE public.ai_spend_records SET cost_usd = 0 WHERE workspace_id = %s",
                        (alice.workspace_id,),
                    )

    def test_a_tenant_cannot_delete_its_own_spend_history(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        alice, _ = two_tenants
        seed_spend(admin_connection, alice.workspace_id)

        with as_user(request_database_url, alice.user_id) as connection:
            with pytest.raises(psycopg.Error):  # noqa: PT012 - the delete is the assertion
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM public.ai_spend_records WHERE workspace_id = %s",
                        (alice.workspace_id,),
                    )


class TestBudgetIsolation:
    """A workspace cannot see, or raise, another workspace's ceiling."""

    def test_a_tenant_cannot_read_another_workspaces_budget(
        self,
        request_database_url: str,
        spend_repository: AISpendRepository,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        alice, bob = two_tenants
        spend_repository.upsert_budget(bob.workspace_id, None, Decimal("500.00"))

        with as_user(request_database_url, alice.user_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM public.ai_budgets WHERE workspace_id = %s",
                    (bob.workspace_id,),
                )
                count = cursor.fetchone()

        assert count is not None
        assert count[0] == 0

    def test_a_tenant_cannot_raise_another_workspaces_ceiling(
        self,
        request_database_url: str,
        spend_repository: AISpendRepository,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        """The obvious attack: lift someone else's limit, or your own via theirs."""
        alice, bob = two_tenants
        spend_repository.upsert_budget(bob.workspace_id, None, Decimal("10.00"))

        with as_user(request_database_url, alice.user_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.ai_budgets SET limit_usd = 999999 WHERE workspace_id = %s",
                    (bob.workspace_id,),
                )
                affected = cursor.rowcount
            connection.commit()

        # A USING mismatch affects zero rows silently rather than raising --
        # which is why this asserts the count rather than expecting an error.
        assert affected == 0

        budgets = spend_repository.budgets_for(bob.workspace_id, "chat")
        assert budgets[0].limit_usd == Decimal("10.000000")

    def test_a_tenant_cannot_clear_its_own_running_total(
        self,
        request_database_url: str,
        spend_repository: AISpendRepository,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        """Resetting `spent_usd` would be granting yourself unlimited budget.

        **This test asserted the opposite until STEP-19.** STEP-18 recorded the
        exposure honestly rather than claiming a protection that did not exist:
        the UPDATE policy permits owner/admin writes for *configuration*, and a
        PostgreSQL policy is per-row rather than per-column, so it reached the
        running total too. The assertion was `affected == 1`.

        Migration `c9d3b71e08af` closes it with the mechanism RLS structurally
        cannot provide -- a **column-level grant**, evaluated before any policy
        runs. The table-wide UPDATE is revoked in favour of one on `limit_usd`
        and `period_interval`, so this write is now refused outright rather than
        affecting a row.

        `InsufficientPrivilege` rather than a zero rowcount, and the difference
        matters: a policy mismatch silently affects no rows, while a missing
        grant raises. The refusal is therefore loud, which is the correct
        treatment for an attempt to rewrite a spend ceiling's enforcement state.
        """
        alice, _ = two_tenants
        spend_repository.upsert_budget(alice.workspace_id, None, Decimal("10.00"))
        spend_repository.try_reserve(alice.workspace_id, "chat", Decimal("5.00"))

        with as_user(request_database_url, alice.user_id) as connection:
            with connection.cursor() as cursor, pytest.raises(psycopg.errors.InsufficientPrivilege):
                cursor.execute(
                    "UPDATE public.ai_budgets SET spent_usd = 0 WHERE workspace_id = %s",
                    (alice.workspace_id,),
                )
            connection.rollback()

        # The counter is untouched, which is the outcome rather than the
        # exception type. `try_reserve` above moved it to 5.
        budgets = spend_repository.budgets_for(alice.workspace_id, "chat")
        assert budgets[0].spent_usd == Decimal("5.000000")

    def test_the_configuration_columns_are_still_writable(
        self,
        request_database_url: str,
        spend_repository: AISpendRepository,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        """The negative control on the grant: it narrowed, it did not close.

        Without this, a migration that revoked UPDATE and granted nothing back
        would pass the test above while breaking the settings route entirely --
        an owner would be unable to change their own spending limit.
        """
        alice, _ = two_tenants
        spend_repository.upsert_budget(alice.workspace_id, None, Decimal("10.00"))

        with as_user(request_database_url, alice.user_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.ai_budgets SET limit_usd = 99 WHERE workspace_id = %s",
                    (alice.workspace_id,),
                )
                assert cursor.rowcount == 1
            connection.commit()

        budgets = spend_repository.budgets_for(alice.workspace_id, "chat")
        assert budgets[0].limit_usd == Decimal("99.000000")

    def test_a_member_cannot_change_a_budget(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        spend_repository: AISpendRepository,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        """Writes are owner/admin only, reads are membership-scoped."""
        alice, _ = two_tenants
        member = uuid.uuid4()

        with admin_connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO public.users (id, email, display_name) VALUES (%s, %s, %s)",
                (member, f"member-{member.hex[:8]}@example.test", "Member"),
            )
            cursor.execute(
                "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
                "VALUES (%s, %s, 'member')",
                (alice.workspace_id, member),
            )

        spend_repository.upsert_budget(alice.workspace_id, None, Decimal("10.00"))

        with as_user(request_database_url, member) as connection:
            with connection.cursor() as cursor:
                # Reads: permitted, because a refused user must be able to see why.
                cursor.execute(
                    "SELECT count(*) FROM public.ai_budgets WHERE workspace_id = %s",
                    (alice.workspace_id,),
                )
                visible = cursor.fetchone()

                cursor.execute(
                    "UPDATE public.ai_budgets SET limit_usd = 999 WHERE workspace_id = %s",
                    (alice.workspace_id,),
                )
                affected = cursor.rowcount
            connection.commit()

        assert visible is not None
        assert visible[0] == 1
        assert affected == 0


class TestShutdownSwitchIsolation:
    """The platform switch belongs to no tenant and is reachable by none."""

    def test_a_tenant_cannot_see_the_platform_shutdown_switch(
        self,
        request_database_url: str,
        spend_repository: AISpendRepository,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        """Seeing it would tell a tenant about an incident affecting other customers."""
        alice, _ = two_tenants
        switch = spend_repository.set_platform_shutdown("platform incident")

        with as_user(request_database_url, alice.user_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM public.ai_shutdown_switches WHERE id = %s",
                    (switch,),
                )
                count = cursor.fetchone()

        assert count is not None
        assert count[0] == 0

    def test_a_tenant_cannot_create_a_platform_wide_shutdown(
        self,
        request_database_url: str,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        """The worst thing a tenant could do here: disable AI for every customer."""
        alice, _ = two_tenants

        with as_user(request_database_url, alice.user_id) as connection:
            with pytest.raises(psycopg.Error):  # noqa: PT012 - the insert is the assertion
                with connection.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO public.ai_shutdown_switches "
                        "(workspace_id, reason) VALUES (NULL, 'hostile')"
                    )

    def test_a_tenant_cannot_lift_another_workspaces_shutdown(
        self,
        request_database_url: str,
        spend_repository: AISpendRepository,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        alice, bob = two_tenants
        spend_repository.set_workspace_shutdown(bob.workspace_id, "runaway")

        with as_user(request_database_url, alice.user_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE public.ai_shutdown_switches SET deleted_at = now() "
                    "WHERE workspace_id = %s",
                    (bob.workspace_id,),
                )
                affected = cursor.rowcount
            connection.commit()

        assert affected == 0
        assert spend_repository.active_shutdown(bob.workspace_id, "chat") == "runaway"


class TestReservationAtomicity:
    """The property a single-threaded fake structurally cannot demonstrate."""

    def test_concurrent_reservations_cannot_both_take_the_last_of_a_budget(
        self,
        spend_repository: AISpendRepository,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        """The TOCTOU race the compare-and-increment exists to close.

        Two threads each try to reserve $6 against a ceiling with $10 of room.
        A read-then-write check admits both, and the ceiling is breached by
        exactly the amount that makes it not a ceiling. Exactly one must win.
        """
        alice, _ = two_tenants
        spend_repository.upsert_budget(alice.workspace_id, None, Decimal("10.00"))

        results: list[bool] = []
        lock = threading.Lock()

        def reserve() -> None:
            granted = spend_repository.try_reserve(alice.workspace_id, "chat", Decimal("6.00"))
            with lock:
                results.append(granted)

        threads = [threading.Thread(target=reserve) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert sum(results) == 1, "exactly one of two competing reservations must win"

        budgets = spend_repository.budgets_for(alice.workspace_id, "chat")
        assert budgets[0].spent_usd <= budgets[0].limit_usd

    def test_many_concurrent_reservations_never_exceed_the_ceiling(
        self,
        spend_repository: AISpendRepository,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        """Under real contention, the invariant is the ceiling, not the count."""
        alice, _ = two_tenants
        spend_repository.upsert_budget(alice.workspace_id, None, Decimal("10.00"))

        granted: list[bool] = []
        lock = threading.Lock()

        def reserve() -> None:
            result = spend_repository.try_reserve(alice.workspace_id, "chat", Decimal("1.00"))
            with lock:
                granted.append(result)

        threads = [threading.Thread(target=reserve) for _ in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert sum(granted) == 10, "exactly ten $1 reservations fit under a $10 ceiling"

        budgets = spend_repository.budgets_for(alice.workspace_id, "chat")
        assert budgets[0].spent_usd == Decimal("10.000000")

    def test_a_reservation_refused_by_one_ceiling_reserves_against_neither(
        self,
        spend_repository: AISpendRepository,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        """All-or-nothing across both applicable budgets.

        Without the rollback, a workspace refused repeatedly by a tight workflow
        ceiling would still bleed its workspace ceiling dry on calls that never
        happened.
        """
        alice, _ = two_tenants
        spend_repository.upsert_budget(alice.workspace_id, None, Decimal("100.00"))
        spend_repository.upsert_budget(alice.workspace_id, "chat", Decimal("1.00"))

        assert spend_repository.try_reserve(alice.workspace_id, "chat", Decimal("5.00")) is False

        budgets = {
            budget.workflow_type: budget
            for budget in spend_repository.budgets_for(alice.workspace_id, "chat")
        }

        assert budgets[None].spent_usd == Decimal(0)
        assert budgets["chat"].spent_usd == Decimal(0)

    def test_an_open_breaker_refuses_the_reservation_in_the_database(
        self,
        spend_repository: AISpendRepository,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        """The breaker is enforced in the same statement as the ceiling.

        Checking it only in Python would leave a window in which a concurrent
        reservation slips past a breaker that has just tripped.
        """
        alice, _ = two_tenants
        spend_repository.upsert_budget(alice.workspace_id, None, Decimal("100.00"))
        spend_repository.trip_breaker(alice.workspace_id, None, "test")

        assert spend_repository.try_reserve(alice.workspace_id, "chat", Decimal("1.00")) is False

    def test_settlement_returns_the_unused_reservation(
        self,
        spend_repository: AISpendRepository,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        alice, _ = two_tenants
        spend_repository.upsert_budget(alice.workspace_id, None, Decimal("100.00"))

        spend_repository.try_reserve(alice.workspace_id, "chat", Decimal("10.00"))
        spend_repository.settle(alice.workspace_id, "chat", Decimal("10.00"), Decimal("0.25"))

        budgets = spend_repository.budgets_for(alice.workspace_id, "chat")
        assert budgets[0].spent_usd == Decimal("0.250000")

    def test_a_running_total_never_goes_negative(
        self,
        spend_repository: AISpendRepository,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        """A settlement without its reservation would otherwise hand out free budget."""
        alice, _ = two_tenants
        spend_repository.upsert_budget(alice.workspace_id, None, Decimal("100.00"))

        spend_repository.settle(alice.workspace_id, "chat", Decimal("50.00"), Decimal(0))

        budgets = spend_repository.budgets_for(alice.workspace_id, "chat")
        assert budgets[0].spent_usd == Decimal(0)

    def test_an_expired_period_resets_the_running_total(
        self,
        spend_repository: AISpendRepository,
        admin_connection: psycopg.Connection,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        alice, _ = two_tenants
        budget_id = spend_repository.upsert_budget(
            alice.workspace_id, None, Decimal("10.00"), dt.timedelta(days=1)
        )
        spend_repository.try_reserve(alice.workspace_id, "chat", Decimal("9.00"))

        with admin_connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.ai_budgets SET period_started_at = now() - interval '2 days' "
                "WHERE id = %s",
                (budget_id,),
            )

        budgets = spend_repository.budgets_for(alice.workspace_id, "chat")

        assert budgets[0].spent_usd == Decimal(0)

    def test_a_period_reset_does_not_clear_a_tripped_breaker(
        self,
        spend_repository: AISpendRepository,
        admin_connection: psycopg.Connection,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        """A breaker that cleared itself on a schedule would let a runaway resume."""
        alice, _ = two_tenants
        budget_id = spend_repository.upsert_budget(
            alice.workspace_id, None, Decimal("10.00"), dt.timedelta(days=1)
        )
        spend_repository.trip_breaker(alice.workspace_id, None, "anomaly")

        with admin_connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.ai_budgets SET period_started_at = now() - interval '2 days' "
                "WHERE id = %s",
                (budget_id,),
            )

        budgets = spend_repository.budgets_for(alice.workspace_id, "chat")

        assert budgets[0].spent_usd == Decimal(0)
        assert budgets[0].is_breaker_open


class TestSchemaGuarantees:
    """Properties the migration must hold, queried from the catalog."""

    @pytest.mark.parametrize(
        "table",
        ["ai_spend_records", "ai_budgets", "ai_shutdown_switches"],
    )
    def test_rls_is_enabled_and_forced(
        self, admin_connection: psycopg.Connection, table: str
    ) -> None:
        """ENABLE alone lets the owner bypass its own policies."""
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
                "WHERE relname = %s AND relnamespace = 'public'::regnamespace",
                (table,),
            )
            row = cursor.fetchone()

        assert row is not None
        assert row[0] is True, f"{table} does not have RLS enabled"
        assert row[1] is True, f"{table} does not have RLS forced"

    @pytest.mark.parametrize(
        "table",
        ["ai_spend_records", "ai_budgets", "ai_shutdown_switches"],
    )
    def test_no_table_grants_delete_or_truncate(
        self, admin_connection: psycopg.Connection, table: str
    ) -> None:
        """TRUNCATE matters most: it is not subject to RLS at all."""
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "SELECT privilege_type FROM information_schema.role_table_grants "
                "WHERE table_name = %s AND grantee IN ('anon', 'authenticated')",
                (table,),
            )
            granted = {row[0] for row in cursor}

        assert "DELETE" not in granted
        assert "TRUNCATE" not in granted

    def test_anon_holds_nothing_on_any_governance_table(
        self, admin_connection: psycopg.Connection
    ) -> None:
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM information_schema.role_table_grants "
                "WHERE table_name IN "
                "('ai_spend_records', 'ai_budgets', 'ai_shutdown_switches') "
                "AND grantee = 'anon'"
            )
            count = cursor.fetchone()

        assert count is not None
        assert count[0] == 0

    def test_the_spend_ledger_grants_no_write_at_all(
        self, admin_connection: psycopg.Connection
    ) -> None:
        """Append-only from every client path: no INSERT or UPDATE grant."""
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "SELECT privilege_type FROM information_schema.role_table_grants "
                "WHERE table_name = 'ai_spend_records' AND grantee = 'authenticated'"
            )
            granted = {row[0] for row in cursor}

        assert granted == {"SELECT"}


class TestPoliciesAreWhatMakeTheseTestsPass:
    """Disable RLS, observe the breach, restore it.

    The negative control STEP-09 established, applied to the governance tables:
    an isolation test that passes with the policies off is asserting nothing.
    """

    def test_the_spend_ledger_is_readable_across_tenants_with_rls_off(
        self,
        request_database_url: str,
        admin_connection: psycopg.Connection,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        alice, bob = two_tenants
        seed_spend(admin_connection, bob.workspace_id)

        with as_user(request_database_url, alice.user_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM public.ai_spend_records WHERE workspace_id = %s",
                    (bob.workspace_id,),
                )
                protected = cursor.fetchone()

        assert protected is not None
        assert protected[0] == 0

        with admin_connection.cursor() as cursor:
            cursor.execute("ALTER TABLE public.ai_spend_records DISABLE ROW LEVEL SECURITY")

        try:
            with as_user(request_database_url, alice.user_id) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT count(*) FROM public.ai_spend_records WHERE workspace_id = %s",
                        (bob.workspace_id,),
                    )
                    breached = cursor.fetchone()

            assert breached is not None
            assert breached[0] == 1, "with RLS off the breach must be observable"
        finally:
            # Restored even if the assertion fails, or every subsequent test in
            # this session runs against an unprotected table.
            with admin_connection.cursor() as cursor:
                cursor.execute("ALTER TABLE public.ai_spend_records ENABLE ROW LEVEL SECURITY")
                cursor.execute("ALTER TABLE public.ai_spend_records FORCE ROW LEVEL SECURITY")

        with as_user(request_database_url, alice.user_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM public.ai_spend_records WHERE workspace_id = %s",
                    (bob.workspace_id,),
                )
                restored = cursor.fetchone()

        assert restored is not None
        assert restored[0] == 0


class TestConnectionBudget:
    """One governed call must not exhaust the connection pool.

    A defect found by running STEP-18's validation, not by reviewing it: the
    repository opened a connection per method, so one AI call cost six, against
    a Supabase session pooler limited to 15. Two concurrent calls exhausted it
    and the pooler answered `EMAXCONNSESSION` -- a cost control becoming an
    availability failure.
    """

    def test_a_guarded_call_uses_a_single_connection(
        self,
        spend_repository: AISpendRepository,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        """Counted, not reasoned about -- the original defect looked fine on paper."""
        from unittest import mock

        from app.ai.provider import TokenUsage
        from app.services.ai_spend_service import AISpendService

        alice, _ = two_tenants
        spend_repository.upsert_budget(alice.workspace_id, None, Decimal("100.00"))
        service = AISpendService(spend_repository)

        real_connect = psycopg.connect
        opened = 0

        def counting_connect(*args: object, **kwargs: object) -> psycopg.Connection:
            nonlocal opened
            opened += 1
            return real_connect(*args, **kwargs)  # type: ignore[arg-type]

        with mock.patch("psycopg.connect", counting_connect):
            with service.guard(alice.workspace_id, "chat", Decimal("0.05")) as entry:
                entry.record("openai", "gpt-4o-mini", TokenUsage(10, 20))

        assert opened == 1, f"one governed call opened {opened} connections, expected 1"

    def test_the_guarded_call_still_records_everything_through_one_connection(
        self,
        spend_repository: AISpendRepository,
        two_tenants: tuple[Identity, Identity],
    ) -> None:
        """The optimisation must not lose a write -- an unwritten ledger row is lost money."""
        from app.ai.provider import TokenUsage
        from app.services.ai_spend_service import AISpendService

        alice, _ = two_tenants
        spend_repository.upsert_budget(alice.workspace_id, None, Decimal("100.00"))
        service = AISpendService(spend_repository)

        with service.guard(alice.workspace_id, "chat", Decimal("0.05")) as entry:
            entry.record("openai", "gpt-4o-mini", TokenUsage(10, 20))

        summary = spend_repository.spend_since(
            alice.workspace_id, dt.datetime.now(dt.UTC) - dt.timedelta(hours=1)
        )

        assert summary.call_count == 1
        assert summary.total_usd > 0

        settled = spend_repository.budgets_for(alice.workspace_id, "chat")[0]
        assert settled.spent_usd == summary.total_usd, "the reservation must settle to actual cost"
