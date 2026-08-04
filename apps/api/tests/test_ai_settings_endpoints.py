"""The AI settings endpoints, through the HTTP layer (STEP-19).

These are the first routes that reach the AI layer at all, so the bar is the
higher one the step note names. Every test here drives a **real HTTP request over
a real database**, as `test_authorization_api.py` does, with only token
verification substituted -- there is no Supabase in CI to mint a token, and
minting one is not what is under test.

## What these prove that a unit test could not

- **A role check that is missing from a route.** The RLS policies would still
  refuse the write, so a policy test passes while the endpoint answers 200 (or
  404) for an operation that silently did nothing. Only an HTTP-layer assertion
  distinguishes "refused" from "refused honestly".
- **A column-level grant.** `spent_usd` being unwritable is a property of the
  PostgreSQL grant added by `c9d3b71e08af`, and no fake can demonstrate it.
- **That no route returns key material.** Asserted by scanning the actual
  response bodies for the submitted key -- the [[STEP-16a Developer Session
  Inspector]] standard, where the proof is a grep against real output rather
  than a reading of the serializer.
"""

import uuid
from collections.abc import Iterator
from decimal import Decimal

import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Environment, Settings, get_settings
from app.core.dependencies import get_database_repository, get_token_service
from app.main import create_app
from app.services.token_service import AuthenticatedUser
from tests.conftest import TEST_BYOK_KEY, Identity, seed_identity
from tests.test_authorization_api import Roles, TokenTable
from tests.test_health import StubDatabase

pytestmark = pytest.mark.usefixtures("migrated_database")

#: A key-shaped value used across these tests.
#:
#: Deliberately distinctive rather than realistic: every leak assertion below
#: scans a response body for this exact string, and a value that could plausibly
#: occur in ordinary output would make a passing scan meaningless.
SUBMITTED_KEY = "sk-test-UNIQUEMARKER-abcdefghijklmnop-9999"


@pytest.fixture
def roles(admin_connection: psycopg.Connection) -> Iterator[Roles]:
    """Seed one workspace containing an owner, an admin and a plain member."""
    owner = seed_identity(admin_connection, "ai-owner")
    admin = seed_identity(admin_connection, "ai-admin")
    member = seed_identity(admin_connection, "ai-member")

    with admin_connection.cursor() as cursor:
        for identity, role in ((admin, "admin"), (member, "member")):
            cursor.execute(
                "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
                "VALUES (%s, %s, %s)",
                (owner.workspace_id, identity.user_id, role),
            )

    yield Roles(owner, admin, member)


@pytest.fixture
def outsider(admin_connection: psycopg.Connection) -> Identity:
    """A user in a different workspace entirely, for the cross-tenant tests."""
    return seed_identity(admin_connection, "ai-outsider")


@pytest.fixture
def client(
    roles: Roles,
    outsider: Identity,
    migrated_database: str,
    request_database_url: str,
) -> Iterator[TestClient]:
    """Return a client backed by the real test database.

    **The two DSNs are deliberately different, exactly as they are in
    production.** `REQUEST_DATABASE_URL` connects as `projectone_api`, the role a
    real request uses, which has no `rolbypassrls`; `DATABASE_URL` connects as
    the owner, which is the privileged path `AISpendRepository` opens for the
    reserve/settle methods that must maintain `spent_usd`.

    An earlier version of this fixture pointed *both* at `projectone_api`,
    reasoning that a stricter privileged role would make the `spent_usd` grant
    test more meaningful. That was wrong in a way only a real database revealed:
    it also stripped the privileged path of the rights it legitimately needs, so
    `PUT .../ai/budgets` failed with `permission denied for table ai_budgets` --
    the route was refused by the very grant that is supposed to constrain only
    the tenant connection.

    The grant tests lose nothing by this. They do not rely on the fixture's
    privileged DSN at all: `test_an_owner_cannot_write_spent_usd_over_the_request_connection`
    and `test_the_granted_columns_are_still_writable` each open their own
    connection to `request_database_url` and `SET LOCAL ROLE authenticated`,
    which is a more faithful reproduction of a route's connection than
    borrowing the fixture's would have been.
    """

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

    tokens = TokenTable(
        {
            f"token-{identity.user_id}": AuthenticatedUser(id=identity.user_id, email=None)
            for identity in (roles.owner, roles.admin, roles.member, outsider)
        }
    )

    app = create_app()
    app.dependency_overrides[get_settings] = settings
    app.dependency_overrides[get_database_repository] = lambda: StubDatabase(reachable=True)
    app.dependency_overrides[get_token_service] = lambda: tokens

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def _providers_url(workspace_id: uuid.UUID, provider: str = "") -> str:
    """Return the provider credential URL, optionally for one provider."""
    base = f"/api/v1/workspaces/{workspace_id}/ai/providers"

    return f"{base}/{provider}" if provider else base


# ---------------------------------------------------------------------------
# No route returns key material
# ---------------------------------------------------------------------------


def test_no_route_returns_a_stored_key(client: TestClient, roles: Roles) -> None:
    """The step's central validation, proven by grep against real responses.

    Reading the serializer would show that `ProviderCredentialResponse` has no
    field for a key. That is the design; this is the evidence. The key is stored
    and then every route that could plausibly carry it is fetched and its raw
    body scanned -- including the store response itself, which is the one place a
    well-meaning implementation would echo the value back.

    The scan checks the **whole body text**, not parsed fields: a key leaking
    through an error message, a debug field or a serialized nested object would
    pass a field-by-field check and fail this one.
    """
    stored = client.put(
        _providers_url(roles.workspace_id, "openai"),
        json={"api_key": SUBMITTED_KEY},
        headers=roles.token_for(roles.owner),
    )

    assert stored.status_code == 200
    assert SUBMITTED_KEY not in stored.text

    # `last_four` is present and correct, so the scan above is not passing
    # against an error response that happens to contain no key.
    assert stored.json()["last_four"] == SUBMITTED_KEY[-4:]

    for response in (
        client.get(_providers_url(roles.workspace_id), headers=roles.token_for(roles.owner)),
        client.get(
            f"/api/v1/workspaces/{roles.workspace_id}/export",
            headers=roles.token_for(roles.owner),
        ),
        client.get(
            f"/api/v1/workspaces/{roles.workspace_id}/audit",
            headers=roles.token_for(roles.owner),
        ),
    ):
        assert response.status_code == 200
        assert SUBMITTED_KEY not in response.text

        # Nor any substring long enough to be useful. A response leaking half a
        # key is still a response leaking a key, and an exact-match scan would
        # pass straight through a truncated one.
        assert SUBMITTED_KEY[:20] not in response.text


def test_the_audit_trail_does_not_record_the_key_or_its_last_four(
    client: TestClient, roles: Roles
) -> None:
    """An audit row is readable by every member, including a plain one.

    So it must record *that* a key was stored and not *which* key -- four
    characters of a credential in a widely-readable table is a leak that took one
    extra step rather than none.
    """
    client.put(
        _providers_url(roles.workspace_id, "openai"),
        json={"api_key": SUBMITTED_KEY},
        headers=roles.token_for(roles.owner),
    )

    response = client.get(
        f"/api/v1/workspaces/{roles.workspace_id}/audit",
        headers=roles.token_for(roles.member),
    )

    assert response.status_code == 200

    actions = [record["action"] for record in response.json()]
    assert "provider_key.stored" in actions
    assert SUBMITTED_KEY[-4:] not in response.text


# ---------------------------------------------------------------------------
# Roles: provider credentials
# ---------------------------------------------------------------------------


def test_a_member_cannot_store_a_provider_key(client: TestClient, roles: Roles) -> None:
    """403, not a silent no-op.

    The RLS policy would refuse the INSERT anyway. Without the `requires(...)`
    dependency that refusal surfaces as a database error or an unaffected row,
    neither of which tells the caller the truth.
    """
    response = client.put(
        _providers_url(roles.workspace_id, "openai"),
        json={"api_key": SUBMITTED_KEY},
        headers=roles.token_for(roles.member),
    )

    assert response.status_code == 403


def test_a_member_cannot_replace_an_existing_provider_key(client: TestClient, roles: Roles) -> None:
    """Replacement is the same route, and must be refused on an existing key too.

    Worth asserting separately: `store` soft-deletes then inserts, so a
    permission gap here would let a member destroy a working credential even if
    their own insert then failed.
    """
    client.put(
        _providers_url(roles.workspace_id, "openai"),
        json={"api_key": SUBMITTED_KEY},
        headers=roles.token_for(roles.owner),
    )

    response = client.put(
        _providers_url(roles.workspace_id, "openai"),
        json={"api_key": "sk-replacement-key-attempt-0000"},
        headers=roles.token_for(roles.member),
    )

    assert response.status_code == 403

    # And the original survives, which is the property that actually matters.
    listed = client.get(_providers_url(roles.workspace_id), headers=roles.token_for(roles.owner))
    assert listed.json()[0]["last_four"] == SUBMITTED_KEY[-4:]


def test_a_member_cannot_revoke_a_provider_key(client: TestClient, roles: Roles) -> None:
    client.put(
        _providers_url(roles.workspace_id, "openai"),
        json={"api_key": SUBMITTED_KEY},
        headers=roles.token_for(roles.owner),
    )

    response = client.delete(
        _providers_url(roles.workspace_id, "openai"),
        headers=roles.token_for(roles.member),
    )

    assert response.status_code == 403


def test_a_member_can_read_which_providers_are_configured(client: TestClient, roles: Roles) -> None:
    """The permission half of the asymmetry.

    Without this, a check that refused everyone would pass every test above. A
    member needs to know whether the workspace can make AI calls at all -- and
    the response carries no secret.
    """
    client.put(
        _providers_url(roles.workspace_id, "openai"),
        json={"api_key": SUBMITTED_KEY},
        headers=roles.token_for(roles.owner),
    )

    response = client.get(
        _providers_url(roles.workspace_id),
        headers=roles.token_for(roles.member),
    )

    assert response.status_code == 200
    assert [entry["provider"] for entry in response.json()] == ["openai"]


def test_an_admin_can_store_and_revoke_a_provider_key(client: TestClient, roles: Roles) -> None:
    """`admin` holds UPDATE_WORKSPACE, so both writes must succeed for them."""
    stored = client.put(
        _providers_url(roles.workspace_id, "anthropic"),
        json={"api_key": SUBMITTED_KEY},
        headers=roles.token_for(roles.admin),
    )
    assert stored.status_code == 200

    revoked = client.delete(
        _providers_url(roles.workspace_id, "anthropic"),
        headers=roles.token_for(roles.admin),
    )
    assert revoked.status_code == 204

    listed = client.get(_providers_url(roles.workspace_id), headers=roles.token_for(roles.admin))
    assert listed.json() == []


def test_revoking_a_key_is_possible_at_all(client: TestClient, roles: Roles) -> None:
    """Regression: revocation was refused for **every role** until STEP-19.

    `provider_credentials_select_same_workspace` filtered `deleted_at IS NULL`,
    and a soft delete produces a row that policy no longer matches — so
    PostgreSQL refused the UPDATE with a *row-level security* error, from the
    policy governing reads rather than the one governing writes. Migration
    `d1f70a4c62be` moves the liveness filter into the queries, the fix
    [[STEP-11a Membership Removal Policy]] established for the identical defect
    on `workspace_members`.

    Nothing caught it because nothing had ever revoked a key: the repository
    method was unit-tested against a fake and had never run against PostgreSQL.
    The same refusal also broke **workspace data erasure**, which soft-deletes
    this table (`ProviderCredentialStore.erase`) — a CLAUDE.md §16 obligation
    that was silently failing.
    """
    client.put(
        _providers_url(roles.workspace_id, "openai"),
        json={"api_key": SUBMITTED_KEY},
        headers=roles.token_for(roles.owner),
    )

    revoked = client.delete(
        _providers_url(roles.workspace_id, "openai"),
        headers=roles.token_for(roles.owner),
    )

    assert revoked.status_code == 204

    # The revoked row is gone from the listing, which is what proves the query's
    # own `deleted_at IS NULL` still filters now that the policy does not.
    listed = client.get(_providers_url(roles.workspace_id), headers=roles.token_for(roles.owner))
    assert listed.json() == []


def test_erasing_a_workspace_removes_its_provider_keys(client: TestClient, roles: Roles) -> None:
    """The other path the revocation defect broke.

    Erasure soft-deletes `provider_credentials`, so it hit the same refusal —
    and a workspace erasure that leaves provider keys behind is a CLAUDE.md §16
    violation, not merely a broken button.
    """
    client.put(
        _providers_url(roles.workspace_id, "openai"),
        json={"api_key": SUBMITTED_KEY},
        headers=roles.token_for(roles.owner),
    )

    erased = client.delete(
        f"/api/v1/workspaces/{roles.workspace_id}/data",
        headers=roles.token_for(roles.owner),
    )

    assert erased.status_code == 200
    assert erased.json()["erased"]["provider_credentials"] == 1


def test_revoking_a_key_that_is_not_stored_is_a_404(client: TestClient, roles: Roles) -> None:
    """A false confirmation is worse than an error for a security action."""
    response = client.delete(
        _providers_url(roles.workspace_id, "openai"),
        headers=roles.token_for(roles.owner),
    )

    assert response.status_code == 404


def test_an_unknown_provider_is_rejected(client: TestClient, roles: Roles) -> None:
    """422 rather than a stored credential for a provider that cannot be used.

    Without the constraint the row would be written, the settings screen would
    show the provider as configured, and the failure would surface only when an
    AI call was finally attempted -- far from the mistake that caused it.
    """
    response = client.put(
        _providers_url(roles.workspace_id, "not-a-provider"),
        json={"api_key": SUBMITTED_KEY},
        headers=roles.token_for(roles.owner),
    )

    assert response.status_code == 422


def test_an_implausibly_short_key_is_rejected_before_anything_is_written(
    client: TestClient, roles: Roles
) -> None:
    """A typo must not replace a working credential."""
    client.put(
        _providers_url(roles.workspace_id, "openai"),
        json={"api_key": SUBMITTED_KEY},
        headers=roles.token_for(roles.owner),
    )

    response = client.put(
        _providers_url(roles.workspace_id, "openai"),
        json={"api_key": "short"},
        headers=roles.token_for(roles.owner),
    )

    assert response.status_code == 422

    listed = client.get(_providers_url(roles.workspace_id), headers=roles.token_for(roles.owner))
    assert listed.json()[0]["last_four"] == SUBMITTED_KEY[-4:]


# ---------------------------------------------------------------------------
# Roles: budgets
# ---------------------------------------------------------------------------


def test_a_member_cannot_change_a_budget(client: TestClient, roles: Roles) -> None:
    response = client.put(
        f"/api/v1/workspaces/{roles.workspace_id}/ai/budgets",
        json={"limit_usd": "500.00"},
        headers=roles.token_for(roles.member),
    )

    assert response.status_code == 403


def test_raising_a_ceiling_does_not_reset_the_billing_period(
    client: TestClient, roles: Roles
) -> None:
    """Regression: STEP-19 found this by running the route, not by review.

    `AISpendRepository.upsert_budget` collapsed an unstated period to a 30-day
    default and **wrote it**, so raising a ceiling on a budget configured with a
    7-day period silently reset it to 30. An edit about one field must not change
    billing behaviour on another.

    The failure was invisible from the response, which is what makes it worth a
    named test: the endpoint reported `period_days: 30` and was telling the
    truth about what had just been written.
    """
    client.put(
        f"/api/v1/workspaces/{roles.workspace_id}/ai/budgets",
        json={"limit_usd": "100.00", "period_days": 7},
        headers=roles.token_for(roles.owner),
    )

    response = client.put(
        f"/api/v1/workspaces/{roles.workspace_id}/ai/budgets",
        json={"limit_usd": "250.00"},
        headers=roles.token_for(roles.owner),
    )

    assert response.json()["period_days"] == 7

    # And an explicitly stated period still changes it, so the fix narrowed the
    # behaviour rather than freezing the field.
    changed = client.put(
        f"/api/v1/workspaces/{roles.workspace_id}/ai/budgets",
        json={"limit_usd": "250.00", "period_days": 14},
        headers=roles.token_for(roles.owner),
    )

    assert changed.json()["period_days"] == 14


def test_a_member_can_read_a_budget(client: TestClient, roles: Roles) -> None:
    """The deliberate asymmetry, and both halves need asserting.

    A tripped ceiling has to be explainable to the person whose request it
    refused. A refusal they cannot investigate is exactly the silent failure
    CLAUDE.md §15a's graceful-degradation rule exists to prevent.
    """
    client.put(
        f"/api/v1/workspaces/{roles.workspace_id}/ai/budgets",
        json={"limit_usd": "500.00", "period_days": 30},
        headers=roles.token_for(roles.owner),
    )

    response = client.get(
        f"/api/v1/workspaces/{roles.workspace_id}/ai/budgets",
        headers=roles.token_for(roles.member),
    )

    assert response.status_code == 200

    budget = response.json()[0]
    assert Decimal(budget["limit_usd"]) == Decimal("500.00")
    assert budget["period_days"] == 30
    assert budget["breaker_open"] is False


def test_an_owner_can_raise_a_ceiling_and_the_response_reflects_stored_state(
    client: TestClient, roles: Roles
) -> None:
    """The response is read back from the database, not echoed from the request.

    `spent_usd` and `period_started_at` were never in the request body, so a
    handler that echoed its input could not produce them.
    """
    client.put(
        f"/api/v1/workspaces/{roles.workspace_id}/ai/budgets",
        json={"limit_usd": "100.00", "period_days": 7},
        headers=roles.token_for(roles.owner),
    )

    response = client.put(
        f"/api/v1/workspaces/{roles.workspace_id}/ai/budgets",
        json={"limit_usd": "250.00"},
        headers=roles.token_for(roles.owner),
    )

    assert response.status_code == 200

    body = response.json()
    assert Decimal(body["limit_usd"]) == Decimal("250.00")
    assert Decimal(body["spent_usd"]) == Decimal(0)
    assert body["period_started_at"] != ""

    # Omitting `period_days` left the stored interval untouched rather than
    # resetting it to the 30-day default -- an edit about one field must not
    # silently change billing behaviour on another.
    assert body["period_days"] == 7


# ---------------------------------------------------------------------------
# `spent_usd` is unwritable, by every mechanism
# ---------------------------------------------------------------------------


def test_the_budget_route_rejects_spent_usd_outright(client: TestClient, roles: Roles) -> None:
    """422, not a silent discard.

    `extra="forbid"` is what makes this a rejection rather than a no-op, and the
    difference is not cosmetic: a discarded field is indistinguishable from an
    accepted one to whoever sent it, so a client could believe it had zeroed a
    running total that never moved.
    """
    client.put(
        f"/api/v1/workspaces/{roles.workspace_id}/ai/budgets",
        json={"limit_usd": "100.00"},
        headers=roles.token_for(roles.owner),
    )

    response = client.put(
        f"/api/v1/workspaces/{roles.workspace_id}/ai/budgets",
        json={"limit_usd": "100.00", "spent_usd": "0"},
        headers=roles.token_for(roles.owner),
    )

    assert response.status_code == 422


def test_an_owner_cannot_write_spent_usd_over_the_request_connection(
    client: TestClient,
    roles: Roles,
    admin_connection: psycopg.Connection,
    request_database_url: str,
) -> None:
    """The second, independent gate: the column-level grant.

    This bypasses the API entirely and issues the UPDATE directly as
    `projectone_api` with the owner's identity set -- exactly what a route that
    forgot the schema constraint would do. Migration `c9d3b71e08af` revoked the
    table-wide UPDATE grant, so PostgreSQL refuses before any policy is even
    evaluated.

    **This is the test that closes the exposure STEP-18 recorded**: an owner
    zeroing their own running total would spend without limit while every
    control above continued to report success.
    """
    client.put(
        f"/api/v1/workspaces/{roles.workspace_id}/ai/budgets",
        json={"limit_usd": "100.00"},
        headers=roles.token_for(roles.owner),
    )

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.ai_budgets SET spent_usd = 42 WHERE workspace_id = %s",
            (roles.workspace_id,),
        )

    with psycopg.connect(request_database_url) as connection, connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE authenticated")
        cursor.execute(
            "SELECT set_config('request.jwt.claim.sub', %s, true)",
            (str(roles.owner.user_id),),
        )

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cursor.execute(
                "UPDATE public.ai_budgets SET spent_usd = 0 WHERE workspace_id = %s",
                (roles.workspace_id,),
            )

    # The running total is untouched, which is the outcome rather than the
    # exception type.
    listed = client.get(
        f"/api/v1/workspaces/{roles.workspace_id}/ai/budgets",
        headers=roles.token_for(roles.owner),
    )
    assert Decimal(listed.json()[0]["spent_usd"]) == Decimal(42)


def test_the_granted_columns_are_still_writable(
    roles: Roles,
    request_database_url: str,
    admin_connection: psycopg.Connection,
) -> None:
    """The negative control on the grant: it narrowed, it did not close.

    Without this, a migration that revoked UPDATE and granted nothing back would
    pass the test above while breaking the settings route entirely.

    Also confirms the `touch_row` trigger still maintains `version` -- the
    trigger runs as the table owner rather than as the caller, so narrowing the
    caller's grant does not stop it. Verified rather than assumed.
    """
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.ai_budgets (workspace_id, workflow_type, limit_usd) "
            "VALUES (%s, NULL, 10) RETURNING version",
            (roles.workspace_id,),
        )
        row = cursor.fetchone()
        assert row is not None
        before = row[0]

    with psycopg.connect(request_database_url) as connection, connection.cursor() as cursor:
        cursor.execute("SET LOCAL ROLE authenticated")
        cursor.execute(
            "SELECT set_config('request.jwt.claim.sub', %s, true)",
            (str(roles.owner.user_id),),
        )
        cursor.execute(
            "UPDATE public.ai_budgets SET limit_usd = 99 WHERE workspace_id = %s",
            (roles.workspace_id,),
        )
        assert cursor.rowcount == 1
        connection.commit()

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT limit_usd, version FROM public.ai_budgets WHERE workspace_id = %s",
            (roles.workspace_id,),
        )
        stored = cursor.fetchone()

    assert stored is not None
    assert stored[0] == Decimal(99)
    assert stored[1] == before + 1


# ---------------------------------------------------------------------------
# Cross-tenant isolation
# ---------------------------------------------------------------------------


def test_an_outsider_cannot_read_another_workspaces_providers(
    client: TestClient, roles: Roles, outsider: Identity
) -> None:
    """403 -- never another tenant's data.

    The outsider holds a perfectly valid session and their own workspace, so this
    is not an authentication question. `requires(VIEW_WORKSPACE)` finds no
    membership and refuses.
    """
    client.put(
        _providers_url(roles.workspace_id, "openai"),
        json={"api_key": SUBMITTED_KEY},
        headers=roles.token_for(roles.owner),
    )

    response = client.get(
        _providers_url(roles.workspace_id),
        headers={"Authorization": f"Bearer token-{outsider.user_id}"},
    )

    assert response.status_code == 403
    assert SUBMITTED_KEY not in response.text


def test_an_outsider_cannot_read_another_workspaces_budgets_or_spend(
    client: TestClient, roles: Roles, outsider: Identity
) -> None:
    client.put(
        f"/api/v1/workspaces/{roles.workspace_id}/ai/budgets",
        json={"limit_usd": "100.00"},
        headers=roles.token_for(roles.owner),
    )

    headers = {"Authorization": f"Bearer token-{outsider.user_id}"}

    for path in ("budgets", "spend"):
        response = client.get(
            f"/api/v1/workspaces/{roles.workspace_id}/ai/{path}",
            headers=headers,
        )

        assert response.status_code == 403


def test_an_outsider_cannot_write_another_workspaces_provider_key(
    client: TestClient, roles: Roles, outsider: Identity
) -> None:
    """The write direction of the same boundary.

    Planting a key in someone else's workspace would make that workspace's AI
    calls bill the attacker's provider account -- or, far worse, route the
    workspace's prompts through a provider account the attacker controls.
    """
    response = client.put(
        _providers_url(roles.workspace_id, "openai"),
        json={"api_key": "sk-planted-by-an-outsider-000000"},
        headers={"Authorization": f"Bearer token-{outsider.user_id}"},
    )

    assert response.status_code == 403

    listed = client.get(_providers_url(roles.workspace_id), headers=roles.token_for(roles.owner))
    assert listed.json() == []


# ---------------------------------------------------------------------------
# Spend history
# ---------------------------------------------------------------------------


def test_spend_history_is_readable_by_a_member_and_scoped_to_the_workspace(
    client: TestClient,
    roles: Roles,
    outsider: Identity,
    admin_connection: psycopg.Connection,
) -> None:
    """Two workspaces each hold a record; each sees only its own.

    Seeded directly rather than by making an AI call: this asserts the read path
    and its tenant scoping, and routing it through a live provider would make the
    test depend on a network call it is not about.
    """
    for workspace_id, model in (
        (roles.workspace_id, "gpt-4o-mini"),
        (outsider.workspace_id, "claude-haiku-4-5"),
    ):
        with admin_connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO public.ai_spend_records
                    (workspace_id, provider, model, workflow_type,
                     prompt_tokens, completion_tokens, cost_usd)
                VALUES (%s, 'openai', %s, 'chat', 100, 50, 0.001234)
                """,
                (workspace_id, model),
            )

    response = client.get(
        f"/api/v1/workspaces/{roles.workspace_id}/ai/spend",
        headers=roles.token_for(roles.member),
    )

    assert response.status_code == 200

    records = response.json()
    assert [record["model"] for record in records] == ["gpt-4o-mini"]
    assert records[0]["cost_usd"] == "0.001234"


def test_the_spend_history_limit_is_bounded(client: TestClient, roles: Roles) -> None:
    """An unbounded limit on an append-only table is an invitation."""
    response = client.get(
        f"/api/v1/workspaces/{roles.workspace_id}/ai/spend?limit=5000",
        headers=roles.token_for(roles.owner),
    )

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Governance refusals reach the client correctly
# ---------------------------------------------------------------------------


def test_a_tripped_breaker_is_visible_on_the_budget_screen(
    client: TestClient, roles: Roles, admin_connection: psycopg.Connection
) -> None:
    """An honest refusal names its cause.

    A budget screen showing a ceiling with room, while every call is refused, is
    the silent failure CLAUDE.md §15a forbids. The breaker state and its reason
    are surfaced so the screen can say what is actually happening.
    """
    client.put(
        f"/api/v1/workspaces/{roles.workspace_id}/ai/budgets",
        json={"limit_usd": "100.00"},
        headers=roles.token_for(roles.owner),
    )

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.ai_budgets "
            "SET breaker_tripped_at = now(), breaker_reason = 'Spend anomaly' "
            "WHERE workspace_id = %s",
            (roles.workspace_id,),
        )

    response = client.get(
        f"/api/v1/workspaces/{roles.workspace_id}/ai/budgets",
        headers=roles.token_for(roles.member),
    )

    budget = response.json()[0]
    assert budget["breaker_open"] is True
    assert budget["breaker_reason"] == "Spend anomaly"
