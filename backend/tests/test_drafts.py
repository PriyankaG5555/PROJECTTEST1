"""Draft endpoints, finalize/reopen and the finalized lock — api-contract-spec.md §1, §5."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.helpers import API, add_activity, create_trip, finalize, first_draft_id, get_draft


def new_draft(
    client: TestClient, trip: dict[str, Any], name: str, copy_from: str | None = None
) -> dict[str, Any]:
    response = client.post(
        f"{API}/trips/{trip['id']}/drafts", json={"name": name, "copyFromDraftId": copy_from}
    )
    assert response.status_code == 201, response.text
    draft: dict[str, Any] = response.json()["draft"]
    return draft


# ---------- Drafts ----------
def test_create_blank_draft(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)

    draft = new_draft(logged_in_client, trip, "Hills plan")

    assert draft["name"] == "Hills plan"
    assert len(draft["days"]) == 4 and draft["totalCost"] == 0
    names = [
        d["name"] for d in logged_in_client.get(f"{API}/trips/{trip['id']}/drafts").json()["drafts"]
    ]
    assert names == ["Draft 1", "Hills plan"]  # oldest first


def test_copy_draft_copies_activities(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)
    source = first_draft_id(trip)
    add_activity(logged_in_client, source, destinationName="Baga Beach", time="09:30", cost=0)
    add_activity(logged_in_client, source, dayNumber=2, destinationName="Fort", cost=300)

    copy = new_draft(logged_in_client, trip, "Beach plan", copy_from=source)

    assert copy["totalCost"] == 300
    assert [a["destinationName"] for a in copy["days"][0]["activities"]] == ["Baga Beach"]
    # Independent copies: editing the copy leaves the source alone.
    activity_id = copy["days"][1]["activities"][0]["id"]
    logged_in_client.patch(f"{API}/activities/{activity_id}", json={"cost": 999})
    assert get_draft(logged_in_client, source)["totalCost"] == 300


def test_copy_from_other_trip_rejected(logged_in_client: TestClient) -> None:
    goa = create_trip(logged_in_client)
    jaipur = create_trip(logged_in_client, destination="Jaipur")

    response = logged_in_client.post(
        f"{API}/trips/{goa['id']}/drafts",
        json={"name": "Copy", "copyFromDraftId": first_draft_id(jaipur)},
    )

    assert response.status_code == 400
    assert "copyFromDraftId" in response.json()["error"]["details"]["fields"]


@pytest.mark.parametrize("name", ["Draft 1", "draft 1", "  DRAFT 1 "])
def test_draft_names_unique_case_insensitive(logged_in_client: TestClient, name: str) -> None:
    trip = create_trip(logged_in_client)

    response = logged_in_client.post(f"{API}/trips/{trip['id']}/drafts", json={"name": name})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DRAFT_NAME_TAKEN"


@pytest.mark.parametrize("name", ["", "   ", "x" * 51])
def test_draft_name_validation(logged_in_client: TestClient, name: str) -> None:
    trip = create_trip(logged_in_client)

    response = logged_in_client.post(f"{API}/trips/{trip['id']}/drafts", json={"name": name})

    assert response.status_code == 400
    assert "name" in response.json()["error"]["details"]["fields"]


def test_draft_limit_is_five(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)
    for i in range(2, 6):
        new_draft(logged_in_client, trip, f"Draft {i}")

    response = logged_in_client.post(f"{API}/trips/{trip['id']}/drafts", json={"name": "Six"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DRAFT_LIMIT_REACHED"


def test_rename_draft(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)
    draft_id = first_draft_id(trip)

    response = logged_in_client.patch(f"{API}/drafts/{draft_id}", json={"name": "Beach plan"})

    assert response.status_code == 200
    summary = response.json()["draft"]
    assert summary["name"] == "Beach plan"
    assert set(summary) == {"id", "name", "isFinal", "activityCount", "totalCost", "updatedAt"}
    # Renaming to its own name in a different case is allowed.
    again = logged_in_client.patch(f"{API}/drafts/{draft_id}", json={"name": "BEACH PLAN"})
    assert again.status_code == 200


def test_rename_to_taken_name(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)
    other = new_draft(logged_in_client, trip, "Hills plan")

    response = logged_in_client.patch(f"{API}/drafts/{other['id']}", json={"name": "draft 1"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DRAFT_NAME_TAKEN"


def test_delete_draft_but_never_the_last_one(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)
    other = new_draft(logged_in_client, trip, "Hills plan")

    assert logged_in_client.delete(f"{API}/drafts/{other['id']}").status_code == 204
    response = logged_in_client.delete(f"{API}/drafts/{first_draft_id(trip)}")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LAST_DRAFT"


def test_other_users_cannot_see_or_change_drafts(
    logged_in_client: TestClient, other_user_client: TestClient
) -> None:
    trip = create_trip(logged_in_client)
    draft_id = first_draft_id(trip)

    for method, url, body in [
        ("GET", f"{API}/trips/{trip['id']}/drafts", None),
        ("POST", f"{API}/trips/{trip['id']}/drafts", {"name": "Mine"}),
        ("PATCH", f"{API}/drafts/{draft_id}", {"name": "Mine"}),
        ("DELETE", f"{API}/drafts/{draft_id}", None),
        ("POST", f"{API}/trips/{trip['id']}/finalize", {"draftId": draft_id}),
        ("POST", f"{API}/trips/{trip['id']}/reopen", None),
    ]:
        assert other_user_client.request(method, url, json=body).status_code == 404, url


# ---------- Finalize / reopen ----------
def test_finalize_marks_trip_and_draft(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)
    hills = new_draft(logged_in_client, trip, "Hills plan")

    response = logged_in_client.post(
        f"{API}/trips/{trip['id']}/finalize", json={"draftId": hills["id"]}
    )

    assert response.status_code == 200
    finalized = response.json()["trip"]
    assert finalized["status"] == "finalized"
    assert finalized["finalizedDraftId"] == hills["id"]
    assert {d["name"]: d["isFinal"] for d in finalized["drafts"]} == {
        "Draft 1": False,
        "Hills plan": True,
    }
    assert get_draft(logged_in_client, hills["id"])["isFinal"] is True


def test_finalize_twice_rejected(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)
    finalize(logged_in_client, trip)

    response = logged_in_client.post(
        f"{API}/trips/{trip['id']}/finalize", json={"draftId": first_draft_id(trip)}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TRIP_FINALIZED"


def test_finalize_with_draft_from_other_trip_rejected(logged_in_client: TestClient) -> None:
    goa = create_trip(logged_in_client)
    jaipur = create_trip(logged_in_client, destination="Jaipur")

    response = logged_in_client.post(
        f"{API}/trips/{goa['id']}/finalize", json={"draftId": first_draft_id(jaipur)}
    )

    assert response.status_code == 400
    assert "draftId" in response.json()["error"]["details"]["fields"]


def test_every_change_is_blocked_while_finalized(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)
    draft_id = first_draft_id(trip)
    activity = add_activity(logged_in_client, draft_id)
    finalize(logged_in_client, trip)

    blocked = [
        ("PATCH", f"{API}/trips/{trip['id']}", {"destination": "X"}),
        ("POST", f"{API}/trips/{trip['id']}/drafts", {"name": "New"}),
        ("PATCH", f"{API}/drafts/{draft_id}", {"name": "New"}),
        ("DELETE", f"{API}/drafts/{draft_id}", None),
        ("POST", f"{API}/drafts/{draft_id}/activities", {"dayNumber": 1, "destinationName": "X"}),
        ("PATCH", f"{API}/activities/{activity['id']}", {"cost": 1}),
        ("DELETE", f"{API}/activities/{activity['id']}", None),
    ]
    for method, url, body in blocked:
        response = logged_in_client.request(method, url, json=body)
        assert response.status_code == 409, (method, url)
        assert response.json()["error"]["code"] == "TRIP_FINALIZED"

    # Reading still works.
    assert logged_in_client.get(f"{API}/drafts/{draft_id}").status_code == 200
    assert logged_in_client.get(f"{API}/trips/{trip['id']}/drafts").status_code == 200


def test_reopen_unlocks_editing(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)
    draft_id = first_draft_id(trip)
    finalize(logged_in_client, trip)

    response = logged_in_client.post(f"{API}/trips/{trip['id']}/reopen")

    assert response.status_code == 200
    reopened = response.json()["trip"]
    assert reopened["status"] == "draft" and reopened["finalizedDraftId"] is None
    assert all(d["isFinal"] is False for d in reopened["drafts"])
    add_activity(logged_in_client, draft_id)


def test_reopen_draft_trip_rejected(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)

    response = logged_in_client.post(f"{API}/trips/{trip['id']}/reopen")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "TRIP_NOT_FINALIZED"


def test_finalized_trip_can_still_be_deleted(logged_in_client: TestClient) -> None:
    trip = create_trip(logged_in_client)
    finalize(logged_in_client, trip)

    assert logged_in_client.delete(f"{API}/trips/{trip['id']}").status_code == 204
