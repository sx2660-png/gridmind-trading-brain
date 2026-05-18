"""Strategy output model."""

from pydantic import BaseModel, Field


class StrategyOutput(BaseModel):
    declaration_curve_96: list[float] = Field(default_factory=list)
    rationale: str = ""
