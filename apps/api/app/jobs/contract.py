"""The job contract: what a job is, what a handler promises, and what it is promised.

**Delivery is at-least-once. A handler will eventually run twice for one
enqueue, and every handler must survive that.** This is stated here, at the top
of the contract, rather than left to be inferred -- a handler author who has to
infer the delivery guarantee will infer the convenient one
([[ADR-005 Async Job Queue and Worker Execution Model]] §6).

## Why at-least-once, and not something more comfortable

A claimed job holds a **lease**. A worker executing a long job extends it; a
worker that dies stops extending, and the job becomes claimable again once the
lease lapses. That is what stops a crashed process from holding a job forever,
and it has one unavoidable consequence: the job becomes claimable *while the
original worker may still be running it*. Exactly-once delivery is not achievable
without distributed consensus, and pretending otherwise would mean every handler
was written against a guarantee that does not hold.

## What that obligates a handler to do

**Duplicate delivery must not duplicate effects.** For work whose state lives in
PostgreSQL this is usually close to free -- a handler that reads where it got to
and continues resumes from the same place on a second delivery.

**It is not free for any handler with an external side effect.** `c8f1a3d54e29`
is the binding precedent in this codebase: a duplicate that reaches an AI
provider is charged twice, and deduplicating the stored result afterwards
prevents a duplicate row and never a duplicate bill. A handler performing a
non-idempotent external action must guard it with its own durable claim, in that
same shape. **The job lease is not a substitute for one**, because the lease can
lapse under a worker that is still running.

## What a handler is promised in return

- **A tenant-scoped session, and nothing else.** `JobContext.tenant_session()`
  opens an RLS-subject session as the *enqueuing user*. There is no privileged
  connection on the context, reachable from it, or held open behind it
  (ADR-005 §5 constraint 3).
- **That its identity was established before it was invoked.** A job whose actor
  can no longer be resolved -- a revoked membership, a deleted user -- fails
  terminally and never reaches a handler at all (ADR-005 §5 constraint 4).
- **A bounded number of attempts**, declared by the handler itself. There is no
  default that silently permits work (ADR-005 §7).

## Retries are classified before they are counted

Not every failure deserves a retry, and retrying the wrong one spends money on a
settled "no". `classify` below is that decision, and it mirrors the
`RetryableProviderError` / `TerminalProviderError` split `AIRouter` already
applies one layer down.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.ai.governance import (
    DEFAULT_MAX_CHAINED_INVOCATIONS,
    GovernanceError,
)
from app.ai.router import DEFAULT_MAX_ATTEMPTS_PER_PROVIDER, DEFAULT_MAX_PROVIDERS_TRIED
from app.core.security import AuthorizationError
from app.repositories.session import TenantSessionFactory
from app.workflows.models import WorkflowError

# ---------------------------------------------------------------- ceilings --

#: How many times one enqueue may be attempted, in total.
#:
#: **Set by the project owner at ADR-005's review on 2026-08-17**, reduced from
#: the 3 the ADR originally proposed. Two attempts is what a retry ceiling is
#: *for*: it absorbs a transient failure and refuses to keep paying for a
#: persistent one. A third attempt buys the case where a fault clears on exactly
#: the second retry, which is rare, and costs 30 more upstream provider requests
#: every time it does not.
#:
#: A claim consumes an attempt, so a lease recovery counts against this exactly
#: as an ordinary failure does (ADR-005 §6). The database enforces the same bound
#: in `ck_jobs_max_attempts_within_ceiling`, and
#: `test_the_database_enforces_the_same_attempt_ceiling` asserts the two agree.
MAX_JOB_ATTEMPTS = 2

#: The worst-case number of upstream AI provider requests **one enqueue** can
#: cause, as arithmetic rather than as a claim.
#:
#: | Layer | Ceiling | Source |
#: |---|---|---|
#: | Provider attempts per provider | 3 | `DEFAULT_MAX_ATTEMPTS_PER_PROVIDER` |
#: | Providers in the fallback chain | 2 | `DEFAULT_MAX_PROVIDERS_TRIED` |
#: | -> upstream requests per `complete()` | **6** | STEP-17 |
#: | Chained AI invocations per run execution | 5 | `DEFAULT_MAX_CHAINED_INVOCATIONS` |
#: | -> upstream requests per run execution | **30** | 5 x 6 |
#: | Job attempts per enqueue | **2** | `MAX_JOB_ATTEMPTS`, set by the owner |
#: | -> **upstream requests per enqueue** | **60** | 2 x 5 x 6 |
#:
#: **Computed from the three constants rather than written as 60**, which is the
#: point of it existing at all. [[CLAUDE|CLAUDE.md]] §15a's worst case is reached
#: not by anyone removing a limit but by three reasonable limits multiplying, so
#: raising any one layer must visibly move this number. A hardcoded 60 would go
#: on reading 60 while the real ceiling doubled.
#:
#: It is the true bound, not the expected case: a resumed run does not re-execute
#: completed steps, so the realistic figure is far lower. A ceiling stated
#: optimistically is not a ceiling.
#:
#: Two adjacent bounds hold independently and are **not** multiplied away:
#: `ExecutionBudget`'s 300-second wall clock and 500,000-token limits apply per
#: run execution, and `AISpendService`'s per-workspace spend ceiling applies
#: across everything. The retry ceiling bounds wasted work; the spend ceiling
#: bounds cost. Both are required and neither substitutes for the other.
MAX_UPSTREAM_REQUESTS_PER_ENQUEUE = (
    MAX_JOB_ATTEMPTS
    * DEFAULT_MAX_CHAINED_INVOCATIONS
    * DEFAULT_MAX_ATTEMPTS_PER_PROVIDER
    * DEFAULT_MAX_PROVIDERS_TRIED
)


# ------------------------------------------------------------------ states --


class JobStatus(StrEnum):
    """Where a job is.

    The values match `ck_jobs_status_valid` in migration `a1b7c3e94f6d` exactly,
    and `test_job_status_vocabulary_matches_the_database` asserts that rather
    than trusting the two were edited together -- the defect STEP-21 paid for on
    `assets.kind`.

    `StrEnum` so a value compares equal to the string the database stores, the
    same choice `RunStatus` and `ProjectStatus` make.
    """

    #: Claimable. A job is `pending` when first enqueued **and** after a
    #: retryable failure that left attempts on the clock -- those are the same
    #: state, which is why there is no separate `failed`.
    PENDING = "pending"

    #: Claimed, with a lease. Still claimable once that lease lapses, which is
    #: the at-least-once case handlers are written to survive.
    RUNNING = "running"

    SUCCEEDED = "succeeded"

    #: Terminal failure: a refusal that retrying cannot fix, or attempts
    #: exhausted. Never a silently dropped row -- reaching this state emits a
    #: logged event carrying the cause ([[CLAUDE|CLAUDE.md]] §26).
    DEAD_LETTERED = "dead_lettered"


#: Job states from which nothing further executes.
TERMINAL_JOB_STATUSES: frozenset[JobStatus] = frozenset(
    {JobStatus.SUCCEEDED, JobStatus.DEAD_LETTERED}
)


# ------------------------------------------------------------------ errors --


class JobError(Exception):
    """A job could not be run.

    Carries a `public_message` like every other error in this codebase, because
    the message reaches `jobs.last_error`, which is a tenant-readable column
    ([[CLAUDE|CLAUDE.md]] §24).
    """

    public_message = "This job could not be completed"

    def __init__(self, message: str, public_message: str | None = None) -> None:
        """Record the internal message, and optionally a safe public one."""
        super().__init__(message)

        if public_message is not None:
            self.public_message = public_message


class TerminalJobError(JobError):
    """A refusal a retry cannot fix.

    Raised by a handler that knows its failure is settled -- a malformed payload,
    a resource that no longer exists. Dead-lettered on the spot rather than
    retried, because retrying a certainty spends the ceiling on it.
    """


class HandlerNotRegisteredError(TerminalJobError):
    """No handler is registered for a job's type.

    Terminal by construction: the registry is fixed at process start, so a second
    attempt in the same deployment asks the same question of the same registry.
    A deploy that adds the handler is the fix, and re-enqueueing is then a
    deliberate act rather than an automatic one.
    """

    public_message = "This job type is not supported by this deployment"


class TenantContextUnavailableError(TerminalJobError):
    """The enqueuing user's tenant context could not be established.

    **The revoked-membership case**, accepted by the project owner on 2026-08-17
    (ADR-005 §4, §7). The RLS policies resolve through `workspace_members` at
    execution time, so a job whose actor has since been removed from the
    workspace would read nothing and fail obscurely. It fails *here* instead,
    before the handler is invoked, naming the cause.

    Terminal, and that is the substantive half: retrying would spend the ceiling
    re-asking a permission question of a database that will keep answering no.
    Work authorized by a membership that no longer exists must not silently
    complete, and it must not silently keep trying either.
    """

    public_message = "The account that started this job no longer has access to this workspace"


def classify(error: BaseException) -> bool:
    """Return whether `error` should be retried.

    **Terminal -- no retry, dead-letter immediately:**

    - Every `GovernanceError`. A budget refusal retried is the refusal repeated;
      a tripped ceiling retried is the ceiling not being a ceiling.
    - Every `AuthorizationError`, including the revoked-membership case above.
      A permission check re-asked of the same database gets the same answer.
    - Every `WorkflowError`. The engine's own refusals -- an unknown type, a run
      that cannot be resumed -- are settled facts about state, not transients.
    - Every `TerminalJobError`, which is a handler saying so directly.

    **Retryable -- bounded, then dead-lettered:** everything else. Transient
    infrastructure failures, an unexpected exception, and lease recoveries.

    Returns:
        True when the failure is worth another attempt.
    """
    terminal = (GovernanceError, AuthorizationError, WorkflowError, TerminalJobError)

    return not isinstance(error, terminal)


# ------------------------------------------------------------------- model --


@dataclass(frozen=True)
class Job:
    """One job, as stored.

    Frozen because a repository result is a snapshot of what was read. A mutable
    row invites a caller to edit it and expect the database to notice.
    """

    id: uuid.UUID
    workspace_id: uuid.UUID
    enqueued_by: uuid.UUID
    job_type: str
    payload: dict[str, Any]
    status: str
    attempts: int
    max_attempts: int
    claimed_by: str | None
    claimed_at: datetime | None
    result: Any
    last_error: str | None
    dead_lettered_at: datetime | None
    correlation_id: str | None
    created_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True)
class ClaimedJob:
    """What the dispatcher hands the worker: an identity, never a connection.

    Deliberately **not** a `Job`. The dispatch path is the one cross-tenant
    operation in the platform (ADR-005 §5), and what leaves it is bounded to a
    job id, a workspace id, a user id, a job type and an opaque payload -- so the
    type it returns is bounded to the same, and a future column added to `jobs`
    does not silently widen what crosses the boundary.
    """

    id: uuid.UUID
    workspace_id: uuid.UUID
    enqueued_by: uuid.UUID
    job_type: str
    payload: dict[str, Any]
    attempt: int
    max_attempts: int
    correlation_id: str | None

    #: Proof that *this* claim owns the job. Required to extend the lease or
    #: record an outcome, so a worker whose lease lapsed cannot settle work that
    #: another worker has since taken -- the at-least-once case ADR-005 §6
    #: describes, made survivable rather than merely acknowledged.
    lease_token: uuid.UUID

    #: Which workflow run this job advances, or None for every other job type.
    #:
    #: **A relational fact, not a payload claim.** `jobs.payload` is
    #: client-writable on INSERT -- the write guard is `BEFORE UPDATE` only --
    #: so a run id carried in the payload would be an assertion a member could
    #: forge. This column is created only by a protected command, is immutable
    #: afterwards, and is checked against the run's workspace by a composite
    #: foreign key (ADR-006 D4, I20).
    #:
    #: Reading it does not widen the dispatch boundary: it comes from the
    #: `RETURNING` clause of a statement that already names `public.jobs` and
    #: nothing else (ADR-005 §5 constraint 1, as restated by ADR-006 D6).
    workflow_run_id: uuid.UUID | None = None


@dataclass(frozen=True)
class JobContext:
    """Everything a handler is given, and the only channel it receives input on.

    Frozen, and passed rather than injected, so a handler cannot reach outside
    what it was handed. In particular there is **no privileged connection here,
    and none reachable from anything here** -- `tenant_session` opens sessions
    through `RequestSessionFactory.authenticated_as`, subject to the same
    policies a request is (ADR-005 §5 constraint 3).

    `attempt` is exposed because at-least-once makes it meaningful: a handler
    that wants to behave differently on a retry can, and one that does not can
    ignore it.
    """

    job_id: uuid.UUID
    workspace_id: uuid.UUID

    #: The user whose identity `tenant_session` replays. A handler needs it for
    #: attribution -- a spend record, an audit entry -- not for access control,
    #: which the session already enforces.
    enqueued_by: uuid.UUID

    payload: dict[str, Any]

    #: 1 on the first delivery. Bounded by `max_attempts`.
    attempt: int
    max_attempts: int

    tenant_session: TenantSessionFactory = field(repr=False)

    #: Proof that this delivery still owns the job, for a handler whose work
    #: needs a fence of its own.
    #:
    #: **An opaque identifier that opens nothing.** It grants no access and
    #: names no data; what it does is let a handler ask "do I still hold this
    #: job?" as part of a database predicate, which is what makes a durable
    #: claim checkable at the moment of writing rather than at the moment of
    #: taking (ADR-006 D8). A handler that has no external effect can ignore it.
    #:
    #: It is never logged, never returned in a job result, and never written to
    #: a tenant-readable column: `authenticated` holds no `SELECT` grant on
    #: `jobs.lease_token`, and a fencing token a client can read is a capability
    #: rather than a fence (ADR-006 I15, I17).
    lease_token: uuid.UUID | None = None

    #: The run this job advances, taken from `jobs.workflow_run_id`.
    #:
    #: A handler that drives a run reads this and **never** a run id from the
    #: payload. A forged payload run id is therefore not so much rejected as
    #: unreachable: there is no code path that would consult it (ADR-006 I20).
    workflow_run_id: uuid.UUID | None = None


@dataclass(frozen=True)
class JobResult:
    """What a handler produced.

    `output` is stored on `jobs.result` as JSON, so a job's outcome is
    inspectable without attaching a debugger. It must be JSON-serializable: a
    value that cannot be stored fails the job loudly rather than being silently
    dropped, which is the same choice `WorkflowRepository.settle_step` makes
    about a step's output.
    """

    output: Any = None

    #: A human-readable note stored alongside it. Shown to users, so it must not
    #: carry internal detail ([[CLAUDE|CLAUDE.md]] §24).
    detail: str | None = None


class JobHandler(ABC):
    """One kind of asynchronous work.

    An ABC rather than a `Protocol`, the same choice and the same reasoning as
    `WorkflowStep` and `AIProvider`: a handler missing `max_attempts` would be
    accepted structurally and fail when it is first executed -- in a worker, on a
    real job. An ABC fails at import.

    **Every handler is duplicate-safe.** That obligation is stated in this
    module's docstring and is not a property a type can carry, so it is enforced
    by review -- and by each handler's own docstring saying *why* it is safe.
    """

    @property
    @abstractmethod
    def job_type(self) -> str:
        """Return the stable identifier stored on `jobs.job_type`.

        A wire value in all but name: renaming it orphans every queued job of the
        old type, which will then dead-letter as unregistered.
        """

    @property
    @abstractmethod
    def max_attempts(self) -> int:
        """Return how many attempts this handler's jobs may have.

        **Abstract on purpose: there is no default.** [[CLAUDE|CLAUDE.md]] §15a
        requires every retry ceiling to be explicit, and a default here would
        mean a handler author who never considered the question ships whatever
        that default happened to be. Bounded above by `MAX_JOB_ATTEMPTS`,
        enforced at registration and again by the database.
        """

    @abstractmethod
    def execute(self, context: JobContext) -> JobResult:
        """Do the work, and return what it produced.

        Raises:
            Exception: any failure fails the attempt. `classify` decides whether
                another one follows. A handler does **not** retry internally --
                `AIRouter` owns retries for AI calls and the job owns retries for
                the job, and a third loop in between would multiply a ceiling
                nobody wrote down (§15a).
        """
