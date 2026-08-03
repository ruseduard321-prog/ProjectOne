"""The workspace and membership endpoints (STEP-13).

Driven over **real connections against a real database**, not stubs. These
assert what RLS, the policies and the last-owner trigger actually do when a
request reaches them, and a stub proving "our fake returned no rows" would say
nothing about any of it.

The identity layer is the only thing substituted: `get_token_service` is
replaced so a test can act as a seeded user without minting a real Supabase
token. Everything below that -- the tenant connection, the policies, the
triggers -- is genuine.
"""

import uuid
from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.api import API_PREFIX
from app.core.config import Environment, Settings, get_settings
from app.core.dependencies import get_database_repository, get_token_service
from app.core.security import InvalidTokenError
from app.main import create_app
from app.services.token_service import AuthenticatedUser
from tests.conftest import TEST_BYOK_KEY, Identity, seed_identity
from tests.test_health import StubDatabase

pytestmark = pytest.mark.usefixtures("migrated_database")


class RosterTokenService:
    """Verifies a token of the form `token-<user id>`.

    A roster rather than a single fixed user, because every test here needs at
    least two identities acting against the same workspace. The token format is
    deliberately trivial: what is under test is authorization and the database,
    not token parsing, which `test_token_service.py` covers against real ES256
    signatures.
    """

    def __init__(self, users: dict[str, AuthenticatedUser]) -> None:
        self._users = users

    def verify(self, token: str) -> AuthenticatedUser:
        user = self._users.get(token)

        if user is None:
            raise InvalidTokenError("Unknown test token")

        return user


@pytest.fixture
def api(
    migrated_database: str,
    request_database_url: str,
    admin_connection: psycopg.Connection,
) -> Iterator[tuple[TestClient, dict[str, Identity]]]:
    """Return a client wired to the real test database, plus seeded identities.

    `request_database_url` connects as `projectone_api` -- the role the API
    genuinely uses, without `rolbypassrls` -- so the endpoints under test are
    subject to exactly the isolation a real request gets. Pointing this at the
    owner connection would make every test here pass while proving nothing.

    `database_url` is the privileged connection, which the workspace-creation
    bootstrap legitimately needs.
    """
    people = {
        name: seed_identity(admin_connection, f"ep-{name}")
        for name in ("owner", "other", "outsider")
    }

    def settings() -> Settings:
        return Settings(
            environment=Environment.DEVELOPMENT,
            SUPABASE_URL="https://project.test",
            SUPABASE_SECRET_KEY=SecretStr("unused"),
            DATABASE_URL=SecretStr(migrated_database),
            REQUEST_DATABASE_URL=SecretStr(request_database_url),
            byok_encryption_key=SecretStr(TEST_BYOK_KEY),
            _env_file=None,
        )

    roster = {
        f"token-{identity.user_id}": AuthenticatedUser(id=identity.user_id, email=identity.email)
        for identity in people.values()
    }

    app = create_app()
    app.dependency_overrides[get_settings] = settings
    app.dependency_overrides[get_database_repository] = lambda: StubDatabase(reachable=True)
    app.dependency_overrides[get_token_service] = lambda: RosterTokenService(roster)

    with TestClient(app) as client:
        yield client, people

    app.dependency_overrides.clear()


def auth(identity: Identity) -> dict[str, str]:
    """Return the bearer header for a seeded identity."""
    return {"Authorization": f"Bearer token-{identity.user_id}"}


# ---------------------------------------------------------------- creation --


def test_creating_a_workspace_makes_the_caller_its_owner(api) -> None:
    """The two-row bootstrap works end to end.

    The membership row is the half a client cannot write for itself, so a
    response that merely returns a workspace id proves nothing -- the caller
    must be able to *see* what they just created, which requires the membership
    row to exist.
    """
    client, people = api

    response = client.post(
        f"{API_PREFIX}/workspaces", json={"name": "Bootstrapped"}, headers=auth(people["owner"])
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Bootstrapped"
    assert body["owner_id"] == str(people["owner"].user_id)

    visible = client.get(f"{API_PREFIX}/workspaces", headers=auth(people["owner"])).json()
    assert body["id"] in [workspace["id"] for workspace in visible]


def test_a_client_cannot_bootstrap_a_workspace_by_direct_insert(
    request_database_url: str, admin_connection: psycopg.Connection
) -> None:
    """The reason the audited path exists, asserted rather than assumed.

    The `workspaces` row inserts fine; the creator's own first membership row is
    refused, because `workspace_members_insert_same_workspace` tests a
    membership the creator does not yet have. If this ever starts passing, the
    privileged bootstrap has become unnecessary -- and, more importantly, a
    client can assemble a tenant boundary row by row.
    """
    identity = seed_identity(admin_connection, "direct")
    workspace_id = uuid.uuid4()

    connection = psycopg.connect(request_database_url)
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE authenticated")
        cursor.execute(
            "SELECT set_config('request.jwt.claim.sub', %s, true)", (str(identity.user_id),)
        )
        cursor.execute(
            "INSERT INTO public.workspaces (id, name, owner_id) VALUES (%s, 'Direct', %s)",
            (workspace_id, identity.user_id),
        )

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cursor.execute(
                "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
                "VALUES (%s, %s, 'owner')",
                (workspace_id, identity.user_id),
            )

    connection.rollback()
    connection.close()


def test_a_workspace_cannot_be_created_for_someone_else(api) -> None:
    """`owner_id` is not accepted from a body, so it cannot be forged.

    The schema has no such field; an extra key is ignored rather than honoured,
    and the owner remains the verified caller.
    """
    client, people = api

    response = client.post(
        f"{API_PREFIX}/workspaces",
        json={"name": "Planted", "owner_id": str(people["other"].user_id)},
        headers=auth(people["owner"]),
    )

    assert response.status_code == 201
    assert response.json()["owner_id"] == str(people["owner"].user_id)


def test_creating_a_workspace_requires_authentication(api) -> None:
    client, _ = api

    assert client.post(f"{API_PREFIX}/workspaces", json={"name": "Anon"}).status_code == 401


def test_a_blank_workspace_name_is_rejected(api) -> None:
    """Whitespace is stripped before the length bound is applied."""
    client, people = api

    response = client.post(
        f"{API_PREFIX}/workspaces", json={"name": "   "}, headers=auth(people["owner"])
    )

    assert response.status_code == 422


# ------------------------------------------------------------------ members --


def test_an_owner_adds_a_member_and_the_listing_shows_them(api) -> None:
    client, people = api
    workspace = people["owner"].workspace_id

    added = client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(people["other"].user_id)},
        headers=auth(people["owner"]),
    )

    assert added.status_code == 204

    members = client.get(
        f"{API_PREFIX}/workspaces/{workspace}/members", headers=auth(people["owner"])
    ).json()

    assert {member["user_id"] for member in members} == {
        str(people["owner"].user_id),
        str(people["other"].user_id),
    }


def test_an_added_member_can_actually_reach_the_workspace(api) -> None:
    """Membership is real, not merely recorded.

    The row only means something if RLS starts admitting the new member -- which
    is the difference between writing a row and granting access.
    """
    client, people = api
    workspace = people["owner"].workspace_id

    before = client.get(f"{API_PREFIX}/workspaces", headers=auth(people["other"])).json()
    assert str(workspace) not in [entry["id"] for entry in before]

    client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(people["other"].user_id)},
        headers=auth(people["owner"]),
    )

    after = client.get(f"{API_PREFIX}/workspaces", headers=auth(people["other"])).json()
    assert str(workspace) in [entry["id"] for entry in after]


def test_a_member_may_not_add_anyone(api) -> None:
    """`MANAGE_MEMBERS` is not held by `member`."""
    client, people = api
    workspace = people["owner"].workspace_id

    client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(people["other"].user_id)},
        headers=auth(people["owner"]),
    )

    refused = client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(people["outsider"].user_id)},
        headers=auth(people["other"]),
    )

    assert refused.status_code == 403


def test_an_admin_may_not_grant_owner(api) -> None:
    """Otherwise `MANAGE_MEMBERS` is a self-promotion path.

    An admin who could mint an owner could add a second account of their own as
    owner and act through it, which makes the owner/admin distinction
    decorative.
    """
    client, people = api
    workspace = people["owner"].workspace_id

    client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(people["other"].user_id), "role": "admin"},
        headers=auth(people["owner"]),
    )

    refused = client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(people["outsider"].user_id), "role": "owner"},
        headers=auth(people["other"]),
    )

    assert refused.status_code == 403


def test_an_outsider_adding_a_member_is_refused_identically_to_a_role_failure(api) -> None:
    """The identical-403-body property, on a new endpoint.

    A caller who is not a member at all and a caller whose role is too low must
    receive the same answer. A difference would turn a workspace id into an
    existence oracle.
    """
    client, people = api
    workspace = people["owner"].workspace_id

    client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(people["other"].user_id)},
        headers=auth(people["owner"]),
    )

    role_too_low = client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(people["outsider"].user_id)},
        headers=auth(people["other"]),
    )
    not_a_member = client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(people["other"].user_id)},
        headers=auth(people["outsider"]),
    )

    assert role_too_low.status_code == not_a_member.status_code == 403
    assert role_too_low.json()["detail"] == not_a_member.json()["detail"]


def test_re_adding_a_removed_member_revives_one_row(
    api, admin_connection: psycopg.Connection
) -> None:
    """The partial unique index does not stop a duplicate live row.

    `uq_workspace_members_active` only constrains rows where `deleted_at IS
    NULL`, so a naive INSERT after a removal leaves two rows for one person --
    one dead, one live -- which passes the constraint and corrupts every count
    that follows.
    """
    client, people = api
    workspace = people["owner"].workspace_id
    target = people["other"].user_id

    for _ in range(2):
        client.post(
            f"{API_PREFIX}/workspaces/{workspace}/members",
            json={"user_id": str(target)},
            headers=auth(people["owner"]),
        )
        client.delete(
            f"{API_PREFIX}/workspaces/{workspace}/members/{target}",
            headers=auth(people["owner"]),
        )

    client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(target)},
        headers=auth(people["owner"]),
    )

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM public.workspace_members "
            "WHERE workspace_id = %s AND user_id = %s",
            (workspace, target),
        )
        total = cursor.fetchone()[0]

    assert total == 1, "re-adding a removed member duplicated the row"


def test_a_removed_member_is_absent_from_the_listing(api) -> None:
    """The SELECT policy no longer filters `deleted_at` -- the query must.

    Migration `b8e1d94c50a7` moved that filter out of the policy, which is what
    made removal possible at all. A listing that relied on the policy would show
    removed people as current members.
    """
    client, people = api
    workspace = people["owner"].workspace_id
    target = people["other"].user_id

    client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(target)},
        headers=auth(people["owner"]),
    )
    client.delete(
        f"{API_PREFIX}/workspaces/{workspace}/members/{target}", headers=auth(people["owner"])
    )

    members = client.get(
        f"{API_PREFIX}/workspaces/{workspace}/members", headers=auth(people["owner"])
    ).json()

    assert str(target) not in {member["user_id"] for member in members}


def test_a_removed_member_loses_access_immediately(api) -> None:
    client, people = api
    workspace = people["owner"].workspace_id
    target = people["other"].user_id

    client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(target)},
        headers=auth(people["owner"]),
    )
    client.delete(
        f"{API_PREFIX}/workspaces/{workspace}/members/{target}", headers=auth(people["owner"])
    )

    visible = client.get(f"{API_PREFIX}/workspaces", headers=auth(people["other"])).json()

    assert str(workspace) not in [entry["id"] for entry in visible]


def test_an_outsider_cannot_list_members(api) -> None:
    client, people = api

    response = client.get(
        f"{API_PREFIX}/workspaces/{people['owner'].workspace_id}/members",
        headers=auth(people["outsider"]),
    )

    assert response.status_code == 403


# ------------------------------------------------- leaving and last owner --


def test_the_last_owner_cannot_leave_and_is_told_why(api) -> None:
    """409, and a deliberately specific message.

    The generic-body rule protects authentication and authorization answers,
    where specificity is an oracle. Here it leaks nothing an owner does not
    already know, and withholding it would leave them stuck.
    """
    client, people = api

    response = client.post(
        f"{API_PREFIX}/workspaces/{people['owner'].workspace_id}/leave",
        headers=auth(people["owner"]),
    )

    assert response.status_code == 409
    assert "ownership" in response.json()["detail"].lower()


def test_a_member_may_leave(api) -> None:
    client, people = api
    workspace = people["owner"].workspace_id

    client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(people["other"].user_id)},
        headers=auth(people["owner"]),
    )

    left = client.post(f"{API_PREFIX}/workspaces/{workspace}/leave", headers=auth(people["other"]))

    assert left.status_code == 204


def test_transferring_ownership_then_leaving_succeeds(api) -> None:
    """The remedy the 409 names actually works.

    An error message pointing at a route that does not deliver is worse than no
    message, so the path it recommends is asserted end to end.
    """
    client, people = api
    workspace = people["owner"].workspace_id

    client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(people["other"].user_id)},
        headers=auth(people["owner"]),
    )

    transferred = client.post(
        f"{API_PREFIX}/workspaces/{workspace}/ownership",
        json={"successor_id": str(people["other"].user_id)},
        headers=auth(people["owner"]),
    )
    assert transferred.status_code == 204

    left = client.post(f"{API_PREFIX}/workspaces/{workspace}/leave", headers=auth(people["owner"]))
    assert left.status_code == 204


def test_a_member_may_not_transfer_ownership(api) -> None:
    client, people = api
    workspace = people["owner"].workspace_id

    client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(people["other"].user_id)},
        headers=auth(people["owner"]),
    )

    refused = client.post(
        f"{API_PREFIX}/workspaces/{workspace}/ownership",
        json={"successor_id": str(people["outsider"].user_id)},
        headers=auth(people["other"]),
    )

    assert refused.status_code == 403


def test_every_new_endpoint_error_carries_the_envelope(api) -> None:
    """The STEP-12 contract holds on the routes added here."""
    client, people = api

    body = client.get(
        f"{API_PREFIX}/workspaces/{people['owner'].workspace_id}/members",
        headers=auth(people["outsider"]),
    ).json()

    assert "detail" in body
    assert body["request_id"] != "-"
