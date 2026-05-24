"""Mock strategy API for electricity trading workflow tests."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


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
