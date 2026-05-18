"""API route definitions."""

from fastapi import APIRouter

from app.core.config import settings
from app.models.prediction import PredictionOutput
from app.models.risk import RiskCheckOutput
from app.models.state import TradingState
from app.models.strategy import StrategyOutput

router = APIRouter(tags=["api"])


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
