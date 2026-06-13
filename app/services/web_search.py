"""Web search service for power market news and expert opinions via Tavily API."""

from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

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
    as_of: datetime | None = None,
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
    if as_of is not None:
        search_query += f" 截至 {as_of.strftime('%Y-%m-%d %H:%M')} 前"
    domains = include_domains or DEFAULT_INCLUDE_DOMAINS

    try:
        response = client.search(
            query=search_query,
            search_depth="advanced",
            max_results=max_results,
            include_domains=domains,
        )
    except Exception as exc:
        return [
            {
                "title": "WEB_SEARCH_ERROR",
                "url": "",
                "content": "",
                "score": 0.0,
                "published_at": None,
                "as_of_datetime": as_of.isoformat() if as_of else None,
                "publication_time_verified": False,
                "source": "tavily_web_search_error",
                "error": str(exc),
            }
        ]

    results = []
    for item in response.get("results", []):
        published_at = _extract_published_at(item)
        if as_of is not None and published_at is not None:
            if _normalize_datetime(published_at) > _normalize_datetime(as_of):
                continue

        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("content", ""),
            "score": item.get("score", 0.0),
            "published_at": published_at.isoformat() if published_at else None,
            "as_of_datetime": as_of.isoformat() if as_of else None,
            "publication_time_verified": published_at is not None,
            "source": "tavily_web_search",
        })
    return results


def _extract_published_at(item: dict[str, Any]) -> datetime | None:
    for key in ("published_at", "published_date", "date"):
        value = item.get(key)
        if not value:
            continue
        parsed = _parse_datetime(value)
        if parsed is not None:
            return parsed
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass

    try:
        return parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone().replace(tzinfo=None)
