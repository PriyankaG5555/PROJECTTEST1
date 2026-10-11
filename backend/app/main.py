"""FastAPI application entry point.

Run locally:  uvicorn app.main:app --reload --port 8000   (from backend/)
On Vercel:    imported by api/index.py
"""

from fastapi import FastAPI

from app import telemetry
from app.config import get_settings
from app.errors import register_error_handlers
from app.middleware import configure_logging, register_middleware
from app.routers import auth, drafts, health, stays, trips
from app.routers import telemetry as telemetry_router

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
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(trips.router, prefix=API_PREFIX)
    app.include_router(drafts.router, prefix=API_PREFIX)
    app.include_router(stays.router, prefix=API_PREFIX)
    app.include_router(telemetry_router.router, prefix=API_PREFIX)
    telemetry.setup(app)
    return app


app = create_app()
