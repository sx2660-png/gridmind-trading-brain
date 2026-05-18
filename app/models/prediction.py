"""Prediction output model."""

from pydantic import BaseModel, Field


class PredictionOutput(BaseModel):
    curve_96: list[float] = Field(default_factory=list)
    source: str = ""
    confidence: float = 0.0
