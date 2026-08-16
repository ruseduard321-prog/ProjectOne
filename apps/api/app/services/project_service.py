"""Project lifecycle rules: the state machine, and who may drive it.

**This module owns the transition rules**, so they hold for any caller -- an HTTP
route, a future workflow step, a background job. Business logic that lives in a
router is logic a non-HTTP caller silently bypasses (CLAUDE.md §12), and every
caller of `projects` in later phases will be a non-HTTP one: [[Workflow Engine]]
advances a project through Generation and Review without a request in sight.

## The lifecycle, and why it is not a straight line

[[Projects]] gives the sequence:

    Idea -> Planning -> Generation -> Review -> Editing -> Approval
         -> Publishing -> Analytics -> Archive

The specification states the order and stops there, so which transitions are
*legal* was a genuine gap rather than something to infer. The project owner
decided it on 2026-08-08: **forward one step, plus the Review/Editing loop, plus
Archive from anywhere.**

Three rules, and each one is a decision rather than a default:

1. **Forward, one step at a time.** A project moves to the next state in the
   sequence and never skips. Skipping is what makes a state meaningless: if a
   project can jump from Idea to Publishing, "in Approval" stops guaranteeing
   that anything was approved, and every consumer of `status` has to re-derive
   what actually happened.

2. **Review and Editing form a loop.** `review -> editing` is the one backward
   edge, and it is the edge content work actually needs: a reviewer sends a draft
   back for changes, and the revised draft goes to review again. Without it a
   rejected review would have to be archived and the project recreated, losing
   its assets and its history over an ordinary editorial event.

3. **Archive is reachable from every state, and is terminal.** A project can be
   abandoned at any point -- an idea that goes nowhere is the common case, not an
   error -- so archiving is always available. Un-archiving is refused: a state
   machine that can leave its terminal state has no terminal state, and
   "restore this project" is a distinct feature (it would need to answer *to
   which state*) rather than a transition.

Everything else is refused. That refusal is the whole value of the type: a
status column accepting any assignment is a `text` field with extra steps, which
is what the step note warns against.

## What this deliberately does not do

**No authorization.** `AuthorizationService` decides who may act; this decides
what act is coherent. Mixing them would mean a caller has to satisfy both to test
either, and the transition rules are the part worth testing exhaustively.

**No status writes outside `transition`.** `ProjectRepository.update_status`
writes whatever it is given, so the only thing standing between a caller and an
illegal state is this method -- which is why every path that changes a status
goes through it.
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from app.core.logging import get_logger, log_context
from app.repositories.projects import Asset, Project, ProjectRepository

logger = get_logger(__name__)


class ProjectStatus(StrEnum):
    """A project's position in the lifecycle.

    The values match `ck_projects_status_valid` in migration `e5a91c34d7f2`
    exactly. `StrEnum` so a value compares equal to the string the database
    stores, which keeps the boundary between the two layers free of conversions
    that could silently disagree -- the same choice `WorkspaceRole` makes for the
    same reason.

    `test_status_vocabulary_matches_the_database` asserts the two lists against
    each other rather than trusting that they were edited together.
    """

    IDEA = "idea"
    PLANNING = "planning"
    GENERATION = "generation"
    REVIEW = "review"
    EDITING = "editing"
    APPROVAL = "approval"
    PUBLISHING = "publishing"
    ANALYTICS = "analytics"
    ARCHIVE = "archive"


#: The state every project starts in. Named rather than defaulted in the
#: migration alone, so the initial state is a decision visible in the code that
#: reasons about states.
INITIAL_STATUS = ProjectStatus.IDEA

#: The terminal state. Nothing leaves it -- see rule 3 in the module docstring.
TERMINAL_STATUS = ProjectStatus.ARCHIVE

# The lifecycle order, exactly as [[Projects]] states it. `ARCHIVE` is
# deliberately absent: it is not a position in the sequence but an exit from it,
# reachable from every state, so including it here would make it look like the
# step that follows Analytics.
_SEQUENCE: tuple[ProjectStatus, ...] = (
    ProjectStatus.IDEA,
    ProjectStatus.PLANNING,
    ProjectStatus.GENERATION,
    ProjectStatus.REVIEW,
    ProjectStatus.EDITING,
    ProjectStatus.APPROVAL,
    ProjectStatus.PUBLISHING,
    ProjectStatus.ANALYTICS,
)

# The one backward edge (rule 2). A tuple of pairs rather than a special case
# inside `_legal_transitions`, so adding a second loop later is a data change
# rather than a new branch in the logic.
_BACKWARD_EDGES: tuple[tuple[ProjectStatus, ProjectStatus], ...] = (
    (ProjectStatus.REVIEW, ProjectStatus.EDITING),
)


def _build_transitions() -> dict[ProjectStatus, frozenset[ProjectStatus]]:
    """Derive the full transition map from the three rules.

    Derived rather than written out as a nine-entry literal, because a literal is
    a fourth place the rules live and the one most likely to drift from the
    prose above it. Reordering `_SEQUENCE` changes the machine correctly here and
    would silently disagree with a hand-written table.
    """
    transitions: dict[ProjectStatus, frozenset[ProjectStatus]] = {}

    for index, status in enumerate(_SEQUENCE):
        allowed: set[ProjectStatus] = set()

        # Rule 1: forward exactly one step.
        if index + 1 < len(_SEQUENCE):
            allowed.add(_SEQUENCE[index + 1])

        # Rule 3: archive from anywhere in the sequence.
        allowed.add(TERMINAL_STATUS)

        transitions[status] = frozenset(allowed)

    # Rule 2: the backward edges, added on top of the forward machine.
    for source, target in _BACKWARD_EDGES:
        transitions[source] = transitions[source] | {target}

    # Rule 3, second half: archive is terminal. An explicit empty set rather than
    # a missing key, so `legal_transitions_from` never has to special-case it and
    # a reader sees the emptiness stated rather than implied.
    transitions[TERMINAL_STATUS] = frozenset()

    return transitions


_TRANSITIONS: dict[ProjectStatus, frozenset[ProjectStatus]] = _build_transitions()


class ProjectNotFoundError(Exception):
    """No live project matched, either because it does not exist or RLS hid it.

    The two causes are deliberately one error. Distinguishing them would tell a
    caller that a project exists in a workspace they cannot see, which is a
    cross-tenant disclosure through an error message.
    """

    public_message = "Project not found"

    def __init__(self, message: str = "Project not found") -> None:
        """Record the internal message; `public_message` is what a client sees."""
        super().__init__(message)


class IllegalTransitionError(Exception):
    """A status change the lifecycle does not permit.

    Unlike `ProjectNotFoundError`, the public message names both states. That is
    safe and useful: the caller already knows the current status (they read the
    project to attempt this), and telling them *why* the move was refused is the
    difference between an actionable error and a mystery (CLAUDE.md §24).
    """

    def __init__(self, current: ProjectStatus, requested: ProjectStatus) -> None:
        """Record both states and build the message a client will see."""
        self.current = current
        self.requested = requested
        self.public_message = f"A project in '{current}' cannot move to '{requested}'"
        super().__init__(self.public_message)


def legal_transitions_from(status: ProjectStatus) -> frozenset[ProjectStatus]:
    """Return every state reachable in one step from `status`.

    Public because a UI needs it: a screen offering a transition that will be
    refused is a screen that wastes the user's time. STEP-21 consumes this rather
    than reimplementing the rules in TypeScript, which is how the two copies
    would begin to disagree.
    """
    return _TRANSITIONS[status]


def is_legal_transition(current: ProjectStatus, requested: ProjectStatus) -> bool:
    """Return whether `current -> requested` is permitted."""
    return requested in _TRANSITIONS[current]


class ProjectService:
    """Creates projects and drives them through the lifecycle."""

    def __init__(self, repository: ProjectRepository) -> None:
        """Store the repository every operation reads and writes through."""
        self._repository = repository

    def create(
        self,
        workspace_id: uuid.UUID,
        name: str,
        created_by: uuid.UUID,
        description: str | None = None,
    ) -> Project:
        """Create a project in its initial state.

        The status is `INITIAL_STATUS` and is not a parameter: a project created
        directly into Approval never went through review, and permitting that
        would undo rule 1 at the point of creation rather than at a transition.

        Raises:
            ValueError: if the name is blank. Checked before the write so the
                caller gets a usable message rather than a constraint violation
                naming `ck_projects_name_not_blank`.
        """
        cleaned = name.strip()

        if not cleaned:
            raise ValueError("A project name is required")

        project = self._repository.create(
            workspace_id=workspace_id,
            name=cleaned,
            description=description,
            status=INITIAL_STATUS,
            created_by=created_by,
        )

        logger.info(
            log_context(
                event="project_created",
                workspace_id=workspace_id,
                project_id=project.id,
            )
        )

        return project

    def get(self, workspace_id: uuid.UUID, project_id: uuid.UUID) -> Project:
        """Return one live project.

        Raises:
            ProjectNotFoundError: no live project matched.
        """
        project = self._repository.get(workspace_id, project_id)

        if project is None:
            raise ProjectNotFoundError()

        return project

    def list_for_workspace(self, workspace_id: uuid.UUID) -> tuple[Project, ...]:
        """Return every live project in a workspace, newest first."""
        return self._repository.list_for_workspace(workspace_id)

    def transition(
        self,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        requested: ProjectStatus,
    ) -> Project:
        """Move a project to a new lifecycle state, if the move is legal.

        **The only path that changes a project's status.** The repository will
        write any value it is handed, so this check is what makes the state
        machine real rather than advisory.

        The current status is read inside the same request transaction as the
        write, so a concurrent transition cannot slip between the check and the
        update: the `UPDATE` takes a row lock, and a second transaction
        attempting the same move blocks until this one commits and then reads the
        new status. The pattern matches the reserve-then-settle reasoning
        [[AI Cost Governance]] established for spend.

        Raises:
            ProjectNotFoundError: no live project matched.
            IllegalTransitionError: the lifecycle does not permit the move.
        """
        project = self.get(workspace_id, project_id)
        current = ProjectStatus(project.status)

        if not is_legal_transition(current, requested):
            # Logged at info, not warning: an illegal transition is a client
            # asking for something coherent-but-wrong, not a system fault. It
            # becomes interesting only in aggregate, which is what a countable
            # event is for (CLAUDE.md §26).
            logger.info(
                log_context(
                    event="project_transition_refused",
                    workspace_id=workspace_id,
                    project_id=project_id,
                    current=str(current),
                    requested=str(requested),
                )
            )
            raise IllegalTransitionError(current, requested)

        updated = self._repository.update_status(workspace_id, project_id, requested)

        # The row was read a moment ago in the same transaction, so this is
        # defensive rather than reachable -- but returning `Project | None` here
        # would push the impossible case onto every caller.
        if updated is None:  # pragma: no cover - defensive
            raise ProjectNotFoundError()

        logger.info(
            log_context(
                event="project_transitioned",
                workspace_id=workspace_id,
                project_id=project_id,
                previous=str(current),
                current=str(requested),
            )
        )

        return updated

    def rename(
        self,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        name: str,
        description: str | None = None,
    ) -> Project:
        """Change a project's name and description.

        Raises:
            ValueError: if the name is blank.
            ProjectNotFoundError: no live project matched.
        """
        cleaned = name.strip()

        if not cleaned:
            raise ValueError("A project name is required")

        updated = self._repository.rename(workspace_id, project_id, cleaned, description)

        if updated is None:
            raise ProjectNotFoundError()

        return updated

    def archive(self, workspace_id: uuid.UUID, project_id: uuid.UUID) -> Project:
        """Move a project to `archive`.

        A named method rather than leaving callers to spell out the transition,
        because archiving is the one move available from every state and is what
        a UI offers as "archive this project" rather than as a lifecycle step.

        Raises:
            ProjectNotFoundError: no live project matched.
            IllegalTransitionError: the project is already archived.
        """
        return self.transition(workspace_id, project_id, TERMINAL_STATUS)

    def delete(self, workspace_id: uuid.UUID, project_id: uuid.UUID) -> None:
        """Soft-delete a project.

        Distinct from archiving, and the distinction matters: **archive is a
        lifecycle state** meaning the work is finished or abandoned but the
        project is still part of the workspace, while **deletion removes it**.
        A user archives a campaign they want to keep a record of and deletes one
        created by mistake.

        Deletion is permitted from any state, archived included. There is no
        rule requiring a project to be archived before it can be removed --
        that would be ceremony, not a safeguard, since the deletion is soft
        either way.

        Raises:
            ProjectNotFoundError: no live project matched.
        """
        if not self._repository.soft_delete(workspace_id, project_id):
            raise ProjectNotFoundError()

        logger.info(
            log_context(
                event="project_deleted",
                workspace_id=workspace_id,
                project_id=project_id,
            )
        )

    # ------------------------------------------------------------- assets --

    def add_asset(
        self,
        workspace_id: uuid.UUID,
        project_id: uuid.UUID,
        name: str,
        kind: str,
        created_by: uuid.UUID,
        storage_path: str | None = None,
    ) -> Asset:
        """Attach an asset to a project.

        The project is fetched first so a missing one raises
        `ProjectNotFoundError` rather than surfacing as a foreign key violation
        naming `fk_assets_project_id_projects` -- the constraint is the
        guarantee, this is the diagnosis.

        Assets may be attached in any lifecycle state. Restricting uploads to
        Generation would be a rule [[Projects]] does not state, and the obvious
        counter-example is a reference image attached while the project is still
        an Idea.

        Raises:
            ValueError: if the name is blank.
            ProjectNotFoundError: no live project matched.
        """
        cleaned = name.strip()

        if not cleaned:
            raise ValueError("An asset name is required")

        self.get(workspace_id, project_id)

        return self._repository.add_asset(
            workspace_id=workspace_id,
            project_id=project_id,
            name=cleaned,
            kind=kind,
            storage_path=storage_path,
            created_by=created_by,
        )

    def list_assets(self, workspace_id: uuid.UUID, project_id: uuid.UUID) -> tuple[Asset, ...]:
        """Return every live asset attached to a project.

        Raises:
            ProjectNotFoundError: no live project matched.
        """
        self.get(workspace_id, project_id)

        return self._repository.list_assets(workspace_id, project_id)

    def get_asset(self, workspace_id: uuid.UUID, asset_id: uuid.UUID) -> Asset:
        """Return one live asset by id.

        Keyed on the workspace rather than on the project, deliberately: a
        caller holding an asset id and a workspace id has already passed the
        membership gate for that workspace, and requiring the project id too
        would make the lookup depend on the caller knowing a second identifier
        that adds no authority.

        Raises:
            ProjectNotFoundError: no live asset matched, or RLS hid it. Reusing
                the project error rather than adding one identical in every
                respect -- both mean "the thing you named is not reachable", and
                both answer 404.
        """
        asset = self._repository.get_asset(workspace_id, asset_id)

        if asset is None:
            raise ProjectNotFoundError("Asset not found")

        return asset

    def attach_storage_path(
        self,
        workspace_id: uuid.UUID,
        asset_id: uuid.UUID,
        storage_path: str,
    ) -> Asset:
        """Record where an asset's bytes were stored.

        Called only after the bytes are actually in the backend
        ([[STEP-28 Asset Upload and Download]] Task 5). Writing this before the
        upload would leave the row pointing at an object that may never exist,
        which is the one inconsistency the ordering there exists to prevent.

        **No validation of `storage_path` here.** It is a locator the storage
        layer produced and returned, never a caller-supplied string, so
        inspecting it would be re-checking the storage layer's own output --
        and the shape of a locator is deliberately not this layer's business.

        Raises:
            ProjectNotFoundError: no live asset matched.
        """
        updated = self._repository.set_asset_storage_path(workspace_id, asset_id, storage_path)

        if updated is None:
            raise ProjectNotFoundError("Asset not found")

        return updated

    def delete_asset(self, workspace_id: uuid.UUID, asset_id: uuid.UUID) -> None:
        """Soft-delete one asset.

        Raises:
            ProjectNotFoundError: no live asset matched. Reusing the project
                error rather than adding an `AssetNotFoundError` that would be
                identical in every respect -- both mean "the thing you named is
                not reachable", and the HTTP layer maps them to the same 404.
        """
        if not self._repository.soft_delete_asset(workspace_id, asset_id):
            raise ProjectNotFoundError("Asset not found")
