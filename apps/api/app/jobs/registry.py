"""Which handler runs which job type, and the ceiling check that happens at registration.

A registry rather than a lookup by import path or by class name. Two reasons,
and the second is the load-bearing one:

- **A job type is a wire value.** It is stored on every queued row and must stay
  stable across a rename of whatever class implements it.
- **Registration is where a handler's retry ceiling is checked.** An invalid
  ceiling is refused when the registry is built -- at import, in every process --
  rather than when a job of that type is first claimed, in a worker, at 3am.
  [[ADR-005 Async Job Queue and Worker Execution Model]] §7 requires that an
  omitted ceiling be "a configuration error at registration, not a job that
  quietly retries forever", and this is that check.

## Both processes build the same registry

The API needs it to refuse an enqueue of an unknown type *at the request*, which
is the only moment a caller can be told. The worker needs it to execute. They
build the same one from the same module, so a type the API accepts is a type some
worker of the same deployment can run -- ADR-005 §3's one-image-two-processes
model is what makes that true rather than hopeful.
"""

from __future__ import annotations

from app.jobs.contract import MAX_JOB_ATTEMPTS, HandlerNotRegisteredError, JobHandler
from app.jobs.handlers import TenantProbeHandler, WorkflowExecutionHandler
from app.workflows.runner import WorkflowDefinitionsFactory


class JobRegistrationError(Exception):
    """A handler cannot be registered.

    Not a `JobError`: nothing has been enqueued and no job exists. This is a
    programming error surfaced at import, which is the only place it can be
    fixed.
    """


class JobHandlerRegistry:
    """Maps a job type to the handler that runs it."""

    def __init__(self, handlers: tuple[JobHandler, ...]) -> None:
        """Index the handlers, refusing any that cannot be safely queued.

        Raises:
            JobRegistrationError: on a duplicate job type, a blank one, or a
                retry ceiling outside `1..MAX_JOB_ATTEMPTS`.

                **The upper bound is the composed ceiling, not a style rule.** A
                handler declaring 10 attempts would multiply the platform's
                worst-case AI spend per enqueue by five, and the arithmetic on
                `MAX_UPSTREAM_REQUESTS_PER_ENQUEUE` would go on describing a
                number that was no longer true. The database refuses the same
                thing independently (`ck_jobs_max_attempts_within_ceiling`), so
                this is the readable failure and that one is the guarantee.
        """
        indexed: dict[str, JobHandler] = {}

        for handler in handlers:
            job_type = handler.job_type

            if not job_type or not job_type.strip():
                raise JobRegistrationError(
                    f"{type(handler).__name__} declares a blank job_type; it is the value "
                    "stored on every queued row and cannot be empty"
                )

            if job_type in indexed:
                raise JobRegistrationError(
                    f"Two handlers claim job type '{job_type}': "
                    f"{type(indexed[job_type]).__name__} and {type(handler).__name__}. "
                    "A queued row names one type, so it must name one handler."
                )

            if not 1 <= handler.max_attempts <= MAX_JOB_ATTEMPTS:
                raise JobRegistrationError(
                    f"{type(handler).__name__} declares max_attempts="
                    f"{handler.max_attempts}, outside 1..{MAX_JOB_ATTEMPTS}. "
                    "The upper bound is the composed retry ceiling accepted in ADR-005 §7 "
                    "— raising it means recomputing MAX_UPSTREAM_REQUESTS_PER_ENQUEUE, "
                    "which is an owner decision rather than a handler's."
                )

            indexed[job_type] = handler

        self._handlers = indexed

    def get(self, job_type: str) -> JobHandler:
        """Return the handler for a job type.

        Raises:
            HandlerNotRegisteredError: when nothing handles it. Terminal, so a
                job of an unknown type is dead-lettered on its first attempt
                rather than retried against a registry that will not change
                within this deployment.
        """
        try:
            return self._handlers[job_type]
        except KeyError:
            raise HandlerNotRegisteredError(
                f"No handler is registered for job type '{job_type}'; "
                f"registered types are {sorted(self._handlers)}"
            ) from None

    def knows(self, job_type: str) -> bool:
        """Return whether a handler exists for a job type.

        Used by the enqueue path to refuse an unknown type **at the request**,
        which is the only moment a caller is present to be told. Without it the
        first news of a typo would be a dead-lettered row nobody is watching.
        """
        return job_type in self._handlers

    @property
    def job_types(self) -> tuple[str, ...]:
        """Return every registered job type, sorted."""
        return tuple(sorted(self._handlers))


#: Every handler this deployment can run that needs nothing constructed for it.
#:
#: The registry is the checklist, in the same spirit as `REGISTERED_STORES`: a
#: handler absent from it is a job type that dead-letters, visibly, rather than
#: one that fails in some subtler way.
#:
#: `WorkflowExecutionHandler` is deliberately **not** here. It needs a factory
#: that builds a workflow definition against a live tenant connection, and a
#: module-level instance would either have to import that factory -- closing an
#: import cycle through `app/core/dependencies.py` -- or reach `Settings` for
#: itself, which is the one thing a handler must not be able to do (ADR-005 §5
#: constraint 3). It is constructed by `build_registry` from what its caller
#: supplies instead.
STATELESS_HANDLERS: tuple[JobHandler, ...] = (TenantProbeHandler(),)


def build_registry(definitions: WorkflowDefinitionsFactory) -> JobHandlerRegistry:
    """Return the registry both processes use.

    A function rather than a module-level instance so a test can build a registry
    of its own without patching module state -- the same reason every other
    collaborator in this codebase is constructed rather than imported
    ([[CLAUDE|CLAUDE.md]] §12).

    Args:
        definitions: how a workflow handler builds a run's definition. Required
            rather than defaulted: a default would have to name a real factory,
            and the only honest alternative -- one that raises when used --
            would turn a wiring mistake into a dead-lettered job in production
            instead of an error at construction.
    """
    return JobHandlerRegistry((*STATELESS_HANDLERS, WorkflowExecutionHandler(definitions)))
