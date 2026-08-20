"""The workflow engine's execution rules (STEP-22, re-fenced by STEP-31).

These run **offline**, against a fake repository, and that is deliberate: the
questions here are about *sequencing and gating*, not about SQL. A test needing a
database to prove "a gated step does not execute without approval" would be a
test nobody runs locally, and this is the property CLAUDE.md §15 makes the
default for every agent.

The database-backed halves live in `test_workflows_api.py`, which proves the same
properties survive real persistence and RLS, and `test_workflow_commands.py`,
which proves the fences themselves against real locks, real concurrency and real
grants. All three are necessary and none substitutes for another.

## What changed here, and why this file changed at all

[[STEP-30 Async Job Infrastructure]]'s note said this suite would not need to
change. **That was wrong once ADR-006 existed**, and it is corrected here rather
than quietly dropped: `WorkflowRunner`'s execution *semantics* are unchanged, but
its *entry and settlement protocol* is not. A step is now admitted before it runs
and settled after, and both are refusable -- so the fake has to model the
conditional claim and the three settlement predicates or every assertion about
what the runner does when it loses ownership would be vacuous.

## What the fake repository is, and is not

`FakeWorkflowRepository` records what the runner asked it to persist, in order,
and enforces the same refusals the protected commands do:

- a non-replayable step may be claimed by **one** execution;
- a settlement requires the caller's claim token, a current job lease, and a
  non-terminal run;
- a gated step is admitted only on an unspent grant, and admission spends it.

**What it cannot prove** is that PostgreSQL enforces those under concurrency,
locks and grants -- a fake has no `FOR UPDATE` and no RLS. That is
`test_workflow_commands.py`'s job, and a fake pretending otherwise would be worse
than no test: STEP-23's chat defect shipped green against exactly such a fake.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from app.ai.governance import ExecutionBudget, ExecutionLimitExceededError
from app.repositories.workflows import WorkflowRepository, WorkflowRun, WorkflowStepRun
from app.workflows.models import (
    RunNotFoundError,
    RunNotResumableError,
    RunStatus,
    StepApprovalRequiredError,
    StepContext,
    StepInterruptedError,
    StepOwnershipLostError,
    StepResult,
    StepStatus,
    WorkflowDefinition,
    WorkflowError,
    WorkflowStep,
)
from app.workflows.runner import WorkflowRunner

#: The job every execution in this file is delivering, and the lease proving it
#: still owns that job. Fixed values because their *identity* is what the fences
#: compare -- a test that rotates one is simulating a takeover, and says so.
JOB_ID = uuid.UUID("00000000-0000-4000-8000-00000000f0b1")
LEASE = uuid.UUID("00000000-0000-4000-8000-00000000f0b2")


class FakeWorkflowRepository:
    """In-memory storage that behaves like `WorkflowRepository`, refusals included.

    Deliberately not a `Mock`: the runner writes state and then reads it back to
    decide where to resume, so a fake that did not actually store would make
    every resumability assertion vacuous -- and one that accepted every write
    would make every fencing assertion vacuous too.
    """

    def __init__(self) -> None:
        """Start with no runs, no steps, and one live job holding its lease."""
        self.runs: dict[uuid.UUID, WorkflowRun] = {}
        self.steps: dict[tuple[uuid.UUID, int], WorkflowStepRun] = {}

        #: Which claim token each claimed step holds. Kept beside the rows rather
        #: than on them, because `WorkflowStepRun` deliberately carries no
        #: fencing column: `authenticated` holds no `SELECT` grant on them.
        self.claims: dict[tuple[uuid.UUID, int], uuid.UUID] = {}

        #: Every status the runner wrote, in order. The *sequence* is what
        #: several tests assert -- a run reaching `completed` without passing
        #: through `running` would be a different bug from never completing.
        self.status_writes: list[RunStatus] = []

        #: The lease currently on the job. Rotating it is how a test says
        #: "another worker took this job over".
        self.live_lease: uuid.UUID = LEASE

    # ------------------------------------------------------ test affordances --

    def create_run(
        self,
        workspace_id: uuid.UUID,
        workflow_type: str,
        definition_version: int,
        triggered_by: uuid.UUID,
        project_id: uuid.UUID | None = None,
    ) -> WorkflowRun:
        """Store a new run in `pending`, as `app_start_workflow_run` would."""
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

    def grant_approval(self, run_id: uuid.UUID, step_index: int, approver: uuid.UUID) -> None:
        """Write an unspent grant, as `app_approve_workflow_step` would.

        The real command also enqueues the job that spends it, in the same
        transaction. That inseparability is a database property and is asserted
        against a database; here the grant alone is what the runner reads.
        """
        step = self.steps[(run_id, step_index)]
        self.steps[(run_id, step_index)] = _replace(step, approved_by=approver)

    def rotate_lease(self) -> uuid.UUID:
        """Simulate another worker claiming the job, superseding this lease."""
        self.live_lease = uuid.uuid4()
        return self.live_lease

    def hold_claim(self, run_id: uuid.UUID, step_index: int) -> uuid.UUID:
        """Simulate a step already claimed by an execution that never released it."""
        token = uuid.uuid4()
        self.claims[(run_id, step_index)] = token
        return token

    # --------------------------------------------------------------- reading --

    def get_run(self, workspace_id: uuid.UUID, run_id: uuid.UUID) -> WorkflowRun | None:
        """Return a stored run, filtering by workspace as the real query does."""
        run = self.runs.get(run_id)

        return None if run is None or run.workspace_id != workspace_id else run

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

    # --------------------------------------------------------------- writing --

    def update_run_status(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        status: RunStatus,
        detail: str | None = None,
        started: bool = False,
        finished: bool = False,
    ) -> WorkflowRun | None:
        """Write a run's status, refusing to move one that is already terminal."""
        run = self.get_run(workspace_id, run_id)

        if run is None or RunStatus(run.status) in (RunStatus.COMPLETED, RunStatus.FAILED):
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

    def admit_step(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        step_index: int,
        step_name: str,
        requires_approval: bool,
        replayable: bool,
        job_id: uuid.UUID,
        lease_token: uuid.UUID,
    ) -> uuid.UUID | None:
        """Enter a step, refusing exactly what `app_admit_workflow_step` refuses."""
        if lease_token != self.live_lease:
            raise StepOwnershipLostError("the job has been re-claimed by another worker")

        existing = self.steps.get((run_id, step_index))

        if requires_approval and (existing is None or existing.approved_by is None):
            raise StepApprovalRequiredError("this step needs a fresh approval")

        claim: uuid.UUID | None = None

        if not replayable:
            if (run_id, step_index) in self.claims:
                raise StepInterruptedError("this step is already held by another execution")

            claim = uuid.uuid4()
            self.claims[(run_id, step_index)] = claim

        now = datetime.now(UTC)
        self.steps[(run_id, step_index)] = WorkflowStepRun(
            id=existing.id if existing else uuid.uuid4(),
            workspace_id=workspace_id,
            run_id=run_id,
            step_index=step_index,
            step_name=step_name,
            status=StepStatus.RUNNING,
            detail=None,
            tokens_used=existing.tokens_used if existing else 0,
            output=existing.output if existing else None,
            started_at=(existing.started_at if existing else None) or now,
            finished_at=None,
            created_at=existing.created_at if existing else now,
            # Consumed at admission, whatever the step's replayability, so a
            # gated step that is also replayable spends its grant exactly once.
            approved_by=None,
        )

        return claim

    def settle_step(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
        step_index: int,
        step_name: str,
        status: StepStatus,
        job_id: uuid.UUID,
        lease_token: uuid.UUID,
        claim_token: uuid.UUID | None = None,
        detail: str | None = None,
        output: object = None,
        tokens_used: int = 0,
    ) -> bool:
        """Persist a step's outcome, subject to the same three predicates.

        Returns False and writes **nothing** when any of them fails, which is the
        behaviour the runner has to react to correctly.
        """
        run = self.runs.get(run_id)

        # (3) the run has not already been terminally reconciled.
        if run is None or RunStatus(run.status) in (RunStatus.COMPLETED, RunStatus.FAILED):
            return False

        # (1) the claim on the step is this caller's.
        if self.claims.get((run_id, step_index)) != claim_token:
            return False

        # (2) this caller still holds the job's current lease.
        if lease_token != self.live_lease:
            return False

        now = datetime.now(UTC)
        existing = self.steps.get((run_id, step_index))

        self.steps[(run_id, step_index)] = WorkflowStepRun(
            id=existing.id if existing else uuid.uuid4(),
            workspace_id=workspace_id,
            run_id=run_id,
            step_index=step_index,
            step_name=step_name,
            status=status,
            detail=detail,
            tokens_used=tokens_used,
            # `coalesce`, matching the real command: a later write carrying no
            # output must not erase one an earlier write stored.
            output=output if output is not None else (existing.output if existing else None),
            started_at=(existing.started_at if existing else None)
            or (now if status == StepStatus.RUNNING else None),
            finished_at=now
            if status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED)
            else (existing.finished_at if existing else None),
            created_at=existing.created_at if existing else now,
            approved_by=None,
        )
        self.claims.pop((run_id, step_index), None)

        return True


def _run_status(run: WorkflowRun, status: RunStatus) -> WorkflowRun:
    """Return a copy of a run with its status replaced.

    Stands in for `app_recover_workflow_run` re-arming a failed run. The command
    does more -- it supersedes the stale claim, audits the decision, and either
    enqueues or re-arms the gate -- and all of that is asserted against a real
    database. Here the only part the runner reacts to is the status.
    """
    return WorkflowRun(
        id=run.id,
        workspace_id=run.workspace_id,
        workflow_type=run.workflow_type,
        definition_version=run.definition_version,
        status=status,
        project_id=run.project_id,
        detail=run.detail,
        triggered_by=run.triggered_by,
        started_at=run.started_at,
        finished_at=None,
        created_at=run.created_at,
        updated_at=run.updated_at,
        version=run.version + 1,
    )


def _replace(step: WorkflowStepRun, **changes: object) -> WorkflowStepRun:
    """Return a copy of a step row with fields replaced."""
    fields = {
        "id": step.id,
        "workspace_id": step.workspace_id,
        "run_id": step.run_id,
        "step_index": step.step_index,
        "step_name": step.step_name,
        "status": step.status,
        "detail": step.detail,
        "tokens_used": step.tokens_used,
        "output": step.output,
        "started_at": step.started_at,
        "finished_at": step.finished_at,
        "created_at": step.created_at,
        "approved_by": step.approved_by,
    }
    fields.update(changes)

    return WorkflowStepRun(**fields)  # type: ignore[arg-type]


# ------------------------------------------------------------------- steps --


class RecordingStep(WorkflowStep):
    """A step that records each execution and returns a fixed result."""

    def __init__(
        self,
        name: str,
        requires_approval: bool = False,
        output: object = "done",
        tokens: int = 0,
        replayable: bool = True,
    ) -> None:
        """Configure the step's identity, gate, replayability and result."""
        self._name = name
        self._requires_approval = requires_approval
        self._output = output
        self._tokens = tokens
        self._replayable = replayable

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

    @property
    def replayable(self) -> bool:
        """Return whether re-executing this step is free of external effect.

        Defaults to `True` here, unlike the base class: most steps in this file
        exist to assert sequencing, and claiming every one of them would make the
        claim tests indistinguishable from the rest.
        """
        return self._replayable

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

    @property
    def replayable(self) -> bool:
        """Replayable, so failure is reached without a claim in the way."""
        return True

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


def _runner(
    repository: FakeWorkflowRepository | None = None,
) -> tuple[WorkflowRunner, FakeWorkflowRepository]:
    """Build a runner over a fake repository, with no real sessions behind it."""
    store = repository if repository is not None else FakeWorkflowRepository()

    @contextmanager
    def sessions() -> Iterator[None]:
        # The runner opens one short session per unit of work and hands it to
        # the repository factory. Offline there is nothing to open, and the
        # factory ignores what it is given.
        yield None

    def repositories(_connection: object) -> WorkflowRepository:
        return store  # type: ignore[return-value]

    return WorkflowRunner(sessions, repositories), store  # type: ignore[arg-type]


def _definition(*steps: WorkflowStep, version: int = 1) -> WorkflowDefinition:
    """Build a definition from steps."""
    return WorkflowDefinition(workflow_type="test_workflow", version=version, steps=steps)


def _definitions(definition: WorkflowDefinition) -> object:
    """Return a definitions factory that always yields `definition`."""

    def for_type(_workflow_type: str) -> object:
        # Takes the runner's *session factory*, not a connection: a definition
        # holds no connection any more, which is what keeps a provider call from
        # running inside an open transaction (ADR-005 §4).
        def build(_sessions: object) -> WorkflowDefinition:
            return definition

        return build

    return for_type


def _start(
    runner: WorkflowRunner,
    repository: FakeWorkflowRepository,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    definition: WorkflowDefinition,
) -> WorkflowRun:
    """Create a run and execute it, as the start command and a worker together do."""
    run = repository.create_run(
        workspace_id=workspace_id,
        workflow_type=definition.workflow_type,
        definition_version=definition.version,
        triggered_by=user_id,
    )

    return _execute(runner, workspace_id, run.id, definition)


def _execute(
    runner: WorkflowRunner,
    workspace_id: uuid.UUID,
    run_id: uuid.UUID,
    definition: WorkflowDefinition,
    lease: uuid.UUID = LEASE,
) -> WorkflowRun:
    """Deliver one job for a run, as a worker does."""
    return runner.execute(
        workspace_id=workspace_id,
        run_id=run_id,
        definitions=_definitions(definition),  # type: ignore[arg-type]
        job_id=JOB_ID,
        lease_token=lease,
    )


def _approve(
    runner: WorkflowRunner,
    repository: FakeWorkflowRepository,
    workspace_id: uuid.UUID,
    run: WorkflowRun,
    definition: WorkflowDefinition,
    approver: uuid.UUID,
) -> WorkflowRun:
    """Grant the awaited step's approval and deliver the job that spends it."""
    awaited = next(
        step
        for step in repository.list_steps(workspace_id, run.id)
        if step.status == StepStatus.AWAITING_APPROVAL
    )
    repository.grant_approval(run.id, awaited.step_index, approver)

    return _execute(runner, workspace_id, run.id, definition)


# --------------------------------------------------------- happy execution --


def test_an_ungated_workflow_runs_to_completion(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Every step executes once, in order, and the run completes."""
    runner, repository = _runner()
    first = RecordingStep("first")
    second = RecordingStep("second")

    run = _start(runner, repository, workspace_id, user_id, _definition(first, second))

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

    _start(
        runner,
        repository,
        workspace_id,
        user_id,
        _definition(ObservingStep("a"), ObservingStep("b")),
    )

    # Step 0 saw zero completed steps; step 1 saw one. That is only true if the
    # first step's completion was committed before the second began.
    assert observed == [0, 1]


def test_a_steps_output_reaches_the_next_step(workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """[[Agent Architecture]]'s communication model: through the engine, not directly."""
    runner, repository = _runner()
    producer = RecordingStep("producer", output={"value": 42})
    consumer = RecordingStep("consumer")

    _start(runner, repository, workspace_id, user_id, _definition(producer, consumer))

    assert consumer.calls[0].outputs["producer"] == {"value": 42}


def test_the_definition_version_is_stamped_on_the_run(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """A run records which version it executed, so history stays honest."""
    runner, repository = _runner()

    run = _start(
        runner, repository, workspace_id, user_id, _definition(RecordingStep("a"), version=7)
    )

    assert run.definition_version == 7


def test_tokens_are_recorded_per_step(workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """A run's cost is answerable from its own history."""
    runner, repository = _runner()

    run = _start(
        runner, repository, workspace_id, user_id, _definition(RecordingStep("a", tokens=120))
    )

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
    runner, repository = _runner()
    gated = RecordingStep("gated", requires_approval=True)

    run = _start(runner, repository, workspace_id, user_id, _definition(gated))

    assert run.status == RunStatus.AWAITING_APPROVAL
    assert gated.calls == [], "a gated step executed without approval"


def test_the_run_pauses_at_the_gate_and_earlier_steps_still_ran(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """The gate stops the run at the gated step, not before it."""
    runner, repository = _runner()
    before = RecordingStep("before")
    gated = RecordingStep("gated", requires_approval=True)
    after = RecordingStep("after")

    run = _start(runner, repository, workspace_id, user_id, _definition(before, gated, after))

    assert run.status == RunStatus.AWAITING_APPROVAL
    assert len(before.calls) == 1
    assert gated.calls == []
    assert after.calls == []


def test_approval_executes_the_gated_step_and_continues(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Approving runs the step it was waiting on, and everything after it."""
    runner, repository = _runner()
    gated = RecordingStep("gated", requires_approval=True)
    after = RecordingStep("after")
    definition = _definition(gated, after)

    run = _start(runner, repository, workspace_id, user_id, definition)
    resumed = _approve(runner, repository, workspace_id, run, definition, user_id)

    assert resumed.status == RunStatus.COMPLETED
    assert len(gated.calls) == 1
    assert len(after.calls) == 1


def test_one_approval_covers_one_step_only(workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """**Approving is not a blanket authorization.**

    A second gated step stops the run again. Anything else would be autonomous
    execution, which CLAUDE.md §15 requires to be a documented, configured opt-in
    rather than a side effect of clicking approve once.
    """
    runner, repository = _runner()
    first_gate = RecordingStep("first_gate", requires_approval=True)
    second_gate = RecordingStep("second_gate", requires_approval=True)
    definition = _definition(first_gate, second_gate)

    run = _start(runner, repository, workspace_id, user_id, definition)
    after_first = _approve(runner, repository, workspace_id, run, definition, user_id)

    assert after_first.status == RunStatus.AWAITING_APPROVAL
    assert len(first_gate.calls) == 1
    assert second_gate.calls == [], "one approval executed two gated steps"

    final = _approve(runner, repository, workspace_id, after_first, definition, user_id)

    assert final.status == RunStatus.COMPLETED
    assert len(second_gate.calls) == 1


def test_a_redelivery_does_not_clear_a_gate(workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """**Delivering the job again must never clear a gate.**

    Otherwise anything able to re-deliver a job -- a lease recovery, an
    automatic retry -- could bypass the human CLAUDE.md §15 put behind it. The
    run pauses again, and the step still has not executed.
    """
    runner, repository = _runner()
    gated = RecordingStep("gated", requires_approval=True)
    definition = _definition(gated)

    run = _start(runner, repository, workspace_id, user_id, definition)

    assert run.status == RunStatus.AWAITING_APPROVAL

    redelivered = _execute(runner, workspace_id, run.id, definition)

    assert redelivered.status == RunStatus.AWAITING_APPROVAL
    assert gated.calls == []


def test_a_grant_is_spent_once_even_for_a_replayable_step(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """**Consumption happens at admission, not at claim time.**

    A step that is gated *and* replayable takes no claim, so tying consumption
    to the claim would leave its grant unspent forever and let every redelivery
    re-run a step a person approved once. Admission is the one thing every step
    passes through, whatever its replayability, which is why the grant is spent
    there (ADR-006 D9).
    """
    runner, repository = _runner()
    gated = RecordingStep("gated", requires_approval=True, replayable=True)
    definition = _definition(gated)

    run = _start(runner, repository, workspace_id, user_id, definition)
    completed = _approve(runner, repository, workspace_id, run, definition, user_id)

    assert completed.status == RunStatus.COMPLETED
    assert len(gated.calls) == 1

    awaited = repository.list_steps(workspace_id, run.id)[0]

    assert awaited.approved_by is None, "the grant survived the execution that spent it"


def test_the_gated_step_is_recorded_as_awaiting_approval(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """The gate is visible on the step, not only on the run.

    A reader inspecting a paused run needs to know *which* step is waiting.
    """
    runner, repository = _runner()
    definition = _definition(RecordingStep("a"), RecordingStep("gated", requires_approval=True))

    run = _start(runner, repository, workspace_id, user_id, definition)
    steps = repository.list_steps(workspace_id, run.id)

    assert steps[1].step_name == "gated"
    assert steps[1].status == StepStatus.AWAITING_APPROVAL


def test_a_gated_step_is_never_recorded_as_skipped(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """`skipped` would silently drop work a user was asked to approve."""
    runner, repository = _runner()
    definition = _definition(RecordingStep("gated", requires_approval=True))

    run = _start(runner, repository, workspace_id, user_id, definition)
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


def test_replayability_defaults_to_unsafe(workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """**The same defaulting decision, for the same reason.**

    A step author who never considered whether re-running their step costs money
    ships the guarded behaviour. Declaring a step replayable when it is not
    removes the only thing standing between a lapsed job lease and a provider
    being paid twice, so the default has to be the one that is never wrong.
    """

    class BareStep(WorkflowStep):
        @property
        def name(self) -> str:
            return "bare"

        def execute(self, context: StepContext) -> StepResult:  # pragma: no cover
            return StepResult()

    assert BareStep().replayable is False


# ------------------------------------------------------- claims and fencing --


def test_a_non_replayable_step_is_claimed_and_a_replayable_one_is_not(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """The claim is taken for exactly the steps that need one.

    Claiming a pure step would buy nothing and would strand a run on work that
    was always safe to repeat.
    """
    runner, repository = _runner()
    pure = RecordingStep("pure", replayable=True)
    paid = RecordingStep("paid", replayable=False)

    run = _start(runner, repository, workspace_id, user_id, _definition(pure, paid))

    assert run.status == RunStatus.COMPLETED

    # Both claims are released by their own settlement; what is asserted is that
    # only one was ever taken, which the fake records as it happens.
    assert repository.claims == {}


def test_a_claimed_step_interrupts_a_replacement_execution(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """**The single most dangerous case in this step, asserted directly.**

    A replacement worker reaching a non-replayable step another execution still
    holds must not run it, must not settle it, and must not report success. It
    raises, terminally, and the job it was delivering dead-letters -- which
    reconciles the run rather than leaving it running forever with nothing able
    to advance it.
    """
    runner, repository = _runner()
    paid = RecordingStep("paid", replayable=False)
    definition = _definition(paid)

    run = repository.create_run(
        workspace_id=workspace_id,
        workflow_type=definition.workflow_type,
        definition_version=definition.version,
        triggered_by=user_id,
    )
    repository.hold_claim(run.id, 0)

    with pytest.raises(StepInterruptedError):
        _execute(runner, workspace_id, run.id, definition)

    assert paid.calls == [], "a replacement execution ran a step another one held"
    assert repository.get_run(workspace_id, run.id).status != RunStatus.COMPLETED  # type: ignore[union-attr]


def test_a_fenced_settlement_writes_nothing_and_does_not_fail_the_run(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Losing the job mid-step stops this execution and touches nothing.

    The step keeps whatever it had, the run is not failed by this worker, and
    the failure is terminal so the job dead-letters. Failing the run from here
    would be this execution overwriting a run another worker may legitimately be
    advancing.
    """
    runner, repository = _runner()

    class LosingStep(RecordingStep):
        def execute(self, context: StepContext) -> StepResult:
            # The lease rotates while the step is running: another worker has
            # claimed this job.
            repository.rotate_lease()
            return super().execute(context)

    definition = _definition(LosingStep("loses"))
    run = repository.create_run(
        workspace_id=workspace_id,
        workflow_type=definition.workflow_type,
        definition_version=definition.version,
        triggered_by=user_id,
    )

    with pytest.raises(StepOwnershipLostError):
        _execute(runner, workspace_id, run.id, definition)

    stored = repository.get_run(workspace_id, run.id)

    assert stored is not None
    assert stored.status != RunStatus.FAILED, "a fenced worker failed a run it no longer owned"
    assert repository.list_steps(workspace_id, run.id)[0].status == StepStatus.RUNNING


def test_an_execution_that_lost_its_lease_never_enters_the_next_step(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Admission is fenced too, not only settlement.

    A worker whose lease lapsed between steps must not enter the next one -- the
    provider call it would make is the cost this whole design exists to avoid.
    """
    runner, repository = _runner()
    second = RecordingStep("second")

    class RotatingStep(RecordingStep):
        def execute(self, context: StepContext) -> StepResult:
            result = super().execute(context)
            repository.rotate_lease()
            return result

    definition = _definition(RotatingStep("first"), second)
    run = repository.create_run(
        workspace_id=workspace_id,
        workflow_type=definition.workflow_type,
        definition_version=definition.version,
        triggered_by=user_id,
    )

    with pytest.raises(StepOwnershipLostError):
        _execute(runner, workspace_id, run.id, definition)

    assert second.calls == []


# ------------------------------------------------------------- resumability --


def test_a_run_resumes_from_its_last_completed_step(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """**The step's second headline Validation check.**

    An interrupted run is simulated by failing the second step, then delivering
    again with a definition whose second step succeeds -- which is exactly the
    shape of a transient failure being retried after the cause is fixed.

    The first step must **not** re-execute: it recorded completion, so its work
    is done.
    """
    runner, repository = _runner()

    first = RecordingStep("first")
    failing = FailingStep("second", WorkflowError("transient"))

    run = _start(runner, repository, workspace_id, user_id, _definition(first, failing))

    assert run.status == RunStatus.FAILED
    assert len(first.calls) == 1

    # Recovery re-arms the run; the runner refuses to move a terminal one.
    repository.runs[run.id] = _run_status(repository.runs[run.id], RunStatus.PENDING)

    recovered = RecordingStep("second")
    third = RecordingStep("third")

    resumed = _execute(runner, workspace_id, run.id, _definition(first, recovered, third))

    assert resumed.status == RunStatus.COMPLETED
    assert len(first.calls) == 1, "a completed step re-executed on resume"
    assert len(recovered.calls) == 1
    assert len(third.calls) == 1


def test_resuming_reads_persisted_state_not_memory(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """A run survives the object that started it.

    A **second runner** over the same storage continues the run, which is what
    "resumable in a process that did not start it" means in a unit test.
    """
    starter, repository = _runner()

    first = RecordingStep("first")
    gated = RecordingStep("gated", requires_approval=True)
    definition = _definition(first, gated)

    run = _start(starter, repository, workspace_id, user_id, definition)

    assert run.status == RunStatus.AWAITING_APPROVAL

    # A different runner instance entirely, over the same storage.
    other, _ = _runner(repository)
    resumed = _approve(other, repository, workspace_id, run, definition, user_id)

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

    The two executions are what make this meaningful: the producer runs in the
    first, the consumer in the second, and nothing is carried between them but
    the repository.
    """
    runner, repository = _runner()
    producer = RecordingStep("producer", output={"name": "carried across"})
    consumer = RecordingStep("consumer", requires_approval=True)
    definition = _definition(producer, consumer)

    run = _start(runner, repository, workspace_id, user_id, definition)

    assert run.status == RunStatus.AWAITING_APPROVAL
    assert consumer.calls == []

    _approve(runner, repository, workspace_id, run, definition, user_id)

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

    run = _start(runner, repository, workspace_id, user_id, definition)

    outputs = {
        step.step_name: step.output
        for step in repository.list_steps(workspace_id, run.id)
        if step.status == StepStatus.COMPLETED
    }

    assert outputs == {"first": "real"}


def test_a_finished_run_is_never_re_entered(workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Completed is terminal, and re-entering it would re-run the whole workflow."""
    runner, repository = _runner()
    definition = _definition(RecordingStep("a"))

    run = _start(runner, repository, workspace_id, user_id, definition)

    assert run.status == RunStatus.COMPLETED

    with pytest.raises(RunNotResumableError):
        _execute(runner, workspace_id, run.id, definition)


def test_executing_an_unknown_run_is_not_found(workspace_id: uuid.UUID) -> None:
    """Absent and hidden are one answer."""
    runner, _ = _runner()

    with pytest.raises(RunNotFoundError):
        _execute(runner, workspace_id, uuid.uuid4(), _definition(RecordingStep("a")))


def test_a_resumed_run_keeps_its_original_start_time(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """A run paused overnight should not report having taken seconds."""
    runner, repository = _runner()
    definition = _definition(RecordingStep("gated", requires_approval=True))

    run = _start(runner, repository, workspace_id, user_id, definition)
    original = run.started_at

    resumed = _approve(runner, repository, workspace_id, run, definition, user_id)

    assert original is not None
    assert resumed.started_at == original


# ------------------------------------------------------------------ failure --


def test_a_failing_step_fails_the_run(workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """A failure stops the run rather than continuing past it."""
    runner, repository = _runner()
    after = RecordingStep("after")

    run = _start(
        runner,
        repository,
        workspace_id,
        user_id,
        _definition(FailingStep("boom", WorkflowError("bad")), after),
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
    runner, repository = _runner()
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

        @property
        def replayable(self) -> bool:
            return True

        def execute(self, context: StepContext) -> StepResult:
            trip()
            return StepResult()  # pragma: no cover - unreachable

    run = _start(runner, repository, workspace_id, user_id, _definition(CeilingStep()))

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
    runner, repository = _runner()
    secret = "connection string postgres://user:hunter2@host/db"

    run = _start(
        runner,
        repository,
        workspace_id,
        user_id,
        _definition(FailingStep("boom", RuntimeError(secret))),
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

    run = _start(
        runner,
        repository,
        workspace_id,
        user_id,
        _definition(
            RecordingStep("ok"),
            FailingStep("bad", WorkflowError("internal", public_message="It did not work")),
        ),
    )

    steps = repository.list_steps(workspace_id, run.id)

    assert steps[0].status == StepStatus.COMPLETED
    assert steps[1].status == StepStatus.FAILED
    assert steps[1].detail == "It did not work"


def test_a_step_is_not_retried_by_the_runner(workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """The runner retries nothing.

    `AIRouter` owns retries for AI calls and the job owns retries for the job; a
    runner retrying on top of both would multiply a ceiling nobody wrote down
    (CLAUDE.md §15a).
    """
    runner, repository = _runner()
    failing = FailingStep("boom", WorkflowError("bad"))

    _start(runner, repository, workspace_id, user_id, _definition(failing))

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

    run = _start(runner, repository, workspace_id, user_id, definition)

    assert run.status == RunStatus.AWAITING_APPROVAL

    # `first` completed, so the next delivery targets index 1 -- which no longer
    # exists in the shortened definition.
    shortened = _definition(first)

    with pytest.raises(WorkflowError):
        _execute(runner, workspace_id, run.id, shortened)


# ------------------------------------------------------------------ budgets --


def test_every_step_in_one_execution_shares_one_budget(
    workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """**The chained-invocation cap depends on this.**

    A budget per step would reset the tally each time, and a ten-step workflow
    would silently get ten times the allowance -- the runaway §15a's cap exists
    to prevent.
    """
    runner, repository = _runner()
    first = RecordingStep("first")
    second = RecordingStep("second")

    _start(runner, repository, workspace_id, user_id, _definition(first, second))

    assert first.calls[0].execution_budget is second.calls[0].execution_budget


def test_a_resumed_run_gets_a_fresh_budget(workspace_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """The ceiling bounds one execution, not the run's whole lifetime.

    A run paused overnight for approval must not fail on wall-clock time that
    elapsed while a human was deciding.
    """
    runner, repository = _runner()
    first = RecordingStep("first")
    gated = RecordingStep("gated", requires_approval=True)
    after = RecordingStep("after")
    definition = _definition(first, gated, after)

    run = _start(runner, repository, workspace_id, user_id, definition)
    _approve(runner, repository, workspace_id, run, definition, user_id)

    # The first execution ran `first`; the second ran `gated` and `after`. Steps
    # inside one execution share a budget, and the two executions do not.
    assert gated.calls[0].execution_budget is after.calls[0].execution_budget
    assert first.calls[0].execution_budget is not gated.calls[0].execution_budget
