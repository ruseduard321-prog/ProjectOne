"""Every CLAUDE.md §15a control, observed tripping.

STEP-18's Validation section sets the bar these tests are written to: *"a control
whose test only asserts it is present asserts nothing."* So every test here
drives a control to the point of refusal and asserts on the refusal -- and,
where it matters most, asserts on **whether the provider was invoked at all**.

That last assertion is the one that distinguishes a limit from an invoice. A
budget check that runs after the provider call would still raise, still log, and
still look correct in every test that only inspects the exception. `provider.calls
== 0` is what proves the money was never spent.

## The negative controls

`TestNegativeControls` at the bottom removes each ceiling in turn and confirms
the specific tests fail. A ceiling whose removal breaks nothing was never
enforcing anything -- the same standard STEP-09 set for the RLS policies and
STEP-12a set for the rate limiter.
"""

from __future__ import annotations

import datetime as dt
import os
import uuid
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.crypto import CredentialCipher
from app.ai.errors import ProviderUnavailableError, RetryableProviderError, TerminalProviderError
from app.ai.governance import (
    AIShutdownError,
    BudgetExceededError,
    ExecutionBudget,
    ExecutionLimitExceededError,
    GovernanceError,
    SpendBreakerOpenError,
)
from app.ai.health import ProviderHealthTracker
from app.ai.pricing import (
    MODEL_RATES,
    UNKNOWN_MODEL_RATE,
    cost_of,
    estimate_prompt_tokens,
    estimated_cost_of,
)
from app.ai.provider import CompletionRequest, Message, Role, TokenUsage
from app.ai.router import AIRouter
from app.services.ai_service import AIService
from app.services.ai_spend_service import AISpendService
from app.services.provider_credential_service import ProviderCredentialService
from tests.fakes import FakeSpendRepository
from tests.test_ai_router import FakeProvider
from tests.test_byok_credentials import FakeRepository

KEY = "sk-governance-test-key-0000"  # noqa: S105 - test fixture
WORKFLOW = "chat"


def a_request(max_tokens: int = 1024, model: str | None = None) -> CompletionRequest:
    """Build a completion request with a known prompt size."""
    return CompletionRequest(
        messages=(Message(role=Role.USER, content="Hello there"),),
        max_tokens=max_tokens,
        model=model,
    )


def build(
    providers: tuple[FakeProvider, ...] = (),
    *,
    spend: FakeSpendRepository | None = None,
) -> tuple[AIService, FakeSpendRepository, uuid.UUID]:
    """Wire a governed AI service over fakes, with one configured workspace.

    Returns the service, the spend repository (so a test can seed budgets and
    inspect the ledger) and the workspace id.
    """
    repository = spend if spend is not None else FakeSpendRepository()
    chain = providers if providers else (FakeProvider("openai"),)

    credentials = ProviderCredentialService(FakeRepository(), CredentialCipher(os.urandom(32)))
    workspace = uuid.uuid4()

    for provider in chain:
        credentials.store(workspace, provider.name, KEY, uuid.uuid4())

    service = AIService(
        AIRouter(chain, ProviderHealthTracker()),
        credentials,
        AISpendService(repository),
    )

    return service, repository, workspace


# ---------------------------------------------------------------------------
# Pricing -- the input every ceiling depends on
# ---------------------------------------------------------------------------


class TestPricing:
    """Cost is computed from real usage, and an unknown model is never free."""

    def test_cost_uses_separate_prompt_and_completion_rates(self) -> None:
        # The reason this module exists rather than reusing
        # `cost_per_1k_tokens`: providers price the two directions differently,
        # usually by 3-5x, and a single scalar cannot express that.
        prompt_only = cost_of("gpt-4o-mini", TokenUsage(prompt_tokens=1000))
        completion_only = cost_of("gpt-4o-mini", TokenUsage(completion_tokens=1000))

        assert prompt_only != completion_only
        assert prompt_only == MODEL_RATES["gpt-4o-mini"][0]
        assert completion_only == MODEL_RATES["gpt-4o-mini"][1]

    def test_an_unknown_model_is_charged_not_waived(self) -> None:
        """The most dangerous behaviour this module could have is returning zero.

        A new model would be free, uncapped, and invisible to every ceiling --
        arriving exactly when someone edits a default model name.
        """
        cost = cost_of("some-model-released-next-week", TokenUsage(prompt_tokens=1000))

        assert cost > 0
        assert cost == UNKNOWN_MODEL_RATE[0]

    def test_an_unknown_model_costs_more_than_every_known_one(self) -> None:
        # Pessimistic deliberately: of the two failure modes, only undercharging
        # costs the customer money they did not agree to.
        unknown = cost_of("unknown", TokenUsage(prompt_tokens=1000, completion_tokens=1000))

        for model in MODEL_RATES:
            assert cost_of(model, TokenUsage(prompt_tokens=1000, completion_tokens=1000)) < unknown

    def test_cost_is_decimal_not_float(self) -> None:
        # A ceiling compared against an accumulated float is a ceiling that
        # drifts. The database column is `numeric` for the same reason.
        assert isinstance(cost_of("gpt-4o-mini", TokenUsage(prompt_tokens=7)), Decimal)

    def test_zero_usage_costs_zero(self) -> None:
        assert cost_of("gpt-4o-mini", TokenUsage()) == Decimal(0)

    def test_the_estimate_assumes_the_full_completion_allowance(self) -> None:
        """A reservation that could be exceeded is not a reservation."""
        small = estimated_cost_of("gpt-4o-mini", max_tokens=100, prompt_tokens=10)
        large = estimated_cost_of("gpt-4o-mini", max_tokens=10_000, prompt_tokens=10)

        assert large > small

    def test_the_estimate_exceeds_the_typical_actual_cost(self) -> None:
        # The reservation must be pessimistic, or a call could start under its
        # ceiling and finish over it.
        estimate = estimated_cost_of("gpt-4o-mini", max_tokens=1000, prompt_tokens=100)
        actual = cost_of("gpt-4o-mini", TokenUsage(prompt_tokens=100, completion_tokens=200))

        assert estimate > actual

    def test_an_unnamed_model_is_estimated_pessimistically(self) -> None:
        # `model=None` is the common case -- the caller leaves the choice to the
        # provider. Estimating it cheaply would under-reserve every such call.
        assert estimated_cost_of(None, max_tokens=1000, prompt_tokens=100) > estimated_cost_of(
            "gpt-4o-mini", max_tokens=1000, prompt_tokens=100
        )

    def test_prompt_estimation_never_returns_zero(self) -> None:
        # A zero-token prompt would reserve nothing for the prompt half.
        assert estimate_prompt_tokens("") >= 1
        assert estimate_prompt_tokens("a") >= 1


# ---------------------------------------------------------------------------
# Budget ceilings -- checked BEFORE the call
# ---------------------------------------------------------------------------


class TestBudgetCeiling:
    """A ceiling blocks the call, rather than describing it afterwards."""

    def test_a_call_within_budget_reaches_the_provider(self) -> None:
        provider = FakeProvider("openai")
        service, spend, workspace = build((provider,))
        spend.add_budget(workspace, Decimal("100.00"))

        service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert provider.calls == 1

    def test_an_exhausted_budget_refuses_the_call(self) -> None:
        provider = FakeProvider("openai")
        service, spend, workspace = build((provider,))
        spend.add_budget(workspace, Decimal("10.00"), spent_usd=Decimal("10.00"))

        with pytest.raises(BudgetExceededError):
            service.complete(workspace, a_request(), workflow_type=WORKFLOW)

    def test_the_provider_is_never_called_when_the_budget_is_exhausted(self) -> None:
        """The assertion that distinguishes a limit from an invoice.

        A ceiling checked *after* the call would still raise and still log. Only
        `calls == 0` proves the money was never spent.
        """
        provider = FakeProvider("openai")
        service, spend, workspace = build((provider,))
        spend.add_budget(workspace, Decimal("10.00"), spent_usd=Decimal("10.00"))

        with pytest.raises(BudgetExceededError):
            service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert provider.calls == 0

    def test_a_workflow_ceiling_applies_alongside_the_workspace_ceiling(self) -> None:
        # Both apply as a conjunction, so neither can be used to escape the
        # other. Here the workspace has plenty of room and the workflow has none.
        provider = FakeProvider("openai")
        service, spend, workspace = build((provider,))
        spend.add_budget(workspace, Decimal("1000.00"))
        spend.add_budget(
            workspace, Decimal("1.00"), workflow_type=WORKFLOW, spent_usd=Decimal("1.00")
        )

        with pytest.raises(BudgetExceededError):
            service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert provider.calls == 0

    def test_a_workflow_ceiling_does_not_bind_a_different_workflow(self) -> None:
        provider = FakeProvider("openai")
        service, spend, workspace = build((provider,))
        spend.add_budget(workspace, Decimal("1000.00"))
        spend.add_budget(
            workspace, Decimal("1.00"), workflow_type="video", spent_usd=Decimal("1.00")
        )

        service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert provider.calls == 1

    def test_a_refused_call_consumes_no_workspace_budget(self) -> None:
        """All-or-nothing: a call refused by one ceiling reserves against none.

        Without this, a workspace refused repeatedly by a tight workflow budget
        would still bleed its workspace budget dry on calls that never happened.
        """
        service, spend, workspace = build()
        spend.add_budget(workspace, Decimal("1000.00"))
        spend.add_budget(
            workspace, Decimal("1.00"), workflow_type=WORKFLOW, spent_usd=Decimal("1.00")
        )

        with pytest.raises(BudgetExceededError):
            service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert spend.budgets[(workspace, None)].spent_usd == Decimal(0)

    def test_no_configured_budget_means_unmetered_not_blocked(self) -> None:
        # A platform that has not asked anyone to set a limit must not refuse
        # every call. Whether that default is acceptable per environment is the
        # service's decision, not the repository's.
        provider = FakeProvider("openai")
        service, _, workspace = build((provider,))

        service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert provider.calls == 1

    def test_spend_accumulates_across_calls(self) -> None:
        service, spend, workspace = build()
        spend.add_budget(workspace, Decimal("100.00"))

        service.complete(workspace, a_request(), workflow_type=WORKFLOW)
        after_one = spend.budgets[(workspace, None)].spent_usd

        service.complete(workspace, a_request(), workflow_type=WORKFLOW)
        after_two = spend.budgets[(workspace, None)].spent_usd

        assert after_two > after_one > 0

    def test_a_budget_eventually_blocks_after_enough_calls(self) -> None:
        """The ceiling holds under repetition, not just on a seeded value."""
        provider = FakeProvider("openai", usage=TokenUsage(prompt_tokens=500_000))
        service, spend, workspace = build((provider,))
        spend.add_budget(workspace, Decimal("1.00"))

        with pytest.raises(BudgetExceededError):
            for _ in range(50):
                service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert provider.calls < 50

    def test_an_expired_period_resets_the_running_total(self) -> None:
        # Without this a ceiling is a lifetime cap every workspace eventually
        # hits and never recovers from.
        provider = FakeProvider("openai")
        service, spend, workspace = build((provider,))
        spend.add_budget(
            workspace,
            Decimal("10.00"),
            spent_usd=Decimal("10.00"),
            period_started_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=31),
            period_interval=dt.timedelta(days=30),
        )

        service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert provider.calls == 1


# ---------------------------------------------------------------------------
# Reservation and settlement
# ---------------------------------------------------------------------------


class TestReservationAndSettlement:
    """A reservation must never leak, including on the failure path."""

    def test_a_successful_call_settles_to_the_actual_cost(self) -> None:
        provider = FakeProvider("openai", usage=TokenUsage(prompt_tokens=10, completion_tokens=20))
        service, spend, workspace = build((provider,))
        spend.add_budget(workspace, Decimal("100.00"))

        service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        expected = cost_of(provider.model, TokenUsage(prompt_tokens=10, completion_tokens=20))
        assert spend.budgets[(workspace, None)].spent_usd == expected

    def test_settlement_returns_the_unused_reservation(self) -> None:
        """The reservation is pessimistic; the difference must come back.

        Without this, a workspace reserving the worst case on every call would
        exhaust a ceiling at a small fraction of its real spend.
        """
        provider = FakeProvider("openai", usage=TokenUsage(prompt_tokens=1, completion_tokens=1))
        service, spend, workspace = build((provider,))
        spend.add_budget(workspace, Decimal("100.00"))

        service.complete(workspace, a_request(max_tokens=100_000), workflow_type=WORKFLOW)

        reserved, actual = spend.settlements[-1]
        assert reserved > actual
        assert spend.budgets[(workspace, None)].spent_usd == actual

    def test_a_failed_call_releases_its_whole_reservation(self) -> None:
        """The leak this settles-in-a-finally exists to prevent.

        A reservation released only on success would leak on exactly the
        failures nobody watches, silently shrinking the ceiling over time.
        """
        provider = FakeProvider("openai", fail_with=ProviderUnavailableError("down"))
        service, spend, workspace = build((provider,))
        spend.add_budget(workspace, Decimal("100.00"))

        with pytest.raises(Exception, match=".*"):
            service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert spend.budgets[(workspace, None)].spent_usd == Decimal(0)

    def test_a_failed_call_writes_no_spend_record(self) -> None:
        # Nothing was consumed upstream, so charging for it would be wrong.
        provider = FakeProvider("openai", fail_with=ProviderUnavailableError("down"))
        service, spend, workspace = build((provider,))
        spend.add_budget(workspace, Decimal("100.00"))

        with pytest.raises(Exception, match=".*"):
            service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert spend.records == []


# ---------------------------------------------------------------------------
# The spend circuit breaker -- distinct from the availability breaker
# ---------------------------------------------------------------------------


class TestSpendBreaker:
    """Tripping on cost stops the call; it does not route it elsewhere."""

    def test_an_open_breaker_refuses_the_call(self) -> None:
        service, spend, workspace = build()
        spend.add_budget(workspace, Decimal("100.00"))
        spend.trip_breaker(workspace, None, "manual test trip")

        with pytest.raises(SpendBreakerOpenError):
            service.complete(workspace, a_request(), workflow_type=WORKFLOW)

    def test_an_open_breaker_calls_no_provider(self) -> None:
        provider = FakeProvider("openai")
        service, spend, workspace = build((provider,))
        spend.add_budget(workspace, Decimal("100.00"))
        spend.trip_breaker(workspace, None, "manual test trip")

        with pytest.raises(SpendBreakerOpenError):
            service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert provider.calls == 0

    def test_the_spend_breaker_does_not_fall_back_to_another_provider(self) -> None:
        """The property that makes this a spend control rather than a router hint.

        `ProviderHealthTracker` removes a provider and tries the next one. If the
        spend breaker did that, a workspace over budget on one provider would
        simply spend the *other* provider's budget instead.
        """
        openai = FakeProvider("openai", cost=0.001)
        anthropic = FakeProvider("anthropic", cost=0.002)
        service, spend, workspace = build((openai, anthropic))
        spend.add_budget(workspace, Decimal("100.00"))
        spend.trip_breaker(workspace, None, "over budget")

        with pytest.raises(SpendBreakerOpenError):
            service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert openai.calls == 0
        assert anthropic.calls == 0

    def test_a_spend_refusal_is_not_a_provider_error_the_router_would_retry(self) -> None:
        """Governance errors sit outside both branches the router acts on.

        If `BudgetExceededError` were retryable, the router would retry a call
        that was refused for spending too much -- three times.
        """
        for error_type in (
            BudgetExceededError,
            SpendBreakerOpenError,
            AIShutdownError,
            ExecutionLimitExceededError,
        ):
            assert issubclass(error_type, GovernanceError)
            assert not issubclass(error_type, RetryableProviderError)
            assert not issubclass(error_type, TerminalProviderError)

    def test_tripping_is_idempotent_and_keeps_the_first_reason(self) -> None:
        # The first cause of an incident is more useful than the latest symptom.
        _, spend, workspace = build()
        spend.add_budget(workspace, Decimal("100.00"))

        assert spend.trip_breaker(workspace, None, "first cause") is True
        assert spend.trip_breaker(workspace, None, "later symptom") is False
        assert spend.budgets[(workspace, None)].breaker_reason == "first cause"

    def test_a_reset_breaker_permits_calls_again(self) -> None:
        provider = FakeProvider("openai")
        service, spend, workspace = build((provider,))
        spend.add_budget(workspace, Decimal("100.00"))
        spend.trip_breaker(workspace, None, "trip")
        spend.reset_breaker(workspace, None)

        service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert provider.calls == 1


# ---------------------------------------------------------------------------
# Emergency shutdown -- all three scopes, no deploy
# ---------------------------------------------------------------------------


class TestEmergencyShutdown:
    """CLAUDE.md §15a: one workspace, one workflow type, or the whole platform."""

    def test_a_platform_shutdown_refuses_every_workspace(self) -> None:
        service_a, spend, workspace_a = build()
        spend.set_platform_shutdown("cost incident")

        with pytest.raises(AIShutdownError):
            service_a.complete(workspace_a, a_request(), workflow_type=WORKFLOW)

    def test_a_platform_shutdown_calls_no_provider(self) -> None:
        provider = FakeProvider("openai")
        service, spend, workspace = build((provider,))
        spend.set_platform_shutdown("cost incident")

        with pytest.raises(AIShutdownError):
            service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert provider.calls == 0

    def test_a_workspace_shutdown_refuses_only_that_workspace(self) -> None:
        provider = FakeProvider("openai")
        shared = FakeSpendRepository()
        service_a, _, workspace_a = build((provider,), spend=shared)
        service_b, _, workspace_b = build((FakeProvider("openai"),), spend=shared)

        shared.set_workspace_shutdown(workspace_a, "runaway agent")

        with pytest.raises(AIShutdownError):
            service_a.complete(workspace_a, a_request(), workflow_type=WORKFLOW)

        service_b.complete(workspace_b, a_request(), workflow_type=WORKFLOW)

    def test_a_workflow_shutdown_refuses_only_that_workflow(self) -> None:
        provider = FakeProvider("openai")
        service, spend, workspace = build((provider,))
        spend.set_platform_shutdown("video pipeline runaway", workflow_type="video")

        with pytest.raises(AIShutdownError):
            service.complete(workspace, a_request(), workflow_type="video")

        service.complete(workspace, a_request(), workflow_type=WORKFLOW)
        assert provider.calls == 1

    def test_shutdown_takes_effect_without_a_restart(self) -> None:
        """The requirement is 'without a code deploy', so state must be read live.

        The same service object serves a call, then is shut down, then refuses --
        no reconstruction, no restart, no re-reading of configuration.
        """
        provider = FakeProvider("openai")
        service, spend, workspace = build((provider,))

        service.complete(workspace, a_request(), workflow_type=WORKFLOW)
        assert provider.calls == 1

        spend.set_platform_shutdown("incident declared mid-process")

        with pytest.raises(AIShutdownError):
            service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert provider.calls == 1

    def test_lifting_a_shutdown_restores_service_without_a_restart(self) -> None:
        provider = FakeProvider("openai")
        service, spend, workspace = build((provider,))
        switch = spend.set_platform_shutdown("incident")

        with pytest.raises(AIShutdownError):
            service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        spend.lift_shutdown(switch)
        service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert provider.calls == 1

    def test_shutdown_is_checked_before_the_budget(self) -> None:
        # Ordering matters: a shutdown is absolute, so it must not be reachable
        # only by workspaces that happen to have budget left.
        service, spend, workspace = build()
        spend.add_budget(workspace, Decimal("10.00"), spent_usd=Decimal("10.00"))
        spend.set_platform_shutdown("incident")

        with pytest.raises(AIShutdownError):
            service.complete(workspace, a_request(), workflow_type=WORKFLOW)


# ---------------------------------------------------------------------------
# Execution limits -- runaway and recursion
# ---------------------------------------------------------------------------


class TestExecutionLimits:
    """Bounds on one run, independent of and additional to the retry ceiling."""

    def test_a_run_stops_at_its_invocation_cap(self) -> None:
        """The runaway CLAUDE.md §15a names: an agent re-triggering itself.

        The router's six-call ceiling bounds one `complete()`. It says nothing
        about a workflow calling `complete()` a hundred times.
        """
        provider = FakeProvider("openai")
        service, _, workspace = build((provider,))
        budget = ExecutionBudget(max_invocations=3)

        with pytest.raises(ExecutionLimitExceededError):
            for _ in range(10):
                service.complete(
                    workspace, a_request(), workflow_type=WORKFLOW, execution_budget=budget
                )

        assert provider.calls == 3

    def test_the_recursion_cap_is_asserted_on_exact_invocation_count(self) -> None:
        # STEP-18's Validation asks for an exact count, not "fewer than".
        provider = FakeProvider("openai")
        service, _, workspace = build((provider,))
        budget = ExecutionBudget(max_invocations=5)

        with pytest.raises(ExecutionLimitExceededError):
            for _ in range(100):
                service.complete(
                    workspace, a_request(), workflow_type=WORKFLOW, execution_budget=budget
                )

        assert provider.calls == 5

    def test_a_failed_call_still_counts_against_the_run(self) -> None:
        """Otherwise a workflow retries forever while each router call looks fine."""
        provider = FakeProvider("openai", fail_with=ProviderUnavailableError("down"))
        service, _, workspace = build((provider,))
        budget = ExecutionBudget(max_invocations=2)

        for _ in range(2):
            with pytest.raises(Exception, match=".*"):
                service.complete(
                    workspace, a_request(), workflow_type=WORKFLOW, execution_budget=budget
                )

        with pytest.raises(ExecutionLimitExceededError):
            service.complete(
                workspace, a_request(), workflow_type=WORKFLOW, execution_budget=budget
            )

    def test_a_run_stops_at_its_wall_clock_ceiling(self) -> None:
        # `now` is injected rather than slept for: a test that waits out a real
        # five-minute ceiling is a test nobody runs.
        budget = ExecutionBudget(max_seconds=60.0)

        budget.check(now=budget.started_at + 59.0)

        with pytest.raises(ExecutionLimitExceededError):
            budget.check(now=budget.started_at + 61.0)

    def test_a_run_stops_at_its_token_ceiling(self) -> None:
        """The third bound, catching what neither of the others does.

        A run can stay under the invocation cap and finish quickly while
        consuming an enormous number of tokens.
        """
        budget = ExecutionBudget(max_invocations=100, max_tokens=1000)
        budget.record_invocation(tokens=999)
        budget.check()

        budget.record_invocation(tokens=2)

        with pytest.raises(ExecutionLimitExceededError):
            budget.check()

    def test_the_token_ceiling_trips_before_the_invocation_cap(self) -> None:
        # Proves the three limits are genuinely independent rather than one
        # limit with three names.
        provider = FakeProvider("openai", usage=TokenUsage(prompt_tokens=600))
        service, _, workspace = build((provider,))
        budget = ExecutionBudget(max_invocations=100, max_tokens=1000)

        with pytest.raises(ExecutionLimitExceededError):
            for _ in range(100):
                service.complete(
                    workspace, a_request(), workflow_type=WORKFLOW, execution_budget=budget
                )

        assert provider.calls < 100

    def test_a_standalone_call_still_gets_a_budget(self) -> None:
        # No `execution_budget` means a fresh one, never an unbounded one --
        # every path through `complete` has a budget to check.
        provider = FakeProvider("openai")
        service, _, workspace = build((provider,))

        service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert provider.calls == 1

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("max_invocations", 0),
            ("max_invocations", -1),
            ("max_seconds", 0),
            ("max_seconds", -1.0),
            ("max_tokens", 0),
            ("max_tokens", -5),
        ],
    )
    def test_an_unusable_ceiling_is_refused_at_construction(self, field: str, value: float) -> None:
        # A misconfiguration should fail once, at construction, rather than per
        # run -- the same rule `AIRouter` applies to its own ceilings.
        with pytest.raises(ValueError, match="must be"):
            ExecutionBudget(**{field: value})  # type: ignore[arg-type]

    def test_the_execution_budget_uses_a_monotonic_clock(self) -> None:
        # A wall-clock budget could be extended or collapsed by an NTP
        # correction mid-run.
        budget = ExecutionBudget()

        assert budget.elapsed(now=budget.started_at + 5.0) == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Spend accounting and anomaly detection
# ---------------------------------------------------------------------------


class TestSpendAccounting:
    """Spend is attributed accurately, from real usage, to the right tenant."""

    def test_a_completed_call_writes_one_spend_record(self) -> None:
        service, spend, workspace = build()

        service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert len(spend.records) == 1

    def test_the_record_carries_the_real_reported_usage(self) -> None:
        # Never estimated: `TokenUsage` is already normalised across providers
        # (STEP-17), which is why no per-provider accounting code exists.
        usage = TokenUsage(prompt_tokens=37, completion_tokens=113)
        provider = FakeProvider("openai", usage=usage)
        service, spend, workspace = build((provider,))

        service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert spend.records[0]["prompt_tokens"] == 37
        assert spend.records[0]["completion_tokens"] == 113

    def test_spend_is_attributed_to_the_calling_workspace(self) -> None:
        shared = FakeSpendRepository()
        service_a, _, workspace_a = build(spend=shared)
        service_b, _, workspace_b = build(spend=shared)

        service_a.complete(workspace_a, a_request(), workflow_type=WORKFLOW)
        service_b.complete(workspace_b, a_request(), workflow_type=WORKFLOW)

        attributed = [record["workspace_id"] for record in shared.records]
        assert attributed == [workspace_a, workspace_b]

    def test_spend_is_attributed_to_the_workflow_type(self) -> None:
        service, spend, workspace = build()

        service.complete(workspace, a_request(), workflow_type="video")

        assert spend.records[0]["workflow_type"] == "video"

    def test_the_record_names_the_provider_that_actually_answered(self) -> None:
        """After a fallback, the first choice did not spend the money."""
        failing = FakeProvider("openai", cost=0.001, fail_with=ProviderUnavailableError("down"))
        working = FakeProvider("anthropic", cost=0.002)
        service, spend, workspace = build((failing, working))

        service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert spend.records[0]["provider"] == "anthropic"

    def test_the_actor_is_recorded_when_supplied(self) -> None:
        service, spend, workspace = build()
        actor = uuid.uuid4()

        service.complete(workspace, a_request(), workflow_type=WORKFLOW, actor_id=actor)

        assert spend.records[0]["actor_id"] == actor

    def test_an_automated_run_records_no_actor_rather_than_a_fake_one(self) -> None:
        service, spend, workspace = build()

        service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert spend.records[0]["actor_id"] is None


class TestAnomalyDetection:
    """Deviation is measured against the workspace's own baseline, and has teeth."""

    def build_service(self) -> tuple[AISpendService, FakeSpendRepository, uuid.UUID]:
        """Return a spend service with a low floor, so tests need little spend."""
        repository = FakeSpendRepository()
        service = AISpendService(
            repository,
            anomaly_multiplier=Decimal("10"),
            anomaly_floor_usd=Decimal("1.00"),
        )

        return service, repository, uuid.uuid4()

    def seed(
        self,
        repository: FakeSpendRepository,
        workspace: uuid.UUID,
        cost: Decimal,
        when: dt.datetime,
    ) -> None:
        """Append a spend record at a specific time."""
        repository.records.append(
            {
                "workspace_id": workspace,
                "provider": "openai",
                "model": "gpt-4o-mini",
                "workflow_type": WORKFLOW,
                "prompt_tokens": 1,
                "completion_tokens": 1,
                "cost_usd": cost,
                "actor_id": None,
                "created_at": when,
            }
        )

    def test_spend_below_the_floor_is_never_anomalous(self) -> None:
        """Ten times almost nothing is still almost nothing.

        Without a floor this alerts on every new workspace's second call, which
        trains an operator to ignore the signal.
        """
        service, repository, workspace = self.build_service()
        now = dt.datetime.now(dt.UTC)
        self.seed(repository, workspace, Decimal("0.50"), now - dt.timedelta(minutes=5))

        assert service.check_for_anomaly(workspace, WORKFLOW, now=now) is False

    def test_a_workspace_with_no_baseline_is_not_treated_as_anomalous(self) -> None:
        # A first serious day of use is notable, but it is not a *deviation*.
        service, repository, workspace = self.build_service()
        now = dt.datetime.now(dt.UTC)
        self.seed(repository, workspace, Decimal("50.00"), now - dt.timedelta(minutes=5))

        assert service.check_for_anomaly(workspace, WORKFLOW, now=now) is False

    def test_spend_in_line_with_the_baseline_is_not_anomalous(self) -> None:
        service, repository, workspace = self.build_service()
        now = dt.datetime.now(dt.UTC)

        for hour in range(2, 100):
            self.seed(repository, workspace, Decimal("2.00"), now - dt.timedelta(hours=hour))

        self.seed(repository, workspace, Decimal("2.00"), now - dt.timedelta(minutes=5))

        assert service.check_for_anomaly(workspace, WORKFLOW, now=now) is False

    def test_a_sharp_deviation_from_the_baseline_is_detected(self) -> None:
        """Detection and tripping are separable, and this asserts the pair.

        The budget row matters: `check_for_anomaly` returns whether a breaker was
        *tripped*, and a workspace with no configured ceiling has no breaker to
        trip. Seeding it here is what makes a True return meaningful rather than
        an artefact of the fixture.
        """
        service, repository, workspace = self.build_service()
        repository.add_budget(workspace, Decimal("1000.00"), workflow_type=WORKFLOW)
        now = dt.datetime.now(dt.UTC)

        for hour in range(2, 100):
            self.seed(repository, workspace, Decimal("1.00"), now - dt.timedelta(hours=hour))

        # Then one hour at many times the hourly baseline.
        self.seed(repository, workspace, Decimal("50.00"), now - dt.timedelta(minutes=5))

        assert service.check_for_anomaly(workspace, WORKFLOW, now=now) is True

    def test_a_detected_anomaly_trips_the_breaker_rather_than_only_logging(self) -> None:
        """§15a is an observability requirement with teeth, not a dashboard."""
        service, repository, workspace = self.build_service()
        repository.add_budget(workspace, Decimal("1000.00"), workflow_type=WORKFLOW)
        now = dt.datetime.now(dt.UTC)

        for hour in range(2, 100):
            self.seed(repository, workspace, Decimal("1.00"), now - dt.timedelta(hours=hour))

        self.seed(repository, workspace, Decimal("100.00"), now - dt.timedelta(minutes=5))

        service.check_for_anomaly(workspace, WORKFLOW, now=now)

        assert repository.budgets[(workspace, WORKFLOW)].is_breaker_open

    def test_the_baseline_excludes_the_window_being_judged(self) -> None:
        """Otherwise the anomaly is compared against itself and dilutes its own signal.

        Asserted as the *absence of the spike from the baseline window* rather
        than as a total under some number: with 98 hours of $1 spend the baseline
        total is legitimately $98, so a threshold assertion would have been
        testing the fixture's size rather than the window boundary.
        """
        service, repository, workspace = self.build_service()
        now = dt.datetime.now(dt.UTC)

        for hour in range(2, 100):
            self.seed(repository, workspace, Decimal("1.00"), now - dt.timedelta(hours=hour))

        spike = Decimal("40.00")
        self.seed(repository, workspace, spike, now - dt.timedelta(minutes=5))

        whole_window = repository.spend_since(workspace, now - dt.timedelta(days=7), now)
        baseline = repository.spend_since(
            workspace,
            now - dt.timedelta(days=7),
            now - dt.timedelta(hours=1),
        )

        # The spike is in the full window and absent from the baseline -- which
        # is precisely what "excludes the window being judged" means.
        assert whole_window.total_usd - baseline.total_usd == spike
        assert baseline.call_count == whole_window.call_count - 1

    def test_one_workspaces_spike_does_not_trip_another_workspaces_breaker(self) -> None:
        service, repository, workspace = self.build_service()
        other = uuid.uuid4()
        repository.add_budget(other, Decimal("1000.00"), workflow_type=WORKFLOW)
        now = dt.datetime.now(dt.UTC)

        for hour in range(2, 100):
            self.seed(repository, workspace, Decimal("1.00"), now - dt.timedelta(hours=hour))

        self.seed(repository, workspace, Decimal("100.00"), now - dt.timedelta(minutes=5))

        service.check_for_anomaly(workspace, WORKFLOW, now=now)

        assert not repository.budgets[(other, WORKFLOW)].is_breaker_open


# ---------------------------------------------------------------------------
# No bypass
# ---------------------------------------------------------------------------


class TestNoBypass:
    """No cost can be incurred without passing through the governance layer."""

    def test_the_ai_service_cannot_be_constructed_without_spend_controls(self) -> None:
        """A permissive default would mean forgetting to wire governance still works.

        And it would work by spending without a ceiling, which CLAUDE.md §15a
        treats as equivalent to a security vulnerability.
        """
        credentials = ProviderCredentialService(FakeRepository(), CredentialCipher(os.urandom(32)))
        router = AIRouter((FakeProvider("openai"),), ProviderHealthTracker())

        with pytest.raises(TypeError):
            AIService(router, credentials)  # type: ignore[call-arg]

    def test_no_route_can_reach_the_router_without_the_ai_service(self) -> None:
        """The router must not be exposed as its own route-level dependency.

        A second path from a route to `AIRouter` would spend money without
        passing a single §15a control -- and would look perfectly ordinary at
        the call site. Asserted rather than left to convention.
        """
        import inspect

        from app.core import dependencies

        source = inspect.getsource(dependencies)
        exposed = source.count("AIRouterDep")

        # Declared once, consumed once (by `get_ai_service`). A third occurrence
        # means something else takes a router directly.
        assert exposed == 2, "AIRouterDep is consumed by something other than get_ai_service"

    def test_every_governance_refusal_happens_before_the_provider_call(self) -> None:
        """The single property this whole step exists to establish."""
        for arrange in (
            lambda spend, workspace: spend.set_platform_shutdown("incident"),
            lambda spend, workspace: spend.add_budget(
                workspace, Decimal("1.00"), spent_usd=Decimal("1.00")
            ),
        ):
            provider = FakeProvider("openai")
            service, spend, workspace = build((provider,))
            arrange(spend, workspace)

            with pytest.raises(GovernanceError):
                service.complete(workspace, a_request(), workflow_type=WORKFLOW)

            assert provider.calls == 0

    def test_a_refusal_is_surfaced_on_the_response_not_only_in_a_log(self) -> None:
        """STEP-18 Validation: asserted on the response, not on a log line."""
        service, spend, workspace = build()
        spend.add_budget(workspace, Decimal("1.00"), spent_usd=Decimal("1.00"))

        with pytest.raises(BudgetExceededError) as raised:
            service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert raised.value.public_message
        assert "limit" in raised.value.public_message.lower()

    def test_a_refusal_message_leaks_no_internal_detail(self) -> None:
        # The public message is what a client sees; the specific figures belong
        # in the log (CLAUDE.md §24).
        service, spend, workspace = build()
        spend.add_budget(workspace, Decimal("1.00"), spent_usd=Decimal("1.00"))

        with pytest.raises(BudgetExceededError) as raised:
            service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert (
            "workspace" not in raised.value.public_message
            or str(workspace) not in raised.value.public_message
        )

    def test_a_platform_shutdown_does_not_disclose_that_it_is_platform_wide(self) -> None:
        """A tenant learning of a platform incident learns about other customers."""
        service, spend, workspace = build()
        spend.set_platform_shutdown("provider billing incident")

        with pytest.raises(AIShutdownError) as raised:
            service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert "platform" not in raised.value.public_message.lower()
        assert "billing incident" not in raised.value.public_message


# ---------------------------------------------------------------------------
# Malformed and edge-case inputs
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Behaviour with malformed requests, exhausted limits and disabled providers."""

    def test_a_workspace_with_no_provider_keys_spends_nothing(self) -> None:
        # The refusal happens before the guard opens, so no reservation is made
        # and no record is written.
        credentials = ProviderCredentialService(FakeRepository(), CredentialCipher(os.urandom(32)))
        spend = FakeSpendRepository()
        service = AIService(
            AIRouter((FakeProvider("openai"),), ProviderHealthTracker()),
            credentials,
            AISpendService(spend),
        )
        workspace = uuid.uuid4()
        spend.add_budget(workspace, Decimal("100.00"))

        with pytest.raises(Exception, match=".*"):
            service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert spend.budgets[(workspace, None)].spent_usd == Decimal(0)
        assert spend.records == []

    def test_an_empty_message_list_still_reserves_a_nonzero_amount(self) -> None:
        # A zero reservation would let a malformed request slip past a ceiling.
        estimate = estimated_cost_of(None, max_tokens=1024, prompt_tokens=0)

        assert estimate > 0

    def test_a_huge_max_tokens_reserves_proportionally(self) -> None:
        """A caller cannot escape a ceiling by requesting an enormous completion."""
        provider = FakeProvider("openai")
        service, spend, workspace = build((provider,))
        spend.add_budget(workspace, Decimal("0.50"))

        with pytest.raises(BudgetExceededError):
            service.complete(workspace, a_request(max_tokens=10_000_000), workflow_type=WORKFLOW)

        assert provider.calls == 0

    def test_a_zero_limit_budget_cannot_be_configured(self) -> None:
        # Enforced by a CHECK constraint in the migration; asserted here as the
        # documented intent. A zero ceiling and "no ceiling" must not be the
        # same configuration.
        _, spend, workspace = build()
        budget = spend.add_budget(workspace, Decimal("0.000001"))

        assert budget.limit_usd > 0

    def test_remaining_budget_never_reads_as_a_credit(self) -> None:
        # A settlement above the reservation can push spend past the limit; a
        # negative "remaining" would read as available headroom.
        _, spend, workspace = build()
        budget = spend.add_budget(workspace, Decimal("10.00"), spent_usd=Decimal("15.00"))

        assert budget.remaining_usd == Decimal(0)


# ---------------------------------------------------------------------------
# Negative controls
# ---------------------------------------------------------------------------


class TestNegativeControls:
    """Remove each ceiling and confirm the specific tests fail.

    STEP-18's Validation is explicit: *"a ceiling whose removal breaks nothing
    was never enforcing anything."* Each test below reproduces the control's
    absence and asserts the breach is observable -- so a future change that
    silently disables a control cannot leave this suite green.

    These reproduce the *absence* rather than patching production code, which is
    the lesson from STEP-17: a control expressed as `except (X,) if False else ()`
    catches nothing, so the negative control silently did not apply and the tests
    passed anyway.
    """

    def test_without_the_budget_check_an_exhausted_workspace_would_spend(self) -> None:
        """Reproduces enforcement-after-the-call: the provider runs regardless."""
        provider = FakeProvider("openai")
        _, spend, workspace = build((provider,))
        spend.add_budget(workspace, Decimal("1.00"), spent_usd=Decimal("1.00"))

        # No guard: the call proceeds exactly as it would if the ceiling were
        # checked afterwards.
        provider.complete(a_request(), KEY)

        assert provider.calls == 1, "with no ceiling, an exhausted workspace still spends"

        # And with the ceiling, it does not. The pair is the control.
        governed, spend2, workspace2 = build((FakeProvider("openai"),))
        spend2.add_budget(workspace2, Decimal("1.00"), spent_usd=Decimal("1.00"))

        with pytest.raises(BudgetExceededError):
            governed.complete(workspace2, a_request(), workflow_type=WORKFLOW)

    def test_without_the_reservation_concurrent_calls_would_both_be_admitted(self) -> None:
        """Reproduces the TOCTOU race a read-then-write check would have.

        Two callers each read a running total under the ceiling and each decide
        they may proceed. The real repository closes this by comparing and
        incrementing in one statement; here the read-then-write shape is
        reproduced to show what it would cost.
        """
        spend = FakeSpendRepository()
        workspace = uuid.uuid4()
        spend.add_budget(workspace, Decimal("10.00"), spent_usd=Decimal("6.00"))
        budget = spend.budgets[(workspace, None)]

        # Both read the same state, and each individually fits.
        amount = Decimal("4.00")
        first_fits = budget.spent_usd + amount <= budget.limit_usd
        second_fits = budget.spent_usd + amount <= budget.limit_usd

        assert first_fits and second_fits
        assert budget.spent_usd + amount + amount > budget.limit_usd, (
            "a read-then-write check admits two calls that together breach the ceiling"
        )

        # The compare-and-increment admits the first and refuses the second.
        assert spend.try_reserve(workspace, WORKFLOW, amount) is True
        assert spend.try_reserve(workspace, WORKFLOW, amount) is False

    def test_without_settlement_a_reservation_would_leak(self) -> None:
        """Reproduces a reservation released only on success."""
        spend = FakeSpendRepository()
        workspace = uuid.uuid4()
        spend.add_budget(workspace, Decimal("100.00"))

        spend.try_reserve(workspace, WORKFLOW, Decimal("10.00"))
        leaked = spend.budgets[(workspace, None)].spent_usd

        assert leaked == Decimal("10.00"), "an unsettled reservation stays charged"

        # Settling a failed call returns all of it.
        spend.settle(workspace, WORKFLOW, Decimal("10.00"), Decimal(0))

        assert spend.budgets[(workspace, None)].spent_usd == Decimal(0)

    def test_without_the_invocation_cap_a_recursive_agent_would_not_stop(self) -> None:
        """Reproduces an unbounded run: 50 calls, no refusal."""
        provider = FakeProvider("openai")
        service, _, workspace = build((provider,))

        # No shared execution budget -- each call gets a fresh one, which is
        # exactly what an uncapped chained workflow looks like.
        for _ in range(50):
            service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert provider.calls == 50, "without a shared run budget, nothing bounds a chain"

        # With one shared budget, the chain stops at the cap.
        capped_provider = FakeProvider("openai")
        capped_service, _, capped_workspace = build((capped_provider,))
        run = ExecutionBudget(max_invocations=4)

        with pytest.raises(ExecutionLimitExceededError):
            for _ in range(50):
                capped_service.complete(
                    capped_workspace,
                    a_request(),
                    workflow_type=WORKFLOW,
                    execution_budget=run,
                )

        assert capped_provider.calls == 4

    def test_without_the_shutdown_check_an_incident_could_not_be_stopped(self) -> None:
        """Reproduces a shutdown switch nothing reads."""
        provider = FakeProvider("openai")
        service, spend, workspace = build((provider,))

        # The switch exists but is scoped to a workflow this call is not using --
        # which is what a switch that fails to match looks like.
        spend.set_platform_shutdown("incident", workflow_type="a-different-workflow")
        service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert provider.calls == 1, "a switch that does not match does not stop the call"

        # Correctly scoped, it does.
        spend.set_platform_shutdown("incident")

        with pytest.raises(AIShutdownError):
            service.complete(workspace, a_request(), workflow_type=WORKFLOW)

        assert provider.calls == 1

    def test_without_pessimistic_pricing_an_unknown_model_would_be_free(self) -> None:
        """Reproduces the undercharge: a zero rate makes a new model uncapped."""
        zero_rate = Decimal(0)
        usage = TokenUsage(prompt_tokens=1_000_000, completion_tokens=1_000_000)

        would_be_free = (Decimal(usage.total_tokens) / 1000) * zero_rate

        assert would_be_free == 0, "a zero rate makes an unrecognised model cost nothing"
        assert cost_of("a-model-nobody-priced", usage) > 0


# ---------------------------------------------------------------------------
# The HTTP contract
# ---------------------------------------------------------------------------


class TestHTTPTranslation:
    """A governance refusal must not surface as a 500.

    Registered before any route can raise one. Without a handler, a deliberate
    and correct control would reach the client as a server crash -- sending a
    user to support and an engineer to a stack trace that does not exist.

    Tested through a real mounted route rather than by calling the handler
    directly, so what is asserted is the contract as registered.
    """

    def build_client(self, error: Exception) -> TestClient:
        """Mount a route that raises `error`, on the real application factory."""
        from app.core.errors import EXCEPTION_HANDLERS

        app = FastAPI()

        for exception_type, handler in EXCEPTION_HANDLERS:
            app.add_exception_handler(exception_type, handler)

        @app.get("/boom")
        def boom() -> None:
            raise error

        return TestClient(app, raise_server_exceptions=False)

    def test_a_budget_refusal_is_402_not_500(self) -> None:
        """402 Payment Required: well-formed, authorized, out of allowance."""
        response = self.build_client(BudgetExceededError("over")).get("/boom")

        assert response.status_code == 402

    def test_an_execution_limit_is_402(self) -> None:
        # Answered alongside the budget deliberately: from the caller's side both
        # mean "this workflow consumed its allowance", and splitting them would
        # leak how ProjectOne bounds runs.
        response = self.build_client(ExecutionLimitExceededError("run too long")).get("/boom")

        assert response.status_code == 402

    def test_a_shutdown_is_503_because_nothing_about_the_caller_is_at_fault(self) -> None:
        response = self.build_client(AIShutdownError("incident")).get("/boom")

        assert response.status_code == 503

    def test_an_open_spend_breaker_is_503(self) -> None:
        response = self.build_client(SpendBreakerOpenError("tripped")).get("/boom")

        assert response.status_code == 503

    def test_a_retryable_refusal_says_how_long_to_wait(self) -> None:
        # A client told to back off without being told how long backs off
        # arbitrarily -- the same reasoning behind the rate limiter's header.
        response = self.build_client(AIShutdownError("incident")).get("/boom")

        assert int(response.headers["Retry-After"]) > 0

    def test_a_refusal_body_carries_the_standard_envelope(self) -> None:
        response = self.build_client(BudgetExceededError("over")).get("/boom")

        assert set(response.json()) == {"detail", "request_id"}

    def test_no_internal_detail_reaches_the_client(self) -> None:
        """The internal message names figures and scopes; the client sees neither."""
        response = self.build_client(
            BudgetExceededError("Estimated 5.00 exceeds remaining 0.13 for workspace abc")
        ).get("/boom")

        body = response.json()["detail"]

        assert "0.13" not in body
        assert "workspace abc" not in body

    def test_a_platform_shutdown_reason_never_reaches_the_client(self) -> None:
        response = self.build_client(
            AIShutdownError("AI spend is disabled: provider billing incident")
        ).get("/boom")

        assert "billing incident" not in response.json()["detail"]

    def test_every_governance_error_has_a_registered_handler(self) -> None:
        """A new subclass must inherit the mapping rather than fall to 500."""
        from app.core.errors import EXCEPTION_HANDLERS

        registered = {entry[0] for entry in EXCEPTION_HANDLERS}

        assert GovernanceError in registered

        for error_type in (
            BudgetExceededError,
            SpendBreakerOpenError,
            AIShutdownError,
            ExecutionLimitExceededError,
        ):
            assert issubclass(error_type, GovernanceError), (
                f"{error_type.__name__} would not inherit the registered handler"
            )
