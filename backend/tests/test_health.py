import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.routers import health


def test_health_ok_when_database_reachable(client: TestClient, db: Session) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_degraded_when_database_unreachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    dead = create_engine(
        "postgresql+psycopg://nobody@127.0.0.1:1/none",
        poolclass=NullPool,
        connect_args={"connect_timeout": 1},
    )
    monkeypatch.setattr(health, "get_engine", lambda: dead)

    response = client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded"}
