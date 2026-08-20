"""The workflow vocabulary: run and step states, the step contract, definitions.

This module is what the engine, the repository and the routes all depend on, and
it deliberately imports nothing from any of them. A step knows how to do its own
work; it knows nothing about HTTP, about persistence, or about the runner that
sequences it.

## The seven phases, and where they live

[[Workflow Engine]] gives the lifecycle:

    Trigger -> Validation -> Planning -> Agent Execution -> Quality Checks
            -> User Approval (optional) -> Completion

**Those are phases of a run, not a fixed list of classes.** Trigger and
Completion are the runner's own boundaries -- a run starting and finishing --
rather than steps a definition lists. The five in between are `WorkflowStep`
implementations, which is what makes a definition a sequence of steps rather than
a hardcoded pipeline: [[Agent Architecture]] requires that "new agents can be
added, replaced or upgraded without affecting existing workflows", and a runner
with the phases baked in could not do that.

## Why a step returns a result rather than mutating a run

`WorkflowStep.execute` returns a `StepResult` and writes nothing. The runner
persists it. That split is what makes a step testable without a database and
makes persistence happen in exactly one place -- a step that wrote its own row
would be a second persistence path, and the resumability guarantee would then
depend on every step remembering to use it.

## Approval is declared, not decided

`requires_approval` is a property of the *step*, set when the definition is
written, and the runner reads it. A step that decided at runtime whether it
needed approval would put the gate under the control of the thing being gated.

[[CLAUDE|CLAUDE.md]] §15's default applies: **any step that writes data, spends
money, publishes, or acts externally requires approval unless an exemption is
documented.** `requires_approval` therefore defaults to `True`, so a step author
who thinks about it not at all gets the safe behaviour.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.ai.governance import ExecutionBudget


class RunStatus(StrEnum):
    """Where a run is.

    The values match `ck_workflow_runs_status_valid` in migration `f3c82b19d4a7`
    exactly. `StrEnum` so a value compares equal to the string the database
    stores -- the same choice `ProjectStatus` and `WorkspaceRole` make.

    `test_run_status_vocabulary_matches_the_database` asserts the two against
    each other rather than trusting they were edited together. That test exists
    because STEP-21 paid for its absence on `assets.kind`.
    """

    #: Created, not yet started. A run is persisted before it executes so that a
    #: crash between creation and first step leaves a record rather than nothing.
    PENDING = "pending"

    RUNNING = "running"

    #: Stopped at a gated step, waiting for a human. A first-class state rather
    #: than a flag on `running`: a run waiting for approval is not executing, and
    #: conflating them makes "how many runs are in flight" unanswerable.
    AWAITING_APPROVAL = "awaiting_approval"

    COMPLETED = "completed"

    #: Terminal failure. Includes a tripped execution ceiling, which §15a
    #: requires to fail loudly rather than degrade.
    FAILED = "failed"


#: Run states from which no further execution happens.
TERMINAL_RUN_STATUSES: frozenset[RunStatus] = frozenset({RunStatus.COMPLETED, RunStatus.FAILED})


class StepStatus(StrEnum):
    """Where one step of a run is.

    Matches `ck_workflow_step_runs_status_valid` in the same migration.
    """

    PENDING = "pending"
    RUNNING = "running"

    #: This step is gated and has not been approved yet. The run carries the same
    #: state, so a reader sees the gate on both the run and the step responsible.
    AWAITING_APPROVAL = "awaiting_approval"

    COMPLETED = "completed"
    FAILED = "failed"

    #: Reserved for a step a future conditional definition chooses not to run.
    #: Nothing produces it today -- branching is explicitly out of this step's
    #: scope -- but the vocabulary includes it because adding a value to a CHECK
    #: constraint later is a migration, and this one costs nothing now.
    SKIPPED = "skipped"


class WorkflowError(Exception):
    """A workflow could not proceed.

    Distinct from a provider or governance error, which have their own handlers.
    This is the engine's own refusal: an unknown workflow type, a run that cannot
    be resumed, a step asked to run out of order.
    """

    public_message = "This workflow could not be run"

    def __init__(self, message: str, public_message: str | None = None) -> None:
        """Record the internal message, and optionally a safe public one."""
        super().__init__(message)

        if public_message is not None:
            self.public_message = public_message


class RunNotFoundError(WorkflowError):
    """No live run matched, either because it does not exist or RLS hid it.

    The two causes are deliberately one error, exactly as `ProjectNotFoundError`
    conflates them. Distinguishing them would tell a caller that a run exists in
    a workspace they cannot see.
    """

    public_message = "Workflow run not found"

    def __init__(self, message: str = "Workflow run not found") -> None:
        """Record the internal message; `public_message` is what a client sees."""
        super().__init__(message)


class WorkflowStateConflictError(WorkflowError):
    """The run or step is not in a state that accepts this transition.

    **409, not 422.** The request was well-formed and the caller holds every
    permission it needs; the resource's own state is what refuses -- the same
    distinction `IllegalTransitionError` draws for a project.

    Raised when a protected command refuses under its row locks: a run that is
    not waiting for an approval, a step index the run is not waiting on, a grant
    that has already been spent, a run that is not `failed` and therefore has
    nothing to recover. The command's own message is kept as the internal one;
    what reaches a client is the fixed sentence below (ADR-006 D7).
    """

    public_message = "This run is not in a state that allows this action"


class StepApprovalRequiredError(WorkflowError):
    """This step needs a fresh, unspent approval before it can execute.

    Raised by admission, under the step's row lock, when a gated step's grant is
    absent or has already been consumed. **It never reaches a client**: the
    runner catches it, records the step and its run as `awaiting_approval`, and
    returns -- which is what a workflow pausing at a gate *is*.

    A separate type from `WorkflowStateConflictError` because the runner has to
    tell "pause and wait for a person" apart from "this transition is refused",
    and telling them apart by message text would be a decision that drifts.
    """

    public_message = "This step is waiting for an approval"


class StepInterruptedError(WorkflowError):
    """Another execution holds this step's durable claim.

    Raised by admission when a non-replayable step is already claimed -- a
    replacement worker reaching a step the original worker took and did not
    release ([[ADR-006 Workflow Async Execution and Run Reconciliation]] D8).

    **This is terminal, and it must never be reported as success.** A
    `WorkflowError` subclass, so `app.jobs.contract.classify` dead-letters it
    without spending another attempt, and the run is reconciled to `failed` in
    the same statement that dead-letters the job (D5).

    The reasoning for terminating rather than succeeding is worth keeping next
    to the exception: **a replacement worker cannot prove the claim holder is
    alive.** Reporting success on a dead holder would leave a job terminally
    `succeeded`, a run still `running`, the original worker gone, and nothing
    left that could ever advance or reconcile that run -- a stranded run nobody
    would notice, which is the CLAUDE.md §26 failure this design exists to
    remove. Between two unprovable states, the safe assumption is interruption,
    and interruption has an honest terminal outcome available.
    """

    public_message = (
        "This run stopped before it finished. Resume it to continue from the last completed step."
    )


class StepOwnershipLostError(WorkflowError):
    """This execution no longer owns the job it is running, so it wrote nothing.

    Raised when a fenced settlement matches nothing: the step's claim is not
    ours, the job's lease has rotated to another worker, or the run has already
    been terminally reconciled (ADR-006 D8, the three predicates).

    Terminal, and deliberately silent about the outside world: whatever this
    execution already did, none of it will land. The queue's own lease fence
    means this worker's dead-letter attempt is itself refused when another
    worker holds the job, so raising here cannot fail a run someone else is
    legitimately executing.
    """

    public_message = (
        "This run stopped before it finished. Resume it to continue from the last completed step."
    )


class RunNotResumableError(WorkflowError):
    """A run was asked to continue from a state that does not permit it.

    Answered as 409 rather than 404 or 422: the run exists, the caller may see
    it, and what refuses them is its current state -- the same shape as
    `IllegalTransitionError` and `LastOwnerError`.
    """

    def __init__(self, current: RunStatus, action: str) -> None:
        """Record the state and the refused action, and build the client message."""
        self.current = current
        self.action = action
        self.public_message = f"A run in '{current}' cannot be {action}"
        super().__init__(self.public_message)


@dataclass(frozen=True)
class StepContext:
    """Everything a step is given, and the only channel it receives input on.

    Frozen, and passed rather than injected, so a step cannot reach outside what
    it was handed. In particular a step has **no database connection**: it
    computes and returns, and the runner persists. A step holding a connection
    would be a step able to write its own history, which is the second
    persistence path the module docstring rules out.

    `outputs` carries what earlier steps produced, keyed by step name. This is
    [[Agent Architecture]]'s "agents exchange structured context, intermediate
    outputs and execution status **through the workflow engine** instead of
    communicating directly" -- a step reads its predecessor's output from here
    rather than calling it.
    """

    workspace_id: uuid.UUID
    run_id: uuid.UUID

    #: The project this run acts on, when it acts on one.
    project_id: uuid.UUID | None

    #: Who triggered the run. Carried for attribution on the spend ledger, so an
    #: automated call is still traceable to the person who started it.
    triggered_by: uuid.UUID

    #: The run's execution budget, shared by every AI call it makes.
    #:
    #: **One budget per run, passed to every call**, which is what makes
    #: CLAUDE.md §15a's chained-invocation cap real: a per-call budget would
    #: reset on each step, and a ten-step workflow would silently get ten times
    #: the allowance. `ExecutionBudget` documents this as the reason it is
    #: mutable accumulated state.
    #:
    #: A step passes it straight to `AIService.complete` rather than checking it
    #: itself -- the service checks before every call, so a step that forgot
    #: would still be bounded.
    execution_budget: ExecutionBudget = field(default_factory=ExecutionBudget)

    #: Outputs of every completed step in this run, keyed by step name.
    outputs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StepResult:
    """What a step produced.

    `output` is placed into the next step's `StepContext.outputs` under this
    step's name. `tokens_used` is recorded on the step's row so a run's cost is
    answerable from its own history rather than only from the global ledger.
    """

    output: Any = None
    tokens_used: int = 0

    #: A human-readable note about what happened, stored on the step row. Shown
    #: to users, so it must not carry internal detail (CLAUDE.md §24).
    detail: str | None = None


class WorkflowStep(ABC):
    """One unit of work in a workflow.

    An ABC rather than a Protocol, the same choice and the same reasoning as
    `AIProvider`: a step missing `name` would be accepted structurally and fail
    when it is first executed -- in production, mid-run. An ABC fails at import.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the step's stable identifier.

        Stored on every step row and used as the key in `StepContext.outputs`, so
        it is a wire value in all but name: renaming it orphans the outputs later
        steps read by that key.
        """

    @property
    def requires_approval(self) -> bool:
        """Return whether a human must approve before this step executes.

        **Defaults to `True`**, which is the whole point. [[CLAUDE|CLAUDE.md]]
        §15 makes approval the default for anything that writes data, spends
        money, publishes or acts externally, and autonomous execution opt-in. A
        default of `False` would mean a step author who did not consider the
        question ships the unsafe behaviour.

        A step overriding this to `False` is asserting it is read-only,
        internal, or trivially reversible -- and owes that reasoning in its
        docstring, which is the documented exemption §15 requires.
        """
        return True

    @property
    def replayable(self) -> bool:
        """Return whether re-executing this step is free of external effect.

        **Defaults to `False`, and is inherited rather than written** -- the
        identical defaulting decision `requires_approval` above makes, for the
        identical reason: a step author who did not consider the question ships
        the safe behaviour.

        A step declared `replayable = True` is asserting that running it twice
        costs nothing and changes nothing outside this database -- a pure read,
        a computation over values already in memory, or a write that converges.
        It owes that reasoning in its docstring, exactly as a
        `requires_approval = False` exemption does.

        What the answer decides: a non-replayable step is entered only by
        winning a durable claim that exactly one execution can hold, and its
        result is persisted only while that execution still owns its job and its
        run is not already reconciled (ADR-006 D8). A replayable step skips the
        claim, because a claim would buy nothing and would strand a run on a
        step that was safe to repeat.

        **Declaring a step replayable when it is not is the most expensive
        mistake available here**: it removes the only thing standing between a
        lapsed job lease and a provider being paid twice for one step.
        """
        return False

    @abstractmethod
    def execute(self, context: StepContext) -> StepResult:
        """Perform the step's work and return what it produced.

        Writes nothing. The runner persists the result, which is what keeps
        persistence in one place and lets a step be tested without a database.

        Raises:
            Exception: any failure fails the run. A step does not retry -- the
                router owns retries for AI calls, and a step retrying on top of
                that would multiply a ceiling nobody wrote down (CLAUDE.md §15a).
        """


@dataclass(frozen=True)
class WorkflowDefinition:
    """An ordered sequence of steps, under a name and a version.

    **Declared in code, never stored**, which is why there is no `workflows`
    table. A definition's steps are executable Python; a definitions table would
    be a second source of truth able to disagree with the code that actually
    runs, and the disagreement would only surface mid-run.

    What *is* stored is which definition and which version a run executed --
    see the migration's docstring.
    """

    workflow_type: str
    version: int
    steps: tuple[WorkflowStep, ...]

    def __post_init__(self) -> None:
        """Refuse a definition that cannot be executed or recorded coherently.

        Raises:
            ValueError: on an empty step list, a non-positive version, or
                duplicate step names. Duplicates matter most: step names key
                `StepContext.outputs`, so two steps sharing one would have the
                second silently overwrite the first's output, and a later step
                reading that key would get the wrong value with no error.
        """
        if not self.steps:
            raise ValueError("A workflow definition needs at least one step")

        if self.version < 1:
            raise ValueError("A workflow definition version must be at least 1")

        names = [step.name for step in self.steps]

        if len(names) != len(set(names)):
            raise ValueError(f"Duplicate step names in '{self.workflow_type}': {names}")

    def step_at(self, index: int) -> WorkflowStep:
        """Return the step at a position.

        Raises:
            WorkflowError: when the index is outside the definition. Reachable
                when a run is resumed against a definition that has since lost
                steps, which is a real hazard rather than a defensive one -- and
                a loud failure is the correct outcome, because silently treating
                the run as finished would report a truncated run as completed.
        """
        if index < 0 or index >= len(self.steps):
            raise WorkflowError(
                f"Step index {index} is outside definition "
                f"'{self.workflow_type}' v{self.version} ({len(self.steps)} steps)",
                public_message="This workflow definition has changed and the run cannot continue",
            )

        return self.steps[index]


#: What a client is told when a run outlives the definition that started it.
#:
#: Fixed and public-safe. It names neither version, because a version number is
#: deployment detail a user cannot act on and naming it would leak what this
#: deployment runs.
#:
#: **"Remains available for review" rather than "preserved unchanged"**, because
#: the second is not true on every path. A worker refusing mid-delivery
#: dead-letters its job, and D5 then reconciles the run to `failed` -- so the
#: run's *status* does change there, while its steps, outputs and history do
#: not. The wording has to be true of both paths, and what is true of both is
#: that nothing executed and the record is still readable.
DEFINITION_CHANGED_MESSAGE = (
    "This workflow's definition has changed since this run started, so it "
    "cannot continue automatically. The run remains available for review."
)


def ensure_definition_matches(
    definition: WorkflowDefinition,
    workflow_type: str,
    definition_version: int,
) -> None:
    """Refuse to advance a run against a definition it did not start under.

    **A run's `definition_version` is stamped at creation and never silently
    rewritten** (migration `f3c82b19d4a7`). Synchronously that was bookkeeping:
    the definition that started a run was necessarily the one that finished it,
    within a single request. Asynchronously it is not -- a run can sit at an
    approval gate, or interrupted awaiting recovery, across a deploy that adds a
    step, reorders two, or changes whether one is gated or replayable.

    Continuing such a run against current code is not a smaller version of
    correct behaviour, it is a different execution: `next_step_index` counts
    completed rows, so an inserted step shifts every index after it, and a step
    that stopped being `replayable` would be re-entered without a claim -- a
    second provider charge with nothing to prevent it.

    Emulating an old definition with current code would mean keeping every
    historical step sequence executable forever, which is the second source of
    truth `WorkflowDefinition` exists to avoid. What happens to an incompatible
    run is a product decision -- migrate it, abandon it, restart it -- and this
    makes it one somebody takes on purpose.

    ## What is guaranteed on every path, and what is not

    Guaranteed wherever this is called: **no mismatched definition executes or
    derives workflow state.** No provider is called, no step is admitted, and no
    approval or claim is consumed -- this runs before any of them. The run's
    persisted steps, outputs and history stay readable either way.

    **The run's status is a different question, and the paths differ.** Do not
    read this as "the run is left untouched":

    - **Approval and recovery** call this in the route, *before* the protected
      command runs, so nothing is written at all and the run keeps the state it
      had.
    - **A worker** has already been handed a job. Refusing raises, the job
      dead-letters, and ADR-006 D5 then reconciles the linked
      non-terminal run to `failed` in the same statement. That is D5 working as
      specified, and it is deliberately given no exception here: a dead-lettered
      job against a live run is precisely the stranded pair D5 exists to prevent.

    Called before **every** mutation of a run: execution, recovery and approval.
    Approval matters as much as the other two, because an approval that enqueues
    a job the worker will refuse turns an owner's decision into a dead-lettered
    job and a run stuck at a gate whose grant has already been spent.

    Args:
        definition: the definition this deployment would execute.
        workflow_type: the type recorded on the run.
        definition_version: the version recorded on the run.

    Raises:
        WorkflowError: on either mismatch, carrying a fixed public-safe message
            that names no version.
    """
    if definition.workflow_type != workflow_type:
        raise WorkflowError(
            f"Run records workflow type '{workflow_type}' but the definition "
            f"supplied is '{definition.workflow_type}'",
            public_message=DEFINITION_CHANGED_MESSAGE,
        )

    if definition.version != definition_version:
        raise WorkflowError(
            f"Run of '{workflow_type}' recorded definition version "
            f"{definition_version}, and this deployment executes version "
            f"{definition.version}",
            public_message=DEFINITION_CHANGED_MESSAGE,
        )
