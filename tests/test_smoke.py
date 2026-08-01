"""Smoke tests verifying the FastAPI application boots."""

from fastapi.testclient import TestClient

from backend.app.main import app


def test_root() -> None:
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "keeperpilot-backend"


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["keeperhub_mock"] == "true"
