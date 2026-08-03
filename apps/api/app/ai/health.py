"""Provider health, so a failing provider leaves rotation instead of being retried forever.

[[AI Providers]] puts an **availability check** between capability and cost in
the selection flow. This is what answers it. Without it, a provider in a total
outage is selected first on every single request, burns the full retry ceiling,
and only then falls back -- so every user pays the latency of a known-dead
provider, over and over, for the entire duration of the outage.

## The design, and what it deliberately is not

This is a **circuit breaker on availability, not on spend.** The distinction
matters because CLAUDE.md §15a requires a spend circuit breaker too, and that
one is [[STEP-18 AI Cost Governance Controls]]'. Conflating them would put spend
enforcement in a module whose failure mode is "a provider is skipped", which is
far too soft a consequence for a budget ceiling.

Three states, and the third is the one that makes recovery possible:

| State | Meaning | Selection |
|---|---|---|
| `HEALTHY` | Under the failure threshold | Eligible |
| `UNHEALTHY` | Threshold reached, cooldown running | **Skipped** |
| `RECOVERING` | Cooldown elapsed, not yet proven | Eligible, one probe |

Without `RECOVERING`, an unhealthy provider would need a successful call to
become healthy and would never be selected to make one -- a provider that fails
once during a blip is out of rotation until the process restarts. The cooldown
expiring admits exactly one request as a probe; that request's outcome decides
whether the provider returns to `HEALTHY` or serves another cooldown.

## In-process, per worker, and that is a stated limitation

Health lives in memory, so N workers each track it independently and a provider
must fail `threshold` times *per worker* to leave rotation there. This mirrors
the rate limiter's own approximation (ADR-002 Future Evolution) and has the same
resolution -- a shared store is a new infrastructure dependency requiring its own
ADR (CLAUDE.md §10, §28), not something to introduce inside an unrelated step.

The approximation is safe in the direction that matters: it makes the breaker
*slower* to open, never slower to close. A provider is never skipped when it is
actually healthy; it is only kept in rotation slightly longer than ideal.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import StrEnum

from app.core.logging import get_logger, log_context

logger = get_logger(__name__)

#: Consecutive failures before a provider leaves rotation.
#:
#: Three rather than one: a single failure is noise -- a dropped connection, one
#: unlucky timeout -- and removing a healthy provider on noise costs more than
#: the one wasted call it saves. Three consecutive failures with no success
#: between them is a signal.
DEFAULT_FAILURE_THRESHOLD = 3

#: How long an unhealthy provider stays out of rotation before being probed.
#:
#: Thirty seconds is short enough that a brief outage does not park a provider
#: for the rest of the process's life, and long enough that a sustained outage
#: is not probed on every request. It is configuration, not a constant of
#: nature -- `ProviderHealthTracker` takes it as a parameter.
DEFAULT_COOLDOWN_SECONDS = 30.0


class HealthState(StrEnum):
    """Where a provider stands with the breaker."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    RECOVERING = "recovering"


@dataclass
class ProviderHealth:
    """One provider's failure record.

    Mutable, unlike most of this codebase's dataclasses, because it *is* the
    mutable state -- freezing it would mean replacing the whole record on every
    call, which reads as immutability while achieving nothing.
    """

    consecutive_failures: int = 0
    unhealthy_since: float | None = None
    total_failures: int = 0
    total_successes: int = 0


class ProviderHealthTracker:
    """Tracks provider failures and answers whether one may be selected.

    Thread-safe: FastAPI runs sync endpoints in a thread pool, so two requests
    genuinely can record failures concurrently. The lock is held only around
    dictionary mutation, never across a provider call.
    """

    def __init__(
        self,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        """Configure the breaker's thresholds.

        Args:
            failure_threshold: Consecutive failures before removal from rotation.
            cooldown_seconds: How long removal lasts before a probe is admitted.
        """
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds
        self._health: dict[str, ProviderHealth] = {}
        self._lock = threading.Lock()

    def state_of(self, provider: str, now: float | None = None) -> HealthState:
        """Return the provider's current state.

        Args:
            provider: The provider's stable name.
            now: Current time, injectable so tests assert cooldown expiry
                without sleeping. A test that sleeps for a real cooldown is a
                test nobody runs often enough to catch a regression.

        Returns:
            The state selection should act on.
        """
        moment = time.monotonic() if now is None else now

        with self._lock:
            record = self._health.get(provider)

            if record is None or record.unhealthy_since is None:
                return HealthState.HEALTHY

            if moment - record.unhealthy_since >= self._cooldown_seconds:
                return HealthState.RECOVERING

            return HealthState.UNHEALTHY

    def is_available(self, provider: str, now: float | None = None) -> bool:
        """Return whether the provider may be selected.

        `RECOVERING` counts as available -- that is the probe. A provider that
        could never be selected while unhealthy could never demonstrate recovery.
        """
        return self.state_of(provider, now) is not HealthState.UNHEALTHY

    def record_success(self, provider: str) -> None:
        """Clear a provider's failure record.

        Resets rather than decrements: the threshold counts *consecutive*
        failures, so any success ends the run. Decrementing would let a provider
        failing every other call hover just under the threshold forever.
        """
        with self._lock:
            record = self._health.setdefault(provider, ProviderHealth())
            recovered = record.unhealthy_since is not None

            record.consecutive_failures = 0
            record.unhealthy_since = None
            record.total_successes += 1

        if recovered:
            # Worth a line at info: a provider returning to rotation is the
            # other half of the story whose first half was logged as a warning,
            # and an outage whose end is not recorded is one nobody can measure
            # the duration of (CLAUDE.md §26).
            logger.info(log_context(event="ai_provider_recovered", provider=provider))

    def record_failure(self, provider: str, now: float | None = None) -> None:
        """Record a failed call, opening the breaker at the threshold.

        Args:
            provider: The provider that failed.
            now: Current time, injectable for tests.
        """
        moment = time.monotonic() if now is None else now

        with self._lock:
            record = self._health.setdefault(provider, ProviderHealth())
            record.consecutive_failures += 1
            record.total_failures += 1

            opened = (
                record.consecutive_failures >= self._failure_threshold
                and record.unhealthy_since is None
            )

            if opened:
                record.unhealthy_since = moment

            failures = record.consecutive_failures

        if opened:
            # A provider leaving rotation is an operational event, not a debug
            # detail: it changes which provider every subsequent request goes
            # to, and it is the signal an on-call engineer needs (CLAUDE.md §26).
            logger.warning(
                log_context(
                    event="ai_provider_unhealthy",
                    provider=provider,
                    consecutive_failures=failures,
                    cooldown_seconds=self._cooldown_seconds,
                )
            )

    def snapshot(self) -> dict[str, ProviderHealth]:
        """Return a copy of every tracked provider's record.

        For diagnostics and tests. A copy rather than the live dictionary so a
        caller cannot mutate breaker state by holding the return value.
        """
        with self._lock:
            return {
                name: ProviderHealth(
                    consecutive_failures=record.consecutive_failures,
                    unhealthy_since=record.unhealthy_since,
                    total_failures=record.total_failures,
                    total_successes=record.total_successes,
                )
                for name, record in self._health.items()
            }

    def clear(self) -> None:
        """Forget every record.

        Exists for tests, which would otherwise leak breaker state between
        cases: an in-process tracker is shared for the life of the process, and
        one test opening a breaker would silently change what the next observes.
        """
        with self._lock:
            self._health.clear()
