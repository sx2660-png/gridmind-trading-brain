"""Resolve LLM config from request body or environment."""

from __future__ import annotations

from typing import Optional

from app.core.config import get_settings
from app.models.llm import LLMConfig


def resolve_llm_config(request_llm: Optional[LLMConfig]) -> Optional[LLMConfig]:
    """Prefer per-request config; fall back to .env when api_key is set."""
    if request_llm is not None:
        if not request_llm.enabled:
            return None
        if request_llm.api_key.strip():
            return request_llm

    cfg = get_settings()
    if cfg.llm_api_key:
        return LLMConfig(
            api_key=cfg.llm_api_key,
            base_url=cfg.llm_base_url,
            model=cfg.llm_model,
            enabled=True,
        )
    return None
