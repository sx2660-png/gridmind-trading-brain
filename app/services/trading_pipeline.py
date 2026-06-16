"""Orchestrate policy → prediction → strategy → risk → mock submission."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any
from uuid import uuid4

from app.agents.policy_agent import PolicyAgent
from app.core.config import get_settings
from app.models.workflow import TradingDayRunRequest, TradingDayRunResponse

# Reuse root-level LangGraph / mock modules without moving files yet.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.agents.execution_agent import ExecutionRequest, submit_declaration  # noqa: E402
from app.agents.prediction_agent import PredictionRequest, build_prediction  # noqa: E402
from app.agents.risk_agent import check_risk  # noqa: E402
from app.agents.strategy_agent import StrategyRequest, build_strategy  # noqa: E402
from app.models.trading_state import TradingState  # noqa: E402

DEFAULT_POLICY_QUERY = "广东电力市场日前交易申报规则、96点曲线与偏差考核要求"
DEFAULT_MAINTENANCE_LIMIT_MWH = 900.0
MAX_RISK_RETRIES = 2


def run_trading_day(request: TradingDayRunRequest) -> TradingDayRunResponse:
    """Run a single trading day through mock agents and return a submission payload."""
    trace_id = f"trace-{request.trade_date.replace('-', '')}-{uuid4().hex[:8]}"
    audit: list[str] = []
    policy_generation_mode = "rules"

    cfg = get_settings()
    audit.append("policy_query_started")
    policy_agent = PolicyAgent(
        source_dir=Path(cfg.policy_articles_dir),
        index_path=Path(cfg.policy_index_path),
    )
    policy_query = request.policy_query or DEFAULT_POLICY_QUERY
    policy_response = policy_agent.query(
        query=policy_query,
        top_k=5,
        llm=request.llm,
    )
    policy_params = policy_response.policy_params
    audit.append(f"policy_query_completed:{policy_response.generation_mode}")
    policy_generation_mode = policy_response.generation_mode

    policy_rules = _policy_rules_from_params(policy_params)

    audit.append("prediction_started")
    prediction = build_prediction(
        PredictionRequest(trading_date=request.trade_date, market_type=request.market_type)
    )
    prediction_output = prediction.model_dump()
    audit.append("prediction_completed")

    mid_long_term_contract_mwh = [
        round(load * 0.92, 2) for load in prediction.predicted_load_mwh
    ]

    state = TradingState(
        trace_id=trace_id,
        trading_date=request.trade_date,
        market_type=request.market_type,
        predicted_da_price=prediction.predicted_da_price,
        predicted_rt_price=prediction.predicted_rt_price,
        predicted_load_mwh=prediction.predicted_load_mwh,
        mid_long_term_contract_mwh=mid_long_term_contract_mwh,
        policy_rules=policy_rules,
    )

    strategy_output: dict[str, Any] = {}
    risk_check_result: dict[str, Any] = {}
    risk_status = "pending"

    for attempt in range(1, MAX_RISK_RETRIES + 1):
        audit.append(f"strategy_started_attempt_{attempt}")
        strategy = build_strategy(
            StrategyRequest(
                predicted_da_price=state.predicted_da_price,
                predicted_rt_price=state.predicted_rt_price,
                predicted_load_mwh=state.predicted_load_mwh,
                mid_long_term_contract_mwh=state.mid_long_term_contract_mwh,
            )
        )
        if attempt > 1:
            strategy = _recalibrated_strategy(state)
        state.declaration_curve_mwh = strategy.declaration_curve_mwh
        state.declaration_ratio = strategy.declaration_ratio
        strategy_output = strategy.model_dump()
        audit.append(f"strategy_completed_attempt_{attempt}")

        audit.append(f"risk_check_started_attempt_{attempt}")
        risk_check_result = check_risk(state)
        risk_status = risk_check_result["risk_status"]
        state.risk_status = risk_status
        state.risk_flags = risk_check_result["risk_flags"]
        audit.append(f"risk_check_completed_attempt_{attempt}:{risk_status}")

        if risk_status != "RETURN_FOR_RECALCULATION":
            break

    execution_payload, workflow_status, human_review = _build_execution_payload(
        state=state,
        policy_params=policy_params,
        risk_check_result=risk_check_result,
    )
    audit.append(f"workflow_finished:{workflow_status}")

    policy_output = {
        "query": policy_query,
        "answer": policy_response.answer,
        "evidence": [item.model_dump() for item in policy_response.evidence],
        "generation_mode": policy_response.generation_mode,
        "generation_note": policy_response.generation_note,
    }

    return TradingDayRunResponse(
        trace_id=trace_id,
        trade_date=request.trade_date,
        status=workflow_status,
        policy_output=policy_output,
        policy_params=policy_params,
        prediction_output=prediction_output,
        strategy_output=strategy_output,
        risk_check_result=risk_check_result,
        execution_payload=execution_payload,
        human_review_required=human_review,
        audit_log=audit,
        policy_generation_mode=policy_generation_mode,
    )


def _policy_rules_from_params(policy_params: dict) -> dict:
    rules = {
        "region": policy_params.get("region", "guangdong"),
        "market_stage": policy_params.get("market_stage", "day_ahead"),
        "maintenance_limit_mwh": DEFAULT_MAINTENANCE_LIMIT_MWH,
    }
    if "time_resolution" in policy_params:
        rules["time_resolution"] = policy_params["time_resolution"]
    limit = policy_params.get("maintenance_limit_mwh")
    if limit is not None:
        rules["maintenance_limit_mwh"] = limit
    return rules


def _recalibrated_strategy(state: TradingState):
    """After risk feedback, align declaration with forecast load (same as workflow_demo)."""
    from app.agents.strategy_agent import StrategyResponse

    declaration_curve = [round(load, 2) for load in state.predicted_load_mwh]
    declaration_ratio = [1.0 for _ in state.predicted_load_mwh]
    return StrategyResponse(
        declaration_curve_mwh=declaration_curve,
        declaration_ratio=declaration_ratio,
        estimated_profit=0.0,
    )


def _build_execution_payload(
    *,
    state: TradingState,
    policy_params: dict,
    risk_check_result: dict,
) -> tuple[dict, str, bool]:
    risk_status = risk_check_result.get("risk_status", "pending")
    human_review = risk_status == "REQUIRES_HUMAN_REVIEW"

    declaration_body = {
        "message_type": "day_ahead_declaration",
        "trace_id": state.trace_id,
        "trading_date": state.trading_date,
        "market_type": state.market_type,
        "declaration_curve_mwh": state.declaration_curve_mwh,
        "declaration_ratio": state.declaration_ratio,
        "policy_params": policy_params,
        "policy_rules": state.policy_rules,
        "risk_status": risk_status,
        "risk_flags": risk_check_result.get("risk_flags", []),
    }

    if risk_status == "PASS":
        submission = submit_declaration(ExecutionRequest(declaration=declaration_body))
        payload = {
            **declaration_body,
            "submission": {
                "status": submission.execution_status,
                "submitted_at": submission.timestamp.isoformat(),
            },
        }
        return payload, "completed", False

    if human_review:
        payload = {
            **declaration_body,
            "submission": {"status": "pending_human_review"},
        }
        return payload, "human_review", True

    if risk_status == "RETURN_FOR_RECALCULATION":
        payload = {
            **declaration_body,
            "submission": {"status": "blocked", "reason": "recalculation_exhausted"},
        }
        return payload, "blocked", False

    payload = {
        **declaration_body,
        "submission": {"status": "rejected", "reason": risk_status},
    }
    return payload, "rejected", False
