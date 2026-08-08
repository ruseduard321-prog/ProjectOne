"""The steps a workflow is built from, including the one real agent.

[[Agent Architecture]] requires that "each agent has a single responsibility,
defined inputs and outputs, measurable success criteria and full execution logs",
and that "new agents can be added, replaced or upgraded without affecting
existing workflows". Both properties come from the same place: an agent is a
`WorkflowStep` and the runner knows nothing else about it.

## The three steps here map to three of the seven phases

    Validation      -> ValidateProjectStep   (no AI, no approval)
    Planning        -> PlanningAgent         (AI, approval required)
    Quality Checks  -> QualityCheckStep      (no AI, no approval)

Trigger and Completion are the runner's own boundaries. Agent Execution beyond
planning, and the wider agent chain [[Agent Architecture]] describes, is later
work -- this step's Scope says the *interface* is the deliverable and one real
agent is enough to prove it.

## Why two of the three are not AI agents

A workflow whose every step is an AI call would prove the engine can call an AI
and nothing else. Validation and quality checks are where a run decides whether
to proceed at all, and they are deterministic on purpose: [[Workflow Engine]]'s
first execution principle is *deterministic*, and a pipeline that cannot make a
decision without a provider is a pipeline that cannot run during an outage.

They are also the steps that demonstrate the approval default correctly: both
are read-only and internal, so both override `requires_approval` to `False` --
with the reasoning stated, which is the documented exemption
[[CLAUDE|CLAUDE.md]] §15 requires.
"""

from __future__ import annotations

from app.ai.provider import CompletionRequest, Message, Role
from app.core.logging import get_logger, log_context
from app.repositories.projects import ProjectRepository
from app.services.ai_service import AIService
from app.workflows.models import StepContext, StepResult, WorkflowError, WorkflowStep

logger = get_logger(__name__)

#: The `workflow_type` every AI call from this workflow is attributed to.
#:
#: Matches the workflow's own name deliberately. `AISpendService` meters
#: per-workflow ceilings on this string, so a mismatch would make "set a limit on
#: project planning" silently govern nothing.
PROJECT_PLANNING_WORKFLOW = "project_planning"

#: How many tokens the planning agent may ask for in one call.
#:
#: Bounded here as well as by the run's `ExecutionBudget`, because the two answer
#: different questions: this bounds one response's size, the budget bounds the
#: whole run. An outline that needs more than this is an outline that has stopped
#: being an outline.
_PLANNING_MAX_TOKENS = 800

#: The shortest outline treated as a real answer.
#:
#: [[Agent Architecture]] requires a **measurable success criterion**. A provider
#: that returns an empty string, a single word, or whitespace has technically
#: answered, and a step that accepted it would attach a useless asset and report
#: success -- the "confident-sounding output" CLAUDE.md §15 forbids.
_MIN_OUTLINE_LENGTH = 40


class ValidateProjectStep(WorkflowStep):
    """Confirm the run has a project it can actually work on.

    The **Validation** phase. Cheap, deterministic, and first, so a run that
    cannot succeed fails before it spends anything -- the same ordering
    `AISpendService` uses for its own checks.
    """

    def __init__(self, projects: ProjectRepository) -> None:
        """Store the repository this step reads the project through."""
        self._projects = projects

    @property
    def name(self) -> str:
        """Return the step's stable identifier."""
        return "validate"

    @property
    def requires_approval(self) -> bool:
        """Read-only and internal, so it runs autonomously.

        **The documented exemption** CLAUDE.md §15 requires: this step reads one
        row and writes nothing, spends nothing, and communicates with no external
        service. There is no consequence for a user to approve.
        """
        return False

    def execute(self, context: StepContext) -> StepResult:
        """Read the project and confirm it is usable.

        Raises:
            WorkflowError: when the run names no project, or names one that is
                not reachable. Both fail the run loudly rather than proceeding
                with nothing to plan.
        """
        if context.project_id is None:
            raise WorkflowError(
                "This workflow requires a project",
                public_message="This workflow needs a project to run against",
            )

        project = self._projects.get(context.workspace_id, context.project_id)

        if project is None:
            # RLS makes "not yours" and "not there" identical here, which is
            # correct -- and the run is inside a workspace the caller already
            # passed a permission check for, so this is a deleted project rather
            # than a cross-tenant probe.
            raise WorkflowError(
                f"Project {context.project_id} is not reachable",
                public_message="The project this run targets no longer exists",
            )

        return StepResult(
            output={"name": project.name, "description": project.description},
            detail=f"Validated project '{project.name}'",
        )


class PlanningAgent(WorkflowStep):
    """Turn a project's name and description into a short outline.

    **The one real agent**, and the first in [[Agent Architecture]]'s chain.

    | Contract | |
    |---|---|
    | **Responsibility** | Produce an outline for one project. Nothing else. |
    | **Input** | The validated project's name and description. |
    | **Output** | Outline text. |
    | **Success criterion** | A non-empty outline of at least `_MIN_OUTLINE_LENGTH` characters. |
    | **Logs** | One structured record per execution, with the provider that answered. |

    ## Why this requires approval

    It does not write data or publish -- but it **spends money**, which
    CLAUDE.md §15 lists alongside them. `requires_approval` is inherited as
    `True` rather than overridden, so this agent is gated by default and the
    inheritance is the decision rather than an oversight.
    """

    def __init__(self, ai: AIService) -> None:
        """Store the service every AI call goes through.

        `AIService`, never `AIRouter`. The router is reachable only through this
        service by design, and a step holding a router would be a path that
        spends money without passing a single §15a control.
        """
        self._ai = ai

    @property
    def name(self) -> str:
        """Return the step's stable identifier."""
        return "plan"

    def execute(self, context: StepContext) -> StepResult:
        """Ask a provider for an outline, inside the run's governance controls.

        The `ExecutionBudget` is **not** passed here, and that is deliberate: the
        runner owns it and passes it in via `AIService.complete`'s parameter when
        it invokes this step's AI call. Threading it through the step interface
        would mean every future agent had to remember to pass it, and the one
        that forgot would be unbounded.

        Raises:
            WorkflowError: when the provider returns nothing usable. Failing
                loudly rather than attaching an empty outline and reporting
                success (CLAUDE.md §15 -- AI never pretends certainty).
        """
        validated = context.outputs.get("validate")

        if not isinstance(validated, dict):  # pragma: no cover - defensive
            raise WorkflowError(
                "Planning ran without a validated project",
                public_message="This run is missing an earlier step's result",
            )

        name = str(validated.get("name", ""))
        description = validated.get("description") or "No description was provided."

        request = CompletionRequest(
            messages=(
                Message(
                    role=Role.SYSTEM,
                    content=(
                        "You plan content projects. Given a project name and "
                        "description, return a short outline of 3 to 6 steps. "
                        "Return only the outline."
                    ),
                ),
                Message(
                    role=Role.USER,
                    content=f"Project: {name}\n\nDescription: {description}",
                ),
            ),
            max_tokens=_PLANNING_MAX_TOKENS,
            workspace_id=context.workspace_id,
        )

        response = self._ai.complete(
            workspace_id=context.workspace_id,
            request=request,
            workflow_type=PROJECT_PLANNING_WORKFLOW,
            execution_budget=context.execution_budget,
            actor_id=context.triggered_by,
        )

        outline = response.content.strip()

        # The measurable success criterion, checked rather than assumed.
        if len(outline) < _MIN_OUTLINE_LENGTH:
            raise WorkflowError(
                f"Planning returned {len(outline)} characters, below the minimum",
                public_message="The planning step did not produce a usable outline",
            )

        logger.info(
            log_context(
                event="workflow_agent_completed",
                agent=self.name,
                workspace_id=context.workspace_id,
                run_id=context.run_id,
                provider=response.provider,
                model=response.model,
                tokens=response.usage.total_tokens,
            )
        )

        return StepResult(
            output=outline,
            tokens_used=response.usage.total_tokens,
            detail=f"Planned by {response.provider}",
        )


class QualityCheckStep(WorkflowStep):
    """Confirm the plan is substantive enough to keep.

    The **Quality Checks** phase, and deliberately not an AI call. An LLM judging
    another LLM's output is a real technique and it is also a second provider
    call, a second cost and a second failure mode -- none of which this step's
    scope justifies. What this asserts is what a quality check exists to assert
    at this stage: that the run produced *something*, and that it looks like an
    outline rather than a refusal.
    """

    @property
    def name(self) -> str:
        """Return the step's stable identifier."""
        return "quality_check"

    @property
    def requires_approval(self) -> bool:
        """Deterministic, read-only, and spends nothing.

        **The documented exemption**: this step inspects a value already in
        memory. There is no external effect to approve.
        """
        return False

    def execute(self, context: StepContext) -> StepResult:
        """Check the outline against the run's own success criterion.

        Raises:
            WorkflowError: when the plan is missing or too short. A failed
                quality check fails the run rather than passing a bad result
                downstream, which is what makes the check a control.
        """
        outline = context.outputs.get("plan")

        if not isinstance(outline, str) or len(outline.strip()) < _MIN_OUTLINE_LENGTH:
            raise WorkflowError(
                "Quality check rejected the plan as too short",
                public_message="The generated plan did not pass its quality check",
            )

        lines = [line for line in outline.splitlines() if line.strip()]

        return StepResult(
            output={"lines": len(lines), "characters": len(outline)},
            detail=f"Plan accepted: {len(lines)} lines",
        )
