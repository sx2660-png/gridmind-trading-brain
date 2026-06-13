"""Minimal Risk Agent for LangGraph electricity trading workflows."""

from __future__ import annotations

from typing import Any

from trading_state import TradingState


EXPECTED_CURVE_POINTS = 24
MAX_DECLARATION_DEVIATION = 0.05


def check_risk(state: TradingState) -> dict[str, Any]:
    """Validate a trading declaration before execution.

    This function is intentionally side-effect free: it accepts the shared
    TradingState and returns a plain dict update, which makes it compatible
    with LangGraph node passing and checkpointing.
    """
    risk_flags: list[str] = []

    # Rule A: the execution-facing declaration curve must be exactly 24 points.
    # The mock workflow uses hourly day-ahead curves; anything else cannot be
    # safely submitted to the virtual trading center.
    if len(state.declaration_curve_mwh) != EXPECTED_CURVE_POINTS:
        risk_flags.append(
            f"CURVE_LENGTH_INVALID: declaration_curve_mwh must contain "
            f"{EXPECTED_CURVE_POINTS} points, got {len(state.declaration_curve_mwh)}."
        )

    # Rule B1: the strategy and risk checks need day-ahead prices to evaluate
    # whether the declaration was built from a complete forecast.
    if not state.predicted_da_price:
        risk_flags.append("MISSING_FIELD: predicted_da_price cannot be empty.")

    # Rule B2: an empty declaration means there is nothing valid to submit.
    if not state.declaration_curve_mwh:
        risk_flags.append("MISSING_FIELD: declaration_curve_mwh cannot be empty.")

    # Rule C: compare declared MWh against predicted load. If any interval
    # deviates by more than 5%, return for recalculation. A zero predicted load
    # only allows a zero declaration for that interval.
    if state.declaration_curve_mwh and state.predicted_load_mwh:
        for index, (declaration, predicted_load) in enumerate(
            zip(state.declaration_curve_mwh, state.predicted_load_mwh), start=1
        ):
            if predicted_load == 0:
                if declaration != 0:
                    risk_flags.append(
                        f"DEVIATION_EXCEEDS_5_PERCENT: interval {index} has "
                        f"zero predicted load but declaration is {declaration} MWh."
                    )
                continue

            deviation = abs(declaration - predicted_load) / abs(predicted_load)
            if deviation > MAX_DECLARATION_DEVIATION:
                risk_flags.append(
                    f"DEVIATION_EXCEEDS_5_PERCENT: interval {index} declaration "
                    f"{declaration} MWh differs from predicted load {predicted_load} "
                    f"MWh by {deviation:.2%}."
                )

    # Rule C guardrail: if declaration/load curves have different lengths, the
    # deviation test may silently skip tail values via zip(), so flag it.
    if state.declaration_curve_mwh and state.predicted_load_mwh:
        if len(state.declaration_curve_mwh) != len(state.predicted_load_mwh):
            risk_flags.append(
                f"CURVE_LENGTH_MISMATCH: declaration_curve_mwh has "
                f"{len(state.declaration_curve_mwh)} points but predicted_load_mwh "
                f"has {len(state.predicted_load_mwh)} points."
            )

    # Rule D: if the Policy Agent provides a maintenance limit, every declared
    # interval must stay under that limit. This blocks declarations that violate
    # known outage, derating, or maintenance constraints.
    maintenance_limit = state.policy_rules.get("maintenance_limit_mwh")
    if maintenance_limit is not None:
        for index, declaration in enumerate(state.declaration_curve_mwh, start=1):
            if declaration > maintenance_limit:
                risk_flags.append(
                    f"MAINTENANCE_LIMIT_EXCEEDED: interval {index} declaration "
                    f"{declaration} MWh exceeds maintenance_limit_mwh "
                    f"{maintenance_limit} MWh."
                )

    # Rule E: market-anomaly warnings are not pure compliance violations, but a
    # high/critical alert means automatic declaration should pause for operator
    # review before submission.
    anomaly_level = state.market_anomaly.get("alert_level")
    if state.market_anomaly.get("requires_human_intervention"):
        risk_flags.append(
            "MARKET_ANOMALY_REQUIRES_HUMAN_REVIEW: "
            f"alert_level={anomaly_level}, score={state.market_anomaly.get('score', 0)}."
        )

    risk_status = _derive_risk_status(risk_flags)
    return {
        "risk_status": risk_status,
        "risk_flags": risk_flags,
    }


def _derive_risk_status(risk_flags: list[str]) -> str:
    """Map detailed flags to the workflow status expected by downstream nodes."""
    if not risk_flags:
        return "PASS"

    if any(flag.startswith(("MISSING_FIELD", "CURVE_LENGTH_INVALID")) for flag in risk_flags):
        return "REJECT"

    if any(flag.startswith(("DEVIATION_EXCEEDS_5_PERCENT", "CURVE_LENGTH_MISMATCH")) for flag in risk_flags):
        return "RETURN_FOR_RECALCULATION"

    if any(flag.startswith("MAINTENANCE_LIMIT_EXCEEDED") for flag in risk_flags):
        return "REQUIRES_HUMAN_REVIEW"

    if any(flag.startswith("MARKET_ANOMALY_REQUIRES_HUMAN_REVIEW") for flag in risk_flags):
        return "REQUIRES_HUMAN_REVIEW"

    return "REQUIRES_HUMAN_REVIEW"


# Example input and output for local testing and LangGraph node wiring.
example_input = TradingState(
    trace_id="trace-risk-demo-001",
    trading_date="2026-05-22",
    market_type="day_ahead",
    date_type="normal_day",
    predicted_da_price=[410.0] * 24,
    predicted_rt_price=[420.0] * 24,
    predicted_load_mwh=[100.0] * 24,
    mid_long_term_contract_mwh=[80.0] * 24,
    declaration_curve_mwh=[104.0] * 23 + [112.0],
    declaration_ratio=[1.04] * 23 + [1.12],
    policy_rules={"maintenance_limit_mwh": 110.0},
)

example_output = check_risk(example_input)


if __name__ == "__main__":
    print(example_output)
