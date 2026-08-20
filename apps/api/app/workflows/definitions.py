"""The workflows this deployment can run.

**The registry, and deliberately the only place a workflow's steps are named** --
the same pattern `get_ai_providers` uses for providers. Adding a workflow is one
function here plus its steps; the runner, the routes and every test reach
workflows through this module rather than by constructing a definition.

## Definitions are built per request, not held as constants

A definition holds *steps*, and steps hold the services they need -- a reader
scoped to one tenant, an `AIService` wired to that caller's settings. A
module-level constant would therefore have to hold whichever tenant's services
happened to build it first, which is a cross-tenant leak wearing the shape of a
performance optimization.

Steps depend on **readers**, not on connection-bound repositories, so how long a
connection lives is the caller's decision rather than the step's. The request path
passes repositories over the request connection; the worker passes readers that
open a short session per call, which is what keeps a provider call from running
inside an open transaction (ADR-005 §4).

Construction is cheap: a definition is a tuple of small objects.

## Versioning

Each definition names its own version, and a run records the version it executed
(migration `f3c82b19d4a7`). **Bump the version when the step sequence changes** --
adding, removing or reordering steps -- so a stored run keeps describing what
actually happened rather than what the current code would do.

Editing a step's *internals* without changing the sequence does not require a
bump: the run executed that step, and the row says so.
"""

from __future__ import annotations

from app.repositories.projects import ProjectReader
from app.services.ai_service import AIService
from app.workflows.agents import (
    PROJECT_PLANNING_WORKFLOW,
    PlanningAgent,
    QualityCheckStep,
    ValidateProjectStep,
)
from app.workflows.models import WorkflowDefinition, WorkflowError

#: Current version of the project-planning definition.
#:
#: Version 1: validate -> plan -> quality_check.
PROJECT_PLANNING_VERSION = 1


def project_planning(projects: ProjectReader, ai: AIService) -> WorkflowDefinition:
    """Build the project-planning workflow.

    Three steps covering the Validation, Agent Execution and Quality Checks
    phases of [[Workflow Engine]]'s lifecycle. Trigger and Completion are the
    runner's boundaries rather than steps.

    The middle step is gated and the two around it are not, which is the
    approval model working as intended rather than a coincidence: the AI call
    spends money, the checks either side do not.
    """
    return WorkflowDefinition(
        workflow_type=PROJECT_PLANNING_WORKFLOW,
        version=PROJECT_PLANNING_VERSION,
        steps=(
            ValidateProjectStep(projects),
            PlanningAgent(ai),
            QualityCheckStep(),
        ),
    )


#: Every workflow this deployment can run, by name.
#:
#: A mapping of *builders* rather than of definitions, for the reason the module
#: docstring gives: a definition holds request-scoped services.
_BUILDERS = {
    PROJECT_PLANNING_WORKFLOW: project_planning,
}

#: The names a client may ask to run. Sorted so the API's error message and any
#: listing are in a stable order rather than a dict's insertion order.
AVAILABLE_WORKFLOWS: tuple[str, ...] = tuple(sorted(_BUILDERS))


def build_definition(
    workflow_type: str,
    projects: ProjectReader,
    ai: AIService,
) -> WorkflowDefinition:
    """Return the definition for a workflow name.

    Raises:
        WorkflowError: when no workflow has that name. The public message names
            the valid options -- unlike an authorization refusal, listing the
            workflows this deployment offers reveals nothing about any tenant,
            and withholding it would make every client integration a guess.
    """
    builder = _BUILDERS.get(workflow_type)

    if builder is None:
        raise WorkflowError(
            f"Unknown workflow type '{workflow_type}'",
            public_message=(
                f"Unknown workflow. Available workflows: {', '.join(AVAILABLE_WORKFLOWS)}"
            ),
        )

    return builder(projects, ai)
