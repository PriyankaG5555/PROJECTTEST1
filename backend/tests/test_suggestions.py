"""Trip priority/budget fields and OpenStreetMap suggestions — contract §3, §5 (US-7a/b/c)."""

import pytest
from fastapi.testclient import TestClient

from app.services import suggestion_service
from app.services.osm_service import ATTRIBUTION
from tests.helpers import API, create_trip
from tests.osm_fixtures import FakeOSM


def names(client: TestClient, trip_id: str) -> list[str]:
    response = client.get(f"{API}/trips/{trip_id}/suggestions")
    assert response.status_code == 200, response.text
    return [s["name"] for s in response.json()["suggestions"]]


# ---------- Trip priority and budget ----------
def test_trip_priority_and_budget_round_trip(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client, topPriority="budget", budget=10000.555)

    assert trip["topPriority"] == "budget" and trip["budget"] == 10000.56

    url = f"{API}/trips/{trip['id']}"
    updated = logged_in_client.patch(url, json={"topPriority": "time"}).json()["trip"]
    assert updated["topPriority"] == "time" and updated["budget"] == 10000.56

    cleared = logged_in_client.patch(url, json={"topPriority": None, "budget": None}).json()["trip"]
    assert cleared["topPriority"] is None and cleared["budget"] is None


@pytest.mark.parametrize(("field", "value"), [("topPriority", "cost"), ("budget", -1)])
def test_priority_and_budget_validation(
    logged_in_client: TestClient, field: str, value: object
) -> None:
    response = logged_in_client.post(
        f"{API}/trips",
        json={
            "destination": "Goa",
            "startDate": "2026-11-14",
            "endDate": "2026-11-17",
            "tripType": "friends",
            field: value,
        },
    )

    assert response.status_code == 400
    assert field in response.json()["error"]["details"]["fields"]


# ---------- Suggestions ----------
def test_budget_priority_lists_free_places_first(
    logged_in_client: TestClient, osm: FakeOSM
) -> None:
    trip = create_trip(logged_in_client, topPriority="budget")

    assert names(logged_in_client, trip["id"]) == [
        "Calangute Beach",
        "Miramar Beach",
        "Fort Aguada",
        "Goa State Museum",
        "Casino Royale",
    ]


def test_default_order_is_most_notable_first(logged_in_client: TestClient, osm: FakeOSM) -> None:
    trip = create_trip(logged_in_client)

    body = logged_in_client.get(f"{API}/trips/{trip['id']}/suggestions").json()

    assert [s["name"] for s in body["suggestions"]][:3] == [
        "Fort Aguada",
        "Calangute Beach",
        "Goa State Museum",
    ]
    assert body["attribution"] == ATTRIBUTION and body["orderedBy"] is None
    beach = body["suggestions"][1]
    assert beach == {
        "placeId": "osm:node/3",
        "name": "Calangute Beach",
        "category": "Beach",
        "address": "Goa",
        "rating": None,
        "ratingCount": None,
        "priceLevel": "free",
        "mapsUrl": "https://www.openstreetmap.org/node/3",
    }


def test_places_are_cached_per_destination(logged_in_client: TestClient, osm: FakeOSM) -> None:
    goa = create_trip(logged_in_client)
    other_goa = create_trip(logged_in_client, destination="  GOA ")

    names(logged_in_client, goa["id"])
    names(logged_in_client, other_goa["id"])

    assert osm.calls == ["Goa"]  # second request served from place_cache


def test_map_failure_means_unavailable(logged_in_client: TestClient, osm: FakeOSM) -> None:
    osm.fail = True
    trip = create_trip(logged_in_client)

    response = logged_in_client.get(f"{API}/trips/{trip['id']}/suggestions")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SUGGESTIONS_UNAVAILABLE"


def test_unknown_destination_returns_empty_list(logged_in_client: TestClient, osm: FakeOSM) -> None:
    osm.places = []
    trip = create_trip(logged_in_client, destination="Nowhereville")

    assert names(logged_in_client, trip["id"]) == []


def test_daily_limit(
    logged_in_client: TestClient, osm: FakeOSM, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(suggestion_service, "DAILY_LIMIT", 2)
    trip = create_trip(logged_in_client)
    url = f"{API}/trips/{trip['id']}/suggestions"

    assert [logged_in_client.get(url).status_code for _ in range(3)] == [200, 200, 429]


def test_other_users_trip_not_found(
    logged_in_client: TestClient, other_user_client: TestClient, osm: FakeOSM
) -> None:
    trip = create_trip(logged_in_client)

    assert other_user_client.get(f"{API}/trips/{trip['id']}/suggestions").status_code == 404
    assert osm.calls == []
