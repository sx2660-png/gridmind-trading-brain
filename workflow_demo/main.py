"""Runnable LangGraph demo for the electricity trading multi-agent workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langgraph.graph import END, START, StateGraph

from mock_api.execution_api import ExecutionRequest, submit_declaration
from mock_api.prediction_api import PredictionRequest, build_prediction
from mock_api.strategy_api import StrategyRequest, build_strategy
from risk_agent import check_risk
from trading_state import TradingState


def prediction_node(state: TradingState) -> dict[str, Any]:
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


def strategy_node(state: TradingState) -> dict[str, Any]:
    """Strategy Agent node: build or recalculate a declaration curve."""
    state = _as_state(state)
    _log_node("Strategy Agent", state)

    strategy = build_strategy(
        StrategyRequest(
            predicted_da_price=state.predicted_da_price,
            predicted_rt_price=state.predicted_rt_price,
            predicted_load_mwh=state.predicted_load_mwh,
            mid_long_term_contract_mwh=state.mid_long_term_contract_mwh,
        )
    )

    declaration_curve = strategy.declaration_curve_mwh
    declaration_ratio = strategy.declaration_ratio

    # If Risk Agent returned the plan for recalculation, tighten the strategy
    # around forecasted load so the next risk pass has a valid baseline.
    if state.risk_status == "RETURN_FOR_RECALCULATION":
        print(f"[Strategy Agent] trace_id={state.trace_id} recalculating declaration after risk feedback")
        declaration_curve = [round(load, 2) for load in state.predicted_load_mwh]
        declaration_ratio = [1.0 for _ in state.predicted_load_mwh]

    print(f"[Strategy Agent] trace_id={state.trace_id} estimated_profit={strategy.estimated_profit}")
    return {
        "declaration_curve_mwh": declaration_curve,
        "declaration_ratio": declaration_ratio,
        "risk_status": "pending",
        "risk_flags": [],
        "updated_at": _now(),
    }


def risk_node(state: TradingState) -> dict[str, Any]:
    """Risk Agent node: apply the compliance gate before execution."""
    state = _as_state(state)
    _log_node("Risk Agent", state)

    risk_result = check_risk(state)
    print(
        f"[Risk Agent] trace_id={state.trace_id} "
        f"risk_status={risk_result['risk_status']} flags={len(risk_result['risk_flags'])}"
    )

    return {
        **risk_result,
        "updated_at": _now(),
    }


def execution_node(state: TradingState) -> dict[str, Any]:
    """Execution Agent node: submit the approved declaration to the mock center."""
    state = _as_state(state)
    _log_node("Execution Agent", state)

    execution = submit_declaration(
        ExecutionRequest(
            declaration={
                "trace_id": state.trace_id,
                "trading_date": state.trading_date,
                "market_type": state.market_type,
                "declaration_curve_mwh": state.declaration_curve_mwh,
                "declaration_ratio": state.declaration_ratio,
                "risk_status": state.risk_status,
            }
        )
    )

    print(
        f"[Execution Agent] trace_id={execution.trace_id} "
        f"execution_status={execution.execution_status} timestamp={execution.timestamp.isoformat()}"
    )
    return {
        "execution_status": execution.execution_status,
        "updated_at": _now(),
    }


def reject_node(state: TradingState) -> dict[str, Any]:
    """Terminal node for invalid declarations that should not be recalculated."""
    state = _as_state(state)
    _log_node("Rejected", state)
    print(f"[Rejected] trace_id={state.trace_id} risk_status={state.risk_status}")
    return {
        "execution_status": "rejected",
        "updated_at": _now(),
    }


def human_review_node(state: TradingState) -> dict[str, Any]:
    """Terminal pause node for cases that need manual operator review."""
    state = _as_state(state)
    _log_node("Human Review", state)
    print(f"[Human Review] trace_id={state.trace_id} workflow paused for operator review")
    return {
        "execution_status": "paused_for_human_review",
        "updated_at": _now(),
    }


def route_after_risk(state: TradingState) -> str:
    """Route graph execution based on Risk Agent status."""
    state = _as_state(state)
    if state.risk_status == "PASS":
        return "execution"
    if state.risk_status == "RETURN_FOR_RECALCULATION":
        return "strategy"
    if state.risk_status == "REJECT":
        return "reject"
    if state.risk_status == "REQUIRES_HUMAN_REVIEW":
        return "human_review"
    return "reject"


def build_workflow():
    """Compile the LangGraph workflow."""
    graph = StateGraph(TradingState)
    graph.add_node("prediction", prediction_node)
    graph.add_node("strategy", strategy_node)
    graph.add_node("risk", risk_node)
    graph.add_node("execution", execution_node)
    graph.add_node("reject", reject_node)
    graph.add_node("human_review", human_review_node)

    graph.add_edge(START, "prediction")
    graph.add_edge("prediction", "strategy")
    graph.add_edge("strategy", "risk")
    graph.add_conditional_edges(
        "risk",
        route_after_risk,
        {
            "execution": "execution",
            "strategy": "strategy",
            "reject": "reject",
            "human_review": "human_review",
        },
    )
    graph.add_edge("execution", END)
    graph.add_edge("reject", END)
    graph.add_edge("human_review", END)
    return graph.compile()


def demo_initial_state() -> TradingState:
    """Create a minimal 24-point state for an end-to-end demo run."""
    return TradingState(
        trace_id="trace-langgraph-demo-001",
        trading_date="2026-05-22",
        market_type="day_ahead",
        date_type="normal_day",
        mid_long_term_contract_mwh=[380.0] * 24,
        policy_rules={
            "region": "guangdong",
            "market_stage": "day_ahead",
            "maintenance_limit_mwh": 900.0,
        },
    )


def main() -> None:
    workflow = build_workflow()
    initial_state = demo_initial_state()
    print(f"[Workflow] starting trace_id={initial_state.trace_id}")
    final_state = workflow.invoke(initial_state)
    final_state = _as_state(final_state)
    print(
        f"[Workflow] finished trace_id={final_state.trace_id} "
        f"risk_status={final_state.risk_status} execution_status={final_state.execution_status}"
    )


def _as_state(state: TradingState | dict[str, Any]) -> TradingState:
    if isinstance(state, TradingState):
        return state
    return TradingState.model_validate(state)


def _log_node(node_name: str, state: TradingState) -> None:
    print(f"[{node_name}] current_node={node_name} trace_id={state.trace_id}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


if __name__ == "__main__":
    main()
