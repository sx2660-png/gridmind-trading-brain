"""Shared LangGraph state model for the electricity trading agents."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class TradingState(BaseModel):
    """State object passed between Policy, Prediction, Strategy, Risk, and Execution agents."""

    # Unique trace id for audit logs, debugging, and LangGraph checkpoint lookup.
    trace_id: str

    # Target trading date, usually formatted as YYYY-MM-DD.
    trading_date: str

    # Market type for this workflow, for example day_ahead, real_time, or mid_long_term.
    market_type: str = "day_ahead"

    # Calendar/date classification, for example normal_day, weekend, holiday, or peak_day.
    date_type: str = "normal_day"

    # Prediction Agent output: forecasted load curve in MWh.
    predicted_load_mwh: list[float] = Field(default_factory=list)

    # Prediction Agent output: forecasted day-ahead market price curve.
    predicted_da_price: list[float] = Field(default_factory=list)

    # Prediction Agent output: forecasted real-time market price curve.
    predicted_rt_price: list[float] = Field(default_factory=list)

    # Existing mid/long-term contracted electricity curve in MWh.
    mid_long_term_contract_mwh: list[float] = Field(default_factory=list)

    # Strategy Agent output: final declaration curve to submit, in MWh.
    declaration_curve_mwh: list[float] = Field(default_factory=list)

    # Strategy Agent output: declaration ratio by trading interval.
    declaration_ratio: list[float] = Field(default_factory=list)

    # Policy Agent output: structured policy/rule parameters used by downstream agents.
    policy_rules: dict = Field(default_factory=dict)

    # Risk Agent output: rule violations, warnings, or review flags.
    risk_flags: list[str] = Field(default_factory=list)

    # Risk workflow status, for example pending, passed, warning, or blocked.
    risk_status: str = "pending"

    # Execution workflow status, for example pending, submitted, failed, or cancelled.
    execution_status: str = "pending"

    # State creation timestamp, useful for checkpointing and audit trails.
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Last update timestamp; nodes should refresh this when they mutate the state.
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Example state object for local testing and LangGraph node input examples.
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
