"""Reads and writes the AI spend ledger, the budget ceilings and the kill switches.

Unlike every other repository in this codebase, this one uses **both**
connections, and which one each method uses is a security decision rather than a
convenience:

| Operation | Connection | Why |
|---|---|---|
| Read budgets for enforcement | privileged | must see a ceiling the caller cannot hide |
| Reserve / settle spend | privileged | `spent_usd` must not be writable by a tenant |
| Write a spend record | privileged | a client-writable ledger is a forgeable one |
| Read the platform switch | privileged | the row belongs to no tenant |
| Read a workspace's own spend | **tenant** | ordinary tenant data, RLS applies |
| Read a workspace's budgets | **tenant** | ordinary tenant data, RLS applies |

## Why enforcement reads privileged, when RLS would also work

A budget check must answer "is this workspace over its ceiling" correctly even
if the caller has somehow arranged not to see their own budget row. Over the
tenant connection, a row hidden by RLS and a row that does not exist are
indistinguishable -- which is exactly the property that makes RLS safe for reads
and **wrong for a control**: "I cannot see a budget" would become "there is no
budget", and no budget means no ceiling.

Reading it privileged inverts that failure: the ceiling is found whether or not
the caller could see it. This is the audited-service-path shape CLAUDE.md §16
requires for operations RLS deliberately cannot express, and the same reasoning
that puts `audit_log` writes on the privileged connection.

**The tenant boundary is not lost.** Every privileged method takes the workspace
id from the verified request context (`AIService` closes over it, exactly as it
does for BYOK keys) and filters on it explicitly. What changes is that the filter
is the code's responsibility here rather than the database's -- which is why
these queries are short, single-purpose, and never take a workspace id from
anything a client sent.

## Why the reservation is one statement

`UPDATE ... SET spent_usd = spent_usd + %s WHERE ... AND spent_usd + %s <= limit_usd`

Compare and increment in a single statement, so PostgreSQL's row lock serialises
concurrent callers. The alternative -- SELECT the total, add in Python, UPDATE --
is a textbook time-of-check-to-time-of-use race: two workers both read a total
under the ceiling, both proceed, and the ceiling is breached by exactly the
amount that makes it not a ceiling.

`cursor.rowcount` is then the answer: 1 means the reservation was granted, 0
means it would have breached a ceiling. No separate read is needed and no
separate read could be trusted.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal

import psycopg

from app.core.config import Settings

#: Scope value meaning "every workflow type", stored as SQL NULL.
#:
#: A module constant rather than a bare None at each call site, because
#: `workflow_type=None` reads as "unspecified" while it actually means
#: "workspace-wide" -- a distinction worth naming where a policy depends on it.
WORKSPACE_WIDE: str | None = None


@dataclass(frozen=True)
class Budget:
    """One configured ceiling, and how much of it is spent."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    workflow_type: str | None
    limit_usd: Decimal
    spent_usd: Decimal
    period_started_at: dt.datetime
    period_interval: dt.timedelta
    breaker_tripped_at: dt.datetime | None
    breaker_reason: str | None

    @property
    def remaining_usd(self) -> Decimal:
        """Return what is left of this ceiling, never below zero.

        Clamped because a reservation settled to a higher actual cost can, in
        principle, push `spent_usd` past `limit_usd` -- and a negative
        "remaining" reads as a credit rather than as an overage.
        """
        return max(Decimal(0), self.limit_usd - self.spent_usd)

    @property
    def is_breaker_open(self) -> bool:
        """Return whether the spend breaker has tripped on this budget."""
        return self.breaker_tripped_at is not None


@dataclass(frozen=True)
class SpendSummary:
    """What a workspace has spent over some window."""

    total_usd: Decimal
    call_count: int
    total_tokens: int


class AISpendRepository:
    """Persists spend, enforces ceilings atomically, and reads kill switches."""

    def __init__(self, settings: Settings) -> None:
        """Store the settings holding the privileged connection string."""
        self._settings = settings
        self._session: psycopg.Connection | None = None

    @contextmanager
    def session(self) -> Iterator[None]:
        """Reuse one connection for every call made inside this block.

        **Found by running it, not by review.** One governed AI call makes eight
        separate repository calls -- shutdown check, period reset, budget read,
        reservation, settlement, ledger write, and two anomaly window reads. With
        a connection per call that is eight connections per request, against a
        Supabase session pooler whose ceiling is 15. Two concurrent AI calls
        would exhaust the pool and the *third* would fail to connect at all --
        turning a cost control into an availability failure.

        Observed directly during STEP-18 validation: twenty concurrent
        reservations produced `EMAXCONNSESSION -- max clients are limited to
        pool_size: 15` from the pooler.

        Opening the session collapses those eight into one. Outside a session
        each method still opens and closes its own connection, so a caller that
        does not need the optimisation is unaffected and no method depends on a
        session being open.

        Not reentrant, and not shared across threads: the repository is
        constructed per request (`get_ai_spend_repository`), so its session is
        request-scoped by construction. A shared one would let two requests
        interleave transactions on the same connection, which is the
        pooled-connection defect STEP-10 reproduced.
        """
        if self._session is not None:  # pragma: no cover - defensive
            raise RuntimeError("A spend repository session is already open")

        connection = self._open()
        self._session = connection

        try:
            yield
        finally:
            self._session = None
            connection.close()

    def _open(self) -> psycopg.Connection:
        """Open a privileged connection.

        Bounded by the same timeout every other privileged connection uses: an
        unbounded connect here would let a degraded database hold an AI request
        open indefinitely.
        """
        return psycopg.connect(
            self._settings.database_url.get_secret_value(),
            connect_timeout=self._settings.database_health_timeout_seconds,
        )

    @contextmanager
    def _connect(self) -> Iterator[psycopg.Connection]:
        """Yield the session's connection, or a fresh one outside a session.

        A context manager rather than a bare connection so callers keep the same
        `with` shape either way. The session's connection is deliberately **not**
        closed on exit -- `session()` owns its lifetime -- while a standalone one
        is, which is what keeps the no-session path identical to the original
        behaviour.
        """
        if self._session is not None:
            yield self._session
            # Committed rather than left open: each method here is one logical
            # unit of work, and holding a transaction open across the provider
            # call would keep a row lock for the duration of an upstream HTTP
            # request -- which is exactly how a budget row becomes a bottleneck.
            self._session.commit()
            return

        with self._open() as connection:
            yield connection

    # ------------------------------------------------------------------
    # Emergency shutdown
    # ------------------------------------------------------------------

    def active_shutdown(
        self,
        workspace_id: uuid.UUID,
        workflow_type: str,
    ) -> str | None:
        """Return the reason AI spend is disabled, or None when it is permitted.

        Checks all three scopes CLAUDE.md §15a requires in one query:

        - **platform-wide** (`workspace_id IS NULL`, `workflow_type IS NULL`)
        - **platform, one workflow type**
        - **one workspace**, either whole or one workflow type

        Read over the privileged connection because the platform row belongs to
        no tenant and is deliberately invisible to every RLS policy. A tenant
        connection would find only the workspace rows and would therefore report
        "no shutdown" during a platform-wide incident -- the exact failure the
        switch exists to prevent.

        Returns:
            The reason string of the most recently activated matching switch, or
            None. The reason rather than a boolean, so an operator reading a log
            sees *why* calls are being refused without a second query.
        """
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT reason
                FROM public.ai_shutdown_switches
                WHERE deleted_at IS NULL
                  AND (workspace_id IS NULL OR workspace_id = %s)
                  AND (workflow_type IS NULL OR workflow_type = %s)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (workspace_id, workflow_type),
            )
            row = cursor.fetchone()

        return None if row is None else str(row[0])

    def set_platform_shutdown(
        self,
        reason: str,
        workflow_type: str | None = None,
        activated_by: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Disable AI spend platform-wide, without a deploy.

        The row is written with `workspace_id = NULL`, which no RLS policy
        matches -- so it can only be created here, on the privileged path. That
        is deliberate: a tenant able to write this row could disable AI for every
        other customer on the platform.

        Returns:
            The switch's id, so it can be lifted again by `lift_shutdown`.
        """
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.ai_shutdown_switches
                    (workspace_id, workflow_type, reason, activated_by)
                VALUES (NULL, %s, %s, %s)
                RETURNING id
                """,
                (workflow_type, reason, activated_by),
            )
            row = cursor.fetchone()

        if row is None:  # pragma: no cover - defensive
            raise RuntimeError("Shutdown switch insert returned no id")

        return uuid.UUID(str(row[0]))

    def set_workspace_shutdown(
        self,
        workspace_id: uuid.UUID,
        reason: str,
        workflow_type: str | None = None,
        activated_by: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Disable AI spend for one workspace, without a deploy."""
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.ai_shutdown_switches
                    (workspace_id, workflow_type, reason, activated_by)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (workspace_id, workflow_type, reason, activated_by),
            )
            row = cursor.fetchone()

        if row is None:  # pragma: no cover - defensive
            raise RuntimeError("Shutdown switch insert returned no id")

        return uuid.UUID(str(row[0]))

    def lift_shutdown(self, switch_id: uuid.UUID) -> bool:
        """Soft-delete a shutdown switch, re-enabling AI spend in its scope.

        A soft delete rather than a hard one, so the record of an incident
        survives the end of the incident.

        Returns:
            True when a live switch was lifted.
        """
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.ai_shutdown_switches
                SET deleted_at = now()
                WHERE id = %s AND deleted_at IS NULL
                """,
                (switch_id,),
            )
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Budgets and the atomic reservation
    # ------------------------------------------------------------------

    def budgets_for(
        self,
        workspace_id: uuid.UUID,
        workflow_type: str,
    ) -> tuple[Budget, ...]:
        """Return every ceiling that applies to one call.

        At most two: the workspace-wide budget and the one scoped to this
        workflow type. Both apply as a **conjunction** -- a call must pass each
        one -- so neither can be used to escape the other.

        Rows whose period has elapsed are reset to zero before being returned, so
        a caller never enforces against a stale period. See `_reset_expired`.

        Read privileged: see the module docstring on why a ceiling must be found
        whether or not the caller could see it.
        """
        self._reset_expired(workspace_id)

        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, workspace_id, workflow_type, limit_usd, spent_usd,
                       period_started_at, period_interval,
                       breaker_tripped_at, breaker_reason
                FROM public.ai_budgets
                WHERE workspace_id = %s
                  AND deleted_at IS NULL
                  AND (workflow_type IS NULL OR workflow_type = %s)
                ORDER BY workflow_type NULLS FIRST
                """,
                (workspace_id, workflow_type),
            )
            rows = cursor.fetchall()

        return tuple(
            Budget(
                id=row[0],
                workspace_id=row[1],
                workflow_type=row[2],
                limit_usd=row[3],
                spent_usd=row[4],
                period_started_at=row[5],
                period_interval=row[6],
                breaker_tripped_at=row[7],
                breaker_reason=row[8],
            )
            for row in rows
        )

    def _reset_expired(self, workspace_id: uuid.UUID) -> None:
        """Roll any budget whose period has elapsed into a fresh period.

        Done in SQL with `now()` rather than in Python, so the comparison and
        the write are one statement and two concurrent callers cannot both
        decide a period expired and both reset it -- which would advance the
        period twice and grant a workspace two allowances.

        `period_started_at` advances to `now()` rather than by exactly one
        interval. The difference matters for a workspace that made no calls for
        several periods: advancing by one interval would leave the row still
        expired and reset it again on the next call, whereas this starts a fresh
        period from the moment of first use.

        The breaker is deliberately **not** cleared here. A tripped spend
        breaker is an incident someone should look at, and having it silently
        clear itself when a billing period rolls over would let a runaway resume
        on a schedule (CLAUDE.md §15a -- a tripped breaker stops, it does not
        degrade into a delay).
        """
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.ai_budgets
                SET spent_usd = 0, period_started_at = now()
                WHERE workspace_id = %s
                  AND deleted_at IS NULL
                  AND period_started_at + period_interval <= now()
                """,
                (workspace_id,),
            )

    def try_reserve(
        self,
        workspace_id: uuid.UUID,
        workflow_type: str,
        amount_usd: Decimal,
    ) -> bool:
        """Atomically reserve spend against every applicable ceiling.

        **The load-bearing method of this whole step.** Compare-and-increment in
        one statement per budget, inside one transaction, so that:

        - Concurrent callers serialise on the row lock rather than racing.
        - A reservation that would breach *any* applicable ceiling reserves
          against *none* of them -- the transaction rolls back, so a call
          refused by its workflow budget has not silently consumed workspace
          budget on the way to being refused.

        Ordered by `id` deliberately: two concurrent calls for the same workspace
        acquire the same row locks in the same order, so they queue rather than
        deadlock. Without a deterministic order, one call taking the workspace
        budget while another takes the workflow budget is a classic deadlock, and
        it would surface as an intermittent 500 on a busy workspace.

        Args:
            workspace_id: The verified tenant.
            workflow_type: What is spending.
            amount_usd: The pessimistic reservation. Settled to the real figure
                by `settle` once the call returns.

        Returns:
            True when every applicable ceiling had room. False when at least one
            did not, in which case nothing was reserved.
        """
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM public.ai_budgets
                WHERE workspace_id = %s
                  AND deleted_at IS NULL
                  AND (workflow_type IS NULL OR workflow_type = %s)
                ORDER BY id
                FOR UPDATE
                """,
                (workspace_id, workflow_type),
            )
            budget_ids = [row[0] for row in cursor.fetchall()]

            # No configured ceiling is not the same as a breached one. A
            # workspace with no budget row is unmetered by configuration, which
            # is the correct default for a platform that has not yet asked
            # anyone to set a limit -- and `AISpendService` is what decides
            # whether that default is acceptable per environment, not this
            # repository.
            if not budget_ids:
                # Committed rather than returned straight out: the `FOR UPDATE`
                # above took no row locks (there are no rows), but leaving the
                # transaction open on a session-scoped connection would hold a
                # snapshot for the duration of the provider call that follows.
                connection.commit()
                return True

            for budget_id in budget_ids:
                cursor.execute(
                    """
                    UPDATE public.ai_budgets
                    SET spent_usd = spent_usd + %s
                    WHERE id = %s
                      AND breaker_tripped_at IS NULL
                      AND spent_usd + %s <= limit_usd
                    """,
                    (amount_usd, budget_id, amount_usd),
                )

                if cursor.rowcount == 0:
                    # Either the ceiling had no room or the breaker is open.
                    # Rolling back is what makes this all-or-nothing: the
                    # budgets updated earlier in this loop are un-reserved.
                    connection.rollback()
                    return False

            connection.commit()

        return True

    def settle(
        self,
        workspace_id: uuid.UUID,
        workflow_type: str,
        reserved_usd: Decimal,
        actual_usd: Decimal,
    ) -> None:
        """Replace a reservation with what the call actually cost.

        Adjusts by the difference rather than by writing an absolute figure,
        because concurrent calls each hold their own reservation against the same
        running total -- an absolute write would discard theirs.

        The adjustment can be negative (the usual case: a reservation is a
        pessimistic worst case and real usage is lower). `GREATEST(..., 0)` keeps
        the running total from going negative if a settlement arrives without its
        matching reservation, which would otherwise hand a workspace free
        allowance.

        **Never skipped on failure.** A call that fails after its reservation
        must still settle, or the reservation leaks and permanently reduces the
        workspace's ceiling. `AISpendService` settles in a `finally`.
        """
        adjustment = actual_usd - reserved_usd

        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.ai_budgets
                SET spent_usd = GREATEST(spent_usd + %s, 0)
                WHERE workspace_id = %s
                  AND deleted_at IS NULL
                  AND (workflow_type IS NULL OR workflow_type = %s)
                """,
                (adjustment, workspace_id, workflow_type),
            )

    def trip_breaker(
        self,
        workspace_id: uuid.UUID,
        workflow_type: str | None,
        reason: str,
    ) -> bool:
        """Open the spend circuit breaker on a budget.

        Distinct from `ProviderHealthTracker` in both mechanism and consequence:
        that one removes a provider from rotation, this one **stops the call**.
        A breaker that rerouted spend to another provider would not be a spend
        control at all.

        Idempotent -- an already-tripped breaker is not re-tripped, so the
        original reason and timestamp survive. The first cause of an incident is
        more useful than the most recent symptom of it.

        Returns:
            True when a breaker was newly tripped.
        """
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.ai_budgets
                SET breaker_tripped_at = now(), breaker_reason = %s
                WHERE workspace_id = %s
                  AND deleted_at IS NULL
                  AND workflow_type IS NOT DISTINCT FROM %s
                  AND breaker_tripped_at IS NULL
                """,
                (reason, workspace_id, workflow_type),
            )
            return cursor.rowcount > 0

    def reset_breaker(self, workspace_id: uuid.UUID, workflow_type: str | None) -> bool:
        """Close a tripped spend breaker.

        Deliberately **manual**. An availability breaker closes itself after a
        cooldown because a provider outage ends on its own; a spend breaker trips
        because something spent more than expected, and that does not resolve by
        waiting. Someone decides it is safe to resume.

        Returns:
            True when a tripped breaker was closed.
        """
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.ai_budgets
                SET breaker_tripped_at = NULL, breaker_reason = NULL
                WHERE workspace_id = %s
                  AND deleted_at IS NULL
                  AND workflow_type IS NOT DISTINCT FROM %s
                  AND breaker_tripped_at IS NOT NULL
                """,
                (workspace_id, workflow_type),
            )
            return cursor.rowcount > 0

    def upsert_budget(
        self,
        workspace_id: uuid.UUID,
        workflow_type: str | None,
        limit_usd: Decimal,
        period_interval: dt.timedelta | None = None,
    ) -> uuid.UUID:
        """Create or update a ceiling.

        Written on the privileged path rather than through the tenant connection
        even though an RLS policy permits owner/admin writes. The policy exists
        for the settings route STEP-19 will add; this method is the platform's
        own path, used by provisioning and by tests.

        Returns:
            The budget's id.
        """
        interval = period_interval if period_interval is not None else dt.timedelta(days=30)

        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE public.ai_budgets
                SET limit_usd = %s, period_interval = %s
                WHERE workspace_id = %s
                  AND deleted_at IS NULL
                  AND workflow_type IS NOT DISTINCT FROM %s
                RETURNING id
                """,
                (limit_usd, interval, workspace_id, workflow_type),
            )
            row = cursor.fetchone()

            if row is not None:
                return uuid.UUID(str(row[0]))

            cursor.execute(
                """
                INSERT INTO public.ai_budgets
                    (workspace_id, workflow_type, limit_usd, period_interval)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (workspace_id, workflow_type, limit_usd, interval),
            )
            inserted = cursor.fetchone()

        if inserted is None:  # pragma: no cover - defensive
            raise RuntimeError("Budget insert returned no id")

        return uuid.UUID(str(inserted[0]))

    # ------------------------------------------------------------------
    # The ledger
    # ------------------------------------------------------------------

    def record(
        self,
        workspace_id: uuid.UUID,
        provider: str,
        model: str,
        workflow_type: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: Decimal,
        actor_id: uuid.UUID | None = None,
    ) -> None:
        """Append one spend record.

        Privileged, and the table has no INSERT policy or grant for
        `authenticated` -- the same append-only shape as `audit_log`, for the
        same reason. A client able to write its own spend records could forge
        them, and a forged ledger is worse than a missing one because it is
        trusted: a workspace could flood it to poison its own anomaly baseline.

        Its own connection rather than the caller's transaction, deliberately.
        A record of spend that *already happened upstream* must survive the
        rollback of whatever the application was doing -- the money left the
        building whether or not this request succeeded.
        """
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.ai_spend_records
                    (workspace_id, provider, model, workflow_type,
                     prompt_tokens, completion_tokens, cost_usd, actor_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    workspace_id,
                    provider,
                    model,
                    workflow_type,
                    prompt_tokens,
                    completion_tokens,
                    cost_usd,
                    actor_id,
                ),
            )

    def spend_since(
        self,
        workspace_id: uuid.UUID,
        since: dt.datetime,
        until: dt.datetime | None = None,
    ) -> SpendSummary:
        """Return what a workspace spent over a window.

        Privileged, because anomaly detection compares two windows and must do so
        on the same basis regardless of who triggered the call being checked --
        including a background job with no user context at all.

        Args:
            workspace_id: The tenant to summarise.
            since: Window start, inclusive.
            until: Window end, exclusive. None means "up to now".
        """
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(SUM(cost_usd), 0),
                       COUNT(*),
                       COALESCE(SUM(prompt_tokens + completion_tokens), 0)
                FROM public.ai_spend_records
                WHERE workspace_id = %s
                  AND deleted_at IS NULL
                  AND created_at >= %s
                  AND (%s::timestamptz IS NULL OR created_at < %s)
                """,
                (workspace_id, since, until, until),
            )
            row = cursor.fetchone()

        if row is None:  # pragma: no cover - aggregate always returns a row
            return SpendSummary(Decimal(0), 0, 0)

        return SpendSummary(total_usd=row[0], call_count=row[1], total_tokens=row[2])

    @staticmethod
    def read_records_for_workspace(
        connection: psycopg.Connection,
        workspace_id: uuid.UUID,
        limit: int,
    ) -> list[dict[str, object]]:
        """Return a workspace's own spend history, newest first.

        Takes an already-authenticated connection rather than opening one, so
        this cannot accidentally run privileged -- the session's identity is the
        connection's, and this function has no way to widen it. The same defence
        `AuditRepository.read_for_workspace` uses.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT created_at, provider, model, workflow_type,
                       prompt_tokens, completion_tokens, cost_usd
                FROM public.ai_spend_records
                WHERE workspace_id = %s AND deleted_at IS NULL
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (workspace_id, limit),
            )

            return [
                {
                    "created_at": row[0].isoformat(),
                    "provider": row[1],
                    "model": row[2],
                    "workflow_type": row[3],
                    "prompt_tokens": row[4],
                    "completion_tokens": row[5],
                    "cost_usd": str(row[6]),
                }
                for row in cursor
            ]
