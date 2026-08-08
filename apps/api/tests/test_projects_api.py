"""Projects and assets through the API (STEP-21).

`test_project_lifecycle.py` proves the *service* refuses an illegal transition
and `test_project_isolation.py` proves the *database* refuses a cross-tenant
read. Both are necessary and neither is sufficient for this step, whose
Validation asks four questions that can only be answered at the route layer:

1. **Does an illegal transition reach the client as 409?** A service raising
   correctly into a router with no handler registered surfaces as a 500 -- a
   deliberate, correct refusal reported as a server crash.
2. **Does a project in another workspace answer 404 rather than 403?** The two
   are different disclosures, and only the response says which one was made.
3. **Does the API offer exactly the legal transitions?** The whole reason
   `legal_transitions` is a response field is that the UI must not hold its own
   copy of the state machine. If the field disagreed with the service, the UI
   would faithfully render the wrong thing.
4. **Can any route return another tenant's project?** Asserted against real
   response bodies, not against repository return values.

These therefore drive real HTTP requests over a real database, with only token
verification substituted -- there is no Supabase in CI to mint a token, and
minting one is not what is under test.
"""

import uuid
from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Environment, Settings, get_settings
from app.core.dependencies import get_database_repository, get_token_service
from app.core.security import InvalidTokenError
from app.core.user_rate_limit import get_user_rate_limiter
from app.main import create_app
from app.schemas.project import AssetKind
from app.services.project_service import ProjectStatus, legal_transitions_from
from app.services.token_service import AuthenticatedUser
from tests.conftest import TEST_BYOK_KEY, Identity, seed_identity
from tests.test_health import StubDatabase

pytestmark = pytest.mark.usefixtures("migrated_database")


class TokenTable:
    """Maps token strings to identities, so a test can act as several users."""

    def __init__(self, users: dict[str, AuthenticatedUser]) -> None:
        """Record the identity behind each accepted token."""
        self._users = users

    def verify(self, token: str) -> AuthenticatedUser:
        """Return the identity a token authenticates, or reject it."""
        user = self._users.get(token)

        if user is None:
            raise InvalidTokenError("Token rejected")

        return user


class Tenants:
    """Two unrelated workspaces, and a plain member inside the first.

    Two tenants rather than one, because half of this step's Validation is about
    what a caller in *another* workspace sees. A single-workspace fixture cannot
    express the question.
    """

    def __init__(self, owner: Identity, member: Identity, stranger: Identity) -> None:
        """Record the seeded identities and the workspace the first two share."""
        self.owner = owner
        self.member = member
        self.stranger = stranger
        self.workspace_id = owner.workspace_id
        self.stranger_workspace_id = stranger.workspace_id

    def token_for(self, identity: Identity) -> dict[str, str]:
        """Return the Authorization header authenticating as one identity."""
        return {"Authorization": f"Bearer token-{identity.user_id}"}


@pytest.fixture
def tenants(admin_connection: psycopg.Connection) -> Iterator[Tenants]:
    """Seed one workspace with an owner and a member, plus an unrelated one."""
    owner = seed_identity(admin_connection, "proj-owner")
    member = seed_identity(admin_connection, "proj-member")
    stranger = seed_identity(admin_connection, "proj-stranger")

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
            "VALUES (%s, %s, 'member')",
            (owner.workspace_id, member.user_id),
        )

    yield Tenants(owner, member, stranger)


@pytest.fixture
def client(tenants: Tenants, request_database_url: str) -> Iterator[TestClient]:
    """Return a client backed by the real test database.

    `request_database_url` connects as `projectone_api`, the role the API
    genuinely uses -- one with no `rolbypassrls`. A client pointed at the owner
    connection would pass every isolation test here while proving nothing.
    """

    def settings() -> Settings:
        return Settings(
            environment=Environment.DEVELOPMENT,
            SUPABASE_URL="https://project.test",
            SUPABASE_SECRET_KEY=SecretStr("unused"),
            DATABASE_URL=SecretStr(request_database_url),
            REQUEST_DATABASE_URL=SecretStr(request_database_url),
            byok_encryption_key=SecretStr(TEST_BYOK_KEY),
            _env_file=None,
        )

    tokens = TokenTable(
        {
            f"token-{identity.user_id}": AuthenticatedUser(id=identity.user_id, email=None)
            for identity in (tenants.owner, tenants.member, tenants.stranger)
        }
    )

    app = create_app()
    app.dependency_overrides[get_settings] = settings
    app.dependency_overrides[get_database_repository] = lambda: StubDatabase(reachable=True)
    app.dependency_overrides[get_token_service] = lambda: tokens

    # The per-user limiter is process-wide state, so a test creating 30 projects
    # would otherwise exhaust the allowance for every test after it -- and the
    # failure would surface in whichever test ran next rather than in the one
    # that caused it.
    get_user_rate_limiter().clear()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _create(client: TestClient, tenants: Tenants, actor: Identity, name: str = "A project") -> dict:
    """Create a project through the API and return its body."""
    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects",
        json={"name": name},
        headers=tenants.token_for(actor),
    )

    assert response.status_code == 201, response.text

    return response.json()


def _advance(client: TestClient, tenants: Tenants, project_id: str, status: str) -> int:
    """Request one transition and return the status code."""
    return client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project_id}/transitions",
        json={"status": status},
        headers=tenants.token_for(tenants.owner),
    ).status_code


# ------------------------------------------------------------ the lifecycle --


def test_a_project_is_created_in_the_initial_state(client: TestClient, tenants: Tenants) -> None:
    """Creation puts a project at the start of the pipeline, not anywhere else."""
    body = _create(client, tenants, tenants.owner)

    assert body["status"] == "idea"
    assert body["version"] == 1


def test_the_status_cannot_be_chosen_at_creation(client: TestClient, tenants: Tenants) -> None:
    """A project created directly into Approval never went through review.

    422 rather than a silent discard: `extra="forbid"` is what makes the refusal
    visible to whoever sent it.
    """
    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects",
        json={"name": "Straight to publishing", "status": "publishing"},
        headers=tenants.token_for(tenants.owner),
    )

    assert response.status_code == 422


def test_a_legal_transition_returns_the_updated_project(
    client: TestClient, tenants: Tenants
) -> None:
    """The permission half. Without it, a route refusing everything would pass."""
    project = _create(client, tenants, tenants.owner)

    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}/transitions",
        json={"status": "planning"},
        headers=tenants.token_for(tenants.owner),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "planning"


def test_an_illegal_transition_is_409_through_http(client: TestClient, tenants: Tenants) -> None:
    """**The step's headline Validation check.**

    `idea -> publishing` skips six states. The service refuses it, and this
    asserts the refusal reaches the client as a 409 rather than as the 500 an
    unregistered handler would produce.
    """
    project = _create(client, tenants, tenants.owner)

    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}/transitions",
        json={"status": "publishing"},
        headers=tenants.token_for(tenants.owner),
    )

    assert response.status_code == 409
    # The message names both states -- safe, because the caller already knows the
    # current one, and the difference between an actionable error and a mystery.
    assert "idea" in response.json()["detail"]
    assert "publishing" in response.json()["detail"]


def test_an_unknown_status_is_422_not_409(client: TestClient, tenants: Tenants) -> None:
    """The two refusals are different answers and must not be collapsed.

    422 says "that is not a state"; 409 says "that is a state, but not from
    here". A client debugging a typo should not be sent to a lifecycle diagram.
    """
    project = _create(client, tenants, tenants.owner)

    assert _advance(client, tenants, project["id"], "not-a-real-status") == 422


def test_archive_is_reachable_from_the_initial_state(client: TestClient, tenants: Tenants) -> None:
    """An idea that goes nowhere is the common case, not an error."""
    project = _create(client, tenants, tenants.owner)

    assert _advance(client, tenants, project["id"], "archive") == 200


def test_archive_is_terminal_through_http(client: TestClient, tenants: Tenants) -> None:
    """A state machine that can leave its terminal state has no terminal state."""
    project = _create(client, tenants, tenants.owner)

    assert _advance(client, tenants, project["id"], "archive") == 200
    assert _advance(client, tenants, project["id"], "idea") == 409


def test_review_can_send_a_project_back_to_editing(client: TestClient, tenants: Tenants) -> None:
    """The one backward edge, walked through the real routes.

    Without it a rejected review would have to be archived and the project
    recreated, losing its assets over an ordinary editorial event.
    """
    project = _create(client, tenants, tenants.owner)

    for status in ("planning", "generation", "review", "editing"):
        assert _advance(client, tenants, project["id"], status) == 200, status

    read = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}",
        headers=tenants.token_for(tenants.owner),
    )

    assert read.json()["status"] == "editing"


# -------------------------------------------- the API offers the real rules --


def test_legal_transitions_match_the_service_in_every_state(
    client: TestClient, tenants: Tenants
) -> None:
    """**The check that keeps the UI from needing its own state machine.**

    A separate project per state, each walked to that state through real
    transitions, and its `legal_transitions` compared against
    `legal_transitions_from`. Asserted rather than eyeballed, per the step's
    Validation.

    Walking to each state rather than writing statuses directly is deliberate:
    it also proves the forward path is traversable end to end, which a test that
    set `status` behind the API's back would not.
    """
    # The forward path, in order. `editing` is reached from `review`, which is
    # the backward edge, so the natural walk visits it before `approval`.
    path = (
        ProjectStatus.PLANNING,
        ProjectStatus.GENERATION,
        ProjectStatus.REVIEW,
        ProjectStatus.EDITING,
        ProjectStatus.APPROVAL,
        ProjectStatus.PUBLISHING,
        ProjectStatus.ANALYTICS,
    )

    project = _create(client, tenants, tenants.owner, "Walked through the pipeline")
    body = project

    # `idea` first, before any transition.
    checked = [ProjectStatus.IDEA]
    assert body["legal_transitions"] == sorted(legal_transitions_from(ProjectStatus.IDEA))

    for target in path:
        response = client.post(
            f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}/transitions",
            json={"status": target},
            headers=tenants.token_for(tenants.owner),
        )

        assert response.status_code == 200, f"{target}: {response.text}"

        body = response.json()
        checked.append(target)

        assert body["legal_transitions"] == sorted(legal_transitions_from(target)), target

    # Archive last, and it reports no moves at all -- the terminal state saying
    # so explicitly rather than the field being absent.
    archived = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}/transitions",
        json={"status": "archive"},
        headers=tenants.token_for(tenants.owner),
    )

    assert archived.json()["legal_transitions"] == []
    checked.append(ProjectStatus.ARCHIVE)

    # Every state in the vocabulary was actually visited. Without this the test
    # would still pass if the walk silently stopped early.
    assert set(checked) == set(ProjectStatus)


def test_offering_only_legal_transitions_would_never_produce_a_409(
    client: TestClient, tenants: Tenants
) -> None:
    """A UI driven by `legal_transitions` cannot ask for something refused.

    The property that makes the field worth returning: every move the API
    advertises is a move the API accepts. Asserted by taking the advertised list
    and submitting each one, against a fresh project each time.
    """
    for target in legal_transitions_from(ProjectStatus.IDEA):
        project = _create(client, tenants, tenants.owner, f"To {target}")

        advertised = project["legal_transitions"]

        assert target in advertised
        assert _advance(client, tenants, project["id"], target) == 200, target


# ----------------------------------------------------- the tenant boundary --


def test_another_tenants_project_is_404_not_403(client: TestClient, tenants: Tenants) -> None:
    """**The step's second Validation check**, and a deliberate asymmetry.

    A *workspace* the caller does not belong to answers 403, so a workspace id
    cannot be used to test which ones exist. A *project* inside a workspace they
    do belong to answers 404, because an invisible project and an absent one are
    the same fact from the caller's side.

    Here the stranger asks their **own** workspace for a project id belonging to
    another tenant -- so `requires(...)` admits them and the question genuinely
    reaches the project lookup, which is the path under test.
    """
    project = _create(client, tenants, tenants.owner)

    response = client.get(
        f"/api/v1/workspaces/{tenants.stranger_workspace_id}/projects/{project['id']}",
        headers=tenants.token_for(tenants.stranger),
    )

    assert response.status_code == 404


def test_a_project_id_is_not_an_existence_oracle(client: TestClient, tenants: Tenants) -> None:
    """A real hidden project and an invented id must be indistinguishable.

    If they differed, a stranger could enumerate which project ids exist by
    comparing responses -- the disclosure the conflation in
    `ProjectNotFoundError` exists to prevent.
    """
    project = _create(client, tenants, tenants.owner)
    invented = uuid.uuid4()

    hidden = client.get(
        f"/api/v1/workspaces/{tenants.stranger_workspace_id}/projects/{project['id']}",
        headers=tenants.token_for(tenants.stranger),
    )
    absent = client.get(
        f"/api/v1/workspaces/{tenants.stranger_workspace_id}/projects/{invented}",
        headers=tenants.token_for(tenants.stranger),
    )

    assert hidden.status_code == absent.status_code == 404
    assert hidden.json()["detail"] == absent.json()["detail"]


def test_a_non_member_is_refused_the_workspace_itself(client: TestClient, tenants: Tenants) -> None:
    """The workspace gate answers 403, and that is the other half of the split."""
    response = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects",
        headers=tenants.token_for(tenants.stranger),
    )

    assert response.status_code == 403


def test_no_route_returns_another_tenants_project(client: TestClient, tenants: Tenants) -> None:
    """**The step's fourth Validation check**, against real response bodies.

    Every read route, asserted as a set rather than one at a time: a single
    forgotten route is the whole exposure, and checking one proves nothing about
    the others.
    """
    project = _create(client, tenants, tenants.owner, "Confidential")

    listing = client.get(
        f"/api/v1/workspaces/{tenants.stranger_workspace_id}/projects",
        headers=tenants.token_for(tenants.stranger),
    )

    assert listing.status_code == 200
    assert listing.json() == []

    # Every route taking a project id, through the stranger's own workspace.
    base = f"/api/v1/workspaces/{tenants.stranger_workspace_id}/projects/{project['id']}"
    headers = tenants.token_for(tenants.stranger)

    assert client.get(base, headers=headers).status_code == 404
    assert client.get(f"{base}/assets", headers=headers).status_code == 404
    assert client.patch(base, json={"name": "Renamed"}, headers=headers).status_code == 404
    assert client.delete(base, headers=headers).status_code == 404
    assert (
        client.post(f"{base}/transitions", json={"status": "planning"}, headers=headers).status_code
        == 404
    )
    assert (
        client.post(
            f"{base}/assets", json={"name": "a", "kind": "document"}, headers=headers
        ).status_code
        == 404
    )

    # And the project is untouched: a 404 that had already written would be far
    # worse than one that merely reported wrongly.
    unchanged = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}",
        headers=tenants.token_for(tenants.owner),
    )

    assert unchanged.json()["name"] == "Confidential"
    assert unchanged.json()["status"] == "idea"


# ------------------------------------------------------------------- roles --


def test_a_plain_member_can_create_a_project(client: TestClient, tenants: Tenants) -> None:
    """Projects are the workspace's shared work, not an administrative setting.

    Deliberately unlike AI keys and budgets, which are owner/admin only. A member
    who cannot create a project cannot use the product.
    """
    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects",
        json={"name": "Made by a member"},
        headers=tenants.token_for(tenants.member),
    )

    assert response.status_code == 201


def test_a_plain_member_can_transition_a_project(client: TestClient, tenants: Tenants) -> None:
    """Moving work through the pipeline is the job, not a privilege."""
    project = _create(client, tenants, tenants.owner)

    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}/transitions",
        json={"status": "planning"},
        headers=tenants.token_for(tenants.member),
    )

    assert response.status_code == 200


def test_authentication_failure_is_still_401(client: TestClient, tenants: Tenants) -> None:
    """The 401/403 distinction survives the new router."""
    response = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects",
        headers={"Authorization": "Bearer nonsense"},
    )

    assert response.status_code == 401


# ---------------------------------------------------- deletion vs archiving --


def test_deleting_a_project_removes_it_from_the_listing(
    client: TestClient, tenants: Tenants
) -> None:
    """Soft deletion, and from the caller's side the project is gone.

    This is also the route-level guard on the defect that cost STEP-11a and
    STEP-19 a step each: a SELECT policy filtering `deleted_at IS NULL` makes the
    soft delete itself impossible, and it would fail right here.
    """
    project = _create(client, tenants, tenants.owner, "To be deleted")

    deleted = client.delete(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}",
        headers=tenants.token_for(tenants.owner),
    )

    assert deleted.status_code == 204

    listing = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects",
        headers=tenants.token_for(tenants.owner),
    )

    assert [item["id"] for item in listing.json()] == []

    read = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}",
        headers=tenants.token_for(tenants.owner),
    )

    assert read.status_code == 404


def test_an_archived_project_stays_in_the_listing(client: TestClient, tenants: Tenants) -> None:
    """**Archive is not deletion**, and the API must not blur them.

    An archived project remains part of the workspace as a record of finished or
    abandoned work. A UI filtering it out would make archiving look like
    deleting, which is the confusion [[Project Lifecycle]] warns about.
    """
    project = _create(client, tenants, tenants.owner, "Abandoned idea")

    assert _advance(client, tenants, project["id"], "archive") == 200

    listing = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects",
        headers=tenants.token_for(tenants.owner),
    )

    entries = {item["id"]: item for item in listing.json()}

    assert project["id"] in entries
    assert entries[project["id"]]["status"] == "archive"


def test_an_archived_project_can_still_be_deleted(client: TestClient, tenants: Tenants) -> None:
    """No rule requires archiving before deletion, and none requires the reverse."""
    project = _create(client, tenants, tenants.owner)

    assert _advance(client, tenants, project["id"], "archive") == 200
    assert (
        client.delete(
            f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}",
            headers=tenants.token_for(tenants.owner),
        ).status_code
        == 204
    )


def test_deleting_a_project_twice_is_404(client: TestClient, tenants: Tenants) -> None:
    """Reporting 204 for a no-op would claim something happened that did not."""
    project = _create(client, tenants, tenants.owner)
    path = f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}"

    assert client.delete(path, headers=tenants.token_for(tenants.owner)).status_code == 204
    assert client.delete(path, headers=tenants.token_for(tenants.owner)).status_code == 404


# ------------------------------------------------------------------ renaming --


def test_renaming_a_project_does_not_change_its_status(
    client: TestClient, tenants: Tenants
) -> None:
    """The rename route has no status field, and this proves the absence holds."""
    project = _create(client, tenants, tenants.owner)

    assert _advance(client, tenants, project["id"], "planning") == 200

    renamed = client.patch(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}",
        json={"name": "A better name", "description": "Now with a description"},
        headers=tenants.token_for(tenants.owner),
    )

    assert renamed.status_code == 200
    assert renamed.json()["name"] == "A better name"
    assert renamed.json()["status"] == "planning"


def test_a_rename_cannot_smuggle_a_status(client: TestClient, tenants: Tenants) -> None:
    """422 rather than a silently discarded field.

    Without `extra="forbid"` this body would return 200 with the status
    unchanged, which is indistinguishable from success to whoever sent it.
    """
    project = _create(client, tenants, tenants.owner)

    response = client.patch(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}",
        json={"name": "Sneaky", "status": "publishing"},
        headers=tenants.token_for(tenants.owner),
    )

    assert response.status_code == 422


def test_a_blank_name_is_refused(client: TestClient, tenants: Tenants) -> None:
    """Whitespace-only passes a naive length check and renders as a blank row."""
    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects",
        json={"name": "   "},
        headers=tenants.token_for(tenants.owner),
    )

    assert response.status_code == 422


def test_a_description_can_be_cleared(client: TestClient, tenants: Tenants) -> None:
    """Explicit null clears it, which is why the field is required-but-nullable."""
    created = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects",
        json={"name": "Described", "description": "Something"},
        headers=tenants.token_for(tenants.owner),
    )

    assert created.json()["description"] == "Something"

    cleared = client.patch(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{created.json()['id']}",
        json={"name": "Described", "description": None},
        headers=tenants.token_for(tenants.owner),
    )

    assert cleared.json()["description"] is None


# ------------------------------------------------------------------ assets --


def test_an_asset_can_be_attached_and_listed(client: TestClient, tenants: Tenants) -> None:
    """Records that an asset exists. It does not store a file -- none can be."""
    project = _create(client, tenants, tenants.owner)

    created = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}/assets",
        json={"name": "Opening script", "kind": "document"},
        headers=tenants.token_for(tenants.owner),
    )

    assert created.status_code == 201
    # Null, and honestly so: no storage backend exists, so nothing populates it.
    assert created.json()["storage_path"] is None

    listing = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}/assets",
        headers=tenants.token_for(tenants.owner),
    )

    assert [asset["name"] for asset in listing.json()] == ["Opening script"]


def test_asset_kind_vocabulary_matches_the_database(
    client: TestClient, tenants: Tenants, admin_connection: psycopg.Connection
) -> None:
    """`AssetKind` and `ck_assets_kind_valid` must be the same four values.

    **This test exists because they were not.** `AssetKind` was first written as
    free text, so the API accepted `kind: "script"` and PostgreSQL refused it --
    a client error reported as a 500, with a constraint name in the log instead
    of a usable message. Found by driving these routes against a real database.

    Asserted against the catalog rather than against a second literal, because a
    literal is a third copy that drifts exactly like the first two did.
    """
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'ck_assets_kind_valid'"
        )
        row = cursor.fetchone()

    assert row is not None, "ck_assets_kind_valid is missing from the database"

    definition = row[0]

    for kind in AssetKind:
        assert f"'{kind.value}'" in definition, f"{kind.value} is not permitted by the constraint"

    # Both directions: a value the database permits but the enum omits would make
    # a legitimate asset kind unreachable through the API.
    assert definition.count("'") // 2 == len(AssetKind), definition


def test_every_accepted_asset_kind_is_actually_storable(
    client: TestClient, tenants: Tenants
) -> None:
    """The end-to-end version of the check above, through the real routes.

    A schema and a constraint agreeing on paper is worth less than a request
    succeeding, and this is the assertion that would have failed originally.
    """
    project = _create(client, tenants, tenants.owner, "Every kind")

    for kind in AssetKind:
        response = client.post(
            f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}/assets",
            json={"name": f"An {kind.value}", "kind": kind.value},
            headers=tenants.token_for(tenants.owner),
        )

        assert response.status_code == 201, f"{kind.value}: {response.text}"


def test_an_unknown_asset_kind_is_422_not_500(client: TestClient, tenants: Tenants) -> None:
    """A kind outside the vocabulary is a client error, answered as one.

    Before `AssetKind` was an enum this reached PostgreSQL and returned 500.
    """
    project = _create(client, tenants, tenants.owner)

    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}/assets",
        json={"name": "A script", "kind": "script"},
        headers=tenants.token_for(tenants.owner),
    )

    assert response.status_code == 422


def test_an_asset_cannot_carry_a_caller_supplied_storage_path(
    client: TestClient, tenants: Tenants
) -> None:
    """A future storage layer will trust this column; a client must not write it."""
    project = _create(client, tenants, tenants.owner)

    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}/assets",
        json={"name": "Injected", "kind": "document", "storage_path": "/etc/passwd"},
        headers=tenants.token_for(tenants.owner),
    )

    assert response.status_code == 422


def test_an_asset_cannot_be_attached_to_an_unreachable_project(
    client: TestClient, tenants: Tenants
) -> None:
    """404, not a foreign key violation surfacing as a 500."""
    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{uuid.uuid4()}/assets",
        json={"name": "Orphan", "kind": "document"},
        headers=tenants.token_for(tenants.owner),
    )

    assert response.status_code == 404


def test_an_asset_can_be_removed(client: TestClient, tenants: Tenants) -> None:
    """Soft deletion again, and the listing stops carrying it."""
    project = _create(client, tenants, tenants.owner)

    asset = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}/assets",
        json={"name": "Temporary", "kind": "document"},
        headers=tenants.token_for(tenants.owner),
    ).json()

    removed = client.delete(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}/assets/{asset['id']}",
        headers=tenants.token_for(tenants.owner),
    )

    assert removed.status_code == 204

    listing = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}/assets",
        headers=tenants.token_for(tenants.owner),
    )

    assert listing.json() == []


def test_an_asset_cannot_be_deleted_through_another_projects_url(
    client: TestClient, tenants: Tenants
) -> None:
    """Every segment of the URL is enforced, not just the ones the query uses.

    `ProjectService.delete_asset` keys only on the workspace, so without the
    route's own check the `{project_id}` segment would be decorative -- and a URL
    whose segments are not all enforced is one a reader reasonably assumes are.
    """
    owning = _create(client, tenants, tenants.owner, "Owns the asset")
    other = _create(client, tenants, tenants.owner, "Does not")

    asset = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{owning['id']}/assets",
        json={"name": "Belongs elsewhere", "kind": "document"},
        headers=tenants.token_for(tenants.owner),
    ).json()

    misdirected = client.delete(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{other['id']}/assets/{asset['id']}",
        headers=tenants.token_for(tenants.owner),
    )

    assert misdirected.status_code == 404

    # Still there, which is the half that matters: a wrong status code with the
    # deletion performed anyway would be the actual defect.
    listing = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects/{owning['id']}/assets",
        headers=tenants.token_for(tenants.owner),
    )

    assert [item["id"] for item in listing.json()] == [asset["id"]]


def test_assets_may_be_attached_in_any_lifecycle_state(
    client: TestClient, tenants: Tenants
) -> None:
    """A reference image attached while a project is still an Idea is normal.

    Restricting attachment to Generation would be a rule [[Projects]] does not
    state.
    """
    project = _create(client, tenants, tenants.owner)

    for status in ("planning", "generation", "review"):
        assert _advance(client, tenants, project["id"], status) == 200

        response = client.post(
            f"/api/v1/workspaces/{tenants.workspace_id}/projects/{project['id']}/assets",
            json={"name": f"Asset for {status}", "kind": "document"},
            headers=tenants.token_for(tenants.owner),
        )

        assert response.status_code == 201, status
