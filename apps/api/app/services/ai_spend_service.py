"""Enforces every spend control that stands between a request and a provider call.

CLAUDE.md §15a in one class. The ordering of the checks is the contract, and it
runs cheapest-and-most-absolute first:

    1. Emergency shutdown   -- is spending disabled at all?
    2. Spend circuit breaker -- has this workspace been stopped for review?
    3. Budget reservation    -- is there room under every applicable ceiling?
    -> the provider call happens here, and only here
    4. Settlement            -- replace the reservation with the real cost
    5. Ledger + anomaly      -- record it, and check it against the baseline

Steps 1-3 all happen **before** any provider is contacted. That is the property
the whole step exists to establish: a ceiling checked after the call is an
invoice, and an invoice is not a control.

## Why this is a context manager rather than two methods

`reserve()` and `settle()` as a public pair would be a control a caller can
forget half of -- and the half they would forget is the settlement, because it
happens on the *failure* path where nobody is looking. A leaked reservation
permanently reduces a workspace's ceiling, silently, until someone notices their
budget shrinking.

`guard()` makes the pairing structural: the reservation is released in a
`finally`, so it settles whether the call returned, raised, or was abandoned. A
caller cannot use the reservation without also getting the settlement.

## What this class deliberately does not do

- **It does not choose a provider.** That is `AIRouter`.
- **It does not retry.** Retries are the router's ceiling, and a governance
  layer that retried would multiply the spend it exists to bound.
- **It does not fall back.** A governance refusal must stop the call, never
  route it to another provider -- that would spend the *other* provider's budget
  on a call that was already denied.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal

from app.ai.governance import (
    AIShutdownError,
    BudgetExceededError,
    SpendBreakerOpenError,
)
from app.ai.pricing import cost_of
from app.ai.provider import TokenUsage
from app.core.logging import get_logger, log_context
from app.repositories.ai_spend import AISpendRepository

logger = get_logger(__name__)

#: How far back the anomaly baseline looks.
#:
#: Seven days rather than a fixed calendar period, so a workspace's baseline
#: covers a full weekly cycle -- weekday and weekend usage differ enough that a
#: shorter window makes Monday look anomalous every week.
BASELINE_WINDOW = dt.timedelta(days=7)

#: The recent window compared against that baseline.
RECENT_WINDOW = dt.timedelta(hours=1)

#: How many times its own hourly baseline a workspace may spend before this is
#: treated as anomalous.
#:
#: CLAUDE.md §15a requires "automatic alerting when usage deviates sharply from
#: that workspace's baseline" -- per workspace, not against a global average,
#: because a large customer's normal hour is a small customer's emergency.
#:
#: Ten is deliberately loose. This is an *alerting* threshold on real customer
#: behaviour, and a tight one produces alerts nobody reads, which is
#: indistinguishable from no alerting at all.
ANOMALY_MULTIPLIER = Decimal("10")

#: Below this hourly spend, the multiplier is not applied at all.
#:
#: Without a floor, a workspace whose baseline is a fraction of a cent trips the
#: multiplier on its second real call -- ten times almost nothing is still almost
#: nothing, and alerting on it is noise that trains an operator to ignore the
#: signal.
ANOMALY_FLOOR_USD = Decimal("1.00")


@dataclass(frozen=True)
class SpendDecision:
    """Why a call was permitted or refused, as data rather than as a log line.

    Returned and asserted on for the same reason `SelectionReason` is: a control
    whose behaviour can only be confirmed by reading log output is a control
    nobody can test, and CLAUDE.md §15 requires AI decisions to be observable
    rather than inferred.
    """

    permitted: bool
    reserved_usd: Decimal
    reason: str
    #: The tightest applicable ceiling, when one is configured. Surfaced so a
    #: refusal can tell a user how much room they had -- an honest refusal
    #: (CLAUDE.md §15a: graceful degradation says what happened).
    limit_usd: Decimal | None = None
    remaining_usd: Decimal | None = None


class AISpendService:
    """The gate every AI call passes through before it reaches a provider."""

    def __init__(
        self,
        repository: AISpendRepository,
        anomaly_multiplier: Decimal = ANOMALY_MULTIPLIER,
        anomaly_floor_usd: Decimal = ANOMALY_FLOOR_USD,
    ) -> None:
        """Wire the service to its store and its anomaly thresholds.

        The thresholds are constructor parameters rather than module constants
        read directly, so a deployment can tune them and a test can assert
        tripping behaviour without waiting for real spend to accumulate.
        """
        self._repository = repository
        self._anomaly_multiplier = anomaly_multiplier
        self._anomaly_floor = anomaly_floor_usd

    # ------------------------------------------------------------------
    # The gate
    # ------------------------------------------------------------------

    def check_permitted(
        self,
        workspace_id: uuid.UUID,
        workflow_type: str,
        estimated_usd: Decimal,
    ) -> SpendDecision:
        """Decide whether a call may proceed, without reserving anything.

        Separate from `guard()` so a caller can ask "would this be allowed"
        without side effects -- a settings screen showing remaining budget, or a
        pre-flight check on a batch. **Not** a substitute for `guard()`: the
        answer is stale the instant it returns, which is precisely why the real
        enforcement is an atomic reservation rather than this.

        Raises:
            AIShutdownError: AI spend is disabled in some scope covering this
                workspace.
            SpendBreakerOpenError: the spend breaker has tripped.
        """
        shutdown = self._repository.active_shutdown(workspace_id, workflow_type)

        if shutdown is not None:
            logger.warning(
                log_context(
                    event="ai_call_refused_shutdown",
                    workspace_id=workspace_id,
                    workflow_type=workflow_type,
                    reason=shutdown,
                )
            )
            raise AIShutdownError(f"AI spend is disabled: {shutdown}")

        budgets = self._repository.budgets_for(workspace_id, workflow_type)

        for budget in budgets:
            if budget.is_breaker_open:
                logger.warning(
                    log_context(
                        event="ai_call_refused_breaker_open",
                        workspace_id=workspace_id,
                        workflow_type=workflow_type,
                        scope=budget.workflow_type or "workspace",
                        reason=budget.breaker_reason or "unspecified",
                    )
                )
                raise SpendBreakerOpenError(
                    f"Spend breaker is open for {budget.workflow_type or 'this workspace'}: "
                    f"{budget.breaker_reason}"
                )

        if not budgets:
            return SpendDecision(
                permitted=True,
                reserved_usd=Decimal(0),
                reason="no_budget_configured",
            )

        # The tightest ceiling is what a refusal should quote -- the one the call
        # would actually hit first.
        tightest = min(budgets, key=lambda budget: budget.remaining_usd)

        if estimated_usd > tightest.remaining_usd:
            return SpendDecision(
                permitted=False,
                reserved_usd=Decimal(0),
                reason="budget_exceeded",
                limit_usd=tightest.limit_usd,
                remaining_usd=tightest.remaining_usd,
            )

        return SpendDecision(
            permitted=True,
            reserved_usd=Decimal(0),
            reason="within_budget",
            limit_usd=tightest.limit_usd,
            remaining_usd=tightest.remaining_usd,
        )

    @contextmanager
    def guard(
        self,
        workspace_id: uuid.UUID,
        workflow_type: str,
        estimated_usd: Decimal,
        actor_id: uuid.UUID | None = None,
    ) -> Iterator[SpendLedgerEntry]:
        """Reserve budget, yield a settlement handle, and always settle.

        The only sanctioned way to spend money on an AI call. Everything before
        the `yield` happens before a provider is contacted; the `finally`
        guarantees the reservation is released even when the call raises.

        Usage::

            with spend.guard(workspace_id, "chat", estimate) as entry:
                response = router.complete(...)
                entry.record(response.provider, response.model, response.usage)

        A caller that never calls `entry.record` still settles -- to zero actual
        cost, which returns the whole reservation. That is the correct outcome
        for a call that failed before reaching a provider: nothing was spent
        upstream, so nothing should be charged.

        Raises:
            AIShutdownError: spending is disabled in a scope covering this call.
            SpendBreakerOpenError: the spend breaker has tripped.
            BudgetExceededError: no applicable ceiling had room. Raised **before
                the provider is called**, which is the whole point.
        """
        with self._session():
            yield from self._guarded(workspace_id, workflow_type, estimated_usd, actor_id)

    @contextmanager
    def _session(self) -> Iterator[None]:
        """Hold one database connection for the whole guarded call, when possible.

        One governed call makes eight repository calls, and a connection each is
        eight connections per AI request -- against a Supabase session pooler
        whose ceiling is 15, which two concurrent calls would exhaust. Observed
        during STEP-18 validation as `EMAXCONNSESSION` from the pooler.

        Degrades to a no-op for any repository without `session()`, which is what
        keeps `tests/fakes.py` a stand-in for the methods the service calls
        rather than for its connection handling.
        """
        session = getattr(self._repository, "session", None)

        if session is None:
            yield
            return

        with session():
            yield

    def _guarded(
        self,
        workspace_id: uuid.UUID,
        workflow_type: str,
        estimated_usd: Decimal,
        actor_id: uuid.UUID | None,
    ) -> Iterator[SpendLedgerEntry]:
        """Run the reserve/yield/settle sequence. See `guard`."""
        decision = self.check_permitted(workspace_id, workflow_type, estimated_usd)

        if not decision.permitted:
            logger.warning(
                log_context(
                    event="ai_call_refused_budget",
                    workspace_id=workspace_id,
                    workflow_type=workflow_type,
                    estimated_usd=str(estimated_usd),
                    remaining_usd=str(decision.remaining_usd),
                )
            )
            raise BudgetExceededError(
                f"Estimated cost {estimated_usd} exceeds remaining budget {decision.remaining_usd}"
            )

        # The atomic reservation. `check_permitted` above is advisory -- it reads
        # a value that another worker may already have consumed. This is the
        # enforcement, and it is a compare-and-increment inside one statement so
        # two concurrent calls cannot both be granted the same headroom.
        if not self._repository.try_reserve(workspace_id, workflow_type, estimated_usd):
            logger.warning(
                log_context(
                    event="ai_call_refused_reservation",
                    workspace_id=workspace_id,
                    workflow_type=workflow_type,
                    estimated_usd=str(estimated_usd),
                )
            )
            raise BudgetExceededError(
                "The workspace's AI budget was exhausted while this request was starting"
            )

        entry = SpendLedgerEntry(estimated_usd)

        try:
            yield entry
        finally:
            # Settled unconditionally. A reservation that leaks on the failure
            # path permanently shrinks the workspace's ceiling, and it does so
            # silently -- the worst shape a bug in a spend control can take.
            self._repository.settle(
                workspace_id=workspace_id,
                workflow_type=workflow_type,
                reserved_usd=estimated_usd,
                actual_usd=entry.actual_usd,
            )

            if entry.recorded:
                self._write_ledger(workspace_id, workflow_type, entry, actor_id)

    def _write_ledger(
        self,
        workspace_id: uuid.UUID,
        workflow_type: str,
        entry: SpendLedgerEntry,
        actor_id: uuid.UUID | None,
    ) -> None:
        """Append the spend record and check the result against the baseline."""
        self._repository.record(
            workspace_id=workspace_id,
            provider=entry.provider,
            model=entry.model,
            workflow_type=workflow_type,
            prompt_tokens=entry.usage.prompt_tokens,
            completion_tokens=entry.usage.completion_tokens,
            cost_usd=entry.actual_usd,
            actor_id=actor_id,
        )

        logger.info(
            log_context(
                event="ai_spend_recorded",
                workspace_id=workspace_id,
                workflow_type=workflow_type,
                provider=entry.provider,
                model=entry.model,
                total_tokens=entry.usage.total_tokens,
                cost_usd=str(entry.actual_usd),
            )
        )

        self.check_for_anomaly(workspace_id, workflow_type)

    # ------------------------------------------------------------------
    # Anomaly detection
    # ------------------------------------------------------------------

    def check_for_anomaly(
        self,
        workspace_id: uuid.UUID,
        workflow_type: str,
        now: dt.datetime | None = None,
    ) -> bool:
        """Compare recent spend to this workspace's own baseline, and trip if wild.

        CLAUDE.md §15a requires near-real-time usage monitoring with automatic
        alerting when spend deviates sharply from **that workspace's** baseline.
        Against its own history rather than a platform average, because a large
        customer's ordinary hour is a small customer's emergency.

        When the deviation is extreme this does not merely alert -- it trips the
        spend breaker, which stops subsequent calls. An anomaly detector that only
        logged would be a dashboard, and §15a is explicit that this is an
        observability *requirement* with teeth, not an optional panel.

        Args:
            workspace_id: The tenant to evaluate.
            workflow_type: The scope the breaker would be tripped on.
            now: Injectable so a test can position the windows without waiting.

        Returns:
            True when an anomaly was detected and the breaker was tripped.
        """
        moment = now if now is not None else dt.datetime.now(dt.UTC)

        recent = self._repository.spend_since(workspace_id, moment - RECENT_WINDOW, moment)

        if recent.total_usd < self._anomaly_floor:
            # Below the floor, the multiplier is meaningless -- ten times almost
            # nothing is almost nothing. Returning early here is what keeps this
            # from alerting on every new workspace's second call.
            return False

        baseline = self._repository.spend_since(
            workspace_id,
            moment - BASELINE_WINDOW,
            moment - RECENT_WINDOW,
        )

        # Hourly average over the baseline window, excluding the recent window so
        # the anomaly is not compared against itself.
        baseline_hours = Decimal((BASELINE_WINDOW - RECENT_WINDOW).total_seconds()) / 3600
        hourly_baseline = baseline.total_usd / baseline_hours

        # A workspace with no history has no baseline to deviate from. The floor
        # above is what protects that case: a first hour above the floor is
        # notable, but it is not a *deviation*, and treating it as one would trip
        # the breaker on every workspace's first serious day of use.
        if hourly_baseline <= 0:
            logger.info(
                log_context(
                    event="ai_spend_no_baseline",
                    workspace_id=workspace_id,
                    recent_usd=str(recent.total_usd),
                )
            )
            return False

        ratio = recent.total_usd / hourly_baseline

        if ratio < self._anomaly_multiplier:
            return False

        logger.error(
            log_context(
                event="ai_spend_anomaly_detected",
                workspace_id=workspace_id,
                workflow_type=workflow_type,
                recent_usd=str(recent.total_usd),
                hourly_baseline_usd=str(hourly_baseline),
                ratio=str(ratio),
                threshold=str(self._anomaly_multiplier),
            )
        )

        return self._repository.trip_breaker(
            workspace_id,
            workflow_type,
            f"Spend anomaly: {recent.total_usd} in the last hour against a "
            f"baseline of {hourly_baseline} per hour",
        )


@dataclass
class SpendLedgerEntry:
    """The handle `guard()` yields, carrying what a call actually cost.

    Mutable because it is filled in *after* the reservation and *during* the
    call it describes -- it is the one piece of state that cannot be known when
    the guard opens.

    Starts at zero actual cost deliberately. A guard whose body raised before
    reaching a provider settles to zero, returning the whole reservation, which
    is the correct accounting for money that was never spent.
    """

    reserved_usd: Decimal
    actual_usd: Decimal = Decimal(0)
    provider: str = ""
    model: str = ""
    usage: TokenUsage = TokenUsage()
    recorded: bool = False

    def record(self, provider: str, model: str, usage: TokenUsage) -> Decimal:
        """Set what the call actually consumed, and price it.

        Priced from the provider's own reported usage through `app.ai.pricing`,
        never from `AIProvider.cost_per_1k_tokens` -- that value is a selection
        heuristic, and billing against it would mean a change to how providers
        are compared silently changed what customers are charged.

        Returns:
            The computed cost, so a caller can surface it.
        """
        self.provider = provider
        self.model = model
        self.usage = usage
        self.actual_usd = cost_of(model, usage)
        self.recorded = True

        return self.actual_usd
