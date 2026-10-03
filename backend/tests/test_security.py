"""Password hashing and session tokens (no database needed)."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings
from app.security import (
    JWT_ALGORITHM,
    create_session_token,
    hash_password,
    read_session_token,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    hashed = hash_password("s3cure-pass")

    assert hashed.startswith("$2")
    assert "s3cure-pass" not in hashed
    assert verify_password("s3cure-pass", hashed)
    assert not verify_password("wrong-pass", hashed)


def test_long_passwords_use_every_character() -> None:
    # bcrypt alone ignores bytes after 72; the pre-hash makes the whole password count.
    base = "x" * 100
    hashed = hash_password(base + "A")

    assert verify_password(base + "A", hashed)
    assert not verify_password(base + "B", hashed)


def test_token_round_trip() -> None:
    user_id = uuid.uuid4()

    assert read_session_token(create_session_token(user_id)) == user_id


def test_expired_token_rejected() -> None:
    past = datetime.now(UTC) - timedelta(days=8)
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "iat": past, "exp": past + timedelta(days=7)},
        get_settings().jwt_secret,
        algorithm=JWT_ALGORITHM,
    )

    assert read_session_token(token) is None


def test_token_signed_with_other_secret_rejected() -> None:
    token = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": datetime.now(UTC) + timedelta(days=1)},
        "some-other-secret-some-other-secret-1234",
        algorithm=JWT_ALGORITHM,
    )

    assert read_session_token(token) is None


def test_garbage_token_rejected() -> None:
    assert read_session_token("not-a-jwt") is None
    assert read_session_token(create_session_token(uuid.uuid4()) + "x") is None
