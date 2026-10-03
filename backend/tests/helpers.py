"""Small API helpers shared by endpoint tests."""

from typing import Any

from fastapi.testclient import TestClient

API = "/api/v1"
GOA = {
    "destination": "Goa",
    "startDate": "2026-11-14",
    "endDate": "2026-11-17",
    "tripType": "friends",
}


def create_trip(client: TestClient, **overrides: Any) -> dict[str, Any]:
    response = client.post(f"{API}/trips", json={**GOA, **overrides})
    assert response.status_code == 201, response.text
    trip: dict[str, Any] = response.json()["trip"]
    return trip


def first_draft_id(trip: dict[str, Any]) -> str:
    draft_id: str = trip["drafts"][0]["id"]
    return draft_id


def add_activity(client: TestClient, draft_id: str, **fields: Any) -> dict[str, Any]:
    body = {"dayNumber": 1, "destinationName": "Baga Beach", **fields}
    response = client.post(f"{API}/drafts/{draft_id}/activities", json=body)
    assert response.status_code == 201, response.text
    activity: dict[str, Any] = response.json()["activity"]
    return activity


def get_draft(client: TestClient, draft_id: str) -> dict[str, Any]:
    response = client.get(f"{API}/drafts/{draft_id}")
    assert response.status_code == 200, response.text
    draft: dict[str, Any] = response.json()["draft"]
    return draft


def finalize(client: TestClient, trip: dict[str, Any], draft_id: str | None = None) -> None:
    response = client.post(
        f"{API}/trips/{trip['id']}/finalize", json={"draftId": draft_id or first_draft_id(trip)}
    )
    assert response.status_code == 200, response.text
