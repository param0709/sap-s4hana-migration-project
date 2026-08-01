"""Health endpoint test."""
from app.config import settings


def test_health_reports_ok_and_database_up(client):
    response = client.get(f"{settings.api_prefix}/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"
    assert body["service"] == settings.app_name
