"""Auth endpoints — api-contract-spec.md §5."""

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.main import app
from app.models import Draft, Trip, TripType, User
from app.security import SESSION_COOKIE
from tests.conftest import PASSWORD, signup_client

AUTH = "/api/v1/auth"


def creds(username: str = "riya_travels", password: str = PASSWORD) -> dict[str, str]:
    return {"username": username, "password": password}


# ---------- Signup ----------
def test_signup_creates_user_and_logs_in(client: TestClient, db: Session) -> None:
    response = client.post(f"{AUTH}/signup", json=creds())

    assert response.status_code == 201
    user = response.json()["user"]
    assert user["username"] == "riya_travels"
    assert set(user) == {"id", "username", "createdAt"}
    assert client.get(f"{AUTH}/me").json()["user"]["id"] == user["id"]


def test_session_cookie_flags(client: TestClient, db: Session) -> None:
    response = client.post(f"{AUTH}/signup", json=creds())

    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    for flag in ("HttpOnly", "SameSite=lax", "Path=/", "Max-Age=604800"):
        assert flag in cookie


def test_password_is_stored_hashed(client: TestClient, db: Session) -> None:
    client.post(f"{AUTH}/signup", json=creds())

    stored = db.scalar(select(User.password_hash))
    assert stored is not None and PASSWORD not in stored


def test_signup_username_taken_case_insensitive(client: TestClient, db: Session) -> None:
    client.post(f"{AUTH}/signup", json=creds("Riya_Travels"))

    response = client.post(f"{AUTH}/signup", json=creds("riya_travels"))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USERNAME_TAKEN"


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"username": "ab", "password": PASSWORD}, "username"),
        ({"username": "riya travels", "password": PASSWORD}, "username"),
        ({"username": "riya_travels", "password": "short"}, "password"),
        ({"username": "riya_travels", "password": "x" * 129}, "password"),
        ({"password": PASSWORD}, "username"),
    ],
)
def test_signup_validation(
    client: TestClient, db: Session, body: dict[str, Any], field: str
) -> None:
    response = client.post(f"{AUTH}/signup", json=body)

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert field in error["details"]["fields"]


# ---------- Login / logout / me ----------
def test_login_with_any_capitalisation(client: TestClient, db: Session) -> None:
    signup_client()

    response = client.post(f"{AUTH}/login", json=creds("RIYA_TRAVELS"))

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "riya_travels"
    assert client.get(f"{AUTH}/me").status_code == 200


@pytest.mark.parametrize("username", ["riya_travels", "nobody_here"])
def test_login_wrong_credentials_same_error(client: TestClient, db: Session, username: str) -> None:
    signup_client()

    response = client.post(f"{AUTH}/login", json=creds(username, "wrong-password"))

    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "INVALID_CREDENTIALS",
        "message": "Incorrect username or password.",
    }
    assert SESSION_COOKIE not in response.cookies


def test_me_requires_login(client: TestClient, db: Session) -> None:
    response = client.get(f"{AUTH}/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_me_rejects_tampered_cookie(client: TestClient, db: Session) -> None:
    client.cookies.set(SESSION_COOKIE, "tampered.token.value")

    assert client.get(f"{AUTH}/me").status_code == 401


def test_logout_clears_session(logged_in_client: TestClient) -> None:
    response = logged_in_client.post(f"{AUTH}/logout")

    assert response.status_code == 204
    assert f"{SESSION_COOKIE}=" in response.headers["set-cookie"]
    assert logged_in_client.get(f"{AUTH}/me").status_code == 401


def test_logout_without_session_still_succeeds(client: TestClient, db: Session) -> None:
    assert client.post(f"{AUTH}/logout").status_code == 204


# ---------- Rate limit ----------
def test_eleventh_attempt_in_a_minute_is_rate_limited(client: TestClient, db: Session) -> None:
    for _ in range(10):
        assert client.post(f"{AUTH}/login", json=creds()).status_code == 401

    response = client.post(f"{AUTH}/login", json=creds())

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"


def test_rate_limit_is_per_ip(db: Session) -> None:
    a = TestClient(app, raise_server_exceptions=False, headers={"X-Forwarded-For": "1.1.1.1"})
    b = TestClient(app, raise_server_exceptions=False, headers={"X-Forwarded-For": "2.2.2.2"})
    for _ in range(11):
        a.post(f"{AUTH}/login", json=creds())

    assert b.post(f"{AUTH}/login", json=creds()).status_code == 401


# ---------- Delete account ----------
def test_delete_account_removes_user_and_all_their_data(
    logged_in_client: TestClient, db: Session
) -> None:
    user_id = logged_in_client.get(f"{AUTH}/me").json()["user"]["id"]
    trip = Trip(
        user_id=user_id,
        destination="Goa",
        start_date=date(2026, 11, 14),
        end_date=date(2026, 11, 17),
        trip_type=TripType.FRIENDS,
    )
    trip.drafts.append(Draft(name="Draft 1", name_normalized="draft 1"))
    db.add(trip)
    db.commit()

    response = logged_in_client.request("DELETE", f"{AUTH}/me", json={"password": PASSWORD})

    assert response.status_code == 204
    assert logged_in_client.get(f"{AUTH}/me").status_code == 401
    db.expire_all()
    for model in (User, Trip, Draft):
        assert db.scalar(select(func.count()).select_from(model)) == 0


def test_delete_account_wrong_password_keeps_everything(
    logged_in_client: TestClient, db: Session
) -> None:
    response = logged_in_client.request("DELETE", f"{AUTH}/me", json={"password": "wrong-pass"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert logged_in_client.get(f"{AUTH}/me").status_code == 200


def test_delete_account_requires_login(client: TestClient, db: Session) -> None:
    response = client.request("DELETE", f"{AUTH}/me", json={"password": PASSWORD})

    assert response.status_code == 401


def test_delete_account_requires_password(logged_in_client: TestClient) -> None:
    response = logged_in_client.request("DELETE", f"{AUTH}/me", json={})

    assert response.status_code == 400
    assert "password" in response.json()["error"]["details"]["fields"]
