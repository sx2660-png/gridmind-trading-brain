"""End-to-end trading day workflow tests."""

from pathlib import Path

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_workflow_run_returns_mock_payload(tmp_path: Path, monkeypatch) -> None:
    # Use isolated policy docs so CI does not depend on large PDFs.
    articles = tmp_path / "articles"
    articles.mkdir()
    (articles / "rule.txt").write_text(
        "广东电力市场日前交易采用96点申报曲线。偏差考核按照结算规则处理。",
        encoding="utf-8",
    )
    index_path = tmp_path / "policy_index.json"

    monkeypatch.setenv("POLICY_ARTICLES_DIR", str(articles))
    monkeypatch.setenv("POLICY_INDEX_PATH", str(index_path))

    from app.core import config

    config.get_settings.cache_clear()

    response = client.post(
        "/workflow/run",
        json={"trade_date": "2026-05-22", "market_type": "day_ahead"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["trade_date"] == "2026-05-22"
    assert body["trace_id"].startswith("trace-20260522-")
    assert body["policy_output"]["evidence"] is not None
    assert body["policy_params"]
    assert body["prediction_output"]["predicted_load_mwh"]
    assert len(body["prediction_output"]["predicted_load_mwh"]) == 24
    assert body["strategy_output"]["declaration_curve_mwh"]
    assert body["risk_check_result"]["risk_status"]
    assert body["execution_payload"]["message_type"] == "day_ahead_declaration"
    assert body["execution_payload"]["declaration_curve_mwh"]
    assert "submission" in body["execution_payload"]
    assert body["audit_log"]

    config.get_settings.cache_clear()
