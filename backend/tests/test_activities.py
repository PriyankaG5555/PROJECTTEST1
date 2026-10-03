"""Draft view (days + sorting + totals) and activity endpoints — api-contract-spec.md §3, §5."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import API, add_activity, create_trip, first_draft_id, get_draft


def test_draft_has_every_day_even_empty_ones(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)

    draft = get_draft(logged_in_client, first_draft_id(trip))

    assert draft["name"] == "Draft 1" and draft["isFinal"] is False
    assert draft["tripId"] == trip["id"]
    assert [(d["dayNumber"], d["date"]) for d in draft["days"]] == [
        (1, "2026-11-14"),
        (2, "2026-11-15"),
        (3, "2026-11-16"),
        (4, "2026-11-17"),
    ]
    assert all(d["activities"] == [] and d["totalCost"] == 0 for d in draft["days"])
    assert draft["totalCost"] == 0


def test_contract_example_sorting_and_totals(logged_in_client: TestClient) -> None:
    draft_id = first_draft_id(create_trip(logged_in_client))
    add_activity(logged_in_client, draft_id, destinationName="Seafood dinner", cost=2000)
    add_activity(
        logged_in_client,
        draft_id,
        destinationName="Fort Aguada",
        time="15:00",
        cost=300,
    )
    add_activity(
        logged_in_client,
        draft_id,
        destinationName="Baga Beach",
        time="09:30",
        cost=0,
    )
    add_activity(logged_in_client, draft_id, dayNumber=3, destinationName="Falls", cost=6100)

    draft = get_draft(logged_in_client, draft_id)

    day1 = draft["days"][0]
    assert [a["destinationName"] for a in day1["activities"]] == [
        "Baga Beach",
        "Fort Aguada",
        "Seafood dinner",  # no time -> last
    ]
    assert day1["totalCost"] == 2300
    assert draft["days"][2]["totalCost"] == 6100
    assert draft["totalCost"] == 8400


def test_add_activity_returns_contract_shape(logged_in_client: TestClient) -> None:
    draft_id = first_draft_id(create_trip(logged_in_client))

    activity = add_activity(
        logged_in_client,
        draft_id,
        destinationName="  Baga Beach ",
        time="09:30",
        cost=12.345,
    )

    assert activity == {
        "id": activity["id"],
        "dayNumber": 1,
        "destinationName": "Baga Beach",
        "time": "09:30",
        "cost": 12.35,
    }


def test_optional_fields_default_to_null(logged_in_client: TestClient) -> None:
    draft_id = first_draft_id(create_trip(logged_in_client))

    activity = add_activity(logged_in_client, draft_id)

    assert activity["time"] is None and activity["cost"] is None


@pytest.mark.parametrize(
    ("fields", "bad"),
    [
        ({"destinationName": ""}, "destinationName"),
        ({"destinationName": "x" * 101}, "destinationName"),
        ({"time": "25:00"}, "time"),
        ({"time": "9:30"}, "time"),
        ({"cost": -1}, "cost"),
        ({"cost": 10_000_001}, "cost"),
        ({"dayNumber": 0}, "dayNumber"),
        ({"dayNumber": 5}, "dayNumber"),  # trip has 4 days
    ],
)
def test_activity_validation(
    logged_in_client: TestClient, fields: dict[str, Any], bad: str
) -> None:
    draft_id = first_draft_id(create_trip(logged_in_client))
    body = {"dayNumber": 1, "destinationName": "Baga Beach", **fields}

    response = logged_in_client.post(f"{API}/drafts/{draft_id}/activities", json=body)

    assert response.status_code == 400
    assert bad in response.json()["error"]["details"]["fields"]


def test_edit_and_move_activity(logged_in_client: TestClient) -> None:
    draft_id = first_draft_id(create_trip(logged_in_client))
    activity = add_activity(logged_in_client, draft_id, time="09:30", cost=100)

    response = logged_in_client.patch(
        f"{API}/activities/{activity['id']}",
        json={"dayNumber": 2, "time": None, "cost": 150},
    )

    assert response.status_code == 200
    updated = response.json()["activity"]
    assert updated["dayNumber"] == 2
    assert updated["time"] is None  # null clears
    assert updated["cost"] == 150
    days = get_draft(logged_in_client, draft_id)["days"]
    assert days[0]["activities"] == [] and len(days[1]["activities"]) == 1


@pytest.mark.parametrize("field", ["dayNumber", "destinationName"])
def test_required_fields_cannot_be_cleared(logged_in_client: TestClient, field: str) -> None:
    activity = add_activity(logged_in_client, first_draft_id(create_trip(logged_in_client)))

    response = logged_in_client.patch(f"{API}/activities/{activity['id']}", json={field: None})

    assert response.status_code == 400
    assert field in response.json()["error"]["details"]["fields"]


def test_delete_activity(logged_in_client: TestClient) -> None:
    draft_id = first_draft_id(create_trip(logged_in_client))
    activity = add_activity(logged_in_client, draft_id)

    response = logged_in_client.delete(f"{API}/activities/{activity['id']}")

    assert response.status_code == 204
    assert get_draft(logged_in_client, draft_id)["days"][0]["activities"] == []
    assert logged_in_client.delete(f"{API}/activities/{activity['id']}").status_code == 404


def test_activity_changes_bump_trip_updated_at(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)

    add_activity(logged_in_client, first_draft_id(trip))

    after = logged_in_client.get(f"{API}/trips/{trip['id']}").json()["trip"]
    assert after["updatedAt"] > trip["updatedAt"]


def test_other_users_cannot_touch_drafts_or_activities(
    logged_in_client: TestClient, other_user_client: TestClient
) -> None:
    draft_id = first_draft_id(create_trip(logged_in_client))
    activity = add_activity(logged_in_client, draft_id)

    attempts = [
        ("GET", f"{API}/drafts/{draft_id}", None),
        ("POST", f"{API}/drafts/{draft_id}/activities", {"dayNumber": 1, "destinationName": "X"}),
        ("PATCH", f"{API}/activities/{activity['id']}", {"cost": 1}),
        ("DELETE", f"{API}/activities/{activity['id']}", None),
    ]
    for method, url, body in attempts:
        response = other_user_client.request(method, url, json=body)
        assert response.status_code == 404, (method, url)
    assert get_draft(logged_in_client, draft_id)["days"][0]["activities"][0]["cost"] is None
