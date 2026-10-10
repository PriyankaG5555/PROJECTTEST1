"""Day planning API ("Plan my day") and activity duration — ai-feature.md §8 (fake map data)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.services.osm_service import ATTRIBUTION
from tests.helpers import API, add_activity, create_trip, finalize, first_draft_id, get_draft
from tests.osm_fixtures import FakeOSM


def plan(client: TestClient, trip: dict[str, Any], **body: Any) -> Any:
    payload = {
        "draftId": first_draft_id(trip),
        "dayNumber": 1,
        "startTime": "09:00",
        "endTime": "18:00",
        **body,
    }
    return client.post(f"{API}/trips/{trip['id']}/ai-plans", json=payload)


def apply(client: TestClient, draft_id: str, token: str, ids: list[str]) -> Any:
    return client.post(
        f"{API}/drafts/{draft_id}/activities/bulk",
        json={"proposalToken": token, "selectedItemIds": ids},
    )


# ---------- Activity duration ----------
def test_duration_saved_and_validated(logged_in_client: TestClient) -> None:
    draft_id = first_draft_id(create_trip(logged_in_client))

    activity = add_activity(logged_in_client, draft_id, time="10:00", durationMinutes=90)
    assert activity["durationMinutes"] == 90

    url = f"{API}/drafts/{draft_id}/activities"
    no_time = logged_in_client.post(
        url, json={"dayNumber": 1, "destinationName": "X", "durationMinutes": 30}
    )
    past_midnight = logged_in_client.post(
        url, json={"dayNumber": 1, "destinationName": "X", "time": "23:30", "durationMinutes": 60}
    )
    clear_time = logged_in_client.patch(f"{API}/activities/{activity['id']}", json={"time": None})
    for response in (no_time, past_midnight, clear_time):
        assert response.status_code == 400
        assert "durationMinutes" in response.json()["error"]["details"]["fields"]


# ---------- Generate ----------
def test_generate_returns_grounded_schedule(logged_in_client: TestClient, osm: FakeOSM) -> None:
    trip = create_trip(logged_in_client)

    response = plan(logged_in_client, trip, avoid=["casino"])

    assert response.status_code == 200, response.text
    body = response.json()
    first = body["activities"][0]
    assert first["destinationName"] == "Fort Aguada" and first["time"] == "09:00"
    assert first["durationMinutes"] == 90 and first["cost"] is None and first["verified"] is True
    assert first["placeId"] == "osm:node/1" and first["source"] == "Wikipedia"
    assert first["attribution"] == ATTRIBUTION
    assert first["mapsUrl"] == "https://www.openstreetmap.org/node/1" and first["reason"]
    assert "Casino Royale" not in [a["destinationName"] for a in body["activities"]]
    assert any("straight-line distance" in w for w in body["warnings"])
    assert (
        get_draft(logged_in_client, first_draft_id(trip))["days"][0]["activities"] == []
    )  # no mutation


def test_unknown_destination_plans_only_must_visit(
    logged_in_client: TestClient, osm: FakeOSM
) -> None:
    osm.places = []
    trip = create_trip(logged_in_client, destination="Nowhereville")

    body = plan(logged_in_client, trip, mustVisit=["Aunty's Cafe"]).json()

    assert [(a["destinationName"], a["verified"]) for a in body["activities"]] == [
        ("Aunty's Cafe", False)
    ]
    assert any("couldn't find places" in w for w in body["warnings"])


def test_existing_activities_are_fixed_constraints(
    logged_in_client: TestClient, osm: FakeOSM
) -> None:
    trip = create_trip(logged_in_client)
    draft_id = first_draft_id(trip)
    add_activity(logged_in_client, draft_id, time="09:00", durationMinutes=120)
    add_activity(logged_in_client, draft_id, time="15:00")  # no duration -> blocks rest of window

    body = plan(logged_in_client, trip).json()

    for a in body["activities"]:
        start = int(a["time"][:2]) * 60 + int(a["time"][3:])
        assert start >= 11 * 60 and start + a["durationMinutes"] <= 15 * 60
    assert any("no duration" in w for w in body["warnings"])


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"startTime": "18:00", "endTime": "09:00"}, "endTime"),
        ({"dayNumber": 9}, "dayNumber"),
        ({"interests": ["x"] * 6}, "interests"),
        ({"startTime": "9am"}, "startTime"),
    ],
)
def test_generate_validation(
    logged_in_client: TestClient, osm: FakeOSM, body: dict[str, Any], field: str
) -> None:
    response = plan(logged_in_client, create_trip(logged_in_client), **body)

    assert response.status_code == 400
    assert field in response.json()["error"]["details"]["fields"]


def test_generate_access_rules(
    logged_in_client: TestClient, other_user_client: TestClient, osm: FakeOSM
) -> None:
    goa = create_trip(logged_in_client)
    jaipur = create_trip(logged_in_client, destination="Jaipur")

    assert plan(other_user_client, goa).status_code == 404
    assert plan(logged_in_client, goa, draftId=first_draft_id(jaipur)).status_code == 404
    finalize(logged_in_client, goa)
    assert plan(logged_in_client, goa).json()["error"]["code"] == "TRIP_FINALIZED"


def test_map_failure_and_daily_limit(
    logged_in_client: TestClient, osm: FakeOSM, monkeypatch: pytest.MonkeyPatch
) -> None:
    trip = create_trip(logged_in_client)
    osm.fail = True
    failed = plan(logged_in_client, trip)
    assert failed.status_code == 503 and failed.json()["error"]["code"] == "AI_PLANNING_UNAVAILABLE"

    osm.fail = False
    monkeypatch.setattr(get_settings(), "ai_plan_daily_limit", 2)
    assert plan(logged_in_client, trip).status_code == 200  # 2nd request today
    assert plan(logged_in_client, trip).json()["error"]["code"] == "RATE_LIMITED"


# ---------- Apply ----------
def test_apply_selected_items_once(logged_in_client: TestClient, osm: FakeOSM) -> None:
    trip = create_trip(logged_in_client)
    draft_id = first_draft_id(trip)
    proposal = plan(logged_in_client, trip).json()
    second = proposal["activities"][1]

    response = apply(logged_in_client, draft_id, proposal["proposalToken"], [second["itemId"]])

    assert response.status_code == 201
    added = response.json()["activities"]
    assert [(a["destinationName"], a["time"], a["durationMinutes"], a["cost"]) for a in added] == [
        (second["destinationName"], second["time"], second["durationMinutes"], None)
    ]
    again = apply(logged_in_client, draft_id, proposal["proposalToken"], ["item-1"])
    assert again.status_code == 409 and again.json()["error"]["code"] == "AI_PROPOSAL_INVALID"


def test_apply_out_of_date_adds_nothing(logged_in_client: TestClient, osm: FakeOSM) -> None:
    trip = create_trip(logged_in_client)
    draft_id = first_draft_id(trip)
    token = plan(logged_in_client, trip).json()["proposalToken"]
    add_activity(
        logged_in_client, draft_id, time="09:30", durationMinutes=30
    )  # edit after generation

    response = apply(logged_in_client, draft_id, token, ["item-1"])

    assert response.status_code == 409
    assert len(get_draft(logged_in_client, draft_id)["days"][0]["activities"]) == 1


def test_apply_rejects_wrong_draft_user_or_token(
    logged_in_client: TestClient, other_user_client: TestClient, osm: FakeOSM
) -> None:
    trip = create_trip(logged_in_client)
    token = plan(logged_in_client, trip).json()["proposalToken"]
    other_draft = logged_in_client.post(
        f"{API}/trips/{trip['id']}/drafts", json={"name": "Plan B"}
    ).json()["draft"]["id"]

    assert apply(logged_in_client, other_draft, token, ["item-1"]).status_code == 409
    assert apply(logged_in_client, first_draft_id(trip), token + "x", ["item-1"]).status_code == 409
    assert apply(other_user_client, first_draft_id(trip), token, ["item-1"]).status_code == 404
    bad = apply(logged_in_client, first_draft_id(trip), token, ["item-9"])
    assert bad.status_code == 400 and "selectedItemIds" in bad.json()["error"]["details"]["fields"]


def test_apply_blocked_when_finalized(logged_in_client: TestClient, osm: FakeOSM) -> None:
    trip = create_trip(logged_in_client)
    token = plan(logged_in_client, trip).json()["proposalToken"]
    finalize(logged_in_client, trip)

    response = apply(logged_in_client, first_draft_id(trip), token, ["item-1"])

    assert response.json()["error"]["code"] == "TRIP_FINALIZED"
