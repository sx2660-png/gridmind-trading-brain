"""Market anomaly signal extraction for replayable trading decisions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any


@dataclass(frozen=True)
class SignalRule:
    code: str
    pattern: str
    weight: int
    description: str


SIGNAL_RULES = [
    SignalRule("PRICE_SPREAD_SHIFT", r"价差|价差扩大|价差收窄|日前.*实时|实时.*日前|倒挂", 3, "日前/实时价差或价差结构出现变化"),
    SignalRule("PRICE_REGIME_SHIFT", r"价格规律|价格结构|出清价格|节点电价|统一结算点.*变化|电价.*突变", 3, "现货价格规律或出清结构出现变化"),
    SignalRule("ABNORMAL_MOVE", r"异常|极端|剧烈|大幅|显著|突变|波动加剧|超预期", 4, "市场出现异常或超预期波动描述"),
    SignalRule("CONSECUTIVE_EVENT", r"连续[一二三四五六七八九十0-9]+天|连续", 2, "异常信号具有连续性"),
    SignalRule("FORECAST_BREAKDOWN", r"预测偏差|预测失准|模型偏差|预测模型|负荷预测.*偏差", 4, "预测模型或负荷预测存在失准风险"),
    SignalRule("SUPPLY_DEMAND_STRESS", r"高温|负荷攀升|负荷高峰|供应紧张|备用不足|新能源出力下降|风光出力下降", 2, "供需或天气因素可能冲击现货价格"),
    SignalRule("GRID_CONSTRAINT", r"检修|断面约束|阻塞|受限|必开|必停|安全约束", 2, "电网或机组约束可能改变价格形成"),
    SignalRule("RULE_OR_PARAMETER_CHANGE", r"规则调整|参数调整|结算规则|考核|A0|D1|回收|披露", 3, "规则、结算或考核参数可能影响申报收益"),
    SignalRule("MARKET_SUSPENSION", r"熔断|暂停|中止|应急|保供", 5, "市场运行机制可能进入特殊状态"),
]


def extract_market_anomaly(
    *,
    trading_date: str,
    as_of: datetime | None,
    search_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Extract deterministic market warning signals from search evidence."""
    search_errors = [
        item for item in search_results
        if item.get("source") == "tavily_web_search_error" or item.get("error")
    ]
    if search_errors:
        return {
            "trading_date": trading_date,
            "as_of_datetime": as_of.isoformat() if as_of else None,
            "alert_level": "UNKNOWN",
            "score": 0,
            "requires_human_intervention": True,
            "signals": [
                {
                    "code": "WEB_SEARCH_UNAVAILABLE",
                    "description": "联网搜索不可用，无法确认申报截点前是否存在市场异常信息",
                    "weight": 0,
                    "evidence_count": len(search_errors),
                }
            ],
            "evidence": [
                {
                    "title": item.get("title", "WEB_SEARCH_ERROR"),
                    "url": item.get("url", ""),
                    "published_at": item.get("published_at"),
                    "score": item.get("score", 0.0),
                    "signals": ["WEB_SEARCH_UNAVAILABLE"],
                    "excerpt": str(item.get("error", ""))[:220],
                }
                for item in search_errors[:3]
            ],
            "recommended_actions": [
                "暂停自动提交，转人工确认外部市场信息",
                "检查 Tavily/API 网络连通性和搜索源可用性",
            ],
        }

    evidence: list[dict[str, Any]] = []
    signals_by_code: dict[str, dict[str, Any]] = {}
    score = 0

    for item in search_results:
        title = str(item.get("title", ""))
        content = str(item.get("content", ""))
        text = f"{title}\n{content}"
        if not _is_relevant_to_guangdong_spot(text):
            continue

        item_signals = []
        for rule in SIGNAL_RULES:
            if re.search(rule.pattern, text, flags=re.IGNORECASE):
                item_signals.append(rule.code)
                if rule.code not in signals_by_code:
                    signals_by_code[rule.code] = {
                        "code": rule.code,
                        "description": rule.description,
                        "weight": rule.weight,
                        "evidence_count": 0,
                    }
                    score += rule.weight
                signals_by_code[rule.code]["evidence_count"] += 1

        if item_signals:
            evidence.append(
                {
                    "title": title,
                    "url": item.get("url", ""),
                    "published_at": item.get("published_at"),
                    "score": item.get("score", 0.0),
                    "signals": item_signals,
                    "excerpt": _excerpt(text),
                }
            )

    alert_level = _alert_level(score=score, signal_count=len(signals_by_code))
    requires_intervention = alert_level in ("HIGH", "CRITICAL")
    recommended_actions = _recommended_actions(alert_level)

    return {
        "trading_date": trading_date,
        "as_of_datetime": as_of.isoformat() if as_of else None,
        "alert_level": alert_level,
        "score": score,
        "requires_human_intervention": requires_intervention,
        "signals": list(signals_by_code.values()),
        "evidence": evidence[:5],
        "recommended_actions": recommended_actions,
    }


def _is_relevant_to_guangdong_spot(text: str) -> bool:
    return ("广东" in text or "南方" in text) and ("现货" in text or "日前" in text or "实时" in text)


def _alert_level(*, score: int, signal_count: int) -> str:
    if score >= 11 or signal_count >= 5:
        return "CRITICAL"
    if score >= 7 or signal_count >= 3:
        return "HIGH"
    if score >= 4 or signal_count >= 2:
        return "MEDIUM"
    if score > 0:
        return "LOW"
    return "NONE"


def _recommended_actions(alert_level: str) -> list[str]:
    if alert_level in ("HIGH", "CRITICAL"):
        return [
            "暂停自动提交，转人工复核申报策略",
            "收敛价差驱动的投机性申报偏移，优先贴近最新负荷预测",
            "复核日前/实时价差、约束、检修、规则参数和披露信息",
        ]
    if alert_level == "MEDIUM":
        return [
            "保留自动申报但提高监控等级",
            "降低价差驱动的申报偏移幅度",
        ]
    if alert_level == "LOW":
        return ["记录预警线索，维持常规申报策略"]
    return []


def _excerpt(text: str, limit: int = 220) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "..."
