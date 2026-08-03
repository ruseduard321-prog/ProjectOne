"""Execution limits and the refusals every governance control raises.

CLAUDE.md §15a requires several bounds that are *not* about money and are not
about provider availability. They belong here because they share one property:
they bound a single run of work, in process, with no database involved.

## What lives here, and what deliberately does not

| Control | Here? | Where |
|---|---|---|
| Retry ceiling | No | `AIRouter` (STEP-17) |
| Fallback chain ceiling | No | `AIRouter` (STEP-17) |
| Availability breaker | No | `ProviderHealthTracker` (STEP-17) |
| **Recursion / chained-invocation cap** | **Yes** | `ExecutionBudget` |
| **Wall-clock limit per run** | **Yes** | `ExecutionBudget` |
| **Total-token limit per run** | **Yes** | `ExecutionBudget` |
| Spend ceiling | No | `AISpendService` (database) |
| Emergency shutdown | No | `AISpendService` (database) |

The split follows what the control is protecting. A spend ceiling protects
*money*, which is shared across every worker and therefore must live in the
database. An execution limit protects *one run* from itself -- a run exists in
one process, so per-process state is not an approximation here, it is the exact
scope.

## Why these are separate from the router's ceilings

STEP-17's two ceilings bound one `complete()` call at six upstream requests. They
say nothing about a workflow that calls `complete()` a hundred times, or an agent
that re-triggers itself.

That is the runaway CLAUDE.md §15a names specifically: *"any agent capable of
triggering another agent or re-triggering itself must have an explicit, low,
hard-coded cap on chained/recursive invocations, independent of and in addition
to its retry limit."* Six calls per `complete()` multiplied by an unbounded
number of `complete()`s is unbounded.

## Failing loudly

§15a is explicit that a workflow hitting a ceiling **fails loudly** rather than
silently continuing. Every limit here raises. None of them returns a flag a
caller could ignore, and none returns a degraded result that would let a run
proceed past its own bound while looking like it succeeded.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.ai.errors import ProviderError
from app.core.logging import get_logger, log_context

logger = get_logger(__name__)

#: Hard ceiling on chained or recursive AI invocations within one run.
#:
#: **Low deliberately.** CLAUDE.md §15a asks for an "explicit, low, hard-coded
#: cap", and the reasoning is that a legitimate workflow needing more than a
#: handful of chained AI steps is rare, while a runaway needing exactly one more
#: than the cap is not a thing that happens. Five permits a genuine
#: generate -> critique -> regenerate -> verify chain and stops a loop.
DEFAULT_MAX_CHAINED_INVOCATIONS = 5

#: Wall-clock ceiling for one run, in seconds.
#:
#: Independent of the per-attempt provider timeout (30s) and of the retry
#: ceiling: a run making six sequential calls each finishing just inside the
#: provider timeout would take three minutes while breaching neither. This is
#: the bound on the *whole* run.
DEFAULT_MAX_RUN_SECONDS = 300.0

#: Total tokens one run may consume across every call it makes.
#:
#: A third bound, and it catches what neither of the others does: a run that
#: stays under the invocation cap and finishes quickly can still consume an
#: enormous number of tokens if each call is large. §15a requires a ceiling on
#: "steps, wall-clock duration, and total token/cost consumption per run" -- all
#: three, because each has a runaway shape the others do not catch.
DEFAULT_MAX_RUN_TOKENS = 500_000


class GovernanceError(ProviderError):
    """A call was refused by a cost governance control.

    Subclasses `ProviderError` so that a caller already handling AI failures
    handles these too rather than seeing an unexpected exception type. That
    inheritance is deliberate but it is **not** a claim that a provider failed:
    every subclass below is raised *before or instead of* any provider call, and
    `public_message` says so.

    Crucially, these are neither `RetryableProviderError` nor
    `TerminalProviderError`. The router branches on those two, and a governance
    refusal must not be routed to the next provider -- falling back on a budget
    refusal would spend the *other* provider's budget on a call that was already
    denied. Sitting outside both branches means the router cannot mistake one
    for a provider failure.
    """

    public_message = "This request was refused by a cost control"


class BudgetExceededError(GovernanceError):
    """The workspace has reached a configured spend ceiling.

    Raised **before** the provider is called. That ordering is the whole point:
    a ceiling checked after the call is an invoice.
    """

    public_message = "This workspace has reached its AI spending limit"


class SpendBreakerOpenError(GovernanceError):
    """The spend circuit breaker has tripped for this workspace or workflow.

    Distinct from `ProviderUnavailableError`, and the distinction is what makes
    this breaker meaningful: an availability failure means *try somewhere else*,
    while a spend breaker means **stop**. Routing this to a fallback provider
    would defeat the control entirely.
    """

    public_message = "AI spending has been paused for this workspace pending review"


class AIShutdownError(GovernanceError):
    """AI spend is disabled by an emergency shutdown switch.

    Covers all three scopes CLAUDE.md §15a requires -- one workspace, one
    workflow type, or the whole platform. The message deliberately does not
    distinguish them: a tenant learning that a *platform-wide* shutdown is in
    effect learns about an incident affecting other customers.
    """

    public_message = "AI features are temporarily disabled"


class ExecutionLimitExceededError(GovernanceError):
    """A run hit its wall-clock, token, or chained-invocation ceiling.

    Loud by construction: §15a requires that a workflow hitting a ceiling fails
    rather than silently continuing, so this raises rather than returning a
    signal a caller could drop.
    """

    public_message = "This AI workflow exceeded its execution limits"


@dataclass
class ExecutionBudget:
    """The bounds on one run of AI work, and the tally against them.

    **One instance per run, never shared.** It is mutable accumulated state
    scoped to a single logical unit of work -- a chat turn, an agent execution --
    and sharing one across runs would make every run consume its predecessors'
    allowance.

    Not thread-safe, and deliberately so. A run is sequential by definition; a
    budget being mutated from two threads means two runs are sharing one, which
    is the misuse a lock would hide rather than prevent.

    Mutable rather than frozen because it *is* the tally. Replacing the whole
    object on each increment would read as immutability while achieving nothing
    (the same reasoning as `ProviderHealth`).
    """

    max_invocations: int = DEFAULT_MAX_CHAINED_INVOCATIONS
    max_seconds: float = DEFAULT_MAX_RUN_SECONDS
    max_tokens: int = DEFAULT_MAX_RUN_TOKENS

    #: When the run started, on the monotonic clock. Monotonic rather than wall
    #: clock so an NTP correction mid-run cannot extend or collapse the limit.
    started_at: float = field(default_factory=time.monotonic)

    invocations: int = 0
    tokens_used: int = 0

    def __post_init__(self) -> None:
        """Refuse a budget that permits nothing or is unbounded.

        Raises:
            ValueError: if any limit is below 1. A zero ceiling would refuse
                every run before its first call, and a negative one would be
                silently unbounded on the comparisons below -- both are
                misconfigurations that should fail at construction rather than
                per run, the same rule `AIRouter` applies to its own ceilings.
        """
        if self.max_invocations < 1:
            raise ValueError("max_invocations must be at least 1")

        if self.max_seconds <= 0:
            raise ValueError("max_seconds must be positive")

        if self.max_tokens < 1:
            raise ValueError("max_tokens must be at least 1")

    def elapsed(self, now: float | None = None) -> float:
        """Return how long this run has been going, in seconds.

        `now` is injectable so a test can assert a timeout without sleeping for
        one -- the same reasoning as `ProviderHealthTracker`. A test that sleeps
        for a real five-minute ceiling is a test nobody runs.
        """
        moment = time.monotonic() if now is None else now
        return moment - self.started_at

    def check(self, now: float | None = None) -> None:
        """Raise if this run has already exhausted any of its ceilings.

        Called **before** each invocation rather than after, so a run that has
        already spent its allowance does not get to make one more call on the
        way out.

        Raises:
            ExecutionLimitExceededError: naming which ceiling was hit. The
                specific limit is in the internal message rather than the public
                one -- an operator needs to know which bound tripped, a caller
                needs only to know the run was refused.
        """
        if self.invocations >= self.max_invocations:
            self._refuse("chained_invocations", self.invocations, self.max_invocations)

        elapsed = self.elapsed(now)
        if elapsed >= self.max_seconds:
            self._refuse("wall_clock_seconds", elapsed, self.max_seconds)

        if self.tokens_used >= self.max_tokens:
            self._refuse("total_tokens", self.tokens_used, self.max_tokens)

    def record_invocation(self, tokens: int = 0) -> None:
        """Count one completed AI call against this run.

        Args:
            tokens: What the call consumed, from the provider's own reported
                usage. Zero when a call failed before returning usage -- the
                invocation still counts, because a failing call that did not
                count would let a run retry forever at the workflow level while
                the router's own ceiling only ever saw single calls.
        """
        self.invocations += 1
        self.tokens_used += tokens

    def _refuse(self, limit: str, reached: float, ceiling: float) -> None:
        """Log the breach and raise.

        Raises:
            ExecutionLimitExceededError: always. The return type is None rather
                than NoReturn because mypy then requires every caller to treat
                the call as terminating, which it does -- but keeping it None
                lets `check` read as a sequence of guards.
        """
        logger.warning(
            log_context(
                event="ai_execution_limit_exceeded",
                limit=limit,
                reached=reached,
                ceiling=ceiling,
            )
        )
        raise ExecutionLimitExceededError(
            f"Run exceeded its {limit} ceiling: {reached} of {ceiling}"
        )
