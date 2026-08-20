"""The job contract's invariants, offline.

Everything here is a property of the *contract* rather than of the queue: the
ceilings and their arithmetic, the registry's refusals, and the failure
classification that decides whether a retry happens at all. None of it needs a
database, and the parts that do are in `test_job_queue.py`.

The composed-ceiling tests are the ones worth understanding. ADR-005 §7 fixes the
worst case at **60 upstream provider requests per enqueue**, and the danger it
names is not that someone removes a limit -- it is that three reasonable limits
multiply while each looks fine on its own. So the number is computed from its
three factors and asserted against the value the owner accepted, which means
raising any single layer fails here, naming the product.
"""

from __future__ import annotations

import pytest

from app.ai.errors import ProviderTimeoutError, TerminalProviderError
from app.ai.governance import (
    DEFAULT_MAX_CHAINED_INVOCATIONS,
    BudgetExceededError,
    ExecutionLimitExceededError,
)
from app.ai.router import DEFAULT_MAX_ATTEMPTS_PER_PROVIDER, DEFAULT_MAX_PROVIDERS_TRIED
from app.core.security import AuthorizationError, WorkspaceAccessError
from app.jobs.contract import (
    MAX_JOB_ATTEMPTS,
    MAX_UPSTREAM_REQUESTS_PER_ENQUEUE,
    HandlerNotRegisteredError,
    JobContext,
    JobHandler,
    JobResult,
    JobStatus,
    TenantContextUnavailableError,
    TerminalJobError,
    classify,
)
from app.jobs.registry import (
    JobHandlerRegistry,
    JobRegistrationError,
    build_registry,
)
from app.workflows.models import RunNotFoundError, WorkflowError
from tests.fakes import unusable_workflow_definitions


class _Handler(JobHandler):
    """A minimal handler for registry tests."""

    def __init__(self, job_type: str = "test", max_attempts: int = 1) -> None:
        self._job_type = job_type
        self._max_attempts = max_attempts

    @property
    def job_type(self) -> str:
        return self._job_type

    @property
    def max_attempts(self) -> int:
        return self._max_attempts

    def execute(self, context: JobContext) -> JobResult:
        return JobResult(output=None)


# ---------------------------------------------------------- the ceilings --


class TestTheComposedCeiling:
    """ADR-005 §7's arithmetic, asserted rather than described."""

    def test_the_accepted_job_attempt_ceiling_is_two(self) -> None:
        """The number the project owner set at ADR-005's review, on 2026-08-17.

        Pinned because it is an owner decision rather than an implementation
        detail: raising it multiplies the platform's worst-case AI spend per
        enqueue, so it must not move without someone editing this line and
        explaining why.
        """
        assert MAX_JOB_ATTEMPTS == 2

    def test_the_composed_ceiling_is_sixty_upstream_requests(self) -> None:
        """2 job attempts x 5 chained invocations x 6 requests per `complete()`.

        The full product, stated as ADR-005 §7 states it. If this fails, one of
        the three layers moved and the accepted ceiling moved with it.
        """
        assert MAX_UPSTREAM_REQUESTS_PER_ENQUEUE == 60

    def test_the_ceiling_is_computed_from_its_factors_not_written_down(self) -> None:
        """Raising any single layer must move the product.

        The point of the constant. A hardcoded 60 would go on reading 60 while
        the real ceiling doubled underneath it -- which is precisely the failure
        §15a describes, reached without anyone removing a limit.
        """
        expected = (
            MAX_JOB_ATTEMPTS
            * DEFAULT_MAX_CHAINED_INVOCATIONS
            * DEFAULT_MAX_ATTEMPTS_PER_PROVIDER
            * DEFAULT_MAX_PROVIDERS_TRIED
        )

        assert MAX_UPSTREAM_REQUESTS_PER_ENQUEUE == expected

    def test_each_layer_is_still_the_value_the_arithmetic_assumes(self) -> None:
        """The three factors, named individually.

        Asserted separately from the product so a failure says *which* layer
        moved rather than only that the total is wrong.
        """
        assert DEFAULT_MAX_ATTEMPTS_PER_PROVIDER == 3
        assert DEFAULT_MAX_PROVIDERS_TRIED == 2
        assert DEFAULT_MAX_CHAINED_INVOCATIONS == 5


# ---------------------------------------------------------- classification --


class TestRetryClassification:
    """Which failures are retried, and which are settled answers."""

    @pytest.mark.parametrize(
        "error",
        [
            BudgetExceededError("over ceiling"),
            ExecutionLimitExceededError("too many invocations"),
            AuthorizationError("not permitted"),
            WorkspaceAccessError("not a member"),
            WorkflowError("unknown workflow"),
            RunNotFoundError(),
            TerminalJobError("settled"),
            HandlerNotRegisteredError("no handler"),
            TenantContextUnavailableError("membership revoked"),
        ],
    )
    def test_a_settled_refusal_is_never_retried(self, error: Exception) -> None:
        """Retrying any of these spends the ceiling on a certainty.

        A budget refusal retried is the refusal repeated; a tripped ceiling
        retried is the ceiling not being a ceiling; a revoked membership retried
        is a permission check re-asked of a database that will keep answering no.
        """
        assert classify(error) is False

    @pytest.mark.parametrize(
        "error",
        [
            ProviderTimeoutError("upstream timed out"),
            ConnectionError("database went away"),
            RuntimeError("something unexpected"),
        ],
    )
    def test_a_transient_failure_is_retried(self, error: Exception) -> None:
        """A second attempt is exactly what a bounded retry ceiling is for."""
        assert classify(error) is True

    def test_a_terminal_provider_error_is_still_retried_at_the_job_layer(self) -> None:
        """Terminal to the *router* is not terminal to the *job*.

        `TerminalProviderError` means "do not try this provider again with this
        request" -- the router then falls back to another provider, which is a
        different action from abandoning the work. A job whose whole provider
        chain failed may still be worth one more attempt later; a governance
        refusal never is. Conflating the two would make a single bad key
        dead-letter work the fallback chain was built to rescue.
        """
        assert classify(TerminalProviderError("bad request", provider="openai")) is True


# ---------------------------------------------------------------- registry --


class TestTheRegistry:
    """Registration is where a ceiling is checked, not first execution."""

    def test_a_handler_is_found_by_its_job_type(self) -> None:
        registry = JobHandlerRegistry((_Handler("alpha"), _Handler("beta")))

        assert registry.get("alpha").job_type == "alpha"
        assert registry.knows("beta") is True
        assert registry.job_types == ("alpha", "beta")

    def test_an_unregistered_type_raises_a_terminal_error(self) -> None:
        """Terminal, so an unknown type dead-letters on its first attempt.

        The registry is fixed at process start, so a second attempt in the same
        deployment asks the same question of the same registry. Retrying it would
        spend an attempt learning nothing.
        """
        registry = JobHandlerRegistry((_Handler("alpha"),))

        with pytest.raises(HandlerNotRegisteredError):
            registry.get("nope")

        assert registry.knows("nope") is False
        assert classify(HandlerNotRegisteredError("x")) is False

    def test_two_handlers_cannot_claim_one_job_type(self) -> None:
        """A queued row names one type, so it must name one handler."""
        with pytest.raises(JobRegistrationError, match="Two handlers claim job type"):
            JobHandlerRegistry((_Handler("same"), _Handler("same")))

    def test_a_blank_job_type_is_refused(self) -> None:
        with pytest.raises(JobRegistrationError, match="blank job_type"):
            JobHandlerRegistry((_Handler("   "),))

    @pytest.mark.parametrize("ceiling", [0, -1, MAX_JOB_ATTEMPTS + 1, 10])
    def test_a_ceiling_outside_the_accepted_bound_is_refused_at_registration(
        self, ceiling: int
    ) -> None:
        """ADR-005 §7: a configuration error at registration, not a job that retries forever.

        The upper bound matters as much as the lower. A handler quietly declaring
        10 attempts would multiply the platform's worst-case spend per enqueue by
        five while `MAX_UPSTREAM_REQUESTS_PER_ENQUEUE` went on reporting 60.
        """
        with pytest.raises(JobRegistrationError, match="max_attempts"):
            JobHandlerRegistry((_Handler("alpha", max_attempts=ceiling),))

    def test_every_shipped_handler_declares_a_ceiling_within_the_bound(self) -> None:
        """The real registry, not a fixture.

        `build_registry` performs the same validation, so this would fail at
        construction — but asserting it here names the offending handler rather
        than failing somewhere unrelated.

        The definitions factory is the one that refuses to build anything: this
        asserts what handlers *declare*, and building a workflow definition would
        be a different test needing a database.
        """
        registry = build_registry(unusable_workflow_definitions)

        assert registry.job_types, "a deployment with no handlers can run no jobs"

        for job_type in registry.job_types:
            handler = registry.get(job_type)

            assert 1 <= handler.max_attempts <= MAX_JOB_ATTEMPTS, (
                f"{type(handler).__name__} declares max_attempts={handler.max_attempts}"
            )

    def test_the_workflow_handler_is_registered(self) -> None:
        """A deployment that cannot run `workflow.execute` cannot run a workflow.

        The registry is the checklist: a handler absent from it is a job type
        that dead-letters visibly. Asserted here because the commands that
        enqueue a workflow job write this exact type as a literal, and a
        deployment where the two disagree queues work nothing will ever run.
        """
        registry = build_registry(unusable_workflow_definitions)

        assert registry.knows("workflow.execute")
        assert registry.get("workflow.execute").max_attempts == MAX_JOB_ATTEMPTS

    def test_a_handler_must_declare_a_ceiling_at_all(self) -> None:
        """`max_attempts` is abstract, so omitting it fails at import.

        There is deliberately no default: a default means a handler author who
        never considered the question ships whatever it happened to be, which is
        the shape [[CLAUDE|CLAUDE.md]] §15a forbids.
        """

        class _NoCeiling(JobHandler):  # type: ignore[misc]
            @property
            def job_type(self) -> str:
                return "no-ceiling"

            def execute(self, context: JobContext) -> JobResult:
                return JobResult()

        with pytest.raises(TypeError, match="max_attempts"):
            _NoCeiling()  # type: ignore[abstract]


# ------------------------------------------------------------------ status --


def test_terminal_statuses_are_the_two_that_stop_execution() -> None:
    """`pending` and `running` are both live states; the other two are not."""
    from app.jobs.contract import TERMINAL_JOB_STATUSES

    assert TERMINAL_JOB_STATUSES == frozenset({JobStatus.SUCCEEDED, JobStatus.DEAD_LETTERED})
    assert JobStatus.PENDING not in TERMINAL_JOB_STATUSES
    assert JobStatus.RUNNING not in TERMINAL_JOB_STATUSES
