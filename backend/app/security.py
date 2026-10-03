"""Passwords, session tokens, cookies and the current-user dependency (backend-spec.md §5)."""

import base64
import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errors import AppError
from app.models import User

SESSION_COOKIE = "gy_session"
JWT_ALGORITHM = "HS256"


# ---------- Passwords ----------
def _prehash(password: str) -> bytes:
    # bcrypt only uses the first 72 bytes; SHA-256 first so all 128 allowed characters count.
    return base64.b64encode(hashlib.sha256(password.encode("utf-8")).digest())


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)
    return bcrypt.hashpw(_prehash(password), salt).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(_prehash(password), password_hash.encode("ascii"))


@lru_cache
def _dummy_hash() -> str:
    return hash_password("dummy-password-for-timing")


def burn_password_check() -> None:
    """Spend the same time as a real check, so unknown usernames can't be detected by timing."""
    verify_password("not-the-password", _dummy_hash())


# ---------- Session tokens ----------
def create_session_token(user_id: uuid.UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(days=settings.session_ttl_days),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def read_session_token(token: str) -> uuid.UUID | None:
    """User ID from a valid, unexpired token; None for anything else."""
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError):
        return None


# ---------- Cookies ----------
def set_session_cookie(response: Response, user_id: uuid.UUID) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user_id),
        max_age=settings.session_ttl_days * 24 * 60 * 60,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        SESSION_COOKIE, path="/", httponly=True, secure=settings.cookie_secure, samesite="lax"
    )


# ---------- Current user ----------
def get_current_user(request: Request, db: Annotated[Session, Depends(get_db)]) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    user_id = read_session_token(token) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise AppError("UNAUTHORIZED", 401, "Please log in.")
    request.state.user_id = str(user.id)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[Session, Depends(get_db)]
