"""The AI Router: picks a provider, bounds what it costs, and says why.

This is the module [[AI Providers]]' selection flow describes:

    User Preference -> Capability -> Availability -> Cost -> Selection -> Execution -> Monitoring

Each stage is a filter over an ordered candidate list, and the **order is the
contract**. Cost last is deliberate: a cheap provider that cannot do the job, is
down, or has no key is not a candidate at any price, so filtering on cost before
eligibility would be sorting a list that still has to be filtered anyway.

## Two ceilings, and neither is optional

CLAUDE.md §15a forbids unbounded retry logic anywhere AI spend is involved.
There are therefore two independent limits, and they multiply rather than
overlap:

| Limit | Bounds | Worst case |
|---|---|---|
| `max_attempts_per_provider` | Retries against *one* provider | 3 |
| `max_providers_tried` | How far the fallback chain runs | 2 |

Six upstream calls, absolute, per `complete()`. Both are constructor parameters
rather than constants so a deployment can lower them, and neither has a code
path that can be skipped -- there is no "retry until success" branch to find.

**This is not the spend ceiling.** Budget limits, spend tracking and anomaly
detection are [[STEP-18 AI Cost Governance Controls]], which is a hard gate
before any of this serves a real user. What lives here is the bound on
*runaway execution*; what lives there is the bound on *money*. Conflating them
would put budget enforcement in a class whose failure mode is "try the next
provider", which is far too soft for a budget.

## Determinism

Given the same candidates, the same health state and the same request, selection
returns the same provider every time. The sort key is `(cost, name)` -- the name
tiebreak exists so two equally-priced providers do not order by dictionary
insertion, which would make the choice depend on import order and turn a
reproducible decision into a coin flip nobody can debug (CLAUDE.md §15).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.ai.errors import (
    AllProvidersFailedError,
    NoProviderAvailableError,
    ProviderError,
    RetryableProviderError,
    TerminalProviderError,
)
from app.ai.health import ProviderHealthTracker
from app.ai.provider import AIProvider, Capability, CompletionRequest, CompletionResponse
from app.core.logging import get_logger, log_context

logger = get_logger(__name__)

#: Attempts against a single provider before moving on, including the first.
#: Three: enough that a transient blip does not cause a visible fallback,
#: bounded so a persistent failure costs a known amount.
DEFAULT_MAX_ATTEMPTS_PER_PROVIDER = 3

#: How many providers the fallback chain will try. Two satisfies [[AI Providers]]'
#: requirement that one provider's outage not take down a critical workflow,
#: without turning one user request into a survey of every provider configured.
DEFAULT_MAX_PROVIDERS_TRIED = 2

#: Resolves one provider's plaintext key, for one workspace.
#:
#: A callable rather than a mapping of every key, deliberately: a fallback that
#: never happens never decrypts the credential it did not need, which keeps the
#: window in which plaintext key material exists as small as the call itself.
KeyResolver = Callable[[str], str]


@dataclass(frozen=True)
class SelectionReason:
    """Why a provider was chosen, and what happened to the others.

    Returned alongside the decision rather than only logged, so a caller can
    surface it and a test can assert on it. A provider choice that can only be
    explained by reading log output is a black box (CLAUDE.md §15).
    """

    selected: str
    considered: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]

    def as_log_fields(self) -> dict[str, str]:
        """Render the decision as flat log fields."""
        return {
            "selected": self.selected,
            "considered": ",".join(self.considered) or "none",
            "rejected": ";".join(f"{name}:{why}" for name, why in self.rejected) or "none",
        }


class AIRouter:
    """Selects a provider, executes against it, and falls back when it fails."""

    def __init__(
        self,
        providers: tuple[AIProvider, ...],
        health: ProviderHealthTracker,
        max_attempts_per_provider: int = DEFAULT_MAX_ATTEMPTS_PER_PROVIDER,
        max_providers_tried: int = DEFAULT_MAX_PROVIDERS_TRIED,
    ) -> None:
        """Wire the router to its providers and its health tracker.

        Args:
            providers: Every provider this deployment can use. Injected rather
                than imported, so a test supplies fakes and a deployment can
                disable one without editing this module (CLAUDE.md §12).
            health: The availability breaker consulted during selection.
            max_attempts_per_provider: Hard retry ceiling per provider.
            max_providers_tried: Hard ceiling on the fallback chain.

        Raises:
            ValueError: if either ceiling is below 1. A zero ceiling would make
                every request fail with no attempt, which is a misconfiguration
                that should not start rather than one discovered per request.
        """
        if max_attempts_per_provider < 1:
            raise ValueError("max_attempts_per_provider must be at least 1")

        if max_providers_tried < 1:
            raise ValueError("max_providers_tried must be at least 1")

        self._providers = {provider.name: provider for provider in providers}
        self._health = health
        self._max_attempts = max_attempts_per_provider
        self._max_providers = max_providers_tried

    def select(
        self,
        capability: Capability,
        available_keys: tuple[str, ...],
        preferred: str | None = None,
    ) -> tuple[tuple[AIProvider, ...], SelectionReason]:
        """Return the ordered candidate chain, and why it looks like that.

        Implements [[AI Providers]]' flow in its documented order. Returns the
        whole chain rather than one provider because fallback needs the runners
        up -- computing the order once is what makes the fallback deterministic
        too.

        Args:
            capability: What the request needs performed.
            available_keys: Providers this workspace holds BYOK keys for. A
                provider without one cannot be used regardless of everything
                else, so this is a hard filter rather than a ranking input.
            preferred: The workspace's stated preference, if any.

        Returns:
            The candidates in the order they should be tried, and the reasoning.

        Raises:
            NoProviderAvailableError: when nothing survives the filters.
        """
        considered = tuple(sorted(self._providers))
        rejected: list[tuple[str, str]] = []
        eligible: list[AIProvider] = []

        for name in considered:
            provider = self._providers[name]

            # Capability: a provider that cannot do this is not a candidate.
            if capability not in provider.capabilities:
                rejected.append((name, "capability"))
                continue

            # BYOK: no key, no call. Checked before health so a workspace that
            # simply has not configured a provider does not read as an outage.
            if name not in available_keys:
                rejected.append((name, "no_key"))
                continue

            # Availability: the breaker. RECOVERING counts as available -- that
            # is the probe that lets a provider come back.
            if not self._health.is_available(name):
                rejected.append((name, "unhealthy"))
                continue

            eligible.append(provider)

        if not eligible:
            reason = SelectionReason("none", considered, tuple(rejected))
            logger.warning(log_context(event="ai_selection_empty", **reason.as_log_fields()))
            raise NoProviderAvailableError(
                "No provider satisfies the request: " + (reason.as_log_fields()["rejected"])
            )

        # Cost, last. The name tiebreak keeps the order deterministic when two
        # providers are priced identically.
        eligible.sort(key=lambda provider: (provider.cost_per_1k_tokens, provider.name))

        # Preference outranks cost, but only among providers that already
        # survived every hard filter. A preference for an unhealthy provider or
        # one with no key does not resurrect it -- it is a preference, not an
        # override of availability.
        if preferred is not None:
            preferred_index = next(
                (i for i, provider in enumerate(eligible) if provider.name == preferred),
                None,
            )
            if preferred_index is not None:
                eligible.insert(0, eligible.pop(preferred_index))
            else:
                rejected.append((preferred, "preference_not_eligible"))

        chain = tuple(eligible[: self._max_providers])
        reason = SelectionReason(chain[0].name, considered, tuple(rejected))

        logger.info(log_context(event="ai_provider_selected", **reason.as_log_fields()))

        return chain, reason

    def complete(
        self,
        request: CompletionRequest,
        available_keys: tuple[str, ...],
        key_resolver: KeyResolver,
        preferred: str | None = None,
    ) -> CompletionResponse:
        """Run a completion, retrying and falling back within the ceilings.

        Args:
            request: What to generate.
            available_keys: Providers this workspace has keys for.
            key_resolver: Called to obtain a provider's plaintext key, one
                provider at a time. A callable rather than a dict of keys so
                that a fallback that never happens never decrypts a credential
                it did not need -- the smallest possible window for plaintext
                key material.
            preferred: The workspace's stated preference.

        Returns:
            The completion, attributed to whichever provider answered.

        Raises:
            NoProviderAvailableError: nothing was eligible.
            AllProvidersFailedError: every candidate was tried and failed.
        """
        chain, _ = self.select(Capability.CHAT_COMPLETION, available_keys, preferred)
        first_choice = chain[0].name
        last_error: ProviderError | None = None

        for provider in chain:
            try:
                response = self._attempt_provider(provider, request, key_resolver)
            except ProviderError as error:
                last_error = error
                # The chain continues: a terminal error is terminal for this
                # provider, not for the request (see `app.ai.errors`).
                continue

            served_after_fallback = provider.name != first_choice

            if served_after_fallback:
                # An answer that came from somewhere other than the first choice
                # is an operational event, and the caller is told too -- see
                # `CompletionResponse.served_after_fallback`.
                logger.warning(
                    log_context(
                        event="ai_fallback_served",
                        first_choice=first_choice,
                        served_by=provider.name,
                    )
                )

            return CompletionResponse(
                content=response.content,
                provider=response.provider,
                model=response.model,
                usage=response.usage,
                served_after_fallback=served_after_fallback,
            )

        logger.error(
            log_context(
                event="ai_all_providers_failed",
                tried=",".join(provider.name for provider in chain),
                last_error=type(last_error).__name__ if last_error else "unknown",
            )
        )

        raise AllProvidersFailedError(
            f"All {len(chain)} provider(s) failed; last error: {last_error}"
        )

    def _attempt_provider(
        self,
        provider: AIProvider,
        request: CompletionRequest,
        key_resolver: KeyResolver,
    ) -> CompletionResponse:
        """Call one provider, retrying only what is worth retrying.

        The loop is bounded by `self._max_attempts` with no early-exit that can
        extend it. A terminal error breaks immediately rather than consuming the
        remaining budget on a certainty.

        `key_resolver` is a parameter rather than instance state, and that is a
        security property rather than a style choice. The router is constructed
        once and shared across requests; holding a request-scoped resolver on
        `self` would let two concurrent requests race, and the loser would
        resolve a key belonging to the *other* workspace. That is the same class
        of defect as the pooled-connection claim leak STEP-10 reproduced, and it
        is prevented here structurally -- there is no instance attribute to
        race on.

        Raises:
            ProviderError: the last failure, once the ceiling is reached.
        """
        key = key_resolver(provider.name)
        last_error: ProviderError

        for attempt in range(1, self._max_attempts + 1):
            try:
                response = provider.complete(request, key)
            except TerminalProviderError as error:
                # No retry. A rejected key or a malformed request produces the
                # same answer every time, and retrying a rejected credential
                # risks the workspace's upstream account being flagged.
                self._health.record_failure(provider.name)
                logger.warning(
                    log_context(
                        event="ai_provider_terminal_error",
                        provider=provider.name,
                        cause=type(error).__name__,
                    )
                )
                raise
            except RetryableProviderError as error:
                last_error = error
                self._health.record_failure(provider.name)
                logger.warning(
                    log_context(
                        event="ai_provider_attempt_failed",
                        provider=provider.name,
                        attempt=attempt,
                        max_attempts=self._max_attempts,
                        cause=type(error).__name__,
                    )
                )
                continue

            self._health.record_success(provider.name)
            return response

        raise last_error
