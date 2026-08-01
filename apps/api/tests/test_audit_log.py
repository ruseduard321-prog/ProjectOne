"""The audit log (STEP-13).

Two things are under test, and the second matters more than the first:

1. **Actions are recorded** — a workspace created, a member added or removed,
   ownership transferred.
2. **The record cannot be tampered with.** An audit trail its own subject can
   edit or delete is not an audit trail; it is a log that will be trusted
   precisely when it should not be. Those guarantees are asserted against the
   real database, because they are enforced by policies and grants rather than
   by application code.
"""

import uuid
from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient

from app.core.api import API_PREFIX
from tests.conftest import Identity
from tests.test_workspace_endpoints import api, auth  # noqa: F401 - fixtures reused

pytestmark = pytest.mark.usefixtures("migrated_database")


def trail(client: TestClient, workspace_id: uuid.UUID, identity: Identity) -> list[dict]:
    """Return a workspace's audit trail as the given identity sees it."""
    response = client.get(f"{API_PREFIX}/workspaces/{workspace_id}/audit", headers=auth(identity))
    assert response.status_code == 200

    return list(response.json())


# --------------------------------------------------------------- recording --


def test_creating_a_workspace_is_audited(api) -> None:  # noqa: F811
    client, people = api

    created = client.post(
        f"{API_PREFIX}/workspaces", json={"name": "Audited"}, headers=auth(people["owner"])
    ).json()

    entries = trail(client, created["id"], people["owner"])

    assert [entry["action"] for entry in entries] == ["workspace.created"]
    assert entries[0]["actor_id"] == str(people["owner"].user_id)
    assert entries[0]["detail"]["name"] == "Audited"


def test_adding_and_removing_a_member_are_both_audited(api) -> None:  # noqa: F811
    client, people = api
    workspace = people["owner"].workspace_id
    target = people["other"].user_id

    client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(target), "role": "admin"},
        headers=auth(people["owner"]),
    )
    client.delete(
        f"{API_PREFIX}/workspaces/{workspace}/members/{target}", headers=auth(people["owner"])
    )

    entries = trail(client, workspace, people["owner"])
    actions = [entry["action"] for entry in entries]

    assert "member.added" in actions
    assert "member.removed" in actions

    added = next(entry for entry in entries if entry["action"] == "member.added")
    assert added["target_id"] == str(target)
    assert added["detail"]["role"] == "admin"


def test_leaving_and_transferring_ownership_are_audited(api) -> None:  # noqa: F811
    client, people = api
    workspace = people["owner"].workspace_id

    client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(people["other"].user_id)},
        headers=auth(people["owner"]),
    )
    client.post(
        f"{API_PREFIX}/workspaces/{workspace}/ownership",
        json={"successor_id": str(people["other"].user_id)},
        headers=auth(people["owner"]),
    )
    client.post(f"{API_PREFIX}/workspaces/{workspace}/leave", headers=auth(people["owner"]))

    actions = [entry["action"] for entry in trail(client, workspace, people["other"])]

    assert "ownership.transferred" in actions
    assert "member.left" in actions


def test_the_trail_records_who_acted_not_merely_that_something_happened(api) -> None:  # noqa: F811
    """The distinction between an audit log and a request log.

    STEP-12's request logging records that a POST happened. This must record
    *which identity* performed it, including the email they held at the time --
    a point-in-time snapshot rather than a live join, so the record stays
    meaningful after the account changes or goes away.
    """
    client, people = api

    created = client.post(
        f"{API_PREFIX}/workspaces", json={"name": "Attributed"}, headers=auth(people["owner"])
    ).json()

    entry = trail(client, created["id"], people["owner"])[0]

    assert entry["actor_id"] == str(people["owner"].user_id)
    assert entry["actor_email"] == people["owner"].email


def test_a_failed_action_leaves_no_audit_entry(api) -> None:  # noqa: F811
    """Recording happens after the operation commits, never before.

    A refused removal must not appear as though it succeeded -- the trail would
    then claim a member was removed who is still there.
    """
    client, people = api
    workspace = people["owner"].workspace_id

    client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(people["other"].user_id)},
        headers=auth(people["owner"]),
    )

    refused = client.delete(
        f"{API_PREFIX}/workspaces/{workspace}/members/{people['owner'].user_id}",
        headers=auth(people["other"]),
    )
    assert refused.status_code == 403

    removals = [
        entry
        for entry in trail(client, workspace, people["owner"])
        if entry["action"] == "member.removed"
    ]

    assert removals == []


# ------------------------------------------------------------- containment --


def test_an_outsider_cannot_read_the_trail(api) -> None:  # noqa: F811
    client, people = api

    response = client.get(
        f"{API_PREFIX}/workspaces/{people['owner'].workspace_id}/audit",
        headers=auth(people["outsider"]),
    )

    assert response.status_code == 403


def test_the_trail_of_another_workspace_is_not_visible(api) -> None:  # noqa: F811
    """`audit_log_select_same_workspace`, proven rather than assumed.

    An audit log readable across tenant boundaries would disclose exactly the
    actions most worth keeping private.
    """
    client, people = api

    outsider_workspace = client.post(
        f"{API_PREFIX}/workspaces", json={"name": "Theirs"}, headers=auth(people["outsider"])
    ).json()["id"]

    response = client.get(
        f"{API_PREFIX}/workspaces/{outsider_workspace}/audit", headers=auth(people["owner"])
    )

    assert response.status_code == 403


# ------------------------------------------------------------ immutability --


@pytest.fixture
def as_member(request_database_url: str) -> Iterator[psycopg.Connection]:
    """A connection acting as `authenticated`, the way a request does."""
    connection = psycopg.connect(request_database_url, autocommit=True)

    yield connection

    connection.close()


def _act_as(connection: psycopg.Connection, user_id: uuid.UUID) -> None:
    """Bind an identity to the connection."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('request.jwt.claim.sub', %s, false)", (str(user_id),))
        cursor.execute("SET ROLE authenticated")


def test_a_client_cannot_write_its_own_audit_rows(
    api,  # noqa: F811
    as_member: psycopg.Connection,
) -> None:
    """No INSERT policy and no INSERT grant.

    A client able to write audit rows could forge them, which is worse than
    having no audit log at all: a forged trail is trusted.
    """
    client, people = api
    _act_as(as_member, people["owner"].user_id)

    with pytest.raises((psycopg.errors.InsufficientPrivilege, psycopg.errors.SyntaxError)):
        with as_member.cursor() as cursor:
            cursor.execute(
                "INSERT INTO public.audit_log (workspace_id, actor_id, action) "
                "VALUES (%s, %s, 'member.removed')",
                (people["owner"].workspace_id, people["owner"].user_id),
            )


def test_a_client_cannot_edit_an_audit_row(
    api,  # noqa: F811
    as_member: psycopg.Connection,
) -> None:
    """No UPDATE policy and no UPDATE grant."""
    client, people = api
    client.post(
        f"{API_PREFIX}/workspaces/{people['owner'].workspace_id}/members",
        json={"user_id": str(people["other"].user_id)},
        headers=auth(people["owner"]),
    )

    _act_as(as_member, people["owner"].user_id)

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with as_member.cursor() as cursor:
            cursor.execute("UPDATE public.audit_log SET action = 'member.left'")


def test_a_client_cannot_delete_or_truncate_the_trail(
    api,  # noqa: F811
    as_member: psycopg.Connection,
) -> None:
    """TRUNCATE matters most: it is not subject to RLS at all.

    A role holding it could empty this table regardless of every policy on it,
    which is why the grant is revoked explicitly rather than left to a default.
    """
    client, people = api
    _act_as(as_member, people["owner"].user_id)

    for statement in (
        "DELETE FROM public.audit_log",
        "TRUNCATE public.audit_log",
    ):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with as_member.cursor() as cursor:
                cursor.execute(statement)


def test_erasing_a_workspace_does_not_erase_its_audit_trail(api) -> None:  # noqa: F811
    """CLAUDE.md §16: audit logs survive the events they record.

    Otherwise anyone holding `DELETE_WORKSPACE` could destroy the evidence of
    what they did on the way out -- the single outcome an audit log exists to
    prevent. The erasure response reports `audit_log: 0`, which discloses the
    retention exception rather than hiding it.
    """
    client, people = api
    workspace = people["owner"].workspace_id

    client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(people["other"].user_id)},
        headers=auth(people["owner"]),
    )

    before = len(trail(client, workspace, people["owner"]))
    assert before > 0

    erased = client.delete(
        f"{API_PREFIX}/workspaces/{workspace}/data", headers=auth(people["owner"])
    )
    assert erased.status_code == 200
    assert erased.json()["erased"]["audit_log"] == 0

    assert len(trail(client, workspace, people["owner"])) == before


def test_the_trail_appears_in_a_workspace_export(api) -> None:  # noqa: F811
    """Exportable even though it is not erasable.

    A user is entitled to a copy of the record of what was done in their
    workspace; retention and portability are different obligations.
    """
    client, people = api
    workspace = people["owner"].workspace_id

    client.post(
        f"{API_PREFIX}/workspaces/{workspace}/members",
        json={"user_id": str(people["other"].user_id)},
        headers=auth(people["owner"]),
    )

    export = client.get(
        f"{API_PREFIX}/workspaces/{workspace}/export", headers=auth(people["owner"])
    ).json()

    assert "audit_log" in export["stores"]
    assert any(record["action"] == "member.added" for record in export["stores"]["audit_log"])
