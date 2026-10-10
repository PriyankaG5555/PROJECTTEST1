"""Rule-based day planner (no LLM) — ranking and scheduling rules in ai-feature.md §5."""

import math
from dataclasses import dataclass, field
from typing import Any

from app.models import TripPriority

DURATIONS = {
    "Museum": 120,
    "Gallery": 90,
    "Fort": 90,
    "Castle": 90,
    "Palace": 90,
    "Archaeological site": 60,
    "Ruins": 60,
    "Monument": 30,
    "Memorial": 30,
    "Viewpoint": 30,
    "Attraction": 60,
    "Zoo": 150,
    "Aquarium": 90,
    "Theme park": 180,
    "Beach": 120,
    "Nature reserve": 90,
    "Garden": 60,
    "Park": 60,
    "Place of worship": 45,
    "Waterfall": 120,
    "Lake": 60,
    "Landmark": 30,
    "Historic site": 60,
    "Market": 60,
}
DEFAULT_DURATION = 60
HISTORY = {
    "Fort",
    "Castle",
    "Palace",
    "Monument",
    "Memorial",
    "Ruins",
    "Archaeological site",
    "Museum",
    "Historic site",
}
NATURE = {"Park", "Garden", "Nature reserve", "Beach", "Viewpoint", "Waterfall", "Lake"}
INTEREST_KEYWORDS: list[tuple[str, set[str]]] = [
    ("museum", {"Museum", "Gallery"}),
    ("art", {"Gallery", "Museum"}),
    ("histor", HISTORY),
    ("heritage", HISTORY),
    ("fort", {"Fort", "Castle"}),
    ("beach", {"Beach"}),
    ("waterfall", {"Waterfall"}),
    ("lake", {"Lake"}),
    ("market", {"Market"}),
    ("shop", {"Market"}),
    ("sea", {"Beach"}),
    ("nature", NATURE),
    ("park", {"Park", "Garden"}),
    ("garden", {"Garden", "Park"}),
    ("view", {"Viewpoint"}),
    ("sunset", {"Viewpoint", "Beach"}),
    ("temple", {"Place of worship"}),
    ("church", {"Place of worship"}),
    ("mosque", {"Place of worship"}),
    ("relig", {"Place of worship"}),
    ("spiritual", {"Place of worship"}),
    ("kid", {"Zoo", "Aquarium", "Theme park", "Park"}),
    ("family", {"Zoo", "Aquarium", "Theme park", "Park"}),
    ("wildlife", {"Zoo", "Nature reserve"}),
    ("animal", {"Zoo", "Aquarium"}),
]
SPEED_KMH = 25
TRAVEL_BUFFER = 10
UNKNOWN_TRAVEL = 15  # between stops when one has no map location
SLOT = 5
NEAREST_OF = 4  # after the first stop, pick the nearest of the next 4 ranked places

Interval = tuple[int, int]


@dataclass
class PlannedItem:
    name: str
    start: int
    duration: int
    place: dict[str, Any] | None
    reason: str


@dataclass
class Plan:
    items: list[PlannedItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def distance_km(a: dict[str, Any], b: dict[str, Any]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a["lat"], a["lon"], b["lat"], b["lon"]))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 6371 * 2 * math.asin(math.sqrt(h))


def travel_minutes(a: dict[str, Any] | None, b: dict[str, Any] | None) -> int:
    if a is None or b is None:
        return UNKNOWN_TRAVEL
    raw = distance_km(a, b) / SPEED_KMH * 60 + TRAVEL_BUFFER
    return math.ceil(raw / SLOT) * SLOT


def interest_categories(interests: list[str]) -> dict[str, str]:
    """category -> the traveller's interest that matched it."""
    matched: dict[str, str] = {}
    for interest in interests:
        low = interest.lower()
        for keyword, categories in INTEREST_KEYWORDS:
            if keyword in low:
                for c in categories:
                    matched.setdefault(c, interest)
    return matched


def _round_up(minutes: int) -> int:
    return math.ceil(minutes / SLOT) * SLOT


def earliest_slot(
    earliest: int, duration: int, window: Interval, taken: list[Interval]
) -> int | None:
    t = _round_up(max(earliest, window[0]))
    while t + duration <= window[1]:
        clash = next((b for b in sorted(taken) if t < b[1] and b[0] < t + duration), None)
        if clash is None:
            return t
        t = _round_up(clash[1])
    return None


def plan_day(
    places: list[dict[str, Any]],
    *,
    must_visit: list[str],
    avoid: list[str],
    interests: list[str],
    priority: TripPriority | None,
    window: Interval,
    busy: list[Interval],
) -> Plan:
    avoid_low = [a.lower() for a in avoid]
    pool = [p for p in places if not any(a in p["name"].lower() for a in avoid_low)]
    wanted = interest_categories(interests)
    plan = Plan()

    # Must-visit: match to a map place when possible, otherwise keep as unverified.
    must: list[tuple[str, dict[str, Any] | None]] = []
    for name in must_visit:
        low = name.lower()
        match = next(
            (p for p in pool if low in p["name"].lower() or p["name"].lower() in low), None
        )
        if match is not None:
            pool.remove(match)
        must.append((match["name"] if match else name, match))

    def rank(p: dict[str, Any]) -> tuple[int, int, str]:
        bonus = 2 if p["category"] in wanted else 0
        if priority is TripPriority.BUDGET:
            return (0 if p["free"] else 1, -(p["notability"] + bonus), p["name"])
        return (0, -(p["notability"] + bonus), p["name"])

    # Stay within the planner's busy-day threshold (more than 4 activities is flagged).
    limit = 3 if priority is TripPriority.TIME else 4
    ranked = sorted(pool, key=rank)[: limit * 2]
    taken = list(busy)
    current, prev = window[0], None
    queue: list[tuple[str, dict[str, Any] | None, bool]] = [(n, p, True) for n, p in must]
    others = [(p["name"], p, False) for p in ranked]

    while (queue or others) and len(plan.items) < max(limit, len(must)) and len(plan.items) < 10:
        if queue:
            name, place, is_must = queue.pop(0)
        elif prev is not None:
            # Nearest of the next few best places (Time priority: nearest of all) - less travel.
            anchor = prev
            shortlist = len(others) if priority is TripPriority.TIME else NEAREST_OF
            best = min(
                range(min(shortlist, len(others))),
                key=lambda k: distance_km(anchor, others[k][1]) if others[k][1] else 1e9,
            )
            name, place, is_must = others.pop(best)
        else:
            name, place, is_must = others.pop(0)
        duration = DURATIONS.get(place["category"], DEFAULT_DURATION) if place else DEFAULT_DURATION
        travel = travel_minutes(prev, place) if plan.items else 0
        start = earliest_slot(current + travel, duration, window, taken)
        if start is None:
            if is_must:
                plan.warnings.append(f"Couldn't fit “{name}” in this time window.")
            continue
        parts = [place["category"] if place else "Your must-visit place"]
        if is_must and place:
            parts.append("your must-visit place")
        if place and place["free"]:
            parts.append("free to visit")
        if place and place["notability"] >= 4:
            parts.append("well-known place")
        if place and place["category"] in wanted:
            parts.append(f"matches “{wanted[place['category']]}”")
        if plan.items and prev is not None and place is not None:
            parts.append(f"{distance_km(prev, place):.1f} km from the previous stop")
        plan.items.append(PlannedItem(name, start, duration, place, " · ".join(parts)))
        taken.append((start, start + duration))
        current, prev = start + duration, place if place else prev
    plan.items.sort(key=lambda i: i.start)
    return plan
