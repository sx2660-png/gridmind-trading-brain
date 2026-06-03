"""Web search service for power market news and expert opinions via Tavily API."""

from __future__ import annotations

from app.core.config import get_settings

DEFAULT_INCLUDE_DOMAINS = [
    "gd.csg.cn",
    "occ.csg.cn",
    "nea.gov.cn",
    "ndrc.gov.cn",
    "mp.weixin.qq.com",
]


def search_power_market_news(
    query: str,
    trading_date: str,
    max_results: int = 5,
    include_domains: list[str] | None = None,
) -> list[dict]:
    """Search for power market news and expert opinions.

    Returns an empty list when the Tavily API key is not configured,
    so the workflow degrades gracefully without web search.
    """
    settings = get_settings()
    if not settings.tavily_api_key or not settings.web_search_enabled:
        return []

    from tavily import TavilyClient

    client = TavilyClient(api_key=settings.tavily_api_key)
    search_query = f"广东电力市场 {query} {trading_date}"
    domains = include_domains or DEFAULT_INCLUDE_DOMAINS

    try:
        response = client.search(
            query=search_query,
            search_depth="advanced",
            max_results=max_results,
            include_domains=domains,
        )
    except Exception:
        return []

    results = []
    for item in response.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
            "score": item.get("score", 0.0),
            "source": "tavily_web_search",
        })
    return results
