"""Trading workflow state model."""

from typing import Optional

from pydantic import BaseModel, Field


class TradingState(BaseModel):
    trace_id: str
    trade_date: str
    policy_params: dict = Field(default_factory=dict)
    prediction_output: dict = Field(default_factory=dict)
    strategy_output: dict = Field(default_factory=dict)
    risk_check_result: dict = Field(default_factory=dict)
    execution_payload: dict = Field(default_factory=dict)
    audit_log: list = Field(default_factory=list)
    human_review_required: bool = False
    status: str = "pending"
    error_message: Optional[str] = None
