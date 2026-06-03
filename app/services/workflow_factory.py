"""Singleton LangGraph workflow with SQLite checkpointer for FastAPI."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.config import get_settings

_workflow = None
_checkpointer = None


def get_workflow():
    """Return a cached compiled LangGraph workflow with SQLite checkpointer."""
    global _workflow, _checkpointer

    if _workflow is not None:
        return _workflow

    from langgraph.checkpoint.sqlite import SqliteSaver
    from workflow_demo.main import build_workflow

    cfg = get_settings()
    db_path = Path(cfg.checkpoint_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    _checkpointer = SqliteSaver(conn)
    _checkpointer.setup()
    _workflow = build_workflow(checkpointer=_checkpointer)
    return _workflow
