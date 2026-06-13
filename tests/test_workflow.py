"""End-to-end trading day workflow tests."""

from pathlib import Path

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_workflow_run_returns_result(tmp_path: Path, monkeypatch) -> None:
    articles = tmp_path / "articles"
    articles.mkdir()
    (articles / "rule.txt").write_text(
        "广东电力市场日前交易采用96点申报曲线。偏差考核按照结算规则处理。",
        encoding="utf-8",
    )
    index_path = tmp_path / "policy_index.json"
    checkpoint_path = tmp_path / "checkpoints.sqlite"

    monkeypatch.setenv("POLICY_ARTICLES_DIR", str(articles))
    monkeypatch.setenv("POLICY_INDEX_PATH", str(index_path))
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(checkpoint_path))
    monkeypatch.setenv("TAVILY_API_KEY", "")

    from app.core import config
    from app.services import workflow_factory

    config.get_settings.cache_clear()
    workflow_factory._workflow = None
    workflow_factory._checkpointer = None

    response = client.post(
        "/workflow/run",
        json={"trade_date": "2026-05-22", "market_type": "day_ahead"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["trade_date"] == "2026-05-22"
    assert body["trace_id"].startswith("trace-20260522-")
    assert body["policy_params"]
    assert body["risk_check_result"]["risk_status"]
    assert body["execution_payload"]["declaration_curve_mwh"]

    config.get_settings.cache_clear()
    workflow_factory._workflow = None
    workflow_factory._checkpointer = None


def test_workflow_run_legacy(tmp_path: Path, monkeypatch) -> None:
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
        "/workflow/run-legacy",
        json={"trade_date": "2026-05-22", "market_type": "day_ahead"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["trace_id"].startswith("trace-20260522-")
    assert body["policy_params"]

    config.get_settings.cache_clear()


def test_langgraph_workflow_standalone(tmp_path: Path, monkeypatch) -> None:
    """Test the LangGraph workflow directly (not via API)."""
    import sys
    import sqlite3

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

    monkeypatch.setenv("TAVILY_API_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "")

    from app.core import config

    config.get_settings.cache_clear()

    from langgraph.checkpoint.sqlite import SqliteSaver
    from workflow_demo.main import build_workflow, _as_state
    from trading_state import TradingState

    conn = sqlite3.connect(str(tmp_path / "test.sqlite"), check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()

    workflow = build_workflow(checkpointer=checkpointer)
    state = TradingState(
        trace_id="test-standalone-001",
        trading_date="2026-06-01",
        market_type="day_ahead",
        mid_long_term_contract_mwh=[380.0] * 24,
    )
    workflow_config = {"configurable": {"thread_id": state.trace_id}}
    result = workflow.invoke(state, config=workflow_config)
    final = _as_state(result)

    assert final.risk_status == "PASS"
    assert final.execution_status == "submitted"
    assert len(final.declaration_curve_mwh) == 24
    assert final.policy_rules

    config.get_settings.cache_clear()


def test_workflow_status_endpoint(tmp_path: Path, monkeypatch) -> None:
    checkpoint_path = tmp_path / "checkpoints.sqlite"
    articles = tmp_path / "articles"
    articles.mkdir()
    (articles / "rule.txt").write_text("广东电力市场日前交易", encoding="utf-8")

    monkeypatch.setenv("POLICY_ARTICLES_DIR", str(articles))
    monkeypatch.setenv("POLICY_INDEX_PATH", str(tmp_path / "idx.json"))
    monkeypatch.setenv("CHECKPOINT_DB_PATH", str(checkpoint_path))
    monkeypatch.setenv("TAVILY_API_KEY", "")

    from app.core import config
    from app.services import workflow_factory

    config.get_settings.cache_clear()
    workflow_factory._workflow = None
    workflow_factory._checkpointer = None

    run_resp = client.post(
        "/workflow/run",
        json={"trade_date": "2026-06-01"},
    )
    assert run_resp.status_code == 200
    trace_id = run_resp.json()["trace_id"]

    status_resp = client.get(f"/workflow/status/{trace_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["trace_id"] == trace_id

    config.get_settings.cache_clear()
    workflow_factory._workflow = None
    workflow_factory._checkpointer = None
