"""Policy agent data models."""

from typing import Optional

from pydantic import BaseModel, Field

from app.models.llm import LLMConfig


class PolicyEvidence(BaseModel):
    source: str
    chunk_id: str
    score: float
    text: str


class PolicyQueryRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    llm: Optional[LLMConfig] = Field(
        default=None,
        description="可选：大模型配置；提供 api_key 时用于 Generation 步骤",
    )


class PolicyQueryResponse(BaseModel):
    query: str
    answer: str
    policy_params: dict = Field(default_factory=dict)
    evidence: list[PolicyEvidence] = Field(default_factory=list)
    generation_mode: str = Field(
        default="rules",
        description="rules | llm | rules_fallback",
    )
    generation_note: Optional[str] = None


class PolicyIndexStatus(BaseModel):
    index_path: str
    source_dir: str
    document_count: int
    chunk_count: int
    embedding_model: str
    ready: bool
