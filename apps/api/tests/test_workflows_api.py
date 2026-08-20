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
from typing import Any

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
from app.jobs.handlers import WorkflowExecutionHandler
from app.jobs.registry import JobHandlerRegistry
from app.jobs.worker import JobWorker
from app.main import create_app
from app.repositories.job_dispatch import JobDispatchRepository
from app.repositories.session import RequestSessionFactory
from app.repositories.workflows import WorkflowRepository
from app.services.token_service import AuthenticatedUser
from app.workflows.execution import build_workflow_definitions
from app.workflows.models import RunStatus, StepStatus
from app.workflows.runner import WorkflowRunner
from tests.conftest import _REQUEST_ROLE_NAME, TEST_BYOK_KEY, Identity, seed_identity
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
    migrated_database: str,
    request_database_url: str,
    provider: StubProvider,
    admin_connection: psycopg.Connection,
) -> Iterator[TestClient]:
    """Return a client backed by the real test database.

    A provider key is seeded for the owner's workspace, because the planning
    agent's call would otherwise be refused with `NoProviderAvailableError`
    before reaching the provider -- which is correct behaviour and not what these
    tests are about.

    ## Both connections are configured, and they are genuinely different

    `DATABASE_URL` is the **privileged** connection and `REQUEST_DATABASE_URL`
    the request role, matching production and matching
    `test_ai_settings_endpoints.py` -- the only other suite that exercises the
    AI spend path.

    That distinction is load-bearing here, unlike in `test_projects_api.py`
    where both may point at the request role because nothing privileged runs.
    `AISpendRepository` reads the shutdown switch and reserves budget over the
    **privileged** connection **by design**: a ceiling must be found whether or
    not the caller can see the row, and `ai_shutdown_switches` grants nothing to
    `authenticated`.

    Pointing both at the request role made every workflow run fail with
    `permission denied for table ai_shutdown_switches` -- a fixture defect that
    only CI could reveal, because the live-database probe reads a real
    privileged `DATABASE_URL` from `.env` and therefore never exercised the
    wrong one.
    """

    configured = Settings(
        environment=Environment.DEVELOPMENT,
        SUPABASE_URL="https://project.test",
        SUPABASE_SECRET_KEY=SecretStr("unused"),
        DATABASE_URL=SecretStr(migrated_database),
        REQUEST_DATABASE_URL=SecretStr(request_database_url),
        byok_encryption_key=SecretStr(TEST_BYOK_KEY),
        _env_file=None,
    )

    def settings() -> Settings:
        return configured

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

    # The worker half of the same deployment, over the same database and the
    # same request role. **The API no longer executes a run**, so a suite that
    # only drove HTTP would assert that nothing happened; driving the real
    # worker is what makes these tests statements about the product rather than
    # about the queue.
    #
    # The provider is substituted through the definitions factory rather than
    # through `dependency_overrides`, because a worker has no FastAPI dependency
    # graph to override -- which is exactly why that factory is a parameter.
    worker = JobWorker(
        dispatch=JobDispatchRepository(configured),
        sessions=RequestSessionFactory(configured),
        registry=JobHandlerRegistry(
            (WorkflowExecutionHandler(build_workflow_definitions(configured, (provider,))),)
        ),
        lease_seconds=300,
        poll_interval_seconds=0.01,
        worker_id="test-workflow-worker",
    )

    with TestClient(app) as test_client:
        test_client.worker = worker  # type: ignore[attr-defined]
        test_client.provider = provider  # type: ignore[attr-defined]
        test_client.settings = configured  # type: ignore[attr-defined]
        test_client.dispatch = JobDispatchRepository(configured)  # type: ignore[attr-defined]

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


#: How many deliveries one test may need before the queue is empty. A run
#: normally takes one; a start followed by an approval takes two. Anything past
#: this is a worker that will not settle, and failing loudly beats spinning.
_MAX_DELIVERIES = 8


def _drain(client: TestClient) -> int:
    """Run the worker until the queue is empty, and return how many jobs it ran.

    **This is where a workflow now executes.** The route accepted the work and
    said so with a 202; this is the other half of that sentence.
    """
    worker: JobWorker = client.worker  # type: ignore[attr-defined]
    delivered = 0

    while worker.run_once():
        delivered += 1

        if delivered > _MAX_DELIVERIES:
            raise AssertionError(
                f"the worker delivered more than {_MAX_DELIVERIES} jobs without emptying "
                "the queue; a run is looping rather than settling"
            )

    return delivered


def _read(
    client: TestClient,
    tenants: Tenants,
    run_id: str,
    actor: Identity | None = None,
) -> dict:
    """Return a run as the API reports it.

    Every assertion about *what happened* reads persisted state through the
    route rather than trusting a POST's body, because the POST's body is now a
    snapshot of a run that had not started yet.
    """
    response = client.get(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs/{run_id}",
        headers=tenants.token_for(actor or tenants.owner),
    )

    assert response.status_code == 200, response.text

    return response.json()


def _assert_accepted(response, client: TestClient, tenants: Tenants) -> str:  # type: ignore[no-untyped-def]
    """Assert an accepted-but-unfinished response, and return the run id.

    Three things, every time: **202**, a `Location` naming the run's own monitor,
    and **no job identifier anywhere in the body**. The last is the one worth
    asserting on every route rather than once: exposing a job id would make the
    queue a public contract and turn ADR-005 §1's broker-migration escape hatch
    into a breaking client change.
    """
    assert response.status_code == 202, response.text

    body = response.json()
    run_id = body["id"]

    expected = f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs/{run_id}"

    assert response.headers["Location"].endswith(expected), response.headers.get("Location")
    assert "job_id" not in body
    assert "job" not in str(body)

    # And it resolves: a `Location` that 404s is worse than none at all.
    assert client.get(expected, headers=tenants.token_for(tenants.owner)).status_code == 200

    return str(run_id)


def _start(
    client: TestClient,
    tenants: Tenants,
    project_id: str | None,
    actor: Identity | None = None,
    execute: bool = True,
) -> dict:
    """Start a project-planning run, let the worker run it, and return the result.

    `execute=False` returns the run as the 202 left it -- queued and untouched --
    which is what a test asserting the *contract* rather than the outcome wants.
    """
    body: dict[str, object] = {"workflow_type": "project_planning"}

    if project_id is not None:
        body["project_id"] = project_id

    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs",
        json=body,
        headers=tenants.token_for(actor or tenants.owner),
    )

    run_id = _assert_accepted(response, client, tenants)

    assert response.json()["status"] == RunStatus.PENDING, (
        "a run was executed inside the request that started it"
    )

    if not execute:
        return response.json()

    _drain(client)

    return _read(client, tenants, run_id, actor)


def _approve(
    client: TestClient,
    tenants: Tenants,
    run_id: str,
    actor: Identity | None = None,
    execute: bool = True,
):  # type: ignore[no-untyped-def]
    """Approve the step a run is waiting on, and let the worker continue it.

    Returns the raw response when it is not a 202, so a test can assert the
    refusal it expected.
    """
    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs/{run_id}/approval",
        headers=tenants.token_for(actor or tenants.owner),
    )

    if response.status_code != 202 or not execute:
        return response

    _assert_accepted(response, client, tenants)
    _drain(client)

    return response


def _resume(
    client: TestClient,
    tenants: Tenants,
    run_id: str,
    actor: Identity | None = None,
    execute: bool = True,
):  # type: ignore[no-untyped-def]
    """Continue a failed run, and let the worker run whatever it enqueued."""
    response = client.post(
        f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs/{run_id}/resume",
        headers=tenants.token_for(actor or tenants.owner),
    )

    if response.status_code != 202 or not execute:
        return response

    _assert_accepted(response, client, tenants)
    _drain(client)

    return response


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

    _approve(client, tenants, run["id"])

    body = _read(client, tenants, run["id"])

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

    response = _approve(client, tenants, run["id"], actor=tenants.member)

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

    _approve(client, tenants, run["id"], actor=tenants.member)

    # Nothing was queued either: a refusal that enqueued the continuation would
    # execute the step a moment later, which is the defect this guards.
    assert _drain(client) == 0

    after = _read(client, tenants, run["id"])

    assert after["status"] == RunStatus.AWAITING_APPROVAL
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

    response = _resume(client, tenants, run["id"], actor=tenants.member)

    assert response.status_code == 409
    assert _drain(client) == 0
    assert provider.calls == 0


def test_approving_a_completed_run_is_409(client: TestClient, tenants: Tenants) -> None:
    """A client acting on stale state is told so rather than silently ignored."""
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    assert _approve(client, tenants, run["id"]).status_code == 202
    assert _read(client, tenants, run["id"])["status"] == RunStatus.COMPLETED

    assert _approve(client, tenants, run["id"]).status_code == 409


# -------------------------------------------------------------- persistence --


def test_a_resumed_step_does_not_gain_a_second_row(client: TestClient, tenants: Tenants) -> None:
    """**The upsert on `(run_id, step_index)`, proven against real rows.**

    The `plan` step is written once as `awaiting_approval` and again as
    `completed`. Two rows would make the run's history show the step twice with
    no indication which one counted, and would break `next_step_index`.
    """
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    _approve(client, tenants, run["id"])

    final = _read(client, tenants, run["id"])

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

    _approve(client, tenants, run["id"])

    body = _read(client, tenants, run["id"])
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

    resumed = _resume(client, tenants, run["id"])

    assert resumed.status_code == 202, resumed.text
    assert _read(client, tenants, run["id"])["status"] == RunStatus.FAILED


def test_a_failing_agent_fails_the_run_with_a_safe_message(
    client: TestClient, tenants: Tenants, provider: StubProvider
) -> None:
    """A provider returning nothing usable fails the run rather than passing it on.

    The agent's measurable success criterion, enforced end to end.
    """
    provider._content = "no."  # noqa: SLF001 - configuring the stub is the test's job

    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    _approve(client, tenants, run["id"])

    approved = _read(client, tenants, run["id"])

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

    _approve(client, tenants, run["id"])

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


# ------------------------------------------------- interruption and recovery --


def _worker_a_enters_the_paid_step(
    client: TestClient, tenants: Tenants, run_id: str
) -> tuple[Any, uuid.UUID]:
    """Claim the queued job and admit the planning step, then abandon it.

    Stands in for a worker that entered a paid step and died before persisting
    anything -- the one case the whole fencing design exists for, and one that
    cannot be produced by driving HTTP alone.
    """
    dispatch = client.dispatch  # type: ignore[attr-defined]
    claimed, _reaped = dispatch.claim("worker-a", 300)

    assert claimed is not None

    sessions = RequestSessionFactory(client.settings)  # type: ignore[attr-defined]

    with sessions.authenticated_as(tenants.owner.user_id) as connection:
        claim = WorkflowRepository(connection).admit_step(
            workspace_id=tenants.workspace_id,
            run_id=uuid.UUID(run_id),
            step_index=1,
            step_name="plan",
            requires_approval=True,
            replayable=False,
            job_id=claimed.id,
            lease_token=claimed.lease_token,
        )

    assert claim is not None

    return claimed, claim


def test_a_replacement_worker_calls_no_provider_and_never_reports_success(
    client: TestClient,
    tenants: Tenants,
    provider: StubProvider,
    admin_connection: psycopg.Connection,
) -> None:
    """**The single most dangerous case in this step, end to end.**

    A worker entered the paid step and died. Its lease lapses, the job is
    redelivered, and the replacement reaches a step it cannot claim. It must:
    call no provider, write nothing to the step, and **never settle its job
    `succeeded`** -- because it cannot prove the holder is dead, and a false
    success would leave a succeeded job, a `running` run and nothing able to
    advance or reconcile it.

    What it does instead is terminate: the job dead-letters and the run is
    reconciled to `failed` in the same statement, with a message that tells the
    user they can continue.
    """
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    assert run["status"] == RunStatus.AWAITING_APPROVAL

    _approve(client, tenants, run["id"], execute=False)

    claimed, claim = _worker_a_enters_the_paid_step(client, tenants, run["id"])
    calls_before = provider.calls

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.jobs SET lease_expires_at = now() - interval '1 second' WHERE id = %s",
            (claimed.id,),
        )

    _drain(client)

    final = _read(client, tenants, run["id"])

    assert provider.calls == calls_before, "a replacement execution called the provider"
    assert final["status"] == RunStatus.FAILED
    assert final["detail"] is not None
    assert "Resume it" in final["detail"], "the user is not told they can continue"

    with admin_connection.cursor() as cursor:
        # The job the replacement was delivering -- the one the approval
        # enqueued, not the one that ran `validate` and legitimately succeeded.
        cursor.execute("SELECT status FROM public.jobs WHERE id = %s", (claimed.id,))
        redelivered = cursor.fetchone()

        cursor.execute(
            "SELECT claim_token, status FROM public.workflow_step_runs "
            "WHERE run_id = %s AND step_index = 1",
            (run["id"],),
        )
        step = cursor.fetchone()

    assert redelivered is not None
    assert redelivered[0] == "dead_lettered", "a replacement worker reported success"

    # The claim survives as evidence, as a fence, and as the thing standing
    # between the next delivery and a provider that has already been paid.
    assert step is not None
    assert step[0] == claim
    assert step[1] == StepStatus.RUNNING


def test_recovery_continues_the_run_and_only_when_asked(
    client: TestClient,
    tenants: Tenants,
    provider: StubProvider,
    admin_connection: psycopg.Connection,
) -> None:
    """**No automatic re-invocation; a deliberate one may repeat the call.**

    The interrupted step is gated, so continuing takes two separate acts: a
    member re-arms the gate, and an owner approves again. Nothing calls the
    provider in between -- asserted on the stub's count, not on logs -- and
    after the fresh approval exactly one further call happens.
    """
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    _approve(client, tenants, run["id"], execute=False)
    claimed, _claim = _worker_a_enters_the_paid_step(client, tenants, run["id"])

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.jobs SET lease_expires_at = now() - interval '1 second' WHERE id = %s",
            (claimed.id,),
        )

    _drain(client)

    assert _read(client, tenants, run["id"])["status"] == RunStatus.FAILED
    assert provider.calls == 0

    # A member may re-arm the gate. It enqueues nothing, because the grant was
    # spent at admission and approval is never inferred.
    resumed = _resume(client, tenants, run["id"], actor=tenants.member)

    assert resumed.status_code == 202
    assert _drain(client) == 0, "recovery of a gated step enqueued work"

    after_resume = _read(client, tenants, run["id"])

    assert after_resume["status"] == RunStatus.AWAITING_APPROVAL
    assert provider.calls == 0

    # A fresh approval by an owner is what continues it, and it costs exactly one
    # provider call.
    _approve(client, tenants, run["id"])

    completed = _read(client, tenants, run["id"])

    assert completed["status"] == RunStatus.COMPLETED
    assert provider.calls == 1


def test_a_forged_payload_run_id_is_unreachable(
    client: TestClient, tenants: Tenants, admin_connection: psycopg.Connection
) -> None:
    """**The handler's run target is the relational link, never the payload.**

    `jobs.payload` is client-writable on INSERT, so a run id carried there would
    be a forgeable claim. A job whose payload names one run while its column
    names another advances only the run its column names -- and the payload is
    not so much rejected as never consulted.
    """
    project_id = _project(client, tenants)
    target = _start(client, tenants, project_id)
    decoy = _start(client, tenants, project_id)

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.jobs SET payload = %s::jsonb "
            "WHERE workflow_run_id = %s AND status = 'pending'",
            (f'{{"run_id": "{decoy["id"]}"}}', target["id"]),
        )

    # Both runs already reached their gate; approve only the target.
    _approve(client, tenants, target["id"], execute=False)

    with admin_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.jobs SET payload = %s::jsonb "
            "WHERE workflow_run_id = %s AND status = 'pending'",
            (f'{{"run_id": "{decoy["id"]}"}}', target["id"]),
        )

    _drain(client)

    assert _read(client, tenants, target["id"])["status"] == RunStatus.COMPLETED
    assert _read(client, tenants, decoy["id"])["status"] == RunStatus.AWAITING_APPROVAL


def test_a_redelivery_resumes_rather_than_restarting(
    client: TestClient, tenants: Tenants, admin_connection: psycopg.Connection
) -> None:
    """A completed step is not re-executed by a later delivery.

    The approval flow is a genuine second delivery in a second process context:
    `validate` ran in the first and must not run again in the second, which is
    what `next_step_index` counting only completed steps buys.
    """
    project_id = _project(client, tenants)
    run = _start(client, tenants, project_id)

    first = {step["step_name"]: step["started_at"] for step in run["steps"]}

    _approve(client, tenants, run["id"])

    final = _read(client, tenants, run["id"])
    second = {step["step_name"]: step["started_at"] for step in final["steps"]}

    assert final["status"] == RunStatus.COMPLETED
    assert second["validate"] == first["validate"], "a completed step was re-executed"


def test_the_rate_limiter_refuses_before_the_command_is_invoked(
    client: TestClient, tenants: Tenants, admin_connection: psycopg.Connection
) -> None:
    """**The route is the only entrance, so its limiter is the only gate.**

    Since no other caller can enter a command, this limiter is what bounds AI
    spend per user -- and the proof it holds is the *absence of a run and a job*
    on the refused call, not the 429 alone.
    """
    project_id = _project(client, tenants)
    path = f"/api/v1/workspaces/{tenants.workspace_id}/workflows/runs"
    body = {"workflow_type": "project_planning", "project_id": project_id}
    headers = tenants.token_for(tenants.owner)

    for _call in range(20):
        assert client.post(path, json=body, headers=headers).status_code == 202

    def counts() -> tuple[int, int]:
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM public.workflow_runs WHERE workspace_id = %s",
                (tenants.workspace_id,),
            )
            runs = cursor.fetchone()
            cursor.execute(
                "SELECT count(*) FROM public.jobs WHERE workspace_id = %s",
                (tenants.workspace_id,),
            )
            jobs = cursor.fetchone()

        return (0 if runs is None else runs[0], 0 if jobs is None else jobs[0])

    before = counts()
    refused = client.post(path, json=body, headers=headers)

    assert refused.status_code == 429
    assert counts() == before, "the 21st call reached the command"


# ---------------------------------------------- the connection a step holds --


class _ObservingProvider(StubProvider):
    """A provider that records the database's own view of itself mid-call.

    The observation is taken on a **separate** connection opened inside
    `complete`, because the question is what *other* connections exist at the
    moment a provider is being called -- which is not a question the connections
    under test can answer about themselves.
    """

    def __init__(self, observer_url: str) -> None:
        """Record where to open the observing connection."""
        super().__init__()
        self._observer_url = observer_url
        self.backends: tuple[tuple[str, str], ...] = ()

    def complete(self, request: CompletionRequest, api_key: str) -> CompletionResponse:
        """Snapshot `pg_stat_activity`, then answer like the stub it extends."""
        with psycopg.connect(self._observer_url) as observer, observer.cursor() as cursor:
            cursor.execute(
                "SELECT usename, state FROM pg_stat_activity "
                "WHERE datname = current_database() AND pid <> pg_backend_pid() "
                "AND usename IS NOT NULL"
            )
            self.backends = tuple((row[0], row[1]) for row in cursor.fetchall())

        return super().complete(request, api_key)


class TestTheProviderCallHoldsNoTenantConnection:
    """A workflow step must not hold a database session across a provider call.

    **"No row is locked" is not the property that matters here.** Admission
    commits before a step runs, so no workflow row is locked either way. What
    this class asserts is narrower and more expensive to get wrong: that no
    `projectone_api` backend *exists* while the provider is being called.

    `RequestSessionFactory.authenticated_as` keeps a transaction open for the
    life of a session -- it must, because `SET LOCAL ROLE` and the local JWT
    claim do not survive outside one. So a step holding a session across a
    provider call is a backend sitting `idle in transaction` for as long as the
    provider takes, up to `ExecutionBudget`'s 300-second ceiling. That pins the
    vacuum horizon, and `idle_in_transaction_session_timeout` would terminate it
    *after* the provider had been paid and before the step could settle.

    ADR-005 §4 states the rule ("no transaction is open while the long work
    runs"); `app/workflows/execution.py` is what implements it, by giving steps
    readers that open a session per call instead of a connection to hold.
    """

    @pytest.fixture
    def provider(self, migrated_database: str) -> _ObservingProvider:
        """Substitute a provider that looks at the database while it is called."""
        return _ObservingProvider(migrated_database)

    def test_no_request_role_connection_exists_during_the_call(
        self, client: TestClient, tenants: Tenants, provider: _ObservingProvider
    ) -> None:
        """The step releases its session before the provider is reached."""
        run = _start(client, tenants, _project(client, tenants))
        _approve(client, tenants, str(run["id"]))

        assert provider.calls == 1, "the observation must be taken during a real call"

        request_role = [name for name, _ in provider.backends if name == _REQUEST_ROLE_NAME]

        assert request_role == [], (
            "a workflow step held a request-role session across the provider call; "
            f"backends were {provider.backends}"
        )

    def test_nothing_is_idle_in_transaction_during_the_call(
        self, client: TestClient, tenants: Tenants, provider: _ObservingProvider
    ) -> None:
        """No connection anywhere is mid-transaction while an external call runs.

        Broader than the test above on purpose. `AISpendService.guard` holds one
        privileged connection for a guarded call rather than opening eight, which
        is a deliberate decision it documents -- and it holds it **idle**, not
        mid-transaction. This asserts that distinction rather than trusting it,
        because the two are one `BEGIN` apart and only one of them is safe to
        keep open across a network round trip.
        """
        run = _start(client, tenants, _project(client, tenants))
        _approve(client, tenants, str(run["id"]))

        assert provider.calls == 1

        mid_transaction = [
            (name, state) for name, state in provider.backends if state == "idle in transaction"
        ]

        assert mid_transaction == [], (
            f"a connection was mid-transaction across the provider call: {mid_transaction}"
        )


# ------------------------------------- the step outcome and the run, as one --


class TestSettlementAndRunTransitionAreOneTransaction:
    """The step outcome and the run transition it causes commit together.

    `test_workflow_commands.py` proves the database half by holding a settling
    transaction open and watching what a second connection can see and do. These
    prove the half that lives in the runner: that it puts both writes in one
    transaction, and that failing the second rolls back the first.
    """

    def test_a_failed_run_transition_rolls_the_step_back_with_it(
        self, client: TestClient, tenants: Tenants, admin_connection: psycopg.Connection
    ) -> None:
        """**The rollback proof, driven through the real runner.**

        `update_run_status` is made to fail after `app_settle_workflow_step` has
        already succeeded in the same transaction. If the two were separate
        transactions the step would be committed and stranded: `completed` under
        a run still `running`, with the claim released. In one transaction it is
        as if neither happened.
        """
        settings: Settings = client.settings  # type: ignore[attr-defined]
        sessions = RequestSessionFactory(settings)

        class RefusesTheRunTransition:
            """The real repository, refusing exactly the paired run transition.

            **Only the transitions that share a settlement's transaction.** The
            run is moved to `running` once at the start of an execution, on its
            own and with no step beside it; failing that would abort before
            anything settled and the test would pass without proving a thing.
            """

            def __init__(self, connection: psycopg.Connection) -> None:
                self._real = WorkflowRepository(connection)

            def __getattr__(self, name: str) -> Any:
                return getattr(self._real, name)

            def update_run_status(
                self, workspace_id: Any, run_id: Any, status: Any, **kwargs: Any
            ) -> Any:
                if status == RunStatus.RUNNING:
                    return self._real.update_run_status(workspace_id, run_id, status, **kwargs)

                raise RuntimeError("the run transition could not be written")

        project_id = _project(client, tenants)
        run = _start(client, tenants, project_id, execute=False)
        run_id = uuid.UUID(str(run["id"]))
        workspace_id = uuid.UUID(str(tenants.workspace_id))

        dispatch: JobDispatchRepository = client.dispatch  # type: ignore[attr-defined]
        claimed, _reaped = dispatch.claim("rollback-worker", 300)

        assert claimed is not None

        runner = WorkflowRunner(
            lambda: sessions.authenticated_as(tenants.owner.user_id),
            RefusesTheRunTransition,  # type: ignore[arg-type]
        )

        with pytest.raises(RuntimeError):
            runner.execute(
                workspace_id=workspace_id,
                run_id=run_id,
                definitions=build_workflow_definitions(
                    settings,
                    (client.provider,),  # type: ignore[attr-defined]
                ),
                job_id=claimed.id,
                lease_token=claimed.lease_token,
            )

        with admin_connection.cursor() as cursor:
            cursor.execute(
                "SELECT step_index, status FROM public.workflow_step_runs "
                "WHERE run_id = %s ORDER BY step_index",
                (run_id,),
            )
            steps = cursor.fetchall()

        # `validate` is an intermediate success: it moves no run state, settles
        # alone, and is legitimately committed. `plan` is the gated step whose
        # pause is paired with the run's move to `awaiting_approval` -- and that
        # pair failed, so neither half may survive.
        assert steps == [(0, StepStatus.COMPLETED)], (
            "a paired step settlement survived a run transition that failed; "
            f"the two are not one transaction: {steps}"
        )

    def test_a_redelivery_after_completion_is_a_success_not_a_dead_letter(
        self, client: TestClient, tenants: Tenants, admin_connection: psycopg.Connection
    ) -> None:
        """**An idempotent no-op.** No provider call, no state change, no dead letter.

        Delivery is at-least-once, so a job whose earlier delivery finished the
        run can arrive again -- its lease lapsed after the work was done rather
        than before. Dead-lettering that would mark a genuinely completed run as
        having a failed job against it, and D5's reconciliation is then the only
        thing standing between that and a `completed` run being rewritten to
        `failed`.
        """
        provider: StubProvider = client.provider  # type: ignore[attr-defined]
        project_id = _project(client, tenants)
        run = _start(client, tenants, project_id)

        _approve(client, tenants, run["id"])

        assert _read(client, tenants, run["id"])["status"] == RunStatus.COMPLETED

        calls_before = provider.calls

        # A fresh delivery of the completed run, enqueued the way a redelivery
        # arrives: same run, same handler, nothing left to do.
        with admin_connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO public.jobs "
                "(workspace_id, enqueued_by, job_type, payload, max_attempts, workflow_run_id) "
                "VALUES (%s, %s, 'workflow.execute', '{}'::jsonb, 2, %s) RETURNING id",
                (tenants.workspace_id, tenants.owner.user_id, run["id"]),
            )
            redelivered = cursor.fetchone()[0]  # type: ignore[index]

        assert _drain(client) == 1

        with admin_connection.cursor() as cursor:
            cursor.execute(
                "SELECT status, dead_lettered_at FROM public.jobs WHERE id = %s",
                (redelivered,),
            )
            status, dead_lettered_at = cursor.fetchone()  # type: ignore[misc]

        assert status == "succeeded", f"a redelivery of a completed run settled {status}"
        assert dead_lettered_at is None
        assert provider.calls == calls_before, "a redelivery called the provider again"
        assert _read(client, tenants, run["id"])["status"] == RunStatus.COMPLETED


# --------------------------------------------- the definition a run started --


def run_status(admin_connection: psycopg.Connection, run_id: str) -> str:
    """Return a run's stored status, read past every route and policy."""
    with admin_connection.cursor() as cursor:
        cursor.execute("SELECT status FROM public.workflow_runs WHERE id = %s", (run_id,))
        row = cursor.fetchone()

    assert row is not None

    return str(row[0])


def _rewrite_stored_version(
    admin_connection: psycopg.Connection, run_id: str, version: int
) -> None:
    """Make a run claim it started under a different definition version.

    Written directly rather than through a route, because there is deliberately
    no way for a caller to change it: the version is stamped at creation and
    never re-read. What this simulates is the deploy, not a request.
    """
    with admin_connection.cursor() as cursor:
        cursor.execute(
            "UPDATE public.workflow_runs SET definition_version = %s WHERE id = %s",
            (version, run_id),
        )


class TestARunCannotOutliveItsDefinition:
    """A run records `definition_version`, and it is now checked before every mutation.

    **Synchronously this could not happen.** The definition that started a run
    was necessarily the one that finished it, inside a single request. A run can
    now sit at an approval gate, or interrupted awaiting recovery, across a
    deploy that adds a step, reorders two, or changes whether one is gated or
    replayable.

    Continuing such a run is not a degraded version of correct behaviour, it is a
    different execution: `next_step_index` counts completed rows, so an inserted
    step shifts every index after it, and a step that stopped being `replayable`
    would be re-entered with no claim -- a second provider charge with nothing to
    prevent it. So this fails closed and preserves the run for a person to decide
    about.
    """

    def test_the_worker_refuses_a_run_whose_version_moved(
        self,
        client: TestClient,
        tenants: Tenants,
        provider: StubProvider,
        admin_connection: psycopg.Connection,
    ) -> None:
        """No provider call, no step admitted, and the run's steps untouched."""
        project_id = _project(client, tenants)
        run = _start(client, tenants, project_id, execute=False)

        _rewrite_stored_version(admin_connection, run["id"], 99)
        _drain(client)

        assert provider.calls == 0, "an incompatible definition reached the provider"

        with admin_connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM public.workflow_step_runs WHERE run_id = %s",
                (run["id"],),
            )

            assert cursor.fetchone()[0] == 0, "a step was admitted under a changed definition"

    def test_recovery_refuses_before_it_reads_requires_approval(
        self, client: TestClient, tenants: Tenants, admin_connection: psycopg.Connection
    ) -> None:
        """The check runs before the gate is re-armed from the wrong definition.

        Whether a step is gated is a property of the definition, so deriving it
        from one the run did not start under would re-arm the wrong gate -- or
        skip one that should have stopped the run.
        """
        project_id = _project(client, tenants)
        run = _start(client, tenants, project_id)

        with admin_connection.cursor() as cursor:
            cursor.execute(
                "UPDATE public.workflow_runs SET status = 'failed' WHERE id = %s",
                (run["id"],),
            )

        _rewrite_stored_version(admin_connection, run["id"], 99)

        refused = _resume(client, tenants, run["id"], execute=False)

        assert refused.status_code == 422, refused.text
        assert "definition has changed" in refused.json()["detail"]
        assert run_status(admin_connection, run["id"]) == "failed", "the run was mutated anyway"

    def test_approval_refuses_rather_than_enqueueing_work_the_worker_will_reject(
        self, client: TestClient, tenants: Tenants, admin_connection: psycopg.Connection
    ) -> None:
        """**The one that is easy to miss.**

        An approval that enqueued a job the worker then refused would turn an
        owner's decision into a dead-lettered job and a gate whose grant has
        already been spent. So it is refused here, with `approved_by` untouched
        and no job created.
        """
        project_id = _project(client, tenants)
        run = _start(client, tenants, project_id)

        _rewrite_stored_version(admin_connection, run["id"], 99)

        refused = _approve(client, tenants, run["id"], execute=False)

        assert refused.status_code == 422, refused.text

        with admin_connection.cursor() as cursor:
            cursor.execute(
                "SELECT approved_by FROM public.workflow_step_runs "
                "WHERE run_id = %s AND status = 'awaiting_approval'",
                (run["id"],),
            )
            granted = cursor.fetchone()

            assert granted is not None and granted[0] is None, "a grant was written anyway"

            cursor.execute(
                "SELECT count(*) FROM public.jobs WHERE workflow_run_id = %s "
                "AND status IN ('pending', 'running')",
                (run["id"],),
            )

            assert cursor.fetchone()[0] == 0, "a job was enqueued for an unexecutable run"

    def test_a_matching_version_is_unaffected(
        self, client: TestClient, tenants: Tenants, provider: StubProvider
    ) -> None:
        """The control. Nothing about the ordinary path changed."""
        project_id = _project(client, tenants)
        run = _start(client, tenants, project_id)

        _approve(client, tenants, run["id"])

        assert _read(client, tenants, run["id"])["status"] == RunStatus.COMPLETED
        assert provider.calls == 1
