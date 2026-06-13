"""API route definitions."""

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.agents.policy_agent import PolicyAgent
from app.core.config import settings
from app.models.policy import PolicyIndexStatus, PolicyQueryRequest, PolicyQueryResponse
from app.models.workflow import (
    TradingDayRunRequest,
    TradingDayRunResponse,
    WorkflowResumeRequest,
    WorkflowStatusResponse,
)
from app.services.trading_pipeline import run_trading_day
from app.services.workflow_factory import get_workflow
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
    """给定交易日，通过 LangGraph 串联：联网搜索 → 政策规则 → 预测 → 策略 → 风控 → 报文。"""
    from trading_state import TradingState as LangGraphState

    workflow = get_workflow()
    trace_id = f"trace-{request.trade_date.replace('-', '')}-{uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": trace_id}}

    initial_state = LangGraphState(
        trace_id=trace_id,
        trading_date=request.trade_date,
        market_type=request.market_type,
        as_of_datetime=request.as_of_datetime,
        mid_long_term_contract_mwh=[380.0] * 24,
    )

    result = workflow.invoke(initial_state, config=config)
    state = LangGraphState.model_validate(result)

    snapshot = workflow.get_state(config)
    is_interrupted = bool(snapshot.next)

    return TradingDayRunResponse(
        trace_id=trace_id,
        trade_date=request.trade_date,
        status="paused_for_human_review" if is_interrupted else "completed",
        policy_params=state.policy_rules,
        market_analysis=state.market_anomaly,
        risk_check_result={
            "risk_status": state.risk_status,
            "risk_flags": state.risk_flags,
        },
        execution_payload={
            "declaration_curve_mwh": state.declaration_curve_mwh,
            "declaration_ratio": state.declaration_ratio,
            "strategy_adjustments": state.strategy_adjustments,
            "execution_status": state.execution_status,
        },
        human_review_required=is_interrupted,
        audit_log=[],
        interrupted=is_interrupted,
        resume_endpoint="/api/workflow/resume" if is_interrupted else None,
    )


@router.post("/workflow/resume", response_model=WorkflowStatusResponse)
def resume_workflow(request: WorkflowResumeRequest) -> WorkflowStatusResponse:
    """Resume a workflow paused at human_review after operator decision."""
    from trading_state import TradingState as LangGraphState

    workflow = get_workflow()
    config = {"configurable": {"thread_id": request.trace_id}}

    snapshot = workflow.get_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail=f"No workflow found for trace_id={request.trace_id}")
    if not snapshot.next:
        raise HTTPException(status_code=400, detail="Workflow is not paused; nothing to resume")

    workflow.update_state(
        config,
        {
            "human_review_decision": request.decision,
            "human_review_comment": request.comment,
        },
    )

    result = workflow.invoke(None, config=config)
    state = LangGraphState.model_validate(result)

    return WorkflowStatusResponse(
        trace_id=request.trace_id,
        status="completed" if state.execution_status in ("submitted", "approved_by_human") else state.execution_status,
        risk_status=state.risk_status,
        execution_status=state.execution_status,
        risk_flags=state.risk_flags,
        human_review_decision=state.human_review_decision,
    )


@router.get("/workflow/status/{trace_id}", response_model=WorkflowStatusResponse)
def get_workflow_status(trace_id: str) -> WorkflowStatusResponse:
    """Check the current state of a workflow by trace_id."""
    from trading_state import TradingState as LangGraphState

    workflow = get_workflow()
    config = {"configurable": {"thread_id": trace_id}}

    snapshot = workflow.get_state(config)
    if not snapshot.values:
        raise HTTPException(status_code=404, detail=f"No workflow found for trace_id={trace_id}")

    state = LangGraphState.model_validate(snapshot.values)
    next_nodes = list(snapshot.next) if snapshot.next else []

    return WorkflowStatusResponse(
        trace_id=trace_id,
        status="paused" if next_nodes else "completed",
        risk_status=state.risk_status,
        execution_status=state.execution_status,
        risk_flags=state.risk_flags,
        human_review_decision=state.human_review_decision,
        next_nodes=next_nodes,
    )


@router.post("/workflow/run-legacy", response_model=TradingDayRunResponse)
def run_workflow_legacy(request: TradingDayRunRequest) -> TradingDayRunResponse:
    """Legacy procedural pipeline (without LangGraph)."""
    return run_trading_day(request)
