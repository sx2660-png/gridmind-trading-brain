"""LLM configuration for RAG generation step."""

from typing import Optional

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    """OpenAI-compatible API settings (per-request or from .env)."""

    api_key: str = Field(..., min_length=1, description="API Key")
    base_url: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI-compatible base URL",
    )
    model: str = Field(default="gpt-4o-mini", description="Chat model name")
    enabled: bool = Field(default=True, description="Use LLM for generation when true")
