"""Web Search Agent node for LangGraph electricity trading workflows."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.services.market_anomaly import extract_market_anomaly
from app.services.web_search import search_power_market_news


MARKET_REPLAY_QUERY = (
    "广东电力现货市场 日前 实时 价格 价差 异常 预测偏差 "
    "出清 负荷 检修 规则调整 申报策略"
)


def web_search_node(state) -> dict[str, Any]:
    """Enrich policy context with market news and expert opinions."""
    from trading_state import TradingState

    if isinstance(state, dict):
        state = TradingState.model_validate(state)

    as_of = state.as_of_datetime or default_decision_cutoff(state.trading_date)

    print(
        f"[Web Search Agent] trace_id={state.trace_id} "
        f"searching market news as_of={as_of.isoformat()}"
    )

    results = search_power_market_news(
        query=MARKET_REPLAY_QUERY,
        trading_date=state.trading_date,
        as_of=as_of,
        max_results=5,
    )

    market_anomaly = extract_market_anomaly(
        trading_date=state.trading_date,
        as_of=as_of,
        search_results=results,
    )

    print(
        f"[Web Search Agent] trace_id={state.trace_id} found {len(results)} results "
        f"alert_level={market_anomaly['alert_level']}"
    )

    return {
        "as_of_datetime": as_of,
        "web_search_results": results,
        "market_anomaly": market_anomaly,
        "updated_at": datetime.now(timezone.utc),
    }


def default_decision_cutoff(trading_date: str) -> datetime:
    """Return D-1 12:00 Asia/Shanghai for day-ahead declaration replay."""
    market_tz = ZoneInfo("Asia/Shanghai")
    trade_day = datetime.fromisoformat(trading_date).date()
    decision_day = trade_day - timedelta(days=1)
    return datetime.combine(decision_day, time(hour=12), tzinfo=market_tz)
