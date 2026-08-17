"""The enqueue side of the job contract.

Small on purpose. Enqueueing is three decisions -- is this job type real, how
many attempts may it have, and what correlation id does it carry -- and all three
belong somewhere a route can reach and a worker cannot accidentally re-decide.

## Why the ceiling comes from the handler rather than the caller

`max_attempts` is read from the registered handler, never taken from a caller.
[[ADR-005 Async Job Queue and Worker Execution Model]] §7 makes the retry ceiling
a property the handler declares, and a caller-supplied one would make it a
property of whoever enqueues -- which is how a ceiling stops being a ceiling. The
database refuses an out-of-range value independently
(`ck_jobs_max_attempts_within_ceiling`), so there are three agreeing gates and no
path around them.

## Why an unknown job type is refused here

The registry is consulted at enqueue so a typo is answered **at the request**,
where a caller exists to be told. Left to the worker it would surface as a
dead-lettered row, correctly but hours later and to nobody in particular.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.core.api import current_request_id
from app.core.logging import get_logger, log_context
from app.jobs.contract import Job, JobError
from app.jobs.registry import JobHandlerRegistry
from app.repositories.jobs import JobRepository

logger = get_logger(__name__)


class UnknownJobTypeError(JobError):
    """A job was enqueued for a type no handler serves.

    Raised before anything is written, so a mistyped type leaves no row behind to
    be found later and wondered about.
    """

    public_message = "This job type is not supported"


class JobService:
    """Enqueues jobs and reads a workspace's queue."""

    def __init__(self, repository: JobRepository, registry: JobHandlerRegistry) -> None:
        """Store the tenant-scoped repository and the handler registry."""
        self._repository = repository
        self._registry = registry

    def enqueue(
        self,
        workspace_id: uuid.UUID,
        enqueued_by: uuid.UUID,
        job_type: str,
        payload: dict[str, Any] | None = None,
    ) -> Job:
        """Queue one job, to be executed later by a worker.

        **Runs on the caller's tenant connection**, so the job is written in the
        same transaction as whatever motivated it. That is the transactional
        enqueue ADR-005 §1 chose a database queue for: the motivating row and its
        job commit together, or neither exists.

        `enqueued_by` must be the verified caller. The INSERT policy enforces it
        against `auth.uid()`, so passing anything else fails rather than
        succeeding quietly -- but callers should pass the request's own user id
        rather than relying on the policy to catch a mistake.

        Args:
            workspace_id: The workspace the job belongs to and is charged to.
            enqueued_by: The verified caller, whose identity the worker replays.
            job_type: A registered handler's type.
            payload: What the handler is given. Stored opaquely.

        Returns:
            The job as stored, in `pending`.

        Raises:
            UnknownJobTypeError: no registered handler serves `job_type`.
        """
        if not self._registry.knows(job_type):
            raise UnknownJobTypeError(
                f"No handler is registered for job type '{job_type}'; "
                f"registered types are {list(self._registry.job_types)}"
            )

        handler = self._registry.get(job_type)

        job = self._repository.enqueue(
            workspace_id=workspace_id,
            enqueued_by=enqueued_by,
            job_type=job_type,
            payload=payload or {},
            max_attempts=handler.max_attempts,
            # Captured rather than passed in: the correlation id belongs to the
            # request being served, and letting a caller supply one would let it
            # claim a different request's identity -- the same reasoning
            # `RequestIdFilter` sets the field unconditionally for.
            correlation_id=current_request_id(),
        )

        logger.info(
            log_context(
                event="job_enqueued",
                job_id=job.id,
                job_type=job.job_type,
                workspace_id=job.workspace_id,
                enqueued_by=job.enqueued_by,
                max_attempts=job.max_attempts,
            )
        )

        return job

    def get(self, workspace_id: uuid.UUID, job_id: uuid.UUID) -> Job | None:
        """Return one of the workspace's jobs, or None when it is not visible."""
        return self._repository.get(workspace_id, job_id)

    def list_for_workspace(self, workspace_id: uuid.UUID, limit: int = 50) -> tuple[Job, ...]:
        """Return a workspace's recent jobs, newest first."""
        return self._repository.list_for_workspace(workspace_id, limit)
