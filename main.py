"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

app.include_router(router)


@app.get("/")
def root() -> dict:
    return {
        "service": settings.app_name,
        "status": "running",
        "message": "具备合规审查能力的自动化电力交易大脑 — 服务已启动",
        "env": settings.app_env,
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name}
