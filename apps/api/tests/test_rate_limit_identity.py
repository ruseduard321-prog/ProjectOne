"""Rate limiting counts against the right identity (STEP-12a, ADR-002).

The regression this closes was observed during STEP-16: with every browser call
proxied through Next.js, the API saw one peer address for the whole platform, so
all users shared one bucket and ten sign-in attempts locked everybody out.

Two properties are under test, and they are different in kind:

- **Public endpoints** must key on the *real* client address, honoured only
  from a trusted proxy. The security assertions live in
  `test_client_address.py`, which tests the resolution rules directly; what is
  asserted here is that the limiter actually uses them.
- **Authenticated endpoints** must key on the verified `user_id`, so one user
  exhausting an allowance cannot affect another.

Offline: identity and database layers are substituted, exactly as in
`test_api_conventions.py`.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.api import API_PREFIX
from app.core.config import Environment, Settings, get_settings
from app.core.dependencies import get_database_repository, get_token_service
from app.core.errors import EXCEPTION_HANDLERS
from app.core.middleware import RateLimitMiddleware, RateLimitRule, RequestContextMiddleware
from app.core.user_rate_limit import UserRateLimiter, get_user_rate_limiter, limit_by_user
from app.main import create_app
from app.services.token_service import AuthenticatedUser
from tests.conftest import TEST_BYOK_KEY
from tests.test_auth_endpoints import StubTokenService, make_settings
from tests.test_health import StubDatabase

#: A second identity, so "independent buckets" can actually be asserted.
USER_A = AuthenticatedUser(id=uuid.uuid4(), email="a@example.test")
USER_B = AuthenticatedUser(id=uuid.uuid4(), email="b@example.test")

TOKEN_A = "token-for-user-a"  # noqa: S105 - a test fixture, not a credential
TOKEN_B = "token-for-user-b"  # noqa: S105 - a test fixture, not a credential

#: The address the TestClient presents as its peer.
TEST_CLIENT_PEER = "testclient"

SIGN_IN = f"{API_PREFIX}/auth/sign-in"
CREDENTIALS = {"email": "user@example.test", "password": "a-long-enough-password"}


class TwoUserTokenService:
    """Verifies two distinct tokens, so two identities can be exercised."""

    def verify(self, token: str) -> AuthenticatedUser:
        if token == TOKEN_A:
            return USER_A
        if token == TOKEN_B:
            return USER_B

        from app.core.security import InvalidTokenError

        raise InvalidTokenError("unknown token")


def settings_trusting_the_test_client() -> Settings:
    """Return Settings that trust the address TestClient connects from.

    TestClient reports its peer as the literal string `testclient`, which is not
    an IP address -- so the allowlist cannot match it and forwarded headers are
    correctly ignored. Tests needing the *trusted* path therefore drive the
    middleware directly (see `trusted_proxy_app`), and this fixture covers the
    untrusted case, which is the security-relevant one.
    """
    return Settings(
        environment=Environment.DEVELOPMENT,
        SUPABASE_URL="https://project.test",
        SUPABASE_SECRET_KEY=make_settings().supabase_secret_key,
        DATABASE_URL=make_settings().database_url,
        REQUEST_DATABASE_URL=make_settings().request_database_url,
        byok_encryption_key=SecretStr(TEST_BYOK_KEY),
        _env_file=None,
    )


@pytest.fixture(autouse=True)
def _reset_user_limits() -> Iterator[None]:
    """Clear per-user counters between tests.

    Without this, one test exhausting an allowance leaks into the next and the
    failure surfaces in whichever test happens to run afterwards rather than in
    the one that caused it.
    """
    get_user_rate_limiter().clear()

    yield

    get_user_rate_limiter().clear()


# ---------------------------------------------------------------------------
# Public endpoints: the forged header must not become the key
# ---------------------------------------------------------------------------


@pytest.fixture
def public_client() -> Iterator[TestClient]:
    """A client against the real app, with identity and database substituted."""
    app = create_app()

    app.dependency_overrides[get_settings] = settings_trusting_the_test_client
    app.dependency_overrides[get_database_repository] = lambda: StubDatabase(reachable=True)
    app.dependency_overrides[get_token_service] = lambda: StubTokenService("unused", USER_A)

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_a_forged_forwarded_header_does_not_reset_the_allowance(
    public_client: TestClient,
) -> None:
    """The end-to-end version of the central security property.

    An attacker varying `X-Forwarded-For` on every request must still be
    refused. If the header were trusted, each request would land in a fresh
    bucket and the limiter would never trip -- unlimited credential stuffing,
    with logs that look entirely healthy.
    """
    statuses = [
        public_client.post(
            SIGN_IN,
            json=CREDENTIALS,
            headers={"X-Forwarded-For": f"203.0.113.{index}"},
        ).status_code
        for index in range(12)
    ]

    assert 429 in statuses, "a forged header must not buy an unlimited allowance"
    assert statuses.index(429) == 10, f"limit tripped at the wrong request: {statuses}"


def test_the_refusal_contract_is_unchanged(public_client: TestClient) -> None:
    """STEP-12's envelope, Retry-After and correlation id all survive."""
    for _ in range(11):
        response = public_client.post(SIGN_IN, json=CREDENTIALS)

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert response.json()["request_id"] != "-"
    assert response.json()["detail"] == "Too many requests. Try again shortly."


# ---------------------------------------------------------------------------
# Public endpoints: a trusted proxy's forwarded address separates clients
# ---------------------------------------------------------------------------


def build_trusted_proxy_app(trusted: tuple[str, ...]) -> FastAPI:
    """Build a minimal app whose limiter trusts `trusted`.

    Deliberately not `create_app()`: TestClient's peer address is the literal
    `testclient`, which no CIDR can match, so the trusted path cannot be
    exercised through it. This app applies the same middleware with the same
    rule table and a peer the allowlist *can* match, which is what makes
    "two clients behind one proxy get separate buckets" assertable.
    """
    from app.core.client_address import parse_trusted_proxies

    app = FastAPI()
    router = APIRouter()

    @router.post("/limited")
    def limited() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(router)
    app.add_middleware(
        RateLimitMiddleware,
        rules={"/limited": RateLimitRule(limit=3, window_seconds=60)},
        trusted_proxies=parse_trusted_proxies(list(trusted)),
    )
    app.add_middleware(RequestContextMiddleware)

    return app


def test_two_clients_behind_one_proxy_have_separate_allowances() -> None:
    """The regression STEP-16 recorded, asserted fixed.

    Both requests arrive from the same proxy; only the forwarded address
    differs. Before this step both would have shared one bucket, so exhausting
    one client's allowance locked out the other.
    """
    app = build_trusted_proxy_app(("127.0.0.0/8",))

    with TestClient(app, client=("127.0.0.1", 5000)) as client:
        first = [
            client.post("/limited", headers={"X-Forwarded-For": "203.0.113.1"}).status_code
            for _ in range(4)
        ]
        second = client.post("/limited", headers={"X-Forwarded-For": "203.0.113.2"}).status_code

    assert 429 in first, "the first client should have exhausted its own allowance"
    assert second == 200, "a different client must not inherit the first one's exhaustion"


def test_an_untrusted_peer_is_limited_as_one_bucket() -> None:
    """With nothing trusted, forwarded addresses are ignored entirely."""
    app = build_trusted_proxy_app(())

    with TestClient(app, client=("127.0.0.1", 5000)) as client:
        statuses = [
            client.post("/limited", headers={"X-Forwarded-For": f"203.0.113.{i}"}).status_code
            for i in range(4)
        ]

    assert statuses[-1] == 429, "an empty allowlist must ignore the header"


# ---------------------------------------------------------------------------
# Authenticated endpoints: independent buckets per verified user
# ---------------------------------------------------------------------------


def build_user_limited_app() -> FastAPI:
    """Build an app with one route limited per user."""
    app = FastAPI()
    router = APIRouter()

    @router.get(
        "/per-user",
        dependencies=[Depends(limit_by_user("test-scope", limit=3, window_seconds=60))],
    )
    def per_user() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(router)

    for exception_type, handler in EXCEPTION_HANDLERS:
        app.add_exception_handler(exception_type, handler)

    app.add_middleware(RequestContextMiddleware)

    app.dependency_overrides[get_settings] = make_settings
    app.dependency_overrides[get_token_service] = TwoUserTokenService

    return app


def test_two_users_have_independent_buckets() -> None:
    """The requirement in one assertion.

    One user exhausting their allowance must leave every other user untouched.
    Sharing a bucket is what turned a rate limiter into a denial of service.
    """
    app = build_user_limited_app()

    with TestClient(app) as client:
        exhausted = [
            client.get("/per-user", headers={"Authorization": f"Bearer {TOKEN_A}"}).status_code
            for _ in range(4)
        ]
        other = client.get("/per-user", headers={"Authorization": f"Bearer {TOKEN_B}"}).status_code

    assert exhausted[-1] == 429, "user A should have exhausted their own allowance"
    assert other == 200, "user B must be unaffected by user A"


def test_the_same_user_is_refused_after_their_allowance() -> None:
    app = build_user_limited_app()

    with TestClient(app) as client:
        statuses = [
            client.get("/per-user", headers={"Authorization": f"Bearer {TOKEN_A}"}).status_code
            for _ in range(4)
        ]

    assert statuses == [200, 200, 200, 429]


def test_a_per_user_refusal_matches_the_middleware_refusal() -> None:
    """A caller must not be able to tell which limiter refused them.

    A difference in shape would reveal whether the endpoint considered them
    authenticated, which is information a rejection must not carry.
    """
    app = build_user_limited_app()

    with TestClient(app) as client:
        for _ in range(4):
            response = client.get("/per-user", headers={"Authorization": f"Bearer {TOKEN_A}"})

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert response.json()["detail"] == "Too many requests. Try again shortly."
    assert response.json()["request_id"] != "-"


def test_the_limit_key_cannot_be_influenced_by_the_request() -> None:
    """The load-bearing rule: identity comes from the verified token only.

    A caller naming another user in a header or a query parameter is counted
    against *their own* verified identity regardless. If this failed, a caller
    could spend someone else's allowance -- or dodge their own.
    """
    app = build_user_limited_app()

    with TestClient(app) as client:
        for _ in range(4):
            client.get(
                "/per-user",
                headers={
                    "Authorization": f"Bearer {TOKEN_A}",
                    # All ignored: none of these is the verified subject.
                    "X-User-Id": str(USER_B.id),
                    "X-Forwarded-For": "203.0.113.77",
                },
                params={"user_id": str(USER_B.id)},
            )

        victim = client.get("/per-user", headers={"Authorization": f"Bearer {TOKEN_B}"}).status_code

    assert victim == 200, "user B's allowance must not be spendable by user A"


def test_an_unauthenticated_request_is_rejected_before_being_counted() -> None:
    """The limiter depends on a verified identity, so 401 comes first."""
    app = build_user_limited_app()

    with TestClient(app) as client:
        response = client.get("/per-user")

    assert response.status_code == 401


def test_distinct_scopes_do_not_share_a_bucket() -> None:
    """Exhausting one route must not lock a user out of an unrelated one."""
    limiter = UserRateLimiter()

    for _ in range(3):
        limiter.check(USER_A.id, "scope-one", limit=3, window_seconds=60)

    # The same user, a different scope: still allowed.
    limiter.check(USER_A.id, "scope-two", limit=3, window_seconds=60)


def test_a_real_route_carries_its_per_user_limit() -> None:
    """`limit_by_user` is wired to production routes, not just to test apps.

    Without this, the mechanism could pass every test above while being applied
    nowhere -- a limiter that exists and limits nothing. Asserted through the
    OpenAPI-independent route table so it survives a path change.
    """
    app = create_app()

    limited = {
        route.path
        for route in app.routes
        if any(
            getattr(dependency.call, "__qualname__", "").startswith("limit_by_user")
            for dependency in getattr(getattr(route, "dependant", None), "dependencies", [])
        )
    }

    assert f"{API_PREFIX}/workspaces" in limited, "workspace creation must be limited per user"
    assert f"{API_PREFIX}/workspaces/{{workspace_id}}/export" in limited, (
        "export is the most expensive read the API serves and must be limited per user"
    )


def test_health_is_still_never_rate_limited(public_client: TestClient) -> None:
    """An unreachable health check reports an outage the check itself caused."""
    statuses = {public_client.get("/health").status_code for _ in range(40)}

    assert statuses == {200}
