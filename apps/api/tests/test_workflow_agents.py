"""The agents themselves, and the governance path their AI calls take (STEP-22).

Offline, against fakes. The question here is whether an agent honours its own
contract -- [[Agent Architecture]]'s "defined inputs and outputs, measurable
success criteria" -- and whether its AI call goes through the one path that
enforces CLAUDE.md §15a. Neither needs a database.

**The most important test in this file is
`test_the_planning_agent_passes_the_runs_budget_to_every_call`.** A step that
called `AIService` without threading the run's `ExecutionBudget` would be
individually correct and collectively unbounded: each call would get a fresh
allowance, and the chained-invocation cap would govern nothing.
"""

from __future__ import annotations

import uuid

import pytest

from app.ai.governance import ExecutionBudget
from app.ai.provider import CompletionRequest, CompletionResponse, TokenUsage
from app.repositories.projects import Project
from app.workflows.agents import (
    PROJECT_PLANNING_WORKFLOW,
    PlanningAgent,
    QualityCheckStep,
    ValidateProjectStep,
)
from app.workflows.models import StepContext, WorkflowError

#: An outline long enough to pass the agent's success criterion.
_GOOD_OUTLINE = (
    "1. Research the topic thoroughly\n"
    "2. Draft the script\n"
    "3. Record the voiceover\n"
    "4. Edit and publish"
)


class FakeProjectRepository:
    """Returns one configured project, or none."""

    def __init__(self, project: Project | None) -> None:
        """Store what `get` will return."""
        self._project = project
        self.calls: list[tuple[uuid.UUID, uuid.UUID]] = []

    def get(self, workspace_id: uuid.UUID, project_id: uuid.UUID) -> Project | None:
        """Record the lookup and return the configured project."""
        self.calls.append((workspace_id, project_id))
        return self._project


class FakeAIService:
    """Records every completion request and returns a configured response."""

    def __init__(self, content: str = _GOOD_OUTLINE, tokens: int = 250) -> None:
        """Configure what every call returns."""
        self._content = content
        self._tokens = tokens

        #: Every call's keyword arguments, so a test can assert what was passed
        #: -- particularly the execution budget and the workflow type.
        self.calls: list[dict[str, object]] = []

    def complete(
        self,
        workspace_id: uuid.UUID,
        request: CompletionRequest,
        preferred: str | None = None,
        workflow_type: str = "chat",
        execution_budget: ExecutionBudget | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> CompletionResponse:
        """Record the call and return the configured completion."""
        self.calls.append(
            {
                "workspace_id": workspace_id,
                "request": request,
                "workflow_type": workflow_type,
                "execution_budget": execution_budget,
                "actor_id": actor_id,
            }
        )

        return CompletionResponse(
            content=self._content,
            provider="openai",
            model="gpt-test",
            usage=TokenUsage(prompt_tokens=100, completion_tokens=self._tokens - 100),
        )


def _project(name: str = "Spring campaign", description: str | None = "A launch") -> Project:
    """Build a stored project."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)

    return Project(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        name=name,
        description=description,
        status="idea",
        created_by=uuid.uuid4(),
        created_at=now,
        updated_at=now,
        version=1,
    )


def _context(
    project_id: uuid.UUID | None = None,
    outputs: dict[str, object] | None = None,
    budget: ExecutionBudget | None = None,
) -> StepContext:
    """Build a step context."""
    return StepContext(
        workspace_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        project_id=project_id if project_id is not None else uuid.uuid4(),
        triggered_by=uuid.uuid4(),
        execution_budget=budget if budget is not None else ExecutionBudget(),
        outputs=outputs or {},
    )


# ------------------------------------------------------------- validation --


def test_validation_returns_the_projects_details() -> None:
    """The Validation phase reads the project and hands it forward."""
    project = _project()
    step = ValidateProjectStep(FakeProjectRepository(project))  # type: ignore[arg-type]

    result = step.execute(_context(project.id))

    assert result.output == {"name": "Spring campaign", "description": "A launch"}


def test_validation_fails_a_run_with_no_project() -> None:
    """A workflow needing a project must not proceed without one."""
    step = ValidateProjectStep(FakeProjectRepository(_project()))  # type: ignore[arg-type]

    context = StepContext(
        workspace_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        project_id=None,
        triggered_by=uuid.uuid4(),
    )

    with pytest.raises(WorkflowError, match="requires a project"):
        step.execute(context)


def test_validation_fails_when_the_project_is_unreachable() -> None:
    """A deleted or hidden project fails the run rather than planning nothing."""
    step = ValidateProjectStep(FakeProjectRepository(None))  # type: ignore[arg-type]

    with pytest.raises(WorkflowError, match="not reachable"):
        step.execute(_context())


def test_validation_runs_without_approval() -> None:
    """**The documented exemption.** It reads one row and writes nothing.

    Asserted rather than assumed, because the base class defaults to requiring
    approval and this override is the deliberate exception.
    """
    step = ValidateProjectStep(FakeProjectRepository(_project()))  # type: ignore[arg-type]

    assert step.requires_approval is False


# ---------------------------------------------------------------- planning --


def test_the_planning_agent_returns_an_outline() -> None:
    """The agent's defined output: outline text."""
    ai = FakeAIService()
    agent = PlanningAgent(ai)  # type: ignore[arg-type]

    result = agent.execute(
        _context(outputs={"validate": {"name": "A project", "description": "Desc"}})
    )

    assert result.output == _GOOD_OUTLINE
    assert result.tokens_used == 250


def test_the_planning_agent_requires_approval() -> None:
    """**It spends money, so it is gated by default.**

    `requires_approval` is *inherited* rather than overridden, which is the
    decision: CLAUDE.md §15 lists spending money alongside publishing and
    writing data, and an agent that quietly opted out would be the silent
    default the rule forbids.
    """
    assert PlanningAgent(FakeAIService()).requires_approval is True  # type: ignore[arg-type]


def test_the_planning_agent_passes_the_runs_budget_to_every_call() -> None:
    """**The chained-invocation cap depends on this.**

    An agent calling `AIService` without the run's budget would get a fresh
    allowance per call, and §15a's cap would govern nothing. Asserted by
    identity, not equality: a *copy* of the budget would tally separately and
    look correct here while being just as unbounded.
    """
    ai = FakeAIService()
    budget = ExecutionBudget()
    agent = PlanningAgent(ai)  # type: ignore[arg-type]

    agent.execute(_context(outputs={"validate": {"name": "P", "description": "D"}}, budget=budget))

    assert ai.calls[0]["execution_budget"] is budget


def test_the_planning_agent_attributes_its_spend_to_its_own_workflow() -> None:
    """Per-workflow ceilings meter on this string.

    A mismatch would make "set a limit on project planning" silently govern
    nothing, and the spend would land in the default `chat` bucket instead.
    """
    ai = FakeAIService()
    agent = PlanningAgent(ai)  # type: ignore[arg-type]

    agent.execute(_context(outputs={"validate": {"name": "P", "description": "D"}}))

    assert ai.calls[0]["workflow_type"] == PROJECT_PLANNING_WORKFLOW


def test_the_planning_agent_attributes_the_call_to_the_triggering_user() -> None:
    """An automated call stays traceable to the person who started the run."""
    ai = FakeAIService()
    agent = PlanningAgent(ai)  # type: ignore[arg-type]
    context = _context(outputs={"validate": {"name": "P", "description": "D"}})

    agent.execute(context)

    assert ai.calls[0]["actor_id"] == context.triggered_by


def test_the_planning_agent_rejects_an_empty_outline() -> None:
    """**The measurable success criterion**, checked rather than trusted.

    A provider returning nothing has technically answered. Accepting it would
    attach a useless result and report success -- the confident-sounding output
    CLAUDE.md §15 forbids.
    """
    agent = PlanningAgent(FakeAIService(content="   "))  # type: ignore[arg-type]

    # Both messages asserted: the internal one names the measured length, which
    # is what an engineer needs, and `public_message` is what the run row and the
    # user actually see. `pytest.raises(match=...)` only ever sees the first.
    with pytest.raises(WorkflowError, match="below the minimum") as raised:
        agent.execute(_context(outputs={"validate": {"name": "P", "description": "D"}}))

    assert raised.value.public_message == "The planning step did not produce a usable outline"


def test_the_planning_agent_rejects_a_too_short_outline() -> None:
    """A one-word answer is not an outline."""
    agent = PlanningAgent(FakeAIService(content="Nope."))  # type: ignore[arg-type]

    with pytest.raises(WorkflowError, match="below the minimum") as raised:
        agent.execute(_context(outputs={"validate": {"name": "P", "description": "D"}}))

    assert raised.value.public_message == "The planning step did not produce a usable outline"


def test_the_planning_agent_handles_a_project_with_no_description() -> None:
    """A description is optional on a project, so the prompt must tolerate None."""
    ai = FakeAIService()
    agent = PlanningAgent(ai)  # type: ignore[arg-type]

    agent.execute(_context(outputs={"validate": {"name": "P", "description": None}}))

    request = ai.calls[0]["request"]

    assert isinstance(request, CompletionRequest)
    # The prompt says so explicitly rather than sending "None", which would be a
    # literal the model reads as content.
    assert "No description was provided" in request.messages[1].content


def test_the_planning_agent_carries_the_workspace_on_its_request() -> None:
    """BYOK key lookup and spend attribution read this field."""
    ai = FakeAIService()
    agent = PlanningAgent(ai)  # type: ignore[arg-type]
    context = _context(outputs={"validate": {"name": "P", "description": "D"}})

    agent.execute(context)

    request = ai.calls[0]["request"]

    assert isinstance(request, CompletionRequest)
    assert request.workspace_id == context.workspace_id


# ---------------------------------------------------------- quality checks --


def test_the_quality_check_accepts_a_real_plan() -> None:
    """The Quality Checks phase passes work that meets the criterion."""
    result = QualityCheckStep().execute(_context(outputs={"plan": _GOOD_OUTLINE}))

    assert result.output == {"lines": 4, "characters": len(_GOOD_OUTLINE)}


def test_the_quality_check_rejects_a_short_plan() -> None:
    """A failed check fails the run rather than passing bad work downstream."""
    with pytest.raises(WorkflowError, match="(?i)quality check"):
        QualityCheckStep().execute(_context(outputs={"plan": "too short"}))


def test_the_quality_check_rejects_a_missing_plan() -> None:
    """A missing predecessor output is a failure, not an empty pass."""
    with pytest.raises(WorkflowError, match="(?i)quality check"):
        QualityCheckStep().execute(_context(outputs={}))


def test_the_quality_check_runs_without_approval() -> None:
    """**The documented exemption.** It inspects a value already in memory."""
    assert QualityCheckStep().requires_approval is False


def test_the_quality_check_makes_no_ai_call() -> None:
    """Deterministic by design.

    A pipeline that cannot make a quality decision without a provider is a
    pipeline that cannot run during an outage -- and [[Workflow Engine]]'s first
    execution principle is *deterministic*. The step takes no service in its
    constructor, which is the structural version of this assertion.
    """
    # Asserted against the class's own attributes rather than a constructor
    # signature: `WorkflowStep` defines no `__init__`, so this class inherits
    # `object`'s and inspecting it says nothing. What is meaningful is that an
    # instance holds no collaborator at all.
    step = QualityCheckStep()

    assert vars(step) == {}
