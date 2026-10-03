"""Trip priority/budget fields and Google Places suggestions — contract §3, §5 (US-7a/b/c)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.services import suggestion_service
from tests.helpers import API, create_trip

PLACES = [
    {
        "id": "p1",
        "displayName": {"text": "Casino Cruise"},
        "rating": 4.0,
        "userRatingCount": 900,
        "priceLevel": "PRICE_LEVEL_EXPENSIVE",
        "googleMapsUri": "https://maps.google.com/?cid=1",
        "formattedAddress": "Panaji, Goa",
    },
    {
        "id": "p2",
        "displayName": {"text": "Baga Beach"},
        "rating": 4.5,
        "userRatingCount": 80000,
        "priceLevel": "PRICE_LEVEL_FREE",
    },
    {"id": "p3", "displayName": {"text": "Hidden Cafe"}, "rating": 4.9, "userRatingCount": 40},
    {
        "id": "p4",
        "displayName": {"text": "Spice Farm"},
        "rating": 4.3,
        "userRatingCount": 5000,
        "priceLevel": "PRICE_LEVEL_INEXPENSIVE",
    },
]


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Pretend a key is configured and Google answers with PLACES. Returns queried destinations."""
    calls: list[str] = []

    def fake_fetch(destination: str, api_key: str) -> list[dict[str, Any]]:
        calls.append(destination)
        return PLACES

    monkeypatch.setattr(get_settings(), "google_places_api_key", "test-key")
    monkeypatch.setattr(suggestion_service, "fetch_places", fake_fetch)
    return calls


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
    assert (
        updated["topPriority"] == "time" and updated["budget"] == 10000.56
    )  # omitted -> unchanged

    cleared = logged_in_client.patch(url, json={"topPriority": None, "budget": None}).json()["trip"]
    assert cleared["topPriority"] is None and cleared["budget"] is None


def test_priority_and_budget_default_to_null(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)

    assert trip["topPriority"] is None and trip["budget"] is None


@pytest.mark.parametrize(
    ("field", "value"), [("topPriority", "cost"), ("budget", -1), ("budget", 10_000_001)]
)
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
def test_budget_priority_orders_cheapest_first(
    logged_in_client: TestClient, google: list[str]
) -> None:
    trip = create_trip(logged_in_client, topPriority="budget")

    assert names(logged_in_client, trip["id"]) == [
        "Baga Beach",
        "Spice Farm",
        "Hidden Cafe",
        "Casino Cruise",
    ]
    assert google == ["Goa"]


def test_destinations_priority_orders_must_see_first(
    logged_in_client: TestClient, google: list[str]
) -> None:
    trip = create_trip(logged_in_client, topPriority="destinations")

    assert names(logged_in_client, trip["id"])[0] == "Baga Beach"  # strong rating + many reviews


def test_default_order_is_by_rating(logged_in_client: TestClient, google: list[str]) -> None:
    trip = create_trip(logged_in_client)

    response = logged_in_client.get(f"{API}/trips/{trip['id']}/suggestions").json()

    assert [s["name"] for s in response["suggestions"]][0] == "Hidden Cafe"
    assert response["orderedBy"] is None and response["attribution"] == "Google"
    first = response["suggestions"][3]  # Casino Cruise: every field mapped
    assert first == {
        "placeId": "p1",
        "name": "Casino Cruise",
        "address": "Panaji, Goa",
        "rating": 4.0,
        "ratingCount": 900,
        "priceLevel": "expensive",
        "mapsUrl": "https://maps.google.com/?cid=1",
    }


def test_no_api_key_means_unavailable(
    logged_in_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "google_places_api_key", None)
    trip = create_trip(logged_in_client)

    response = logged_in_client.get(f"{API}/trips/{trip['id']}/suggestions")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SUGGESTIONS_UNAVAILABLE"


def test_google_failure_means_unavailable(
    logged_in_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(destination: str, api_key: str) -> list[dict[str, Any]]:
        raise TimeoutError

    monkeypatch.setattr(get_settings(), "google_places_api_key", "test-key")
    monkeypatch.setattr(suggestion_service, "fetch_places", broken)
    trip = create_trip(logged_in_client)

    assert logged_in_client.get(f"{API}/trips/{trip['id']}/suggestions").status_code == 503


def test_daily_limit(
    logged_in_client: TestClient, google: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(suggestion_service, "DAILY_LIMIT", 2)
    trip = create_trip(logged_in_client)
    url = f"{API}/trips/{trip['id']}/suggestions"

    assert [logged_in_client.get(url).status_code for _ in range(3)] == [200, 200, 429]


def test_other_users_trip_not_found(
    logged_in_client: TestClient, other_user_client: TestClient, google: list[str]
) -> None:
    trip = create_trip(logged_in_client)

    assert other_user_client.get(f"{API}/trips/{trip['id']}/suggestions").status_code == 404
    assert google == []
