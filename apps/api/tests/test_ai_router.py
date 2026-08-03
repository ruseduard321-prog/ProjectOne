"""Selection, retry ceilings, fallback and health.

The tests that matter most in STEP-17 are the ones asserting *bounds*. An AI
router without an enforced ceiling is the runaway-spend failure CLAUDE.md §15a
exists to prevent, and a ceiling nobody counted is a ceiling that does not exist
-- so these assert exact call counts rather than "it eventually stopped".

Fake providers rather than the real adapters: this suite is about the router's
decisions, and a fake can be made to fail on demand, deterministically, without
a substituted transport in the way.
"""

from __future__ import annotations

import pytest

from app.ai.errors import (
    AllProvidersFailedError,
    NoProviderAvailableError,
    ProviderAuthenticationError,
    ProviderUnavailableError,
)
from app.ai.health import DEFAULT_FAILURE_THRESHOLD, HealthState, ProviderHealthTracker
from app.ai.provider import (
    AIProvider,
    Capability,
    CompletionRequest,
    CompletionResponse,
    Message,
    Role,
    TokenUsage,
)
from app.ai.router import AIRouter


class FakeProvider(AIProvider):
    """A provider whose behaviour a test dictates."""

    def __init__(
        self,
        name: str,
        cost: float = 0.001,
        fail_with: Exception | None = None,
        capabilities: frozenset[Capability] | None = None,
        usage: TokenUsage | None = None,
        model: str = "fake-model",
    ) -> None:
        self._name = name
        self._cost = cost
        self._fail_with = fail_with
        self._capabilities = (
            capabilities if capabilities is not None else frozenset({Capability.CHAT_COMPLETION})
        )
        # Added by STEP-18: the spend tests need to dictate reported usage and
        # the model name, since those are what cost is computed from. Defaulted
        # so every STEP-17 test constructs this exactly as before.
        self._usage = usage if usage is not None else TokenUsage(1, 1)
        self.model = model
        self.calls = 0
        self.keys_seen: list[str] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def capabilities(self) -> frozenset[Capability]:
        return self._capabilities

    @property
    def cost_per_1k_tokens(self) -> float:
        return self._cost

    def complete(self, request: CompletionRequest, api_key: str) -> CompletionResponse:
        self.calls += 1
        self.keys_seen.append(api_key)

        if self._fail_with is not None:
            raise self._fail_with

        return CompletionResponse(
            content=f"answer from {self._name}",
            provider=self._name,
            model=self.model,
            usage=self._usage,
        )


def a_request() -> CompletionRequest:
    """Build a minimal completion request."""
    return CompletionRequest(messages=(Message(role=Role.USER, content="Hi"),))


def resolver(_provider_name: str) -> str:
    """Return a fake key for any provider."""
    return "sk-fake-key-value"


@pytest.fixture
def health() -> ProviderHealthTracker:
    """Return a fresh tracker, so breaker state never leaks between tests."""
    return ProviderHealthTracker()


class TestSelectionFollowsTheDocumentedFlow:
    """[[AI Providers]]: preference -> capability -> availability -> cost."""

    def test_the_cheapest_eligible_provider_wins(self, health: ProviderHealthTracker) -> None:
        cheap = FakeProvider("cheap", cost=0.0001)
        pricey = FakeProvider("pricey", cost=0.05)
        router = AIRouter((pricey, cheap), health)

        chain, reason = router.select(Capability.CHAT_COMPLETION, ("cheap", "pricey"))

        assert chain[0].name == "cheap"
        assert reason.selected == "cheap"

    def test_a_provider_without_a_key_is_not_a_candidate(
        self, health: ProviderHealthTracker
    ) -> None:
        # BYOK is a hard filter, not a ranking input: no key means no call is
        # possible at any price.
        cheap = FakeProvider("cheap", cost=0.0001)
        pricey = FakeProvider("pricey", cost=0.05)
        router = AIRouter((cheap, pricey), health)

        chain, reason = router.select(Capability.CHAT_COMPLETION, ("pricey",))

        assert [p.name for p in chain] == ["pricey"]
        assert ("cheap", "no_key") in reason.rejected

    def test_a_provider_lacking_the_capability_is_not_a_candidate(
        self, health: ProviderHealthTracker
    ) -> None:
        useless = FakeProvider("useless", cost=0.0, capabilities=frozenset())
        capable = FakeProvider("capable", cost=0.05)
        router = AIRouter((useless, capable), health)

        chain, reason = router.select(Capability.CHAT_COMPLETION, ("useless", "capable"))

        assert [p.name for p in chain] == ["capable"]
        assert ("useless", "capability") in reason.rejected

    def test_an_unhealthy_provider_is_skipped(self, health: ProviderHealthTracker) -> None:
        cheap = FakeProvider("cheap", cost=0.0001)
        pricey = FakeProvider("pricey", cost=0.05)
        router = AIRouter((cheap, pricey), health)

        for _ in range(DEFAULT_FAILURE_THRESHOLD):
            health.record_failure("cheap")

        chain, reason = router.select(Capability.CHAT_COMPLETION, ("cheap", "pricey"))

        assert [p.name for p in chain] == ["pricey"]
        assert ("cheap", "unhealthy") in reason.rejected

    def test_a_preference_outranks_cost(self, health: ProviderHealthTracker) -> None:
        cheap = FakeProvider("cheap", cost=0.0001)
        pricey = FakeProvider("pricey", cost=0.05)
        router = AIRouter((cheap, pricey), health)

        chain, reason = router.select(
            Capability.CHAT_COMPLETION, ("cheap", "pricey"), preferred="pricey"
        )

        assert chain[0].name == "pricey"
        assert reason.selected == "pricey"

    def test_a_preference_does_not_resurrect_an_ineligible_provider(
        self, health: ProviderHealthTracker
    ) -> None:
        # A preference ranks among survivors. It is not an override of
        # availability -- preferring a dead provider must not select it.
        cheap = FakeProvider("cheap", cost=0.0001)
        pricey = FakeProvider("pricey", cost=0.05)
        router = AIRouter((cheap, pricey), health)

        for _ in range(DEFAULT_FAILURE_THRESHOLD):
            health.record_failure("pricey")

        chain, reason = router.select(
            Capability.CHAT_COMPLETION, ("cheap", "pricey"), preferred="pricey"
        )

        assert chain[0].name == "cheap"
        assert ("pricey", "unhealthy") in reason.rejected

    def test_selection_is_deterministic_when_costs_tie(self, health: ProviderHealthTracker) -> None:
        # Without the name tiebreak, two equally-priced providers would order by
        # dictionary insertion -- making the choice depend on import order and
        # turning a reproducible decision into a coin flip (CLAUDE.md §15).
        first = FakeProvider("aaa", cost=0.01)
        second = FakeProvider("bbb", cost=0.01)

        forward = AIRouter((first, second), health)
        backward = AIRouter((second, first), health)

        chain_a, _ = forward.select(Capability.CHAT_COMPLETION, ("aaa", "bbb"))
        chain_b, _ = backward.select(Capability.CHAT_COMPLETION, ("aaa", "bbb"))

        assert chain_a[0].name == chain_b[0].name == "aaa"

    def test_repeated_selection_returns_the_same_provider(
        self, health: ProviderHealthTracker
    ) -> None:
        router = AIRouter((FakeProvider("a", cost=0.01), FakeProvider("b", cost=0.02)), health)

        choices = {
            router.select(Capability.CHAT_COMPLETION, ("a", "b"))[0][0].name for _ in range(10)
        }

        assert choices == {"a"}

    def test_no_eligible_provider_is_an_honest_error(self, health: ProviderHealthTracker) -> None:
        # Not a degraded or canned response -- that is the "confident-sounding
        # output" CLAUDE.md §15 forbids.
        router = AIRouter((FakeProvider("a"),), health)

        with pytest.raises(NoProviderAvailableError):
            router.select(Capability.CHAT_COMPLETION, ())

    def test_the_decision_records_what_was_rejected_and_why(
        self, health: ProviderHealthTracker
    ) -> None:
        # An unexplained provider choice is a black box (CLAUDE.md §15).
        router = AIRouter(
            (
                FakeProvider("chosen"),
                FakeProvider("nokey"),
                FakeProvider("nocap", capabilities=frozenset()),
            ),
            health,
        )

        _, reason = router.select(Capability.CHAT_COMPLETION, ("chosen", "nocap"))

        assert reason.selected == "chosen"
        assert ("nokey", "no_key") in reason.rejected
        assert ("nocap", "capability") in reason.rejected
        assert "chosen" in reason.as_log_fields()["selected"]


class TestRetryCeiling:
    """CLAUDE.md §15a: unbounded retry logic is forbidden."""

    def test_a_failing_provider_stops_at_the_ceiling(self, health: ProviderHealthTracker) -> None:
        # The exact count is the assertion. "It stopped eventually" is what an
        # unbounded loop also does, given a timeout.
        failing = FakeProvider("failing", fail_with=ProviderUnavailableError("down", "failing"))
        router = AIRouter((failing,), health, max_attempts_per_provider=3)

        with pytest.raises(AllProvidersFailedError):
            router.complete(a_request(), ("failing",), resolver)

        assert failing.calls == 3

    def test_a_lower_ceiling_is_honoured(self, health: ProviderHealthTracker) -> None:
        failing = FakeProvider("failing", fail_with=ProviderUnavailableError("down", "failing"))
        router = AIRouter((failing,), health, max_attempts_per_provider=1)

        with pytest.raises(AllProvidersFailedError):
            router.complete(a_request(), ("failing",), resolver)

        assert failing.calls == 1

    def test_a_terminal_error_is_not_retried_at_all(self, health: ProviderHealthTracker) -> None:
        # Retrying a rejected credential cannot succeed, and repeating it risks
        # the workspace's upstream account being flagged for abuse.
        rejected = FakeProvider(
            "rejected", fail_with=ProviderAuthenticationError("bad key", "rejected")
        )
        router = AIRouter((rejected,), health, max_attempts_per_provider=3)

        with pytest.raises(AllProvidersFailedError):
            router.complete(a_request(), ("rejected",), resolver)

        assert rejected.calls == 1

    def test_a_zero_ceiling_is_refused_at_construction(self, health: ProviderHealthTracker) -> None:
        with pytest.raises(ValueError):
            AIRouter((FakeProvider("a"),), health, max_attempts_per_provider=0)

        with pytest.raises(ValueError):
            AIRouter((FakeProvider("a"),), health, max_providers_tried=0)

    def test_total_upstream_calls_are_bounded_by_both_ceilings(
        self, health: ProviderHealthTracker
    ) -> None:
        # The two limits multiply. This asserts the product, because that is the
        # number that actually bounds spend for one request.
        first = FakeProvider("aaa", cost=0.01, fail_with=ProviderUnavailableError("x", "aaa"))
        second = FakeProvider("bbb", cost=0.02, fail_with=ProviderUnavailableError("x", "bbb"))
        third = FakeProvider("ccc", cost=0.03, fail_with=ProviderUnavailableError("x", "ccc"))
        router = AIRouter(
            (first, second, third), health, max_attempts_per_provider=2, max_providers_tried=2
        )

        with pytest.raises(AllProvidersFailedError):
            router.complete(a_request(), ("aaa", "bbb", "ccc"), resolver)

        assert first.calls == 2
        assert second.calls == 2
        # Never reached: the chain stops at max_providers_tried.
        assert third.calls == 0


class TestFallback:
    """[[AI Providers]]: one provider's outage must not fail the request."""

    def test_the_call_completes_through_the_secondary(self, health: ProviderHealthTracker) -> None:
        primary = FakeProvider(
            "primary", cost=0.001, fail_with=ProviderUnavailableError("down", "primary")
        )
        secondary = FakeProvider("secondary", cost=0.002)
        router = AIRouter((primary, secondary), health)

        response = router.complete(a_request(), ("primary", "secondary"), resolver)

        assert response.content == "answer from secondary"
        assert response.provider == "secondary"

    def test_a_fallback_is_disclosed_on_the_response(self, health: ProviderHealthTracker) -> None:
        # A silent fallback is exactly the dishonesty CLAUDE.md §15 forbids: the
        # caller asked for one provider and another answered.
        primary = FakeProvider(
            "primary", cost=0.001, fail_with=ProviderUnavailableError("down", "primary")
        )
        secondary = FakeProvider("secondary", cost=0.002)
        router = AIRouter((primary, secondary), health)

        response = router.complete(a_request(), ("primary", "secondary"), resolver)

        assert response.served_after_fallback is True

    def test_a_direct_success_is_not_marked_as_a_fallback(
        self, health: ProviderHealthTracker
    ) -> None:
        router = AIRouter((FakeProvider("primary"),), health)

        response = router.complete(a_request(), ("primary",), resolver)

        assert response.served_after_fallback is False

    def test_a_terminal_failure_still_falls_back(self, health: ProviderHealthTracker) -> None:
        # Terminal is scoped to the provider, not to the request: a workspace
        # whose OpenAI key was revoked can still be served by Anthropic.
        rejected = FakeProvider(
            "rejected", cost=0.001, fail_with=ProviderAuthenticationError("bad", "rejected")
        )
        working = FakeProvider("working", cost=0.002)
        router = AIRouter((rejected, working), health)

        response = router.complete(a_request(), ("rejected", "working"), resolver)

        assert response.provider == "working"
        assert rejected.calls == 1

    def test_every_provider_failing_is_reported_honestly(
        self, health: ProviderHealthTracker
    ) -> None:
        first = FakeProvider("aaa", cost=0.001, fail_with=ProviderUnavailableError("x", "aaa"))
        second = FakeProvider("bbb", cost=0.002, fail_with=ProviderUnavailableError("x", "bbb"))
        router = AIRouter((first, second), health)

        with pytest.raises(AllProvidersFailedError):
            router.complete(a_request(), ("aaa", "bbb"), resolver)

    def test_a_key_is_resolved_only_for_a_provider_actually_tried(
        self, health: ProviderHealthTracker
    ) -> None:
        # The narrowest possible window for plaintext key material: a fallback
        # that never happens never decrypts the credential it did not need.
        resolved: list[str] = []

        def recording_resolver(provider_name: str) -> str:
            resolved.append(provider_name)
            return "sk-fake"

        router = AIRouter(
            (FakeProvider("primary", cost=0.001), FakeProvider("secondary", cost=0.002)), health
        )

        router.complete(a_request(), ("primary", "secondary"), recording_resolver)

        assert resolved == ["primary"]


class TestHealthTracking:
    """Repeated failures take a provider out of rotation, and it can return."""

    def test_a_provider_starts_healthy(self, health: ProviderHealthTracker) -> None:
        assert health.state_of("anything") is HealthState.HEALTHY
        assert health.is_available("anything") is True

    def test_the_breaker_opens_at_the_threshold(self) -> None:
        tracker = ProviderHealthTracker(failure_threshold=3)

        tracker.record_failure("p")
        tracker.record_failure("p")
        assert tracker.is_available("p") is True

        tracker.record_failure("p")
        assert tracker.state_of("p") is HealthState.UNHEALTHY
        assert tracker.is_available("p") is False

    def test_a_success_resets_the_run(self) -> None:
        # Consecutive failures, not cumulative: otherwise a provider failing
        # every other call would eventually trip on noise.
        tracker = ProviderHealthTracker(failure_threshold=3)

        tracker.record_failure("p")
        tracker.record_failure("p")
        tracker.record_success("p")
        tracker.record_failure("p")
        tracker.record_failure("p")

        assert tracker.is_available("p") is True

    def test_the_cooldown_admits_a_probe(self) -> None:
        # Without RECOVERING an unhealthy provider needs a success to recover
        # and is never selected to make one -- it would be out until restart.
        tracker = ProviderHealthTracker(failure_threshold=1, cooldown_seconds=30.0)

        tracker.record_failure("p", now=1000.0)
        assert tracker.state_of("p", now=1010.0) is HealthState.UNHEALTHY

        assert tracker.state_of("p", now=1031.0) is HealthState.RECOVERING
        assert tracker.is_available("p", now=1031.0) is True

    def test_a_successful_probe_restores_the_provider(self) -> None:
        tracker = ProviderHealthTracker(failure_threshold=1, cooldown_seconds=30.0)

        tracker.record_failure("p", now=1000.0)
        tracker.record_success("p")

        assert tracker.state_of("p") is HealthState.HEALTHY

    def test_the_router_records_failures_against_health(
        self, health: ProviderHealthTracker
    ) -> None:
        # The wiring test: a router that never fed the tracker would leave every
        # breaker permanently closed, and every test above would still pass.
        failing = FakeProvider("failing", fail_with=ProviderUnavailableError("down", "failing"))
        router = AIRouter((failing,), health, max_attempts_per_provider=3)

        with pytest.raises(AllProvidersFailedError):
            router.complete(a_request(), ("failing",), resolver)

        assert health.state_of("failing") is HealthState.UNHEALTHY

    def test_the_router_records_successes_against_health(
        self, health: ProviderHealthTracker
    ) -> None:
        router = AIRouter((FakeProvider("working"),), health)

        router.complete(a_request(), ("working",), resolver)

        assert health.snapshot()["working"].total_successes == 1

    def test_an_unhealthy_provider_is_not_called_again(self, health: ProviderHealthTracker) -> None:
        # The point of the breaker: during an outage a dead provider must stop
        # being selected first, rather than burning the ceiling on every request.
        failing = FakeProvider(
            "failing", cost=0.001, fail_with=ProviderUnavailableError("down", "failing")
        )
        working = FakeProvider("working", cost=0.002)
        router = AIRouter((failing, working), health, max_attempts_per_provider=3)

        router.complete(a_request(), ("failing", "working"), resolver)
        calls_after_first = failing.calls

        router.complete(a_request(), ("failing", "working"), resolver)

        assert failing.calls == calls_after_first
        assert working.calls == 2
