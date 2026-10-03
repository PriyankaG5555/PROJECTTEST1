"""FastAPI application entry point.

Run locally:  uvicorn app.main:app --reload --port 8000   (from backend/)
On Vercel:    imported by api/index.py
"""

from fastapi import FastAPI

from app.config import get_settings
from app.routers import health

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="GhumakkadYatri API",
        version="0.1.0",
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
        redoc_url=None,
        debug=settings.environment == "development",
    )
    app.include_router(health.router, prefix=API_PREFIX)
    return app


app = create_app()
