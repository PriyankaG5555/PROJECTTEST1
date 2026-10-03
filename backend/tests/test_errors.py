"""Error format (api-contract-spec.md §2) and middleware (backend-spec.md §6, §9)."""

from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import AppError, register_error_handlers
from app.middleware import MAX_BODY_BYTES, SECURITY_HEADERS, register_middleware
from app.schemas.base import ApiModel


class TripIn(ApiModel):
    destination: str
    end_date: date


def make_client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    register_middleware(app)

    @app.post("/echo")
    def echo(body: TripIn) -> dict[str, str]:
        return {"destination": body.destination}

    @app.get("/conflict")
    def conflict() -> None:
        raise AppError("TRIP_FINALIZED", 409, "This trip is finalized.", {"tripId": "t1"})

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    return TestClient(app, raise_server_exceptions=False)


client = make_client()


def test_validation_error_uses_contract_format_and_camel_case_fields() -> None:
    response = client.post("/echo", json={"destination": "Goa", "endDate": "not-a-date"})

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert set(error["details"]["fields"]) == {"endDate"}
    assert error["message"] == error["details"]["fields"]["endDate"]


def test_missing_fields_are_all_reported() -> None:
    response = client.post("/echo", json={})

    assert set(response.json()["error"]["details"]["fields"]) == {"destination", "endDate"}


def test_camel_case_body_is_accepted() -> None:
    response = client.post("/echo", json={"destination": "Goa", "endDate": "2026-11-17"})

    assert response.status_code == 200


def test_app_error_rendered_with_details() -> None:
    response = client.get("/conflict")

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "TRIP_FINALIZED",
            "message": "This trip is finalized.",
            "details": {"tripId": "t1"},
        }
    }


def test_unknown_route_is_not_found() -> None:
    response = client.get("/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_wrong_method_is_method_not_allowed() -> None:
    response = client.delete("/echo")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_unexpected_error_hides_internal_details() -> None:
    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret" not in response.text


def test_body_over_limit_is_rejected() -> None:
    big = "x" * (MAX_BODY_BYTES + 1)
    response = client.post("/echo", content=big, headers={"content-type": "application/json"})

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_security_headers_and_request_id_on_every_response() -> None:
    response = client.post("/echo", json={"destination": "Goa", "endDate": "2026-11-17"})

    for header, value in SECURITY_HEADERS.items():
        assert response.headers[header] == value
    assert response.headers["X-Request-ID"]


def test_request_id_is_echoed_when_provided() -> None:
    response = client.get("/nope", headers={"X-Request-ID": "abc123"})

    assert response.headers["X-Request-ID"] == "abc123"
