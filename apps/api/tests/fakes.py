"""Test doubles shared across suites.

## Why a fake spend repository rather than a database

The governance *logic* -- the ordering of the checks, the reservation/settlement
pairing, the anomaly comparison -- is application behaviour, and asserting it
against a live database would make the whole suite require PostgreSQL to prove
something PostgreSQL is not responsible for.

**What this fake deliberately does not claim to prove** is the part that is
genuinely the database's: that `try_reserve` is atomic under concurrency, and
that RLS keeps one workspace's spend records away from another's. A fake cannot
demonstrate either, and a test that pretended to would be worse than no test.
Those live in `test_ai_spend_isolation.py`, against a real database, exactly like
the RLS isolation suites.

The fake still models the real semantics closely enough to be meaningful:
compare-and-increment against every applicable budget, all-or-nothing across
them, breaker respected, period reset on expiry. Where it diverges from the real
repository the divergence is noted at the method.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from app.repositories.ai_spend import Budget, SpendSummary


class FakeSpendRepository:
    """An in-memory stand-in for `AISpendRepository`.

    Structurally compatible rather than a subclass: it implements the methods
    `AISpendService` calls, and nothing else. Subclassing would inherit the real
    connection handling, which is the one thing a fake must not have.
    """

    def __init__(self) -> None:
        """Start with no budgets, no records and no shutdown switches."""
        self.budgets: dict[tuple[uuid.UUID, str | None], Budget] = {}
        self.records: list[dict[str, object]] = []
        self.shutdowns: list[tuple[uuid.UUID | None, str | None, str]] = []
        self.settlements: list[tuple[Decimal, Decimal]] = []

    # -- budgets -------------------------------------------------------

    def add_budget(
        self,
        workspace_id: uuid.UUID,
        limit_usd: Decimal,
        workflow_type: str | None = None,
        spent_usd: Decimal = Decimal(0),
        period_started_at: dt.datetime | None = None,
        period_interval: dt.timedelta = dt.timedelta(days=30),
    ) -> Budget:
        """Seed a ceiling. Test-only; the real repository has `upsert_budget`."""
        budget = Budget(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            workflow_type=workflow_type,
            limit_usd=limit_usd,
            spent_usd=spent_usd,
            period_started_at=period_started_at or dt.datetime.now(dt.UTC),
            period_interval=period_interval,
            breaker_tripped_at=None,
            breaker_reason=None,
        )
        self.budgets[(workspace_id, workflow_type)] = budget

        return budget

    def _applicable(self, workspace_id: uuid.UUID, workflow_type: str) -> list[Budget]:
        """Return the workspace-wide and workflow-scoped budgets, in that order."""
        return [
            budget
            for key, budget in sorted(self.budgets.items(), key=lambda item: str(item[0][1]))
            if key[0] == workspace_id and key[1] in (None, workflow_type)
        ]

    def budgets_for(self, workspace_id: uuid.UUID, workflow_type: str) -> tuple[Budget, ...]:
        """Return applicable ceilings, resetting any whose period has elapsed."""
        now = dt.datetime.now(dt.UTC)

        for key, budget in list(self.budgets.items()):
            if key[0] != workspace_id:
                continue

            if budget.period_started_at + budget.period_interval <= now:
                # Matches `_reset_expired`: the running total resets, the breaker
                # deliberately does not.
                self.budgets[key] = Budget(
                    id=budget.id,
                    workspace_id=budget.workspace_id,
                    workflow_type=budget.workflow_type,
                    limit_usd=budget.limit_usd,
                    spent_usd=Decimal(0),
                    period_started_at=now,
                    period_interval=budget.period_interval,
                    breaker_tripped_at=budget.breaker_tripped_at,
                    breaker_reason=budget.breaker_reason,
                )

        return tuple(self._applicable(workspace_id, workflow_type))

    def try_reserve(
        self,
        workspace_id: uuid.UUID,
        workflow_type: str,
        amount_usd: Decimal,
    ) -> bool:
        """Reserve against every applicable ceiling, all or nothing.

        Models the real method's semantics, including the all-or-nothing
        property: a reservation refused by one budget un-reserves the others.

        It does **not** model atomicity under concurrency -- a single-threaded
        fake cannot. `test_ai_spend_isolation.py` covers that against a real
        database.
        """
        applicable = self._applicable(workspace_id, workflow_type)

        if not applicable:
            return True

        reserved: list[tuple[uuid.UUID, str | None]] = []

        for budget in applicable:
            key = (budget.workspace_id, budget.workflow_type)
            current = self.budgets[key]

            if current.breaker_tripped_at is not None or (
                current.spent_usd + amount_usd > current.limit_usd
            ):
                for undo_key in reserved:
                    undone = self.budgets[undo_key]
                    self.budgets[undo_key] = self._with_spent(undone, undone.spent_usd - amount_usd)
                return False

            self.budgets[key] = self._with_spent(current, current.spent_usd + amount_usd)
            reserved.append(key)

        return True

    def settle(
        self,
        workspace_id: uuid.UUID,
        workflow_type: str,
        reserved_usd: Decimal,
        actual_usd: Decimal,
    ) -> None:
        """Adjust every applicable ceiling by the difference."""
        self.settlements.append((reserved_usd, actual_usd))
        adjustment = actual_usd - reserved_usd

        for budget in self._applicable(workspace_id, workflow_type):
            key = (budget.workspace_id, budget.workflow_type)
            current = self.budgets[key]
            self.budgets[key] = self._with_spent(
                current, max(Decimal(0), current.spent_usd + adjustment)
            )

    @staticmethod
    def _with_spent(budget: Budget, spent: Decimal) -> Budget:
        """Return a copy of a budget with a new running total."""
        return Budget(
            id=budget.id,
            workspace_id=budget.workspace_id,
            workflow_type=budget.workflow_type,
            limit_usd=budget.limit_usd,
            spent_usd=spent,
            period_started_at=budget.period_started_at,
            period_interval=budget.period_interval,
            breaker_tripped_at=budget.breaker_tripped_at,
            breaker_reason=budget.breaker_reason,
        )

    def trip_breaker(
        self,
        workspace_id: uuid.UUID,
        workflow_type: str | None,
        reason: str,
    ) -> bool:
        """Open the spend breaker, idempotently."""
        key = (workspace_id, workflow_type)
        budget = self.budgets.get(key)

        if budget is None or budget.breaker_tripped_at is not None:
            return False

        self.budgets[key] = Budget(
            id=budget.id,
            workspace_id=budget.workspace_id,
            workflow_type=budget.workflow_type,
            limit_usd=budget.limit_usd,
            spent_usd=budget.spent_usd,
            period_started_at=budget.period_started_at,
            period_interval=budget.period_interval,
            breaker_tripped_at=dt.datetime.now(dt.UTC),
            breaker_reason=reason,
        )

        return True

    def reset_breaker(self, workspace_id: uuid.UUID, workflow_type: str | None) -> bool:
        """Close a tripped spend breaker.

        Rebuilt explicitly rather than through `_with_spent`, which deliberately
        *preserves* breaker state -- using it here left the breaker tripped while
        reporting success, which is the one outcome a reset must not produce.
        """
        key = (workspace_id, workflow_type)
        budget = self.budgets.get(key)

        if budget is None or budget.breaker_tripped_at is None:
            return False

        self.budgets[key] = Budget(
            id=budget.id,
            workspace_id=budget.workspace_id,
            workflow_type=budget.workflow_type,
            limit_usd=budget.limit_usd,
            spent_usd=budget.spent_usd,
            period_started_at=budget.period_started_at,
            period_interval=budget.period_interval,
            breaker_tripped_at=None,
            breaker_reason=None,
        )

        return True

    # -- shutdown ------------------------------------------------------

    def active_shutdown(self, workspace_id: uuid.UUID, workflow_type: str) -> str | None:
        """Return the newest matching switch's reason, across all three scopes."""
        for scope_workspace, scope_workflow, reason in reversed(self.shutdowns):
            workspace_matches = scope_workspace is None or scope_workspace == workspace_id
            workflow_matches = scope_workflow is None or scope_workflow == workflow_type

            if workspace_matches and workflow_matches:
                return reason

        return None

    def set_platform_shutdown(
        self,
        reason: str,
        workflow_type: str | None = None,
        activated_by: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Disable AI spend platform-wide."""
        self.shutdowns.append((None, workflow_type, reason))
        return uuid.uuid4()

    def set_workspace_shutdown(
        self,
        workspace_id: uuid.UUID,
        reason: str,
        workflow_type: str | None = None,
        activated_by: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Disable AI spend for one workspace."""
        self.shutdowns.append((workspace_id, workflow_type, reason))
        return uuid.uuid4()

    def lift_shutdown(self, switch_id: uuid.UUID) -> bool:
        """Clear every switch. Coarser than the real method, which lifts one."""
        had_any = bool(self.shutdowns)
        self.shutdowns.clear()

        return had_any

    # -- ledger --------------------------------------------------------

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
        """Append a spend record."""
        self.records.append(
            {
                "workspace_id": workspace_id,
                "provider": provider,
                "model": model,
                "workflow_type": workflow_type,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost_usd": cost_usd,
                "actor_id": actor_id,
                "created_at": dt.datetime.now(dt.UTC),
            }
        )

    def spend_since(
        self,
        workspace_id: uuid.UUID,
        since: dt.datetime,
        until: dt.datetime | None = None,
    ) -> SpendSummary:
        """Summarise recorded spend over a window."""
        matching = [
            record
            for record in self.records
            if record["workspace_id"] == workspace_id
            and isinstance(record["created_at"], dt.datetime)
            and record["created_at"] >= since
            and (until is None or record["created_at"] < until)
        ]

        total = sum(
            (record["cost_usd"] for record in matching if isinstance(record["cost_usd"], Decimal)),
            Decimal(0),
        )
        tokens = sum(
            int(record["prompt_tokens"]) + int(record["completion_tokens"])  # type: ignore[call-overload]
            for record in matching
        )

        return SpendSummary(total_usd=total, call_count=len(matching), total_tokens=tokens)
