"""Tests for the cross-cutting API conventions (STEP-12).

Offline: nothing here needs Supabase or PostgreSQL. What is under test is the
contract every endpoint inherits — the version prefix, the error envelope, the
correlation id, the rate limiter, and the rule that no credential reaches a
log — none of which depends on a real backend.

The credential-redaction tests matter more than their size suggests. That rule
is the one most easily broken by a later convenience change, and it fails
silently when it breaks: nothing turns red, the token is simply in the log
file. These assertions are what turn it red.
"""

import logging
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.api import API_PREFIX, REQUEST_ID_HEADER
from app.core.config import get_settings
from app.core.dependencies import (
    get_database_repository,
    get_tenant_connection,
    get_token_service,
)
from app.core.logging import RedactingFilter, redact
from app.main import create_app
from tests.test_auth_endpoints import (
    USER,
    VALID_TOKEN,
    StubConnection,
    StubTokenService,
    make_settings,
)
from tests.test_health import StubDatabase


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Return a client whose identity and database layers are substituted.

    **`get_tenant_connection` is deliberately not overridden here.** Overriding
    it replaces the whole dependency subtree beneath it — including
    `get_current_user` — so an unauthenticated request would reach the handler
    and return 200. Every rejection test in this module would then pass
    against an app that was not checking anything.

    Tests that need a *successful* tenant query use `authenticated_client`
    below, which applies that override knowingly and only where the auth gate
    is not what is being asserted.
    """
    app = create_app()

    app.dependency_overrides[get_settings] = make_settings
    app.dependency_overrides[get_database_repository] = lambda: StubDatabase(reachable=True)
    app.dependency_overrides[get_token_service] = lambda: StubTokenService(VALID_TOKEN, USER)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_client(client: TestClient) -> TestClient:
    """Return a client whose tenant connection is stubbed as well.

    For tests asserting what a *served* request does — its correlation id, its
    log line — rather than whether it was allowed through.
    """
    client.app.dependency_overrides[get_tenant_connection] = StubConnection  # type: ignore[attr-defined]

    return client


def auth_header() -> dict[str, str]:
    """Return a header carrying the stub's accepted token."""
    return {"Authorization": f"Bearer {VALID_TOKEN}"}


# --------------------------------------------------------------------------
# Versioning
# --------------------------------------------------------------------------


def test_every_product_route_answers_on_the_versioned_path(
    authenticated_client: TestClient,
) -> None:
    """The migration moved the routes rather than duplicating them."""
    response = authenticated_client.get(f"{API_PREFIX}/workspaces", headers=auth_header())

    assert response.status_code == 200


def test_the_unversioned_path_no_longer_answers(authenticated_client: TestClient) -> None:
    """The old path is gone, not merely shadowed.

    This is the assertion that proves a *migration* happened. If both paths
    answered, the version prefix would be decoration: clients would keep using
    the unversioned route, and v2 would break them exactly as if versioning had
    never been introduced.
    """
    response = authenticated_client.get("/workspaces", headers=auth_header())

    assert response.status_code == 404


def test_health_stays_unversioned(client: TestClient) -> None:
    """Health is infrastructure, not a product API contract.

    Deliberate: orchestrators and uptime checks point at `/health`, and moving
    it under a version prefix would make every API version bump a deploy
    configuration change.
    """
    assert client.get("/health").status_code == 200
    assert client.get(f"{API_PREFIX}/health").status_code == 404


# --------------------------------------------------------------------------
# The error envelope
# --------------------------------------------------------------------------


def test_an_error_body_carries_a_request_id(client: TestClient) -> None:
    """Every error is findable in the log by the id the caller was shown."""
    body = client.get(f"{API_PREFIX}/workspaces").json()

    assert body["detail"] == "Not authenticated"
    assert body["request_id"] != "-"


def test_authentication_failures_share_one_identical_detail(client: TestClient) -> None:
    """The STEP-10 property, re-proven against the new envelope.

    Distinguishing "expired" from "bad signature" from "no token" hands an
    attacker a free oracle. `request_id` varies per request by design, so the
    comparison is on `detail` alone — which is exactly why the id was added
    beside `detail` rather than folded into it.
    """
    bodies = {
        client.get(f"{API_PREFIX}/workspaces").json()["detail"],
        client.get(f"{API_PREFIX}/workspaces", headers={"Authorization": "Bearer nope"}).json()[
            "detail"
        ],
        client.get(
            f"{API_PREFIX}/workspaces", headers={"Authorization": "Bearer jwks-down"}
        ).json()["detail"],
    }

    assert bodies == {"Not authenticated"}


def test_a_401_still_carries_the_challenge_header(client: TestClient) -> None:
    """Moving translation into a handler must not drop `WWW-Authenticate`."""
    response = client.get(f"{API_PREFIX}/workspaces")

    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"


def test_a_404_carries_the_envelope_too(client: TestClient) -> None:
    """Starlette's own 404 is rendered through the contract, not around it."""
    body = client.get(f"{API_PREFIX}/nothing-here").json()

    assert "detail" in body
    assert "request_id" in body


def test_a_validation_failure_reports_fields_without_echoing_the_input(
    client: TestClient,
) -> None:
    """422 names the offending field but never reflects the value.

    On `/auth/sign-up` the rejected value *is* the password. Pydantic echoes an
    `input` key by default; reflecting a credential into a response body is how
    it reaches a browser console, an error tracker and a support ticket.
    """
    response = client.post(
        f"{API_PREFIX}/auth/sign-up",
        json={"email": "user@example.test", "password": "hunter2"},
    )

    assert response.status_code == 422

    body = response.json()
    assert body["request_id"] != "-"
    assert any(error["field"].endswith("password") for error in body["errors"])
    assert "hunter2" not in response.text


# --------------------------------------------------------------------------
# Correlation id
# --------------------------------------------------------------------------


def test_a_response_echoes_a_correlation_id(authenticated_client: TestClient) -> None:
    response = authenticated_client.get(f"{API_PREFIX}/workspaces", headers=auth_header())

    assert response.headers[REQUEST_ID_HEADER]


def test_a_supplied_correlation_id_is_honoured(authenticated_client: TestClient) -> None:
    """A trace survives the hop from an upstream proxy or client."""
    supplied = "trace-abc-123"

    response = authenticated_client.get(
        f"{API_PREFIX}/workspaces",
        headers={**auth_header(), REQUEST_ID_HEADER: supplied},
    )

    assert response.headers[REQUEST_ID_HEADER] == supplied


def test_a_hostile_correlation_id_is_replaced(authenticated_client: TestClient) -> None:
    """A caller-supplied id lands in every log line, so it is untrusted input.

    A newline would let a caller forge log entries; unbounded length would let
    them flood the log (CLAUDE.md §16).
    """
    response = authenticated_client.get(
        f"{API_PREFIX}/workspaces",
        headers={**auth_header(), REQUEST_ID_HEADER: "abc def"},
    )

    echoed = response.headers[REQUEST_ID_HEADER]

    assert echoed != "abc def"
    assert uuid.UUID(echoed)


def test_the_correlation_id_in_the_log_matches_the_one_returned(
    authenticated_client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The whole point: a user quotes an id, and the log line is findable."""
    with caplog.at_level(logging.INFO):
        response = authenticated_client.get(
            f"{API_PREFIX}/workspaces",
            headers={**auth_header(), REQUEST_ID_HEADER: "findable-id"},
        )

    assert response.headers[REQUEST_ID_HEADER] == "findable-id"

    root = logging.getLogger()
    middleware_logger = logging.getLogger("app.core.middleware")
    state = (
        f"captured={[(r.name, getattr(r, 'request_id', None)) for r in caplog.records]} "
        f"root_level={logging.getLevelName(root.level)} "
        f"root_handlers={[h.get_name() or type(h).__name__ for h in root.handlers]} "
        f"mw_propagate={middleware_logger.propagate} "
        f"mw_effective={logging.getLevelName(middleware_logger.getEffectiveLevel())} "
        f"logging_disable={logging.root.manager.disable}"
    )

    assert any(getattr(record, "request_id", None) == "findable-id" for record in caplog.records), (
        f"no log record carried the request's correlation id. {state}"
    )


def test_a_request_is_logged_with_its_method_path_and_status(
    authenticated_client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        authenticated_client.get(f"{API_PREFIX}/workspaces", headers=auth_header())

    assert any(
        "method=GET" in record.getMessage()
        and f"path={API_PREFIX}/workspaces" in record.getMessage()
        for record in caplog.records
    )


# --------------------------------------------------------------------------
# Credential redaction
# --------------------------------------------------------------------------


def test_no_log_line_contains_the_authorization_header_or_a_token(
    authenticated_client: TestClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The rule STEP-10 deferred to this step, asserted rather than assumed.

    Nothing in the request path logs headers today. This test exists so that
    the day someone adds `logger.info(request.headers)` while debugging, the
    suite fails instead of the token silently reaching a log file.
    """
    with caplog.at_level(logging.DEBUG):
        authenticated_client.get(f"{API_PREFIX}/workspaces", headers=auth_header())
        authenticated_client.post(
            f"{API_PREFIX}/auth/sign-in",
            json={"email": "user@example.test", "password": "a-real-password"},
        )

    logged = "\n".join(record.getMessage() for record in caplog.records)

    assert VALID_TOKEN not in logged
    assert "a-real-password" not in logged
    assert "authorization:" not in logged.lower()


@pytest.mark.parametrize(
    "line",
    [
        "Authorization: Bearer eyJhbGciOiJFUzI1NiJ9.payload.signature",
        "{'authorization': 'Bearer abc.def.ghi'}",
        'headers={"Authorization": "Basic dXNlcjpwYXNz"}',
        "access_token=eyJhbGciOiJFUzI1NiJ9.body.sig",
        "refresh_token: 'v1.MRjLQ8...'",
        '{"password": "hunter2"}',
        "api_key=sb_secret_abcdefghijklmnop",
    ],
)
def test_credential_shaped_values_are_redacted(line: str) -> None:
    """The redaction rule itself, tested directly rather than through a handler.

    Testing through the whole logging pipeline tests the pipeline; this tests
    the rule, which is what actually has to be right.
    """
    result = redact(line)

    assert "[REDACTED]" in result
    for leaked in (
        "eyJhbGciOiJFUzI1NiJ9",
        "abc.def.ghi",
        "dXNlcjpwYXNz",
        "hunter2",
        "sb_secret_abcdefghijklmnop",
        "v1.MRjLQ8",
    ):
        assert leaked not in result


def test_redaction_keeps_the_label_so_the_line_stays_debuggable() -> None:
    """A redacted line still says *that* a credential was present.

    Silently deleting the evidence is harder to debug than saying "there was a
    token here" — and a redaction nobody can interpret is one someone
    eventually turns off.
    """
    assert "Bearer [REDACTED]" in redact("Authorization: Bearer secret-token-value")


def test_the_filter_censors_rather_than_drops() -> None:
    """A record containing a token is redacted and still emitted.

    Dropping it would lose the event as well as the credential, and the event
    is usually the interesting half of an auth failure.
    """
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="calling with %s",
        args=("Bearer leaked-token",),
        exc_info=None,
    )

    assert RedactingFilter().filter(record) is True
    assert "leaked-token" not in record.getMessage()
    assert "[REDACTED]" in record.getMessage()


# --------------------------------------------------------------------------
# Rate limiting
# --------------------------------------------------------------------------


def test_sign_in_refuses_the_request_after_its_allowance(client: TestClient) -> None:
    """The n+1th request in the window is actually refused, observed.

    The stub token service means these never reach Supabase; what is under test
    is the limiter, and it must refuse before the request is served at all.
    """
    payload = {"email": "user@example.test", "password": "a-long-enough-password"}
    statuses = [
        client.post(f"{API_PREFIX}/auth/sign-in", json=payload).status_code for _ in range(12)
    ]

    assert 429 in statuses
    assert statuses.index(429) == 10, f"limit tripped at the wrong request: {statuses}"


def test_a_rate_limited_response_carries_the_envelope_and_retry_after(
    client: TestClient,
) -> None:
    payload = {"email": "user@example.test", "password": "a-long-enough-password"}

    for _ in range(11):
        response = client.post(f"{API_PREFIX}/auth/sign-in", json=payload)

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert response.json()["request_id"] != "-"


def test_separate_endpoints_have_separate_allowances(client: TestClient) -> None:
    """Exhausting sign-in must not lock the caller out of sign-up.

    They protect different things — credential stuffing and account spam — and
    a shared counter would make one attack a denial of service against the
    other endpoint.
    """
    for _ in range(11):
        client.post(
            f"{API_PREFIX}/auth/sign-in",
            json={"email": "user@example.test", "password": "a-long-enough-password"},
        )

    response = client.post(
        f"{API_PREFIX}/auth/sign-up",
        json={"email": "new@example.test", "password": "a-long-enough-password"},
    )

    assert response.status_code != 429


def test_health_is_never_rate_limited(client: TestClient) -> None:
    """An unreachable health check reports an outage the check itself caused."""
    statuses = {client.get("/health").status_code for _ in range(40)}

    assert statuses == {200}
