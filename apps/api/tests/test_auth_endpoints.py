"""Tests for the authentication endpoints and the protection they apply.

Offline: the token service and the tenant connection are substituted, so these
assert the router's contract and its rejection behaviour without needing
Supabase or PostgreSQL. The end-to-end proof that RLS reaches the API lives in
`test_request_session.py`, which uses real connections.
"""

import uuid
from collections.abc import Iterator
from contextlib import nullcontext
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Environment, Settings, get_settings
from app.core.dependencies import (
    get_database_repository,
    get_request_session_factory,
    get_tenant_connection,
    get_token_service,
)
from app.core.security import InvalidTokenError, SigningKeyUnavailableError
from app.main import create_app
from app.services.token_service import AuthenticatedUser
from tests.conftest import TEST_BYOK_KEY
from tests.test_health import StubDatabase


def make_settings() -> Settings:
    """Build Settings without reading the ambient environment."""
    return Settings(
        environment=Environment.DEVELOPMENT,
        SUPABASE_URL="https://project.test",
        SUPABASE_SECRET_KEY=SecretStr("unused"),
        DATABASE_URL=SecretStr("postgresql://unused/db"),
        REQUEST_DATABASE_URL=SecretStr("postgresql://unused/db"),
        byok_encryption_key=SecretStr(TEST_BYOK_KEY),
        _env_file=None,
    )


class StubTokenService:
    """Verifies exactly one token string and rejects everything else."""

    def __init__(self, valid_token: str, user: AuthenticatedUser) -> None:
        self._valid = valid_token
        self._user = user

    def verify(self, token: str) -> AuthenticatedUser:
        if token == self._valid:
            return self._user
        if token == "jwks-down":
            raise SigningKeyUnavailableError("JWKS unreachable")
        raise InvalidTokenError("Token rejected")


VALID_TOKEN = "a-valid-token"  # noqa: S105 - a test fixture, not a credential
USER = AuthenticatedUser(id=uuid.uuid4(), email="user@example.test")


class StubCursor:
    """A cursor that accepts any query and yields no rows."""

    def __enter__(self) -> "StubCursor":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, *args: object) -> None:
        return None

    def __iter__(self) -> Iterator[tuple[object, ...]]:
        return iter(())


class StubConnection:
    """A connection standing in for a real tenant-scoped session."""

    def cursor(self) -> StubCursor:
        return StubCursor()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Return a client whose token verification is substituted."""
    settings = make_settings()
    app = create_app()

    app.dependency_overrides[get_settings] = make_settings
    app.dependency_overrides[get_database_repository] = lambda: StubDatabase(reachable=True)
    app.dependency_overrides[get_token_service] = lambda: StubTokenService(VALID_TOKEN, USER)

    del settings

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def test_a_request_with_no_token_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/workspaces")

    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"


def test_a_request_with_an_invalid_token_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/workspaces", headers={"Authorization": "Bearer nonsense"})

    assert response.status_code == 401


def test_a_request_with_a_tampered_token_is_rejected(client: TestClient) -> None:
    """A token that fails verification is rejected regardless of its shape."""
    response = client.get(
        "/api/v1/workspaces", headers={"Authorization": f"Bearer {VALID_TOKEN}-tampered"}
    )

    assert response.status_code == 401


def test_rejections_do_not_reveal_why(client: TestClient) -> None:
    """Every rejection returns the same body.

    Distinguishing "expired" from "bad signature" from "no token" hands an
    attacker a free oracle for refining an attack. The reason stays in the log.
    """

    def detail(token: str | None) -> str:
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        return str(client.get("/api/v1/workspaces", headers=headers).json()["detail"])

    bodies = {detail(None), detail("nope"), detail("jwks-down")}

    assert bodies == {"Not authenticated"}


def test_an_unverifiable_token_is_not_admitted(client: TestClient) -> None:
    """A JWKS outage must reject the request, never let it through unverified."""
    response = client.get("/api/v1/workspaces", headers={"Authorization": "Bearer jwks-down"})

    assert response.status_code == 401


def test_a_valid_token_reaches_the_route(client: TestClient) -> None:
    """A verified token gets past authentication and into the handler.

    The tenant connection is substituted here, so this asserts the auth gate
    opens — not what the query returns, which `test_request_session.py` covers
    against a real database.
    """
    app = client.app
    app.dependency_overrides[get_tenant_connection] = StubConnection  # type: ignore[attr-defined]

    response = client.get("/api/v1/workspaces", headers={"Authorization": f"Bearer {VALID_TOKEN}"})

    assert response.status_code == 200
    assert response.json() == []


def test_sign_up_validates_its_input(client: TestClient) -> None:
    """A short password is rejected before it reaches the identity provider."""
    response = client.post(
        "/api/v1/auth/sign-up", json={"email": "user@example.test", "password": "short"}
    )

    assert response.status_code == 422


def test_sign_up_rejects_a_malformed_address(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/sign-up", json={"email": "not-an-email", "password": "a" * 12}
    )

    assert response.status_code == 422


def test_the_tenant_connection_is_opened_for_the_verified_identity(
    client: TestClient,
) -> None:
    """The identity used to scope the database session is the token's.

    The link that makes RLS work end to end: `get_tenant_connection` depends on
    `get_current_user`, so the user id reaching the session factory is always
    the verified one and there is no parameter through which a caller could ask
    for someone else's.
    """
    scoped_to: list[uuid.UUID] = []

    class RecordingFactory:
        def authenticated_as(self, user_id: uuid.UUID) -> Any:
            scoped_to.append(user_id)
            return nullcontext(StubConnection())

    app = client.app
    app.dependency_overrides[get_request_session_factory] = RecordingFactory  # type: ignore[attr-defined]

    response = client.get("/api/v1/workspaces", headers={"Authorization": f"Bearer {VALID_TOKEN}"})

    assert response.status_code == 200
    assert scoped_to == [USER.id]
