"""Web Search Agent node for LangGraph electricity trading workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.web_search import search_power_market_news


def web_search_node(state) -> dict[str, Any]:
    """Enrich policy context with market news and expert opinions."""
    from trading_state import TradingState

    if isinstance(state, dict):
        state = TradingState.model_validate(state)

    print(f"[Web Search Agent] trace_id={state.trace_id} searching market news")

    results = search_power_market_news(
        query="日前交易 申报 电价趋势 偏差考核",
        trading_date=state.trading_date,
        max_results=5,
    )

    print(f"[Web Search Agent] trace_id={state.trace_id} found {len(results)} results")

    return {
        "web_search_results": results,
        "updated_at": datetime.now(timezone.utc),
    }
