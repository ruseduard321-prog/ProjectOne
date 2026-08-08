"""Workflow runs through the API, over a real database (STEP-22).

`test_workflow_engine.py` proves the *runner* gates and resumes correctly against
a fake repository. That is necessary and not sufficient: this step's Validation
asks questions only a real database and a real route can answer.

1. **Does resumability survive persistence?** The engine tests prove the runner
   reads back what it wrote; these prove the SQL actually writes it -- including
   the upsert on `(run_id, step_index)` that stops a resumed step gaining a
   second row.
2. **Does the approval gate hold through HTTP, with the right role?** A gate the
   runner enforces but the route exposes to any member would be a gate in the
   wrong place.
3. **Can a run cross the tenant boundary?** Asserted against real response
   bodies, not repository returns.
4. **Do the status vocabularies match the CHECK constraints?** The defect
   STEP-21 paid for on `assets.kind`, guarded here at creation time.

The AI provider is substituted -- there is no provider key in CI and calling one
is not what is under test. Everything else is real: real HTTP, real policies,
real rows.
"""

import uuid
from collections.abc import Iterator

import psycopg
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.ai.provider import (
    AIProvider,
    Capability,
    CompletionRequest,
    CompletionResponse,
    TokenUsage,
)
from app.core.config import Environment, Settings, get_settings
from app.core.dependencies import (
    get_ai_providers,
    get_database_repository,
    get_token_service,
)
from app.core.security import InvalidTokenError
from app.core.user_rate_limit import get_user_rate_limiter
from app.main import create_app
from app.services.token_service import AuthenticatedUser
from app.workflows.models import RunStatus, StepStatus
from tests.conftest import TEST_BYOK_KEY, Identity, seed_identity
from tests.test_health import StubDatabase

pytestmark = pytest.mark.usefixtures("migrated_database")

#: An outline long enough to satisfy the planning agent's success criterion.
_OUTLINE = (
    "1. Research the audience\n2. Draft the script\n3. Record and edit\n4. Publish and measure"
)


class StubProvider(AIProvider):
    """A provider that answers without a network call.

    Substituted at `get_ai_providers`, which is the registry every AI path
    resolves through -- so this replaces the provider without touching the
    router, the spend controls, or the credential lookup. All three still run.
    """

    def __init__(self, content: str = _OUTLINE) -> None:
        """Configure what every completion returns."""
        self._content = content
        self.calls = 0

    @property
    def name(self) -> str:
        """Match the real provider's identifier, so stored keys resolve."""
        return "openai"

    @property
    def capabilities(self) -> frozenset[Capability]:
        """Chat completion, like the provider it stands in for."""
        return frozenset({Capability.CHAT_COMPLETION})

    @property
    def cost_per_1k_tokens(self) -> float:
        """A nominal cost, so selection has a number to compare."""
        return 0.001

    def complete(self, request: CompletionRequest, api_key: str) -> CompletionResponse:
        """Return the configured content."""
        self.calls += 1

        return CompletionResponse(
            content=self._content,
            provider=self.name,
            model="stub-model",
            usage=TokenUsage(prompt_tokens=50, completion_tokens=100),
        )


class TokenTable:
    """Maps token strings to identities."""

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
    """One workspace with an owner and a member, plus an unrelated workspace."""

    def __init__(self, owner: Identity, member: Identity, stranger: Identity) -> None:
        """Record the identities and the workspace the first two share."""
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
    owner = seed_identity(admin_connection, "wf-owner")
    member = seed_identity(admin_connection, "wf-member")
    stranger = seed_identity(admin_connection, "wf-stranger")

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO public.workspace_members (workspace_id, user_id, role) "
            "VALUES (%s, %s, 'member')",
            (owner.workspace_id, member.user_id),
        )

    yield Tenants(owner, member, stranger)


@pytest.fixture
def provider() -> StubProvider:
    """Return the substituted provider, so a test can inspect its call count."""
    return StubProvider()


@pytest.fixture
def client(
    tenants: Tenants,
    request_database_url: str,
    provider: StubProvider,
    admin_connection: psycopg.Connection,
) -> Iterator[TestClient]:
    """Return a client backed by the real test database.

    A provider key is seeded for the owner's workspace, because the planning
    agent's call would otherwise be refused with `NoProviderAvailableError`
    before reaching the provider -- which is correct behaviour and not what these
    tests are about.
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
    app.dependency_overrides[get_ai_providers] = lambda: (provider,)

    get_user_rate_limiter().clear()

    with TestClient(app) as test_client:
        # Stored through the API so the key is encrypted by the real cipher --
        # inserting ciphertext by hand would be asserting against a fixture
        # rather than against the path a real workspace uses.
        stored = test_client.put(
            f"/api/v1/workspaces/{tenants.workspace_id}/ai/providers/openai",
            json={"api_key": "sk-test-key-for-workflow-runs"},
            headers=tenants.token_for(tenants.owner),
        )

        assert stored.status_code == 200, stored.text

        yield test_client

    app.dependency_overrides.clear()


def _project(client: TestClient, tenants: Tenants, name: str = "A project") -> str:
    """Create a project and return its id."""
    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/projects",
        json={"name": name, "description": "Something worth planning"},
        headers=tenants.token_for(tenants.owner),
    )

    assert response.status_code == 201, response.text

    return str(response.json()["id"])


def _start(
    client: TestClient,
    tenants: Tenants,
    project_id: str | None,
    actor: Identity | None = None,
) -> dict:
    """Start a project-planning run and return the response body."""
    body: dict[str, object] = {"workflow_type": "project_planning"}

    if project_id is not None:
        body["project_id"] = project_id

    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs",
        json=body,
        headers=tenants.token_for(actor or tenants.owner),
    )

    assert response.status_code == 201, response.text

    return response.json()


# ------------------------------------------------------------ vocabularies --


def test_run_status_vocabulary_matches_the_database(
    client: TestClient, admin_connection: psycopg.Connection
) -> None:
    """`RunStatus` and `ck_workflow_runs_status_valid` must be the same set.

    **This test exists because STEP-21 paid for its absence.** `assets.kind` was
    typed as free text against a CHECK constraint, so the API accepted a value
    PostgreSQL refused -- a client error surfacing as a 500. Asserted against the
    catalog rather than a second literal, because a literal is a third copy that
    drifts like the first two.
    """
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'ck_workflow_runs_status_valid'"
        )
        row = cursor.fetchone()

    assert row is not None, "ck_workflow_runs_status_valid is missing"

    definition = row[0]

    for status in RunStatus:
        assert f"'{status.value}'" in definition, f"{status.value} is not permitted"

    assert definition.count("'") // 2 == len(RunStatus), definition


def test_step_status_vocabulary_matches_the_database(
    client: TestClient, admin_connection: psycopg.Connection
) -> None:
    """The same check for `StepStatus`."""
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'ck_workflow_step_runs_status_valid'"
        )
        row = cursor.fetchone()

    assert row is not None, "ck_workflow_step_runs_status_valid is missing"

    definition = row[0]

    for status in StepStatus:
        assert f"'{status.value}'" in definition, f"{status.value} is not permitted"

    assert definition.count("'") // 2 == len(StepStatus), definition


def test_the_catalog_lists_the_available_workflows(client: TestClient, tenants: Tenants) -> None:
    """A client picker reads this rather than hardcoding names."""
    response = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/catalog",
        headers=tenants.token_for(tenants.member),
    )

    assert response.status_code == 200
    assert response.json()["workflows"] == ["project_planning"]


def test_an_unknown_workflow_is_422(client: TestClient, tenants: Tenants) -> None:
    """A run that could never have formed is a 422, not a 500."""
    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs",
        json={"workflow_type": "not_a_workflow"},
        headers=tenants.token_for(tenants.owner),
    )

    assert response.status_code == 422
    # The message names the valid options: unlike an authorization refusal, this
    # reveals nothing about any tenant.
    assert "project_planning" in response.json()["detail"]


# -------------------------------------------------------- the approval gate --


def test_a_run_stops_at_the_gated_step(client: TestClient, tenants: Tenants) -> None:
    """**The step's headline Validation check, through HTTP and a real database.**

    Validation runs (ungated), planning does not (gated). The provider must not
    have been called at all -- a gate that let the AI call happen and merely
    flagged it would be a gate in name only.
    """
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    assert run["status"] == RunStatus.AWAITING_APPROVAL
    assert run["detail"] is not None
    assert "plan" in run["detail"]

    statuses = {step["step_name"]: step["status"] for step in run["steps"]}

    assert statuses["validate"] == StepStatus.COMPLETED
    assert statuses["plan"] == StepStatus.AWAITING_APPROVAL
    assert "quality_check" not in statuses


def test_the_gated_step_makes_no_provider_call(
    client: TestClient, tenants: Tenants, provider: StubProvider
) -> None:
    """No AI call happens before approval. Money is not spent on an unapproved step."""
    project_id = _project(client, tenants)
    _start(client, tenants, project_id)

    assert provider.calls == 0, "an unapproved step called the provider"


def test_approval_runs_the_gated_step_and_completes_the_run(
    client: TestClient, tenants: Tenants, provider: StubProvider
) -> None:
    """The permission half. Without it, a gate refusing everyone would pass."""
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    approved = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs/{run['id']}/approval",
        headers=tenants.token_for(tenants.owner),
    )

    assert approved.status_code == 200, approved.text

    body = approved.json()

    assert body["status"] == RunStatus.COMPLETED
    assert provider.calls == 1

    statuses = {step["step_name"]: step["status"] for step in body["steps"]}

    assert statuses == {
        "validate": StepStatus.COMPLETED,
        "plan": StepStatus.COMPLETED,
        "quality_check": StepStatus.COMPLETED,
    }


def test_a_member_cannot_approve_a_run(client: TestClient, tenants: Tenants) -> None:
    """**Approval is owner/admin only** — the project owner's decision on 2026-08-08.

    A gated step spends money or acts externally, which is the same class of
    consequence guarding AI keys and spend ceilings. 403, not a silent no-op.
    """
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs/{run['id']}/approval",
        headers=tenants.token_for(tenants.member),
    )

    assert response.status_code == 403


def test_a_refused_approval_leaves_the_run_paused(
    client: TestClient, tenants: Tenants, provider: StubProvider
) -> None:
    """A 403 must not have executed the step anyway.

    The half that matters: a wrong status code with the work performed regardless
    would be the actual defect.
    """
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs/{run['id']}/approval",
        headers=tenants.token_for(tenants.member),
    )

    after = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs/{run['id']}",
        headers=tenants.token_for(tenants.owner),
    )

    assert after.json()["status"] == RunStatus.AWAITING_APPROVAL
    assert provider.calls == 0


def test_a_member_can_start_and_read_a_run(client: TestClient, tenants: Tenants) -> None:
    """Starting is `VIEW_WORKSPACE`: a member who cannot run a workflow on their
    own project cannot use the product. Only *approval* is narrower.
    """
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id, actor=tenants.member)

    read = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs/{run['id']}",
        headers=tenants.token_for(tenants.member),
    )

    assert read.status_code == 200


def test_resuming_does_not_clear_the_approval_gate(
    client: TestClient, tenants: Tenants, provider: StubProvider
) -> None:
    """**Resuming is not approving**, asserted through the route.

    Otherwise anyone able to restart a run -- including an automated retry --
    could bypass the human CLAUDE.md §15 put behind it. `VIEW_WORKSPACE` is
    enough to resume, which is exactly why this must be refused.
    """
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs/{run['id']}/resume",
        headers=tenants.token_for(tenants.member),
    )

    assert response.status_code == 409
    assert provider.calls == 0


def test_approving_a_completed_run_is_409(client: TestClient, tenants: Tenants) -> None:
    """A client acting on stale state is told so rather than silently ignored."""
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)
    path = f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs/{run['id']}/approval"

    assert client.post(path, headers=tenants.token_for(tenants.owner)).status_code == 200
    assert client.post(path, headers=tenants.token_for(tenants.owner)).status_code == 409


# -------------------------------------------------------------- persistence --


def test_a_resumed_step_does_not_gain_a_second_row(client: TestClient, tenants: Tenants) -> None:
    """**The upsert on `(run_id, step_index)`, proven against real rows.**

    The `plan` step is written once as `awaiting_approval` and again as
    `completed`. Two rows would make the run's history show the step twice with
    no indication which one counted, and would break `next_step_index`.
    """
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs/{run['id']}/approval",
        headers=tenants.token_for(tenants.owner),
    )

    final = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs/{run['id']}",
        headers=tenants.token_for(tenants.owner),
    ).json()

    names = [step["step_name"] for step in final["steps"]]

    assert names == ["validate", "plan", "quality_check"]
    assert len(names) == len(set(names)), "a step gained a duplicate row"


def test_the_run_records_the_definition_version_it_executed(
    client: TestClient, tenants: Tenants
) -> None:
    """Versioned execution, persisted rather than resolved at read time."""
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    assert run["definition_version"] == 1


def test_a_completed_run_records_its_token_usage(client: TestClient, tenants: Tenants) -> None:
    """A run's cost is answerable from its own history, not only the ledger."""
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    body = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs/{run['id']}/approval",
        headers=tenants.token_for(tenants.owner),
    ).json()

    tokens = {step["step_name"]: step["tokens_used"] for step in body["steps"]}

    assert tokens["plan"] == 150
    # The deterministic steps spent nothing, recorded as zero rather than null:
    # the step ran and made no call.
    assert tokens["validate"] == 0
    assert tokens["quality_check"] == 0


def test_a_run_appears_in_the_workspace_listing(client: TestClient, tenants: Tenants) -> None:
    """Runs are readable by every member — a control nobody can inspect is one
    nobody can act on.
    """
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    listing = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs",
        headers=tenants.token_for(tenants.member),
    )

    assert listing.status_code == 200
    assert any(item["id"] == run["id"] for item in listing.json())


def test_the_run_records_who_triggered_it(client: TestClient, tenants: Tenants) -> None:
    """An automated run stays traceable to the person who started it."""
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id, actor=tenants.member)

    assert run["triggered_by"] == str(tenants.member.user_id)


# ------------------------------------------------------------------ failure --


def test_a_workflow_without_a_project_fails_the_run_not_the_request(
    client: TestClient, tenants: Tenants
) -> None:
    """**A failed run is a 201, not a 500.**

    The request succeeded: the run was created, executed, and recorded why it
    stopped. Reporting it as a server error would tell the client its call did
    not happen when it did, and would lose the run id they need to investigate.
    """
    run = _start(client, tenants, project_id=None)

    assert run["status"] == RunStatus.FAILED
    assert run["detail"] == "This workflow needs a project to run against"

    statuses = {step["step_name"]: step["status"] for step in run["steps"]}

    assert statuses["validate"] == StepStatus.FAILED


def test_a_failed_run_can_be_resumed(client: TestClient, tenants: Tenants) -> None:
    """**Failure Recovery**, and the reason `resume` accepts a failed run.

    A run that failed on a transient condition must be retryable without
    recreating it, which is what [[Workflow Engine]] means by "resume from
    checkpoints while preserving execution history".

    Here the failure is a missing project rather than a transient one, so the
    retry fails again — which still proves the path: the run was accepted for
    resumption rather than refused as terminal.
    """
    run = _start(client, tenants, project_id=None)

    assert run["status"] == RunStatus.FAILED

    resumed = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs/{run['id']}/resume",
        headers=tenants.token_for(tenants.owner),
    )

    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["status"] == RunStatus.FAILED


def test_a_failing_agent_fails_the_run_with_a_safe_message(
    client: TestClient, tenants: Tenants, provider: StubProvider
) -> None:
    """A provider returning nothing usable fails the run rather than passing it on.

    The agent's measurable success criterion, enforced end to end.
    """
    provider._content = "no."  # noqa: SLF001 - configuring the stub is the test's job

    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    approved = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs/{run['id']}/approval",
        headers=tenants.token_for(tenants.owner),
    ).json()

    assert approved["status"] == RunStatus.FAILED
    assert approved["detail"] == "The planning step did not produce a usable outline"


# ------------------------------------------------------ the tenant boundary --


def test_another_tenants_run_is_404_not_403(client: TestClient, tenants: Tenants) -> None:
    """A run id must not become an existence oracle across workspaces.

    The stranger asks their **own** workspace for a run id belonging to another
    tenant, so `requires(...)` admits them and the question genuinely reaches the
    run lookup.
    """
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    response = client.get(
        f"/api/v1/workspaces/{tenants.stranger_workspace_id}/workflows/runs/{run['id']}",
        headers=tenants.token_for(tenants.stranger),
    )

    assert response.status_code == 404


def test_a_run_id_is_not_an_existence_oracle(client: TestClient, tenants: Tenants) -> None:
    """A real hidden run and an invented id must be indistinguishable."""
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)
    invented = uuid.uuid4()

    hidden = client.get(
        f"/api/v1/workspaces/{tenants.stranger_workspace_id}/workflows/runs/{run['id']}",
        headers=tenants.token_for(tenants.stranger),
    )
    absent = client.get(
        f"/api/v1/workspaces/{tenants.stranger_workspace_id}/workflows/runs/{invented}",
        headers=tenants.token_for(tenants.stranger),
    )

    assert hidden.status_code == absent.status_code == 404
    assert hidden.json()["detail"] == absent.json()["detail"]


def test_no_route_reaches_another_tenants_run(client: TestClient, tenants: Tenants) -> None:
    """Every route taking a run id, asserted as a set.

    A single forgotten route is the whole exposure, so checking one proves
    nothing about the others.
    """
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    base = f"/api/v1/workspaces/{tenants.stranger_workspace_id}/workflows/runs/{run['id']}"
    headers = tenants.token_for(tenants.stranger)

    assert client.get(base, headers=headers).status_code == 404
    assert client.post(f"{base}/approval", headers=headers).status_code == 404
    assert client.post(f"{base}/resume", headers=headers).status_code == 404

    # And the run is untouched: a 404 that had already acted would be far worse
    # than one that merely reported wrongly.
    unchanged = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs/{run['id']}",
        headers=tenants.token_for(tenants.owner),
    ).json()

    assert unchanged["status"] == RunStatus.AWAITING_APPROVAL


def test_a_strangers_listing_excludes_our_runs(client: TestClient, tenants: Tenants) -> None:
    """RLS filters the listing, not a WHERE clause this code could forget."""
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    listing = client.get(
        f"/api/v1/workspaces/{tenants.stranger_workspace_id}/workflows/runs",
        headers=tenants.token_for(tenants.stranger),
    )

    assert listing.status_code == 200
    assert not any(item["id"] == run["id"] for item in listing.json())


def test_a_non_member_is_refused_the_workspace_itself(client: TestClient, tenants: Tenants) -> None:
    """The workspace gate answers 403 — the other half of the 404/403 split."""
    response = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs",
        headers=tenants.token_for(tenants.stranger),
    )

    assert response.status_code == 403


def test_a_run_cannot_name_another_tenants_project(client: TestClient, tenants: Tenants) -> None:
    """A cross-tenant `project_id` must not attach a run to another workspace.

    The composite foreign key to `(id, workspace_id)` is what makes this
    structural rather than a filter this code could forget — the same protection
    `assets` uses.

    **The run is never created at all**, which is stronger than failing it: the
    database refuses the insert, so there is no row claiming a cross-tenant
    project even in a failed state. The refusal is translated to a 404 matching
    every other unreachable project — without that translation it surfaced as an
    unhandled `ForeignKeyViolation` and a 500, which is how this was found.
    """
    project_id = _project(client, tenants)

    response = client.post(
        f"/api/v1/workspaces/{tenants.stranger_workspace_id}/workflows/runs",
        json={"workflow_type": "project_planning", "project_id": project_id},
        headers=tenants.token_for(tenants.stranger),
    )

    assert response.status_code == 404

    # And no run was recorded in the stranger's workspace.
    listing = client.get(
        f"/api/v1/workspaces/{tenants.stranger_workspace_id}/workflows/runs",
        headers=tenants.token_for(tenants.stranger),
    )

    assert listing.json() == []


# --------------------------------------------------------------- governance --


def test_a_run_is_recorded_in_the_spend_ledger(
    client: TestClient, tenants: Tenants, admin_connection: psycopg.Connection
) -> None:
    """**Every AI call passes through governance**, proven against the ledger.

    An agent reaching a provider without `AIService` would spend money invisibly.
    The spend row's `workflow_type` is what per-workflow ceilings meter on, so a
    mis-attributed row would make "set a limit on project planning" govern
    nothing.
    """
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs/{run['id']}/approval",
        headers=tenants.token_for(tenants.owner),
    )

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "SELECT workflow_type, prompt_tokens, completion_tokens "
            "FROM public.ai_spend_records WHERE workspace_id = %s",
            (tenants.workspace_id,),
        )
        rows = cursor.fetchall()

    assert len(rows) == 1
    assert rows[0][0] == "project_planning"
    assert rows[0][1] == 50
    assert rows[0][2] == 100


def test_workflow_tables_are_registered_for_erasure(client: TestClient, tenants: Tenants) -> None:
    """**CLAUDE.md §16**: a feature persisting user data registers its store.

    A run records what the platform did on a user's behalf, which is their data.
    An erasure leaving runs behind would leave a behavioural record of a
    workspace that asked to be forgotten.
    """
    project_id = _project(client, tenants)
    _start(client, tenants, project_id)

    erased = client.delete(
        f"/api/v1/workspaces/{tenants.workspace_id}/data",
        headers=tenants.token_for(tenants.owner),
    )

    assert erased.status_code == 200

    counts = erased.json()["erased"]

    assert counts["workflow_runs"] == 1
    # Two steps: `validate` completed and `plan` awaiting approval.
    assert counts["workflow_step_runs"] == 2


def test_an_erased_run_disappears_from_the_listing(client: TestClient, tenants: Tenants) -> None:
    """**The soft delete actually works.**

    This is the guard against the defect that cost STEP-11a and STEP-19 a step
    each: a SELECT policy filtering `deleted_at IS NULL` makes the erasing UPDATE
    affect zero rows, silently. Here it would show as a run still listed after
    erasure.
    """
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    client.delete(
        f"/api/v1/workspaces/{tenants.workspace_id}/data",
        headers=tenants.token_for(tenants.owner),
    )

    listing = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs",
        headers=tenants.token_for(tenants.owner),
    )

    assert not any(item["id"] == run["id"] for item in listing.json())
