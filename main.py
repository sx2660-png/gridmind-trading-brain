"""FastAPI application entry point."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/ui")
def ui() -> FileResponse:
    """Simple web console for workflow and policy APIs."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/")
def root() -> dict:
    return {
        "service": settings.app_name,
        "status": "running",
        "message": "具备合规审查能力的自动化电力交易大脑 — 服务已启动",
        "env": settings.app_env,
        "ui": "/ui",
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name}
