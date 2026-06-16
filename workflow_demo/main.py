"""Runnable demo for the electricity trading multi-agent workflow."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.models.trading_state import TradingState
from app.services.workflow_graph import _as_state, build_workflow


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


if __name__ == "__main__":
    main()
