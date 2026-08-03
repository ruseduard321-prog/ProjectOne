"""Tests for the health endpoint and its service.

Two levels deliberately: the service is tested without HTTP, proving business
logic is testable independent of the web framework (CLAUDE.md §18), and the
route is tested through the app, proving the wiring works.

No test here touches a real database. The database repository is substituted,
so the suite stays fast, runs offline, and passes in CI — where the connection
string is a deliberate placeholder (STEP-07).
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.core.config import Environment, Settings
from app.core.dependencies import get_database_repository
from app.main import create_app
from app.repositories.database import DatabaseRepository
from app.services.health_service import HealthService
from tests.conftest import TEST_BYOK_KEY


class StubDatabase(DatabaseRepository):
    """A database repository that reports a fixed answer.

    Subclasses the real repository so the substitution stays type-correct: if
    the interface changes, this fails to type-check rather than silently
    diverging from what it stands in for.
    """

    def __init__(self, *, reachable: bool) -> None:
        """Record the answer this stub will always give."""
        self._reachable = reachable

    def is_reachable(self) -> bool:
        """Return the configured answer without touching a database."""
        return self._reachable


def make_settings(**overrides: object) -> Settings:
    """Build Settings for tests without reading the ambient environment.

    `_env_file=None` keeps a developer's real `.env` from leaking into a test
    result — otherwise these would pass or fail depending on whose machine ran
    them.
    """
    values: dict[str, object] = {
        "app_name": "Test API",
        "environment": Environment.STAGING,
        "version": "9.9.9",
        "SUPABASE_URL": "https://test.supabase.co",
        "SUPABASE_SECRET_KEY": "sb_secret_test",
        "DATABASE_URL": "postgresql://test:test@127.0.0.1:5432/test",
        # Required as of STEP-10. Distinct from DATABASE_URL on purpose: the two
        # are different roles in every real environment, and a test fixture that
        # collapsed them would model a configuration that must never exist.
        "REQUEST_DATABASE_URL": "postgresql://projectone_api:test@127.0.0.1:5432/test",
        # Required as of STEP-17. Shared from conftest so the next required
        # setting is one edit rather than eight.
        "byok_encryption_key": TEST_BYOK_KEY,
    }
    values.update(overrides)

    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def test_health_service_reports_ok_without_http() -> None:
    result = HealthService(make_settings(), StubDatabase(reachable=True)).check()

    assert result.status == "ok"
    assert result.service == "Test API"
    assert result.environment == "staging"
    assert result.version == "9.9.9"
    assert [(d.name, d.healthy) for d in result.dependencies] == [("database", True)]


def test_health_service_reports_degraded_when_database_is_down() -> None:
    result = HealthService(make_settings(), StubDatabase(reachable=False)).check()

    assert result.status == "degraded"
    assert result.dependencies[0].name == "database"
    assert result.dependencies[0].healthy is False


def test_settings_rejects_unknown_environment() -> None:
    """An environment outside the documented set is a misconfiguration."""
    with pytest.raises(ValidationError):
        make_settings(environment="test")


def test_settings_requires_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The application refuses to start without PROJECTONE_ENVIRONMENT.

    Guards the deliberate absence of a default: if someone later adds one, the
    silent-wrong-mode failure this prevents comes back, and this test fails.
    """
    monkeypatch.delenv("PROJECTONE_ENVIRONMENT", raising=False)

    with pytest.raises(ValidationError) as caught:
        Settings(  # type: ignore[call-arg]
            _env_file=None,
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_SECRET_KEY="sb_secret_test",
            DATABASE_URL="postgresql://test:test@127.0.0.1:5432/test",
        )

    assert "environment" in str(caught.value)


def test_settings_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """The API will not start without a database to talk to."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError) as caught:
        Settings(  # type: ignore[call-arg]
            _env_file=None,
            environment=Environment.STAGING,
            SUPABASE_URL="https://test.supabase.co",
            SUPABASE_SECRET_KEY="sb_secret_test",
        )

    assert "DATABASE_URL" in str(caught.value)


def test_secrets_are_masked_in_representation() -> None:
    """Credentials must not leak through logs, reprs or tracebacks."""
    settings = make_settings()

    assert "test:test" not in repr(settings)
    assert "sb_secret_test" not in repr(settings)
    assert isinstance(settings.database_url, SecretStr)


def make_client(*, database_reachable: bool) -> TestClient:
    """Build a test client with the database dependency substituted."""
    app = create_app()
    app.dependency_overrides[get_database_repository] = lambda: StubDatabase(
        reachable=database_reachable
    )

    return TestClient(app)


def test_health_endpoint_returns_ok() -> None:
    response = make_client(database_reachable=True).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_endpoint_returns_503_when_database_is_down() -> None:
    """A degraded instance must say so in its status code.

    An orchestrator reads the code, not the body — reporting 200 while the
    database is unreachable would keep a broken instance in the load balancer.
    """
    response = make_client(database_reachable=False).get("/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
