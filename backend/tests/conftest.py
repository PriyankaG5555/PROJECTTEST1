"""Test setup.

Test database, in order of preference:
  1. TEST_DATABASE_URL (environment or backend/.env) — locally, the Neon "test" branch
  2. DATABASE_URL when ENVIRONMENT=test — CI's PostgreSQL service
Tests marked with the `db` fixture are skipped when neither is configured.
The test database is WIPED at the start of the run, so it must never be the dev database.
"""

import os
from collections.abc import Iterator
from pathlib import Path

from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parent.parent
_dotenv = dotenv_values(BACKEND_DIR / ".env")

TEST_DATABASE_URL = (
    os.environ.get("TEST_DATABASE_URL")
    or _dotenv.get("TEST_DATABASE_URL")
    or (os.environ.get("DATABASE_URL") if os.environ.get("ENVIRONMENT") == "test" else None)
)
if TEST_DATABASE_URL and _dotenv.get("DATABASE_URL") == TEST_DATABASE_URL:
    raise RuntimeError("TEST_DATABASE_URL must not point at the development database.")

# Settings must be in place before the app is imported (env vars beat backend/.env).
os.environ["DATABASE_URL"] = TEST_DATABASE_URL or "postgresql+psycopg://nobody@127.0.0.1:1/none"
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-123"
os.environ["ENVIRONMENT"] = "test"
os.environ["COOKIE_SECURE"] = "false"
os.environ["LOG_LEVEL"] = "WARNING"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db import get_engine, get_sessionmaker  # noqa: E402
from app.main import app  # noqa: E402


def alembic_config() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


@pytest.fixture(scope="session")
def migrated_db() -> None:
    """Rebuild the test database from the migrations once per test run."""
    if not TEST_DATABASE_URL:
        pytest.skip("No test database configured (set TEST_DATABASE_URL in backend/.env).")
    with get_engine().begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    command.upgrade(alembic_config(), "head")


@pytest.fixture
def db(migrated_db: None) -> Iterator[Session]:
    """A session on an empty database."""
    with get_engine().begin() as conn:
        conn.execute(text("TRUNCATE users, auth_attempts CASCADE"))
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)
