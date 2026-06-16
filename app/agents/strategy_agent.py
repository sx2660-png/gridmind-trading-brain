"""Strategy Agent for electricity trading workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.trading_state import TradingState


class StrategyRequest(BaseModel):
    predicted_da_price: list[float] = Field(..., min_length=24, max_length=24)
    predicted_rt_price: list[float] = Field(..., min_length=24, max_length=24)
    predicted_load_mwh: list[float] = Field(..., min_length=24, max_length=24)
    mid_long_term_contract_mwh: list[float] = Field(..., min_length=24, max_length=24)

    @model_validator(mode="after")
    def validate_curve_lengths(self) -> "StrategyRequest":
        lengths = {
            len(self.predicted_da_price),
            len(self.predicted_rt_price),
            len(self.predicted_load_mwh),
            len(self.mid_long_term_contract_mwh),
        }
        if lengths != {24}:
            raise ValueError("All strategy input curves must contain exactly 24 points.")
        return self


class StrategyResponse(BaseModel):
    declaration_curve_mwh: list[float]
    declaration_ratio: list[float]
    estimated_profit: float


def build_strategy(request: StrategyRequest) -> StrategyResponse:
    """Generate a simple ratio-based declaration plan."""
    declaration_curve: list[float] = []
    declaration_ratio: list[float] = []
    estimated_profit = 0.0

    for load, contract, da_price, rt_price in zip(
        request.predicted_load_mwh,
        request.mid_long_term_contract_mwh,
        request.predicted_da_price,
        request.predicted_rt_price,
    ):
        ratio = _declaration_ratio(da_price=da_price, rt_price=rt_price)
        target_mwh = load * ratio
        contract_gap = max(target_mwh - contract, 0.0)
        declaration_curve.append(round(target_mwh, 2))
        declaration_ratio.append(round(ratio, 4))
        estimated_profit += contract_gap * max(rt_price - da_price, 0.0)

    return StrategyResponse(
        declaration_curve_mwh=declaration_curve,
        declaration_ratio=declaration_ratio,
        estimated_profit=round(estimated_profit, 2),
    )


def strategy_node(state: TradingState | dict[str, Any]) -> dict[str, Any]:
    """Strategy Agent node: build or recalculate a declaration curve."""
    state = _as_state(state)
    _log_node("Strategy Agent", state)

    strategy = build_strategy(
        StrategyRequest(
            predicted_da_price=state.predicted_da_price,
            predicted_rt_price=state.predicted_rt_price,
            predicted_load_mwh=state.predicted_load_mwh,
            mid_long_term_contract_mwh=state.mid_long_term_contract_mwh,
        )
    )

    declaration_curve = strategy.declaration_curve_mwh
    declaration_ratio = strategy.declaration_ratio
    strategy_adjustments: list[str] = []

    if state.risk_status == "RETURN_FOR_RECALCULATION":
        print(f"[Strategy Agent] trace_id={state.trace_id} recalculating declaration after risk feedback")
        declaration_curve = [round(load, 2) for load in state.predicted_load_mwh]
        declaration_ratio = [1.0 for _ in state.predicted_load_mwh]
        strategy_adjustments.append("RISK_RECALCULATION_ALIGN_TO_FORECAST_LOAD")

    anomaly_level = state.market_anomaly.get("alert_level", "NONE")
    if anomaly_level in ("HIGH", "CRITICAL", "UNKNOWN"):
        print(
            f"[Strategy Agent] trace_id={state.trace_id} "
            f"market_anomaly={anomaly_level}; applying defensive declaration"
        )
        declaration_curve = [round(load, 2) for load in state.predicted_load_mwh]
        declaration_ratio = [1.0 for _ in state.predicted_load_mwh]
        strategy_adjustments.append("MARKET_ANOMALY_DEFENSIVE_ALIGN_TO_FORECAST_LOAD")

    print(f"[Strategy Agent] trace_id={state.trace_id} estimated_profit={strategy.estimated_profit}")
    return {
        "declaration_curve_mwh": declaration_curve,
        "declaration_ratio": declaration_ratio,
        "strategy_adjustments": strategy_adjustments,
        "risk_status": "pending",
        "risk_flags": [],
        "updated_at": _now(),
    }


def _declaration_ratio(da_price: float, rt_price: float) -> float:
    price_spread = rt_price - da_price
    if price_spread > 30.0:
        return 1.03
    if price_spread > 10.0:
        return 1.01
    if price_spread < -30.0:
        return 0.94
    if price_spread < -10.0:
        return 0.97
    return 0.99


def _as_state(state: TradingState | dict[str, Any]) -> TradingState:
    if isinstance(state, TradingState):
        return state
    return TradingState.model_validate(state)


def _log_node(node_name: str, state: TradingState) -> None:
    print(f"[{node_name}] current_node={node_name} trace_id={state.trace_id}")


def _now() -> datetime:
    return datetime.now(timezone.utc)
