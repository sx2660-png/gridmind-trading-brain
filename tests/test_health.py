"""Smoke tests for API health endpoints."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["ui"] == "/ui"


def test_ui_page() -> None:
    response = client.get("/ui")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "电力交易大脑" in response.text


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


def test_policy_status() -> None:
    response = client.get("/policy/status")
    assert response.status_code == 200
    body = response.json()
    assert "index_path" in body
    assert "embedding_model" in body
