import os

# Test settings must be in place before the app is imported.
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://gy:gy_test_password@localhost:5433/ghumakkadyatri_test"
)
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-123")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("COOKIE_SECURE", "false")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
