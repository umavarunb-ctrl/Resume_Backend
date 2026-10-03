from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


def test_health_check_returns_200() -> None:
    """Verify GET /api/health returns 200 with the expected payload structure."""
    response = client.get("/api/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == settings.APP_NAME
    assert data["version"] == settings.APP_VERSION


def test_health_check_headers() -> None:
    """Verify GET /api/health returns application/json content type."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
