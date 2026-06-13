"""Runnable LangGraph demo for the electricity trading multi-agent workflow.

Graph topology:
  START → web_search → policy → prediction → strategy → risk → conditional
    ├─ PASS → execution → END
    ├─ RETURN_FOR_RECALCULATION → strategy (loop)
    ├─ REJECT → reject → END
    └─ REQUIRES_HUMAN_REVIEW → (interrupt) → human_review → conditional
                                                ├─ approved → execution → END
                                                └─ rejected → END
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langgraph.graph import END, START, StateGraph

from app.agents.policy_agent import policy_node
from app.agents.web_search_agent import web_search_node
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
    strategy_adjustments: list[str] = []

    if state.risk_status == "RETURN_FOR_RECALCULATION":
        print(f"[Strategy Agent] trace_id={state.trace_id} recalculating declaration after risk feedback")
        declaration_curve = [round(load, 2) for load in state.predicted_load_mwh]
        declaration_ratio = [1.0 for _ in state.predicted_load_mwh]
        strategy_adjustments.append("RISK_RECALCULATION_ALIGN_TO_FORECAST_LOAD")

    anomaly_level = state.market_anomaly.get("alert_level", "NONE")
    if anomaly_level in ("HIGH", "CRITICAL", "UNKNOWN"):
        print(
            f"[Strategy Agent] trace_id={state.trace_id} "
            f"market_anomaly={anomaly_level}; applying defensive declaration"
        )
        declaration_curve = [round(load, 2) for load in state.predicted_load_mwh]
        declaration_ratio = [1.0 for _ in state.predicted_load_mwh]
        strategy_adjustments.append(
            "MARKET_ANOMALY_DEFENSIVE_ALIGN_TO_FORECAST_LOAD"
        )

    print(f"[Strategy Agent] trace_id={state.trace_id} estimated_profit={strategy.estimated_profit}")
    return {
        "declaration_curve_mwh": declaration_curve,
        "declaration_ratio": declaration_ratio,
        "strategy_adjustments": strategy_adjustments,
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
    """Process the human review decision injected via workflow.update_state()."""
    state = _as_state(state)
    _log_node("Human Review", state)

    if state.human_review_decision == "approved":
        print(f"[Human Review] trace_id={state.trace_id} approved by operator")
        return {
            "risk_status": "PASS",
            "execution_status": "approved_by_human",
            "updated_at": _now(),
        }

    if state.human_review_decision == "rejected":
        print(f"[Human Review] trace_id={state.trace_id} rejected by operator")
        return {
            "execution_status": "rejected_by_human",
            "updated_at": _now(),
        }

    print(f"[Human Review] trace_id={state.trace_id} awaiting operator decision")
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


def route_after_human_review(state: TradingState) -> str:
    """Route after human review: approved → execution, otherwise → end."""
    state = _as_state(state)
    if state.risk_status == "PASS":
        return "execution"
    return "end"


def build_workflow(checkpointer=None):
    """Compile the LangGraph workflow with optional checkpointer and interrupt."""
    graph = StateGraph(TradingState)

    graph.add_node("web_search", web_search_node)
    graph.add_node("policy", policy_node)
    graph.add_node("prediction", prediction_node)
    graph.add_node("strategy", strategy_node)
    graph.add_node("risk", risk_node)
    graph.add_node("execution", execution_node)
    graph.add_node("reject", reject_node)
    graph.add_node("human_review", human_review_node)

    graph.add_edge(START, "web_search")
    graph.add_edge("web_search", "policy")
    graph.add_edge("policy", "prediction")
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
    graph.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {
            "execution": "execution",
            "end": END,
        },
    )
    graph.add_edge("execution", END)
    graph.add_edge("reject", END)

    compile_kwargs: dict[str, Any] = {}
    if checkpointer is not None:
        compile_kwargs["checkpointer"] = checkpointer
        compile_kwargs["interrupt_before"] = ["human_review"]

    return graph.compile(**compile_kwargs)


def demo_initial_state() -> TradingState:
    """Create a minimal 24-point state for an end-to-end demo run."""
    return TradingState(
        trace_id="trace-langgraph-demo-001",
        trading_date="2026-05-22",
        market_type="day_ahead",
        date_type="normal_day",
        mid_long_term_contract_mwh=[380.0] * 24,
    )


def main() -> None:
    import sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver

    Path("data").mkdir(exist_ok=True)
    conn = sqlite3.connect("data/checkpoints.sqlite", check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()

    workflow = build_workflow(checkpointer=checkpointer)
    initial_state = demo_initial_state()
    config = {"configurable": {"thread_id": initial_state.trace_id}}

    print(f"[Workflow] starting trace_id={initial_state.trace_id}")
    final_state = workflow.invoke(initial_state, config=config)
    final_state = _as_state(final_state)

    snapshot = workflow.get_state(config)
    if snapshot.next:
        print(
            f"[Workflow] paused at {snapshot.next} trace_id={final_state.trace_id} "
            f"risk_status={final_state.risk_status}"
        )
        print("[Workflow] to resume, call workflow.update_state() with human_review_decision")
    else:
        print(
            f"[Workflow] finished trace_id={final_state.trace_id} "
            f"risk_status={final_state.risk_status} "
            f"execution_status={final_state.execution_status}"
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
