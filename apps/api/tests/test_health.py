"""Tests for the health endpoint and its service.

Two levels deliberately: the service is tested without HTTP, proving business
logic is testable independent of the web framework (CLAUDE.md 18), and the
route is tested through the app, proving the wiring works.
"""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Environment, Settings
from app.main import create_app
from app.services.health_service import HealthService


def test_health_service_reports_ok_without_http() -> None:
    settings = Settings(
        app_name="Test API",
        environment=Environment.STAGING,
        version="9.9.9",
    )

    result = HealthService(settings).check()

    assert result.status == "ok"
    assert result.service == "Test API"
    assert result.environment == "staging"
    assert result.version == "9.9.9"


def test_settings_rejects_unknown_environment() -> None:
    """An environment outside the documented set is a misconfiguration."""
    with pytest.raises(ValidationError):
        Settings(environment="test")  # type: ignore[arg-type]


def test_settings_requires_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """The application refuses to start without PROJECTONE_ENVIRONMENT.

    Guards the deliberate absence of a default: if someone later adds one, the
    silent-wrong-mode failure this prevents comes back, and this test fails.
    """
    monkeypatch.delenv("PROJECTONE_ENVIRONMENT", raising=False)

    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None)  # type: ignore[call-arg]

    assert "environment" in str(caught.value)


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
