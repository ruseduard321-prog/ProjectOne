"""The project lifecycle state machine (STEP-20).

These run without a database. The state machine is pure logic over a repository
interface, which is exactly the property CLAUDE.md §18 asks for -- "business
rules must remain deterministic and testable independent of the AI or
infrastructure layer around them" -- so it is tested exhaustively here and the
database-backed behaviour is tested separately in
`test_project_isolation.py`.

**The exhaustive test is the one that matters.** Asserting a handful of legal
moves proves the map has entries; asserting every one of the 81 ordered pairs
proves it has no *extra* entries, which is the property a state machine exists
for. A permissive bug in a transition table is invisible to a test suite that
only tries the moves it expects to work.
"""

from __future__ import annotations

import uuid

import pytest

from app.repositories.projects import Project, ProjectRepository
from app.services.project_service import (
    INITIAL_STATUS,
    TERMINAL_STATUS,
    IllegalTransitionError,
    ProjectNotFoundError,
    ProjectService,
    ProjectStatus,
    is_legal_transition,
    legal_transitions_from,
)

# The lifecycle order, restated independently of `_SEQUENCE` in the service.
#
# Deliberately a second copy: importing the private tuple the machine is built
# from would make this suite agree with any reordering, including a wrong one.
# [[Projects]] is the source, and this is that document transcribed by hand.
LIFECYCLE = (
    ProjectStatus.IDEA,
    ProjectStatus.PLANNING,
    ProjectStatus.GENERATION,
    ProjectStatus.REVIEW,
    ProjectStatus.EDITING,
    ProjectStatus.APPROVAL,
    ProjectStatus.PUBLISHING,
    ProjectStatus.ANALYTICS,
)

# Every transition the owner's decision permits, written out as data rather than
# derived. This is the specification; the service derives the same set from three
# rules, and `test_every_ordered_pair_matches_the_specification` asserts the two
# agree across all 81 pairs.
EXPECTED_LEGAL: frozenset[tuple[ProjectStatus, ProjectStatus]] = frozenset(
    # Rule 1: forward one step.
    [(LIFECYCLE[i], LIFECYCLE[i + 1]) for i in range(len(LIFECYCLE) - 1)]
    # Rule 3: archive from anywhere in the sequence.
    + [(status, ProjectStatus.ARCHIVE) for status in LIFECYCLE]
    # Rule 2: the Review -> Editing loop.
    + [(ProjectStatus.REVIEW, ProjectStatus.EDITING)]
)


class FakeProjectRepository(ProjectRepository):
    """An in-memory stand-in, holding one project.

    Subclasses the real repository without calling its `__init__`, so a method
    added to `ProjectRepository` and forgotten here is a type error rather than
    a silently-inherited database call against a connection that does not exist.
    """

    def __init__(self, project: Project | None) -> None:
        """Hold the single project every lookup returns."""
        self._project = project
        self.written: list[str] = []

    def get(self, workspace_id: uuid.UUID, project_id: uuid.UUID) -> Project | None:
        """Return the held project."""
        return self._project

    def update_status(
        self, workspace_id: uuid.UUID, project_id: uuid.UUID, status: str
    ) -> Project | None:
        """Record the write and return the project in its new state."""
        self.written.append(status)

        if self._project is None:
            return None

        updated = Project(
            id=self._project.id,
            workspace_id=self._project.workspace_id,
            name=self._project.name,
            description=self._project.description,
            status=status,
            created_by=self._project.created_by,
            created_at=self._project.created_at,
            updated_at=self._project.updated_at,
            version=self._project.version + 1,
        )
        self._project = updated

        return updated


def make_project(status: ProjectStatus) -> Project:
    """Build a project fixed in one lifecycle state."""
    from datetime import UTC, datetime

    now = datetime.now(UTC)

    return Project(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        name="A project",
        description=None,
        status=status,
        created_by=uuid.uuid4(),
        created_at=now,
        updated_at=now,
        version=1,
    )


def make_service(status: ProjectStatus) -> tuple[ProjectService, FakeProjectRepository]:
    """Build a service over a project fixed in one state."""
    repository = FakeProjectRepository(make_project(status))

    return ProjectService(repository), repository


# ------------------------------------------------------- the transition map --


def test_every_ordered_pair_matches_the_specification() -> None:
    """All 81 ordered pairs agree with the owner's decision, in both directions.

    The load-bearing test in this module. It asserts not only that every legal
    move is permitted but that **every other move is refused** -- the half a
    suite of hand-picked positive cases structurally cannot cover.

    A bug that made the machine permissive (an off-by-one making the map include
    two forward steps, a stray backward edge) passes every "the legal move
    works" test ever written and fails here.
    """
    unexpected_legal: list[tuple[ProjectStatus, ProjectStatus]] = []
    unexpected_refused: list[tuple[ProjectStatus, ProjectStatus]] = []

    for current in ProjectStatus:
        for requested in ProjectStatus:
            permitted = is_legal_transition(current, requested)
            expected = (current, requested) in EXPECTED_LEGAL

            if permitted and not expected:
                unexpected_legal.append((current, requested))
            elif expected and not permitted:
                unexpected_refused.append((current, requested))

    assert not unexpected_legal, f"transitions permitted that should not be: {unexpected_legal}"
    assert not unexpected_refused, f"transitions refused that should be legal: {unexpected_refused}"


def test_no_state_transitions_to_itself() -> None:
    """A project cannot 'move' to the state it is already in.

    Not a special case in the machine -- it falls out of the rules -- but worth
    asserting because a self-transition is the shape a double-clicked button
    produces, and permitting it would inflate `version` and `updated_at` on a
    no-op.
    """
    for status in ProjectStatus:
        assert not is_legal_transition(status, status), f"{status} may transition to itself"


def test_the_sequence_advances_one_step_at_a_time() -> None:
    """Each state reaches its immediate successor and no later one (rule 1)."""
    for index, current in enumerate(LIFECYCLE):
        for later in LIFECYCLE[index + 2 :]:
            assert not is_legal_transition(current, later), f"{current} may skip ahead to {later}"

        if index + 1 < len(LIFECYCLE):
            assert is_legal_transition(current, LIFECYCLE[index + 1])


def test_review_may_send_work_back_to_editing() -> None:
    """The one backward edge exists (rule 2)."""
    assert is_legal_transition(ProjectStatus.REVIEW, ProjectStatus.EDITING)


def test_editing_returns_to_approval_not_review() -> None:
    """The loop closes forward, so revised work is re-approved rather than re-reviewed.

    Worth stating explicitly because "Review <-> Editing loop" reads as if the
    edge were symmetric. It is not: `editing -> approval` is rule 1's ordinary
    forward step, which is what [[Projects]] sequences.
    """
    assert is_legal_transition(ProjectStatus.EDITING, ProjectStatus.APPROVAL)
    assert not is_legal_transition(ProjectStatus.EDITING, ProjectStatus.REVIEW)


def test_no_other_backward_edge_exists() -> None:
    """Review -> Editing is the only move against the sequence (rule 2)."""
    for index, current in enumerate(LIFECYCLE):
        for earlier in LIFECYCLE[:index]:
            if (current, earlier) == (ProjectStatus.REVIEW, ProjectStatus.EDITING):
                continue

            assert not is_legal_transition(current, earlier), (
                f"{current} may move backward to {earlier}"
            )


def test_archive_is_reachable_from_every_state() -> None:
    """A project can be abandoned at any point (rule 3)."""
    for status in LIFECYCLE:
        assert is_legal_transition(status, TERMINAL_STATUS), f"{status} cannot be archived"


def test_archive_is_terminal() -> None:
    """Nothing leaves the archive (rule 3).

    Un-archiving is refused deliberately: restoring a project would have to
    answer *to which state*, which makes it a feature rather than a transition.
    """
    assert legal_transitions_from(TERMINAL_STATUS) == frozenset()

    for status in ProjectStatus:
        assert not is_legal_transition(TERMINAL_STATUS, status)


def test_legal_transitions_from_is_usable_by_a_ui() -> None:
    """The helper a screen calls returns exactly the permitted next states.

    STEP-21 consumes this to decide which actions to offer. It is asserted here
    so the UI's source of truth is the same map the service enforces, rather
    than a second copy in TypeScript.
    """
    assert legal_transitions_from(ProjectStatus.IDEA) == frozenset(
        {ProjectStatus.PLANNING, ProjectStatus.ARCHIVE}
    )
    assert legal_transitions_from(ProjectStatus.REVIEW) == frozenset(
        {ProjectStatus.EDITING, ProjectStatus.ARCHIVE}
    )
    assert legal_transitions_from(ProjectStatus.ANALYTICS) == frozenset({ProjectStatus.ARCHIVE})


# ------------------------------------------------------------- the service --


def test_a_legal_transition_succeeds_and_is_written() -> None:
    """The legal half of the step's validation: a permitted move goes through."""
    service, repository = make_service(ProjectStatus.IDEA)

    updated = service.transition(uuid.uuid4(), uuid.uuid4(), ProjectStatus.PLANNING)

    assert updated.status == ProjectStatus.PLANNING
    assert repository.written == [ProjectStatus.PLANNING]


def test_an_illegal_transition_is_refused_and_writes_nothing() -> None:
    """The illegal half, and the part that makes it a control rather than a check.

    Asserting the refusal alone would pass against a service that raised *after*
    writing. The repository recording no write is what proves the state machine
    runs first.
    """
    service, repository = make_service(ProjectStatus.IDEA)

    with pytest.raises(IllegalTransitionError) as raised:
        service.transition(uuid.uuid4(), uuid.uuid4(), ProjectStatus.PUBLISHING)

    assert repository.written == []
    assert raised.value.current == ProjectStatus.IDEA
    assert raised.value.requested == ProjectStatus.PUBLISHING


def test_the_refusal_message_names_both_states() -> None:
    """An illegal transition tells the caller why, unlike a not-found error.

    Safe because the caller already knows the current status -- they read the
    project to attempt the move (CLAUDE.md §24: actionable, without disclosing
    anything they could not already see).
    """
    service, _ = make_service(ProjectStatus.IDEA)

    with pytest.raises(IllegalTransitionError) as raised:
        service.transition(uuid.uuid4(), uuid.uuid4(), ProjectStatus.PUBLISHING)

    assert "idea" in raised.value.public_message
    assert "publishing" in raised.value.public_message


def test_a_project_is_created_in_the_initial_state() -> None:
    """Creation does not accept a status, so nothing starts mid-lifecycle."""
    assert INITIAL_STATUS == ProjectStatus.IDEA


def test_creating_a_project_with_a_blank_name_is_refused() -> None:
    """Checked before the write, so the caller gets a message rather than a constraint."""
    service, _ = make_service(ProjectStatus.IDEA)

    with pytest.raises(ValueError, match="name is required"):
        service.create(uuid.uuid4(), "   ", uuid.uuid4())


def test_archiving_an_archived_project_is_refused() -> None:
    """`archive()` is the terminal rule applied through the named method."""
    service, repository = make_service(TERMINAL_STATUS)

    with pytest.raises(IllegalTransitionError):
        service.archive(uuid.uuid4(), uuid.uuid4())

    assert repository.written == []


def test_a_missing_project_raises_not_found() -> None:
    """Absent and hidden-by-RLS are one error, deliberately.

    Distinguishing them would confirm a project exists in a workspace the caller
    cannot see -- a cross-tenant disclosure through an error message.
    """
    service = ProjectService(FakeProjectRepository(None))

    with pytest.raises(ProjectNotFoundError):
        service.get(uuid.uuid4(), uuid.uuid4())


def test_a_full_lifecycle_run_reaches_analytics() -> None:
    """The whole sequence is walkable end to end.

    The integration of the individual rules: each step legal on its own does not
    guarantee the path exists, and a machine nobody can walk from Idea to
    Analytics would satisfy every pairwise test above.
    """
    service, repository = make_service(ProjectStatus.IDEA)
    workspace_id, project_id = uuid.uuid4(), uuid.uuid4()

    for target in LIFECYCLE[1:]:
        service.transition(workspace_id, project_id, target)

    assert repository.written == list(LIFECYCLE[1:])


def test_a_rejected_review_can_be_revised_and_approved() -> None:
    """The loop works as a path, not only as an edge.

    Review -> Editing -> Approval is the sequence rule 2 exists for, and it is
    the reason the machine is not strictly linear.
    """
    service, repository = make_service(ProjectStatus.REVIEW)
    workspace_id, project_id = uuid.uuid4(), uuid.uuid4()

    service.transition(workspace_id, project_id, ProjectStatus.EDITING)
    service.transition(workspace_id, project_id, ProjectStatus.APPROVAL)

    assert repository.written == [ProjectStatus.EDITING, ProjectStatus.APPROVAL]
