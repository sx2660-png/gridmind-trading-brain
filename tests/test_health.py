"""Smoke tests for API health endpoints."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_demo_state() -> None:
    response = client.get("/demo/state")
    assert response.status_code == 200
    body = response.json()
    assert body["trace_id"] == "demo-trace-001"
    assert "prediction_output" in body
