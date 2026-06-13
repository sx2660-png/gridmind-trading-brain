"""Replay tests for market-anomaly driven day-ahead intervention."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo


def test_web_search_filters_results_after_as_of(monkeypatch) -> None:
    from app.services import web_search

    class FakeTavilyClient:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key

        def search(self, **kwargs):
            return {
                "results": [
                    {
                        "title": "广东电力现货市场价差提示",
                        "url": "https://example.test/before",
                        "content": "广东电力现货市场日前实时价差出现异常。",
                        "score": 0.9,
                        "published_date": "2026-05-24T11:30:00+08:00",
                    },
                    {
                        "title": "广东电力现货市场事后复盘",
                        "url": "https://example.test/after",
                        "content": "广东电力现货市场5月25日价格异常复盘。",
                        "score": 0.8,
                        "published_date": "2026-05-24T12:30:00+08:00",
                    },
                ]
            }

    import tavily

    monkeypatch.setattr(
        web_search,
        "get_settings",
        lambda: SimpleNamespace(tavily_api_key="fake-key", web_search_enabled=True),
    )
    monkeypatch.setattr(tavily, "TavilyClient", FakeTavilyClient)

    as_of = datetime(2026, 5, 24, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    results = web_search.search_power_market_news(
        query="日前 实时 价差 异常",
        trading_date="2026-05-25",
        as_of=as_of,
        max_results=5,
    )

    assert [item["url"] for item in results] == ["https://example.test/before"]
    assert results[0]["as_of_datetime"] == as_of.isoformat()


def test_enterprise_case_triggers_human_review(monkeypatch) -> None:
    from app.agents import web_search_agent
    from trading_state import TradingState
    from workflow_demo.main import _as_state, build_workflow

    def fake_search_power_market_news(**kwargs):
        assert kwargs["trading_date"] == "2026-05-25"
        assert kwargs["as_of"].isoformat() == "2026-05-24T12:00:00+08:00"
        return [
            {
                "title": "广东电力现货市场价格和价差异常提示",
                "url": "https://example.test/market-warning",
                "content": (
                    "广东电力现货市场日前和实时价差出现大幅变化，"
                    "价格规律突变，连续多日可能造成预测模型偏差。"
                    "建议售电公司复核申报策略，关注检修、断面约束和负荷变化。"
                ),
                "score": 0.95,
                "published_at": "2026-05-24T11:40:00+08:00",
                "source": "test_fixture",
            }
        ]

    monkeypatch.setattr(
        web_search_agent,
        "search_power_market_news",
        fake_search_power_market_news,
    )

    workflow = build_workflow()
    state = TradingState(
        trace_id="enterprise-replay-20260525",
        trading_date="2026-05-25",
        market_type="day_ahead",
        mid_long_term_contract_mwh=[380.0] * 24,
    )

    final = _as_state(workflow.invoke(state))

    assert final.market_anomaly["alert_level"] in ("HIGH", "CRITICAL")
    assert final.market_anomaly["requires_human_intervention"] is True
    assert "MARKET_ANOMALY_DEFENSIVE_ALIGN_TO_FORECAST_LOAD" in final.strategy_adjustments
    assert final.risk_status == "REQUIRES_HUMAN_REVIEW"
    assert any(flag.startswith("MARKET_ANOMALY_REQUIRES_HUMAN_REVIEW") for flag in final.risk_flags)
    assert final.execution_status == "paused_for_human_review"
