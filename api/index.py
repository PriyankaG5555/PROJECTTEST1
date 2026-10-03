"""Vercel Python serverless entry point (backend-spec §11).

Vercel routes /api/* here (see vercel.json); the FastAPI app lives in backend/app.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402

__all__ = ["app"]
