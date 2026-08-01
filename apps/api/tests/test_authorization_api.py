"""Authorization through the API (STEP-11).

`test_rbac_policies.py` proves the *database* enforces roles. That is necessary
and not sufficient: the step's Validation asks whether a `member` is refused an
owner-only action **through the API**, and an endpoint missing its permission
dependency would satisfy every policy test while returning 200 and a body
describing a change that silently did not happen.

These therefore drive real HTTP requests over a real database, with only token
verification substituted -- there is no Supabase in CI to mint a token, and
minting one is not what is under test here.

**The 401/403 distinction is the other property under test.** Conflating them is
a correctness bug before it is a security one: a 401 tells a correct client its
session is broken and sends it into a refresh loop over what is a settled "no".
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
from app.main import create_app
from app.services.token_service import AuthenticatedUser
from tests.conftest import Identity, seed_identity
from tests.test_health import StubDatabase

pytestmark = pytest.mark.usefixtures("migrated_database")


class TokenTable:
    """Maps token strings to identities, so a test can act as several users.

    The stub in `test_auth_endpoints.py` verifies exactly one token. These tests
    need three concurrent identities in one workspace, so this substitutes a
    small table instead of a single valid string.
    """

    def __init__(self, users: dict[str, AuthenticatedUser]) -> None:
        self._users = users

    def verify(self, token: str) -> AuthenticatedUser:
        user = self._users.get(token)

        if user is None:
            raise InvalidTokenError("Token rejected")

        return user


class Roles:
    """Three identities in one workspace, and the tokens that authenticate them."""

    def __init__(self, owner: Identity, admin: Identity, member: Identity) -> None:
        """Record the seeded identities and derive the workspace they share."""
        self.owner = owner
        self.admin = admin
        self.member = member
        self.workspace_id = owner.workspace_id

    def token_for(self, identity: Identity) -> dict[str, str]:
        """Return the Authorization header authenticating as one identity."""
        return {"Authorization": f"Bearer token-{identity.user_id}"}


@pytest.fixture
def roles(admin_connection: psycopg.Connection) -> Iterator[Roles]:
    """Seed one workspace containing an owner, an admin and a plain member."""
    owner = seed_identity(admin_connection, "api-owner")
    admin = seed_identity(admin_connection, "api-admin")
    member = seed_identity(admin_connection, "api-member")

    with admin_connection.cursor() as cursor:
        for identity, role in ((admin, "admin"), (member, "member")):
            cursor.execute(
                "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
                "VALUES (%s, %s, %s)",
                (owner.workspace_id, identity.user_id, role),
            )

    yield Roles(owner, admin, member)


@pytest.fixture
def client(roles: Roles, request_database_url: str) -> Iterator[TestClient]:
    """Return a client backed by the real test database.

    `request_database_url` connects as `projectone_api`, the role the API
    genuinely uses -- one with no `rolbypassrls`. A client pointed at the owner
    connection would pass every test here while proving nothing, because RLS
    would not apply to any of it.
    """

    def settings() -> Settings:
        return Settings(
            environment=Environment.DEVELOPMENT,
            SUPABASE_URL="https://project.test",
            SUPABASE_SECRET_KEY=SecretStr("unused"),
            DATABASE_URL=SecretStr(request_database_url),
            REQUEST_DATABASE_URL=SecretStr(request_database_url),
            _env_file=None,
        )

    tokens = TokenTable(
        {
            f"token-{identity.user_id}": AuthenticatedUser(id=identity.user_id, email=None)
            for identity in (roles.owner, roles.admin, roles.member)
        }
    )

    app = create_app()
    app.dependency_overrides[get_settings] = settings
    app.dependency_overrides[get_database_repository] = lambda: StubDatabase(reachable=True)
    app.dependency_overrides[get_token_service] = lambda: tokens

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


# ------------------------------------------------------------ 403, not 401 --


def test_a_member_is_refused_an_owner_only_action(client: TestClient, roles: Roles) -> None:
    """The denial half of the step's Validation, through the API.

    Erasing a workspace's data is owner-only. A member holds a perfectly valid
    session, so the answer must be 403 -- the request was understood, the caller
    was identified, and the answer is still no.
    """
    response = client.delete(
        f"/workspaces/{roles.workspace_id}/data",
        headers=roles.token_for(roles.member),
    )

    assert response.status_code == 403


def test_an_owner_is_allowed_the_same_action(client: TestClient, roles: Roles) -> None:
    """The permission half. Without it, a check denying everyone would pass.

    Asserts the owner is *admitted* -- 200 rather than 403 -- which is what this
    test is about. The count is 0 because `workspace_members` cannot currently be
    erased over the request path at all: STEP-09's SELECT policy blocks every
    soft delete on that table, for every role. See
    `DataOwnershipService.WorkspaceMembersStore.erase` for the reproduction and
    why the store reports 0 rather than raising or bypassing RLS.
    """
    response = client.delete(
        f"/workspaces/{roles.workspace_id}/data",
        headers=roles.token_for(roles.owner),
    )

    assert response.status_code == 200
    assert response.json()["erased"] == {"workspace_members": 0}


def test_a_member_cannot_rename_the_workspace_through_the_api(
    client: TestClient, roles: Roles
) -> None:
    """A 403 rather than a silent 200 over an UPDATE that matched no rows.

    This is precisely why the service layer exists alongside RLS: the policy
    alone would return `UPDATE 0` and this endpoint would answer 200 with a name
    that was never written.
    """
    response = client.patch(
        f"/workspaces/{roles.workspace_id}",
        json={"name": "renamed by a member"},
        headers=roles.token_for(roles.member),
    )

    assert response.status_code == 403


def test_an_admin_can_rename_the_workspace_through_the_api(
    client: TestClient, roles: Roles
) -> None:
    response = client.patch(
        f"/workspaces/{roles.workspace_id}",
        json={"name": "renamed by an admin"},
        headers=roles.token_for(roles.admin),
    )

    assert response.status_code == 200
    assert response.json()["name"] == "renamed by an admin"


def test_a_member_cannot_export_the_workspace(client: TestClient, roles: Roles) -> None:
    """An export is a bulk copy of every member's data, not ordinary reading."""
    response = client.get(
        f"/workspaces/{roles.workspace_id}/export",
        headers=roles.token_for(roles.member),
    )

    assert response.status_code == 403


def test_an_admin_can_export_the_workspace(client: TestClient, roles: Roles) -> None:
    response = client.get(
        f"/workspaces/{roles.workspace_id}/export",
        headers=roles.token_for(roles.admin),
    )

    assert response.status_code == 200
    assert len(response.json()["stores"]["workspace_members"]) == 3


def test_a_member_can_still_read_what_their_role_permits(client: TestClient, roles: Roles) -> None:
    """RBAC must narrow, never break the product for ordinary members."""
    response = client.get(
        f"/workspaces/{roles.workspace_id}/permissions",
        headers=roles.token_for(roles.member),
    )

    assert response.status_code == 200
    assert response.json()["role"] == "member"
    assert response.json()["permissions"] == ["workspace:view"]


def test_an_owner_holds_every_permission(client: TestClient, roles: Roles) -> None:
    response = client.get(
        f"/workspaces/{roles.workspace_id}/permissions",
        headers=roles.token_for(roles.owner),
    )

    assert response.status_code == 200
    assert "workspace:delete" in response.json()["permissions"]


# ---------------------------------------------- authentication is still 401 --


def test_authentication_failure_is_still_401(client: TestClient, roles: Roles) -> None:
    """The two must not be conflated -- the whole point of the new error type."""
    response = client.patch(
        f"/workspaces/{roles.workspace_id}",
        json={"name": "anything"},
        headers={"Authorization": "Bearer nonsense"},
    )

    assert response.status_code == 401


def test_a_missing_token_is_401_not_403(client: TestClient, roles: Roles) -> None:
    """No credentials means "I do not know who you are", which is 401."""
    response = client.patch(f"/workspaces/{roles.workspace_id}", json={"name": "anything"})

    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"


# --------------------------------------------------- the tenant boundary --


def test_a_non_member_is_refused_and_told_nothing(client: TestClient, roles: Roles) -> None:
    """A workspace the caller does not belong to must not be distinguishable.

    A 404 here versus a 403 elsewhere would reveal whether a workspace id exists
    at all, turning every endpoint taking one into an existence oracle. Both
    surface as the same 403 with the same body.
    """
    stranger_workspace = uuid.uuid4()

    absent = client.get(
        f"/workspaces/{stranger_workspace}/permissions",
        headers=roles.token_for(roles.member),
    )
    forbidden = client.get(
        f"/workspaces/{roles.workspace_id}/export",
        headers=roles.token_for(roles.member),
    )

    assert absent.status_code == forbidden.status_code == 403
    assert absent.json()["detail"] == forbidden.json()["detail"]


def test_a_role_change_takes_effect_on_the_next_request(
    client: TestClient, roles: Roles, admin_connection: psycopg.Connection
) -> None:
    """The invalidation window is one request, and this is what proves it.

    The alternative design -- carrying the role as a JWT claim -- would leave a
    demoted admin fully privileged until their access token expired. Resolving
    the role per request means a demotion is effective immediately, and "one
    request" is the documented window rather than a discovered one.
    """
    before = client.patch(
        f"/workspaces/{roles.workspace_id}",
        json={"name": "while still an admin"},
        headers=roles.token_for(roles.admin),
    )

    assert before.status_code == 200

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.workspace_members SET role = 'member' "
            "WHERE workspace_id = %s AND user_id = %s",
            (roles.workspace_id, roles.admin.user_id),
        )

    after = client.patch(
        f"/workspaces/{roles.workspace_id}",
        json={"name": "after demotion"},
        headers=roles.token_for(roles.admin),
    )

    assert after.status_code == 403, "a demoted admin kept their privileges"
