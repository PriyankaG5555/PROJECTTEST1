"""FastAPI application entry point.

Run locally:  uvicorn app.main:app --reload --port 8000   (from backend/)
On Vercel:    imported by api/index.py
"""

from fastapi import FastAPI

from app.config import get_settings
from app.errors import register_error_handlers
from app.middleware import configure_logging, register_middleware
from app.routers import health

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="GhumakkadYatri API",
        version="0.1.0",
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
        redoc_url=None,
    )
    register_error_handlers(app)
    register_middleware(app)
    app.include_router(health.router, prefix=API_PREFIX)
    return app


app = create_app()
