from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import app
from app.db import get_db, normalize_database_url


client = TestClient(app)


def test_database_url_normalization_preserves_connection_details() -> None:
    url = "postgresql://user:@p%40ss@pooler.supabase.com:5432/postgres"

    assert normalize_database_url(url) == (
        "postgresql+psycopg://user:%40p%40ss@pooler.supabase.com:5432/postgres"
    )


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


class FakeDatabase:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.executed = []

    def execute(self, statement):
        if self.error:
            raise self.error
        self.executed.append(str(statement))


def test_database_health_uses_select_one_without_a_real_database() -> None:
    database = FakeDatabase()

    def override_get_db():
        yield database

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/api/v1/db-health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "database"}
    assert database.executed == ["SELECT 1"]


def test_database_health_hides_database_errors() -> None:
    database = FakeDatabase(error=OperationalError("SELECT 1", {}, Exception("secret")))

    def override_get_db():
        yield database

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/api/v1/db-health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "service": "database"}
    assert "secret" not in response.text
