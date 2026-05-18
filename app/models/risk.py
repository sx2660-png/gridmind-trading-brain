"""Risk check output model."""

from typing import Optional

from pydantic import BaseModel, Field


class RiskCheckOutput(BaseModel):
    passed: bool = True
    violations: list[str] = Field(default_factory=list)
    suggested_fix: Optional[str] = None
