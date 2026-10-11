"""Hotel suggestions from OpenStreetMap Nominatim (accommodation-feature.md §3). Free, keyless."""

import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, literal, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import telemetry
from app.db import get_engine
from app.errors import AppError
from app.models import PlaceCache, SuggestionUsage, Trip, TripPriority, User
from app.services import osm_service, suggestion_service
from app.services.ownership import get_owned_trip
from app.services.planner_service import distance_km

TYPES = ("hotel", "guest house", "hostel")
# Not places a traveller can book: institutional or generic entries in OSM.
EXCLUDE_WORDS = (
    "student",
    "department",
    "government",
    "staff",
    "employee",
    "officers",
    "boys",
    "girls",
    "prison",
    "university",
    "college",
    "hospital",
    "railway",
    "police",
    "army",
    "navy",
)
GENERIC_NAMES = {"hotel", "guest house", "guesthouse", "hostel", "lodge", "resort", "home stay"}
KINDS = {
    "hotel": "hotel",
    "guest_house": "guest_house",
    "hostel": "hostel",
    "motel": "motel",
    "apartment": "apartment",
    "chalet": "apartment",
    "resort": "resort",
}
BUDGET_ORDER = {"hostel": 0, "guest_house": 1, "motel": 2, "apartment": 3, "hotel": 4, "resort": 5}
MAX_RESULTS = 15
CACHE_DAYS = 7


def _stars(extratags: dict[str, str]) -> int | None:
    raw = (extratags.get("stars") or "").strip()[:1]
    return int(raw) if raw.isdigit() and 1 <= int(raw) <= 7 else None


def normalize(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Nominatim search results -> accommodations, deduplicated by OSM id."""
    hotels: dict[str, dict[str, Any]] = {}
    for r in results:
        kind = KINDS.get(r.get("type", ""))
        if r.get("category") not in ("tourism", "leisure", "building") or kind is None:
            continue
        name = (r.get("name") or "").strip()
        low = name.lower()
        if not name or low in GENERIC_NAMES or any(w in low for w in EXCLUDE_WORDS):
            continue
        extra = r.get("extratags") or {}
        osm_id = f"osm:{r['osm_type']}/{r['osm_id']}"
        address = ", ".join(r.get("display_name", "").split(", ")[1:3]) or None
        hotels[osm_id] = {
            "place_id": osm_id,
            "name": name[:100],
            "kind": "resort" if "resort" in name.lower() and kind == "hotel" else kind,
            "stars": _stars(extra),
            "address": address[:200] if address else None,
            "website": extra.get("website") or extra.get("contact:website"),
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            "maps_url": f"https://www.openstreetmap.org/{r['osm_type']}/{r['osm_id']}",
        }
    return list(hotels.values())


def fetch_hotels(destination: str) -> list[dict[str, Any]]:
    """Live Nominatim lookups within the destination's area (fair use: ~1 request/second).

    Tests replace this function.
    """
    found = osm_service.nominatim_search(destination)
    if not found:
        return []
    south, north, west, east = (float(x) for x in found[0]["boundingbox"])
    results: list[dict[str, Any]] = []
    for kind in TYPES:
        time.sleep(1)
        results += osm_service.nominatim_search(
            kind, limit=50, extratags=True, viewbox=f"{west},{north},{east},{south}"
        )
    return normalize(results)


def hotels_for(db: Session, destination: str) -> list[dict[str, Any]]:
    key = ("hotels:" + destination.strip().lower())[:100]
    cached = db.scalar(
        select(PlaceCache.places).where(
            PlaceCache.destination_key == key,
            PlaceCache.fetched_at > func.now() - timedelta(days=CACHE_DAYS),
        )
    )
    if cached is not None:
        return list(cached)
    hotels = fetch_hotels(destination)
    db.execute(
        insert(PlaceCache)
        .values(destination_key=key, places=hotels, fetched_at=func.now())
        .on_conflict_do_update(
            index_elements=[PlaceCache.destination_key],
            set_={"places": hotels, "fetched_at": func.now()},
        )
    )
    return hotels


def order(
    hotels: list[dict[str, Any]], priority: TripPriority | None, places: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    notable = [p for p in places[:10] if "lat" in p]
    centre = (
        {
            "lat": sum(p["lat"] for p in notable) / len(notable),
            "lon": sum(p["lon"] for p in notable) / len(notable),
        }
        if notable
        else None
    )
    for h in hotels:
        h["distance_km"] = round(distance_km(h, centre), 1) if centre else None

    def near_notable(h: dict[str, Any]) -> float:
        return min((distance_km(h, p) for p in notable), default=0.0)

    if priority is TripPriority.BUDGET:
        key: Any = lambda h: (BUDGET_ORDER.get(h["kind"], 9), h["stars"] or 0, h["name"])  # noqa: E731
    elif priority is TripPriority.DESTINATIONS and notable:
        key = lambda h: (near_notable(h), h["name"])  # noqa: E731
    elif priority is TripPriority.TIME and centre:
        key = lambda h: (h["distance_km"], h["name"])  # noqa: E731
    else:
        key = lambda h: (-(h["stars"] or 0), h["name"])  # noqa: E731
    return sorted(hotels, key=key)


def _count(user: User) -> None:
    upsert = (
        insert(SuggestionUsage)
        .values(user_id=user.id, day=datetime.now(UTC).date(), count=1)
        .on_conflict_do_update(
            index_elements=[SuggestionUsage.user_id, SuggestionUsage.day],
            set_={"count": SuggestionUsage.count + literal(1)},
        )
        .returning(SuggestionUsage.count)
    )
    with get_engine().begin() as conn:
        count = conn.execute(upsert).scalar_one()
    if count > suggestion_service.DAILY_LIMIT:
        raise AppError(
            "RATE_LIMITED", 429, "You've used today's suggestion requests. Try tomorrow."
        )


def hotel_suggestions(db: Session, user: User, trip_id: str) -> tuple[Trip, list[dict[str, Any]]]:
    trip = get_owned_trip(db, trip_id, user)
    _count(user)
    with telemetry.tracer.start_as_current_span("hotels.fetch") as span:
        try:
            hotels = hotels_for(db, trip.destination)
            places = osm_service.places_for(db, trip.destination)
        except osm_service.OSMUnavailable:
            raise suggestion_service.unavailable() from None
        span.set_attribute("gy.results", len(hotels))
    info = osm_service.resolve_destination(db, trip.destination) if telemetry.enabled() else None
    telemetry.HOTELS.add(1, telemetry.destination_attrs(info, trip.destination))
    return trip, order(hotels, trip.top_priority, places)[:MAX_RESULTS]
