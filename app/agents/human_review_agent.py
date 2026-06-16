"""Human review node for paused trading workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.trading_state import TradingState


def human_review_node(state: TradingState | dict[str, Any]) -> dict[str, Any]:
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


def _as_state(state: TradingState | dict[str, Any]) -> TradingState:
    if isinstance(state, TradingState):
        return state
    return TradingState.model_validate(state)


def _log_node(node_name: str, state: TradingState) -> None:
    print(f"[{node_name}] current_node={node_name} trace_id={state.trace_id}")


def _now() -> datetime:
    return datetime.now(timezone.utc)
