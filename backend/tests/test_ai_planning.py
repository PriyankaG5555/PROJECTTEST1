"""AI day planning and activity duration — specs/ai-feature.md §8 (fake providers only)."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.services import ai_providers, suggestion_service
from app.services.ai_providers import LLMPlan, LLMPlanItem
from tests.helpers import API, add_activity, create_trip, finalize, first_draft_id, get_draft

PLACES = [
    {
        "id": "p-museum",
        "displayName": {"text": "Goa State Museum"},
        "rating": 4.3,
        "googleMapsUri": "https://maps.google.com/?cid=1",
    },
    {"id": "p-fort", "displayName": {"text": "Fort Aguada"}, "rating": 4.5},
    {"id": "p-casino", "displayName": {"text": "Casino Royale"}, "rating": 4.0},
]


def item(index: int | None, start: str, minutes: int, name: str | None = None) -> LLMPlanItem:
    return LLMPlanItem(
        candidate_index=index,
        must_visit_name=name,
        start_time=start,
        duration_minutes=minutes,
        reason="Good in the morning.",
    )


class FakeAI:
    """Replaces Claude and Google; records what the planner sent."""

    def __init__(self) -> None:
        self.plan = LLMPlan(items=[item(0, "10:00", 120), item(1, "13:00", 90)])
        self.contexts: list[dict[str, Any]] = []
        self.fail = False

    def __call__(self, context: dict[str, Any]) -> LLMPlan:
        self.contexts.append(context)
        if self.fail:
            raise ai_providers.ProviderUnavailable("down")
        return self.plan


@pytest.fixture
def ai(monkeypatch: pytest.MonkeyPatch) -> FakeAI:
    fake = FakeAI()
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_llm_provider", "anthropic")
    monkeypatch.setattr(settings, "ai_llm_api_key", "test-key")
    monkeypatch.setattr(settings, "google_places_api_key", "test-key")
    monkeypatch.setattr(ai_providers, "plan_with_llm", fake)
    monkeypatch.setattr(suggestion_service, "fetch_places", lambda query, key: PLACES)
    return fake


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


def test_existing_activities_without_duration_still_work(logged_in_client: TestClient) -> None:
    draft_id = first_draft_id(create_trip(logged_in_client))
    add_activity(logged_in_client, draft_id, time="09:30")

    assert (
        get_draft(logged_in_client, draft_id)["days"][0]["activities"][0]["durationMinutes"] is None
    )


# ---------- Generate ----------
def test_generate_returns_grounded_schedule(logged_in_client: TestClient, ai: FakeAI) -> None:
    trip = create_trip(logged_in_client, topPriority="budget", budget=5000)

    response = plan(logged_in_client, trip, interests=["museums"], avoid=["casino"])

    assert response.status_code == 200, response.text
    body = response.json()
    first = body["activities"][0]
    assert first == {
        "itemId": "item-1",
        "destinationName": "Goa State Museum",
        "time": "10:00",
        "durationMinutes": 120,
        "cost": None,
        "placeId": "p-museum",
        "verified": True,
        "reason": "Good in the morning.",
        "source": "Google Places",
        "attribution": "Powered by Google",
        "mapsUrl": "https://maps.google.com/?cid=1",
    }
    assert body["proposalToken"] and body["validUntil"]
    assert any("not verified" in w for w in body["warnings"])
    sent = ai.contexts[0]
    assert [c["name"] for c in sent["candidates"]] == [
        "Goa State Museum",
        "Fort Aguada",
    ]  # casino avoided
    assert sent["top_priority"] == "budget" and sent["budget_inr"] == 5000
    assert sent["interests"] == ["museums"]
    assert (
        get_draft(logged_in_client, first_draft_id(trip))["days"][0]["activities"] == []
    )  # no mutation


def test_must_visit_items_are_unverified(logged_in_client: TestClient, ai: FakeAI) -> None:
    ai.plan = LLMPlan(items=[item(None, "11:00", 60, name="Aunty's Cafe")])
    trip = create_trip(logged_in_client)

    body = plan(logged_in_client, trip, mustVisit=["Aunty's Cafe"]).json()

    assert body["activities"][0]["verified"] is False
    assert body["activities"][0]["placeId"] is None


@pytest.mark.parametrize(
    "bad_plan",
    [
        LLMPlan(items=[item(None, "10:00", 60, name="Invented Palace")]),  # not grounded
        LLMPlan(items=[item(7, "10:00", 60)]),  # bad candidate index
        LLMPlan(items=[item(0, "08:00", 60)]),  # before window
        LLMPlan(items=[item(0, "17:30", 60)]),  # past window
        LLMPlan(items=[item(0, "10:00", 120), item(1, "11:00", 60)]),  # overlap
        LLMPlan(items=[item(0, "10:00", 5)]),  # unrealistic duration
    ],
)
def test_invalid_llm_output_is_rejected(
    logged_in_client: TestClient, ai: FakeAI, bad_plan: LLMPlan
) -> None:
    ai.plan = bad_plan
    trip = create_trip(logged_in_client)

    response = plan(logged_in_client, trip)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "AI_PLANNING_UNAVAILABLE"


def test_existing_activities_are_fixed_constraints(
    logged_in_client: TestClient, ai: FakeAI
) -> None:
    trip = create_trip(logged_in_client)
    draft_id = first_draft_id(trip)
    add_activity(logged_in_client, draft_id, time="10:30", durationMinutes=60)
    add_activity(logged_in_client, draft_id, time="16:00")  # no duration -> blocks rest of window

    assert plan(logged_in_client, trip).status_code == 503  # 10:00-12:00 overlaps 10:30-11:30
    sent = ai.contexts[0]["fixed_busy_blocks"]
    assert sent == [{"start": "10:30", "end": "11:30"}, {"start": "16:00", "end": "18:00"}]

    ai.plan = LLMPlan(items=[item(0, "12:00", 120)])
    body = plan(logged_in_client, trip).json()
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
    logged_in_client: TestClient, ai: FakeAI, body: dict[str, Any], field: str
) -> None:
    response = plan(logged_in_client, create_trip(logged_in_client), **body)

    assert response.status_code == 400
    assert field in response.json()["error"]["details"]["fields"]


def test_generate_access_rules(
    logged_in_client: TestClient, other_user_client: TestClient, ai: FakeAI
) -> None:
    goa = create_trip(logged_in_client)
    jaipur = create_trip(logged_in_client, destination="Jaipur")

    assert plan(other_user_client, goa).status_code == 404
    assert plan(logged_in_client, goa, draftId=first_draft_id(jaipur)).status_code == 404
    finalize(logged_in_client, goa)
    assert plan(logged_in_client, goa).json()["error"]["code"] == "TRIP_FINALIZED"


def test_unavailable_and_limits(
    logged_in_client: TestClient, ai: FakeAI, monkeypatch: pytest.MonkeyPatch
) -> None:
    trip = create_trip(logged_in_client)
    ai.fail = True
    assert plan(logged_in_client, trip).status_code == 503

    ai.fail = False
    monkeypatch.setattr(get_settings(), "ai_plan_daily_limit", 2)
    assert plan(logged_in_client, trip).status_code == 200  # 2nd request today
    assert plan(logged_in_client, trip).json()["error"]["code"] == "RATE_LIMITED"

    monkeypatch.setattr(get_settings(), "ai_llm_provider", None)
    assert plan(logged_in_client, trip).json()["error"]["code"] == "AI_PLANNING_UNAVAILABLE"


# ---------- Apply ----------
def test_apply_selected_items_once(logged_in_client: TestClient, ai: FakeAI) -> None:
    trip = create_trip(logged_in_client)
    draft_id = first_draft_id(trip)
    token = plan(logged_in_client, trip).json()["proposalToken"]

    response = apply(logged_in_client, draft_id, token, ["item-2"])

    assert response.status_code == 201
    added = response.json()["activities"]
    assert [(a["destinationName"], a["time"], a["durationMinutes"], a["cost"]) for a in added] == [
        ("Fort Aguada", "13:00", 90, None)
    ]
    assert len(get_draft(logged_in_client, draft_id)["days"][0]["activities"]) == 1
    again = apply(logged_in_client, draft_id, token, ["item-1"])
    assert again.status_code == 409 and again.json()["error"]["code"] == "AI_PROPOSAL_INVALID"


def test_apply_out_of_date_adds_nothing(logged_in_client: TestClient, ai: FakeAI) -> None:
    trip = create_trip(logged_in_client)
    draft_id = first_draft_id(trip)
    token = plan(logged_in_client, trip).json()["proposalToken"]
    add_activity(
        logged_in_client, draft_id, time="10:30", durationMinutes=30
    )  # edit after generation

    response = apply(logged_in_client, draft_id, token, ["item-1", "item-2"])

    assert response.status_code == 409
    assert len(get_draft(logged_in_client, draft_id)["days"][0]["activities"]) == 1


def test_apply_rejects_wrong_draft_user_or_token(
    logged_in_client: TestClient, other_user_client: TestClient, ai: FakeAI
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


def test_apply_blocked_when_finalized(logged_in_client: TestClient, ai: FakeAI) -> None:
    trip = create_trip(logged_in_client)
    token = plan(logged_in_client, trip).json()["proposalToken"]
    finalize(logged_in_client, trip)

    response = apply(logged_in_client, first_draft_id(trip), token, ["item-1"])

    assert response.json()["error"]["code"] == "TRIP_FINALIZED"
