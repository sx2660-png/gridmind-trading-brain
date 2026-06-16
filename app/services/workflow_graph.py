"""LangGraph workflow composition for the electricity trading agents."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.execution_agent import execution_node, reject_node
from app.agents.human_review_agent import human_review_node
from app.agents.policy_agent import policy_node
from app.agents.prediction_agent import prediction_node
from app.agents.risk_agent import risk_node
from app.agents.strategy_agent import strategy_node
from app.agents.web_search_agent import web_search_node
from app.models.trading_state import TradingState


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


def _as_state(state: TradingState | dict[str, Any]) -> TradingState:
    if isinstance(state, TradingState):
        return state
    return TradingState.model_validate(state)
