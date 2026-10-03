"""Per-IP rate limit for auth endpoints, stored in PostgreSQL (backend-spec.md §4).

Counted in its own transaction, so attempts that fail (e.g. wrong password, which rolls back
the request's session) still count.
"""

from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import delete, func, literal
from sqlalchemy.dialects.postgresql import insert

from app.db import get_engine
from app.errors import AppError
from app.models import AuthAttempt

MAX_ATTEMPTS_PER_MINUTE = 10


def client_ip(request: Request) -> str:
    # Vercel sets X-Forwarded-For to the real client IP (first entry).
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else "")
    return ip[:45] or "unknown"


def check_auth_rate_limit(request: Request) -> None:
    now = datetime.now(UTC)
    window = now.replace(second=0, microsecond=0)
    upsert = (
        insert(AuthAttempt)
        .values(ip=client_ip(request), window_start=window, count=1)
        .on_conflict_do_update(
            index_elements=[AuthAttempt.ip, AuthAttempt.window_start],
            set_={"count": AuthAttempt.count + literal(1)},
        )
        .returning(AuthAttempt.count)
    )
    with get_engine().begin() as conn:
        count = conn.execute(upsert).scalar_one()
        conn.execute(
            delete(AuthAttempt).where(AuthAttempt.window_start < func.now() - timedelta(hours=1))
        )
    if count > MAX_ATTEMPTS_PER_MINUTE:
        raise AppError(
            "RATE_LIMITED", 429, "Too many attempts. Please wait a minute and try again."
        )
