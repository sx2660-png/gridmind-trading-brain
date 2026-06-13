"""End-to-end trading day workflow API models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.models.llm import LLMConfig


class TradingDayRunRequest(BaseModel):
    trade_date: str = Field(..., description="交易日，格式 YYYY-MM-DD")
    market_type: str = Field(default="day_ahead", description="市场类型，如 day_ahead")
    policy_query: Optional[str] = Field(
        default=None,
        description="政策检索问句；为空时使用默认问句",
    )
    as_of_datetime: Optional[datetime] = Field(
        default=None,
        description="信息截点；为空时默认使用交易日前一日 12:00",
    )
    llm: Optional[LLMConfig] = Field(
        default=None,
        description="可选：大模型配置，用于政策 Generation",
    )


class TradingDayRunResponse(BaseModel):
    trace_id: str
    trade_date: str
    status: str
    policy_output: dict = Field(
        default_factory=dict,
        description="政策 RAG：检索证据 + 生成结果",
    )
    policy_params: dict = Field(default_factory=dict)
    prediction_output: dict = Field(default_factory=dict)
    market_analysis: dict = Field(default_factory=dict)
    strategy_output: dict = Field(default_factory=dict)
    risk_check_result: dict = Field(default_factory=dict)
    execution_payload: dict = Field(default_factory=dict)
    human_review_required: bool = False
    audit_log: list[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    policy_generation_mode: Optional[str] = None
    interrupted: bool = False
    resume_endpoint: Optional[str] = None


class WorkflowResumeRequest(BaseModel):
    trace_id: str = Field(..., description="The trace_id / thread_id of the paused workflow")
    decision: str = Field(..., description="'approved' or 'rejected'")
    comment: str = Field(default="", description="Human reviewer's comment")


class WorkflowStatusResponse(BaseModel):
    trace_id: str
    status: str
    risk_status: str = "pending"
    execution_status: str = "pending"
    risk_flags: list[str] = Field(default_factory=list)
    human_review_decision: str = "pending"
    next_nodes: list[str] = Field(default_factory=list)
