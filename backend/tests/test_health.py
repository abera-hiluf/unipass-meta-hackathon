from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root_returns_application_metadata() -> None:
    response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "UniPass AI + AgentX"
    assert body["description"]
    assert body["docs"] == "/docs"


def test_health_returns_healthy_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_versioned_health_returns_v1_status() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "version": "v1"}
