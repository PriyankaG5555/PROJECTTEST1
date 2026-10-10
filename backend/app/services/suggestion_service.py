"""Activity suggestions from the Google Places API (New) — backend-spec.md §7, contract §5.

Called only on request, never stored (Google terms), limited per user per day.
"""

import json
import logging
import math
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import literal
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_engine
from app.errors import AppError
from app.models import SuggestionUsage, Trip, TripPriority, User
from app.services.ownership import get_owned_trip

logger = logging.getLogger("app.suggestions")

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join(
    f"places.{f}"
    for f in (
        "id",
        "displayName",
        "formattedAddress",
        "rating",
        "userRatingCount",
        "priceLevel",
        "googleMapsUri",
    )
)
MAX_RESULTS = 10
DAILY_LIMIT = 30
TIMEOUT_SECONDS = 8
PRICE_LEVELS = {
    "PRICE_LEVEL_FREE": "free",
    "PRICE_LEVEL_INEXPENSIVE": "inexpensive",
    "PRICE_LEVEL_MODERATE": "moderate",
    "PRICE_LEVEL_EXPENSIVE": "expensive",
    "PRICE_LEVEL_VERY_EXPENSIVE": "very_expensive",
}
PRICE_RANK = {"free": 0, "inexpensive": 1, "moderate": 2, "expensive": 3, "very_expensive": 4}


def unavailable() -> AppError:
    return AppError(
        "SUGGESTIONS_UNAVAILABLE", 503, "Suggestions aren't available right now. Please try later."
    )


def fetch_places(destination: str, api_key: str) -> list[dict[str, Any]]:
    """Raw Google Text Search results. Separate function so tests can replace it."""
    body = json.dumps(
        {
            "textQuery": f"top tourist attractions in {destination}",
            "maxResultCount": MAX_RESULTS,
            "languageCode": "en",
        }
    ).encode()
    request = urllib.request.Request(
        PLACES_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
        places: list[dict[str, Any]] = json.load(response).get("places", [])
        return places


def normalize(place: dict[str, Any]) -> dict[str, Any]:
    return {
        "place_id": place.get("id", ""),
        "name": (place.get("displayName") or {}).get("text", ""),
        "address": place.get("formattedAddress"),
        "rating": place.get("rating"),
        "rating_count": place.get("userRatingCount"),
        "price_level": PRICE_LEVELS.get(place.get("priceLevel", "")),
        "maps_url": place.get("googleMapsUri"),
    }


def order(places: list[dict[str, Any]], priority: TripPriority | None) -> list[dict[str, Any]]:
    """Order by the trip's top priority (goal-spec F8/F11)."""

    def rating(p: dict[str, Any]) -> float:
        return float(p["rating"] or 0)

    if (
        priority is TripPriority.BUDGET
    ):  # cheapest first; unknown price sits between cheap and moderate
        key = lambda p: (PRICE_RANK.get(p["price_level"], 1.5), -rating(p))  # noqa: E731
    elif priority is TripPriority.DESTINATIONS:  # must-see: good rating backed by many reviews
        key = lambda p: (0, -rating(p) * math.log10((p["rating_count"] or 0) + 10))  # noqa: E731
    else:
        key = lambda p: (0, -rating(p))  # noqa: E731
    return sorted(places, key=key)


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
    with get_engine().begin() as conn:  # own transaction: counts even if Google fails
        count = conn.execute(upsert).scalar_one()
    if count > DAILY_LIMIT:
        raise AppError(
            "RATE_LIMITED",
            429,
            f"You've used today's {DAILY_LIMIT} suggestion requests. Try tomorrow.",
        )


def suggestions_for(db: Session, user: User, trip_id: str) -> tuple[Trip, list[dict[str, Any]]]:
    trip = get_owned_trip(db, trip_id, user)
    api_key = get_settings().google_places_api_key
    if not api_key:
        raise unavailable()
    _count_request(user)
    try:
        raw = fetch_places(trip.destination, api_key)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        logger.warning("google places failed", extra={"error": type(exc).__name__})
        raise unavailable() from None
    places = [normalize(p) for p in raw if p.get("displayName")]
    return trip, order(places, trip.top_priority)
