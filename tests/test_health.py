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


def test_mock_endpoints() -> None:
    predict_response = client.post(
        "/mock/predict",
        json={"trading_date": "2026-05-25", "market_type": "day_ahead"},
    )
    assert predict_response.status_code == 200
    prediction = predict_response.json()
    assert len(prediction["predicted_da_price"]) == 24
    assert len(prediction["predicted_rt_price"]) == 24
    assert len(prediction["predicted_load_mwh"]) == 24

    strategy_response = client.post(
        "/mock/strategy",
        json={
            "predicted_da_price": prediction["predicted_da_price"],
            "predicted_rt_price": prediction["predicted_rt_price"],
            "predicted_load_mwh": prediction["predicted_load_mwh"],
            "mid_long_term_contract_mwh": [380.0] * 24,
        },
    )
    assert strategy_response.status_code == 200
    strategy = strategy_response.json()
    assert len(strategy["declaration_curve_mwh"]) == 24
    assert len(strategy["declaration_ratio"]) == 24

    execution_response = client.post(
        "/mock/execute",
        json={"declaration": {"trace_id": "mock-api-test", **strategy}},
    )
    assert execution_response.status_code == 200
    assert execution_response.json()["execution_status"] == "submitted"
