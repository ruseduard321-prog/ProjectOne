"""The membership service layer (STEP-11a).

`test_membership_rules.py` proves the *database* enforces the owner's rules.
This proves the service above them turns each refusal into the right answer,
which is the whole reason that layer exists ([[Authorization Model]]): without
it, every violation surfaces as a silently-zero-row `UPDATE` or a raw PostgreSQL
constraint error, and a client can act on neither.

**No endpoints are exercised here, deliberately.** Membership routes belong to
STEP-13; adding them now would be scope creep ([[CLAUDE|CLAUDE.md]] §29/§35).
The service is driven directly over a real RLS-subject connection, so the
policies and the trigger are genuinely in play.

The distinction under test throughout is **403 versus 409**:

- **403** — the caller's role does not permit the act.
- **409** — the caller's role permits it and the workspace's state does not.
  An owner leaving holds `LEAVE_WORKSPACE`; what stops them is being the last
  owner, which no amount of re-authenticating would change.
"""

import uuid
from collections.abc import Iterator

import psycopg
import pytest

from app.core.security import AuthorizationError, LastOwnerError, WorkspaceAccessError
from app.repositories.memberships import MembershipRepository
from app.services.authorization_service import AuthorizationService
from app.services.membership_service import MembershipService
from tests.conftest import Identity, seed_identity
from tests.test_membership_rules import live_role

pytestmark = pytest.mark.usefixtures("migrated_database")


class Cast:
    """An owner, an admin and a member sharing one workspace."""

    def __init__(self, owner: Identity, admin: Identity, member: Identity) -> None:
        """Record the identities and the workspace they share."""
        self.owner = owner
        self.admin = admin
        self.member = member
        self.id = owner.workspace_id


@pytest.fixture
def cast(admin_connection: psycopg.Connection) -> Iterator[Cast]:
    """Seed one workspace holding all three roles."""
    owner = seed_identity(admin_connection, "svc-owner")
    admin = seed_identity(admin_connection, "svc-admin")
    member = seed_identity(admin_connection, "svc-member")

    with admin_connection.cursor() as cursor:
        for identity, role in ((admin, "admin"), (member, "member")):
            cursor.execute(
                "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
                "VALUES (%s, %s, %s)",
                (owner.workspace_id, identity.user_id, role),
            )

    yield Cast(owner, admin, member)


@pytest.fixture
def service_for(request_database_url: str) -> Iterator[object]:
    """Return a factory building the service as one user, over a real connection.

    `request_database_url` connects as `projectone_api` -- the role the API
    genuinely uses, with no `rolbypassrls`. A service built over the owner
    connection would pass every test here while proving nothing about RLS.
    """
    connections: list[psycopg.Connection] = []

    def build(user_id: uuid.UUID) -> MembershipService:
        # `autocommit` so each service call lands immediately, the way a real
        # request's transaction does when it commits. Without it psycopg holds an
        # implicit transaction open and every write is rolled back at close --
        # the assertions then read the pre-call state and fail for a reason that
        # has nothing to do with the rule under test.
        #
        # The role and claim are therefore set with `is_local => false`: there is
        # no surrounding transaction for `SET LOCAL` to scope them to, and a
        # session-scoped claim is safe here because this connection serves
        # exactly one identity and is closed at teardown. Production must never
        # do this -- see `RequestSessionFactory`, where a session-scoped claim on
        # a *pooled* connection is the cross-tenant leak STEP-10 reproduced.
        connection = psycopg.connect(request_database_url, autocommit=True)
        connections.append(connection)

        cursor = connection.cursor()
        cursor.execute("SELECT set_config('request.jwt.claim.sub', %s, false)", (str(user_id),))
        cursor.execute("SET ROLE authenticated")

        repository = MembershipRepository(connection)

        return MembershipService(repository, AuthorizationService(repository))

    yield build

    for connection in connections:
        connection.close()


# ------------------------------------------------------------------ removal --


def test_an_owner_removing_an_admin_succeeds(
    admin_connection: psycopg.Connection, cast: Cast, service_for
) -> None:
    service = service_for(cast.owner.user_id)
    service.remove_member(cast.id, cast.owner.user_id, cast.admin.user_id)

    assert live_role(admin_connection, cast.id, cast.admin.user_id) is None


def test_an_admin_removing_a_member_succeeds(
    admin_connection: psycopg.Connection, cast: Cast, service_for
) -> None:
    service = service_for(cast.admin.user_id)
    service.remove_member(cast.id, cast.admin.user_id, cast.member.user_id)

    assert live_role(admin_connection, cast.id, cast.member.user_id) is None


def test_an_admin_removing_an_owner_is_an_authorization_error(
    admin_connection: psycopg.Connection, cast: Cast, service_for
) -> None:
    """403, not a silent no-op -- the difference the service layer exists for."""
    service = service_for(cast.admin.user_id)

    with pytest.raises(AuthorizationError):
        service.remove_member(cast.id, cast.admin.user_id, cast.owner.user_id)

    assert live_role(admin_connection, cast.id, cast.owner.user_id) == "owner"


def test_a_member_removing_anyone_is_an_authorization_error(cast: Cast, service_for) -> None:
    service = service_for(cast.member.user_id)

    with pytest.raises(AuthorizationError):
        service.remove_member(cast.id, cast.member.user_id, cast.admin.user_id)


def test_removing_yourself_is_refused_and_points_at_leaving(cast: Cast, service_for) -> None:
    """Self-removal must not route through the ranked comparison.

    If it did, the strict `>` would compare a role against itself and refuse --
    correct by accident. Worse, relaxing it to `>=` to "fix" that would let an
    owner remove a co-owner, which the rules forbid. Leaving is its own act.
    """
    service = service_for(cast.owner.user_id)

    with pytest.raises(AuthorizationError):
        service.remove_member(cast.id, cast.owner.user_id, cast.owner.user_id)


def test_removing_a_non_member_does_not_reveal_that_they_are_absent(
    cast: Cast, service_for
) -> None:
    """An authorization error, not a 404.

    A distinct "no such member" answers a question about someone else's
    membership of a workspace the caller cannot see into.
    """
    service = service_for(cast.owner.user_id)

    with pytest.raises(AuthorizationError):
        service.remove_member(cast.id, cast.owner.user_id, uuid.uuid4())


# ------------------------------------------------------------------ leaving --


def test_a_member_may_leave(admin_connection: psycopg.Connection, cast: Cast, service_for) -> None:
    service = service_for(cast.member.user_id)
    service.leave_workspace(cast.id, cast.member.user_id)

    assert live_role(admin_connection, cast.id, cast.member.user_id) is None


def test_the_last_owner_leaving_is_a_conflict_not_a_permission_failure(
    admin_connection: psycopg.Connection, cast: Cast, service_for
) -> None:
    """The 403/409 distinction, which is the point of `LastOwnerError`.

    The owner holds `LEAVE_WORKSPACE`. Answering 403 would send them hunting for
    a permission problem that does not exist; 409 tells them the truth, and the
    message names transferring ownership as the remedy.
    """
    service = service_for(cast.owner.user_id)

    with pytest.raises(LastOwnerError) as raised:
        service.leave_workspace(cast.id, cast.owner.user_id)

    assert not isinstance(raised.value, AuthorizationError)
    assert "Transfer ownership" in raised.value.public_message
    assert live_role(admin_connection, cast.id, cast.owner.user_id) == "owner"


def test_a_non_member_cannot_leave_a_workspace_they_are_not_in(cast: Cast, service_for) -> None:
    stranger = uuid.uuid4()
    service = service_for(stranger)

    with pytest.raises(WorkspaceAccessError):
        service.leave_workspace(cast.id, stranger)


# ---------------------------------------------------------------- transfer --


def test_an_owner_may_transfer_ownership_and_then_leave(
    admin_connection: psycopg.Connection, cast: Cast, service_for
) -> None:
    """Rule 3 end to end, which is the sequence the rule was written to enable."""
    service = service_for(cast.owner.user_id)
    service.transfer_ownership(cast.id, cast.owner.user_id, cast.admin.user_id)

    assert live_role(admin_connection, cast.id, cast.admin.user_id) == "owner"
    assert live_role(admin_connection, cast.id, cast.owner.user_id) == "admin"

    # The departure that was a 409 a moment ago now succeeds, because a second
    # owner exists. This is what "transfer before leaving" means in practice.
    service.leave_workspace(cast.id, cast.owner.user_id)

    assert live_role(admin_connection, cast.id, cast.owner.user_id) is None


def test_an_admin_may_not_transfer_ownership(cast: Cast, service_for) -> None:
    """Owner-only, or an admin could manufacture themselves an owner."""
    service = service_for(cast.admin.user_id)

    with pytest.raises(AuthorizationError):
        service.transfer_ownership(cast.id, cast.admin.user_id, cast.member.user_id)


def test_transferring_to_a_non_member_is_refused(cast: Cast, service_for) -> None:
    """Ownership cannot be handed to someone outside the workspace."""
    service = service_for(cast.owner.user_id)

    with pytest.raises(AuthorizationError):
        service.transfer_ownership(cast.id, cast.owner.user_id, uuid.uuid4())


def test_transferring_to_yourself_is_refused(cast: Cast, service_for) -> None:
    """A no-op dressed as a transfer, and the kind that hides a UI bug."""
    service = service_for(cast.owner.user_id)

    with pytest.raises(AuthorizationError):
        service.transfer_ownership(cast.id, cast.owner.user_id, cast.owner.user_id)


def test_a_transfer_never_leaves_the_workspace_without_an_owner(
    admin_connection: psycopg.Connection, cast: Cast, service_for
) -> None:
    """The invariant the whole step protects, asserted after the fact.

    The transfer runs as two statements inside one transaction. The deferrable
    trigger permits the momentary two-owner state between them and would still
    catch an ownerless one at commit.
    """
    service = service_for(cast.owner.user_id)
    service.transfer_ownership(cast.id, cast.owner.user_id, cast.member.user_id)

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM public.workspace_members "
            "WHERE workspace_id = %s AND role = 'owner' AND deleted_at IS NULL",
            (cast.id,),
        )
        owners = cursor.fetchone()

    assert owners is not None
    assert owners[0] == 1


def test_the_service_agrees_with_the_database(
    admin_connection: psycopg.Connection, cast: Cast, service_for
) -> None:
    """The two layers must refuse the same things.

    A service that permitted what the policy denies would produce a 200 over an
    `UPDATE` that changed nothing -- the exact failure the second layer exists
    to prevent. Asserted by having the service perform an act the policy forbids
    and observing it refuse *before* reaching the database.
    """
    service = service_for(cast.member.user_id)

    with pytest.raises(AuthorizationError):
        service.remove_member(cast.id, cast.member.user_id, cast.owner.user_id)

    # And the reverse: what the service permits, the database performs.
    owner_service = service_for(cast.owner.user_id)
    owner_service.remove_member(cast.id, cast.owner.user_id, cast.member.user_id)

    assert live_role(admin_connection, cast.id, cast.member.user_id) is None


def test_a_removed_member_cannot_act_on_their_next_request(
    admin_connection: psycopg.Connection, cast: Cast, service_for
) -> None:
    """Removal takes effect immediately, exactly like a demotion.

    The invalidation window [[Authorization Model]] documents is one request,
    and it must hold for removal as much as for a role change -- a removed
    member whose token is still valid must not keep acting until it expires.
    """
    owner_service = service_for(cast.owner.user_id)
    owner_service.remove_member(cast.id, cast.owner.user_id, cast.admin.user_id)

    # A fresh connection, standing in for the removed member's next request.
    removed_service = service_for(cast.admin.user_id)

    with pytest.raises(WorkspaceAccessError):
        removed_service.leave_workspace(cast.id, cast.admin.user_id)
