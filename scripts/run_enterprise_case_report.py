"""Generate a replay report for the Guangdong market anomaly enterprise case."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.trading_state import TradingState
from app.services.workflow_graph import _as_state, build_workflow


TRADE_DATES = ["2026-05-25", "2026-05-26", "2026-05-27"]
REPORT_PATH = PROJECT_ROOT / "docs" / "reports" / "enterprise_case_market_anomaly_report.md"


def main() -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    runs = [_run_case(trade_date) for trade_date in TRADE_DATES]
    report = _render_report(runs)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"Saved report: {REPORT_PATH}")
    print(report)


def _run_case(trade_date: str) -> dict[str, Any]:
    state = TradingState(
        trace_id=f"enterprise-case-{trade_date}",
        trading_date=trade_date,
        market_type="day_ahead",
        mid_long_term_contract_mwh=[380.0] * 24,
    )
    final = _as_state(build_workflow().invoke(state))
    return {
        "trade_date": trade_date,
        "as_of": final.as_of_datetime.isoformat() if final.as_of_datetime else "",
        "web_search_results_count": len(final.web_search_results),
        "market_anomaly": final.market_anomaly,
        "strategy_adjustments": final.strategy_adjustments,
        "risk_status": final.risk_status,
        "risk_flags": final.risk_flags,
        "execution_status": final.execution_status,
        "declaration_ratio_min": min(final.declaration_ratio) if final.declaration_ratio else None,
        "declaration_ratio_max": max(final.declaration_ratio) if final.declaration_ratio else None,
    }


def _render_report(runs: list[dict[str, Any]]) -> str:
    generated_at = datetime.now().isoformat(timespec="seconds")
    lines = [
        "# Enterprise Case Market Anomaly Replay Report",
        "",
        f"Generated at: `{generated_at}`",
        "",
        "Scenario: day-ahead declaration replay for Guangdong spot market anomaly on 2026-05-25 to 2026-05-27.",
        "Information cutoff: D-1 12:00 Asia/Shanghai for each trading date.",
        "",
        "## Summary",
        "",
        "| Trade Date | As Of | Search Results | Alert Level | Human Review | Strategy Adjustment | Risk Status | Execution Status |",
        "|---|---|---:|---|---|---|---|---|",
    ]

    for run in runs:
        anomaly = run["market_anomaly"]
        lines.append(
            "| {trade_date} | {as_of} | {count} | {level} | {review} | {adjustment} | {risk} | {execution} |".format(
                trade_date=run["trade_date"],
                as_of=run["as_of"],
                count=run["web_search_results_count"],
                level=anomaly.get("alert_level", ""),
                review=anomaly.get("requires_human_intervention", ""),
                adjustment=", ".join(run["strategy_adjustments"]) or "-",
                risk=run["risk_status"],
                execution=run["execution_status"],
            )
        )

    for run in runs:
        anomaly = run["market_anomaly"]
        signals = anomaly.get("signals", [])
        evidence = anomaly.get("evidence", [])

        lines.extend(
            [
                "",
                f"## {run['trade_date']}",
                "",
                f"- As of: `{run['as_of']}`",
                f"- Alert level: `{anomaly.get('alert_level', '')}`",
                f"- Market score: `{anomaly.get('score', '')}`",
                f"- Requires human intervention: `{anomaly.get('requires_human_intervention', '')}`",
                f"- Risk status: `{run['risk_status']}`",
                f"- Execution status: `{run['execution_status']}`",
                f"- Strategy adjustments: `{', '.join(run['strategy_adjustments']) or '-'}`",
                f"- Declaration ratio min/max: `{run['declaration_ratio_min']}` / `{run['declaration_ratio_max']}`",
                "",
                "### Signals",
                "",
            ]
        )

        if signals:
            for signal in signals:
                lines.append(
                    "- `{code}` ({count} evidence): {description}".format(
                        code=signal.get("code", ""),
                        count=signal.get("evidence_count", 0),
                        description=signal.get("description", ""),
                    )
                )
        else:
            lines.append("- No signals.")

        lines.extend(["", "### Evidence", ""])
        if evidence:
            for index, item in enumerate(evidence, start=1):
                lines.extend(
                    [
                        f"#### Evidence {index}",
                        "",
                        f"- Title: {item.get('title', '')}",
                        f"- URL: {item.get('url', '') or '-'}",
                        f"- Published at: `{item.get('published_at') or '-'}`",
                        f"- Search score: `{item.get('score', '')}`",
                        f"- Matched signals: `{', '.join(item.get('signals', [])) or '-'}`",
                        "",
                        "Excerpt:",
                        "",
                        f"> {_quote_text(item.get('excerpt', ''))}",
                        "",
                    ]
                )
        else:
            lines.append("No evidence captured.")

        actions = anomaly.get("recommended_actions", [])
        lines.extend(["", "### Recommended Actions", ""])
        if actions:
            for action in actions:
                lines.append(f"- {action}")
        else:
            lines.append("- No actions.")

    lines.append("")
    return "\n".join(lines)


def _quote_text(text: str) -> str:
    compact = " ".join(str(text).split())
    return compact.replace("\n", " ")


if __name__ == "__main__":
    main()
