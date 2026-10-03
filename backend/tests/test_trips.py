"""Trip endpoints — api-contract-spec.md §5."""

import uuid
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import Activity, Draft, Trip, TripStatus

TRIPS = "/api/v1/trips"
GOA = {
    "destination": "Goa",
    "startDate": "2026-11-14",
    "endDate": "2026-11-17",
    "tripType": "friends",
}


def create(client: TestClient, **overrides: Any) -> dict[str, Any]:
    response = client.post(TRIPS, json={**GOA, **overrides})
    assert response.status_code == 201, response.text
    trip: dict[str, Any] = response.json()["trip"]
    return trip


def add_activity(db: Session, draft_id: str, day: int, name: str, cost: str | None = None) -> None:
    db.add(
        Activity(
            draft_id=uuid.UUID(draft_id),
            day_number=day,
            destination_name=name,
            cost=Decimal(cost) if cost else None,
        )
    )
    db.commit()


def finalize_in_db(db: Session, trip: dict[str, Any]) -> None:
    db.execute(
        update(Trip)
        .where(Trip.id == uuid.UUID(trip["id"]))
        .values(status=TripStatus.FINALIZED, finalized_draft_id=uuid.UUID(trip["drafts"][0]["id"]))
    )
    db.commit()


# ---------- Create ----------
def test_create_trip_with_first_draft(logged_in_client: TestClient) -> None:
    trip = create(logged_in_client)

    assert trip["destination"] == "Goa"
    assert trip["startDate"] == "2026-11-14" and trip["endDate"] == "2026-11-17"
    assert trip["tripType"] == "friends"
    assert trip["status"] == "draft"
    assert trip["finalizedDraftId"] is None
    assert trip["dayCount"] == 4 and trip["draftCount"] == 1
    assert [d["name"] for d in trip["drafts"]] == ["Draft 1"]
    draft = trip["drafts"][0]
    assert draft == {
        "id": draft["id"],
        "name": "Draft 1",
        "isFinal": False,
        "activityCount": 0,
        "totalCost": 0.0,
        "updatedAt": draft["updatedAt"],
    }


def test_destination_is_trimmed(logged_in_client: TestClient) -> None:
    assert create(logged_in_client, destination="  Goa  ")["destination"] == "Goa"


@pytest.mark.parametrize(
    ("start", "end", "days"), [("2026-11-14", "2026-11-14", 1), ("2026-11-01", "2026-11-30", 30)]
)
def test_trip_length_limits_allowed(
    logged_in_client: TestClient, start: str, end: str, days: int
) -> None:
    assert create(logged_in_client, startDate=start, endDate=end)["dayCount"] == days


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"endDate": "2026-11-13"}, "endDate"),
        ({"startDate": "2026-11-01", "endDate": "2026-12-01"}, "endDate"),  # 31 days
        ({"destination": "   "}, "destination"),
        ({"destination": "x" * 101}, "destination"),
        ({"tripType": "corporate"}, "tripType"),
        ({"startDate": "14-11-2026"}, "startDate"),
    ],
)
def test_create_validation(
    logged_in_client: TestClient, overrides: dict[str, str], field: str
) -> None:
    response = logged_in_client.post(TRIPS, json={**GOA, **overrides})

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert field in error["details"]["fields"]


def test_create_requires_all_fields(logged_in_client: TestClient) -> None:
    response = logged_in_client.post(TRIPS, json={})

    fields = response.json()["error"]["details"]["fields"]
    assert set(fields) == {"destination", "startDate", "endDate", "tripType"}


def test_trips_require_login(client: TestClient, db: Session) -> None:
    assert client.get(TRIPS).status_code == 401
    assert client.post(TRIPS, json=GOA).status_code == 401


# ---------- List / get ----------
def test_list_newest_first_with_counts(logged_in_client: TestClient) -> None:
    goa = create(logged_in_client)
    jaipur = create(logged_in_client, destination="Jaipur", tripType="family")

    trips = logged_in_client.get(TRIPS).json()["trips"]

    assert [t["id"] for t in trips] == [jaipur["id"], goa["id"]]
    assert "drafts" not in trips[0]
    assert trips[0]["draftCount"] == 1 and trips[0]["dayCount"] == 4


def test_list_status_filter(logged_in_client: TestClient, db: Session) -> None:
    goa = create(logged_in_client)
    create(logged_in_client, destination="Jaipur")
    finalize_in_db(db, goa)

    finalized = logged_in_client.get(TRIPS, params={"status": "finalized"}).json()["trips"]
    drafts = logged_in_client.get(TRIPS, params={"status": "draft"}).json()["trips"]

    assert [t["destination"] for t in finalized] == ["Goa"]
    assert [t["destination"] for t in drafts] == ["Jaipur"]


def test_list_invalid_status(logged_in_client: TestClient) -> None:
    response = logged_in_client.get(TRIPS, params={"status": "done"})

    assert response.status_code == 400
    assert "status" in response.json()["error"]["details"]["fields"]


def test_users_only_see_their_own_trips(
    logged_in_client: TestClient, other_user_client: TestClient
) -> None:
    trip = create(logged_in_client)

    assert other_user_client.get(TRIPS).json()["trips"] == []
    for method in ("GET", "PATCH", "DELETE"):
        response = other_user_client.request(method, f"{TRIPS}/{trip['id']}", json={})
        assert response.status_code == 404, method
        assert response.json()["error"]["code"] == "NOT_FOUND"


def test_get_trip_with_draft_summaries(logged_in_client: TestClient, db: Session) -> None:
    trip = create(logged_in_client)
    draft_id = trip["drafts"][0]["id"]
    add_activity(db, draft_id, 1, "Baga Beach", "0")
    add_activity(db, draft_id, 1, "Fort Aguada", "300")
    add_activity(db, draft_id, 2, "Seafood dinner", "2000.50")
    add_activity(db, draft_id, 3, "Walk")

    fetched = logged_in_client.get(f"{TRIPS}/{trip['id']}").json()["trip"]

    assert fetched["drafts"][0]["activityCount"] == 4
    assert fetched["drafts"][0]["totalCost"] == 2300.5


@pytest.mark.parametrize("trip_id", [str(uuid.uuid4()), "not-a-uuid"])
def test_unknown_trip_is_not_found(logged_in_client: TestClient, trip_id: str) -> None:
    response = logged_in_client.get(f"{TRIPS}/{trip_id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# ---------- Update ----------
def test_update_details(logged_in_client: TestClient) -> None:
    trip = create(logged_in_client)

    response = logged_in_client.patch(
        f"{TRIPS}/{trip['id']}", json={"destination": "North Goa", "tripType": "couple"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["deletedActivityCount"] == 0
    assert body["trip"]["destination"] == "North Goa"
    assert body["trip"]["tripType"] == "couple"
    assert body["trip"]["startDate"] == "2026-11-14"  # unchanged
    assert body["trip"]["updatedAt"] > trip["updatedAt"]


def test_update_moves_trip_to_top_of_list(logged_in_client: TestClient) -> None:
    goa = create(logged_in_client)
    create(logged_in_client, destination="Jaipur")

    logged_in_client.patch(f"{TRIPS}/{goa['id']}", json={"destination": "Goa!"})

    assert logged_in_client.get(TRIPS).json()["trips"][0]["id"] == goa["id"]


def test_lengthen_trip(logged_in_client: TestClient) -> None:
    trip = create(logged_in_client)

    response = logged_in_client.patch(f"{TRIPS}/{trip['id']}", json={"endDate": "2026-11-20"})

    assert response.json()["trip"]["dayCount"] == 7


def test_update_date_rules_use_existing_values(logged_in_client: TestClient) -> None:
    trip = create(logged_in_client)

    response = logged_in_client.patch(f"{TRIPS}/{trip['id']}", json={"startDate": "2026-11-18"})

    assert response.status_code == 400
    assert "endDate" in response.json()["error"]["details"]["fields"]


def test_null_for_required_field_rejected(logged_in_client: TestClient) -> None:
    trip = create(logged_in_client)

    response = logged_in_client.patch(f"{TRIPS}/{trip['id']}", json={"destination": None})

    assert response.status_code == 400
    assert "destination" in response.json()["error"]["details"]["fields"]


def test_shorten_without_activities_on_removed_days(
    logged_in_client: TestClient, db: Session
) -> None:
    trip = create(logged_in_client)
    add_activity(db, trip["drafts"][0]["id"], 2, "Baga Beach")

    response = logged_in_client.patch(f"{TRIPS}/{trip['id']}", json={"endDate": "2026-11-15"})

    assert response.status_code == 200
    assert response.json()["trip"]["dayCount"] == 2
    assert response.json()["deletedActivityCount"] == 0


def test_shorten_requires_confirmation_then_deletes(
    logged_in_client: TestClient, db: Session
) -> None:
    trip = create(logged_in_client)
    draft_id = trip["drafts"][0]["id"]
    add_activity(db, draft_id, 1, "Baga Beach")
    add_activity(db, draft_id, 3, "Dudhsagar Falls")
    add_activity(db, draft_id, 4, "Airport")
    url = f"{TRIPS}/{trip['id']}"

    first = logged_in_client.patch(url, json={"endDate": "2026-11-15"})

    assert first.status_code == 409
    error = first.json()["error"]
    assert error["code"] == "ACTIVITIES_WOULD_BE_DELETED"
    assert error["message"] == "Shortening this trip will delete 2 activities."
    affected = error["details"]["affected"]
    assert [(a["dayNumber"], a["destinationName"]) for a in affected] == [
        (3, "Dudhsagar Falls"),
        (4, "Airport"),
    ]
    assert set(affected[0]) == {
        "draftId",
        "draftName",
        "dayNumber",
        "activityId",
        "destinationName",
    }
    assert logged_in_client.get(url).json()["trip"]["dayCount"] == 4  # nothing changed

    second = logged_in_client.patch(
        url, json={"endDate": "2026-11-15", "confirmDeleteActivities": True}
    )

    assert second.status_code == 200
    assert second.json()["deletedActivityCount"] == 2
    assert second.json()["trip"]["dayCount"] == 2
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Activity)) == 1


def test_finalized_trip_cannot_be_edited(logged_in_client: TestClient, db: Session) -> None:
    trip = create(logged_in_client)
    finalize_in_db(db, trip)

    response = logged_in_client.patch(f"{TRIPS}/{trip['id']}", json={"destination": "Goa!"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TRIP_FINALIZED"


# ---------- Delete ----------
def test_delete_trip_and_everything_in_it(logged_in_client: TestClient, db: Session) -> None:
    trip = create(logged_in_client)
    add_activity(db, trip["drafts"][0]["id"], 1, "Baga Beach")

    response = logged_in_client.delete(f"{TRIPS}/{trip['id']}")

    assert response.status_code == 204
    assert logged_in_client.get(f"{TRIPS}/{trip['id']}").status_code == 404
    db.expire_all()
    for model in (Trip, Draft, Activity):
        assert db.scalar(select(func.count()).select_from(model)) == 0


def test_finalized_trip_can_be_deleted(logged_in_client: TestClient, db: Session) -> None:
    trip = create(logged_in_client)
    finalize_in_db(db, trip)

    assert logged_in_client.delete(f"{TRIPS}/{trip['id']}").status_code == 204
