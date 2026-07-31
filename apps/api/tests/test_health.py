"""Tests for the health endpoint and its service.

Two levels deliberately: the service is tested without HTTP, proving business
logic is testable independent of the web framework (CLAUDE.md 18), and the
route is tested through the app, proving the wiring works.
"""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.health_service import HealthService


def test_health_service_reports_ok_without_http() -> None:
    settings = Settings(app_name="Test API", environment="test", version="9.9.9")

    result = HealthService(settings).check()

    assert result.status == "ok"
    assert result.service == "Test API"
    assert result.environment == "test"
    assert result.version == "9.9.9"


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
