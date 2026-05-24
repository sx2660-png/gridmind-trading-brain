"""FastAPI entry point for mock electricity trading APIs."""

from fastapi import FastAPI

from execution_api import ExecutionRequest, ExecutionResponse, submit_declaration
from prediction_api import PredictionRequest, PredictionResponse, build_prediction
from strategy_api import StrategyRequest, StrategyResponse, build_strategy


app = FastAPI(
    title="mock-electricity-trading-api",
    description="Mock services for end-to-end electricity trading multi-agent workflow tests.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "mock-electricity-trading-api"}


@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest) -> PredictionResponse:
    return build_prediction(request)


@app.post("/strategy", response_model=StrategyResponse)
def strategy(request: StrategyRequest) -> StrategyResponse:
    return build_strategy(request)


@app.post("/execute", response_model=ExecutionResponse)
def execute(request: ExecutionRequest) -> ExecutionResponse:
    return submit_declaration(request)
