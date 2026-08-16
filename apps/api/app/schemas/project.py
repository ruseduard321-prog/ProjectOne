"""Request and response contracts for the project endpoints.

[[STEP-21 Projects UI]] puts the first HTTP surface on the lifecycle
[[STEP-20 Projects Schema and Lifecycle]] built. Three properties are enforced
here rather than in a route body, because a schema is the one place a rule
cannot be forgotten by the next endpoint added:

1. **A response carries its own legal next states.** `ProjectResponse.
   legal_transitions` is derived server-side from `legal_transitions_from`, so a
   UI offers exactly the moves the server will accept. Without it the frontend
   would need its own copy of the state machine -- and two copies of a state
   machine diverge, which is the specific outcome the step note forbids.
2. **`status` is never accepted on create or rename.** A project starts in
   `INITIAL_STATUS` and moves only through the transition route, so there is no
   field here through which a caller could set one. That is rule 1 of the
   lifecycle enforced at the edge rather than only in the service.
3. **Every request model forbids extra fields.** `extra="forbid"` throughout, as
   STEP-19 established: a body carrying an unexpected field is a 422 naming it
   rather than a silent discard, and "silently discarded" is indistinguishable
   from "accepted" to whoever sent it.

`workspace_id` appears in no request model. It is always the verified path
parameter that `requires(...)` authorized against -- a body-supplied tenant id
would be a caller choosing their own permission check.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.services.project_service import ProjectStatus

#: A project's name.
#:
#: Stripped before the bound is applied, so a whitespace-only submission is
#: rejected at the edge rather than reaching `ProjectService.create`'s own
#: `ValueError` -- the same reasoning, and the same construction, as
#: `WorkspaceName`. Both checks stay: this one produces a 422 naming the field,
#: the service's protects every non-HTTP caller.
ProjectName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]

#: Free text describing what a project is for.
#:
#: Optional and generously bounded -- it is a note to the workspace, not a
#: structured field. Not stripped to empty-means-absent: a user who clears the
#: description means to clear it, and `None` and `""` are collapsed by the route
#: rather than by silently rejecting one of them.
ProjectDescription = Annotated[str, StringConstraints(max_length=2000)]


class AssetKind(StrEnum):
    """What an asset *is*, matching `ck_assets_kind_valid` exactly.

    **A closed vocabulary, not free text**, and the constraint in migration
    `e5a91c34d7f2` is why. An accepted-but-invalid value reaches the database and
    fails as a `CheckViolation` -- a 500 for what is a client's malformed request,
    which is the wrong answer twice over: it reports a caller error as a server
    fault, and it puts a constraint name in a log line instead of a usable
    message.

    That is not hypothetical. This was written as free text first and found by
    driving the routes against a real database: the API accepted `kind: "script"`
    and PostgreSQL rejected it. Typing it here turns the same request into a 422
    naming the four values.

    Deliberately coarse. Generation, Publishing and Analytics are later phases,
    so this covers what a project can hold today; the step producing a new kind
    extends both the constraint and this enum in one change -- which is exactly
    why the column is `text` with a CHECK rather than a PostgreSQL `ENUM`
    ([[Table Conventions]]).
    """

    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


#: An asset's display name.
AssetName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class ProjectResponse(BaseModel):
    """One project, as a client may see it.

    Timestamps and ids are serialized as strings rather than as native types,
    matching every other response model in this codebase: a client renders them,
    and a string that survived the round trip is one the client can display
    without a parser disagreeing about a timezone.
    """

    id: str
    workspace_id: str
    name: str
    description: str | None
    status: ProjectStatus

    #: Every state this project can move to in one step.
    #:
    #: **The reason this field exists is that the UI must not reimplement the
    #: lifecycle.** Derived from `legal_transitions_from` at render time, so a
    #: change to the rules reaches every client without a frontend deploy, and a
    #: screen physically cannot offer a transition the server would refuse.
    #:
    #: Empty for an archived project, which is the terminal state saying so
    #: rather than the field being absent -- a client rendering "no moves
    #: available" needs the empty list, not a missing key.
    legal_transitions: list[ProjectStatus]

    created_by: str
    created_at: str
    updated_at: str

    #: The optimistic-concurrency counter from `Table Conventions`. Surfaced
    #: because a client that shows a stale project can at least detect it;
    #: nothing consumes it for conflict detection yet.
    version: int


class ProjectCreateRequest(BaseModel):
    """A new project.

    Carries no `status`: a project created directly into Approval never went
    through review, and accepting one here would undo lifecycle rule 1 at the
    point of creation rather than at a transition (`ProjectService.create`).

    Carries no `created_by` either -- that is the verified caller, and an id
    field here would be an attribution parameter.
    """

    model_config = ConfigDict(extra="forbid")

    name: ProjectName
    description: ProjectDescription | None = None


class ProjectRenameRequest(BaseModel):
    """A change to a project's name and description.

    Both fields, because the service writes both in one statement and a partial
    request would silently blank the description it did not carry. `description`
    being explicitly `null` is how a caller clears it -- distinct from omitting
    it, which this model does not offer precisely so the distinction cannot be
    accidental.
    """

    model_config = ConfigDict(extra="forbid")

    name: ProjectName
    description: ProjectDescription | None = None


class ProjectTransitionRequest(BaseModel):
    """A requested move to a new lifecycle state.

    `status` is typed as `ProjectStatus`, so a value outside the vocabulary is a
    **422** before any service code runs, while a value inside it that the
    machine refuses is a **409**. The two are genuinely different answers: the
    first says "that is not a state", the second says "that is a state, but not
    from here", and collapsing them would send a client debugging a typo through
    a lifecycle diagram.
    """

    model_config = ConfigDict(extra="forbid")

    status: ProjectStatus


class AssetResponse(BaseModel):
    """One asset attached to a project."""

    id: str
    project_id: str
    name: str
    kind: AssetKind

    #: An opaque locator, populated once bytes are attached.
    #:
    #: **Null is an ordinary value, not an error.** Two routes create assets: the
    #: upload route stores bytes and fills this in, while the metadata-only route
    #: records an asset that has none. A failed upload also leaves it null (see
    #: `AssetStorageService`), so a client renders "no file attached" rather than
    #: assuming every asset is downloadable.
    #:
    #: **Opaque to clients, and must stay that way.** It is a logical name the
    #: storage layer produced; it is not a URL, not a path, and not something to
    #: parse, split or prefix. Bytes are reached through the download route,
    #: which exchanges it for a signed URL (ADR-004).
    storage_path: str | None

    created_by: str
    created_at: str


class AssetCreateRequest(BaseModel):
    """An asset being attached to a project.

    No `storage_path`: there is nothing to point at yet, and accepting a
    caller-supplied path would let a client name an arbitrary location in a
    field that a future storage layer will trust. When upload exists, the path
    will be produced by that layer rather than submitted.
    """

    model_config = ConfigDict(extra="forbid")

    name: AssetName
    kind: AssetKind


class AssetDownloadResponse(BaseModel):
    """A time-limited URL for one asset's bytes.

    **A capability, not a location.** Anyone holding `url` can read the object
    until it expires, with no further authentication — which is precisely why it
    is short-lived and why the API never returns a durable bucket path
    ([[STEP-28 Asset Upload and Download#Decisions]] D3).

    `expires_in_seconds` is restated rather than left for the client to extract
    from the URL's own signature parameters: those are provider-specific, and a
    client parsing them would be depending on the storage vendor through a field
    designed to hide it.
    """

    url: str
    expires_in_seconds: int
