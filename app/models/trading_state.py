"""Shared LangGraph state model for the electricity trading agents."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class TradingState(BaseModel):
    """State object passed between Policy, Prediction, Strategy, Risk, and Execution agents."""

    trace_id: str
    trading_date: str
    market_type: str = "day_ahead"
    as_of_datetime: datetime | None = None
    date_type: str = "normal_day"

    predicted_load_mwh: list[float] = Field(default_factory=list)
    predicted_da_price: list[float] = Field(default_factory=list)
    predicted_rt_price: list[float] = Field(default_factory=list)
    mid_long_term_contract_mwh: list[float] = Field(default_factory=list)

    declaration_curve_mwh: list[float] = Field(default_factory=list)
    declaration_ratio: list[float] = Field(default_factory=list)

    policy_rules: dict = Field(default_factory=dict)
    risk_flags: list[str] = Field(default_factory=list)
    web_search_results: list[dict] = Field(default_factory=list)
    market_anomaly: dict = Field(default_factory=dict)
    strategy_adjustments: list[str] = Field(default_factory=list)

    risk_status: str = "pending"
    execution_status: str = "pending"
    human_review_decision: str = "pending"
    human_review_comment: str = ""

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


example_state = TradingState(
    trace_id="trace-20260522-001",
    trading_date="2026-05-22",
    market_type="day_ahead",
    date_type="normal_day",
    predicted_load_mwh=[100.0, 105.5, 98.2],
    predicted_da_price=[420.0, 415.5, 430.2],
    predicted_rt_price=[425.0, 418.0, 435.0],
    mid_long_term_contract_mwh=[80.0, 82.0, 79.5],
    declaration_curve_mwh=[95.0, 100.0, 96.0],
    declaration_ratio=[0.95, 0.95, 0.98],
    policy_rules={
        "region": "guangdong",
        "market_stage": "day_ahead",
        "time_resolution": {"interval_minutes": 15, "points_per_day": 96},
    },
    risk_flags=[],
    risk_status="pending",
    execution_status="pending",
)
