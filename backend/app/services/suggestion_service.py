"""Places to visit near the destination, from OpenStreetMap (goal-spec F11, contract §5).

Free and keyless; cached 7 days per destination; limited per user per day.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import literal
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import telemetry
from app.db import get_engine
from app.errors import AppError
from app.models import SuggestionUsage, Trip, TripPriority, User
from app.services import osm_service
from app.services.ownership import get_owned_trip

MAX_RESULTS = 10
DAILY_LIMIT = 30


def unavailable() -> AppError:
    return AppError(
        "SUGGESTIONS_UNAVAILABLE", 503, "Suggestions aren't available right now. Please try later."
    )


def order(places: list[dict[str, Any]], priority: TripPriority | None) -> list[dict[str, Any]]:
    """Budget: free places first; otherwise most notable first (goal-spec F8/F11)."""
    if priority is TripPriority.BUDGET:
        return sorted(places, key=lambda p: (not p["free"], -p["notability"], p["name"]))
    return sorted(places, key=lambda p: (-p["notability"], p["name"]))


def to_suggestion(place: dict[str, Any]) -> dict[str, Any]:
    return {
        "place_id": place["place_id"],
        "name": place["name"],
        "category": place["category"],
        "address": place["address"],
        "rating": None,
        "rating_count": None,
        "price_level": "free" if place["free"] else None,
        "maps_url": place["url"],
    }


def _count_request(user: User) -> None:
    upsert = (
        insert(SuggestionUsage)
        .values(user_id=user.id, day=datetime.now(UTC).date(), count=1)
        .on_conflict_do_update(
            index_elements=[SuggestionUsage.user_id, SuggestionUsage.day],
            set_={"count": SuggestionUsage.count + literal(1)},
        )
        .returning(SuggestionUsage.count)
    )
    with get_engine().begin() as conn:  # own transaction: counts even if the map lookup fails
        count = conn.execute(upsert).scalar_one()
    if count > DAILY_LIMIT:
        raise AppError(
            "RATE_LIMITED",
            429,
            f"You've used today's {DAILY_LIMIT} suggestion requests. Try tomorrow.",
        )


def suggestions_for(db: Session, user: User, trip_id: str) -> tuple[Trip, list[dict[str, Any]]]:
    trip = get_owned_trip(db, trip_id, user)
    _count_request(user)
    try:
        places = osm_service.places_for(db, trip.destination)
    except osm_service.OSMUnavailable:
        raise unavailable() from None
    info = osm_service.resolve_destination(db, trip.destination) if telemetry.enabled() else None
    telemetry.SUGGESTIONS.add(1, telemetry.destination_attrs(info, trip.destination))
    return trip, [to_suggestion(p) for p in order(places, trip.top_priority)[:MAX_RESULTS]]
