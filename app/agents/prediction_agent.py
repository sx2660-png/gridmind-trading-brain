"""Prediction Agent for electricity trading workflows."""

from __future__ import annotations

from datetime import datetime, timezone
import math
import random
from typing import Any

from pydantic import BaseModel, Field

from app.models.trading_state import TradingState


POINTS_PER_DAY = 24


class PredictionRequest(BaseModel):
    trading_date: str = Field(..., description="Target trading date, formatted as YYYY-MM-DD.")
    market_type: str = Field(default="day_ahead", description="Market type, such as day_ahead or real_time.")


class PredictionResponse(BaseModel):
    trading_date: str
    market_type: str
    predicted_da_price: list[float]
    predicted_rt_price: list[float]
    predicted_load_mwh: list[float]


def build_prediction(request: PredictionRequest) -> PredictionResponse:
    """Generate fake 24-point price and load curves with deterministic daily shape."""
    seed = f"{request.trading_date}:{request.market_type}"
    rng = random.Random(seed)
    day_factor = _day_factor(request.trading_date)

    load_baseline = _daily_load_baseline(day_factor)
    da_price_baseline = _daily_price_baseline(base_price=390.0 + day_factor * 12.0)

    predicted_load = [_round(value * rng.uniform(0.96, 1.05)) for value in load_baseline]
    predicted_da_price = [_round(value * rng.uniform(0.94, 1.07)) for value in da_price_baseline]
    predicted_rt_price = [
        _round(da_price * rng.uniform(0.92, 1.10) + rng.uniform(-12.0, 12.0))
        for da_price in predicted_da_price
    ]

    return PredictionResponse(
        trading_date=request.trading_date,
        market_type=request.market_type,
        predicted_da_price=predicted_da_price,
        predicted_rt_price=predicted_rt_price,
        predicted_load_mwh=predicted_load,
    )


def prediction_node(state: TradingState | dict[str, Any]) -> dict[str, Any]:
    """Prediction Agent node: produce mock price/load forecasts."""
    state = _as_state(state)
    _log_node("Prediction Agent", state)

    prediction = build_prediction(
        PredictionRequest(
            trading_date=state.trading_date,
            market_type=state.market_type,
        )
    )

    return {
        "predicted_da_price": prediction.predicted_da_price,
        "predicted_rt_price": prediction.predicted_rt_price,
        "predicted_load_mwh": prediction.predicted_load_mwh,
        "updated_at": _now(),
    }


def _daily_load_baseline(day_factor: float) -> list[float]:
    baseline: list[float] = []
    for hour in range(POINTS_PER_DAY):
        morning_peak = 90.0 * math.exp(-((hour - 10) ** 2) / 18.0)
        evening_peak = 130.0 * math.exp(-((hour - 20) ** 2) / 14.0)
        midday_solar_dip = 35.0 * math.exp(-((hour - 14) ** 2) / 10.0)
        value = 420.0 + day_factor * 30.0 + morning_peak + evening_peak - midday_solar_dip
        baseline.append(value)
    return baseline


def _daily_price_baseline(base_price: float) -> list[float]:
    baseline: list[float] = []
    for hour in range(POINTS_PER_DAY):
        evening_spread = 70.0 * math.exp(-((hour - 19) ** 2) / 12.0)
        noon_discount = 45.0 * math.exp(-((hour - 13) ** 2) / 8.0)
        value = base_price + evening_spread - noon_discount
        baseline.append(value)
    return baseline


def _day_factor(trading_date: str) -> float:
    try:
        date_value = datetime.strptime(trading_date, "%Y-%m-%d")
    except ValueError:
        return 0.0
    weekend_boost = 0.5 if date_value.weekday() >= 5 else 0.0
    seasonal = math.sin(date_value.timetuple().tm_yday / 365.0 * 2.0 * math.pi)
    return seasonal + weekend_boost


def _round(value: float) -> float:
    return round(value, 2)


def _as_state(state: TradingState | dict[str, Any]) -> TradingState:
    if isinstance(state, TradingState):
        return state
    return TradingState.model_validate(state)


def _log_node(node_name: str, state: TradingState) -> None:
    print(f"[{node_name}] current_node={node_name} trace_id={state.trace_id}")


def _now() -> datetime:
    return datetime.now(timezone.utc)
