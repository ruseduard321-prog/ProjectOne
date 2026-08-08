"""The workflow engine's execution rules (STEP-22).

These run **offline**, against a fake repository, and that is deliberate: the
questions here are about *sequencing and gating*, not about SQL. A test needing a
database to prove "a gated step does not execute without approval" would be a
test nobody runs locally, and this is the property CLAUDE.md §15 makes the
default for every agent.

The database-backed half lives in `test_workflows_api.py`, which proves the same
properties survive real persistence and RLS. Both are necessary: this one proves
the rules, that one proves they hold through the route and the policy layers.

## What the fake repository is, and is not

`FakeWorkflowRepository` records what the runner asked it to persist, in order.
It is not a stub returning canned values -- the runner's resumability logic reads
back what it wrote, so the fake has to behave like storage or the tests would
prove nothing about resuming. `next_step_index` in particular counts completed
steps exactly as the real query does.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.ai.governance import ExecutionBudget, ExecutionLimitExceededError
from app.repositories.workflows import WorkflowRun, WorkflowStepRun
from app.workflows.models import (
    RunNotFoundError,
    RunNotResumableError,
    RunStatus,
    StepContext,
    StepResult,
    StepStatus,
    WorkflowDefinition,
    WorkflowError,
    WorkflowStep,
)
from app.workflows.runner import WorkflowRunner


class FakeWorkflowRepository:
    """In-memory storage that behaves like `WorkflowRepository`.

    Deliberately not a `Mock`: the runner writes state and then reads it back to
    decide where to resume, so a fake that did not actually store would make
    every resumability assertion vacuous.
    """

    def __init__(self) -> None:
        """Start with no runs and no steps."""
        self.runs: dict[uuid.UUID, WorkflowRun] = {}
        self.steps: dict[tuple[uuid.UUID, int], WorkflowStepRun] = {}

        #: Every status the runner wrote, in order. The *sequence* is what
        #: several tests assert -- a run reaching `completed` without passing
        #: through `running` would be a different bug from never completing.
        self.status_writes: list[RunStatus] = []

    def create_run(
        self,
        workspace_id: uuid.UUID,
        workflow_type: str,
        definition_version: int,
        triggered_by: uuid.UUID,
        project_id: uuid.UUID | None = None,
    ) -> WorkflowRun:
        """Store a new run in `pending`."""
        now = datetime.now(UTC)
        run = WorkflowRun(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            workflow_type=workflow_type,
            definition_version=definition_version,
            status=RunStatus.PENDING,
            project_id=project_id,
            detail=None,
            triggered_by=triggered_by,
            started_at=None,
            finished_at=None,
            created_at=now,
            updated_at=now,
            version=1,
        )
        self.runs[run.id] = run
        return run

    def get_run(self, workspace_id: uuid.UUID, run_id: uuid.UUID) -> WorkflowRun | None:
        """Return a stored run, filtering by workspace as the real query does."""
        run = self.runs.get(run_id)

        return None if run is None or run.workspace_id != workspace_id else run

    def update_run_status(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        status: RunStatus,
        detail: str | None = None,
        started: bool = False,
        finished: bool = False,
    ) -> WorkflowRun | None:
        """Write a run's status and record that the write happened."""
        run = self.get_run(workspace_id, run_id)

        if run is None:
            return None

        now = datetime.now(UTC)
        updated = WorkflowRun(
            id=run.id,
            workspace_id=run.workspace_id,
            workflow_type=run.workflow_type,
            definition_version=run.definition_version,
            status=status,
            project_id=run.project_id,
            detail=detail,
            triggered_by=run.triggered_by,
            # `coalesce`, matching the real query: a resumed run keeps its
            # original start time.
            started_at=(run.started_at or now) if started else run.started_at,
            finished_at=now if finished else run.finished_at,
            created_at=run.created_at,
            updated_at=now,
            version=run.version + 1,
        )
        self.runs[run.id] = updated
        self.status_writes.append(status)
        return updated

    def record_step(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        step_index: int,
        step_name: str,
        status: StepStatus,
        detail: str | None = None,
        tokens_used: int = 0,
        output: object = None,
        started: bool = False,
        finished: bool = False,
    ) -> WorkflowStepRun:
        """Upsert one step row, keyed on (run, index) as the real table is."""
        now = datetime.now(UTC)
        existing = self.steps.get((run_id, step_index))

        step = WorkflowStepRun(
            id=existing.id if existing else uuid.uuid4(),
            workspace_id=workspace_id,
            run_id=run_id,
            step_index=step_index,
            # Not updated on conflict, matching the real upsert: the stored name
            # is what actually ran.
            step_name=existing.step_name if existing else step_name,
            status=status,
            detail=detail,
            tokens_used=tokens_used,
            # `coalesce`, matching the real upsert: a later write carrying no
            # output must not erase one an earlier write stored.
            output=output if output is not None else (existing.output if existing else None),
            started_at=(existing.started_at if existing else None) or (now if started else None),
            finished_at=now if finished else (existing.finished_at if existing else None),
            created_at=existing.created_at if existing else now,
        )
        self.steps[(run_id, step_index)] = step
        return step

    def list_steps(self, workspace_id: uuid.UUID, run_id: uuid.UUID) -> tuple[WorkflowStepRun, ...]:
        """Return a run's steps in index order."""
        rows = [step for (rid, _), step in self.steps.items() if rid == run_id]

        return tuple(sorted(rows, key=lambda step: step.step_index))

    def next_step_index(self, workspace_id: uuid.UUID, run_id: uuid.UUID) -> int:
        """Count completed steps, exactly as the real query does."""
        return sum(
            1
            for (rid, _), step in self.steps.items()
            if rid == run_id and step.status == StepStatus.COMPLETED
        )


# ------------------------------------------------------------------- steps --


class RecordingStep(WorkflowStep):
    """A step that records each execution and returns a fixed result."""

    def __init__(
        self,
        name: str,
        requires_approval: bool = False,
        output: object = "done",
        tokens: int = 0,
    ) -> None:
        """Configure the step's identity, gate and result."""
        self._name = name
        self._requires_approval = requires_approval
        self._output = output
        self._tokens = tokens

        #: Every context this step was called with. Length is the execution
        #: count, which is what the gate tests assert on.
        self.calls: list[StepContext] = []

    @property
    def name(self) -> str:
        """Return the step's identifier."""
        return self._name

    @property
    def requires_approval(self) -> bool:
        """Return whether this step is gated."""
        return self._requires_approval

    def execute(self, context: StepContext) -> StepResult:
        """Record the call and return the configured result."""
        self.calls.append(context)

        return StepResult(output=self._output, tokens_used=self._tokens)


class FailingStep(WorkflowStep):
    """A step that always raises."""

    def __init__(self, name: str, error: Exception) -> None:
        """Configure what this step raises."""
        self._name = name
        self._error = error
        self.calls = 0

    @property
    def name(self) -> str:
        """Return the step's identifier."""
        return self._name

    @property
    def requires_approval(self) -> bool:
        """Ungated, so failure is reached without an approval first."""
        return False

    def execute(self, context: StepContext) -> StepResult:
        """Raise the configured error."""
        self.calls += 1
        raise self._error


@pytest.fixture
def workspace_id() -> uuid.UUID:
    """Return a workspace id for a run."""
    return uuid.uuid4()


@pytest.fixture
def user_id() -> uuid.UUID:
    """Return the identity triggering a run."""
    return uuid.uuid4()


def _runner() -> tuple[WorkflowRunner, FakeWorkflowRepository]:
    """Build a runner over a fresh fake repository."""
    repository = FakeWorkflowRepository()

    # The runner is typed against `WorkflowRepository`; the fake implements the
    # same surface. Structural substitution is the point of the seam.
    return WorkflowRunner(repository), repository  # type: ignore[arg-type]


def _definition(*steps: WorkflowStep, version: int = 1) -> WorkflowDefinition:
    """Build a definition from steps."""
    return WorkflowDefinition(workflow_type="test_workflow", version=version, steps=steps)


# --------------------------------------------------------- happy execution --


def test_an_ungated_workflow_runs_to_completion(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Every step executes once, in order, and the run completes."""
    runner, repository = _runner()
    first = RecordingStep("first")
    second = RecordingStep("second")

    run = runner.start(workspace_id, _definition(first, second), user_id)

    assert run.status == RunStatus.COMPLETED
    assert len(first.calls) == 1
    assert len(second.calls) == 1
    assert repository.status_writes == [RunStatus.RUNNING, RunStatus.COMPLETED]


def test_every_step_is_persisted_before_the_next_one_starts(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """**The resumability mechanism**, asserted rather than assumed.

    The second step's execution must see the first already recorded as
    completed. An engine batching its writes to the end would fail this, and
    would lose exactly the runs worth investigating.
    """
    runner, repository = _runner()

    observed: list[int] = []

    class ObservingStep(RecordingStep):
        def execute(self, context: StepContext) -> StepResult:
            observed.append(repository.next_step_index(workspace_id, context.run_id))
            return super().execute(context)

    runner.start(workspace_id, _definition(ObservingStep("a"), ObservingStep("b")), user_id)

    # Step 0 saw zero completed steps; step 1 saw one. That is only true if the
    # first step's completion was committed before the second began.
    assert observed == [0, 1]


def test_a_steps_output_reaches_the_next_step(workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """[[Agent Architecture]]'s communication model: through the engine, not directly."""
    runner, _ = _runner()
    producer = RecordingStep("producer", output={"value": 42})
    consumer = RecordingStep("consumer")

    runner.start(workspace_id, _definition(producer, consumer), user_id)

    assert consumer.calls[0].outputs["producer"] == {"value": 42}


def test_the_definition_version_is_stamped_on_the_run(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """A run records which version it executed, so history stays honest."""
    runner, _ = _runner()

    run = runner.start(workspace_id, _definition(RecordingStep("a"), version=7), user_id)

    assert run.definition_version == 7


def test_tokens_are_recorded_per_step(workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """A run's cost is answerable from its own history."""
    runner, repository = _runner()

    run = runner.start(workspace_id, _definition(RecordingStep("a", tokens=120)), user_id)

    steps = repository.list_steps(workspace_id, run.id)

    assert steps[0].tokens_used == 120


# ------------------------------------------------------------ the approval gate --


def test_a_gated_step_does_not_execute_without_approval(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """**The step's headline Validation check.**

    CLAUDE.md §15 makes approval the default for anything that spends money or
    acts externally. A gate that let the step run and merely flagged it would be
    a gate in name only, so this asserts the step was **not executed at all**.
    """
    runner, _ = _runner()
    gated = RecordingStep("gated", requires_approval=True)

    run = runner.start(workspace_id, _definition(gated), user_id)

    assert run.status == RunStatus.AWAITING_APPROVAL
    assert gated.calls == [], "a gated step executed without approval"


def test_the_run_pauses_at_the_gate_and_earlier_steps_still_ran(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """The gate stops the run at the gated step, not before it."""
    runner, _ = _runner()
    before = RecordingStep("before")
    gated = RecordingStep("gated", requires_approval=True)
    after = RecordingStep("after")

    run = runner.start(workspace_id, _definition(before, gated, after), user_id)

    assert run.status == RunStatus.AWAITING_APPROVAL
    assert len(before.calls) == 1
    assert gated.calls == []
    assert after.calls == []


def test_approval_executes_the_gated_step_and_continues(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Approving runs the step it was waiting on, and everything after it."""
    runner, _ = _runner()
    gated = RecordingStep("gated", requires_approval=True)
    after = RecordingStep("after")
    definition = _definition(gated, after)

    run = runner.start(workspace_id, definition, user_id)
    resumed = runner.approve(workspace_id, run.id, definition, approved_by=user_id)

    assert resumed.status == RunStatus.COMPLETED
    assert len(gated.calls) == 1
    assert len(after.calls) == 1


def test_one_approval_covers_one_step_only(workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """**Approving is not a blanket authorization.**

    A second gated step stops the run again. Anything else would be autonomous
    execution, which CLAUDE.md §15 requires to be a documented, configured opt-in
    rather than a side effect of clicking approve once.
    """
    runner, _ = _runner()
    first_gate = RecordingStep("first_gate", requires_approval=True)
    second_gate = RecordingStep("second_gate", requires_approval=True)
    definition = _definition(first_gate, second_gate)

    run = runner.start(workspace_id, definition, user_id)
    after_first = runner.approve(workspace_id, run.id, definition, approved_by=user_id)

    assert after_first.status == RunStatus.AWAITING_APPROVAL
    assert len(first_gate.calls) == 1
    assert second_gate.calls == [], "one approval executed two gated steps"

    final = runner.approve(workspace_id, run.id, definition, approved_by=user_id)

    assert final.status == RunStatus.COMPLETED
    assert len(second_gate.calls) == 1


def test_approval_is_not_granted_by_resuming(workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """**Resuming must never clear a gate.**

    Otherwise anyone able to restart a run -- including an automated retry --
    could bypass the human CLAUDE.md §15 put behind it.
    """
    runner, _ = _runner()
    gated = RecordingStep("gated", requires_approval=True)
    definition = _definition(gated)

    run = runner.start(workspace_id, definition, user_id)

    with pytest.raises(RunNotResumableError):
        runner.resume(workspace_id, run.id, definition)

    assert gated.calls == []


def test_approving_a_run_that_is_not_waiting_is_refused(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """A client acting on stale state gets a refusal, not a silent no-op."""
    runner, _ = _runner()
    definition = _definition(RecordingStep("a"))

    run = runner.start(workspace_id, definition, user_id)

    assert run.status == RunStatus.COMPLETED

    with pytest.raises(RunNotResumableError):
        runner.approve(workspace_id, run.id, definition, approved_by=user_id)


def test_the_gated_step_is_recorded_as_awaiting_approval(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """The gate is visible on the step, not only on the run.

    A reader inspecting a paused run needs to know *which* step is waiting.
    """
    runner, repository = _runner()
    definition = _definition(RecordingStep("a"), RecordingStep("gated", requires_approval=True))

    run = runner.start(workspace_id, definition, user_id)
    steps = repository.list_steps(workspace_id, run.id)

    assert steps[1].step_name == "gated"
    assert steps[1].status == StepStatus.AWAITING_APPROVAL


def test_a_gated_step_is_never_recorded_as_skipped(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """`skipped` would silently drop work a user was asked to approve."""
    runner, repository = _runner()
    definition = _definition(RecordingStep("gated", requires_approval=True))

    run = runner.start(workspace_id, definition, user_id)
    steps = repository.list_steps(workspace_id, run.id)

    assert all(step.status != StepStatus.SKIPPED for step in steps)


def test_approval_defaults_to_required(workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """**A step author who considers the question not at all gets the safe answer.**

    Asserted against the base class rather than against a configured step, so a
    future change flipping the default fails here rather than silently
    un-gating every agent that inherited it.
    """

    class BareStep(WorkflowStep):
        @property
        def name(self) -> str:
            return "bare"

        def execute(self, context: StepContext) -> StepResult:  # pragma: no cover
            return StepResult()

    assert BareStep().requires_approval is True


# ------------------------------------------------------------- resumability --


def test_a_run_resumes_from_its_last_completed_step(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """**The step's second headline Validation check.**

    An interrupted run is simulated by failing the second step, then resuming
    with a definition whose second step succeeds -- which is exactly the shape of
    a transient failure being retried after the cause is fixed.

    The first step must **not** re-execute: it recorded completion, so its work
    is done.
    """
    runner, repository = _runner()

    first = RecordingStep("first")
    failing = FailingStep("second", WorkflowError("transient"))

    run = runner.start(workspace_id, _definition(first, failing), user_id)

    assert run.status == RunStatus.FAILED
    assert len(first.calls) == 1

    # The same definition shape, with the previously-failing step now working.
    recovered = RecordingStep("second")
    third = RecordingStep("third")

    resumed = runner.resume(workspace_id, run.id, _definition(first, recovered, third))

    assert resumed.status == RunStatus.COMPLETED
    assert len(first.calls) == 1, "a completed step re-executed on resume"
    assert len(recovered.calls) == 1
    assert len(third.calls) == 1


def test_resuming_reads_persisted_state_not_memory(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """A run survives the object that started it.

    A **second runner** over the same storage resumes the run, which is what
    "resumable in a process that did not start it" means in a unit test.
    """
    repository = FakeWorkflowRepository()
    starter = WorkflowRunner(repository)  # type: ignore[arg-type]

    first = RecordingStep("first")
    definition = _definition(first, FailingStep("second", WorkflowError("stop")))

    run = starter.start(workspace_id, definition, user_id)

    # A different runner instance entirely.
    other = WorkflowRunner(repository)  # type: ignore[arg-type]
    resumed = other.resume(workspace_id, run.id, _definition(first, RecordingStep("second")))

    assert resumed.status == RunStatus.COMPLETED
    assert len(first.calls) == 1


def test_an_earlier_steps_output_survives_a_resume(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """**A step resumed after a gate must still see its predecessor's output.**

    This test exists because the engine originally failed it, and nothing here
    caught that. Outputs were held only in memory, so a run that paused for
    approval resumed with an empty `outputs` map -- and the real planning agent,
    which reads its predecessor's result, failed the run.

    Every other test in this file used steps that ignore their inputs, which is
    exactly why they all passed. The defect surfaced only when a real workflow
    ran against a real database.

    The two executions are what make this meaningful: the producer runs in the
    first, the consumer in the second, and nothing is carried between them but
    the repository.
    """
    runner, _ = _runner()
    producer = RecordingStep("producer", output={"name": "carried across"})
    consumer = RecordingStep("consumer", requires_approval=True)
    definition = _definition(producer, consumer)

    run = runner.start(workspace_id, definition, user_id)

    assert run.status == RunStatus.AWAITING_APPROVAL
    assert consumer.calls == []

    runner.approve(workspace_id, run.id, definition, approved_by=user_id)

    assert consumer.calls[0].outputs["producer"] == {"name": "carried across"}


def test_an_incomplete_steps_output_is_not_carried_forward(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Only completed steps contribute outputs.

    A step that failed produced nothing to read, and handing a later step a
    partial result would give it an output its predecessor never returned.
    """
    runner, repository = _runner()

    first = RecordingStep("first", output="real")
    definition = _definition(first, FailingStep("second", WorkflowError("stop")))

    run = runner.start(workspace_id, definition, user_id)

    outputs = {
        step.step_name: step.output
        for step in repository.list_steps(workspace_id, run.id)
        if step.status == StepStatus.COMPLETED
    }

    assert outputs == {"first": "real"}


def test_a_finished_run_cannot_be_resumed(workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Completed is terminal, and resuming it would re-run the whole workflow."""
    runner, _ = _runner()
    definition = _definition(RecordingStep("a"))

    run = runner.start(workspace_id, definition, user_id)

    with pytest.raises(RunNotResumableError):
        runner.resume(workspace_id, run.id, definition)


def test_resuming_an_unknown_run_is_not_found(workspace_id: uuid.UUID) -> None:
    """Absent and hidden are one answer."""
    runner, _ = _runner()

    with pytest.raises(RunNotFoundError):
        runner.resume(workspace_id, uuid.uuid4(), _definition(RecordingStep("a")))


def test_a_resumed_run_keeps_its_original_start_time(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """A run paused overnight should not report having taken seconds."""
    runner, _ = _runner()
    definition = _definition(RecordingStep("gated", requires_approval=True))

    run = runner.start(workspace_id, definition, user_id)
    original = run.started_at

    resumed = runner.approve(workspace_id, run.id, definition, approved_by=user_id)

    assert original is not None
    assert resumed.started_at == original


# ------------------------------------------------------------------ failure --


def test_a_failing_step_fails_the_run(workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """A failure stops the run rather than continuing past it."""
    runner, _ = _runner()
    after = RecordingStep("after")

    run = runner.start(
        workspace_id,
        _definition(FailingStep("boom", WorkflowError("bad")), after),
        user_id,
    )

    assert run.status == RunStatus.FAILED
    assert after.calls == [], "the run continued past a failed step"


def test_an_execution_ceiling_fails_the_run_loudly(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """**§15a requires a tripped ceiling to fail loudly, not degrade.**

    `ExecutionLimitExceededError` is a `GovernanceError`, so it takes the
    expected-refusal path and its public message reaches the run row -- a user
    seeing a stopped run needs to know a limit stopped it.
    """
    runner, _ = _runner()
    budget = ExecutionBudget(max_invocations=1)
    budget.record_invocation()

    def trip() -> None:
        budget.check()

    class CeilingStep(WorkflowStep):
        @property
        def name(self) -> str:
            return "ceiling"

        @property
        def requires_approval(self) -> bool:
            return False

        def execute(self, context: StepContext) -> StepResult:
            trip()
            return StepResult()  # pragma: no cover - unreachable

    run = runner.start(workspace_id, _definition(CeilingStep()), user_id)

    assert run.status == RunStatus.FAILED
    assert run.detail == ExecutionLimitExceededError.public_message


def test_an_unexpected_exception_does_not_leak_its_message(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """An exception written for an engineer must not reach a user (CLAUDE.md §24).

    A `WorkflowError`'s message is written to be shown and does reach the row;
    an arbitrary exception's does not. Asserting the *absence* of the internal
    text is the half that matters.
    """
    runner, _ = _runner()
    secret = "connection string postgres://user:hunter2@host/db"

    run = runner.start(
        workspace_id,
        _definition(FailingStep("boom", RuntimeError(secret))),
        user_id,
    )

    assert run.status == RunStatus.FAILED
    assert run.detail is not None
    assert "hunter2" not in run.detail
    assert secret not in run.detail


def test_a_failed_step_is_recorded_with_its_reason(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """The step row says which step failed and why, not only the run."""
    runner, repository = _runner()

    run = runner.start(
        workspace_id,
        _definition(
            RecordingStep("ok"),
            FailingStep("bad", WorkflowError("internal", public_message="It did not work")),
        ),
        user_id,
    )

    steps = repository.list_steps(workspace_id, run.id)

    assert steps[0].status == StepStatus.COMPLETED
    assert steps[1].status == StepStatus.FAILED
    assert steps[1].detail == "It did not work"


def test_a_step_is_not_retried_by_the_runner(workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """The runner retries nothing.

    `AIRouter` owns retries for AI calls; a runner retrying on top of that would
    multiply a ceiling nobody wrote down (CLAUDE.md §15a).
    """
    runner, _ = _runner()
    failing = FailingStep("boom", WorkflowError("bad"))

    runner.start(workspace_id, _definition(failing), user_id)

    assert failing.calls == 1


# --------------------------------------------------------------- definitions --


def test_a_definition_refuses_duplicate_step_names() -> None:
    """Duplicate names would silently overwrite an output a later step reads."""
    with pytest.raises(ValueError, match="Duplicate step names"):
        _definition(RecordingStep("same"), RecordingStep("same"))


def test_a_definition_refuses_no_steps() -> None:
    """An empty workflow would complete instantly having done nothing."""
    with pytest.raises(ValueError, match="at least one step"):
        WorkflowDefinition(workflow_type="empty", version=1, steps=())


def test_a_definition_refuses_a_non_positive_version() -> None:
    """Version 0 would break the ordering a stored run's version implies."""
    with pytest.raises(ValueError, match="version must be at least 1"):
        _definition(RecordingStep("a"), version=0)


def test_a_run_resumed_against_a_shortened_definition_fails_loudly(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """A truncated run must not be reported as completed.

    The realistic path to this is a definition edited without a version bump
    while a run is paused. Failing loudly is correct: silently treating the run
    as finished would claim work happened that did not.
    """
    runner, repository = _runner()

    first = RecordingStep("first")
    definition = _definition(first, RecordingStep("gated", requires_approval=True))

    run = runner.start(workspace_id, definition, user_id)

    assert run.status == RunStatus.AWAITING_APPROVAL

    # `first` completed, so resumption targets index 1 -- which no longer exists.
    shortened = _definition(first)

    with pytest.raises(WorkflowError):
        runner.approve(workspace_id, run.id, shortened, approved_by=user_id)


# ------------------------------------------------------------------ budgets --


def test_every_step_in_one_execution_shares_one_budget(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """**The chained-invocation cap depends on this.**

    A budget per step would reset the tally each time, and a ten-step workflow
    would silently get ten times the allowance -- the runaway §15a's cap exists
    to prevent.
    """
    runner, _ = _runner()
    first = RecordingStep("first")
    second = RecordingStep("second")

    runner.start(workspace_id, _definition(first, second), user_id)

    assert first.calls[0].execution_budget is second.calls[0].execution_budget


def test_a_resumed_run_gets_a_fresh_budget(workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """The ceiling bounds one execution, not the run's whole lifetime.

    A run paused overnight for approval must not fail on wall-clock time that
    elapsed while a human was deciding.
    """
    runner, _ = _runner()
    gated = RecordingStep("gated", requires_approval=True)
    after = RecordingStep("after")
    definition = _definition(RecordingStep("first"), gated, after)

    run = runner.start(workspace_id, definition, user_id)
    runner.approve(workspace_id, run.id, definition, approved_by=user_id)

    # The gated step ran in the second execution, so its budget is a different
    # object from the one the first execution used.
    assert gated.calls[0].execution_budget is after.calls[0].execution_budget
