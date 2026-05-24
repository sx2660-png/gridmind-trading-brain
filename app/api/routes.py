"""API route definitions."""

from pathlib import Path

from fastapi import APIRouter

from app.agents.policy_agent import PolicyAgent
from app.core.config import settings
from app.models.policy import PolicyIndexStatus, PolicyQueryRequest, PolicyQueryResponse
from app.models.workflow import TradingDayRunRequest, TradingDayRunResponse
from app.services.trading_pipeline import run_trading_day
from app.models.prediction import PredictionOutput
from app.models.risk import RiskCheckOutput
from app.models.state import TradingState
from app.models.strategy import StrategyOutput

router = APIRouter(tags=["api"])


def get_policy_agent() -> PolicyAgent:
    return PolicyAgent(
        source_dir=Path(settings.policy_articles_dir),
        index_path=Path(settings.policy_index_path),
    )


@router.get("/health")
def api_health() -> dict:
    return {"status": "ok", "service": settings.app_name}


@router.get("/demo/state")
def demo_state() -> TradingState:
    prediction = PredictionOutput(
        curve_96=[0.0] * 96,
        source="mock",
        confidence=0.85,
    )
    strategy = StrategyOutput(
        declaration_curve_96=[0.0] * 96,
        rationale="Day 1 示例：尚未接入真实策略引擎",
    )
    risk = RiskCheckOutput(passed=True, violations=[])

    return TradingState(
        trace_id="demo-trace-001",
        trade_date="2026-05-17",
        policy_params={"region": "guangdong", "year": 2026},
        prediction_output=prediction.model_dump(),
        strategy_output=strategy.model_dump(),
        risk_check_result=risk.model_dump(),
        execution_payload={},
        audit_log=["init", "demo_state_generated"],
        human_review_required=False,
        status="demo",
    )


@router.get("/policy/status", response_model=PolicyIndexStatus)
def policy_status() -> dict:
    return get_policy_agent().status()


@router.post("/policy/index", response_model=PolicyIndexStatus)
def rebuild_policy_index() -> dict:
    return get_policy_agent().rebuild_index()


@router.post("/policy/query", response_model=PolicyQueryResponse)
def query_policy(request: PolicyQueryRequest) -> PolicyQueryResponse:
    return get_policy_agent().query(
        query=request.query,
        top_k=request.top_k,
        llm=request.llm,
    )


@router.get("/demo/policy-agent", response_model=PolicyQueryResponse)
def demo_policy_agent() -> PolicyQueryResponse:
    return get_policy_agent().query(query="广东电力市场日前交易申报规则和96点曲线要求", top_k=5)


@router.post("/workflow/run", response_model=TradingDayRunResponse)
def run_workflow(request: TradingDayRunRequest) -> TradingDayRunResponse:
    """给定交易日，串联：政策规则 → mock 预测 → mock 策略 → 风控 → mock 报文。"""
    return run_trading_day(request)
