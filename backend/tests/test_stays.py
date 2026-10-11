"""Stays, hotel suggestions and hotel-aware planning — accommodation-feature.md §5."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.models import TripPriority
from app.services import hotel_service
from app.services.planner_service import plan_day, travel_minutes
from tests.helpers import API, create_trip, finalize, first_draft_id
from tests.osm_fixtures import MUSEUM, PLACES, FakeOSM, place

HOTEL = {"name": "Hotel Mandovi", "lat": 15.4989, "lon": 73.8278}
NOMINATIM = [
    {
        "category": "tourism",
        "type": "hotel",
        "name": "Hotel Mandovi",
        "osm_type": "node",
        "osm_id": 1,
        "lat": "15.4989",
        "lon": "73.8278",
        "display_name": "Hotel Mandovi, D.B. Marg, Panaji, Goa",
        "extratags": {"stars": "3", "website": "https://mandovi.example"},
    },
    {
        "category": "tourism",
        "type": "hostel",
        "name": "Bunkd Hostel",
        "osm_type": "node",
        "osm_id": 2,
        "lat": "15.55",
        "lon": "73.75",
        "display_name": "Bunkd Hostel, Calangute, Goa",
    },
    {
        "category": "tourism",
        "type": "guest_house",
        "name": "Guest House",
        "osm_type": "node",
        "osm_id": 3,
        "lat": "15.5",
        "lon": "73.8",
        "display_name": "x",
    },  # generic name -> dropped
    {
        "category": "tourism",
        "type": "hostel",
        "name": "International Students Hostel",
        "osm_type": "way",
        "osm_id": 4,
        "lat": "15.5",
        "lon": "73.8",
        "display_name": "x",
    },  # institutional -> dropped
    {
        "category": "amenity",
        "type": "restaurant",
        "name": "Fish Thali",
        "osm_type": "node",
        "osm_id": 5,
        "lat": "15.5",
        "lon": "73.8",
        "display_name": "x",
    },  # not accommodation
]


def stay(client: TestClient, trip: dict[str, Any], **fields: Any) -> Any:
    body = {"name": "Hotel Mandovi", "checkInDay": 1, "checkOutDay": 3, **fields}
    return client.post(f"{API}/trips/{trip['id']}/stays", json=body)


@pytest.fixture
def hotels(monkeypatch: pytest.MonkeyPatch, osm: FakeOSM) -> list[str]:
    calls: list[str] = []

    def fake(destination: str) -> list[dict[str, Any]]:
        calls.append(destination)
        return hotel_service.normalize(NOMINATIM)

    monkeypatch.setattr(hotel_service, "fetch_hotels", fake)
    return calls


# ---------- Stays ----------
def test_add_stay_and_trip_detail_totals(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)  # 4 days

    response = stay(
        logged_in_client, trip, costPerNight=3500, lat=15.4989, lon=73.8278, placeId="osm:node/1"
    )

    assert response.status_code == 201, response.text
    created = response.json()["stay"]
    assert created["nights"] == 2 and created["totalCost"] == 7000 and created["verified"] is True
    detail = logged_in_client.get(f"{API}/trips/{trip['id']}").json()["trip"]
    assert [s["name"] for s in detail["stays"]] == ["Hotel Mandovi"] and detail[
        "staysTotalCost"
    ] == 7000


@pytest.mark.parametrize(
    ("fields", "field"),
    [
        ({"checkInDay": 5, "checkOutDay": 6}, "checkInDay"),
        ({"checkOutDay": 1}, "checkOutDay"),
        ({"checkOutDay": 6}, "checkOutDay"),
        ({"name": ""}, "name"),
        ({"costPerNight": -1}, "costPerNight"),
    ],
)
def test_stay_validation(logged_in_client: TestClient, fields: dict[str, Any], field: str) -> None:
    response = stay(logged_in_client, create_trip(logged_in_client), **fields)

    assert response.status_code == 400
    assert field in response.json()["error"]["details"]["fields"]


def test_overlapping_stays_rejected_back_to_back_allowed(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)
    stay(logged_in_client, trip)  # nights 1-2

    overlap = stay(logged_in_client, trip, name="Other", checkInDay=2, checkOutDay=4)
    next_stay = stay(logged_in_client, trip, name="Beach Hut", checkInDay=3, checkOutDay=5)

    assert overlap.status_code == 409 and overlap.json()["error"]["code"] == "STAY_OVERLAP"
    assert next_stay.status_code == 201


def test_edit_and_delete_stay(logged_in_client: TestClient, other_user_client: TestClient) -> None:
    trip = create_trip(logged_in_client)
    stay_id = stay(logged_in_client, trip, costPerNight=1000).json()["stay"]["id"]

    edited = logged_in_client.patch(
        f"{API}/stays/{stay_id}", json={"checkOutDay": 4, "costPerNight": None}
    )
    assert edited.status_code == 200
    assert edited.json()["stay"]["nights"] == 3 and edited.json()["stay"]["totalCost"] is None
    assert other_user_client.delete(f"{API}/stays/{stay_id}").status_code == 404
    assert logged_in_client.delete(f"{API}/stays/{stay_id}").status_code == 204


def test_stays_locked_when_finalized(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)
    finalize(logged_in_client, trip)

    assert stay(logged_in_client, trip).json()["error"]["code"] == "TRIP_FINALIZED"


def test_shortening_trip_lists_and_removes_stays(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)  # days 1-4
    stay(logged_in_client, trip, checkInDay=1, checkOutDay=3)
    stay(logged_in_client, trip, name="Beach Hut", checkInDay=3, checkOutDay=5)
    url = f"{API}/trips/{trip['id']}"

    first = logged_in_client.patch(url, json={"endDate": "2026-11-15"})  # 2 days
    assert first.status_code == 409
    assert [s["name"] for s in first.json()["error"]["details"]["affectedStays"]] == ["Beach Hut"]

    second = logged_in_client.patch(
        url, json={"endDate": "2026-11-15", "confirmDeleteActivities": True}
    )
    stays = second.json()["trip"]["stays"]
    assert [(s["name"], s["checkInDay"], s["checkOutDay"]) for s in stays] == [
        ("Hotel Mandovi", 1, 3)
    ]


# ---------- Hotel suggestions ----------
def test_hotel_suggestions_normalized_and_ordered(
    logged_in_client: TestClient, hotels: list[str]
) -> None:
    trip = create_trip(logged_in_client, topPriority="budget")

    body = logged_in_client.get(f"{API}/trips/{trip['id']}/hotel-suggestions").json()

    assert [h["name"] for h in body["hotels"]] == [
        "Bunkd Hostel",
        "Hotel Mandovi",
    ]  # budget: hostel first
    mandovi = body["hotels"][1]
    assert mandovi["kind"] == "hotel" and mandovi["stars"] == 3
    assert (
        mandovi["website"] == "https://mandovi.example"
        and mandovi["address"] == "D.B. Marg, Panaji"
    )
    assert mandovi["mapsUrl"] == "https://www.openstreetmap.org/node/1"
    assert body["attribution"] == "© OpenStreetMap contributors"
    logged_in_client.get(f"{API}/trips/{trip['id']}/hotel-suggestions")
    assert hotels == ["Goa"]  # cached


def test_hotel_suggestions_map_failure(logged_in_client: TestClient, osm: FakeOSM) -> None:
    osm.fail = True
    trip = create_trip(logged_in_client)

    assert logged_in_client.get(f"{API}/trips/{trip['id']}/hotel-suggestions").status_code == 503


# ---------- Hotel-aware planning ----------
def test_plan_starts_from_hotel_and_returns_in_time() -> None:
    window = (9 * 60, 13 * 60)
    plan = plan_day(
        PLACES,
        must_visit=[],
        avoid=[],
        interests=[],
        priority=None,
        window=window,
        busy=[],
        hotel=HOTEL,
        return_to_hotel=True,
    )

    first, last = plan.items[0], plan.items[-1]
    assert first.start >= window[0] + travel_minutes(HOTEL, first.place) - 5
    assert "km from your hotel" in first.reason
    assert last.start + last.duration + travel_minutes(last.place, HOTEL) <= window[1]


def test_places_near_hotel_rank_higher() -> None:
    far = place("9", "Aaa Far Fort", "Fort", 3, False, 16.2, 73.5)  # ~85 km away, same notability
    common: dict[str, Any] = {
        "must_visit": [],
        "avoid": [],
        "interests": [],
        "priority": TripPriority.DESTINATIONS,
        "window": (9 * 60, 18 * 60),
        "busy": [],
    }

    without_hotel = plan_day([far, MUSEUM], **common)
    with_hotel = plan_day([far, MUSEUM], **common, hotel=HOTEL)

    assert without_hotel.items[0].place is far  # tie broken by name
    assert with_hotel.items[0].place is MUSEUM  # near-hotel bonus


def test_plan_api_uses_night_stay(logged_in_client: TestClient, osm: FakeOSM) -> None:
    trip = create_trip(logged_in_client)
    stay(logged_in_client, trip, lat=15.4989, lon=73.8278, placeId="osm:node/1")
    draft_id = first_draft_id(trip)
    url = f"{API}/trips/{trip['id']}/ai-plans"
    body = {"draftId": draft_id, "dayNumber": 1, "startTime": "09:00", "endTime": "18:00"}

    with_stay = logged_in_client.post(url, json=body).json()
    without = logged_in_client.post(url, json={**body, "useStay": False}).json()
    no_night = logged_in_client.post(url, json={**body, "dayNumber": 4}).json()

    assert with_stay["startPoint"] == {"name": "Hotel Mandovi", "lat": 15.4989, "lon": 73.8278}
    assert without["startPoint"] is None
    assert no_night["startPoint"] is None and any("No hotel set" in w for w in no_night["warnings"])
